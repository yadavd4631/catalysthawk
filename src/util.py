"""Shared helpers: HTTP session (SEC-compliant UA), JSON state, paths, config."""
import json
import os
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter, Retry

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE = ROOT / "state"
OUT = ROOT / "out"


def http() -> requests.Session:
    """Session with retries + a proper User-Agent (SEC requires contact info)."""
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    contact = os.environ.get("SEC_CONTACT_EMAIL", "contact@example.com")
    s.headers.update(
        {
            "User-Agent": f"CatalystHawk research bot ({contact})",
            "Accept-Encoding": "gzip, deflate",
        }
    )
    return s


def load_json(path, default):
    p = Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return default
    return default


def save_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, default=str))


def config() -> dict:
    return load_json(ROOT / "config.json", {})


def dry_run() -> bool:
    """Safety default: anything except explicit 'false' means DRY RUN (no posting)."""
    return os.environ.get("DRY_RUN", "true").strip().lower() != "false"


def log(*args):
    print("[hawk]", *args, flush=True)
