"""Registry data tests for the census modelo foundation."""

from __future__ import annotations

import pytest

from aeat.core.paths import PROJECT_ROOT
from aeat.core.resources import bundled_path

from . import build_snapshot, discover_modelo_sources, load_registry_tree
from ._coverage import build_model_law_coverage_ledger
from ._errors import RegistrySnapshotError
from ._schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from ._sources import verify_source_file
from ._temporal import select_revision

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _modelos_by_id() -> tuple[dict[str, ModeloDefinition], RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return {modelo.id: modelo for modelo in modelos}, catalogues


def _snapshot(period: str = "alta") -> RegistrySnapshot:
    modelos, catalogues = _modelos_by_id()
    modelo = modelos["036"]
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period=period,
    )


def test_committed_modelo_036_registry_data_loads_as_active_census_foundation() -> None:
    snapshot = _snapshot()

    assert snapshot.modelo.id == "036"
    assert snapshot.modelo.cadence == "ad_hoc"
    assert snapshot.revision.period_selector.periods == ("alta", "modificacion", "baja")
    assert snapshot.filing_schedules["modelo-036-event-triggered"].period_kind == "ad_hoc"
    assert snapshot.filing_schedules["modelo-036-event-triggered"].periods == ("alta", "modificacion", "baja")


def test_committed_modelo_036_binds_census_status_from_profile() -> None:
    snapshot = _snapshot("modificacion")
    binding = snapshot.revision.bindings[0]
    casilla = next(item for item in snapshot.revision.casillas if item.id == "decl.event-kind")

    assert binding.id == "modelo-036-profile-census-status"
    assert binding.source == "profile"
    assert binding.selector == {"profile_key": "census.status"}
    assert binding.typed_enum == "census_event_kind"
    assert casilla.input_kind == "bound"
    assert casilla.binding == binding.id


def test_committed_modelo_036_has_registry_authority_coverage() -> None:
    snapshot = _snapshot("baja")
    ledger = build_model_law_coverage_ledger(snapshot)
    gates = {gate.tier: gate for gate in ledger.gates}

    assert gates["legal_authority"].status == "satisfied"
    assert "orden-hac-1526-2024:art-1" in gates["legal_authority"].legal_refs
    assert gates["official_source_guidance"].status == "satisfied"
    assert "aeat-modelo-036-procedure" in gates["official_source_guidance"].source_refs
    assert gates["layout_authority"].status == "satisfied"
    assert "aeat-dr-036-2025" in gates["layout_authority"].source_refs


def test_committed_modelo_036_record_design_source_matches_manifest() -> None:
    _, catalogues = _modelos_by_id()
    source = catalogues.sources["aeat-dr-036-2025"]

    assert source.corpus_path == (
        "corpus/aeat_official/disenos_registro/modelo_036/files/"
        "01-036-diseno-de-registro-del-modelo-m036-03-02-2025-y-siguientes-124-kb-xlsx.xlsx"
    )
    assert source.sha256 == "791479fbf9e905faf1e43fa0bfbff974d5edaf85d198495892fa8446a1da2ebd"
    assert source.bytes == 126664
    verify_source_file(PROJECT_ROOT, source)


def test_modelo_037_is_historical_catalogue_metadata_not_active_registry_model() -> None:
    modelos, catalogues = _modelos_by_id()

    assert "037" not in modelos
    assert "boe-modelo-037-historical-suppression" in catalogues.sources
    assert "orden-hac-1526-2024:art-1" in catalogues.legal
    verify_source_file(PROJECT_ROOT, catalogues.sources["boe-modelo-037-historical-suppression"])


def test_modelo_036_rejects_unknown_census_event_period() -> None:
    modelos, _ = _modelos_by_id()

    with pytest.raises(RegistrySnapshotError, match="no revision"):
        select_revision(modelos["036"], filing_year=2025, period="037")


def test_no_committed_modelo_037_toml_can_revive_active_support() -> None:
    sources = discover_modelo_sources(bundled_path("registry", "aeat", "modelos"))
    assert "037" not in {source.modelo_id for source in sources}
