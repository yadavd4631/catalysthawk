# 🦅 CatalystHawk

**Small-cap catalysts, straight from official filings.**
US government contract awards (USAspending) + insider cluster buys (SEC Form 4) →
branded alert cards → auto-posted to X + Telegram. Sab kuch GitHub Actions pe chalta hai — koi server nahi.

---

## System kaise kaam karta hai

```
har 30 min (US market hours, cron)
        │
        ▼
┌─ collect_form4.py ──────┐   SEC EDGAR se naye Form 4 (insider buys, code P)
├─ collect_contracts.py ──┤   USAspending se naye contract awards (>= $5M)
│        │                │   sab data/ me JSON commit hota hai = historical moat
│        ▼                │
├─ detect.py ─────────────┤   rules: award/mcap ratio, insider clusters, small-cap filter
│        ▼                │
├─ charts.py ─────────────┤   dark template card (amber = contract, green = insider)
│        ▼                │
└─ publish.py ────────────┘   X (no-URL caption = $0.015/post) + Telegram + Discord
```

## Repo structure

```
catalysthawk/
├── .github/workflows/
│   ├── pipeline.yml        # main cron pipeline (har 30 min, US hours)
│   └── backfill.yml        # manual: contracts history backfill (90 din default)
├── src/
│   ├── run_pipeline.py     # entrypoint (--demo flag bhi hai)
│   ├── collect_form4.py    # SEC EDGAR Form 4 collector
│   ├── collect_contracts.py# USAspending collector
│   ├── detect.py           # story rules + name->ticker matching
│   ├── charts.py           # alert card renderer (template design)
│   ├── publish.py          # X / Telegram / Discord posting + captions
│   ├── market.py           # Stooq prices + EDGAR shares outstanding -> mcap
│   └── util.py             # http session, state, config helpers
├── config.json             # saare thresholds (yahi tune karna)
├── data/tickers.json       # recipient-name -> ticker overrides + blocklist
├── data/                   # collected JSON (commit hota hai — yahi asset hai)
├── state/                  # dedupe state (posted.json, seen ids)
└── out/                    # generated cards (archive)
```

---

## Setup (ek baar, ~30 min)

### 1. Repo banao
- GitHub pe **public** repo banao (public = Actions minutes unlimited free).
  Code chhupana ho to private bhi chalega (2000 min/month me ye pipeline fit hai, lekin tight).
- Ye saari files push karo.

### 2. X (Twitter) developer setup
1. Brand account banao (e.g. `@CatalystHawk`) — **web se** Premium lo (₹427/mo; app se 30% mehenga).
2. [developer.x.com](https://developer.x.com) pe **usi account se** login → project/app banao → **pay-per-use credits** add karo ($10-15 kaafi hai mahine ke liye).
3. App permissions: **Read and Write** karo, phir **API Key/Secret** aur **Access Token/Secret** generate karo (4 values).

### 3. Telegram setup
1. [@BotFather](https://t.me/BotFather) → `/newbot` → token copy karo.
2. Public channel banao (e.g. `@CatalystHawkAlerts`) → bot ko **admin** banao (post permission).

### 4. GitHub Secrets & Variables
Repo → Settings → Secrets and variables → Actions:

**Secrets (naam exactly ye):**
| Secret | Value |
|---|---|
| `SEC_CONTACT_EMAIL` | aapka email (SEC ke fair-access rules ke liye User-Agent me jata hai) |
| `X_API_KEY` / `X_API_SECRET` | X app consumer keys |
| `X_ACCESS_TOKEN` / `X_ACCESS_SECRET` | X access token pair |
| `TELEGRAM_BOT_TOKEN` | BotFather ka token |
| `DISCORD_WEBHOOK_URL` | (optional) Discord channel webhook |

**Variables:**
| Variable | Value |
|---|---|
| `DRY_RUN` | `true` (pehle hafte test mode — kuch post NahI hoga) |
| `TELEGRAM_PUBLIC_CHANNEL` | `@CatalystHawkAlerts` (aapka channel handle) |

### 5. Pehla test
- Actions tab → **pipeline** → *Run workflow* (manual).
- Logs me dekho: collectors data la rahe hain, detect stories bana raha hai, publish `dry_run=True` me captions print kar raha hai.
- `out/` folder me generated cards dikhengi, `data/` me JSON.
- **backfill-contracts** workflow bhi ek baar chalao (90 din) — day 1 se history milegi.

### 6. Go live 🚀
- 2-3 din DRY_RUN me output quality dekho (`out/` ke cards + logs ke captions).
- Thresholds adjust karo `config.json` me (niche dekho).
- Ready ho to Variables me `DRY_RUN` = `false` → agli run se live posting.

---

## Tuning (config.json)

| Key | Default | Matlab |
|---|---|---|
| `contract_min_value` | $5M | isse chhote awards ignore |
| `contract_min_mcap_ratio_alert` | 0.10 | award ≥ 10% of market cap tabhi post |
| `contract_ratio_siren` | 0.50 | ≥ 50% pe caption me 🚨 |
| `max_mcap_for_smallcap` | $2B | isse badi companies skip (small-cap focus) |
| `cluster_min_insiders` | 3 | itne alag insiders khareedein to cluster |
| `cluster_min_total` | $500K | cluster ka minimum total |
| `single_buy_min` | $250K | akela CEO/CFO buy bhi post ho sakta hai |
| `max_posts_per_run` | 3 | flood + X cost control |

**data/tickers.json** — USAspending recipient names ko tickers se match karne ke liye:
- `overrides`: pakke matches (grow karte raho — ye aapka moat hai)
- `blocklist`: large-caps jo kabhi match nahi hone chahiye
- Auto-match SEC ki official company list se hota hai (guarded), lekin overrides best hain.

## Costs & limits
- **GitHub Actions:** public repo = free unlimited (standard runners)
- **X API:** ~$0.015/post (image+text, **no URL** — code URLs strip karta hai kyunki URL-post $0.20 ka hai)
- **Telegram/Discord:** free
- Est. total: **$2-5/month**

## Important notes
- **Not financial advice** — har card/caption me disclaimer hai; isse hatana mat.
- SEC fair access: 10 req/s limit — code politeness delays ke saath hai; cron ko 15 min se tight mat karo.
- USAspending kuch awards 1-3 din late dikhata hai (agencies ki reporting) — lookback window isko cover karta hai.
- Congress trading (45-day lag), defense.gov announcements, FDA calendar — future collectors ke natural slots hain.

## Roadmap (jab followers aa jayein)
1. **Month 3-4:** private Telegram (real-time, full alerts) — Dodo Payments/Gumroad subscription → invite link
2. **Month 4-6:** GitHub Pages dashboard (committed JSON se static site)
3. **Month 6+:** API tier ($49/mo) — API.market listing ya khud ka FastAPI
