"""Add quick_answer fields and convert headings to question format for AEO."""
import json, os, glob

# Quick answers for top pages — 40-60 word direct answers to the page's implicit question
QUICK_ANSWERS = {
    "what-is-a-prediction-market": "A prediction market is a platform where you buy and sell contracts on the outcome of real-world events. Prices move between $0 and $1 based on what traders think will happen. If you're right, the contract pays $1. If you're wrong, you lose your stake. Think of it as a stock market for events instead of companies.",
    "what-can-you-bet-one-dollar-on": "You can bet $1 on almost anything through prediction markets and sportsbooks: elections, weather events, sports games, cryptocurrency prices, celebrity news, Supreme Court rulings, and more. Platforms like Kalshi and Polymarket let you start with as little as $1 per contract.",
    "what-is-an-underdog-bet": "An underdog bet is a wager on the side expected to lose. Because underdogs are less likely to win, they pay more when they do. In the $1 framing: a heavy underdog at +1000 means $1 returns $10. The longer the odds, the bigger the potential payout — and the less likely it happens.",
    "what-is-a-prediction-market": "A prediction market is a platform where you buy and sell contracts on the outcome of real-world events. Prices move between $0 and $1 based on what traders think will happen. If you're right, the contract pays $1. If you're wrong, you lose your stake. Think of it as a stock market for events instead of companies.",
    "prediction-market-longshots": "Prediction market longshots are contracts priced under 10 cents — meaning the market thinks there's less than a 10% chance of the event happening. A $1 bet on a contract priced at $0.01 would return $100 if it hits. These are high-risk, high-reward wagers on unlikely outcomes.",
    "how-do-longshot-odds-work": "Longshot odds like +1000, +5000, or +10000 tell you how much profit you'd make on a winning bet relative to your stake. +1000 means $1 returns $10 in profit (plus your $1 back). The bigger the number, the less likely the outcome — and the more it pays if it happens.",
    "what-does-plus-10000-odds-mean": "+10000 odds mean that for every $1 you bet, you'd win $100 in profit if the bet hits. The implied probability is about 1% — the market thinks there's roughly a 1-in-100 chance of this outcome happening. These are extreme longshots with massive potential returns.",
    "betting-odds-explained": "Betting odds represent the probability of an outcome and determine your payout. American odds use + and - signs (+200 means $1 wins $2, -200 means you need $2 to win $1). Decimal odds show your total return per dollar. Fractional odds show profit relative to stake. All three formats express the same underlying probability.",
    "what-is-a-moneyline-bet": "A moneyline bet is the simplest wager in sports: you pick which team wins, with no point spread involved. The odds determine your payout. Favorites have negative odds (you bet more to win less) and underdogs have positive odds (you bet less to win more). A $1 moneyline bet on a +300 underdog returns $3.",
    "what-is-a-spread-bet": "A spread bet adds or subtracts points from a team's final score to level the playing field. If a team is -7.5, they need to win by 8 or more for your bet to pay. If they're +7.5, they can lose by up to 7 and your bet still wins. Spreads make lopsided matchups more interesting to bet on.",
    "prediction-markets-for-beginners": "Prediction markets let you trade on the outcome of real events — elections, weather, sports, economics, anything with a verifiable result. You buy Yes or No contracts priced between $0 and $1. The price reflects the market's estimated probability. If you buy Yes at $0.30 and it happens, you get $1 back. Start with $1 to learn how it works.",
    "what-is-a-parlay-bet": "A parlay combines multiple individual bets into a single wager. Every leg must win for the parlay to pay out. The odds multiply together, so payouts grow fast — but so does your chance of losing. A 3-leg parlay at even odds turns $1 into $8, but you need to go 3-for-3.",
    "same-game-parlays-explained": "A same-game parlay (SGP) combines multiple bets from a single game into one ticket. You might bet on the winner, total points, and a player prop all in one wager. The legs are correlated — they come from the same game — so the sportsbook adjusts the odds. Payouts are big, but SGPs are harder to hit than they look.",
    "what-is-a-prop-bet": "A prop bet (proposition bet) is a wager on a specific occurrence within an event, rather than the final outcome. Player props cover individual stats like touchdowns or strikeouts. Game props cover things like first team to score or whether the game goes to overtime. Prop bets let you bet on the details, not just the result.",
    "prediction-markets-vs-sports-betting": "Prediction markets and sports betting both let you wager on outcomes, but they're structured differently. Sports betting uses a bookmaker who sets odds. Prediction markets use an exchange where traders set prices by buying and selling contracts. Prediction markets cover non-sports events (elections, economics, weather) and are regulated differently in the US.",
    "can-you-legally-bet-on-elections": "Yes, you can legally bet on US elections through CFTC-regulated prediction markets like Kalshi. A 2024 federal court ruling confirmed that election event contracts are legal. Polymarket also offers election markets but is not available to US users. Traditional sportsbooks do not offer election betting in the United States.",
    "best-prediction-market-sites": "The top prediction market sites are Kalshi (CFTC-regulated, US-legal, $1 minimums), Polymarket (crypto-based, largest volume, non-US only), and PredictIt (academic platform, limited markets). For sports odds, DraftKings, FanDuel, and BetMGM offer the widest coverage. Dollar Bets curates the most interesting markets from across all platforms daily.",
    "weather-betting-markets": "Yes, you can bet on the weather. Kalshi offers regulated event contracts on temperature, rainfall, snowfall, and hurricanes. You can wager on whether it will rain in a specific city, whether temperatures will break records, or whether a hurricane will make landfall. Weather markets are some of the most entertaining longshots on prediction platforms.",
    "lottery-vs-sports-longshots": "Sports longshots give your dollar significantly better odds than the lottery. A typical lottery ticket has a 1-in-300-million chance of the jackpot. A +10000 sports longshot has a 1-in-100 implied probability — still unlikely, but 3 million times more likely than hitting the lottery. The expected return on sports longshots is also higher.",
    "weird-prediction-markets": "The weirdest active prediction markets include bets on asteroid flybys, Fed interest rate decisions, celebrity baby names, hot dog eating contest records, and whether it will snow in unlikely cities. Platforms like Kalshi and Polymarket turn almost any verifiable event into a tradeable market. Dollar Bets surfaces the strangest ones daily.",
    "weird-prop-bets": "The weirdest prop bets available right now span culture, weather, politics, and things that probably shouldn't be markets. You can bet on award show winners, reality TV outcomes, weather records, and political events that sound made up but are real. Prop bets turn the absurd corners of the world into actual wagers.",
}

# Heading rewrites — convert statement H2s to question format where it makes sense
HEADING_REWRITES = {
    # what-is-a-prediction-market
    "how prediction markets work": "How do prediction markets work?",
    "where to trade": "Where can you trade prediction markets?",
    "the dollar framing": "Why does Dollar Bets frame everything as $1?",
    # what-is-an-underdog-bet
    "how underdog odds work": "How do underdog odds work?",
    "underdogs on prediction markets": "How do underdogs work on prediction markets?",
    # how-do-longshot-odds-work
    "what the numbers mean": "What do longshot odds numbers mean?",
    "american odds decoded": "How do you read American odds?",
    "decimal and fractional": "How do decimal and fractional odds work?",
    "the catch": "What's the catch with longshot bets?",
    # betting-odds-explained
    "american odds": "How do American odds work?",
    "decimal odds": "How do decimal odds work?",
    "fractional odds": "How do fractional odds work?",
    "implied probability": "What is implied probability?",
    "the vig": "What is the vig (juice)?",
    # what-is-a-moneyline-bet
    "how moneyline odds work": "How do moneyline odds work?",
    "favorites vs underdogs": "What's the difference between favorites and underdogs?",
    "when to bet the moneyline": "When should you bet the moneyline?",
    # what-is-a-spread-bet
    "how point spreads work": "How do point spreads work?",
    "covering the spread": "What does covering the spread mean?",
    "the hook": "What is the hook in spread betting?",
    # prediction-markets-for-beginners
    "how it works": "How do prediction markets work?",
    "where to start": "Where should beginners start?",
    "what you can trade": "What can you trade on prediction markets?",
    "the $1 entry point": "Can you start with just $1?",
    # what-is-a-parlay-bet
    "how parlays work": "How do parlay bets work?",
    "the math": "How is the parlay payout calculated?",
    "why parlays are popular": "Why are parlays so popular?",
    # same-game-parlays-explained
    "how sgps work": "How do same-game parlays work?",
    "why sportsbooks love them": "Why do sportsbooks push same-game parlays?",
    "sgp strategy": "Is there a strategy for same-game parlays?",
    # what-is-a-prop-bet
    "types of prop bets": "What types of prop bets are there?",
    "player props": "What are player prop bets?",
    "game props": "What are game prop bets?",
    # prediction-markets-vs-sports-betting
    "how they're different": "How are prediction markets different from sports betting?",
    "regulation": "How are prediction markets and sportsbooks regulated?",
    "which is better": "Which is better: prediction markets or sports betting?",
    # weather-betting-markets
    "how weather markets work": "How do weather betting markets work?",
    "what you can bet on": "What weather events can you bet on?",
    "where to bet on weather": "Where can you bet on the weather?",
    # can-you-legally-bet-on-elections
    "the legal landscape": "What's the legal status of election betting?",
    "prediction markets vs sportsbooks": "Can you bet on elections at regular sportsbooks?",
    "state restrictions": "Are there state restrictions on election betting?",
}

updated = 0
for filepath in sorted(glob.glob('content/**/*.json', recursive=True)):
    with open(filepath) as f:
        data = json.load(f)
    
    slug = data.get('slug', '')
    changed = False
    
    # Add quick_answer if we have one
    if slug in QUICK_ANSWERS and not data.get('quick_answer'):
        data['quick_answer'] = QUICK_ANSWERS[slug]
        changed = True
    
    # Rewrite headings to question format
    for block in data.get('body', []):
        if block.get('type') == 'heading':
            lower = block['content'].lower().strip()
            if lower in HEADING_REWRITES:
                block['content'] = HEADING_REWRITES[lower]
                changed = True
    
    if changed:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
        updated += 1
        has_qa = bool(data.get('quick_answer'))
        q_count = sum(1 for b in data.get('body', []) if b.get('type') == 'heading' and '?' in b['content'])
        total_h = sum(1 for b in data.get('body', []) if b.get('type') == 'heading')
        print(f'Updated: {slug:50s} | qa:{has_qa} | {q_count}/{total_h} Q-headings')

print(f'\nTotal: {updated} files updated')
