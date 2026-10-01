#!/usr/bin/env python3
"""Refresh filings/data/filings.json from SEC EDGAR.

Runs daily in GitHub Actions. Uses only the Python standard library.
SEC asks every automated client to identify itself with a contact email:
set the SEC_CONTACT_EMAIL repository secret (Settings > Secrets and variables > Actions).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPANIES_FILE = ROOT / "scripts" / "companies.json"
OUT_FILE = ROOT / "filings" / "data" / "filings.json"

KEEP_DAYS = 365          # filings older than this drop off the dashboard
INSIDER_DAYS = 30        # window for counting Form 4 insider filings

# Forms shown on the dashboard (matched on prefix, so "424B" covers 424B2..424B5).
MATERIAL_PREFIXES = (
    "10-K", "10-Q", "8-K", "6-K", "20-F", "40-F",
    "S-1", "S-3", "F-1", "F-3", "424B",
    "DEF 14A", "DEFA14A", "SC 13D", "SC 13G", "SCHEDULE 13D", "SCHEDULE 13G",
)

DESCRIPTIONS = [
    ("10-K", "Annual report"),
    ("10-Q", "Quarterly report"),
    ("8-K", "Current report"),
    ("6-K", "Current report of foreign issuer"),
    ("20-F", "Annual report (foreign issuer)"),
    ("40-F", "Annual report (Canadian issuer)"),
    ("S-1", "IPO registration statement"),
    ("F-1", "IPO registration statement (foreign issuer)"),
    ("S-3", "Shelf registration"),
    ("F-3", "Shelf registration (foreign issuer)"),
    ("424B", "Prospectus (securities offering)"),
    ("DEF 14A", "Definitive proxy statement"),
    ("DEFA14A", "Additional proxy materials"),
    ("SC 13", "Beneficial ownership report"),
    ("SCHEDULE 13", "Beneficial ownership report"),
]


def user_agent() -> str:
    email = os.environ.get("SEC_CONTACT_EMAIL", "").strip()
    if not email:
        print("SEC_CONTACT_EMAIL is not set; SEC may refuse requests without a contact email.", file=sys.stderr)
        email = "webmaster@alldatasi.com"
    return f"AllDataSI filings dashboard {email}"


def get_json(url: str, ua: str, tries: int = 4):
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            raise
        except urllib.error.URLError:
            if attempt < tries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            raise
        finally:
            time.sleep(0.25)  # stay well under SEC's 10 requests/second limit


def describe(form: str) -> str:
    base = form.replace("/A", "")
    for prefix, label in DESCRIPTIONS:
        if base.startswith(prefix):
            return label + (" (amendment)" if form.endswith("/A") else "")
    return form


def is_material(form: str) -> bool:
    return form.replace("/A", "").startswith(MATERIAL_PREFIXES)


def load_ticker_map(ua: str) -> dict:
    data = get_json("https://www.sec.gov/files/company_tickers.json", ua)
    return {row["ticker"].upper(): str(row["cik_str"]).zfill(10) for row in data.values()}


def company_filings(cik: str, ticker: str, ua: str, today: date):
    sub = get_json(f"https://data.sec.gov/submissions/CIK{cik}.json", ua)
    recent = sub.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    keep_from = (today - timedelta(days=KEEP_DAYS)).isoformat()
    insider_from = (today - timedelta(days=INSIDER_DAYS)).isoformat()
    cik_int = str(int(cik))
    out, insider = [], 0
    for i, form in enumerate(forms):
        filed = recent["filingDate"][i]
        if form == "4" and filed >= insider_from:
            insider += 1
        if filed < keep_from or not is_material(form):
            continue
        acc = recent["accessionNumber"][i]
        doc = recent.get("primaryDocument", [""] * len(forms))[i]
        folder = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc.replace('-', '')}"
        out.append({
            "id": acc,
            "ticker": ticker,
            "form": form,
            "desc": describe(form),
            "date": filed,
            "url": f"{folder}/{doc}" if doc else f"{folder}/",
        })
    return out, insider


def main() -> int:
    ua = user_agent()
    today = datetime.now(timezone.utc).date()
    config = json.loads(COMPANIES_FILE.read_text())["companies"]

    previous = {}
    if OUT_FILE.exists():
        previous = json.loads(OUT_FILE.read_text())
    from_edgar = previous.get("source") == "edgar"
    prev_added = {f["id"]: f.get("addedOn", "") for f in previous.get("filings", [])} if from_edgar else {}
    prev_by_ticker = {}
    for f in previous.get("filings", []):
        prev_by_ticker.setdefault(f["ticker"], []).append(f)
    prev_companies = {c["ticker"]: c for c in previous.get("companies", [])}

    ticker_map = load_ticker_map(ua)
    filings, companies, failures = [], [], []

    for c in config:
        ticker = c["ticker"].upper()
        cik = c.get("cik") or ticker_map.get(ticker)
        entry = {k: c[k] for k in ("ticker", "name", "group", "note") if k in c}
        if not cik:
            failures.append(f"{ticker}: no CIK found")
            entry["insider30d"] = None
            companies.append(entry)
            continue
        try:
            rows, insider = company_filings(cik, ticker, ua, today)
        except Exception as e:  # keep yesterday's data for this company rather than dropping it
            failures.append(f"{ticker}: {e}")
            filings.extend(prev_by_ticker.get(ticker, []))
            entry["insider30d"] = prev_companies.get(ticker, {}).get("insider30d")
            companies.append(entry)
            continue
        entry["insider30d"] = insider
        companies.append(entry)
        filings.extend(rows)

    new_ids = []
    for f in filings:
        if not from_edgar:
            f["addedOn"] = ""            # first EDGAR run: don't flag the whole history as new
        elif f["id"] in prev_added:
            f["addedOn"] = prev_added[f["id"]]
        else:
            f["addedOn"] = today.isoformat()
            new_ids.append(f"{f['ticker']} {f['form']}")

    filings.sort(key=lambda f: (f["date"], f["ticker"]), reverse=True)
    result = {
        "source": "edgar",
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "newCount": len(new_ids),
        "newSummary": ", ".join(new_ids[:12]),
        "failures": failures,
        "companies": companies,
        "filings": filings,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(result, indent=1))
    print(f"{len(filings)} filings, {len(new_ids)} new. {('Failures: ' + '; '.join(failures)) if failures else ''}")
    # Fail the run only if nothing could be fetched, so a partial outage still publishes what worked.
    return 1 if len(failures) == len(config) else 0


if __name__ == "__main__":
    sys.exit(main())
