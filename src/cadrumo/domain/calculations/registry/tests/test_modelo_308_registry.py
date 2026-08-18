"""Tests for the committed Modelo 308 (IVA solicitud de devolución) registry foundation."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path
from .. import ModeloDefinition, RegistryCatalogues, RegistryValidator
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_modelo_308() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("308")


def test_modelo_308_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_308()
    assert modelo.id == "308"
    assert modelo.revisions, "308 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "308 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_308_metadata_matches_orden_eha_3786_2008_art_2() -> None:
    modelo, catalogues = _load_modelo_308()
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "ad_hoc"
    assert modelo.jurisdiction == "ES-AEAT"
    assert "orden-eha-3786-2008:art-2" in modelo.legal_refs
    assert "orden-eha-3786-2008:art-11" in modelo.legal_refs
    assert "aeat-dr-308-2019" in modelo.source_refs
    assert catalogues.sources["aeat-modelo-308-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-308-2008-form"].evidence_tier == "layout_authority"


def test_modelo_308_revision_starts_at_2009() -> None:
    modelo, _ = _load_modelo_308()
    revision = modelo.revisions["2022"]
    assert revision.valid_from == date(2009, 1, 1)
    assert revision.period_selector.year_from == 2009
    assert revision.period_selector.periods == ("AD-HOC",)
    assert revision.orden_aplicabilidad == ("orden-eha-3786-2008:art-2",)


def test_modelo_308_snapshot_builds_for_recent_filing_years() -> None:
    for filing_year in (2020, 2024, 2025, 2026):
        snapshot = _committed_snapshot("308", filing_year, "AD-HOC")
        assert snapshot.revision.id == "2022"


def test_modelo_308_snapshot_carries_legal_authority() -> None:
    snapshot = _committed_snapshot("308", 2025, "AD-HOC")
    assert "orden-eha-3786-2008:art-2" in snapshot.legal
    assert "orden-eha-3786-2008:art-11" in snapshot.legal
    assert snapshot.revision.orden_aplicabilidad == ("orden-eha-3786-2008:art-2",)
    assert snapshot.legal["orden-eha-3786-2008:art-11"].article == "11"
    assert "aeat-dr-308-2019" in snapshot.sources
    assert "aeat-modelo-308-procedure" in snapshot.sources
    assert "boe-modelo-308-2008-form" in snapshot.sources


def test_modelo_308_filing_schedule_is_ad_hoc() -> None:
    modelo, _ = _load_modelo_308()
    revision = modelo.revisions["2022"]
    schedule = next(s for s in revision.filing_schedules if s.id == "modelo-308-ad-hoc")
    assert schedule.period_kind == "ad_hoc"
    assert schedule.periods == ("AD-HOC",)
    assert "orden-eha-3786-2008:art-11" in schedule.legal_refs


def test_modelo_308_live_cross_references_forbid_writes() -> None:
    modelo, _ = _load_modelo_308()
    revision = modelo.revisions["2022"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}

    static_ref = cross_refs["modelo-308-static-documentation"]
    assert static_ref.surface == "static_official_documentation"
    assert static_ref.requires_authentication is False

    filed_ref = cross_refs["modelo-308-filed-declarations-read"]
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert set(filed_ref.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
    assert {"presentation", "signing", "amendment", "payment"}.issubset(set(filed_ref.forbidden_actions))


def test_modelo_308_construct_links_filing_workbook_parity() -> None:
    modelo, _ = _load_modelo_308()
    revision = modelo.revisions["2022"]
    construct = next(c for c in revision.constructs if c.id == "modelo-308-iva-solicitud-devolucion")
    assert "modelo-308-filing" in construct.application_links
    assert "modelo-308-deadline" in construct.application_links
    assert construct.filing_schedules == ("modelo-308-ad-hoc",)
    assert "modelo-308-dr-2019" in construct.workbook_parity_refs
