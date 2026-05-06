"""Tests for the committed Modelo 303 (IVA autoliquidacion) registry foundation."""

from __future__ import annotations

from datetime import date

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import RegistryCatalogues, RegistryValidator, build_snapshot, load_registry_tree
from ._schema import ModeloDefinition

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _load_modelo_303() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(m for m in modelos if m.id == "303")
    return modelo, catalogues


def test_modelo_303_registry_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_303()
    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)


def test_modelo_303_metadata_matches_orden_eha_3786_2008() -> None:
    modelo, _ = _load_modelo_303()

    assert modelo.title == "IVA. Autoliquidacion (trimestral)"
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "quarterly"
    assert modelo.jurisdiction == "ES-AEAT"
    assert "orden-eha-3786-2008:art-1" in modelo.legal_refs
    assert "orden-eha-3786-2008:art-7" in modelo.legal_refs
    assert "aeat-dr-303-2025" in modelo.source_refs
    assert "aeat-modelo-303-procedure" in modelo.source_refs


def test_modelo_303_revision_period_selector_starts_at_2009() -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2009-y-siguientes"]

    assert revision.valid_from == date(2009, 1, 1)
    assert revision.period_selector.year_from == 2009
    assert revision.period_selector.periods == ("1T", "2T", "3T", "4T")


def test_modelo_303_snapshot_builds_for_each_quarter() -> None:
    modelo, catalogues = _load_modelo_303()

    for period in ("1T", "2T", "3T", "4T"):
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=PROJECT_ROOT,
            filing_year=2025,
            period=period,
        )
        assert snapshot.revision.id == "2009-y-siguientes"


def test_modelo_303_snapshot_carries_legal_authority_and_record_design() -> None:
    modelo, catalogues = _load_modelo_303()
    snapshot = build_snapshot(
        modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="1T"
    )

    assert "orden-eha-3786-2008:art-1" in snapshot.legal
    assert "orden-eha-3786-2008:art-7" in snapshot.legal
    assert snapshot.legal["orden-eha-3786-2008:art-7"].article == "7"
    assert "aeat-dr-303-2025" in snapshot.sources
    assert "aeat-modelo-303-procedure" in snapshot.sources
    assert "boe-modelo-303-2008-form" in snapshot.sources


def test_modelo_303_quarterly_deadlines_match_orden_eha_3786_2008_art_7() -> None:
    """1T-3T close on day 20; 4T closes on day 30 of January following."""
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2009-y-siguientes"]
    windows = {w.id: w for w in revision.deadline_windows}

    expected = {
        "modelo-303-2025-1t": (date(2025, 4, 1), date(2025, 4, 21)),
        "modelo-303-2025-2t": (date(2025, 7, 1), date(2025, 7, 21)),
        "modelo-303-2025-3t": (date(2025, 10, 1), date(2025, 10, 20)),
        "modelo-303-2025-4t": (date(2026, 1, 1), date(2026, 1, 30)),
        "modelo-303-2026-1t": (date(2026, 4, 1), date(2026, 4, 20)),
        "modelo-303-2026-2t": (date(2026, 7, 1), date(2026, 7, 20)),
        "modelo-303-2026-3t": (date(2026, 10, 1), date(2026, 10, 20)),
        "modelo-303-2026-4t": (date(2027, 1, 1), date(2027, 1, 30)),
    }

    for window_id, (opens, closes) in expected.items():
        assert windows[window_id].opens_on == opens
        assert windows[window_id].closes_on == closes


def test_modelo_303_live_cross_references_forbid_writes() -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2009-y-siguientes"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}

    static_ref = cross_refs["modelo-303-static-documentation"]
    assert static_ref.surface == "static_official_documentation"
    assert static_ref.requires_authentication is False

    filed_ref = cross_refs["modelo-303-filed-declarations-read"]
    assert filed_ref.surface == "authenticated_read_surface"
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert set(filed_ref.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
    assert set(filed_ref.allowed_hosts) == {
        "www1.agenciatributaria.gob.es",
        "www6.agenciatributaria.gob.es",
    }
    forbidden = set(filed_ref.forbidden_actions)
    assert {
        "presentation",
        "signing",
        "amendment",
        "payment",
        "cancellation",
        "declaration-submission",
        "document-submission",
        "server-side-save",
    }.issubset(forbidden)


def test_modelo_303_construct_links_filing_extractor_verification() -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2009-y-siguientes"]
    construct = next(c for c in revision.constructs if c.id == "modelo-303-iva-autoliquidacion")

    assert "modelo-303-filing" in construct.application_links
    assert "modelo-303-extractor" in construct.application_links
    assert "modelo-303-verification" in construct.application_links
    assert "modelo-303-deadline" in construct.application_links
    assert construct.filing_schedules == ("modelo-303-trimestral",)
    assert "modelo-303-dr-2025" in construct.workbook_parity_refs


def test_modelo_303_workbook_parity_ref_anchors_record_design_layout() -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2009-y-siguientes"]
    parity = next(p for p in revision.workbook_parity_refs if p.id == "modelo-303-dr-2025")

    assert parity.workbook_source == "aeat-dr-303-2025"
    assert parity.formula_coverage == "record_design_layout"
    assert parity.fixture_id == "modelo-303-2025-record-design-layout"
