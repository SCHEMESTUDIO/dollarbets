#!/usr/bin/env python3
"""
Dollar Bets — Static Board Generator (v2)
Craigslist-utility aesthetic. Off-white. Emoji color squares.
"$1 → $X" payout framing. Editorial quips on every wager.
"""

import json
import sys
import os
from datetime import datetime, timezone

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "public")


def tier_emoji(tier):
    return {
        "green": "🟩",
        "yellow": "🟨",
        "orange": "🟧",
        "red": "🟥",
        "purple": "🟪",
    }.get(tier, "⬜")


def tier_label(tier):
    return {
        "green": "<5x",
        "yellow": "<10x",
        "orange": "<100x",
        "red": "<1000x",
        "purple": "infinite money glitch",
    }.get(tier, "???")


def format_payout(payout):
    if payout >= 1000:
        return f"${payout:,.0f}"
    elif payout == int(payout):
        return f"${int(payout)}"
    else:
        return f"${payout:.2f}"


def render_market_row(m, index):
    emoji = tier_emoji(m["tier"])
    payout_str = format_payout(m["payout"])
    title = m["title"]
    quip = m.get("quip", "")
    url = m["url"]

    return f"""      <li class="wager">
        <a href="{url}" target="_blank" rel="noopener">
          <span class="wager-emoji">{emoji}</span>
          <span class="wager-body">
            <span class="wager-title">{title}</span>
            <span class="wager-payout">$1 &rarr; {payout_str}</span>
            <span class="wager-quip">{quip}</span>
          </span>
        </a>
      </li>"""


def render_html(data):
    generated_at = data.get("generated_at", "")
    board = data.get("board", [])

    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        date_str = dt.strftime("%B %d, %Y")
    except (ValueError, AttributeError):
        date_str = generated_at

    market_rows = "\n".join(render_market_row(m, i) for i, m in enumerate(board))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>dollar bets — what does $1 pay?</title>
  <meta name="description" content="A buck says maybe. Daily board of the internet's most entertaining wagers.">
  <meta property="og:title" content="dollar bets — a buck says maybe.">
  <meta property="og:description" content="A buck says maybe. The internet's most entertaining wagers.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://dollarbets.lol">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>💵</text></svg>">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
      background: #f4f3ee;
      color: #2a2a2a;
      font-family: 'Courier New', Courier, monospace;
      font-size: 14px;
      line-height: 1.5;
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }}

    .container {{
      max-width: 640px;
      margin: 0 auto;
      padding: 24px 16px;
    }}

    /* === HEADER === */
    .header {{
      margin-bottom: 16px;
    }}

    .site-title {{
      font-size: 22px;
      font-weight: 700;
      color: #111;
      letter-spacing: -0.5px;
    }}

    .tagline {{
      font-size: 13px;
      color: #777;
      margin-top: 3px;
      font-style: italic;
      letter-spacing: 0.2px;
    }}

    .date-line {{
      font-size: 11px;
      color: #aaa;
      margin-top: 4px;
      letter-spacing: 0.3px;
    }}

    hr {{
      border: none;
      border-top: 1px solid #d5d4cd;
      margin: 14px 0;
    }}

    /* === LEGEND === */
    .legend {{
      font-size: 11px;
      color: #888;
      margin-bottom: 18px;
      line-height: 1.8;
      letter-spacing: 0.3px;
    }}

    /* === WAGER LIST === */
    .board {{
      list-style: none;
      padding: 0;
      margin: 0;
    }}

    .wager {{
      margin-bottom: 6px;
    }}

    .wager a {{
      display: flex;
      align-items: flex-start;
      gap: 10px;
      text-decoration: none;
      color: inherit;
      padding: 10px 12px;
      border-radius: 3px;
      background: #faf9f5;
      border: 1px solid #e8e7e0;
      border-bottom-width: 2px;
      border-bottom-color: #d8d7d0;
      transition: all 0.12s ease;
    }}

    .wager a:hover {{
      background: #fff;
      border-color: #ccc;
      border-bottom-color: #bbb;
      transform: translateY(-1px);
      box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }}

    .wager a:active {{
      transform: translateY(0);
      border-bottom-width: 1px;
      margin-bottom: 1px;
      box-shadow: none;
    }}

    .wager-emoji {{
      font-size: 16px;
      flex-shrink: 0;
      line-height: 1.5;
    }}

    .wager-body {{
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}

    .wager-payout {{
      font-size: 15px;
      font-weight: 700;
      color: #111;
      letter-spacing: -0.3px;
    }}

    .wager-title {{
      font-size: 13px;
      color: #333;
      font-weight: 700;
      line-height: 1.4;
    }}

    .wager-quip {{
      font-size: 11.5px;
      color: #777;
      font-style: italic;
      letter-spacing: 0.2px;
    }}

    /* === SIGNUP === */
    .signup {{
      margin: 28px 0;
      padding: 16px;
      border: 1px solid #d5d4cd;
      border-bottom-width: 2px;
      border-bottom-color: #c5c4bd;
      border-radius: 3px;
      background: #faf9f5;
    }}

    .signup-heading {{
      font-size: 13px;
      font-weight: 700;
      color: #111;
      margin-bottom: 4px;
    }}

    .signup-sub {{
      font-size: 11px;
      color: #999;
      margin-bottom: 10px;
    }}

    .signup-form {{
      display: flex;
      gap: 8px;
    }}

    .signup-form input {{
      flex: 1;
      background: #fff;
      border: 1px solid #ccc;
      border-radius: 2px;
      color: #222;
      font-family: 'Courier New', monospace;
      font-size: 13px;
      padding: 9px 10px;
    }}

    .signup-form input::placeholder {{
      color: #bbb;
    }}

    .signup-form input:focus {{
      outline: none;
      border-color: #999;
    }}

    .signup-form button {{
      background: #222;
      color: #f4f3ee;
      border: none;
      border-radius: 2px;
      font-family: 'Courier New', monospace;
      font-size: 12px;
      font-weight: 700;
      padding: 9px 20px;
      cursor: pointer;
      letter-spacing: 0.3px;
      transition: background 0.1s;
    }}

    .signup-form button:hover {{
      background: #444;
    }}

    .signup-form button:active {{
      background: #111;
    }}

    /* === FOOTER === */
    .footer {{
      margin-top: 28px;
      padding-top: 14px;
      border-top: 1px solid #d5d4cd;
      font-size: 10px;
      color: #b0afa8;
      line-height: 1.8;
    }}

    .footer a {{
      color: #999;
    }}

    /* === MOBILE === */
    @media (max-width: 500px) {{
      .container {{ padding: 16px 12px; }}
      .wager a {{ padding: 9px 10px; }}
      .wager-payout {{ font-size: 14px; }}
      .wager-title {{ font-size: 12px; }}
      .signup-form {{ flex-direction: column; }}
      .signup-form button {{ width: 100%; padding: 12px; }}
    }}
  </style>
</head>
<body>
  <div class="container">

    <div class="header">
      <div class="site-title">dollar bets</div>
      <div class="tagline">a buck says maybe.</div>
      <div class="date-line">{date_str}</div>
    </div>

    <hr>

    <div class="legend">
      🟩 &lt;5x &nbsp; 🟨 &lt;10x &nbsp; 🟧 &lt;100x &nbsp; 🟥 &lt;1000x &nbsp; 🟪 infinite money glitch
    </div>

    <ul class="board">
{market_rows}
    </ul>

    <hr>

    <div class="signup">
      <div class="signup-heading">get tomorrow's board in your inbox</div>
      <div class="signup-sub">free daily email. no spam. unsubscribe anytime.</div>
      <form class="signup-form" id="signup-form" method="POST" action="https://subscribe-forms.beehiiv.com/c3a5e668-1de1-4095-b6ab-094a1c0e2764" target="_blank">
        <input type="email" name="form[email]" placeholder="you@email.com" required>
        <button type="submit">subscribe</button>
      </form>
    </div>

    <div class="footer">
      <p>dollar bets is entertainment, not financial advice. not a sportsbook. not affiliated with kalshi.<br>
      all markets link to <a href="https://kalshi.com" target="_blank">kalshi.com</a>. you must be 18+ to trade. bet responsibly.<br>
      "$1 pays" = what one dollar returns if the event happens. actual returns depend on price at purchase.</p>
      <p style="margin-top:6px">&copy; {{datetime.now().year}} dollarbets.lol &middot; <a href="mailto:james.lamon@gmail.com">contact</a></p>
    </div>

  </div>
</body>
</html>"""


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    html = render_html(data)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, "index.html")

    with open(out_path, "w") as f:
        f.write(html)

    print(f"[generate] Wrote {out_path} ({len(data.get('board', []))} markets)", file=sys.stderr)


if __name__ == "__main__":
    main()
