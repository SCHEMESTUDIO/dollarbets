#!/usr/bin/env python3
"""Fee maths for /kalshi-payout-calculator/ against Kalshi's own General Trading Fees Table
(fee schedule effective July 7, 2026), plus the display helpers on /best-kalshi-bets-today/.

  python3 tests/test_best_kalshi.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generate_best_kalshi as g

# price -> (fee for 1 contract, fee for 100 contracts), as printed by Kalshi
TABLE = {0.01: (0.01, 0.07), 0.05: (0.01, 0.34), 0.10: (0.01, 0.63), 0.15: (0.01, 0.90), 0.20: (0.02, 1.12), 0.25: (0.02, 1.32)}
for p, (one, hundred) in TABLE.items():
    assert g.fee(1, p) == one, (p, g.fee(1, p), one)
    assert g.fee(100, p) == hundred, (p, g.fee(100, p), hundred)
assert g.fee(400, 0.25) == 5.25          # the worked example in the page copy
assert g.fee(100, 0.50) == 1.75
assert g.fee(100, 0.50, mult=0) == 0     # resting order on a market with no maker fee
assert g.fee(100, 0.50, rate=g.MAKER_RATE) == 0.44
assert g.cents(0.25) == "25¢" and g.cents(0.947) == "94.7¢"
assert g.pays(0.25) == "$4.00" and g.pays(0.005) == "$200"
head, out = g.names({"event_title": "BYU vs Kansas", "title": "BYU wins", "yes_label": "BYU"})
assert (head, out) == ("BYU vs Kansas", "BYU")
rows = [{"event_ticker": "A", "v": 1}, {"event_ticker": "A", "v": 2}, {"event_ticker": "B", "v": 3}]
assert [r["v"] for r in g.one_per_event(rows, 5)] == [1, 3]
print("ok: kalshi fee table, display helpers")
