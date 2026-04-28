# Affiliate Link Integration — Dollar Bets

How market links work, where they live in the codebase, and how to add new platforms.

---

## Architecture overview: /go/ redirect system

Dollar Bets now routes all market links through a `/go/` serverless redirect. This enables:
- **Geo-aware routing**: Different users see different platforms based on their location
- **Platform agnostic**: Easily swap or add platforms without changing UI
- **Affiliate flexibility**: Change affiliate IDs or tracking params without rebuilding
- **Analytics**: GA4 tracks all redirects

The flow:
1. UI renders bet cards with `/go/{market_ticker}` links (e.g., `/go/KXGROK`)
2. User clicks → Vercel redirect routes to `/api/go.py`
3. Serverless function reads `x-vercel-ip-country` header
4. Queries `partners.json` to find best eligible partner
5. Returns 302 redirect to partner's market URL (with affiliate params)

---

## Key files and their roles

| File | Purpose |
|------|---------|
| `config/partners.json` | Master config: all platforms, affiliate IDs, geo rules, priority |
| `link_resolver.py` | Geo/eligibility logic — resolves market to best partner |
| `api/go.py` | Vercel serverless function — handles redirects |
| `generate.py` | Site generator — renders bet cards with `/go/` links |
| `scanner.py` | Market scanner — now outputs canonical ticker + sources array (future) |
| `vercel.json` | Routing config — maps `/go/:slug` to `/api/go.py` |

---

## How partners.json is structured

```json
{
  "partners": [
    {
      "slug": "kalshi",
      "display_name": "Kalshi",
      "base_url": "https://kalshi.com/markets",
      "affiliate_id": "e690aa11-1f29-49d1-b27f-d5e6ccf38d9f",
      "tracking_param_name": "referral",
      "enabled": true,
      "allowed_countries": "all",
      "blocked_countries": ["comment: AZ, IL, MA, MD, MI, MT, NV, OH are US state exclusions"],
      "min_age": 21,
      "requires_disclaimer": true,
      "priority_rank": 1,
      "market_url_format": "{base_url}/{ticker}?{tracking_param_name}={affiliate_id}"
    },
    // ... more platforms
  ]
}
```

**Field meanings:**
- `slug`: Unique identifier (used in `/go/:slug` URLs and code)
- `display_name`: User-friendly name
- `base_url`: Root URL for this platform
- `affiliate_id`: Affiliate tracking ID (empty string if not available)
- `tracking_param_name`: Query param name for affiliate tracking (e.g., `referral`, `ref`)
- `enabled`: Whether this platform should be offered (boolean)
- `allowed_countries`: "all" or array of ISO country codes (e.g., `["US", "GB"]`)
- `blocked_countries`: Array of ISO codes to exclude (overrides `allowed_countries`)
- `min_age`: Minimum user age for this platform
- `requires_disclaimer`: Whether to show a disclaimer
- `priority_rank`: Lower = higher priority when multiple platforms are eligible
- `market_url_format`: Template for URL construction (not currently used, for future expansion)

---

## Current platform configuration

### Kalshi ✓ (enabled)
- **Status**: Live and routing all traffic
- **Affiliate ID**: `e690aa11-1f29-49d1-b27f-d5e6ccf38d9f`
- **Tracking param**: `?referral=`
- **Geo rules**: Available worldwide except US states AZ, IL, MA, MD, MI, MT, NV, OH
- **Priority**: 1 (highest)

### Polymarket (disabled, stub)
- **Status**: Stub — ready for implementation
- **Blocked countries**: NL, PL, FR, BE, CH, PT, HU, IT, UA, RU, IR, KP, CU, SY, BY, VE, MM, SG, AR
- **Priority**: 2

### Coinbase (disabled, stub)
- **Status**: Stub
- **Priority**: 3

### Sportsbook (disabled, stub)
- **Status**: Stub
- **Priority**: 4

---

## How to change the Kalshi affiliate ID

1. Open `config/partners.json`
2. Find the `"kalshi"` object
3. Update `"affiliate_id"` to your new ID
4. Save and rebuild

That's it. No code changes needed.

---

## How to enable a new platform

1. **Update `partners.json`**:
   - Find the platform's object (e.g., Polymarket)
   - Set `"enabled": true`
   - Fill in `affiliate_id` if you have one
   - Adjust `allowed_countries` and `blocked_countries` as needed
   - Adjust `priority_rank` relative to other platforms

2. **Implement the platform adapter** (optional, if using live API):
   - Create `integrations/{platform_slug}/` directory
   - Implement API methods to fetch and normalize market data
   - Import in `scanner.py` and add logic to handle multi-platform boards

3. **Test the /go/ redirect**:
   - Build and deploy
   - Click a market link
   - Verify it redirects to the new platform

---

## How the /go/ redirect works in detail

### 1. Rendering a bet card (generate.py)

```python
def render_bet_card(m):
    # Instead of kalshi_ref_url(m.get("url")), we now use:
    ticker = m.get("ticker", "")
    url = market_link(ticker)  # Returns /go/KXGROK/
    # ... render link
```

### 2. User clicks a link

```html
<a href="/go/KXGROK/" target="_blank">View market</a>
```

### 3. Vercel routes to serverless function (vercel.json)

```json
{ "source": "/go/:slug", "destination": "/api/go.py?market=:slug" }
```

### 4. /api/go.py resolves and redirects

```python
def handler(request):
    market_id = "KXGROK"
    user_country = request.headers.get("x-vercel-ip-country")  # e.g., "US"

    result = resolve_market_destination(
        market_id=market_id,
        user_country=user_country
    )

    if result["eligible"]:
        # Redirect to final URL (with affiliate params baked in)
        return { "statusCode": 302, "headers": { "Location": result["destination_url"] } }
    else:
        # Geo-blocked or no eligible partners
        return { "statusCode": 302, "headers": { "Location": "/unavailable/" } }
```

### 5. User lands on partner platform (or unavailable page)

---

## Analytics tracking

GA4 is configured to track all `/go/` clicks:

```javascript
// In page_shell() analytics snippet
document.addEventListener('click', function(e) {
  var link = e.target.closest('a[href^="/go/"]');
  if (link) {
    gtag('event', 'click', {
      event_category: 'outbound',
      event_label: link.href,
      transport_type: 'beacon'
    });
  }
});
```

Each click fires a GA4 event with the `/go/` URL. You can cross-reference with Vercel logs to see which platform actually served the traffic.

---

## Data model: canonical market format

Currently, board JSON files store the old format:
```json
{
  "board": [
    {
      "ticker": "KXGROK",
      "title": "...",
      "url": "https://kalshi.com/markets/KXGROK?referral=...",
      "payout": 4.76,
      ...
    }
  ]
}
```

**Future (when multi-platform support is needed)**, the format will evolve to:
```json
{
  "board": [
    {
      "ticker": "KXGROK",
      "title": "...",
      "sources": [
        {
          "platform": "kalshi",
          "market_id": "KXGROK",
          "url": "https://kalshi.com/markets/KXGROK",
          "price": 0.21,
          "volume": 17253.75
        }
      ],
      "payout": 4.76,
      ...
    }
  ]
}
```

The `/go/` redirect system is designed to support this transition without changing the UI or build pipeline.

---

## Troubleshooting

### Links are 404ing
- Check that `/api/go.py` exists and has correct Python syntax
- Verify `vercel.json` has the `/go/:slug` rewrite
- Deploy and wait for Vercel to rebuild

### Wrong platform is showing
- Check user's country in Vercel logs (`x-vercel-ip-country` header)
- Verify `partners.json` has correct `enabled` and `blocked_countries`
- Check `priority_rank` — lower number = higher priority

### Affiliate params not appearing
- Verify `affiliate_id` is non-empty in `partners.json`
- Check `tracking_param_name` matches the platform's API docs
- Test by visiting `/go/MARKET?platform=kalshi` to force a platform

### Unavailable page is showing
- User's country is blocked for all enabled platforms
- Or no board data file exists
- Check Vercel logs for the specific reason

---

## Quick checklist for any change

- [ ] Update `config/partners.json` (if changing IDs, enabling/disabling, geo rules)
- [ ] Update `api/go.py` or `link_resolver.py` (if changing routing logic)
- [ ] Run build: `bash build.sh` in site directory
- [ ] Spot-check output HTML: `grep -r "/go/" public/ | head`
- [ ] Test locally or on staging
- [ ] Commit and push
- [ ] Verify Vercel build succeeds

---

## Files reference

- **config/partners.json** — Master partner configuration (JSON)
- **api/go.py** — Serverless redirect handler (Python)
- **link_resolver.py** — Geo/eligibility resolution logic (Python)
- **generate.py** — Site generator (Python, updated to use /go/ links)
- **vercel.json** — Vercel routing config (JSON, updated with /go/ rewrite)
- **integrations/*** — Platform adapter stubs (Python, for future expansion)
