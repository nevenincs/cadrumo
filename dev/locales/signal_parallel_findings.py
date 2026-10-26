"""Typed localization-data findings for TOML and gettext inventories."""

from __future__ import annotations

from pathlib import Path


def data_finding(kind: str, path: Path, field: str, detail: str) -> dict[str, object]:
    """Describe a blocking malformed or incomplete localization-data declaration."""
    next_action = (
        "add the missing accented target-language translation"
        if kind in {"parallel_translation_missing", "docs_translation_missing"}
        else "repair the localization data source"
    )
    return {
        "classification": "blocking",
        "kind": kind,
        "location": str(path),
        "field": field,
        "detail": detail,
        "next_action": next_action,
    }
