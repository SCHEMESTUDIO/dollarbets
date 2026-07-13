#!/usr/bin/env python3
"""
gsc_pull.py — Pull Google Search Console data for dollarbets.lol via the
Search Console API and write CSVs in the exact layout the Monday
weekly-gsc-analysis task reads.

Zero pip dependencies: Python stdlib only (system `openssl` is used only by the
legacy service-account JWT path / --selftest). Runs on macOS system python3.

Replaces the Claude-in-Chrome DOM scrape (retired 2026-06-11).

Auth (2026-06-15): primary path is gcloud Application Default Credentials
(user OAuth refresh token), because the org policy
iam.managed.disableServiceAccountKeyCreation blocks downloadable
service-account keys. The original service-account keyfile path still works as
a fallback if such a key ever becomes available.

Output layout (monday = most recent Monday on or before today):
  gsc-data/weekly/{monday}/   Queries.csv Pages.csv Countries.csv Devices.csv
                              Search appearance.csv Chart.csv Filters.csv
  gsc-data/28day/{monday}/    same set
  gsc-data/page-detail/{monday}/{slug}-Queries.csv   (top pages by 28d impressions)

Setup (one-time): see scripts/GSC-API-SETUP.md
  Primary (ADC / keyless):
  - gcloud auth application-default login \
      --scopes=https://www.googleapis.com/auth/cloud-platform,\
https://www.googleapis.com/auth/webmasters.readonly
  - The logged-in user must already have access to the sc-domain property
    (you do — you own dollarbets.lol in Search Console).
  - If you hit a quota/"API not enabled" 403:
      gcloud services enable searchconsole.googleapis.com --project=<PROJECT_ID>
      gcloud auth application-default set-quota-project <PROJECT_ID>
  Legacy (service-account key, only if the org policy is ever lifted):
  - Key JSON at ~/.config/dollarbets/gsc-service-account.json (chmod 600)

Usage:
  python3 scripts/gsc_pull.py            # full pull (auto-detects ADC vs SA key)
  python3 scripts/gsc_pull.py --selftest # validate creds locally, no network

Notes:
  - Date window ends 2 days ago (GSC data for the last ~48h is incomplete).
  - searchAppearance often has no rows for small sites; "(no data)" is written,
    matching the old scrape convention.
  - API positions have full precision; we format to 1 decimal to match the
    existing CSVs so week-over-week diffs stay comparable.
"""

import argparse
import base64
import csv
import datetime as dt
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

PROPERTY = "sc-domain:dollarbets.lol"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://www.googleapis.com/webmasters/v3/sites"
ROW_LIMIT = 1000
PAGE_DETAIL_COUNT = 8  # top pages by 28d impressions to pull query detail for

DEFAULT_SA_FILE = os.path.expanduser("~/.config/dollarbets/gsc-service-account.json")
DEFAULT_ADC_FILE = os.path.expanduser(
    "~/.config/gcloud/application_default_credentials.json")
QUOTA_PROJECT = None  # from ADC quota_project_id; sent as x-goog-user-project
# repo site dir = parent of the scripts/ dir this file lives in
SITE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COUNTRY_NAMES = {
    "usa": "United States", "ind": "India", "gbr": "United Kingdom",
    "can": "Canada", "aus": "Australia", "deu": "Germany", "fra": "France",
    "nld": "Netherlands", "pak": "Pakistan", "phl": "Philippines",
    "nga": "Nigeria", "bgd": "Bangladesh", "idn": "Indonesia",
    "sgp": "Singapore", "are": "United Arab Emirates", "mex": "Mexico",
    "bra": "Brazil", "esp": "Spain", "ita": "Italy", "pol": "Poland",
    "irl": "Ireland", "nzl": "New Zealand", "zaf": "South Africa",
    "ken": "Kenya", "mys": "Malaysia", "tha": "Thailand", "vnm": "Vietnam",
    "jpn": "Japan", "kor": "South Korea", "chn": "China", "tur": "Turkey",
    "ukr": "Ukraine", "rou": "Romania", "prt": "Portugal", "swe": "Sweden",
    "nor": "Norway", "dnk": "Denmark", "fin": "Finland", "che": "Switzerland",
    "aut": "Austria", "bel": "Belgium", "grc": "Greece", "isr": "Israel",
    "sau": "Saudi Arabia", "egy": "Egypt", "lka": "Sri Lanka", "npl": "Nepal",
    "col": "Colombia", "arg": "Argentina", "chl": "Chile", "per": "Peru",
}


def log(msg):
    print(f"[gsc_pull] {msg}", file=sys.stderr)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def sign_rs256(signing_input: bytes, private_key_pem: str) -> bytes:
    """RS256-sign with the system openssl binary (no pip crypto deps)."""
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as kf:
        os.chmod(kf.name, 0o600)
        kf.write(private_key_pem)
        key_path = kf.name
    try:
        proc = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", key_path],
            input=signing_input, capture_output=True, check=True,
        )
        return proc.stdout
    finally:
        os.unlink(key_path)


def make_jwt(sa: dict, now: int = None) -> str:
    now = now or int(dt.datetime.now(dt.timezone.utc).timestamp())
    header = b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = b64url(json.dumps({
        "iss": sa["client_email"],
        "scope": SCOPE,
        "aud": TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }).encode())
    signing_input = f"{header}.{claims}".encode("ascii")
    signature = b64url(sign_rs256(signing_input, sa["private_key"]))
    return f"{header}.{claims}.{signature}"


def _token_request(body: bytes) -> str:
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)["access_token"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"Token exchange failed (HTTP {e.code}): {detail}") from e


def get_access_token_service_account(sa: dict) -> str:
    return _token_request(urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": make_jwt(sa),
    }).encode("ascii"))


def get_access_token_authorized_user(creds: dict) -> str:
    return _token_request(urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
    }).encode("ascii"))


def get_access_token(creds: dict) -> str:
    """Dispatch on credential type: gcloud ADC user creds vs SA key."""
    ctype = creds.get("type")
    if ctype == "authorized_user":
        return get_access_token_authorized_user(creds)
    if ctype == "service_account" or "private_key" in creds:
        return get_access_token_service_account(creds)
    raise RuntimeError(f"Unrecognized credential type: {ctype!r}")


def query_api(token: str, body: dict) -> list:
    url = f"{API_BASE}/{urllib.parse.quote(PROPERTY, safe='')}/searchAnalytics/query"
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {token}"}
    if QUOTA_PROJECT:
        headers["x-goog-user-project"] = QUOTA_PROJECT
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
        headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp).get("rows", [])
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"API query failed (HTTP {e.code}): {detail}\nBody: {body}") from e


# ---------- formatting (match existing GSC-UI-style CSVs) ----------

def fmt_ctr(ctr: float) -> str:
    pct = ctr * 100
    s = f"{pct:.1f}"
    if s.endswith(".0"):
        s = s[:-2]
    return f"{s}%"


def fmt_pos(pos: float) -> str:
    return f"{pos:.1f}"


def fmt_day(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def rows_to_csv(rows: list, first_col_header: str, key_fn=None) -> str:
    """rows: API rows with .keys[0] as the dimension value."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow([first_col_header, "Clicks", "Impressions", "CTR", "Position"])
    for r in rows:
        key = r["keys"][0]
        if key_fn:
            key = key_fn(key)
        w.writerow([key, r["clicks"], r["impressions"],
                    fmt_ctr(r["ctr"]), fmt_pos(r["position"])])
    return out.getvalue()


def write_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    log(f"wrote {os.path.relpath(path, SITE_DIR)} ({len(content)} bytes)")


def url_slug(page_url: str) -> str:
    path = urllib.parse.urlparse(page_url).path.strip("/")
    return path.replace("/", "_") if path else "root"


# ---------- pull logic ----------

def pull_range(token: str, start: dt.date, end: dt.date, out_dir: str, label: str):
    base = {"startDate": start.isoformat(), "endDate": end.isoformat(),
            "rowLimit": ROW_LIMIT}

    specs = [
        ("query", "Queries.csv", "Top queries", None),
        ("page", "Pages.csv", "Top pages", None),
        ("country", "Countries.csv", "Country",
         lambda c: COUNTRY_NAMES.get(c.lower(), c.upper())),
        ("device", "Devices.csv", "Device", lambda d: d.capitalize()),
        ("searchAppearance", "Search appearance.csv", "Search Appearance", None),
        ("date", "Chart.csv", "Day", fmt_day),
    ]
    for dim, fname, header, key_fn in specs:
        rows = query_api(token, {**base, "dimensions": [dim]})
        if dim == "date":
            rows.sort(key=lambda r: r["keys"][0], reverse=True)
        if not rows and dim == "searchAppearance":
            write_file(os.path.join(out_dir, fname), "(no data)")
            continue
        write_file(os.path.join(out_dir, fname),
                   rows_to_csv(rows, header, key_fn))

    write_file(os.path.join(out_dir, "Filters.csv"),
               f"Filter,Value\nSearch type,Web\nDate,Last {label}\n")


def pull_page_detail(token: str, start: dt.date, end: dt.date,
                     pages_28d: list, out_dir: str):
    top = sorted(pages_28d, key=lambda r: r["impressions"], reverse=True)
    top = top[:PAGE_DETAIL_COUNT]
    for r in top:
        page_url = r["keys"][0]
        rows = query_api(token, {
            "startDate": start.isoformat(), "endDate": end.isoformat(),
            "rowLimit": ROW_LIMIT, "dimensions": ["query"],
            "dimensionFilterGroups": [{"filters": [
                {"dimension": "page", "operator": "equals",
                 "expression": page_url}]}],
        })
        fname = f"{url_slug(page_url)}-Queries.csv"
        write_file(os.path.join(out_dir, fname),
                   rows_to_csv(rows, "Top queries"))


def selftest() -> int:
    """Validate available credentials locally (no network)."""
    if os.path.exists(DEFAULT_ADC_FILE):
        with open(DEFAULT_ADC_FILE) as f:
            c = json.load(f)
        if c.get("type") == "authorized_user":
            ok = all(c.get(k) for k in
                     ("client_id", "client_secret", "refresh_token"))
            fields = "OK" if ok else "INCOMPLETE"
            qp = c.get("quota_project_id") or (
                "NONE (set with: gcloud auth application-default "
                "set-quota-project <PROJECT_ID>)")
            log(f"selftest: ADC authorized_user creds present at "
                f"{DEFAULT_ADC_FILE}; required fields {fields}; "
                f"quota_project={qp}")
            return 0 if ok else 1
    log("selftest: no ADC file; testing openssl JWT signing path…")
    log("selftest: generating throwaway RSA key…")
    key = subprocess.run(["openssl", "genrsa", "2048"],
                         capture_output=True, check=True).stdout.decode()
    fake_sa = {"client_email": "test@selftest.iam.gserviceaccount.com",
               "private_key": key}
    jwt = make_jwt(fake_sa, now=1700000000)
    h, c, s = jwt.split(".")
    # verify the signature with openssl
    sig = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as kf:
        kf.write(key)
        keyf = kf.name
    pub = subprocess.run(["openssl", "rsa", "-in", keyf, "-pubout"],
                         capture_output=True, check=True).stdout
    with tempfile.NamedTemporaryFile("wb", suffix=".pem", delete=False) as pf:
        pf.write(pub)
        pubf = pf.name
    with tempfile.NamedTemporaryFile("wb", suffix=".sig", delete=False) as sf:
        sf.write(sig)
        sigf = sf.name
    try:
        v = subprocess.run(
            ["openssl", "dgst", "-sha256", "-verify", pubf, "-signature", sigf],
            input=f"{h}.{c}".encode(), capture_output=True)
        ok = b"Verified OK" in v.stdout
        claims = json.loads(base64.urlsafe_b64decode(c + "=" * (-len(c) % 4)))
        assert claims["scope"] == SCOPE and claims["aud"] == TOKEN_URL
        log(f"selftest: JWT structure OK, signature verify: "
            f"{'OK' if ok else 'FAILED'}")
        return 0 if ok else 1
    finally:
        for f in (keyf, pubf, sigf):
            os.unlink(f)


def resolve_creds_path(args) -> str:
    """Explicit --creds wins; else prefer gcloud ADC, then legacy SA keyfile."""
    if args.creds:
        return args.creds if os.path.exists(args.creds) else ""
    if os.path.exists(DEFAULT_ADC_FILE):
        return DEFAULT_ADC_FILE
    if os.path.exists(args.sa_file):
        return args.sa_file
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--creds", default=os.environ.get("GSC_CREDS"),
        help="Credentials JSON path (gcloud ADC user creds or SA key). "
             "Default: ADC, then the service-account keyfile.")
    ap.add_argument("--sa-file", default=os.environ.get(
        "GSC_SA_FILE", DEFAULT_SA_FILE), help=argparse.SUPPRESS)  # legacy alias
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    creds_path = resolve_creds_path(args)
    if not creds_path:
        log("ERROR: no credentials found.")
        log(f"  ADC (preferred):      {DEFAULT_ADC_FILE}")
        log(f"  service-account key:  {args.sa_file}")
        log("See scripts/GSC-API-SETUP.md for one-time setup.")
        return 1
    with open(creds_path) as f:
        creds = json.load(f)
    log(f"using credentials: {creds_path} "
        f"(type={creds.get('type', 'service_account')})")

    global QUOTA_PROJECT
    QUOTA_PROJECT = (creds.get("quota_project_id")
                     or os.environ.get("GOOGLE_CLOUD_QUOTA_PROJECT"))
    if creds.get("type") == "authorized_user" and not QUOTA_PROJECT:
        log("WARNING: no quota project set for ADC. If the pull fails with "
            "HTTP 403 (API not enabled / quota), run: gcloud auth "
            "application-default set-quota-project <PROJECT_ID>")

    today = dt.date.today()
    monday = today - dt.timedelta(days=today.weekday())
    end = today - dt.timedelta(days=2)  # GSC data lags ~48h
    wk_start = end - dt.timedelta(days=6)
    mo_start = end - dt.timedelta(days=27)
    log(f"monday={monday}  7d={wk_start}..{end}  28d={mo_start}..{end}")

    token = get_access_token(creds)
    log("auth OK")

    gsc_dir = os.path.join(SITE_DIR, "gsc-data")
    pull_range(token, wk_start, end,
               os.path.join(gsc_dir, "weekly", str(monday)), "7 days")
    pull_range(token, mo_start, end,
               os.path.join(gsc_dir, "28day", str(monday)), "28 days")

    pages_28d = query_api(token, {
        "startDate": mo_start.isoformat(), "endDate": end.isoformat(),
        "rowLimit": ROW_LIMIT, "dimensions": ["page"]})
    pull_page_detail(token, mo_start, end, pages_28d,
                     os.path.join(gsc_dir, "page-detail", str(monday)))

    log("done — all CSVs written")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"FATAL: {e}")
        sys.exit(1)
