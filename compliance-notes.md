# Dollar Bets — Compliance Notes

Last updated: 2026-05-01

## What Dollar Bets is (and isn't)

Dollar Bets is an editorial discovery site. It curates and comments on prediction markets.
It does NOT operate markets, take bets, hold funds, provide financial advice, or act as a broker/bookmaker/exchange.

## Geo-restriction strategy

Three tiers of response based on user location:

### Tier 1: Full experience (US only for Kalshi; non-blocked countries for Polymarket)
- Normal CTAs ("view market", "see odds")
- Outbound `/go/` links active
- Jurisdiction interstitial shown before redirect

### Tier 2: Commentary-only mode (restricted countries)
- CTAs softened to "view market info"
- Banner: "market commentary only — trading may not be available in your region"
- Outbound links still function (interstitial gate applies)
- No "sign up", "trade now", or "register" language

### Tier 3: Blocked (sanctioned / fully restricted)
- `/go/` redirect sends to `/unavailable/` page
- Both platforms report ineligible

## Commentary-only countries

GB, AU, CN, HK, IN, JP, KR, IR, KP, CU, SY, BY, RU, VE, MM

Rationale:
- **GB**: FCA regulates prediction markets; Kalshi US-only; Polymarket blocks UK
- **AU**: ASIC restrictions on binary options / prediction markets
- **CN, HK**: Gambling/speculative trading broadly restricted
- **IN**: Legal gray area; FEMA and Public Gambling Act concerns
- **JP**: Gambling Act restrictions; prediction markets not clearly legal
- **KR**: National Gambling Control Commission oversight
- **Sanctioned (IR, KP, CU, SY, BY, RU, VE, MM)**: OFAC/international sanctions; both platforms block these

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

- **Interstitial**: All `/go/` clicks pass through an HTML warning page before redirect (api/go.py)
- **Geo endpoint**: `/api/geo` returns user's country and commentary-only status (api/geo.py)
- **Client-side suppression**: JS on page load checks `/api/geo`, softens CTAs and shows banner for restricted countries
- **Config**: All geo rules live in `config/partners.json` under `geo_compliance` and per-partner `blocked_countries`/`allowed_countries`

## CTA language rules

| Context | Allowed | Not allowed |
|---------|---------|-------------|
| Unrestricted | "view market", "see odds" | "bet now", "trade now", "register now", "wager" |
| Commentary-only | "view market info" | All of the above + "sign up" |
| Blocked | N/A (redirected to /unavailable/) | All CTAs |

Note: Existing CTA labels in link_resolver.py already use safe language ("view market", "see odds").
The words "bet" and "wager" appear in editorial copy (quips, headlines) but these are editorial/commentary, not calls to action.
