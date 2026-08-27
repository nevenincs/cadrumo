"""Tests for the committed Modelo 360 (IVA devolución 8ª Directiva) foundation."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.snapshot import build_snapshot

from .....core.resources import bundled_path
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_modelo_360() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("360")


def test_modelo_360_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_360()
    assert modelo.id == "360"
    assert modelo.revisions, "360 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "360 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_360_metadata_matches_orden_eha_789_2010() -> None:
    modelo, catalogues = _load_modelo_360()
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "ad_hoc"
    assert "orden-eha-789-2010:art-1" in modelo.legal_refs
    assert "orden-eha-789-2010:art-4" in modelo.legal_refs
    assert "aeat-dr-360-2010" in modelo.source_refs
    assert catalogues.sources["aeat-modelo-360-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-360-2010-form"].evidence_tier == "layout_authority"


def test_modelo_360_revision_starts_at_2010() -> None:
    modelo, _ = _load_modelo_360()
    revision = modelo.revisions["2010-y-siguientes"]
    assert revision.valid_from == date(2010, 4, 1)
    assert revision.period_selector.year_from == 2010
    assert revision.orden_aplicabilidad == ("orden-eha-789-2010:art-1",)


def test_modelo_360_september_30_deadline_matches_orden_eha_789_2010_art_4() -> None:
    """Art 4: plazo concludes on 30 September of the year following the ejercicio."""
    modelo, _ = _load_modelo_360()
    revision = modelo.revisions["2010-y-siguientes"]
    windows = {w.id: w for w in revision.deadline_windows}

    win_2024 = windows["modelo-360-2024-ad-hoc"]
    assert win_2024.opens_on == date(2025, 1, 1)
    assert win_2024.closes_on == date(2025, 9, 30)

    win_2025 = windows["modelo-360-2025-ad-hoc"]
    assert win_2025.opens_on == date(2026, 1, 1)
    assert win_2025.closes_on == date(2026, 9, 30)


def test_modelo_360_snapshot_builds_for_ad_hoc_period() -> None:
    modelo, catalogues = _load_modelo_360()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="AD-HOC")
    assert snapshot.revision.id == "2010-y-siguientes"
    assert snapshot.revision.orden_aplicabilidad == ("orden-eha-789-2010:art-1",)
    assert "orden-eha-789-2010:art-1" in snapshot.legal


def test_modelo_360_live_cross_references_forbid_writes() -> None:
    modelo, _ = _load_modelo_360()
    revision = modelo.revisions["2010-y-siguientes"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}
    filed_ref = cross_refs["modelo-360-filed-declarations-read"]
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True


def test_modelo_360_construct_links_workbook_parity() -> None:
    modelo, _ = _load_modelo_360()
    revision = modelo.revisions["2010-y-siguientes"]
    construct = next(c for c in revision.constructs if c.id == "modelo-360-iva-devolucion-ue")
    assert "modelo-360-dr-2010" in construct.workbook_parity_refs
    assert construct.filing_schedules == ("modelo-360-ad-hoc",)
