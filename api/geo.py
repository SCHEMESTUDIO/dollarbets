#!/usr/bin/env python3
"""
Dollar Bets — Geo Detection Endpoint (/api/geo)

Returns the user's country code from Vercel's x-vercel-ip-country header.
Used by client-side JS to soften/hide CTAs in restricted jurisdictions, and
(since 2026-09-19) by generate.py's analytics_head() to decide whether the
GA4 consent banner is required: `consent_required` is true for the EEA, UK
and Switzerland, and true when the country is unknown (fail-safe).
Reached at /api/geo/ (trailing slash — the site-wide trailingSlash redirect
308s /api/geo; there is no vercel.json rewrite, filesystem routing serves it).
"""

import json
import os
from http.server import BaseHTTPRequestHandler


def load_geo_compliance():
    """Load geo_compliance config from partners.json."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "partners.json"
    )
    try:
        with open(config_path) as f:
            config = json.load(f)
        return config.get("geo_compliance", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# EU-27 + EEA (IS, LI, NO) + UK + CH: where analytics cookies need opt-in consent.
CONSENT_COUNTRIES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES",
    "SE", "IS", "LI", "NO", "GB", "CH",
}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        user_country = self.headers.get("x-vercel-ip-country", "")
        geo_config = load_geo_compliance()

        commentary_only = user_country.upper() in geo_config.get("commentary_only_countries", []) if user_country else False

        response = {
            "country": user_country or None,
            "commentary_only": commentary_only,
            "consent_required": (not user_country) or user_country.upper() in CONSENT_COUNTRIES,
        }

        if commentary_only:
            response["cta_label"] = geo_config.get("commentary_only_cta", "view market info")
            response["banner"] = geo_config.get("commentary_only_banner", "")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "private, max-age=3600")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))
