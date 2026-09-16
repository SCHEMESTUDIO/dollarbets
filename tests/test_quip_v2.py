#!/usr/bin/env python3
"""Offline checks for the v2 quip pipeline (no network).

Run from the site/ directory:
    python3 tests/test_quip_v2.py

Covers: the SSE parser, the prompt files and their placeholders, the editor-example
filter, and the v1 fallback when the API key is missing.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
sys.path.insert(0, SITE)

import scanner  # noqa: E402

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
        print("FAIL:", msg)


# 1. SSE parser collects text deltas, stop reason and usage; ignores junk
stream = "\n\n".join([
    'event: message_start\ndata: {"type":"message_start","message":{"usage":{"input_tokens":12}}}',
    'event: content_block_start\ndata: {"type":"content_block_start","content_block":{"type":"thinking"}}',
    'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"thinking_delta","thinking":"hmm"}}',
    'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"text_delta","text":"[{\\"n\\": 1"}}',
    'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"text_delta","text":", \\"x\\": 2}]"}}',
    'event: ping\ndata: {"type":"ping"}',
    'data: not json at all',
    'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":9}}',
])
text, stop, usage = scanner._v2_parse_sse(stream)
check(text == '[{"n": 1, "x": 2}]', f"sse text mismatch: {text!r}")
check(stop == "end_turn", f"sse stop mismatch: {stop!r}")
check(usage.get("input_tokens") == 12 and usage.get("output_tokens") == 9, f"sse usage mismatch: {usage}")

# 2. Prompt files exist and the judge template carries its placeholders
persona = scanner._v2_read_prompt("quip-persona.md")
judge = scanner._v2_read_prompt("quip-judge.md")
check("TITLE REWRITING RULES" in persona, "persona prompt lacks title rules")
check("YES_RESOLVES_TO" in persona, "persona prompt lacks the YES_RESOLVES_TO rule")
for ph in ("{{LESSONS}}", "{{EXAMPLES}}", "{{CONTRASTS}}"):
    check(ph in judge, f"judge prompt lacks {ph}")

# 3. Lessons render, and the rendered judge prompt has no placeholders left
lessons = scanner._v2_lessons_block()
check(lessons.startswith("- "), "lessons block empty")
rendered = (judge.replace("{{LESSONS}}", lessons)
            .replace("{{EXAMPLES}}", scanner._v2_examples_block(scanner._v2_editor_examples(), 30))
            .replace("{{CONTRASTS}}", scanner._v2_contrast_block(scanner._v2_editor_examples(), 10)))
check("{{" not in rendered, "rendered judge prompt still has a placeholder")

# 4. Editor examples exclude pool anchors and trims
ex = scanner._v2_editor_examples()
check(len(ex) >= 60, f"expected >=60 editor examples, got {len(ex)}")
pool = {q.lower() for q in scanner.ALL_QUIPS}
check(all(o["editor_quip"].strip().lower() not in pool for o in ex), "a pool quip leaked into editor examples")
check(any("Matt Damon" in o["editor_quip"] for o in ex), "2026-09-12 verdict lines missing from overrides")

# 5. Without an API key, v2 hands the board back unchanged (v1 also no-ops without a key)
saved = scanner.ANTHROPIC_API_KEY
scanner.ANTHROPIC_API_KEY = ""
board = [{"title": "Will X happen?", "payout": 5.0, "tier": "yellow", "quip": "placeholder", "ticker": "T-1"}]
out = scanner.generate_quips_v2([dict(b) for b in board])
check(out[0]["quip"] == "placeholder" and "quip_alts" not in out[0], "v2 without a key should be a no-op")
scanner.ANTHROPIC_API_KEY = saved

if failures:
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1)
print("test_quip_v2: all checks passed")
