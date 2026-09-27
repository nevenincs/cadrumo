"""Tests for the committed Modelo 360 (IVA devolución 8ª Directiva) foundation."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot

from ..conformance.registry_schema_support import committed_modelo as _committed_modelo
from .authored_edition_support import legal_reference
from .profile_schema_support import committed_registry_validator, committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_SUPPORT = committed_supported_filing_years()
# The day Orden EHA/789/2010 makes the Modelo 360 form applicable, as the catalogued
# approving article is in force from.
_APPROVING_ORDEN_APPLIES_FROM = legal_reference("orden-eha-789-2010:art-1").effective_from


def _load_modelo_360() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("360")


def test_modelo_360_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_360()
    assert modelo.id == "360"
    assert modelo.revisions, "360 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "360 must declare casillas"
    committed_registry_validator(catalogues).validate_modelo(modelo)


def test_modelo_360_metadata_matches_its_approving_orden() -> None:
    modelo, catalogues = _load_modelo_360()
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "ad_hoc"
    assert "orden-eha-789-2010:art-1" in modelo.legal_refs
    assert "orden-eha-789-2010:art-4" in modelo.legal_refs
    assert "aeat-dr-360-2010" in modelo.source_refs
    assert catalogues.sources["aeat-modelo-360-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-360-2010-form"].evidence_tier == "layout_authority"


def test_modelo_360_revision_starts_when_its_approving_orden_applies() -> None:
    modelo, _ = _load_modelo_360()
    revision = modelo.revisions[f"{_APPROVING_ORDEN_APPLIES_FROM.year}-y-siguientes"]
    assert revision.valid_from == _APPROVING_ORDEN_APPLIES_FROM
    assert revision.period_selector.year_from == _APPROVING_ORDEN_APPLIES_FROM.year
    assert revision.orden_aplicabilidad == ("orden-eha-789-2010:art-1",)


@pytest.mark.parametrize("ejercicio", _SUPPORT.years)
def test_modelo_360_september_30_deadline_matches_its_approving_orden_art_4(ejercicio: int) -> None:
    """Art 4: plazo concludes on 30 September of the year following the ejercicio."""
    modelo, _ = _load_modelo_360()
    revision = modelo.revisions[f"{_APPROVING_ORDEN_APPLIES_FROM.year}-y-siguientes"]
    windows = {w.id: w for w in revision.deadline_windows}

    window = windows[f"modelo-360-{ejercicio}-ad-hoc"]
    assert window.opens_on == date(ejercicio + 1, 1, 1)
    assert window.closes_on == date(ejercicio + 1, 9, 30)


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
    assert "modelo-360-dr" in construct.workbook_parity_refs
    assert construct.filing_schedules == ("modelo-360-ad-hoc",)
