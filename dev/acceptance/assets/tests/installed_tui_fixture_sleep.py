"""Controlled child that proves the supervisor cleans up only its timed-out child."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--workspace-root")
    parser.add_argument("--profile-label")
    parser.add_argument("--journey")
    args = parser.parse_args()
    args.receipt.write_text(
        json.dumps({"status": "running", "stage": "fixture_sleep"}) + "\n",
        encoding="utf-8",
    )
    time.sleep(30.0)
    return 0


if __name__ == "__main__":  # pragma: no cover - child process fixture
    raise SystemExit(main())
