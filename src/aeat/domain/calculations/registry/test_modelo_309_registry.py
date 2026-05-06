"""Tests for the committed Modelo 309 (IVA no periódica) registry foundation."""

from __future__ import annotations

from datetime import date

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import RegistryCatalogues, RegistryValidator, build_snapshot, load_registry_tree
from ._schema import ModeloDefinition

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _load_modelo_309() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(m for m in modelos if m.id == "309")
    return modelo, catalogues


def test_modelo_309_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_309()
    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)


def test_modelo_309_metadata_matches_orden_hac_3625_2003() -> None:
    modelo, _ = _load_modelo_309()
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "ad_hoc"
    assert "orden-hac-3625-2003:apartado-1" in modelo.legal_refs
    assert "orden-hac-3625-2003:apartado-3" in modelo.legal_refs
    assert "aeat-dr-309-2023" in modelo.source_refs


def test_modelo_309_revision_uses_ad_hoc_period_selector() -> None:
    modelo, _ = _load_modelo_309()
    revision = modelo.revisions["2004-y-siguientes"]
    assert revision.period_selector.year_from == 2004
    assert revision.period_selector.periods == ("AD-HOC",)


def test_modelo_309_snapshot_builds_for_ad_hoc_period() -> None:
    modelo, catalogues = _load_modelo_309()
    snapshot = build_snapshot(
        modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="AD-HOC"
    )
    assert snapshot.revision.id == "2004-y-siguientes"
    assert "orden-hac-3625-2003:apartado-1" in snapshot.legal
    assert "orden-hac-3625-2003:apartado-3" in snapshot.legal


def test_modelo_309_filing_schedule_is_ad_hoc() -> None:
    modelo, _ = _load_modelo_309()
    revision = modelo.revisions["2004-y-siguientes"]
    schedule = next(s for s in revision.filing_schedules if s.id == "modelo-309-ad-hoc")
    assert schedule.period_kind == "ad_hoc"
    assert schedule.periods == ("AD-HOC",)


def test_modelo_309_live_cross_references_forbid_writes() -> None:
    modelo, _ = _load_modelo_309()
    revision = modelo.revisions["2004-y-siguientes"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}
    filed_ref = cross_refs["modelo-309-filed-declarations-read"]
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert {"presentation", "signing", "amendment", "payment"}.issubset(
        set(filed_ref.forbidden_actions)
    )


def test_modelo_309_construct_links_workbook_parity() -> None:
    modelo, _ = _load_modelo_309()
    revision = modelo.revisions["2004-y-siguientes"]
    construct = next(c for c in revision.constructs if c.id == "modelo-309-iva-no-periodica")
    assert "modelo-309-dr-2023" in construct.workbook_parity_refs
    assert construct.filing_schedules == ("modelo-309-ad-hoc",)
