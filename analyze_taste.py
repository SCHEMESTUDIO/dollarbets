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

# Import cluster classification from scanner
from scanner import classify_quip, ALL_QUIPS

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OVERRIDES_PATH = os.path.join(DATA_DIR, "quip-overrides.json")
STYLE_GUIDE_PATH = os.path.join(DATA_DIR, "style-guide.json")
CUSTOM_CLUSTERS_PATH = os.path.join(DATA_DIR, "custom-clusters.json")

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
    """Format overrides into a readable block for Claude, with cluster classification."""
    lines = []
    for i, o in enumerate(overrides):
        editor_quip = o["editor_quip"]
        cluster = classify_quip(editor_quip)
        lines.append(
            f'{i+1}. Bet: "{o["title"]}" '
            f'(category: {o.get("category", "n/a")}, '
            f'tier: {o.get("tier", "n/a")}, '
            f'payout: ${o.get("payout", "?")})\n'
            f'   AI wrote: "{o["original_quip"]}"\n'
            f'   Editor changed to: "{editor_quip}"\n'
            f'   Auto-classified cluster: {cluster}'
        )
    return "\n\n".join(lines)


def get_cluster_summary():
    """Build a summary of existing quip clusters and their sizes."""
    clusters = {}
    for q in ALL_QUIPS:
        label = classify_quip(q)
        clusters.setdefault(label, []).append(q)

    lines = []
    for label in sorted(clusters.keys()):
        examples = clusters[label][:3]
        example_str = ", ".join(f'"{e}"' for e in examples)
        lines.append(f"  {label} ({len(clusters[label])} quips) — e.g. {example_str}")
    return "\n".join(lines)


def analyze_taste(overrides, existing_guide=None):
    """Call Claude to extract editorial meta-patterns from overrides."""
    if not ANTHROPIC_API_KEY:
        print("[taste] No ANTHROPIC_API_KEY, cannot analyze", file=sys.stderr)
        return None

    overrides_text = format_overrides_for_analysis(overrides)
    cluster_summary = get_cluster_summary()

    existing_section = ""
    if existing_guide and existing_guide.get("principles"):
        existing_section = f"""
The current style guide has these principles (refine, merge, or replace as needed based on new evidence):
{json.dumps(existing_guide['principles'], indent=2)}
"""

    prompt = f"""You are analyzing editorial decisions made by the editors of Dollar Bets, a daily prediction market discovery board with a Craigslist/Drudge Report aesthetic and dry internet humor.

Below are cases where an editor rejected the AI-generated quip and replaced it with their own. Your job is to:
1. Extract *meta-patterns* — editorial techniques and principles behind these corrections
2. Review the cluster classification for each editor quip and recommend updates

EDITOR CORRECTIONS (each includes its auto-classified cluster):
{overrides_text}

EXISTING QUIP CLUSTERS (used for daily tone-anchor sampling):
{cluster_summary}
{existing_section}
Analyze these corrections and produce a JSON object with this structure:

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
  "voice_notes": "2-3 sentences describing the overall editorial voice",
  "cluster_review": [
    {{
      "editor_quip": "the exact editor quip text",
      "auto_cluster": "what classify_quip assigned",
      "recommended_cluster": "the cluster it actually belongs in (existing or new)",
      "rationale": "why, if the auto-classification was wrong or a new cluster is needed"
    }}
  ],
  "new_clusters": [
    {{
      "id": "proposed-cluster-id",
      "description": "What this cluster captures that no existing cluster does",
      "keywords": ["keyword1", "keyword2"],
      "evidence_quips": ["editor quips that would belong here"]
    }}
  ]
}}

Rules:
- Extract TECHNIQUES, not specific quips. "Use topical cultural references" not "use 'shake it off'"
- A pattern needs at least 2 supporting corrections to be included
- Be specific about when a technique applies (category, payout tier, bet type)
- The "avoid" section is just as important — what do editors consistently reject?
- If a correction is clearly a one-off creative choice (not a repeatable pattern), skip it
- Keep principles to 10 or fewer — quality over quantity
- voice_notes should capture the personality, not just the rules
- cluster_review: include EVERY editor quip. If auto_cluster is correct, set recommended_cluster to the same value and rationale to "correct"
- new_clusters: only propose a new cluster if 2+ editor quips share a voice pattern not captured by existing clusters. Include keywords that could power keyword-based classification
- If "general_wit" is assigned to an editor quip, that's the catch-all — check if it truly doesn't fit elsewhere or if a new cluster is warranted

Respond with ONLY the JSON object."""

    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 8192,
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
        with urllib.request.urlopen(req, timeout=120) as resp:
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
            n_principles = len(guide.get('principles', []))
            n_avoid = len(guide.get('avoid', []))
            n_new_clusters = len(guide.get('new_clusters', []))
            misclassified = [r for r in guide.get('cluster_review', [])
                            if r.get('auto_cluster') != r.get('recommended_cluster')]
            print(f"[taste] Extracted {n_principles} principles, "
                  f"{n_avoid} anti-patterns", file=sys.stderr)
            if misclassified:
                print(f"[taste] {len(misclassified)} quips need reclassification:", file=sys.stderr)
                for r in misclassified:
                    print(f"[taste]   '{r['editor_quip']}': "
                          f"{r['auto_cluster']} -> {r['recommended_cluster']} "
                          f"({r.get('rationale', '')})", file=sys.stderr)
            if n_new_clusters:
                print(f"[taste] {n_new_clusters} new cluster(s) proposed:", file=sys.stderr)
                for c in guide['new_clusters']:
                    print(f"[taste]   {c['id']}: {c['description']}", file=sys.stderr)
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

    # Auto-apply new clusters to custom-clusters.json
    new_clusters = guide.get("new_clusters", [])
    if new_clusters:
        # Load existing custom clusters (if any) and merge
        existing_custom = {}
        try:
            with open(CUSTOM_CLUSTERS_PATH) as f:
                existing_data = json.load(f)
            for c in existing_data.get("clusters", []):
                existing_custom[c["id"]] = c
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        added = 0
        for nc in new_clusters:
            cid = nc["id"]
            keywords = nc.get("keywords", [])
            if not keywords:
                print(f"[taste] Skipping cluster '{cid}' — no keywords", file=sys.stderr)
                continue
            existing_custom[cid] = {
                "id": cid,
                "description": nc.get("description", ""),
                "keywords": keywords,
                "added_at": guide["meta"]["generated_at"],
                "evidence_quips": nc.get("evidence_quips", []),
            }
            added += 1

        if added:
            custom_data = {
                "meta": {
                    "updated_at": guide["meta"]["generated_at"],
                    "note": "Auto-generated by taste analysis. Custom clusters are checked first by classify_quip().",
                },
                "clusters": list(existing_custom.values()),
            }
            with open(CUSTOM_CLUSTERS_PATH, "w") as f:
                json.dump(custom_data, f, indent=2)
                f.write("\n")
            print(f"[taste] Wrote {added} new cluster(s) to {CUSTOM_CLUSTERS_PATH} "
                  f"({len(existing_custom)} total custom clusters)", file=sys.stderr)
        else:
            print("[taste] No new clusters with valid keywords to apply", file=sys.stderr)
    else:
        print("[taste] No new clusters proposed", file=sys.stderr)


if __name__ == "__main__":
    main()
