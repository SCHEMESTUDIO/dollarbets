#!/usr/bin/env python3
"""
Dollar Bets — subject-matched background photo for a social card.

Called by daily_tweets.py at post time, once per posted card (three a day),
so the whole thing costs well under a dollar a month:

  1. Opus 5 writes two stock-photo search phrases for the market. Scenes,
     not subjects: "night sky desert", not "UFO". Effort low, tiny output.
  2. Pexels is searched for each phrase. If nothing from Pexels survives the
     vision pass, Openverse (Wikimedia / Flickr, commercial-use licences only)
     is searched and vetted the same way.
  3. Pillow scores every candidate for darkness and low detail in the lower
     half, where the payout sits, and keeps the best 16.
  4. Haiku 4.5 looks at the 16 thumbnails and picks one, or none. It rejects
     people, faces, logos, flags, readable text, and anything that is plainly
     about the wrong subject.
  5. None means the caller posts the plain card. A photo is never forced.

Env:
  ANTHROPIC_API_KEY   required (steps 1 and 4); without it: no photo
  PEXELS_API_KEY      Pexels; without it Openverse is the only source
  SOCIAL_PHOTO_QUERY_MODEL / SOCIAL_PHOTO_RANK_MODEL   optional overrides

Every pick is returned with source, id, page URL, photographer and licence so
the queue file carries the attribution.
"""

import base64
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

QUERY_MODEL = os.environ.get("SOCIAL_PHOTO_QUERY_MODEL", "claude-opus-5")
RANK_MODEL = os.environ.get("SOCIAL_PHOTO_RANK_MODEL", "claude-haiku-4-5")
QUERIES_PER_CARD = 2
PER_QUERY = 8
RANK_POOL = 16
UA = "dollarbets-social/1.0 (https://www.dollarbets.lol; james@schemestudio.lol)"

DEFAULT_QUERY_BY_CATEGORY = {
    "Politics": "marble columns dusk", "Sports": "empty stadium floodlights night",
    "Science and Technology": "server room blue light", "Climate and Weather": "storm clouds horizon",
    "Financials": "glass office tower rain", "Companies": "glass office tower night",
    "Entertainment": "theatre stage lights", "World": "city skyline night", "Other": "neon sign dark street",
}


def log(msg):
    print(f"[photo] {msg}", file=sys.stderr)


def _secret(name):
    """A secret set through a shell pipe can arrive with a trailing newline or
    even two copies on two lines. Header values can't contain newlines, so take
    the first non-empty line and strip it."""
    raw = os.environ.get(name) or ""
    for line in raw.splitlines():
        if line.strip():
            return line.strip()
    return ""


# ── Claude ─────────────────────────────────────────────────────────────────

def _claude(messages, model, max_tokens, effort=None):
    key = _secret("ANTHROPIC_API_KEY")
    if not key:
        return None, {}
    body = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if effort:
        body["output_config"] = {"effort": effort}
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read().decode())
    text = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text").strip()
    return text, out.get("usage", {})


def search_phrases(m):
    """Two Pexels-style phrases in plain nouns. Returns (phrases, usage)."""
    prompt = f"""Give {QUERIES_PER_CARD} search phrases for a background photo behind this prediction-market card. The photo sits under large text, so it should be a scene, not a subject.

Market: {m.get('title')}
Quip: {m.get('quip')}
Category: {m.get('category')}

Rules:
- 2 to 4 plain, concrete nouns a stock-photo site indexes: places, objects, weather, times of day. No adjectives like "redacted", "ominous", "scattered". No abstract words.
- Never a person, face, crowd, logo, flag, or text.
- Prefer night, dusk, rain, empty venues, architecture, landscape.
- Evoke the subject obliquely: one phrase close to it, one further away.
Examples: UFO files -> "night sky desert" / "filing cabinet dark office"; MLB strikeouts -> "baseball stadium night" / "pitchers mound dirt"; Robinhood stock -> "glass office tower rain" / "smartphone screen dark".

Reply with the {QUERIES_PER_CARD} phrases only, one per line, no numbering."""
    text, usage = _claude([{"role": "user", "content": prompt}], QUERY_MODEL, max_tokens=2000, effort="low")
    if not text:
        return [], usage
    qs = [ln.strip().strip('"-• ') for ln in text.splitlines() if ln.strip()]
    return qs[:QUERIES_PER_CARD], usage


def rank_candidates(m, scored):
    """Vision pass. Returns (index or None, usage)."""
    content = [{"type": "text", "text": f"""These are candidate background photos for a card about this prediction market:
"{m.get('title')}" (quip: "{m.get('quip')}").

Pick the ONE best photo. Rules, in order:
1. REJECT any photo containing a recognisable person, face, crowd, logo, brand, flag, or readable text.
2. REJECT any photo that is plainly about the wrong subject (fruit for a baseball market, a lighthouse for the Vatican). Vague and moody is fine; wrong is not.
3. Prefer a calm, dark or muted lower half (large text sits there).
4. Prefer a real place or scene over abstract/CGI, and film-still mood over stock-photo gloss.
5. It should evoke the subject obliquely, not illustrate it literally.

Reply with ONLY the number of the best photo, or 0 if none is acceptable. When in doubt, 0."""}]
    from PIL import Image, ImageOps
    for i, cand in enumerate(scored, 1):
        th = ImageOps.fit(cand["img"], (400, 400), method=Image.LANCZOS)
        buf = io.BytesIO()
        th.save(buf, "JPEG", quality=70)
        content.append({"type": "text", "text": f"Photo {i}:"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                     "data": base64.b64encode(buf.getvalue()).decode()}})
    text, usage = _claude([{"role": "user", "content": content}], RANK_MODEL, max_tokens=10)
    if not text:
        return None, usage
    mm = re.search(r"\d+", text)
    n = int(mm.group()) if mm else 0
    return (n - 1 if 1 <= n <= len(scored) else None), usage


# ── Sources ────────────────────────────────────────────────────────────────

def _get_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


_PEXELS_KEY_OK = None


def _pexels_keys():
    """Every distinct non-empty line of the secret. A secret set through a
    shell pipe once arrived as three lines (a placeholder, then the key twice);
    the first line that Pexels accepts is remembered for the rest of the run."""
    raw = os.environ.get("PEXELS_API_KEY") or ""
    seen, out = set(), []
    for line in raw.splitlines():
        k = line.strip()
        if k and k not in seen:
            seen.add(k); out.append(k)
    return out


def pexels(query, key=None):
    global _PEXELS_KEY_OK
    keys = [_PEXELS_KEY_OK] if _PEXELS_KEY_OK else _pexels_keys()
    if not keys:
        return []
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": query, "per_page": PER_QUERY, "orientation": "square", "size": "large"})
    data = None
    for k in keys:
        try:
            data = _get_json(url, {"Authorization": k})
            _PEXELS_KEY_OK = k
            break
        except urllib.error.HTTPError as e:
            if e.code in (401, 403) and k is not keys[-1]:
                continue            # not this line — try the next
            log(f"pexels error for {query!r}: {e}")
            return []
        except Exception as e:
            log(f"pexels error for {query!r}: {e}")
            return []
    if data is None:
        log(f"pexels: no line of PEXELS_API_KEY was accepted")
        return []
    out = []
    for ph in data.get("photos", []):
        out.append({"source": "pexels", "id": str(ph["id"]), "page": ph.get("url"),
                    "download": ph["src"]["large2x"], "thumb": ph["src"]["medium"],
                    "photographer": ph.get("photographer", ""),
                    "license": "Pexels License", "credit": f"photo: {ph.get('photographer', '').strip()} · pexels"})
    return out


def openverse(query):
    """Openverse (Wikimedia, Flickr, ...). Commercial-use licences only; no key
    needed at this volume. Attribution is required for CC BY, so the credit
    line always names the creator and the licence."""
    url = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(
        {"q": query, "license_type": "commercial", "size": "large",
         "page_size": PER_QUERY, "mature": "false"})   # no aspect filter: it starves results; we cover-crop
    try:
        data = _get_json(url)
    except Exception as e:
        log(f"openverse error for {query!r}: {e}")
        return []
    out = []
    for r in data.get("results", []):
        if (r.get("filetype") or "").lower() not in ("jpg", "jpeg", "png", ""):
            continue
        lic = (r.get("license") or "").upper()          # "BY-SA", "CC0", "PDM"
        ver = r.get("license_version") or ""
        lic_name = lic if lic in ("CC0", "PDM") else f"CC {lic}"
        creator = (r.get("creator") or "").strip()
        # CC0 / public domain need no attribution; CC BY(-SA) require it.
        credit = f"photo: {creator} · {lic_name}" if creator and lic not in ("CC0", "PDM") else f"photo: {lic_name} · openverse"
        out.append({"source": "openverse", "id": r["id"], "page": r.get("foreign_landing_url"),
                    "download": r.get("url"), "thumb": r.get("thumbnail"),
                    "photographer": creator or "unknown",
                    "license": f"{lic_name} {ver}".strip(), "credit": credit})
    return out


def _wikimedia_thumb(url, width=800):
    """upload.wikimedia.org/wikipedia/commons/a/ab/Name.jpg ->
    .../commons/thumb/a/ab/Name.jpg/800px-Name.jpg — a cached derivative,
    far cheaper for Wikimedia than the original and not rate-limited the same way."""
    m = re.match(r"^(https://upload\.wikimedia\.org/wikipedia/commons)/([0-9a-f])/([0-9a-f]{2})/([^/]+)$", url or "")
    if not m:
        return None
    base, a, ab, name = m.groups()
    return f"{base}/thumb/{a}/{ab}/{name}/{width}px-{name}"


def _fetch_image(url, min_bytes=20_000):
    from PIL import Image
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    if len(data) < min_bytes:
        raise ValueError("too small")
    return Image.open(io.BytesIO(data)).convert("RGB")


def _fetch_original(c):
    """The full-size file for the chosen candidate, with one retry. Falls back
    to the thumbnail already in hand (600px, upscaled) rather than losing the pick."""
    import time
    url = _wikimedia_thumb(c["download"], 1600) or c["download"]
    for attempt in (1, 2):
        try:
            return _fetch_image(url)
        except Exception as e:
            log(f"original fetch attempt {attempt} failed for {c['source']}:{c['id']} ({e})")
            time.sleep(3)
    return c["img"]


def _score(img):
    """Lower is better: dark-ish overall, calm lower half, little edge detail."""
    from PIL import ImageFilter, ImageOps
    g = ImageOps.grayscale(img.resize((256, 256)))
    px = list(g.getdata())
    lum = sum(px) / len(px)
    lower = px[128 * 256:]
    lum_lower = sum(lower) / len(lower)
    ep = list(g.filter(ImageFilter.FIND_EDGES).getdata())
    edge = sum(ep) / len(ep)
    return abs(lum - 90) * 0.6 + abs(lum_lower - 70) * 0.8 + edge * 1.5


# ── Public API ─────────────────────────────────────────────────────────────

def choose_photo(market):
    """Return {"img": PIL image, "credit": str, ...attribution, "usage": {...}}
    or None when nothing acceptable was found. Never raises for a source or
    model failure — the caller falls back to the plain card."""
    usage = {"input_tokens": 0, "output_tokens": 0}

    def add(u):
        usage["input_tokens"] += u.get("input_tokens", 0)
        usage["output_tokens"] += u.get("output_tokens", 0)

    try:
        phrases, u = search_phrases(market)
        add(u)
    except Exception as e:
        log(f"phrase step failed: {e}")
        phrases = []
    if not phrases:
        phrases = [DEFAULT_QUERY_BY_CATEGORY.get(market.get("category", ""), "city skyline night")]
    log(f"phrases: {phrases}")

    pexels_key = bool(_pexels_keys())

    def variants(q):
        """The phrase, then its first two words, then its last two — Openverse
        matches literally, so 'empty ballpark dusk' finds nothing but 'ballpark' does."""
        w = q.split()
        out = [q]
        if len(w) > 2:
            out += [" ".join(w[:2]), " ".join(w[-2:])]
        if len(w) > 1:
            out += [w[0], w[-1]]
        return out

    def pool(source_fn, tag, loosen=False):
        cands, seen = [], set()
        for q in phrases:
            for qq in (variants(q) if loosen else [q]):
                got = 0
                for c in source_fn(qq):
                    if c["id"] not in seen:
                        seen.add(c["id"]); cands.append(c); got += 1
                if got >= 4:
                    break
        scored = []
        import time
        for c in cands:
            # Prefer a real thumbnail: Wikimedia's own derivative, then the
            # source's thumbnail, then the original. Openverse fetches are
            # spaced out — Wikimedia 429s a burst of requests.
            tries = [u for u in (_wikimedia_thumb(c["download"]), c.get("thumb"), c["download"]) if u]
            img = None
            for u in tries:
                try:
                    img = _fetch_image(u, min_bytes=5_000)
                    break
                except Exception as e:
                    last = e
            if img is None:
                log(f"skip {c['source']}:{c['id']} ({last})")
                continue
            c["img"] = img
            if c["source"] == "openverse":
                time.sleep(0.7)
            c["score"] = _score(c["img"])
            scored.append(c)
        scored.sort(key=lambda c: c["score"])
        log(f"{tag}: {len(cands)} candidates, {len(scored)} fetched")
        return scored[:RANK_POOL]

    def vet(scored):
        if not scored:
            return None
        try:
            pick, u = rank_candidates(market, scored)
            add(u)
        except Exception as e:
            log(f"rank step failed: {e}")
            return None
        return scored[pick] if pick is not None else None

    # Round 1: Pexels. Round 2: Openverse, only if Pexels had nothing acceptable —
    # the vision pass rejecting the whole pool is the usual "wrong subject" case.
    c = None
    if pexels_key:
        c = vet(pool(pexels, "pexels"))
        if c is None:
            log("pexels: nothing acceptable — trying openverse")
    if c is None:
        c = vet(pool(openverse, "openverse", loosen=True))
    if c is None:
        log("nothing acceptable from any source — plain card")
        return None
    log(f"pick {c['source']}:{c['id']} by {c['photographer']} ({c['license']})")
    c["img"] = _fetch_original(c)
    return {"img": c["img"], "credit": c["credit"], "source": c["source"], "id": c["id"],
            "page": c["page"], "photographer": c["photographer"], "license": c["license"],
            "phrases": phrases, "usage": usage}


if __name__ == "__main__":
    import argparse
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, ROOT)
    from share_card import render_card, safe_ticker

    p = argparse.ArgumentParser(description="Render photo cards for a board (local test)")
    p.add_argument("--board", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--only")
    a = p.parse_args()
    data = json.load(open(a.board))
    date = os.path.basename(a.board)[:-5]
    for m in data["board"]:
        if a.only and m["ticker"] != a.only:
            continue
        r = choose_photo(m)
        out = os.path.join(a.out, f"{safe_ticker(m['ticker'])}.png")
        if r:
            render_card(m, "photo", out, board_date=date, photo=r["img"], credit=r["credit"])
            print(f"photo {out}  [{r['source']} {r['photographer']}]  tokens={r['usage']}")
        else:
            render_card(m, "tile", out, board_date=date)
            print(f"plain {out}")
