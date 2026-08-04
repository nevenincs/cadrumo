"""Real-behavior tests for the migration resolved localization matrix."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.core.resources import bundled_path
from dev.registry.migration import (
    ResolvedLocalizationEntry,
    ResolvedLocalizationMatrix,
    build_source_inventory,
    extract_resolved_localization_matrix,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def _entry(
    matrix: ResolvedLocalizationMatrix,
    *,
    modelo_id: str,
    revision_id: str,
    casilla_id: str,
    locale: str,
    field: str,
) -> ResolvedLocalizationEntry:
    """Return one matrix coordinate for focused assertions."""
    entries = matrix.entries
    return next(
        item
        for item in entries
        if (
            item.modelo_id,
            item.revision_id,
            item.casilla_id,
            item.locale,
            item.field,
        )
        == (modelo_id, revision_id, casilla_id, locale, field)
    )


def test_bundled_matrix_extracts_every_real_resolved_coordinate() -> None:
    """The current loader supplies the complete measured resolution population."""
    root = bundled_path("registry", "aeat")
    inventory = build_source_inventory(root)
    before = {
        path.relative_to(root).as_posix(): (path.stat().st_mtime_ns, path.stat().st_size)
        for path in root.rglob("*.toml")
        if path.is_file()
    }

    matrix = extract_resolved_localization_matrix(root, inventory)

    after = {
        path.relative_to(root).as_posix(): (path.stat().st_mtime_ns, path.stat().st_size)
        for path in root.rglob("*.toml")
        if path.is_file()
    }
    assert after == before
    assert matrix.corpus_fingerprint == inventory.corpus_fingerprint
    assert matrix.locales == ("es", "en", "ca", "hu")
    assert matrix.fields == ("label", "help")
    assert matrix.modelo_count == 73
    assert matrix.revision_count == 90
    assert matrix.occurrence_count == 15_774
    assert matrix.entry_count == 126_192
    assert matrix.localized_count == 42_108
    assert matrix.official_spanish_fallback_count == 37_326
    assert matrix.absent_count == 46_758
    assert matrix.entry_count == (matrix.localized_count + matrix.official_spanish_fallback_count + matrix.absent_count)
    assert tuple(
        (item.modelo_id, item.revision_id, item.casilla_id, item.locale, item.field) for item in matrix.entries
    ) == tuple(
        sorted((item.modelo_id, item.revision_id, item.casilla_id, item.locale, item.field) for item in matrix.entries),
    )

    m100_2020_label = _entry(
        matrix,
        modelo_id="100",
        revision_id="2020",
        casilla_id="0001",
        locale="en",
        field="label",
    )
    assert m100_2020_label.value == "Contribuyente que obtiene los rendimientos"
    assert m100_2020_label.resolution == "official_spanish"

    m100_2020_help = _entry(
        matrix,
        modelo_id="100",
        revision_id="2020",
        casilla_id="0001",
        locale="en",
        field="help",
    )
    assert m100_2020_help.value is None
    assert m100_2020_help.resolution == "absent"

    m100_2024_label = _entry(
        matrix,
        modelo_id="100",
        revision_id="2024",
        casilla_id="0001",
        locale="en",
        field="label",
    )
    assert m100_2024_label.value == "Taxpayer obtaining yield"
    assert m100_2024_label.resolution == "localized"


def test_resolved_entry_rejects_inconsistent_absent_state() -> None:
    """The matrix cannot encode a value while claiming that resolution was absent."""
    with pytest.raises(ValidationError, match="absent resolution must not carry a value"):
        ResolvedLocalizationEntry(
            modelo_id="100",
            revision_id="2020",
            casilla_id="0001",
            locale="en",
            field="help",
            value="unexpected",
            resolution="absent",
        )
