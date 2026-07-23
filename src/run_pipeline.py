"""Pipeline entrypoint: collect -> detect -> render+publish.

Usage:
  python -m src.run_pipeline           # full run (posting gated by DRY_RUN)
  python -m src.run_pipeline --demo    # render sample cards only, no network posts
"""
import os
import sys

from .util import log


def main():
    if "--demo" in sys.argv:
        from . import publish

        publish.demo()
        return

    if os.environ.get("DRY_RUN", "").strip().lower() == "test":
        from . import publish

        publish.test_post()
        return

    from . import collect_contracts, collect_form4, detect, publish

    for name, step in (
        ("collect_form4", collect_form4.run),
        ("collect_contracts", collect_contracts.run),
    ):
        try:
            step()
        except Exception as e:
            log(f"{name} FAILED (continuing):", e)

    try:
        detect.run()
    except Exception as e:
        log("detect FAILED:", e)
        return

    try:
        publish.run()
    except Exception as e:
        log("publish FAILED:", e)


if __name__ == "__main__":
    main()
