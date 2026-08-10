#!/usr/bin/env python3
"""
Dollar Bets — Email Signup Endpoint (/api/subscribe)

Adds a contact to the Dollar Bets audience in Resend. Replaces the old
beehiiv iframe embed (retired 2026-08-09) so the list lives in our own
Resend account as a distinct audience for future targeting.

Env vars (Vercel → Settings → Environment Variables):
    RESEND_API_KEY      — Resend API key (create in Resend dashboard → API Keys)
    RESEND_AUDIENCE_ID  — the "Dollar Bets" audience id (Resend → Audiences)

Vercel Python serverless function using BaseHTTPRequestHandler.
"""

import json
import os
import re
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

# Pragmatic email shape check — real validation is Resend's problem.
# Bounded length prevents junk payloads.
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,24}$")

_MAX_BODY = 4096


class handler(BaseHTTPRequestHandler):
    def _respond(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._respond(405, {"error": "POST only"})

    def do_POST(self):
        try:
            length = int(self.headers.get("content-length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > _MAX_BODY:
            self._respond(400, {"error": "bad request"})
            return

        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._respond(400, {"error": "bad request"})
            return

        # Honeypot: bots fill the hidden "website" field. Pretend success
        # so they move on; no contact is created.
        if (data.get("website") or "").strip():
            self._respond(200, {"ok": True})
            return

        email = (data.get("email") or "").strip().lower()
        if not _EMAIL_RE.fullmatch(email):
            self._respond(400, {"error": "that doesn't look like an email address"})
            return

        api_key = os.environ.get("RESEND_API_KEY", "")
        audience_id = os.environ.get("RESEND_AUDIENCE_ID", "")
        if not api_key or not audience_id:
            # Env not configured yet — fail soft, never expose internals.
            self._respond(503, {"error": "signups are napping — try again later"})
            return

        req = urllib.request.Request(
            f"https://api.resend.com/audiences/{audience_id}/contacts",
            data=json.dumps({"email": email, "unsubscribed": False}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            self._respond(200, {"ok": True})
        except urllib.error.HTTPError as e:
            # 409 = already subscribed → success from the user's POV.
            if e.code == 409:
                self._respond(200, {"ok": True})
            else:
                self._respond(502, {"error": "signup didn't take — try again later"})
        except Exception:
            self._respond(502, {"error": "signup didn't take — try again later"})

    def log_message(self, fmt, *args):  # keep function logs quiet
        pass
