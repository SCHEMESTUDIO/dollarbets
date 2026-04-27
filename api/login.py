"""
Dollar Bets CMS — Login endpoint
POST /api/login  { "password": "..." }
Returns 200 + token on success, 401 on failure.
"""

from http.server import BaseHTTPRequestHandler
import json
import hashlib
import hmac
import os
import time


CMS_PASSWORD = os.environ.get("CMS_PASSWORD", "")
CMS_SECRET = os.environ.get("CMS_SECRET", CMS_PASSWORD)  # fallback to password


def make_token(password):
    """Create a simple HMAC token valid for 24 hours."""
    day = str(int(time.time()) // 86400)
    return hmac.new(
        CMS_SECRET.encode(), f"{password}:{day}".encode(), hashlib.sha256
    ).hexdigest()


def verify_token(token):
    """Verify the token is valid for today (or yesterday, for timezone grace)."""
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


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except (json.JSONDecodeError, ValueError):
            self._respond(400, {"error": "invalid json"})
            return

        password = body.get("password", "")

        if not CMS_PASSWORD:
            self._respond(500, {"error": "CMS_PASSWORD not configured"})
            return

        if not hmac.compare_digest(password, CMS_PASSWORD):
            self._respond(401, {"error": "wrong password"})
            return

        token = make_token(password)
        self._respond(200, {"ok": True, "token": token})

    def do_OPTIONS(self):
        self._cors_preflight()

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
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
