"""Story detector: collected data -> postable stories (state/queue.json).

Rules (config.json):
- Contract story : recipient matches a listed US public company, award >= min value,
                   small-cap only, and (if mcap known) award/mcap >= ratio threshold.
- Insider story  : >=N distinct insiders bought within lookback window with total >= X,
                   OR a single CEO/CFO buy >= single_buy_min. Small-cap only.

Dedupe: state/posted.json (story ids). Cluster ids include insider count, so a
3-insider cluster growing to 5 can legitimately re-fire as a bigger story.
"""
import datetime as dt
import re

from .market import market_cap, ticker_cik_map
from .util import DATA, STATE, config, http, load_json, log, save_json

SUFFIX = re.compile(
    r"\b(INC|CORP|CORPORATION|CO|COMPANY|LLC|L L C|LP|LTD|PLC|HOLDINGS?|GROUP|"
    r"INCORPORATED|INTERNATIONAL|ENTERPRISES?|INDUSTRIES)\b\.?|[.,&'\"()-]"
)


def norm(name: str) -> str:
    return re.sub(r"\s+", " ", SUFFIX.sub(" ", (name or "").upper())).strip()


def recent(dirname: str, days: int) -> list:
    rows = []
    for i in range(days + 1):
        d = (dt.date.today() - dt.timedelta(days=i)).isoformat()
        rows += load_json(DATA / dirname / f"{d}.json", [])
    return rows


def match_ticker(recipient: str, tmap: dict, overrides: dict, blocklist: set):
    """Recipient name -> ticker. Manual overrides first, then guarded auto-match."""
    n = norm(recipient)
    if not n:
        return None
    # blocklist: exact ya prefix match (e.g. "LEIDOS" blocks "LEIDOS BIOMEDICAL RESEARCH")
    for b in blocklist:
        if b and (n == b or n.startswith(b + " ")):
            return None
    for name, tk in overrides.items():
        if not tk:
            continue
        nn = norm(name)
        if nn and (n == nn or n.startswith(nn + " ") or nn.startswith(n + " ")):
            return tk.upper()
    if len(n) >= 6:  # guard against short/generic names false-matching
        for tk, info in tmap.items():
            nm = norm(info["name"])
            if len(nm) >= 6 and (nm == n or n.startswith(nm + " ") or nm.startswith(n + " ")):
                return tk
    return None


def run():
    cfg = config()
    s = http()
    posted = set(load_json(STATE / "posted.json", []))
    max_mcap = cfg.get("max_mcap_for_smallcap", 2_000_000_000)
    stories = []

    # ---------- contract stories ----------
    tick_file = load_json(DATA / "tickers.json", {})
    overrides = tick_file.get("overrides", {})
    blocklist = {norm(b) for b in tick_file.get("blocklist", [])}
    tmap = ticker_cik_map(s)

    for c in recent("contracts", cfg.get("contracts_lookback_days", 5)):
        sid = f"contract:{c['id']}"
        if sid in posted:
            continue
        amount = float(c.get("amount") or 0)
        if amount < cfg.get("contract_min_value", 5_000_000):
            continue
        if amount > cfg.get("contract_max_value", 2_000_000_000):
            continue  # mega-prime / ceiling awards — small-cap catalyst nahi
        tk = match_ticker(c.get("recipient", ""), tmap, overrides, blocklist)
        if not tk:
            continue
        mcap = market_cap(s, tk)
        if mcap is None:
            continue  # mcap verify nahi hui -> post NAHI (false-positive safety)
        if mcap > max_mcap:
            continue
        ratio = amount / mcap
        if ratio < cfg.get("contract_min_mcap_ratio_alert", 0.10):
            continue
        if ratio > cfg.get("contract_max_mcap_ratio_sanity", 5.0):
            continue  # award >> mcap = ceiling/IDV data artifact
        stories.append(
            {
                "id": sid,
                "type": "contract",
                "ticker": tk,
                "amount": amount,
                "agency": c.get("sub_agency") or c.get("agency") or "U.S. Government",
                "desc": c.get("desc", ""),
                "date": c.get("date"),
                "mcap": mcap,
                "ratio": ratio,
                "score": amount * (ratio if ratio else 0.05),
            }
        )

    # ---------- insider cluster stories ----------
    buys = [b for b in recent("form4", cfg.get("lookback_days_cluster", 7)) if b.get("symbol")]
    by_sym = {}
    for b in buys:
        by_sym.setdefault(b["symbol"], []).append(b)

    for sym, rows in by_sym.items():
        owners = {}
        for b in rows:
            o = owners.setdefault(
                b["owner"], {"title": b["title"], "value": 0.0, "date": b["date"]}
            )
            o["value"] += b["value"]
            o["date"] = max(o["date"], b["date"])
        total = sum(o["value"] for o in owners.values())
        n = len(owners)

        exec_big_buy = any(
            o["value"] >= cfg.get("single_buy_min", 250_000)
            and any(k in o["title"].upper() for k in ("CEO", "CFO", "CHIEF"))
            for o in owners.values()
        )
        cluster_ok = n >= cfg.get("cluster_min_insiders", 3) and total >= cfg.get(
            "cluster_min_total", 500_000
        )
        if not (cluster_ok or exec_big_buy):
            continue

        sid = f"cluster:{sym}:{n}"
        if sid in posted:
            continue
        mcap = market_cap(s, sym)
        if mcap and mcap > max_mcap:
            continue
        rows_out = sorted(
            ({"who": k, **v} for k, v in owners.items()), key=lambda r: -r["value"]
        )[:6]
        stories.append(
            {
                "id": sid,
                "type": "insider",
                "ticker": sym,
                "insiders": n,
                "total": total,
                "rows": rows_out,
                "mcap": mcap,
                "score": total * (1.5 if cluster_ok else 1.0),
            }
        )

    stories.sort(key=lambda x: -x["score"])
    stories = stories[: cfg.get("max_posts_per_run", 3)]
    save_json(STATE / "queue.json", stories)
    log(f"detect: queued {len(stories)} stories")
    for st in stories:
        log("  ->", st["id"], st["ticker"])


if __name__ == "__main__":
    run()
