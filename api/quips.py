"""
Dollar Bets CMS — Quip Room endpoint

GET  /api/quips                  → the last 14 daily boards, each flagged reviewed or not
GET  /api/quips?date=YYYY-MM-DD  → that board (markets carry `quip_alts`) plus its
                                   verdict record if one exists
POST /api/quips                  → save the editor's verdicts for one board

A POST writes three files in ONE commit on the branch:
  data/quip-verdicts/<date>.json   the record: every market, what shipped, what he did
  data/boards/<date>.json          his lines go live (the site rebuilds from this file)
  data/quip-overrides.json         one row per market he rewrote (tweak / mine), the
                                   example set for the quip generator and judge
The push then runs .github/workflows/quip-lessons.yml, which writes a lesson per
changed market into data/quip-lessons.json (the judge's calibration).

Verdicts, one per market, keyed by ticker:
  {"pick": "ship"}                         the line shipped as is
  {"pick": "tweak", "edit": "..."}         his rewording of the shipped line
  {"pick": "alt",   "alt": 3}              a candidate from quip_alts was better
  {"pick": "mine",  "edit": "..."}         his own line
Every market on the board needs a verdict; a board is "reviewed" once its record exists.
Re-saving a reviewed board replaces its record and its override rows, and compares
against the machine's original line (`quip_machine`), never against an earlier edit.

Same env vars as api/board.py: CMS_PASSWORD, CMS_SECRET, GITHUB_TOKEN (a PAT, so the
push triggers workflows), GITHUB_REPO, GITHUB_BRANCH.
"""

from http.server import BaseHTTPRequestHandler
import base64
import hashlib
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


# ── Inline auth (Vercel runs each function in isolation) ──

CMS_PASSWORD = os.environ.get("CMS_PASSWORD", "")
CMS_SECRET = os.environ.get("CMS_SECRET", CMS_PASSWORD)


def verify_token(token):
    """Same one-UTC-day HMAC token as api/login.py and api/board.py."""
    if not CMS_PASSWORD or not token:
        return False
    today = str(int(time.time()) // 86400)
    expected = hmac.new(
        CMS_SECRET.encode(), f"{CMS_PASSWORD}:{today}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(token, expected)


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_API = "https://api.github.com"

BOARD_DIR = "data/boards"
VERDICT_DIR = "data/quip-verdicts"
OVERRIDES_PATH = "data/quip-overrides.json"
LIST_DAYS = 14
OVERRIDES_CAP = 500  # same cap as api/board.py

PICKS = ("ship", "tweak", "alt", "mine")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Pure helpers (no network; covered by tests/test_quip_room.py) ──

class VerdictError(ValueError):
    """A verdict payload the editor can fix: the message is shown on the page."""


def shipped_line(market):
    """The machine's line. After a review the board's `quip` is the editor's line
    and the machine's original sits in `quip_machine`."""
    return (market.get("quip_machine") or market.get("quip") or "").strip()


def candidate_for(market, line):
    """The quip_alts entry whose text is `line`, or None."""
    for a in market.get("quip_alts") or []:
        if (a.get("quip") or "").strip() == line:
            return a
    return None


def normalise_verdicts(board, verdicts):
    """Validate the editor's verdicts against the board. Returns a list aligned with
    the board: {"pick", "edit", "alt"} per market. Raises VerdictError."""
    if not isinstance(verdicts, dict):
        raise VerdictError("verdicts must be an object keyed by ticker")
    out = []
    for m in board:
        ticker = m.get("ticker")
        if not ticker:
            raise VerdictError("a market on this board has no ticker")
        v = verdicts.get(ticker)
        if not isinstance(v, dict) or v.get("pick") not in PICKS:
            raise VerdictError(f"no verdict for {m.get('title') or ticker}")
        pick = v["pick"]
        edit = (v.get("edit") or "").strip()
        alt = v.get("alt")
        alts = m.get("quip_alts") or []
        if pick in ("tweak", "mine"):
            if not edit:
                raise VerdictError(f"'{pick}' needs the line, on {m.get('title') or ticker}")
            if edit == shipped_line(m):
                raise VerdictError(f"'{pick}' is the shipped line unchanged, on {m.get('title') or ticker}")
            alt = None
        elif pick == "alt":
            try:
                alt = int(alt)
            except (TypeError, ValueError):
                raise VerdictError(f"'alt' needs a candidate, on {m.get('title') or ticker}")
            if not (0 <= alt < len(alts)):
                raise VerdictError(f"candidate {alt} is not on {m.get('title') or ticker}")
            if (alts[alt].get("quip") or "").strip() == shipped_line(m):
                raise VerdictError(f"that candidate is the shipped line, on {m.get('title') or ticker}; tick 'ship'")
            edit = ""
        else:
            edit, alt = "", None
        out.append({"pick": pick, "edit": edit, "alt": alt})
    return out


def final_line(market, verdict):
    """The line that goes live under this verdict."""
    pick = verdict["pick"]
    if pick == "ship":
        return shipped_line(market)
    if pick == "alt":
        return (market["quip_alts"][verdict["alt"]].get("quip") or "").strip()
    return verdict["edit"]


def build_record(date_str, board_data, verdicts, now=None):
    """The verdict record for data/quip-verdicts/<date>.json."""
    board = board_data.get("board") or []
    norm = normalise_verdicts(board, verdicts)
    now = now or datetime.now(timezone.utc).isoformat()
    markets, counts = [], {p: 0 for p in PICKS}
    for m, v in zip(board, norm):
        shipped = shipped_line(m)
        pick_c = candidate_for(m, shipped) or {}
        final = final_line(m, v)
        alt_c = m["quip_alts"][v["alt"]] if v["pick"] == "alt" else None
        counts[v["pick"]] += 1
        markets.append({
            "ticker": m.get("ticker"),
            "title": m.get("title", ""),
            "category": m.get("category", ""),
            "payout": m.get("payout"),
            "tier": m.get("tier", ""),
            "platform": m.get("platform", "kalshi"),
            "shipped": shipped,
            "shipped_score": pick_c.get("score"),
            "shipped_mode": pick_c.get("mode"),
            "pick": v["pick"],
            "final": final,
            "edit": v["edit"] or None,
            "alt_index": v["alt"],
            "alt_score": alt_c.get("score") if alt_c else None,
            "alt_mode": alt_c.get("mode") if alt_c else None,
            "candidates": [{"quip": (a.get("quip") or "").strip(), "mode": a.get("mode"),
                            "score": a.get("score")} for a in (m.get("quip_alts") or [])],
        })
    return {
        "date": date_str,
        "saved_at": now,
        "board_generated_at": board_data.get("generated_at"),
        "quip_pipeline": board_data.get("quip_pipeline"),
        "counts": counts,
        "markets": markets,
    }


def apply_record(board_data, record):
    """Put the editor's lines on the board. Keeps quip_alts; stores the machine's
    original in quip_machine; stamps quip_verdict on every market."""
    by_ticker = {r["ticker"]: r for r in record["markets"]}
    for m in board_data.get("board") or []:
        r = by_ticker.get(m.get("ticker"))
        if not r:
            continue
        machine = shipped_line(m)
        m["quip"] = r["final"]
        if r["final"] != machine:
            m["quip_machine"] = machine
        else:
            m.pop("quip_machine", None)
        m["quip_verdict"] = r["pick"]
    board_data["quip_reviewed_at"] = record["saved_at"]
    return board_data


def override_rows(record):
    """Rows for data/quip-overrides.json, the markets he rewrote in his own words.
    An 'alt' pick is a machine line he preferred; the verdict file and the lesson
    record it, and it never poses as an editor line."""
    rows = []
    for r in record["markets"]:
        if r["pick"] not in ("tweak", "mine"):
            continue
        rows.append({
            "date": record["date"],
            "title": r["title"],
            "category": r["category"],
            "payout": r["payout"],
            "tier": r["tier"],
            "original_quip": r["shipped"],
            "editor_quip": r["final"],
            "source": f"quip-room-{record['date']}",
            "verdict": r["pick"],
        })
    return rows


def merge_overrides(existing, record):
    """Replace any rows from an earlier save of the same board, append the new ones,
    keep the file capped like api/board.py does."""
    source = f"quip-room-{record['date']}"
    kept = [o for o in existing if o.get("source") != source]
    kept.extend(override_rows(record))
    if len(kept) > OVERRIDES_CAP:
        kept = kept[-OVERRIDES_CAP:]
    return kept


def commit_message(record):
    c = record["counts"]
    return (f"quip room: verdicts {record['date']} "
            f"({c['ship']} ship, {c['tweak']} tweak, {c['alt']} alt, {c['mine']} mine)")


# ── GitHub ──

def _gh_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DollarBets-CMS/1.0",
    }


def _gh(method, path, body=None, timeout=20):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = _gh_headers()
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _gh_contents(path):
    """Decoded file contents + sha, or (None, None) when absent."""
    try:
        r = _gh("GET", f"contents/{path}?ref={GITHUB_BRANCH}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None
        raise
    return base64.b64decode(r["content"]).decode(), r["sha"]


def _gh_listdir(path):
    try:
        r = _gh("GET", f"contents/{path}?ref={GITHUB_BRANCH}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise
    return [f.get("name", "") for f in r if isinstance(f, dict)]


class RefMoved(Exception):
    """The branch advanced between read and write; the editor should reload."""


def commit_files(files, message):
    """One commit carrying every file in `files` ({path: text}) on GITHUB_BRANCH,
    via the Git Data API. The ref update is fast-forward only, so a concurrent
    push raises RefMoved instead of overwriting it."""
    head = _gh("GET", f"git/ref/heads/{GITHUB_BRANCH}")["object"]["sha"]
    base_tree = _gh("GET", f"git/commits/{head}")["tree"]["sha"]
    tree = []
    for path, text in files.items():
        blob = _gh("POST", "git/blobs", {"content": text, "encoding": "utf-8"})
        tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    new_tree = _gh("POST", "git/trees", {"base_tree": base_tree, "tree": tree})["sha"]
    commit = _gh("POST", "git/commits", {"message": message, "tree": new_tree, "parents": [head]})
    try:
        _gh("PATCH", f"git/refs/heads/{GITHUB_BRANCH}", {"sha": commit["sha"], "force": False})
    except urllib.error.HTTPError as e:
        if e.code == 422:
            raise RefMoved() from e
        raise
    return commit["sha"]


def list_boards():
    """The last LIST_DAYS daily boards, newest first, with their review state."""
    dates = sorted((n[:-5] for n in _gh_listdir(BOARD_DIR) if DATE_RE.match(n[:-5] or "")), reverse=True)
    reviewed = {n[:-5] for n in _gh_listdir(VERDICT_DIR) if n.endswith(".json")}
    return [{"date": d, "reviewed": d in reviewed} for d in dates[:LIST_DAYS]]


def load_board(date_str):
    text, sha = _gh_contents(f"{BOARD_DIR}/{date_str}.json")
    if text is None:
        return None, None
    return json.loads(text), sha


def load_verdict(date_str):
    text, _ = _gh_contents(f"{VERDICT_DIR}/{date_str}.json")
    return json.loads(text) if text else None


def save_verdicts(date_str, board_sha, verdicts):
    """Validate, build the record, and write the three files in one commit."""
    board_data, sha = load_board(date_str)
    if board_data is None:
        raise VerdictError(f"no board for {date_str}")
    if board_sha and sha != board_sha:
        raise RefMoved()
    record = build_record(date_str, board_data, verdicts)
    overrides_text, _ = _gh_contents(OVERRIDES_PATH)
    try:
        existing = json.loads(overrides_text) if overrides_text else []
    except json.JSONDecodeError:
        existing = []
    if not isinstance(existing, list):
        existing = []
    merged = merge_overrides(existing, record)
    files = {
        f"{VERDICT_DIR}/{date_str}.json": json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        f"{BOARD_DIR}/{date_str}.json": json.dumps(apply_record(board_data, record), indent=2) + "\n",
        OVERRIDES_PATH: json.dumps(merged, indent=2) + "\n",
    }
    commit = commit_files(files, commit_message(record))
    return record, commit


# ── Handler ──

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not verify_token(self._get_token()):
            self._respond(401, {"error": "unauthorized"})
            return
        if not GITHUB_TOKEN or not GITHUB_REPO:
            self._respond(500, {"error": "GitHub not configured"})
            return
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        date_str = params.get("date", [None])[0]
        try:
            if not date_str:
                self._respond(200, {"boards": list_boards()})
                return
            if not DATE_RE.match(date_str):
                self._respond(400, {"error": "date must be YYYY-MM-DD"})
                return
            board_data, sha = load_board(date_str)
            if board_data is None:
                self._respond(404, {"error": f"no board for {date_str}"})
                return
            self._respond(200, {"date": date_str, "board_sha": sha, "board": board_data,
                                "verdict": load_verdict(date_str)})
        except urllib.error.HTTPError as e:
            self._respond(502, {"error": f"GitHub API error: {e.code}"})
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def do_POST(self):
        if not verify_token(self._get_token()):
            self._respond(401, {"error": "unauthorized"})
            return
        if not GITHUB_TOKEN or not GITHUB_REPO:
            self._respond(500, {"error": "GitHub not configured"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except (json.JSONDecodeError, ValueError):
            self._respond(400, {"error": "invalid json"})
            return
        date_str = body.get("date") or ""
        if not DATE_RE.match(date_str):
            self._respond(400, {"error": "date must be YYYY-MM-DD"})
            return
        try:
            record, commit = save_verdicts(date_str, body.get("board_sha"), body.get("verdicts"))
            self._respond(200, {"ok": True, "commit": commit, "counts": record["counts"],
                                "message": f"Verdicts for {date_str} saved. Rebuild triggered."})
        except VerdictError as e:
            self._respond(400, {"error": str(e)})
        except RefMoved:
            self._respond(409, {"error": "the board changed since you loaded it (a scan or another save). Reload and try again."})
        except urllib.error.HTTPError as e:
            detail = e.read().decode() if e.fp else ""
            self._respond(502, {"error": f"GitHub API error: {e.code}", "detail": detail[:500]})
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _get_token(self):
        auth = self.headers.get("Authorization", "")
        return auth[7:] if auth.startswith("Bearer ") else ""

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
