"""Modelo 200 authored revision source-tier checks."""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from .authored_edition_support import newest_authored_editions, revision_covering

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_200_revision_fragments_never_cite_another_years_annual_manual() -> None:
    """Every M200 fragment keeps annual guidance inside its own ejercicio."""

    earlier, later = newest_authored_editions("200", 2)
    for edition, other_edition in ((earlier, later), (later, earlier)):
        revision_id = revision_covering("200", edition).id
        allowed_manual = f"aeat-modelo-200-manual-{edition}"
        forbidden_manual = f"aeat-modelo-200-manual-{other_edition}"
        revision_root = bundled_path("registry", "aeat", "modelos", "200", "revisions", revision_id)
        fragments = tuple(revision_root.rglob("*.toml"))
        assert fragments, f"expected authored Modelo 200 revision fragments for {revision_id}"
        text = "\n".join(fragment.read_text(encoding="utf-8") for fragment in fragments)
        assert allowed_manual in text, f"{revision_id} must retain its own annual manual evidence"
        assert forbidden_manual not in text, f"{revision_id} must not cite {forbidden_manual}"
