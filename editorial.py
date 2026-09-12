"""Editorial standards helpers (adopted 2026-09-12): casing, datelines, dash discipline.

House style from this date:
- Headlines (H1, <title>) in Title Case. Section headings, UI labels, buttons, strips in
  sentence case. All-lowercase display text is retired site-wide.
- Datelines in NYT/AP form: "Sept. 12, 2026". Bylines "By Dollar Bets Staff".
- Em dashes: at most two per page in body copy; the rest become commas.

Everything here is conservative: a string that already carries mixed case is left alone,
so hand-cased text and proper nouns survive. Only all-lowercase strings are re-cased.
"""
import re
from datetime import datetime, date

# Canonical spellings for words that must keep their case inside sentence-cased text.
PROPER = {}
for w in ("Kalshi Polymarket PredictIt Manifold Metaculus Robinhood Coinbase DraftKings FanDuel Underdog Novig ProphetX Fanatics "
          "Sporttrade Nadex Crypto.com OG.com Binance Bitcoin Ethereum Dogecoin Solana Tesla SpaceX NASA OpenAI Nvidia Apple Google "
          "Amazon Netflix Disney HBO Spotify TikTok Reddit Twitter YouTube Instagram Facebook Meta Microsoft "
          "Trump Biden Harris Vance Musk Newsom Ossoff Rubio Buttigieg Shapiro Powell Bezos Zuckerberg Altman Swift Kelce Beyoncé Drake "
          "Bolsonaro Putin Zelensky Netanyahu Macron Starmer Modi Xi "
          "America American Americans US U.S. USA UK EU Europe European Canada Mexico China Chinese Russia Russian Iran Iranian Israel "
          "Israeli Ukraine Ukrainian India Japan Brazil France French Germany German Britain British England Sweden Swedish Nigeria "
          "Washington Nevada Michigan Massachusetts Utah Ohio Arizona Maryland Texas California Florida Georgia Maine Alaska Iowa "
          "Kansas Kentucky Louisiana Montana Nebraska Oregon Tennessee Virginia Wyoming Illinois Colorado Delaware Idaho Minnesota "
          "Mississippi Missouri Oklahoma Pennsylvania Vermont Wisconsin Hawaii Indiana Alabama Arkansas Connecticut York Jersey "
          "Carolina Dakota Hampshire Rhode Island NYC Vegas London Paris Moscow Kyiv Beijing Tehran Gaza Hormuz "
          "Congress Senate House Supreme Court White Fed FOMC CFTC SEC FTC OMB OPM DOJ FBI CIA NATO UN WHO IRS GDP CPI ETF IPO AI GPT SCOTUS POTUS "
          "Republican Republicans Democrat Democrats Democratic GOP MAGA "
          "NFL NBA MLB NHL WNBA MLS UFC WWE NCAA PGA ATP F1 NASCAR FIFA UEFA Olympics Olympic "
          "Oscars Oscar Emmys Emmy Grammys Grammy Tonys Globes BAFTA Eurovision Survivor Bachelor Bachelorette Traitors "
          "Super Bowl Cup Series Finals Madness Derby Wimbledon Masters Christmas Halloween Thanksgiving Easter "
          "January February March April May June July August September October November December "
          "Monday Tuesday Wednesday Thursday Friday Saturday Sunday "
          "Hall Filth Dollar Bets Odds Desk").split():
    PROPER[w.lower()] = w
for w in ("cup series finals masters court white island york jersey carolina dakota hampshire rhode hall filth dollar bets odds desk "
          "swift meta apple may march who un underdog").split():
    PROPER.pop(w, None)
for w in ("i",): PROPER[w] = "I"
PHRASES = {"dollar bets": "Dollar Bets", "hall of filth": "Hall of Filth", "odds desk": "Odds Desk", "new york": "New York",
           "new jersey": "New Jersey", "north carolina": "North Carolina", "south carolina": "South Carolina", "north dakota": "North Dakota",
           "south dakota": "South Dakota", "new hampshire": "New Hampshire", "rhode island": "Rhode Island", "west virginia": "West Virginia",
           "new mexico": "New Mexico", "white house": "White House", "supreme court": "Supreme Court", "super bowl": "Super Bowl",
           "world cup": "World Cup", "world series": "World Series", "march madness": "March Madness", "wall street": "Wall Street",
           "ball street": "Ball Street", "kentucky derby": "Kentucky Derby", "taylor swift": "Taylor Swift", "elon musk": "Elon Musk",
           "big brother": "Big Brother", "love island": "Love Island", "stanley cup": "Stanley Cup", "nba finals": "NBA Finals",
           "the ocho": "The Ocho", "the lineup": "The Lineup", "black swans": "Black Swans", "combo meal": "Combo Meal"}
def _apply_phrases(s):
    low = s.lower()
    for k, v in PHRASES.items():
        i = low.find(k)
        while i != -1:
            s = s[:i] + v + s[i+len(k):]; low = s.lower(); i = low.find(k, i + len(k))
    return s

SMALL = {"a", "an", "the", "and", "but", "or", "nor", "for", "so", "yet", "at", "by", "in", "of", "on", "to", "up", "vs", "vs.", "v.", "per", "via", "as", "if", "than"}

_WORD = re.compile(r"[A-Za-z][A-Za-z'’.&-]*")


def learn_proper_nouns(texts):
    """Words that appear Capitalized mid-sentence in the page's own copy are proper nouns
    for this page. Returns a {lower: Canonical} dict merged over PROPER."""
    found = dict(PROPER)
    cand = {}; lowers = set()
    for t in texts:
        if not t: continue
        t = re.sub(r"<[^>]+>", " ", str(t))
        for w in _WORD.findall(t):
            if w.islower(): lowers.add(w.strip(".&-"))
        for sent in re.split(r"(?<=[.!?])\s+", t):
            words = _WORD.findall(sent)
            for w in words[1:]:
                core = w.strip(".&-")
                if core[:1].isupper() and core.lower() not in SMALL and len(core) > 1 and not core.isupper():
                    cand.setdefault(core.lower(), core)
                elif core.isupper() and len(core) >= 2:
                    cand.setdefault(core.lower(), core)
    # A word that also appears lowercase somewhere on the page is a common noun that happened
    # to sit inside a name ("Dollar Bets", "Odds Desk"); only words never seen lowercase count.
    for k, v in cand.items():
        if k not in lowers: found.setdefault(k, v)
    return found


def _is_all_lower(s):
    """House-style lowercase = the first letter is lowercase and no word is Capitalized
    (all-caps acronyms like US or NBA are allowed inside a lowercase string)."""
    m = re.search(r"[A-Za-z]", s or "")
    if not m or not s[m.start()].islower(): return False
    for w in _WORD.findall(s):
        for part in re.split(r"[-/.]", w):
            if part and part[0].isupper() and not part.isupper(): return False
    return True


def _fix_word(w, proper):
    key = w.lower().strip(".,;:!?()\"'’")
    if key in proper:
        canon = proper[key]
        return w.lower().replace(key, canon, 1) if key in w.lower() else canon
    return None


def _cap_first(s):
    m = re.search(r"[A-Za-z]", s or "")
    return s if not m else s[:m.start()] + s[m.start()].upper() + s[m.start()+1:]


def sentence_case(s, proper=None):
    """'what counts as a shutdown?' -> 'What counts as a shutdown?'. Mixed-case input only gets its first letter capitalized."""
    if not s: return s
    if not _is_all_lower(s): return _cap_first(s)
    proper = proper or PROPER
    out = []
    for i, tok in enumerate(re.split(r"(\s+)", s)):
        if not tok or tok.isspace(): out.append(tok); continue
        fixed = _fix_word(tok, proper)
        out.append(fixed if fixed else tok)
    s2 = _apply_phrases("".join(out))
    m = re.search(r"[A-Za-z]", s2)
    if m: s2 = s2[:m.start()] + s2[m.start()].upper() + s2[m.start()+1:]
    return s2


def title_case(s, proper=None):
    """AP-style headline case for all-lowercase input. Mixed-case input only gets its first letter capitalized."""
    if not s: return s
    if not _is_all_lower(s): return _cap_first(s)
    proper = proper or PROPER
    toks = re.split(r"(\s+)", s)
    words = [t for t in toks if t and not t.isspace()]
    out = []; wi = 0; after_colon = True
    for tok in toks:
        if not tok or tok.isspace(): out.append(tok); continue
        wi += 1
        fixed = _fix_word(tok, proper)
        if fixed: cand = fixed
        else:
            core = tok.lower().strip(".,;:!?()\"'’")
            if core in SMALL and not after_colon and wi != 1 and wi != len(words):
                cand = tok.lower()
            else:
                parts = re.split(r"([-/])", tok)
                cand = "".join(pt if pt.isupper() or pt in "-/" else pt.lower()[:1].upper() + pt.lower()[1:] for pt in parts)
        out.append(cand)
        after_colon = tok.endswith(":")
    return _apply_phrases("".join(out))


_MONTHS = {1: "Jan.", 2: "Feb.", 3: "March", 4: "April", 5: "May", 6: "June", 7: "July", 8: "Aug.", 9: "Sept.", 10: "Oct.", 11: "Nov.", 12: "Dec."}


def nyt_date(value):
    """'2026-09-12' -> 'Sept. 12, 2026'. Accepts ISO strings, date, datetime; returns '' on failure."""
    if not value: return ""
    try:
        if isinstance(value, (datetime, date)): d = value
        else: d = datetime.fromisoformat(str(value)[:10])
        return f"{_MONTHS[d.month]} {d.day}, {d.year}"
    except Exception:
        return str(value)


_DASH = re.compile(r"\s*(?:—|&mdash;|–|&ndash;)\s*")


def reduce_dashes(text, keep=2):
    """Keep the first `keep` em/en dashes in a block of copy; turn the rest into commas."""
    if not text: return text, 0
    n = 0
    def rep(m):
        nonlocal n
        n += 1
        if n <= keep: return " — "
        return ", "
    out = _DASH.sub(rep, text)
    out = re.sub(r",\s*,", ",", out).replace(" ,", ",")
    return out, max(0, n - keep)


def recase_headings_html(html, proper=None):
    """Safety net for generated HTML: Title Case all-lowercase page-title H1s; sentence-case
    all-lowercase H2/H3 text. Only touches headings whose text is entirely lowercase."""
    def h1(m): return m.group(1) + title_case(m.group(2), proper) + m.group(3)
    def h23(m): return m.group(1) + sentence_case(m.group(2), proper) + m.group(3)
    html = re.sub(r'(<h1 class="page-title"[^>]*>)([^<]+)(</h1>)', h1, html)
    html = re.sub(r'(<h[23](?:\s[^>]*)?>)([^<]+)(</h[23]>)', h23, html)
    return html
