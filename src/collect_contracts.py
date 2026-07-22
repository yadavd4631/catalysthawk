"""Collector 2: USAspending.gov -> recent US government contract awards.

Keyless official API. We pull awards >= contract_min_value from the last N days
(action_date), dedupe by award id, and append to data/contracts/YYYY-MM-DD.json.

Note: agencies report on their own schedules, so awards can appear with a lag
of a few days — the rolling lookback window + dedupe handles that.
BACKFILL_DAYS env var widens the window (used by backfill workflow).
"""
import datetime as dt
import os

from .util import DATA, STATE, config, http, load_json, log, save_json

API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"


def run():
    cfg = config()
    s = http()
    days = int(os.environ.get("BACKFILL_DAYS") or cfg.get("contracts_lookback_days", 5))
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    seen = set(load_json(STATE / "contracts_seen.json", []))
    got = []

    page = 1
    while page <= 10:
        body = {
            "filters": {
                "award_type_codes": ["A", "B", "C", "D"],
                "time_period": [
                    {
                        "start_date": start.isoformat(),
                        "end_date": end.isoformat(),
                        "date_type": "action_date",
                    }
                ],
                "award_amounts": [
                    {"lower_bound": cfg.get("contract_min_value", 5_000_000)}
                ],
            },
            "fields": [
                "Award ID",
                "Recipient Name",
                "Award Amount",
                "Awarding Agency",
                "Awarding Sub Agency",
                "Description",
                "Start Date",
            ],
            "sort": "Award Amount",
            "order": "desc",
            "limit": 100,
            "page": page,
        }
        try:
            r = s.post(API, json=body, timeout=45)
            r.raise_for_status()
            results = r.json().get("results", [])
        except Exception as e:
            log("usaspending fail:", e)
            break

        for a in results:
            aid = a.get("generated_internal_id") or a.get("Award ID")
            if not aid or aid in seen:
                continue
            seen.add(aid)
            got.append(
                {
                    "id": str(aid),
                    "recipient": (a.get("Recipient Name") or "").upper(),
                    "amount": a.get("Award Amount"),
                    "agency": a.get("Awarding Agency"),
                    "sub_agency": a.get("Awarding Sub Agency"),
                    "desc": (a.get("Description") or "").strip()[:140],
                    "date": a.get("Start Date"),
                }
            )
        if len(results) < 100:
            break
        page += 1

    today = dt.date.today().isoformat()
    path = DATA / "contracts" / f"{today}.json"
    day = load_json(path, [])
    day += got
    save_json(path, day)
    save_json(STATE / "contracts_seen.json", sorted(seen)[-25000:])
    log(f"contracts: +{len(got)} new awards >= min value, today total {len(day)}")


if __name__ == "__main__":
    run()
