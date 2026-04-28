# Affiliate Link Integration — Dollar Bets

How the Kalshi referral link works, where it lives in the codebase, and how to add links for other platforms in the future.

---

## How the Kalshi referral link works

Every outbound link to kalshi.com on Dollar Bets carries the referral parameter `?referral=e690aa11-1f29-49d1-b27f-d5e6ccf38d9f`. This is appended automatically at three points in the pipeline:

### 1. When the scanner creates board data (`scanner.py`)

The scanner pulls markets from the Kalshi API daily and writes JSON files to `data/boards/`. A constant and helper function build every market URL with the referral parameter baked in from the start.

```python
# scanner.py — lines 22-29
KALSHI_REFERRAL = "e690aa11-1f29-49d1-b27f-d5e6ccf38d9f"

def kalshi_url(ticker):
    """Build a Kalshi market URL with referral tracking."""
    return f"https://kalshi.com/markets/{ticker}?referral={KALSHI_REFERRAL}"
```

This function is called everywhere the scanner constructs a market URL (currently two places, around lines 930 and 1081). The result is that every `"url"` field in the board JSON already contains the referral parameter before the site is even built.

### 2. When the site generator renders bet cards (`generate.py`)

A second constant and helper function in `generate.py` handle any URL that arrives without the parameter — either from older board data or from content JSON files.

```python
# generate.py — lines 30-40
KALSHI_REFERRAL = "e690aa11-1f29-49d1-b27f-d5e6ccf38d9f"

def kalshi_ref_url(url):
    """Append referral parameter to any Kalshi URL that doesn't already have one."""
    if not url or "kalshi.com" not in url:
        return url
    if "referral=" in url:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}referral={KALSHI_REFERRAL}"
```

This is called in two places:

- `render_bet_card()` (line ~613) — wraps every bet card's URL, which covers the daily board, category pages, archetype pages, and weekly recaps
- The autopsy page generator (line ~1156) — wraps the "view on kalshi" link

### 3. Post-processing safety net (`generate.py`, end of `main()`)

After all pages are generated, a regex-based post-processor walks every `.html` file in `public/` and finds any `href=` or `data-url=` pointing to `kalshi.com` that doesn't already have `referral=`. If it finds one, it appends the parameter. This catches edge cases and future code paths.

```python
# generate.py — around line 1530
_kalshi_href_pattern = re.compile(r'(href="|data-url=")https://kalshi\.com([^"]*)"')
```

### 4. GA4 click tracking

Every page includes a click listener that fires a GA4 event whenever someone clicks a link starting with `https://kalshi.com`. This selector is intentionally broad — it matches URLs both with and without the referral parameter, so tracking works regardless of how the URL was constructed.

```javascript
// In page_shell() — line ~58
var link = e.target.closest('a[href^="https://kalshi.com"]');
```

### 5. Content JSON files

Hero bet objects in content JSON files (`content/pages/*.json`, `content/hall-of-filth/*.json`) also have their `"url"` fields set with the referral parameter. These are currently display-only (the hero bet card doesn't render as a clickable link), but they're ready if that changes.

---

## Current coverage

After a clean build, every clickable Kalshi link on the site has the referral parameter:

- 119 `href` links (bet cards, autopsy pages, footer links)
- 82 `data-url` attributes (share buttons)
- 0 clickable Kalshi links without the parameter

The only bare `kalshi.com` references are the GA4 CSS selector (not a link) and editorial text mentions in the about page and category intros (plain text, not clickable links to specific markets).

---

## How to change the Kalshi referral ID

If the referral ID changes, update it in two places:

1. `scanner.py` line 22 — `KALSHI_REFERRAL = "new-id-here"`
2. `generate.py` line 31 — `KALSHI_REFERRAL = "new-id-here"`

Then update the `"url"` fields in content JSON files (5 files currently). Grep for the old ID: `grep -r "e690aa11" content/`.

The post-processor will handle everything else on the next build.

---

## How to add a new affiliate platform

If Dollar Bets starts linking to a second platform (e.g., Polymarket, PredictIt, a sportsbook), here's the pattern to follow.

### Step 1: Add the constant and helper to `scanner.py`

```python
# Example for a hypothetical Polymarket affiliate
POLYMARKET_AFFILIATE = "your-affiliate-id"

def polymarket_url(slug):
    """Build a Polymarket URL with affiliate tracking."""
    return f"https://polymarket.com/event/{slug}?ref={POLYMARKET_AFFILIATE}"
```

Use this function wherever the scanner constructs URLs for that platform's markets. The parameter name (`ref`, `affiliate`, `utm_source`, etc.) depends on what the platform uses — check their affiliate program docs.

### Step 2: Add the constant and helper to `generate.py`

```python
POLYMARKET_AFFILIATE = "your-affiliate-id"

def polymarket_ref_url(url):
    """Append affiliate parameter to any Polymarket URL."""
    if not url or "polymarket.com" not in url:
        return url
    if "ref=" in url:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}ref={POLYMARKET_AFFILIATE}"
```

### Step 3: Apply it in `render_bet_card()`

The `render_bet_card()` function currently only calls `kalshi_ref_url()`. To handle multiple platforms, chain the helpers or create a generic one:

```python
def affiliate_url(url):
    """Apply the correct affiliate parameter for any supported platform."""
    url = kalshi_ref_url(url)
    url = polymarket_ref_url(url)
    # Add more platforms here
    return url
```

Then in `render_bet_card()`:

```python
url = affiliate_url(m.get("url", "#"))
```

### Step 4: Extend the post-processor

Add a second regex pattern for the new domain in the post-processing block at the end of `main()`, following the same structure as the Kalshi one.

### Step 5: Update GA4 click tracking

The current click tracker only watches for `kalshi.com` links. To track clicks to other platforms, broaden the selector or add a second listener in the `page_shell()` function:

```javascript
// Option A: multiple selectors
var link = e.target.closest('a[href^="https://kalshi.com"], a[href^="https://polymarket.com"]');

// Option B: track all outbound links
var link = e.target.closest('a[target="_blank"]');
```

### Step 6: Update compliance pages

- `affiliate-disclosure.json` — add the new platform and its relationship
- `editorial-policy.json` — note that affiliate links exist for the new platform
- Footer disclaimer already says "some links may be affiliate links" which covers all platforms

---

## File reference

| File | What it does |
|------|-------------|
| `scanner.py` | Builds market URLs with referral param when pulling from Kalshi API |
| `generate.py` | Renders all pages; applies referral param at render time + post-processes |
| `generate_content.py` | Renders content/SEO pages; imports `render_bet_card` from generate.py |
| `content/pages/*.json` | Hero bet URLs have referral param in the JSON |
| `content/hall-of-filth/*.json` | Same as above |

---

## Quick checklist for any affiliate link change

- [ ] Update the ID constant in `scanner.py`
- [ ] Update the ID constant in `generate.py`
- [ ] Update content JSON files (`grep -r "old-id" content/`)
- [ ] Rebuild and verify: `grep -roh 'href="https://platform.com[^"]*"' public/ | grep -v affiliate-param | head`
- [ ] Update `affiliate-disclosure.json` if adding a new platform
- [ ] Push and confirm Vercel build succeeds
