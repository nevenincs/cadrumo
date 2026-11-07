"""Quarterly deadlines of the retention-return models (111, 115, 123): (due date, domiciled-payment date)."""

from __future__ import annotations

import json
from pathlib import Path

QUARTERLY_RETENCION_DEADLINES: dict[int, tuple[tuple[str, str | None], ...]] = {
    int(exercise): tuple((close, cutoff) for close, cutoff in rows)
    for exercise, rows in json.loads(
        Path(__file__).with_name("quarterly_retencion_deadlines.json").read_text(encoding="utf-8")
    ).items()
}
"""Each published exercise's four (close, domiciled-payment) pairs, read from the census data beside this module."""
