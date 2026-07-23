"""Collector 1: SEC EDGAR latest Form 4 filings -> open-market insider BUYS.

Source: EDGAR 'current events' atom feed (keyless, near real-time).
Only transactions with code P (open-market purchase) + acquired 'A' are kept.
Output: data/form4/YYYY-MM-DD.json  (appended each run, deduped by accession no.)

SEC fair-access rules: proper User-Agent (util.http) + stay well under 10 req/s.
"""
import datetime as dt
import re
import time
import xml.etree.ElementTree as ET

from .util import DATA, STATE, http, load_json, log, save_json

FEED = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
    "&type=4&company=&dateb=&owner=include&count=100&start={start}&output=atom"
)
INDEX_RE = re.compile(
    r'href="https://www\.sec\.gov/Archives/edgar/data/(\d+)/(\d+)/([\d-]+)-index\.htm"'
)


def _text(root, path):
    el = root.find(path)
    return el.text.strip() if el is not None and el.text else ""


def parse_form4(xml_text: str) -> list:
    """One Form 4 XML -> list of purchase rows."""
    root = ET.fromstring(xml_text)
    sym = _text(root, ".//issuerTradingSymbol").upper()
    issuer = _text(root, ".//issuerName")
    owner = _text(root, ".//rptOwnerName").title()
    is_director = _text(root, ".//isDirector").strip() in ("1", "true")
    title = _text(root, ".//officerTitle") or ("Director" if is_director else "Owner")
    rows = []
    if not sym:
        return rows
    for t in root.findall(".//nonDerivativeTransaction"):
        code = _text(t, ".//transactionCode")
        acq = _text(t, ".//transactionAcquiredDisposedCode/value")
        if code != "P" or acq != "A":
            continue
        try:
            shares = float(_text(t, ".//transactionShares/value") or 0)
            price = float(_text(t, ".//transactionPricePerShare/value") or 0)
        except ValueError:
            continue
        if shares <= 0 or price <= 0:
            continue
        rows.append(
            {
                "symbol": sym,
                "issuer": issuer,
                "owner": owner,
                "title": title[:40],
                "date": _text(t, ".//transactionDate/value"),
                "value": round(shares * price, 2),
            }
        )
    return rows


def run():
    s = http()
    seen = set(load_json(STATE / "form4_seen.json", []))
    new_rows = []
    checked = 0

    for start in (0, 100, 200):
        try:
            r = s.get(FEED.format(start=start), timeout=30)
            links = INDEX_RE.findall(r.text)
        except Exception as e:
            log("form4 feed fail:", e)
            break
        if not links:
            break
        for cik, folder, acc in links:
            if acc in seen:
                continue
            seen.add(acc)
            checked += 1
            base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{folder}"
            try:
                idx = s.get(base + "/index.json", timeout=20).json()
                items = idx.get("directory", {}).get("item", [])
                xmls = [i["name"] for i in items if i["name"].lower().endswith(".xml")]
                if not xmls:
                    continue
                xml_text = s.get(base + "/" + xmls[0], timeout=20).text
                new_rows += parse_form4(xml_text)
            except Exception:
                continue
            time.sleep(0.15)  # politeness: ~6 req/s max including index fetches

    today = dt.date.today().isoformat()
    path = DATA / "form4" / f"{today}.json"
    day = load_json(path, [])
    day += new_rows
    save_json(path, day)
    save_json(STATE / "form4_seen.json", sorted(seen)[-8000:])
    log(f"form4: checked {checked} filings, +{len(new_rows)} buys, today total {len(day)}")


if __name__ == "__main__":
    run()
