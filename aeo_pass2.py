"""Second pass — rewrite headings with correct exact matches."""
import json, glob

HEADING_REWRITES = {
    # how-do-longshot-odds-work
    "the american odds format": "How do American odds work?",
    "a ladder of examples": "What do different longshot odds pay?",
    "prediction markets work slightly different": "How are prediction market odds different?",
    "what implied probability means": "What is implied probability?",
    "why this matters": "Why do longshot odds matter?",
    # weather-betting-markets
    "how weather contracts work": "How do weather betting contracts work?",
    "why weather markets are interesting": "Why are weather markets interesting?",
    "types of weather markets": "What types of weather markets can you bet on?",
    # same-game-parlays-explained
    "how same-game parlays work": "How do same-game parlays work?",
    "why sportsbooks push them": "Why do sportsbooks push same-game parlays?",
    "the sweet spot": "What's the sweet spot for same-game parlays?",
    # what-does-plus-10000-odds-mean
    "how the math works": "How does the math behind +10000 odds work?",
    "what it means in probability terms": "What is the implied probability of +10000 odds?",
    "the plus sign vs the minus sign": "What's the difference between plus and minus odds?",
    "where you'll see +10000 odds": "Where do +10000 odds show up?",
    "converting to other formats": "How do you convert +10000 to decimal or fractional odds?",
    # prediction-market-longshots
    "why longshots exist on prediction markets": "Why do longshots exist on prediction markets?",
    "the math of cheap contracts": "How does the math of cheap contracts work?",
    "what kinds of longshots show up": "What kinds of longshots show up on prediction markets?",
    "when longshots actually hit": "When do prediction market longshots actually hit?",
    "how dollar bets finds them": "How does Dollar Bets find longshots?",
    # what-is-a-spread-bet
    "how the point spread works": "How does the point spread work?",
    "what the numbers actually mean": "What do the spread numbers actually mean?",
    "why spreads are usually -110": "Why are spread bets usually -110?",
    "alternate spreads and big payouts": "What are alternate spreads and how do they pay?",
    # weird-prediction-markets
    "weather markets that feel personal": "What weather prediction markets can you bet on?",
    "government and regulatory markets": "Can you bet on government and regulatory decisions?",
    "space and science markets": "Can you bet on space and science events?",
    "pop culture contracts nobody asked for": "What pop culture prediction markets exist?",
    "economic indicators as spectator sport": "Can you bet on economic indicators?",
    "why weird markets matter": "Why do weird prediction markets matter?",
    # betting-odds-explained (remaining)
    "american odds (moneyline)": "How do American (moneyline) odds work?",
    "the conversion cheat sheet": "How do you convert between odds formats?",
    "odds vs probability": "What's the difference between odds and probability?",
    "the dollar bets translation": "How does Dollar Bets translate odds?",
    # weird-prop-bets (check these too)
    "culture and entertainment props": "What culture and entertainment prop bets exist?",
    "weather props": "What weather prop bets can you make?",
    "political props": "What political prop bets are available?",
    "internet and tech props": "What internet and tech prop bets exist?",
    "why prop bets work": "Why are prop bets so popular?",
    "where to find them": "Where can you find weird prop bets?",
}

updated = 0
for filepath in sorted(glob.glob('content/**/*.json', recursive=True)):
    with open(filepath) as f:
        data = json.load(f)
    
    changed = False
    for block in data.get('body', []):
        if block.get('type') == 'heading':
            lower = block['content'].lower().strip()
            if lower in HEADING_REWRITES:
                block['content'] = HEADING_REWRITES[lower]
                changed = True
    
    if changed:
        slug = data.get('slug', '')
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
        updated += 1
        q_count = sum(1 for b in data.get('body', []) if b.get('type') == 'heading' and '?' in b['content'])
        total_h = sum(1 for b in data.get('body', []) if b.get('type') == 'heading')
        print(f'Updated: {slug:50s} | {q_count}/{total_h} Q-headings')

print(f'\nTotal: {updated} files updated')
