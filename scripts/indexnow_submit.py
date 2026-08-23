#!/usr/bin/env python3
"""
IndexNow submitter — change-gated.

Replaces the old build.sh block, which blind-POSTed an arbitrary
`find public -name index.html | head -100` slice to IndexNow on EVERY build
(~3x/day, since Daily Board Scan fires the Vercel deploy hook after each of
its three commits) regardless of whether a single byte had changed.

How the gate works
------------------
1. Hash every generated page under public/ (sha256 of the file bytes).
2. Fetch the manifest published by the PREVIOUS deploy from the live site.
   public/ is gitignored, so the live copy is the only available baseline.
3. Submit only URLs that are new or whose hash changed.
4. Write the new manifest into public/ so it ships with this deploy and
   becomes the next build's baseline.

Fail-closed by design: if the previous manifest cannot be fetched, we cannot
tell what changed, so we seed the manifest and submit NOTHING. A skipped
submission costs nothing; resubmitting the whole site three times a day is
the bug being fixed here.

If a submission fails, the PREVIOUS manifest is written back unchanged, so the
next build recomputes the same diff and retries rather than silently losing it.

Never fails the build: every error path is a warning and the exit code is
always 0. Stdlib only, matching scripts/gsc_pull.py's zero-dependency policy.

Usage:
    python3 scripts/indexnow_submit.py [--dry-run] [--public-dir public]
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

SITE_URL = os.environ.get("INDEXNOW_SITE_URL", "https://www.dollarbets.lol")
HOST = SITE_URL.split("://", 1)[-1].strip("/")
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "d0b1e5f7a3c94e8b")
MANIFEST_NAME = "indexnow-manifest.json"
ENDPOINT = "https://api.indexnow.org/indexnow"

# IndexNow accepts up to 10,000 URLs per request.
MAX_URLS = 10000
# Above this, something regenerated far more than expected (template change,
# global date stamp, wiped baseline). Still submitted, but called out loudly.
SANITY_WARN = 200

UA = "DollarBets-IndexNow/1.0"


def log(msg):
    print(f"[indexnow] {msg}", file=sys.stderr)


def url_path_for(rel_path):
    """public/foo/index.html -> /foo/ ; public/index.html -> /"""
    parts = rel_path.replace(os.sep, "/")
    if parts.endswith("index.html"):
        parts = parts[: -len("index.html")]
    if not parts.startswith("/"):
        parts = "/" + parts
    return parts


def build_manifest(public_dir):
    """Map every generated page to a content hash."""
    urls = {}
    for dirpath, _dirnames, filenames in os.walk(public_dir):
        for fn in filenames:
            if fn != "index.html":
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, public_dir)
            try:
                with open(full, "rb") as f:
                    digest = hashlib.sha256(f.read()).hexdigest()
            except OSError as e:
                log(f"WARNING: could not read {full}: {e}")
                continue
            urls[url_path_for(rel)] = digest
    return urls


def fetch_previous():
    """Fetch the last deploy's manifest. Returns dict of url->hash, or None."""
    url = f"{SITE_URL}/{MANIFEST_NAME}"
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": UA}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log("no previous manifest on the live site (first gated build)")
        else:
            log(f"WARNING: manifest fetch failed: HTTP {e.code}")
        return None
    except Exception as e:
        log(f"WARNING: manifest fetch failed: {e}")
        return None

    urls = data.get("urls")
    if not isinstance(urls, dict):
        log("WARNING: previous manifest has unexpected shape — ignoring")
        return None
    return urls


def diff(current, previous):
    """URLs that are new or whose content hash changed, sorted."""
    return sorted(u for u, h in current.items() if previous.get(u) != h)


def submit(urls):
    payload = json.dumps(
        {
            "host": HOST,
            "key": INDEXNOW_KEY,
            "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt",
            "urlList": [f"{SITE_URL}{u}" for u in urls],
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": UA},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            log(f"submitted {len(urls)} URL(s) — HTTP {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        log(f"WARNING: submission rejected: HTTP {e.code} {e.reason}")
        return False
    except Exception as e:
        log(f"WARNING: submission failed: {e}")
        return False


def write_manifest(public_dir, urls):
    path = os.path.join(public_dir, MANIFEST_NAME)
    body = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "urls": urls,
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(body, f, separators=(",", ":"), sort_keys=True)
        log(f"manifest written: {path} ({len(urls)} URLs)")
    except OSError as e:
        log(f"WARNING: could not write manifest: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--public-dir", default="public")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be submitted; do not POST or write the manifest",
    )
    args = ap.parse_args()

    public_dir = args.public_dir
    if not os.path.isdir(public_dir):
        log(f"WARNING: {public_dir}/ not found — nothing to do")
        return

    current = build_manifest(public_dir)
    if not current:
        log("WARNING: no generated pages found — nothing to do")
        return
    log(f"{len(current)} generated page(s) hashed")

    previous = fetch_previous()
    if previous is None:
        # Fail closed: without a baseline we cannot tell new from unchanged,
        # and submitting everything is precisely the behaviour being removed.
        log("no baseline — seeding manifest, submitting nothing this build")
        if not args.dry_run:
            write_manifest(public_dir, current)
        return

    changed = diff(current, previous)
    if not changed:
        log("no content changes since last deploy — nothing to submit")
        if not args.dry_run:
            write_manifest(public_dir, current)
        return

    log(f"{len(changed)} changed/new URL(s):")
    for u in changed[:20]:
        log(f"  {u}")
    if len(changed) > 20:
        log(f"  ... and {len(changed) - 20} more")

    if len(changed) > SANITY_WARN:
        log(
            f"WARNING: {len(changed)} URLs changed in one build — that is more "
            "than routine board churn. Check for a template change or a "
            "per-build timestamp leaking into every page."
        )

    if len(changed) > MAX_URLS:
        log(f"WARNING: capping submission at {MAX_URLS} URLs")
        changed = changed[:MAX_URLS]

    if args.dry_run:
        log("dry run — not submitting, not writing manifest")
        return

    if submit(changed):
        write_manifest(public_dir, current)
    else:
        # Keep the old baseline so the next build retries this same diff.
        log("submission failed — preserving previous baseline for retry")
        write_manifest(public_dir, previous)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never break the build
        log(f"WARNING: unexpected error, skipping IndexNow: {e}")
    sys.exit(0)
