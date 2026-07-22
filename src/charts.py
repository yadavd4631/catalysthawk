"""CatalystHawk alert cards — dark template.

Design system:
  canvas #0e1116 | amber #f0a83c = contracts | green #3fb950 = insider buys
  one card = one story = one hero number | watermark bottom-right, source bottom-left
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from .util import OUT, log

BG = "#0e1116"
AMBER = "#f0a83c"
GREEN = "#3fb950"
RED = "#f85149"
GRAY = "#8b949e"
WHITE = "#f0f6fc"
DIM = "#30363d"
MONO = "DejaVu Sans Mono"
SANS = "DejaVu Sans"


def money(v):
    if v is None:
        return "—"
    for cut, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= cut:
            out = f"{v / cut:.1f}".rstrip("0").rstrip(".")
            return f"${out}{suf}"
    return f"${v:,.0f}"


def _base(accent, tag, ticker):
    fig = plt.figure(figsize=(8, 8), dpi=200)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.text(
        6, 92, f" {tag} ",
        fontsize=11, family=MONO, color=accent, va="center",
        bbox=dict(boxstyle="round,pad=0.5", fc=BG, ec=accent, lw=1.3),
    )
    ax.text(
        94, 92, f"${ticker}",
        fontsize=18, family=MONO, color=WHITE, ha="right", va="center", weight="bold",
    )
    return fig, ax


def _footer(ax, source):
    ax.plot([6, 94], [9.5, 9.5], color=DIM, lw=0.8)
    ax.text(6, 6, f"Source: {source}", fontsize=9, family=MONO, color=GRAY)
    ax.text(94, 6.6, "CATALYSTHAWK", fontsize=11, family=SANS, weight="bold",
            color=AMBER, ha="right")
    ax.text(94, 3.4, "not financial advice", fontsize=6.5, family=MONO,
            color=GRAY, ha="right")


def _sparkline(fig, closes, rect, buy_marks=None):
    if not closes or len(closes) < 2:
        return
    sax = fig.add_axes(rect)
    sax.set_facecolor(BG)
    sax.plot(range(len(closes)), closes, color=GRAY, lw=1.6)
    if buy_marks:
        for i in buy_marks:
            if 0 <= i < len(closes):
                sax.plot(i, closes[i], "o", color=GREEN, ms=6)
    for sp in sax.spines.values():
        sp.set_visible(False)
    sax.set_xticks([])
    sax.set_yticks([])
    chg = (closes[-1] / closes[0] - 1) * 100
    sax.set_title(
        f"{'▲' if chg >= 0 else '▼'} {chg:+.1f}%  ({len(closes)}d)",
        fontsize=9, family=MONO, color=GREEN if chg >= 0 else RED,
        loc="left", pad=3,
    )


def contract_card(story, closes, outdir=None) -> Path:
    fig, ax = _base(AMBER, "CONTRACT ALERT", story["ticker"])

    ax.text(5.5, 76, money(story["amount"]), fontsize=54, family=SANS,
            weight="bold", color=AMBER, va="center")
    agency = (story.get("agency") or "U.S. Government")[:40]
    ax.text(6, 66.5, f"{agency} contract awarded", fontsize=14.5,
            family=SANS, color=WHITE)
    if story.get("desc"):
        ax.text(6, 61.5, story["desc"][:66], fontsize=9, family=MONO, color=GRAY)

    if story.get("mcap"):
        a, m = story["amount"], story["mcap"]
        scale = 56.0 / max(a, m)
        ax.text(6, 52.5, f"Contract   {money(a)}", fontsize=10.5, family=MONO, color=AMBER)
        ax.add_patch(FancyBboxPatch((6, 47.2), max(a * scale, 2.5), 3.4,
                                    boxstyle="round,pad=0.02", fc=AMBER, ec="none"))
        ax.text(6, 41.5, f"Market cap {money(m)}", fontsize=10.5, family=MONO, color=GRAY)
        ax.add_patch(FancyBboxPatch((6, 36.2), max(m * scale, 2.5), 3.4,
                                    boxstyle="round,pad=0.02", fc=DIM, ec="none"))
        if story.get("ratio"):
            ax.text(94, 45, f"= {story['ratio'] * 100:.0f}%", fontsize=26, family=SANS,
                    weight="bold", color=WHITE, ha="right")
            ax.text(94, 39.5, "of market cap", fontsize=10, family=SANS,
                    color=GRAY, ha="right")

    _sparkline(fig, closes, [0.07, 0.135, 0.34, 0.12])
    _footer(ax, "USAspending.gov")

    outdir = Path(outdir or OUT)
    outdir.mkdir(parents=True, exist_ok=True)
    p = outdir / f"{story['id'].replace(':', '_').replace('/', '_')}.png"
    fig.savefig(p, facecolor=BG)
    plt.close(fig)
    log("chart:", p.name)
    return p


def insider_card(story, closes, outdir=None) -> Path:
    fig, ax = _base(GREEN, "INSIDER CLUSTER BUY", story["ticker"])

    ax.text(5.5, 76, money(story["total"]), fontsize=54, family=SANS,
            weight="bold", color=GREEN, va="center")
    n = story.get("insiders", 1)
    label = f"bought by {n} insiders in the last 7 days" if n > 1 else "insider purchase this week"
    ax.text(6, 66.5, label, fontsize=14.5, family=SANS, color=WHITE)
    if story.get("mcap"):
        ax.text(6, 61.5, f"market cap {money(story['mcap'])}", fontsize=9.5,
                family=MONO, color=GRAY)

    y = 53.5
    for r in story.get("rows", [])[:5]:
        who = f"{r['title'][:16]:<17}" if r.get("title") else ""
        date = (r.get("date") or "")[5:]
        ax.text(6, y, "▲", fontsize=11, family=MONO, color=GREEN)
        ax.text(9.5, y, f"{who} +{money(r['value'])}", fontsize=11.5,
                family=MONO, color=WHITE)
        ax.text(70, y, date, fontsize=10, family=MONO, color=GRAY)
        y -= 5.4

    _sparkline(fig, closes, [0.07, 0.135, 0.34, 0.11],
               buy_marks=[len(closes) - 2, len(closes) - 4, len(closes) - 6] if closes else None)
    _footer(ax, "SEC Form 4 (EDGAR)")

    outdir = Path(outdir or OUT)
    outdir.mkdir(parents=True, exist_ok=True)
    p = outdir / f"{story['id'].replace(':', '_').replace('/', '_')}.png"
    fig.savefig(p, facecolor=BG)
    plt.close(fig)
    log("chart:", p.name)
    return p


def render(story, closes, outdir=None) -> Path:
    if story["type"] == "contract":
        return contract_card(story, closes, outdir)
    return insider_card(story, closes, outdir)
