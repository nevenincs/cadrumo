"""Controlled child that proves the supervisor cleans up only its timed-out child."""

from __future__ import annotations

import json
import time

from ._installed_tui_fixture_support import parse_receipt_path


def main() -> int:
    receipt = parse_receipt_path()
    receipt.write_text(
        json.dumps({"status": "running", "stage": "fixture_sleep"}) + "\n",
        encoding="utf-8",
    )
    time.sleep(30.0)
    return 0


if __name__ == "__main__":  # pragma: no cover - child process fixture
    raise SystemExit(main())
