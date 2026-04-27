#!/usr/bin/env python3
"""
Dollar Bets — Editorial Taste Analyzer

Reads editor quip overrides and distills them into a living style guide.
The style guide captures *meta-patterns* — editorial techniques and
principles — not specific quips to reuse.

Run weekly via GitHub Actions. Outputs data/style-guide.json.

Example patterns it might extract:
  - "Editors like topical song/lyric references for culturally relevant bets"
  - "Editors prefer dry understatement over exclamation for political markets"
  - "Editors avoid literal keyword matches — a crypto bet doesn't need a crypto quip"
"""

import json
import os
import sys
import urllib.request
import urllib.error

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OVERRIDES_PATH = os.path.join(DATA_DIR, "quip-overrides.json")
STYLE_GUIDE_PATH = os.path.join(DATA_DIR, "style-guide.json")

# Minimum overrides needed before we can extract meaningful patterns
MIN_OVERRIDES = 5


def load_overrides():
    """Load editor quip overrides."""
    try:
        with open(OVERRIDES_PATH) as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return []


def load_existing_guide():
    """Load the current style guide (if any) so the analyzer can refine it."""
    try:
        with open(STYLE_GUIDE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def format_overrides_for_analysis(overrides):
    """Format overrides into a readable block for Claude."""
    lines = []
    for i, o in enumerate(overrides):
        lines.append(
            f'{i+1}. Bet: "{o["title"]}" '
            f'(category: {o.get("category", "n/a")}, '
            f'tier: {o.get("tier", "n/a")}, '
            f'payout: ${o.get("payout", "?")})\n'
            f'   AI wrote: "{o["original_quip"]}"\n'
            f'   Editor changed to: "{o["editor_quip"]}"'
        )
    return "\n\n".join(lines)


def analyze_taste(overrides, existing_guide=None):
    """Call Claude to extract editorial meta-patterns from overrides."""
    if not ANTHROPIC_API_KEY:
        print("[taste] No ANTHROPIC_API_KEY, cannot analyze", file=sys.stderr)
        return None

    overrides_text = format_overrides_for_analysis(overrides)

    existing_section = ""
    if existing_guide and existing_guide.get("principles"):
        existing_section = f"""
The current style guide has these principles (refine, merge, or replace as needed based on new evidence):
{json.dumps(existing_guide['principles'], indent=2)}
"""

    prompt = f"""You are analyzing editorial decisions made by the editors of Dollar Bets, a daily prediction market discovery board with a Craigslist/Drudge Report aesthetic and dry internet humor.

Below are cases where an editor rejected the AI-generated quip and replaced it with their own. Your job is to extract the *meta-patterns* — the editorial techniques and principles behind these corrections, NOT the specific quips themselves.

EDITOR CORRECTIONS:
{overrides_text}
{existing_section}
Analyze these corrections and produce a style guide as a JSON object with this structure:

{{
  "principles": [
    {{
      "id": "short-kebab-case-id",
      "principle": "One-sentence description of the editorial principle",
      "technique": "How to apply this when writing quips",
      "examples_for": ["categories or bet types this applies to"],
      "evidence_count": <number of overrides that demonstrate this pattern>
    }}
  ],
  "avoid": [
    {{
      "id": "short-kebab-case-id",
      "pattern": "Description of what NOT to do",
      "why": "Why editors consistently reject this"
    }}
  ],
  "voice_notes": "2-3 sentences describing the overall editorial voice as demonstrated by these corrections"
}}

Rules:
- Extract TECHNIQUES, not specific quips. "Use topical cultural references" not "use 'shake it off'"
- A pattern needs at least 2 supporting corrections to be included
- Be specific about when a technique applies (category, payout tier, bet type)
- The "avoid" section is just as important — what do editors consistently reject?
- If a correction is clearly a one-off creative choice (not a repeatable pattern), skip it
- Keep principles to 10 or fewer — quality over quantity
- voice_notes should capture the personality, not just the rules

Respond with ONLY the JSON object."""

    body = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        print("[taste] Calling Claude for taste analysis...", file=sys.stderr)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            result = json.loads(raw)
            text = result["content"][0]["text"].strip()

            # Strip markdown fences if present
            if text.startswith("```"):
                import re
                text = re.sub(r'^```\w*\n?', '', text)
                text = re.sub(r'\n?```$', '', text)
                text = text.strip()

            guide = json.loads(text)
            print(f"[taste] Extracted {len(guide.get('principles', []))} principles, "
                  f"{len(guide.get('avoid', []))} anti-patterns", file=sys.stderr)
            return guide

    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else "no body"
        print(f"[taste] API error HTTP {e.code}: {err_body[:200]}", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"[taste] Failed to parse Claude response as JSON: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[taste] Analysis failed: {type(e).__name__}: {e}", file=sys.stderr)

    return None


def main():
    print("[taste] Loading editor overrides...", file=sys.stderr)
    overrides = load_overrides()
    print(f"[taste] Found {len(overrides)} overrides", file=sys.stderr)

    if len(overrides) < MIN_OVERRIDES:
        print(f"[taste] Need at least {MIN_OVERRIDES} overrides to extract patterns. "
              f"Have {len(overrides)}. Skipping.", file=sys.stderr)
        return

    existing_guide = load_existing_guide()
    if existing_guide:
        print(f"[taste] Existing style guide found — will refine", file=sys.stderr)

    guide = analyze_taste(overrides, existing_guide)
    if not guide:
        print("[taste] Analysis failed, keeping existing guide", file=sys.stderr)
        return

    # Add metadata
    from datetime import datetime, timezone
    guide["meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "override_count": len(overrides),
        "version": (existing_guide or {}).get("meta", {}).get("version", 0) + 1,
    }

    # Write style guide
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STYLE_GUIDE_PATH, "w") as f:
        json.dump(guide, f, indent=2)
        f.write("\n")

    print(f"[taste] Style guide written to {STYLE_GUIDE_PATH}", file=sys.stderr)
    print(f"[taste] Version {guide['meta']['version']}, "
          f"{len(guide.get('principles', []))} principles", file=sys.stderr)


if __name__ == "__main__":
    main()
