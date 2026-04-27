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
    """Verify the HMAC token is valid for today or yesterday."""
    if not CMS_PASSWORD or not token:
        return False
    today = str(int(time.time()) // 86400)
    yesterday = str(int(time.time()) // 86400 - 1)
    for day in [today, yesterday]:
        expected = hmac.new(
            CMS_SECRET.encode(), f"{CMS_PASSWORD}:{day}".encode(), hashlib.sha256
        ).hexdigest()
        if hmac.compare_digest(token, expected):
            return True
    return False


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


def list_board_dates():
    """List available board dates from GitHub."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{BOARD_PATH}?ref={GITHUB_BRANCH}"
    req = urllib.request.Request(url, headers=_gh_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            files = json.loads(resp.read().decode())
        dates = []
        for f in files:
            name = f.get("name", "")
            if name.endswith(".json"):
                dates.append(name.replace(".json", ""))
        dates.sort(reverse=True)
        return dates
    except urllib.error.HTTPError:
        return []


def get_board(date_str):
    """Fetch a board JSON from GitHub. Returns (data_dict, sha) or (None, None)."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return None, None

    result = _gh_get(f"{BOARD_PATH}/{date_str}.json")
    if not result:
        return None, None

    content = base64.b64decode(result["content"]).decode()
    sha = result["sha"]
    return json.loads(content), sha


def update_board(date_str, board_data, sha):
    """Write updated board JSON to GitHub. Returns commit info."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise ValueError("invalid date format")

    content_str = json.dumps(board_data, indent=2) + "\n"
    path = f"{BOARD_PATH}/{date_str}.json"
    message = f"CMS: update board {date_str}"

    return _gh_put(path, content_str, sha=sha, message=message)


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

        # If no date, return list of available dates
        if not date_str:
            try:
                dates = list_board_dates()
                self._respond(200, {"dates": dates})
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
            result = update_board(date_str, board_data, sha)
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
