"""Modelo 200 authored revision source-tier checks."""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_200_revision_fragments_never_cite_another_years_annual_manual() -> None:
    """Every M200 fragment keeps annual guidance inside its own ejercicio."""

    for revision_id, allowed_manual, forbidden_manual in (
        ("2024", "aeat-modelo-200-manual-2024", "aeat-modelo-200-manual-2025"),
        ("2025-y-siguientes", "aeat-modelo-200-manual-2025", "aeat-modelo-200-manual-2024"),
    ):
        revision_root = bundled_path("registry", "aeat", "modelos", "200", "revisions", revision_id)
        fragments = tuple(revision_root.rglob("*.toml"))
        assert fragments, f"expected authored Modelo 200 revision fragments for {revision_id}"
        text = "\n".join(fragment.read_text(encoding="utf-8") for fragment in fragments)
        assert allowed_manual in text, f"{revision_id} must retain its own annual manual evidence"
        assert forbidden_manual not in text, f"{revision_id} must not cite {forbidden_manual}"
