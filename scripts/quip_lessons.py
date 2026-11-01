#!/usr/bin/env python3
"""Turn the editor's quip-room verdicts into judge lessons.

    python3 scripts/quip_lessons.py                # every verdict file not yet in the lessons
    python3 scripts/quip_lessons.py 2026-11-01     # one board (re-runs replace that date's lessons)
    python3 scripts/quip_lessons.py --dry-run      # print, write nothing

Reads data/quip-verdicts/<date>.json (written by /api/quips when the editor saves a
review) and appends one lesson per market he changed (tweak / alt / mine) to
data/quip-lessons.json, which prompts/quip-judge.md renders as {{LESSONS}}. A lesson is
the facts (what shipped, its score, what he did) plus one sentence on the principle,
written by Claude in the voice of the existing lessons; if the API is unavailable the
facts ship alone. Markets he shipped as is get no lesson, since the judge already
agrees with him there and the lessons block only carries the last twenty.

Also keeps meta.scoreboard (ship / tweak / alt / mine per board) and meta.reviewed_dates.
Runs in .github/workflows/quip-lessons.yml on every push that touches data/quip-verdicts/.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
VERDICT_DIR = os.path.join(SITE, "data", "quip-verdicts")
LESSONS_PATH = os.path.join(SITE, "data", "quip-lessons.json")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-5"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MODES = {1: "invented consequence", 2: "confession", 3: "dumb enthusiasm", 4: "impression",
         5: "the bet's own number", 6: "sideways comparison", 7: "unfair at a place",
         8: "shared reference", 9: "deadpan tag"}


def _score(s):
    return "unscored" if s is None else f"scored {s:g}" if isinstance(s, (int, float)) else f"scored {s}"


def _toks(s):
    return set(re.findall(r"[a-z0-9']+", (s or "").lower()))


def closest_candidate(market):
    """The candidate his own line most overlaps with, if the overlap is real."""
    mine = _toks(market["final"])
    best, best_r = None, 0.0
    for c in market.get("candidates") or []:
        if c["quip"] == market["shipped"]:
            continue
        ct = _toks(c["quip"])
        if not ct or not mine:
            continue
        r = len(ct & mine) / len(ct | mine)
        if r > best_r:
            best, best_r = c, r
    return best if best_r >= 0.3 else None


def candidate_mode(market):
    """The mode of the line he chose: the alt's, the tweaked line's, or the mode of
    the candidate his own line is closest to ('his own' when it is nobody's)."""
    if market["pick"] == "alt":
        return MODES.get(market.get("alt_mode"), market.get("alt_mode") or "unknown")
    if market["pick"] == "tweak":
        return MODES.get(market.get("shipped_mode"), market.get("shipped_mode") or "unknown") + " (same line, reworded)"
    base = closest_candidate(market)
    if base:
        return MODES.get(base.get("mode"), base.get("mode") or "unknown") + " (built from a candidate)"
    return "his own, matching no candidate"


def facts(market):
    """The templated half of a lesson: what shipped and what he did."""
    title = market["title"].rstrip(".")
    head = f'{title}. Shipped ({_score(market["shipped_score"])}): "{market["shipped"]}".'
    pick = market["pick"]
    if pick == "tweak":
        return f'{head} He reworded it to "{market["final"]}".'
    if pick == "alt":
        return (f'{head} He took the candidate {_score(market["alt_score"])}, '
                f'"{market["final"]}", instead.')
    base = closest_candidate(market)
    if base:
        return (f'{head} He built his line from a candidate {_score(base["score"])}, '
                f'"{base["quip"]}", and shipped "{market["final"]}".')
    return f'{head} He wrote "{market["final"]}".'


def principle(market, examples):
    """One sentence from Claude on why his line beat the machine's. Empty on any failure."""
    if not ANTHROPIC_API_KEY:
        return ""
    cands = "\n".join(f'  [{i}] ({MODES.get(c.get("mode"), c.get("mode"))}, {_score(c.get("score"))}) {c["quip"]}'
                      for i, c in enumerate(market.get("candidates") or []))
    shown = "\n".join(f"- {e}" for e in examples[-3:]) or "- (none yet)"
    rejected_mode = MODES.get(market.get("shipped_mode"), market.get("shipped_mode") or "unknown")
    chosen = candidate_mode(market)
    prompt = f"""You write the calibration notes for the judge that scores Dollar Bets quips. Each note is the facts of one market followed by ONE sentence stating the principle the editor's choice reveals, in the voice of these earlier notes:

{shown}

THIS MARKET
{facts(market)}
He REJECTED the shipped line, whose mode was: {rejected_mode}.
He CHOSE a line whose mode is: {chosen}.
All candidates the judge scored:
{cands}

Write only the one principle sentence. Plain words a sub-editor would use, no metaphors of your own, no hedging, no em dashes, under 30 words. It must be about the line he chose over the line he rejected: what the chosen one does that the rejected one did not (a shared reference, a cut, the bet's number, a picture instead of a named emotion, a flat tag, a meaner angle, a sillier one). Never praise the rejected line's mode. Do not restate the facts."""
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 200,
        "thinking": {"type": "disabled"},
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"Content-Type": "application/json", "x-api-key": ANTHROPIC_API_KEY,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"[lessons] principle call failed: {e}", file=sys.stderr)
        return ""
    text = "".join(b.get("text", "") for b in result.get("content") or [] if b.get("type") == "text").strip()
    text = text.replace("—", ",").replace(" -- ", ", ").strip().strip('"')
    if not text or len(text.split()) > 45:
        return ""
    return text if text.endswith((".", "!", "?")) else text + "."


def lesson_text(market, examples):
    why = principle(market, examples)
    return f"{facts(market)} {why}".strip()


def load_lessons():
    with open(LESSONS_PATH) as f:
        return json.load(f)


def save_lessons(data):
    with open(LESSONS_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def verdict_dates():
    if not os.path.isdir(VERDICT_DIR):
        return []
    return sorted(n[:-5] for n in os.listdir(VERDICT_DIR) if n.endswith(".json") and DATE_RE.match(n[:-5]))


def ingest(data, record, write_principles=True):
    """Fold one verdict record into the lessons data. Returns the new lessons."""
    date = record["date"]
    meta = data.setdefault("meta", {})
    counts = record.get("counts") or {}
    meta.setdefault("scoreboard", {})[date] = {k: counts.get(k, 0) for k in ("ship", "tweak", "alt", "mine")}
    lessons = data.setdefault("lessons", [])
    # A re-run for the same date replaces its lessons.
    data["lessons"] = lessons = [l for l in lessons if l.get("date") != date]
    examples = [l["text"] for l in lessons]
    new = []
    for m in record["markets"]:
        if m["pick"] == "ship":
            continue
        text = lesson_text(m, examples) if write_principles else facts(m)
        entry = {"date": date, "ticker": m["ticker"], "verdict": m["pick"], "text": text}
        lessons.append(entry)
        examples.append(text)
        new.append(entry)
    reviewed = meta.setdefault("reviewed_dates", [])
    if date not in reviewed:
        reviewed.append(date)
        reviewed.sort()
    meta["updated_at"] = datetime.now(timezone.utc).date().isoformat()
    return new


def main(argv):
    dry = "--dry-run" in argv
    dates = [a for a in argv if DATE_RE.match(a)]
    data = load_lessons()
    done = set(data.get("meta", {}).get("reviewed_dates") or [])
    if not dates:
        dates = [d for d in verdict_dates() if d not in done]
    if not dates:
        print("[lessons] nothing to ingest")
        return 0
    total = 0
    for date in dates:
        path = os.path.join(VERDICT_DIR, f"{date}.json")
        if not os.path.exists(path):
            print(f"[lessons] no verdict file for {date}", file=sys.stderr)
            continue
        with open(path) as f:
            record = json.load(f)
        new = ingest(data, record, write_principles=not dry)
        c = record.get("counts") or {}
        print(f"[lessons] {date}: {c.get('ship', 0)} ship / {c.get('tweak', 0)} tweak / "
              f"{c.get('alt', 0)} alt / {c.get('mine', 0)} mine -> {len(new)} lesson(s)")
        for e in new:
            print("   -", e["text"])
        total += len(new)
    if dry:
        print("[lessons] dry run, nothing written")
        return 0
    save_lessons(data)
    print(f"[lessons] wrote {total} lesson(s) to {LESSONS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
