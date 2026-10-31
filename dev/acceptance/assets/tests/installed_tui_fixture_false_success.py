"""Controlled child that must not turn an early zero exit into journey proof."""

from __future__ import annotations

import json

from ._installed_tui_fixture_support import parse_receipt_path


def main() -> int:
    receipt = parse_receipt_path()
    receipt.write_text(
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
