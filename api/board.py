"""
Dollar Bets CMS — Board endpoint
GET  /api/board?date=2026-04-26   → returns board JSON for that date
POST /api/board                   → updates board JSON via GitHub commit

Requires env vars:
  CMS_PASSWORD  — shared editor password
  CMS_SECRET    — HMAC signing key (falls back to CMS_PASSWORD)
  GITHUB_TOKEN  — personal access token with repo write access
  GITHUB_REPO   — e.g. "username/dollarbets"
  GITHUB_BRANCH — optional, defaults to "main"
"""

from http.server import BaseHTTPRequestHandler
import json
import hashlib
import hmac
import os
import re
import time
import base64
import urllib.request
import urllib.error
import urllib.parse


# ── Inline auth (Vercel runs each function in isolation) ──

CMS_PASSWORD = os.environ.get("CMS_PASSWORD", "")
CMS_SECRET = os.environ.get("CMS_SECRET", CMS_PASSWORD)


def verify_token(token):
    """Verify the HMAC token is valid for the current UTC day.

    Token TTL is one UTC day. Earlier versions accepted yesterday's token as
    well for a 48h window — closed because /api/login has no rate limiting.
    """
    if not CMS_PASSWORD or not token:
        return False
    today = str(int(time.time()) // 86400)
    expected = hmac.new(
        CMS_SECRET.encode(), f"{CMS_PASSWORD}:{today}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(token, expected)


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_API = "https://api.github.com"
BOARD_PATH = "data/boards"


def _gh_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DollarBets-CMS/1.0",
    }


def _gh_get(path):
    """GET from GitHub API."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}?ref={GITHUB_BRANCH}"
    req = urllib.request.Request(url, headers=_gh_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _gh_put(path, content_str, sha=None, message="CMS edit"):
    """PUT (create or update) a file on GitHub."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    body = {
        "message": message,
        "content": base64.b64encode(content_str.encode()).decode(),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        body["sha"] = sha

    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={
        **_gh_headers(),
        "Content-Type": "application/json",
    }, method="PUT")

    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def list_board_dates(board_type="daily"):
    """List available board dates from GitHub.

    board_type: "daily" for prediction market boards, "sports" for underdogs boards.
    """
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{BOARD_PATH}?ref={GITHUB_BRANCH}"
    req = urllib.request.Request(url, headers=_gh_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            files = json.loads(resp.read().decode())
        dates = []
        for f in files:
            name = f.get("name", "")
            if not name.endswith(".json"):
                continue
            stem = name.replace(".json", "")
            if board_type == "sports":
                if name.startswith("sports-"):
                    dates.append(stem)
            else:
                # Daily boards: only pure date files (YYYY-MM-DD.json)
                if stem[0:1].isdigit():
                    dates.append(stem)
        dates.sort(reverse=True)
        return dates
    except urllib.error.HTTPError:
        return []


def _validate_board_filename(date_str):
    """Validate and return the filename for a board date string.
    Accepts '2026-05-02' (daily) or 'sports-2026-05-02' (sports).
    """
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return f"{date_str}.json"
    if re.match(r"^sports-\d{4}-\d{2}-\d{2}$", date_str):
        return f"{date_str}.json"
    return None


def get_board(date_str):
    """Fetch a board JSON from GitHub. Returns (data_dict, sha) or (None, None)."""
    filename = _validate_board_filename(date_str)
    if not filename:
        return None, None

    result = _gh_get(f"{BOARD_PATH}/{filename}")
    if not result:
        return None, None

    content = base64.b64decode(result["content"]).decode()
    sha = result["sha"]
    return json.loads(content), sha


def update_board(date_str, board_data, sha):
    """Write updated board JSON to GitHub. Returns commit info."""
    filename = _validate_board_filename(date_str)
    if not filename:
        raise ValueError("invalid date format")

    content_str = json.dumps(board_data, indent=2) + "\n"
    path = f"{BOARD_PATH}/{filename}"
    board_label = "sports board" if date_str.startswith("sports-") else "board"
    message = f"CMS: update {board_label} {date_str}"

    return _gh_put(path, content_str, sha=sha, message=message)


# ── Quip override tracking ────────────────────────────────

OVERRIDES_PATH = "data/quip-overrides.json"


def extract_overrides(old_board, new_board, date_str):
    """Compare two boards and return list of quip overrides."""
    old_bets = {b.get("title", ""): b for b in (old_board.get("board") or [])}
    overrides = []

    for bet in (new_board.get("board") or []):
        title = bet.get("title", "")
        if title in old_bets:
            old_quip = old_bets[title].get("quip", "")
            new_quip = bet.get("quip", "")
            if old_quip and new_quip and old_quip != new_quip:
                overrides.append({
                    "date": date_str,
                    "title": title,
                    "category": bet.get("category", ""),
                    "payout": bet.get("payout", 0),
                    "tier": bet.get("tier", ""),
                    "original_quip": old_quip,
                    "editor_quip": new_quip,
                })
    return overrides


def log_overrides(overrides):
    """Append quip overrides to the overrides file in the repo."""
    if not overrides:
        return

    # Load existing overrides
    existing = []
    existing_sha = None
    result = _gh_get(OVERRIDES_PATH)
    if result:
        try:
            content = base64.b64decode(result["content"]).decode()
            existing = json.loads(content)
            existing_sha = result["sha"]
        except (json.JSONDecodeError, KeyError):
            pass

    # Append new overrides
    existing.extend(overrides)

    # Cap at 500 most recent to keep the file manageable
    if len(existing) > 500:
        existing = existing[-500:]

    content_str = json.dumps(existing, indent=2) + "\n"
    message = f"CMS: log {len(overrides)} quip override(s)"

    try:
        _gh_put(OVERRIDES_PATH, content_str, sha=existing_sha, message=message)
    except Exception:
        # Don't let override logging break the main save
        pass


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Auth check
        token = self._get_token()
        if not verify_token(token):
            self._respond(401, {"error": "unauthorized"})
            return

        if not GITHUB_TOKEN or not GITHUB_REPO:
            self._respond(500, {"error": "GitHub not configured"})
            return

        # Parse query params
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        date_str = params.get("date", [None])[0]
        board_type = params.get("type", ["daily"])[0]

        # If no date, return list of available dates
        if not date_str:
            try:
                dates = list_board_dates(board_type=board_type)
                self._respond(200, {"dates": dates, "board_type": board_type})
            except Exception as e:
                self._respond(500, {"error": str(e)})
            return

        # Return board for specific date
        try:
            data, sha = get_board(date_str)
            if data is None:
                self._respond(404, {"error": f"no board for {date_str}"})
                return
            self._respond(200, {"date": date_str, "sha": sha, "board": data})
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def do_POST(self):
        # Auth check
        token = self._get_token()
        if not verify_token(token):
            self._respond(401, {"error": "unauthorized"})
            return

        if not GITHUB_TOKEN or not GITHUB_REPO:
            self._respond(500, {"error": "GitHub not configured"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except (json.JSONDecodeError, ValueError):
            self._respond(400, {"error": "invalid json"})
            return

        date_str = body.get("date")
        sha = body.get("sha")
        board_data = body.get("board")

        if not date_str or not sha or not board_data:
            self._respond(400, {"error": "missing date, sha, or board"})
            return

        try:
            # Fetch current board to diff for quip overrides
            old_board, _ = get_board(date_str)

            result = update_board(date_str, board_data, sha)

            # Log quip overrides (non-blocking — failures won't break save)
            if old_board:
                overrides = extract_overrides(old_board, board_data, date_str)
                if overrides:
                    log_overrides(overrides)

            self._respond(200, {
                "ok": True,
                "commit": result.get("commit", {}).get("sha", ""),
                "message": f"Board {date_str} updated. Rebuild triggered.",
            })
        except urllib.error.HTTPError as e:
            err_body = e.read().decode() if e.fp else ""
            if e.code == 409:
                self._respond(409, {
                    "error": "conflict — board was modified by someone else. Refresh and try again.",
                    "detail": err_body,
                })
            else:
                self._respond(e.code, {"error": f"GitHub API error: {e.code}", "detail": err_body})
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def do_OPTIONS(self):
        self._cors_preflight()

    def _get_token(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return ""

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _cors_preflight(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
