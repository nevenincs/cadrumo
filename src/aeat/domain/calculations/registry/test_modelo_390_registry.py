"""Tests for the committed Modelo 390 (IVA Resumen Anual) registry foundation."""

from __future__ import annotations

from datetime import date

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import RegistryCatalogues, RegistryValidator, build_snapshot, load_registry_tree
from ._schema import ModeloDefinition

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _load_modelo_390() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(m for m in modelos if m.id == "390")
    return modelo, catalogues


def test_modelo_390_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_390()
    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)


def test_modelo_390_metadata_matches_orden_eha_3111_2009() -> None:
    modelo, _ = _load_modelo_390()
    assert modelo.title == "IVA. Declaracion-resumen anual"
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "annual"
    assert modelo.jurisdiction == "ES-AEAT"
    assert "orden-eha-3111-2009:art-1" in modelo.legal_refs
    assert "orden-eha-3111-2009:art-8" in modelo.legal_refs
    assert "aeat-dr-390-2025" in modelo.source_refs


def test_modelo_390_revision_period_selector_starts_at_2010() -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    assert revision.valid_from == date(2010, 1, 1)
    assert revision.period_selector.year_from == 2010
    assert revision.period_selector.periods == ("0A",)


def test_modelo_390_snapshot_builds_for_each_published_filing_year() -> None:
    modelo, catalogues = _load_modelo_390()
    for filing_year in (2020, 2021, 2022, 2023, 2024, 2025, 2026):
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=PROJECT_ROOT,
            filing_year=filing_year,
            period="0A",
        )
        assert snapshot.revision.id == "2010-y-siguientes"


def test_modelo_390_snapshot_carries_legal_authority_and_record_design() -> None:
    modelo, catalogues = _load_modelo_390()
    snapshot = build_snapshot(
        modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="0A"
    )
    assert "orden-eha-3111-2009:art-1" in snapshot.legal
    assert "orden-eha-3111-2009:art-8" in snapshot.legal
    assert snapshot.legal["orden-eha-3111-2009:art-8"].article == "8"
    assert "aeat-dr-390-2025" in snapshot.sources
    assert "aeat-modelo-390-procedure" in snapshot.sources


def test_modelo_390_january_30_deadline_matches_orden_eha_3111_2009_art_8() -> None:
    """Art 8: presentación en los treinta primeros días naturales del mes de enero siguiente."""
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    windows = {w.id: w for w in revision.deadline_windows}

    expected = {
        "modelo-390-2020-0a": (date(2021, 1, 1), date(2021, 1, 30)),
        "modelo-390-2021-0a": (date(2022, 1, 1), date(2022, 1, 30)),
        "modelo-390-2022-0a": (date(2023, 1, 1), date(2023, 1, 30)),
        "modelo-390-2023-0a": (date(2024, 1, 1), date(2024, 1, 30)),
        "modelo-390-2024-0a": (date(2025, 1, 1), date(2025, 1, 30)),
        "modelo-390-2025-0a": (date(2026, 1, 1), date(2026, 1, 30)),
        "modelo-390-2026-0a": (date(2027, 1, 1), date(2027, 1, 30)),
    }

    for window_id, (opens, closes) in expected.items():
        assert windows[window_id].opens_on == opens
        assert windows[window_id].closes_on == closes


def test_modelo_390_live_cross_references_are_read_only() -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}

    static_ref = cross_refs["modelo-390-static-documentation"]
    assert static_ref.surface == "static_official_documentation"
    assert static_ref.requires_authentication is False

    filed_ref = cross_refs["modelo-390-filed-declarations-read"]
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert set(filed_ref.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
    forbidden = set(filed_ref.forbidden_actions)
    assert {"presentation", "signing", "amendment", "payment"}.issubset(forbidden)


def test_modelo_390_construct_links_filing_workbook_parity() -> None:
    modelo, _ = _load_modelo_390()
    revision = modelo.revisions["2010-y-siguientes"]
    construct = next(c for c in revision.constructs if c.id == "modelo-390-iva-resumen-anual")
    assert "modelo-390-filing" in construct.application_links
    assert "modelo-390-deadline" in construct.application_links
    assert construct.filing_schedules == ("modelo-390-anual",)
    assert "modelo-390-dr-2025" in construct.workbook_parity_refs
