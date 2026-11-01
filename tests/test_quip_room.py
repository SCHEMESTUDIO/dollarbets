#!/usr/bin/env python3
"""Offline checks for the quip room (no network).

Run from the repo root:
    python3 tests/test_quip_room.py

Covers api/quips.py's pure helpers (verdict validation, the record, applying his lines
to the board, override rows, re-save replacement) and scripts/quip_lessons.py's
templated lesson text and scoreboard bookkeeping.
"""
import copy
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SITE, "scripts"))


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SITE, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


quips = load("quips_api", "api/quips.py")
lessons = load("quip_lessons", "scripts/quip_lessons.py")

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
        print("FAIL:", msg)


def expect_error(fn, needle):
    try:
        fn()
    except quips.VerdictError as e:
        check(needle in str(e), f"wrong error for {needle!r}: {e}")
        return
    check(False, f"expected VerdictError mentioning {needle!r}")


BOARD = {
    "generated_at": "2026-11-01T00:44:56+00:00",
    "quip_pipeline": "v2",
    "board": [
        {"ticker": "A-1", "title": "Harvard ruling affirmed", "category": "Politics", "payout": 1.61,
         "tier": "green", "platform": "kalshi", "quip": "harvard line",
         "quip_alts": [{"quip": "harvard line", "mode": 5, "score": 8.5},
                       {"quip": "yale praying", "mode": 7, "score": 7},
                       {"quip": "crimson stays liquid", "mode": 9, "score": 4}]},
        {"ticker": "B-2", "title": "Boston snow", "category": "Weather", "payout": 2.94,
         "tier": "green", "platform": "polymarket", "quip": "affleck photo",
         "quip_alts": [{"quip": "market basket fistfight", "mode": 1, "score": 8.5},
                       {"quip": "affleck photo", "mode": 8, "score": 8.5}]},
        {"ticker": "C-3", "title": "RFK leaves", "category": "Politics", "payout": 5.56,
         "tier": "yellow", "platform": "polymarket", "quip": "podcast by spring",
         "quip_alts": [{"quip": "podcast by spring", "mode": 1, "score": 9},
                       {"quip": "the worm resigns too", "mode": 9, "score": 8}]},
        {"ticker": "D-4", "title": "Moon landing", "category": "Science", "payout": 30.3,
         "tier": "red", "platform": "kalshi", "quip": "buzz aldrin punches",
         "quip_alts": [{"quip": "buzz aldrin punches", "mode": 8, "score": 9},
                       {"quip": "flag with a QR code", "mode": 1, "score": 8}]},
    ],
}
VERDICTS = {
    "A-1": {"pick": "ship"},
    "B-2": {"pick": "alt", "alt": 0},
    "C-3": {"pick": "tweak", "edit": "podcast circuit by spring, supplement line by fall"},
    "D-4": {"pick": "mine", "edit": "flag with a QR code and a gift shop"},
}

# 1. validation: every market needs a verdict and each pick its material
norm = quips.normalise_verdicts(BOARD["board"], VERDICTS)
check([v["pick"] for v in norm] == ["ship", "alt", "tweak", "mine"], "normalised picks wrong")
expect_error(lambda: quips.normalise_verdicts(BOARD["board"], {k: v for k, v in VERDICTS.items() if k != "D-4"}), "no verdict for Moon landing")
expect_error(lambda: quips.normalise_verdicts(BOARD["board"], {**VERDICTS, "C-3": {"pick": "tweak", "edit": "  "}}), "needs the line")
expect_error(lambda: quips.normalise_verdicts(BOARD["board"], {**VERDICTS, "C-3": {"pick": "mine", "edit": "podcast by spring"}}), "unchanged")
expect_error(lambda: quips.normalise_verdicts(BOARD["board"], {**VERDICTS, "B-2": {"pick": "alt", "alt": 9}}), "not on Boston snow")
expect_error(lambda: quips.normalise_verdicts(BOARD["board"], {**VERDICTS, "B-2": {"pick": "alt", "alt": 1}}), "tick 'ship'")
expect_error(lambda: quips.normalise_verdicts(BOARD["board"], {**VERDICTS, "A-1": {"pick": "yes"}}), "no verdict for")
expect_error(lambda: quips.normalise_verdicts(BOARD["board"], []), "object keyed by ticker")

# 2. the record
rec = quips.build_record("2026-11-01", copy.deepcopy(BOARD), VERDICTS, now="2026-11-01T09:00:00+00:00")
check(rec["counts"] == {"ship": 1, "alt": 1, "tweak": 1, "mine": 1}, f"counts wrong: {rec['counts']}")
by = {m["ticker"]: m for m in rec["markets"]}
check(by["A-1"]["final"] == "harvard line" and by["A-1"]["shipped_score"] == 8.5 and by["A-1"]["shipped_mode"] == 5, "ship record wrong")
check(by["B-2"]["final"] == "market basket fistfight" and by["B-2"]["alt_score"] == 8.5 and by["B-2"]["alt_index"] == 0, "alt record wrong")
check(by["C-3"]["final"].startswith("podcast circuit") and by["C-3"]["edit"] == by["C-3"]["final"], "tweak record wrong")
check(len(by["D-4"]["candidates"]) == 2, "candidates not carried")
check(quips.commit_message(rec) == "quip room: verdicts 2026-11-01 (1 ship, 1 tweak, 1 alt, 1 mine)", quips.commit_message(rec))

# 3. applying to the board: his lines go live, the machine's line is kept, alts untouched
applied = quips.apply_record(copy.deepcopy(BOARD), rec)
am = {m["ticker"]: m for m in applied["board"]}
check(am["A-1"]["quip"] == "harvard line" and "quip_machine" not in am["A-1"] and am["A-1"]["quip_verdict"] == "ship", "ship apply wrong")
check(am["B-2"]["quip"] == "market basket fistfight" and am["B-2"]["quip_machine"] == "affleck photo", "alt apply wrong")
check(am["D-4"]["quip"].startswith("flag with a QR code and") and am["D-4"]["quip_machine"] == "buzz aldrin punches", "mine apply wrong")
check(all(len(m["quip_alts"]) == len(o["quip_alts"]) for m, o in zip(applied["board"], BOARD["board"])), "quip_alts changed")
check(applied["quip_reviewed_at"] == "2026-11-01T09:00:00+00:00", "reviewed stamp missing")

# 4. a re-review compares against the machine's line, not the earlier edit
rec2 = quips.build_record("2026-11-01", copy.deepcopy(applied), {**VERDICTS, "D-4": {"pick": "ship"}}, now="x")
check({m["ticker"]: m["shipped"] for m in rec2["markets"]}["D-4"] == "buzz aldrin punches", "re-review lost the machine line")
check({m["ticker"]: m["final"] for m in rec2["markets"]}["D-4"] == "buzz aldrin punches", "re-review ship should restore the machine line")
reapplied = quips.apply_record(copy.deepcopy(applied), rec2)
check("quip_machine" not in {m["ticker"]: m for m in reapplied["board"]}["D-4"], "quip_machine should clear when he ships the machine line again")

# 5. override rows: only his own words, and a re-save replaces the earlier rows
rows = quips.override_rows(rec)
check([r["verdict"] for r in rows] == ["tweak", "mine"], f"override rows wrong: {rows}")
check(rows[0]["original_quip"] == "podcast by spring" and rows[0]["source"] == "quip-room-2026-11-01", "override row shape wrong")
existing = [{"date": "2026-09-16", "editor_quip": "old", "source": "quip-room-2026-09-16"},
            {"date": "2026-11-01", "editor_quip": "stale", "source": "quip-room-2026-11-01"}]
merged = quips.merge_overrides(existing, rec)
check(len(merged) == 3 and merged[0]["editor_quip"] == "old" and "stale" not in [m["editor_quip"] for m in merged], "merge did not replace the earlier save")
capped = quips.merge_overrides([{"source": "x"}] * 600, rec)
check(len(capped) == quips.OVERRIDES_CAP, "overrides cap not applied")

# 6. lessons: facts text per verdict kind, scoreboard, replacement on re-run
L = {"meta": {"scoreboard": {}, "reviewed_dates": []}, "lessons": [{"date": "2026-09-16", "ticker": "Z", "text": "old lesson"}]}
new = lessons.ingest(L, rec, write_principles=False)
check(len(new) == 3, f"expected 3 lessons (no lesson for a ship), got {len(new)}")
texts = {e["ticker"]: e["text"] for e in new}
check(texts["B-2"] == 'Boston snow. Shipped (scored 8.5): "affleck photo". He took the candidate scored 8.5, "market basket fistfight", instead.', texts["B-2"])
check(texts["C-3"].startswith('RFK leaves. Shipped (scored 9): "podcast by spring". He reworded it to "podcast circuit'), texts["C-3"])
check('built his line from a candidate scored 8, "flag with a QR code"' in texts["D-4"], texts["D-4"])
check(L["meta"]["scoreboard"]["2026-11-01"] == {"ship": 1, "tweak": 1, "alt": 1, "mine": 1}, "scoreboard not written")
check(L["meta"]["reviewed_dates"] == ["2026-11-01"], "reviewed_dates not written")
lessons.ingest(L, rec, write_principles=False)
check(sum(1 for l in L["lessons"] if l["date"] == "2026-11-01") == 3 and L["lessons"][0]["text"] == "old lesson", "re-run duplicated lessons")

# 7. the judge prompt renders the new lessons (they carry 'text' like the old ones)
sys.path.insert(0, SITE)
os.chdir(SITE)
import scanner  # noqa: E402
block = scanner._v2_lessons_block()
check(block.startswith("- "), "lessons block broke")

# 8. the page and the rewrite exist
check(os.path.exists(os.path.join(SITE, "src", "admin", "quips", "index.html")), "quip room page missing")
with open(os.path.join(SITE, "vercel.json")) as f:
    check('"/api/quips"' in f.read(), "vercel.json has no /api/quips rewrite")

if failures:
    print(f"{len(failures)} check(s) failed")
    sys.exit(1)
print("test_quip_room: all checks passed")
