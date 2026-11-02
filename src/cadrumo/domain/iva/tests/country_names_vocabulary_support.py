"""The bundled country-name vocabulary rows, read as the registry file declares them."""

from __future__ import annotations

from pathlib import Path

from ....core.resources.bundled_data import bundled_path
from ....core.toml import parse_toml


def country_vocabulary() -> list[dict[str, object]]:
    payload = parse_toml(Path(bundled_path("registry", "aeat", "iva", "country_names.toml")).read_text("utf-8"))
    raw_country = payload.get("country")
    assert isinstance(raw_country, list)
    rows: list[dict[str, object]] = []
    for raw_row in raw_country:
        assert isinstance(raw_row, dict)
        row: dict[str, object] = {}
        for key, value in raw_row.items():
            assert isinstance(key, str)
            row[key] = value
        rows.append(row)
    return rows
