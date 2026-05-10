#!/usr/bin/env python3
"""Regression test for scanner.classify_quip and the keyword classifier.

Run from the site/ directory:
    python3 tests/test_classify.py

What it covers:
  1. RECALL — every editor override classifies to its LLM-recommended cluster,
     with a documented allowlist of known-misses (quips that have no shared
     lexical signature with any other quip and are handled at generation time
     via style-guide principles instead).
  2. SANITY — representative quips per cluster (one good, one bad/edge case)
     classify as expected.
  3. POOL DISTRIBUTION — ALL_QUIPS distribution stays within ±20% of the
     last-known-good snapshot, so a future change can't quietly collapse
     coverage back into general_wit.

Exit code 0 on success, 1 on any assertion failure.
"""
import json
import os
import sys
from collections import Counter

# Make scanner/analyze_taste importable when run from anywhere
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
sys.path.insert(0, SITE)

from scanner import classify_quip, ALL_QUIPS  # noqa: E402


# ── Known-miss allowlist ────────────────────────────────────────────────
# These editor quips were placed in a recommended_cluster by the LLM, but
# have no lexical signature shared with any other quip. We rely on the
# style-guide principles (e.g. commit-to-a-hot-take) to teach the generator
# the pattern, rather than forcing classify_quip to catch them.
KNOWN_MISSES = {
    "Toy Story 5 > The Odyssey": "general_wit",
    "if geopolitics was Catan, this is like blocking longest road with a port": "general_wit",
    # Editor typo ("thinks" instead of "things") — not worth a dedicated keyword
    "Crazier thinks have happened, truly": "general_wit",
}


# ── Sanity cases — representative quips per cluster ─────────────────────
# Format: (quip, expected_cluster). One canonical match per cluster, plus a
# few edge cases that have caused trouble historically.
SANITY_CASES = [
    # custom clusters (checked first)
    ("probably gravy", "dry_acceptance"),
    ("seen this one before", "dry_acceptance"),
    ("Stranger things have happened at this club", "dry_acceptance"),
    ("if Toy Story 5 doesn't clinch I'm going on hunger strike", "hot_take"),
    ("name a bigger company that exists out of pure spite", "hot_take"),

    # hardcoded specific-reference clusters
    ("60% of the time, it works every time", "film_tv_reference"),  # Anchorman
    ("this film was meant to be told in one part", "film_tv_reference"),
    ("are Spurs entering their Brat era", "music_reference"),  # Charli XCX
    ("I think it's gonna be a long, long time", "music_reference"),  # Rocket Man w/ comma
    ("Drone, drone on the range, where the militants play", "music_reference"),
    ("wikipedia page currently under construction", "internet_meme"),
    ("Money printer go brrrr", "internet_meme"),
    ("money ball, but make the ball also money", "books_history"),  # Moneyball w/ space

    # sports
    ("the eye test guys are assembling", "sports"),
    ("the most famous Cade in league history", "sports"),
    ("Alonso has waited 17 years", "sports"),
    ("short the club", "sports"),

    # tone clusters
    ("in other memecoin news, vending machines accept doge", "chaos_energy"),
    ("in other news: Al-Qaeda pivoting to champion green energy", "chaos_energy"),
    ("redeem the tears of crypto bros at your nearest bank branch", "chaos_energy"),
    ("a MacBook with opinions about your divorce", "chaos_energy"),
    ("fanboys writing congress as we speak", "internet_discourse"),
    ("back when i was a kid google searches were free", "person_has_opinion"),
    ("Could you pick your state rep out of a lineup?", "person_has_opinion"),
    ("just please on the day I bring an umbrella", "person_has_opinion"),
    ("you can still write in Will Ferrell on the ballot", "comedy_framing"),
    ("can't say you didn't see it coming", "understated"),
    ("more love for craft catering", "understated"),
    ("the man spent twenty years removing ports for this", "understated"),

    # negative cases — catch-all should still be possible for unsignatured quips
    ("Toy Story 5 > The Odyssey", "general_wit"),  # known miss, asserted explicitly
]


# ── Pool distribution snapshot ──────────────────────────────────────────
# Last-known-good as of 2026-05-10 after the keyword audit. Future runs
# should land within ±20% of these counts on each cluster. If a cluster
# moves outside the band, that's a signal something changed.
POOL_SNAPSHOT = {
    "general_wit": 128,
    "sports": 48,
    "meta_wager": 33,
    "internet_discourse": 24,
    "film_tv_reference": 20,
    "data_nerd": 17,
    "internet_meme": 17,
    "person_has_opinion": 14,
    "vibes_check": 12,
    "chaos_energy": 12,
    "music_reference": 11,
    "understated": 9,
    "comedy_framing": 8,
    "books_history": 7,
    "cosmic_vibes": 4,
    "dry_acceptance": 3,
}
POOL_TOLERANCE = 0.20  # ±20%


# ── Test runners ────────────────────────────────────────────────────────
class Failures:
    def __init__(self):
        self.items = []
    def add(self, msg):
        self.items.append(msg)
    def __bool__(self):
        return bool(self.items)


def test_recall_against_overrides(failures):
    """Every editor quip should classify to its LLM-recommended cluster,
    or be on the known-miss allowlist."""
    guide_path = os.path.join(SITE, "data", "style-guide.json")
    with open(guide_path) as f:
        review = json.load(f).get("cluster_review", [])

    misses = []
    for r in review:
        q = r["editor_quip"]
        rec = r["recommended_cluster"]
        actual = classify_quip(q)
        if actual == rec:
            continue
        # Allowed miss?
        if KNOWN_MISSES.get(q) == actual:
            continue
        misses.append((q, actual, rec))

    n_total = len(review)
    n_pass = n_total - len(misses)
    print(f"  recall: {n_pass}/{n_total} overrides classified correctly "
          f"(or on known-miss allowlist)")

    if misses:
        for q, actual, rec in misses:
            failures.add(f"recall: '{q[:50]}' classified as {actual}, "
                         f"expected {rec} (or add to KNOWN_MISSES)")


def test_sanity_cases(failures):
    """Representative quips classify as expected."""
    n_pass = 0
    for q, expected in SANITY_CASES:
        actual = classify_quip(q)
        if actual == expected:
            n_pass += 1
        else:
            failures.add(f"sanity: '{q[:50]}' → {actual}, expected {expected}")
    print(f"  sanity: {n_pass}/{len(SANITY_CASES)} representative quips correct")


def test_pool_distribution(failures):
    """ALL_QUIPS cluster sizes stay within tolerance of the snapshot."""
    counts = Counter(classify_quip(q) for q in ALL_QUIPS)
    drifted = []
    new_clusters = []

    for cluster, baseline in POOL_SNAPSHOT.items():
        actual = counts.get(cluster, 0)
        low = baseline * (1 - POOL_TOLERANCE)
        high = baseline * (1 + POOL_TOLERANCE)
        if actual < low or actual > high:
            drifted.append((cluster, baseline, actual))

    for cluster in counts:
        if cluster not in POOL_SNAPSHOT:
            new_clusters.append((cluster, counts[cluster]))

    print(f"  pool: {len(POOL_SNAPSHOT)} clusters checked against snapshot "
          f"(tolerance ±{int(POOL_TOLERANCE*100)}%)")

    for c, baseline, actual in drifted:
        failures.add(f"pool drift: {c} = {actual}, snapshot was {baseline} "
                     f"(outside ±{int(POOL_TOLERANCE*100)}% band)")
    for c, n in new_clusters:
        failures.add(f"pool: new cluster '{c}' ({n} quips) — update snapshot if intentional")


def main():
    print("Running classifier regression tests...")
    failures = Failures()

    print("\n[1/3] Override recall")
    test_recall_against_overrides(failures)

    print("\n[2/3] Sanity cases")
    test_sanity_cases(failures)

    print("\n[3/3] Pool distribution snapshot")
    test_pool_distribution(failures)

    print()
    if failures:
        print(f"FAIL — {len(failures.items)} assertion(s) failed:")
        for msg in failures.items:
            print(f"  ✗ {msg}")
        sys.exit(1)
    else:
        print("PASS — all classifier tests green.")
        sys.exit(0)


if __name__ == "__main__":
    main()
