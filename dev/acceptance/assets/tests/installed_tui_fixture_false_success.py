"""Controlled child that must not turn an early zero exit into journey proof."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--workspace-root")
    parser.add_argument("--profile-label")
    parser.add_argument("--journey")
    parser.add_argument("--profile-bootstrap")
    args = parser.parse_args()
    args.receipt.write_text(
        json.dumps(
            {
                "status": "proven",
                "stage": "completed",
                "completed_stages": ["installed_origin", "registration", "launcher_exit"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - child process fixture
    raise SystemExit(main())
