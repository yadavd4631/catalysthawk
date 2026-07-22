"""Market helpers (all keyless/free):
- price history  -> Stooq daily CSV
- shares outstanding -> SEC EDGAR XBRL company facts
- market cap = last close x shares outstanding
- ticker <-> CIK <-> company name map -> SEC company_tickers.json
"""
import datetime as dt

from .util import DATA, http, load_json, log, save_json

_TICKER_MAP = None


def ticker_cik_map(session) -> dict:
    """{'KTOS': {'cik': 1069258, 'name': 'KRATOS DEFENSE & SECURITY...'}, ...}"""
    global _TICKER_MAP
    if _TICKER_MAP is not None:
        return _TICKER_MAP
    cache = DATA / "cache" / "company_tickers.json"
    data = load_json(cache, None)
    if not data:
        r = session.get("https://www.sec.gov/files/company_tickers.json", timeout=30)
        r.raise_for_status()
        data = r.json()
        save_json(cache, data)
    _TICKER_MAP = {
        v["ticker"].upper(): {"cik": v["cik_str"], "name": (v["title"] or "").upper()}
        for v in data.values()
    }
    return _TICKER_MAP


def price_history(session, ticker: str, days: int = 45) -> list:
    """Daily closes (oldest -> newest) from Stooq. Empty list on failure."""
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    url = (
        f"https://stooq.com/q/d/l/?s={ticker.lower()}.us"
        f"&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d"
    )
    try:
        r = session.get(url, timeout=20)
        closes = []
        for line in r.text.strip().splitlines()[1:]:
            parts = line.split(",")
            if len(parts) >= 5:
                try:
                    closes.append(float(parts[4]))
                except ValueError:
                    pass
        return closes
    except Exception as e:
        log("price_history fail", ticker, e)
        return []


def shares_outstanding(session, ticker: str):
    m = ticker_cik_map(session).get(ticker.upper())
    if not m:
        return None
    cik10 = str(m["cik"]).zfill(10)
    url = (
        "https://data.sec.gov/api/xbrl/companyconcept/"
        f"CIK{cik10}/dei/EntityCommonStockSharesOutstanding.json"
    )
    try:
        r = session.get(url, timeout=30)
        if r.status_code != 200:
            return None
        vals = (r.json().get("units") or {}).get("shares") or []
        if not vals:
            return None
        vals.sort(key=lambda x: x.get("end", ""))
        return float(vals[-1]["val"])
    except Exception:
        return None


def market_cap(session, ticker: str):
    closes = price_history(session, ticker, days=10)
    sh = shares_outstanding(session, ticker)
    if closes and sh:
        return closes[-1] * sh
    return None
