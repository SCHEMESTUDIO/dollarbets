# Dollar Bets — Compliance Notes

Last updated: 2026-05-12

## What Dollar Bets is (and isn't)

Dollar Bets is an editorial discovery site. It curates and comments on prediction markets.
It does NOT operate markets, take bets, hold funds, provide financial advice, or act as a broker/bookmaker/exchange.

## Geo-restriction strategy

Compliance is enforced at the `/go/` redirect layer, not on the board pages. Every visitor sees the same editorial content; partner availability is checked only when a user clicks a market link, and only against the specific partner being opened.

### What every user sees on the site
- The same board, same legend, same disclosure strip ("we earn affiliate commissions when you sign up to kalshi or polymarket through our links…")
- No region-aware copy on the homepage or board pages

### What happens at /go/{ticker}
The redirect handler (`api/go.py`) reads the user's country from Vercel headers and looks up the destination partner in `config/partners.json`. There are two possible outcomes:

1. **Partner is available in this region** → show jurisdiction interstitial → redirect to partner's market URL with affiliate params
2. **Partner is blocked in this region** → render `unavailable_html()` page explaining why (named partner, named region) and suggesting alternatives where applicable

There is no middle "commentary-only" tier any more. The previous client-side banner/CTA-softening behavior was removed on 2026-05-12; geo enforcement happens entirely at click-through against a specific partner.

## Regional notes (informational — actual enforcement is per-partner)

- **GB**: FCA regulates prediction markets; Kalshi US-only; Polymarket blocks UK
- **AU**: ASIC restrictions on binary options / prediction markets
- **CN, HK**: Gambling/speculative trading broadly restricted
- **IN**: Legal gray area; FEMA and Public Gambling Act concerns
- **JP**: Gambling Act restrictions; prediction markets not clearly legal
- **KR**: National Gambling Control Commission oversight
- **Sanctioned (IR, KP, CU, SY, BY, RU, VE, MM)**: OFAC/international sanctions; both platforms block these natively

## Kalshi geo rules

- `allowed_countries`: US only (Kalshi is CFTC-regulated, US-only platform)
- Blocked US states: AZ, IL, MA, MD, MI, MT, NV, OH (cannot enforce via country-level geo-IP — state-level would require IP geolocation database)
- State-level blocking is a known gap; noted in config as informational only

## Polymarket geo rules

- `blocked_countries`: US + EU countries where blocked (NL, PL, FR, BE, CH, PT, HU, IT) + GB, AU, CN, HK, IN, JP, KR + sanctioned nations
- US blocked because Polymarket operates outside US regulatory framework

## Outstanding business actions

- [ ] Get written approval from Kalshi for affiliate link usage, especially for international traffic referrals
- [ ] Get written approval from Polymarket for affiliate/builder links if/when affiliate_id is activated
- [ ] Review Kalshi and Polymarket ToS quarterly for changes to geo-restrictions
- [ ] Consider adding state-level IP geolocation for Kalshi's blocked US states (MaxMind GeoIP2 or similar)
- [ ] Consult with attorney on whether editorial "discovery" framing is sufficient in specific jurisdictions (UK, AU, Singapore)

## Technical implementation

- **Interstitial**: All `/go/` clicks pass through an HTML warning page before redirect (`api/go.py`, `interstitial_html()`)
- **Unavailable page**: Region/partner mismatches render `unavailable_html()` instead of redirecting (`api/go.py`)
- **Country detection**: `x-vercel-ip-country` header read directly in `api/go.py`. No separate geo endpoint.
- **Config**: Per-partner `allowed_countries` and `blocked_countries` arrays in `config/partners.json` are the only source of truth.

## CTA language rules

| Context | Allowed | Not allowed |
|---------|---------|-------------|
| Site-wide | "view market", "see odds" | "bet now", "trade now", "register now", "wager" |
| Blocked (on /go/ → /unavailable/) | N/A | All CTAs — the page explains the restriction instead |

Note: Existing CTA labels in `link_resolver.py` already use safe language ("view market", "see odds").
The words "bet" and "wager" appear in editorial copy (quips, headlines) but these are editorial/commentary, not calls to action.
