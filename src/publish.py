"""Publisher: queued stories -> chart render -> X + Telegram (+ optional Discord).

Safety:
- DRY_RUN (repo variable) defaults to true -> renders + logs, posts NOTHING.
- X captions never contain URLs (X bills $0.20/post with URL vs $0.015 without).
- Each channel is isolated: one failing never blocks the others.
"""
import datetime as dt
import os

from .charts import money, render
from .market import price_history
from .util import OUT, STATE, dry_run, http, load_json, log, save_json


# ---------- captions ----------

def strip_urls(text: str) -> str:
    return (
        text.replace("http://", "").replace("https://", "").replace("www.", "")
    )


def x_caption(story) -> str:
    t = story["ticker"]
    if story["type"] == "contract":
        siren = "🚨 " if (story.get("ratio") or 0) >= 0.5 else ""
        lines = [
            f"{siren}${t} just won a {money(story['amount'])} "
            f"{story.get('agency', 'U.S. government')} contract"
        ]
        if story.get("ratio"):
            lines.append(f"That's {story['ratio'] * 100:.0f}% of its entire market cap.")
        lines.append("Source: USAspending")
    else:
        n = story.get("insiders", 1)
        siren = "🚨 " if story.get("total", 0) >= 2_000_000 else ""
        head = (
            f"{siren}{n} insiders at ${t} just bought {money(story['total'])} of their own stock"
            if n > 1
            else f"{siren}An insider at ${t} just bought {money(story['total'])} of stock"
        )
        rows = [
            f"{r['title'].split(',')[0][:14]} +{money(r['value'])}"
            for r in story.get("rows", [])[:4]
        ]
        lines = [head, "\n".join(rows), "Source: SEC Form 4"]
    return strip_urls("\n\n".join(lines))[:275]


def tg_caption(story) -> str:
    base = x_caption(story)
    return base + "\n\n🦅 CatalystHawk — not financial advice"


# ---------- channels ----------

def post_x(text: str, image_path) -> bool:
    import tweepy

    ck, cs = os.environ["X_API_KEY"], os.environ["X_API_SECRET"]
    at, ats = os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"]
    auth = tweepy.OAuth1UserHandler(ck, cs, at, ats)
    media = tweepy.API(auth).media_upload(str(image_path))
    client = tweepy.Client(
        consumer_key=ck, consumer_secret=cs,
        access_token=at, access_token_secret=ats,
    )
    client.create_tweet(text=text, media_ids=[media.media_id])
    return True


def post_telegram(text: str, image_path) -> bool:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat = os.environ["TELEGRAM_PUBLIC_CHANNEL"]
    with open(image_path, "rb") as f:
        r = http().post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data={"chat_id": chat, "caption": text[:1000]},
            files={"photo": f},
            timeout=60,
        )
    r.raise_for_status()
    return True


def post_discord(text: str, image_path) -> bool:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        return False
    with open(image_path, "rb") as f:
        r = http().post(url, data={"content": text[:1900]},
                        files={"file": f}, timeout=60)
    r.raise_for_status()
    return True


# ---------- main ----------

def run():
    s = http()
    queue = load_json(STATE / "queue.json", [])
    if not queue:
        log("publish: queue empty")
        return
    posted = load_json(STATE / "posted.json", [])
    outdir = OUT / dt.date.today().isoformat()
    dry = dry_run()

    for story in queue:
        closes = price_history(s, story["ticker"], days=45)
        img = render(story, closes, outdir)
        cap = x_caption(story)
        log(f"publish: {story['id']}  dry_run={dry}")
        log("caption:\n" + cap)

        if not dry:
            ok = False
            try:
                post_x(cap, img)
                ok = True
                log("  -> X posted")
            except Exception as e:
                log("  -> X failed:", e)
            try:
                post_telegram(tg_caption(story), img)
                ok = True
                log("  -> Telegram posted")
            except Exception as e:
                log("  -> Telegram failed:", e)
            try:
                if post_discord(tg_caption(story), img):
                    log("  -> Discord posted")
            except Exception as e:
                log("  -> Discord failed:", e)
            if not ok:
                continue  # nothing went out -> let it retry next run

        posted.append(story["id"])

    save_json(STATE / "posted.json", posted[-5000:])
    save_json(STATE / "queue.json", [])
    log("publish: done")


# ---------- demo (no network posting, sample stories) ----------

def demo():
    import random

    random.seed(7)
    closes = [10.0]
    for _ in range(44):
        closes.append(max(1, closes[-1] * (1 + random.uniform(-0.03, 0.035))))

    contract_story = {
        "id": "demo:contract",
        "type": "contract",
        "ticker": "KTOS",
        "amount": 48_200_000,
        "agency": "U.S. Air Force",
        "desc": "Tactical drone systems — production & support",
        "mcap": 61_000_000,
        "ratio": 48_200_000 / 61_000_000,
    }
    insider_story = {
        "id": "demo:insider",
        "type": "insider",
        "ticker": "ABCD",
        "insiders": 4,
        "total": 2_100_000,
        "mcap": 95_000_000,
        "rows": [
            {"who": "John Smith", "title": "CEO", "value": 850_000, "date": "2026-07-18"},
            {"who": "Jane Doe", "title": "CFO", "value": 600_000, "date": "2026-07-18"},
            {"who": "A. Patel", "title": "Director", "value": 400_000, "date": "2026-07-21"},
            {"who": "M. Chen", "title": "Director", "value": 250_000, "date": "2026-07-22"},
        ],
    }
    outdir = OUT / "demo"
    for st in (contract_story, insider_story):
        img = render(st, closes, outdir)
        log("demo caption:\n" + x_caption(st))
        log("demo image:", img)


if __name__ == "__main__":
    run()
