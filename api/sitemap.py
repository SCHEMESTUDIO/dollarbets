#!/usr/bin/env python3
"""
api/sitemap.py — serve /sitemap.xml through a serverless function.

WHY THIS EXISTS (2026-08-20): GSC has said "Sitemap could not be read" for
every sitemap on this host since May — XML, cache-busted XML, and the plain
text sitemap-urls.txt alike — while parsing the same formats fine on a
non-Vercel host (headshotswithabird.com) and fetching regular pages here
fine. Fixing Content-Type/Content-Disposition on the static path did not
help. Conclusion: something about Vercel's *static file* response path
breaks Google's sitemap parser; serving the identical bytes from the
serverless path sidesteps it. vercel.json 307-redirects /sitemap.xml here
(redirects fire before the filesystem check — same mechanism as the
apex→www host redirect, which already fires on paths with static files).

Content source, in order:
  1. public/sitemap.xml bundled into this function at build time
     (vercel.json → functions → includeFiles).
  2. Fallback: fetch /sitemap-data.xml — a second copy generate.py now
     writes, on a path with no redirect, so no loop is possible.
"""

import os
import urllib.request
from http.server import BaseHTTPRequestHandler

DATA_URL = "https://www.dollarbets.lol/sitemap-data.xml"


def _load_local():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.getcwd(), "public", "sitemap.xml"),
        os.path.join(here, "..", "public", "sitemap.xml"),
        "/var/task/public/sitemap.xml",
    ]
    for path in candidates:
        try:
            with open(path, "rb") as f:
                data = f.read()
            if data.lstrip().startswith(b"<?xml") or b"<urlset" in data[:500]:
                return data, "bundle:" + path
        except OSError:
            continue
    return None, None


def _load_http():
    req = urllib.request.Request(DATA_URL)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read(), "http"


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        data, source = _load_local()
        if data is None:
            try:
                data, source = _load_http()
            except Exception as exc:  # noqa: BLE001 — surface any failure as 503
                body = ("sitemap unavailable: %s" % exc).encode()
                self.send_response(503)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
        self.send_response(200)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=0, must-revalidate")
        self.send_header("X-Sitemap-Source", source)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.end_headers()
