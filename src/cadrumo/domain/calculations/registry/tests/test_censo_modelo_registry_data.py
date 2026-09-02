"""Registry data tests for the censo modelo foundation."""

from __future__ import annotations

import pytest

from .....core.resources.bundled_data import bundled_path
from .....tests import REPO_ROOT
from .....tests.registry_snapshot import build_snapshot
from ..binding_selector_utils import selector_as_dict
from ..corpus_catalogue import verify_source_file
from ..coverage import build_model_law_coverage_ledger
from ..errors import RegistrySnapshotError
from ..loader import load_modelo_directory
from ..loader_cache import discover_modelo_sources
from ..schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from ..schema_input_kind import InputKind
from ..temporal import select_revision
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelos_by_id() -> tuple[dict[str, ModeloDefinition], RegistryCatalogues]:
    modelos, catalogues = _committed_registry_tree()
    return {modelo.id: modelo for modelo in modelos}, catalogues


def _snapshot(period: str = "alta") -> RegistrySnapshot:
    modelos, catalogues = _modelos_by_id()
    modelo = modelos["036"]
    # Modelo 036 declares `authority_grade = applicability`: its censal
    # alta/modificacion/baja is filed on AEAT's sede and produces no fichero
    # here, so it is not intended to reach filing and its revision is not
    # reviewed to that rung. Ask for the rung the law-selected revision itself
    # declares rather than the FILING default, and a later promotion of 036
    # carries here without an edit.
    revision = select_revision(modelo, filing_year=2025, period=period)
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2025,
        period=period,
        grade=revision.effective_authority_grade,
    )


def test_committed_modelo_036_registry_data_loads_as_active_censo_foundation() -> None:
    snapshot = _snapshot()

    assert snapshot.modelo.id == "036"
    assert snapshot.modelo.cadence == "ad_hoc"
    assert snapshot.revision.period_selector.periods == ("alta", "modificacion", "baja")
    assert snapshot.filing_schedules["modelo-036-event-triggered"].period_kind == "ad_hoc"
    assert snapshot.filing_schedules["modelo-036-event-triggered"].periods == ("alta", "modificacion", "baja")


def test_committed_modelo_036_binds_censo_status_from_profile() -> None:
    snapshot = _snapshot("modificacion")
    binding = snapshot.revision.bindings[0]
    casilla = next(item for item in snapshot.revision.casillas if item.id == "decl.event-kind")

    assert binding.id == "modelo-036-profile-censo-status"
    assert binding.source == "profile"
    assert selector_as_dict(binding) == {"profile_key": "censo.status"}
    assert binding.typed_enum == "censo_event_kind"
    assert casilla.input_kind == InputKind.BOUND
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
    verify_source_file(REPO_ROOT, source)


def test_modelo_037_is_historical_catalogue_metadata_not_active_registry_model() -> None:
    modelos, catalogues = _modelos_by_id()

    assert "037" not in modelos
    assert "boe-modelo-037-historical-suppression" in catalogues.sources
    assert "orden-hac-1526-2024:art-1" in catalogues.legal
    source = catalogues.sources["boe-modelo-037-historical-suppression"]
    assert source.kind == "suppression_notice"
    assert source.evidence_tier == "official_source_guidance"
    verify_source_file(REPO_ROOT, source)


def test_modelo_036_rejects_unknown_censo_event_period() -> None:
    modelos, _ = _modelos_by_id()

    with pytest.raises(RegistrySnapshotError, match="no revision"):
        select_revision(modelos["036"], filing_year=2025, period="037")


def test_no_committed_modelo_037_toml_can_revive_active_support() -> None:
    sources = discover_modelo_sources(bundled_path("registry", "aeat", "modelos"))
    assert "037" not in {source.modelo_id for source in sources}


def _assert_periods_lowercase(label: str, periods: tuple[str, ...]) -> None:
    """Raise AssertionError if any period value contains an uppercase character.

    AEAT publishes event-kind values uppercase in Anexo 3 HTML tables (ALTA,
    MODIFICACION, BAJA). CENSO_MODELO_EVENT_KINDS canonicalises them lowercase.
    A registry author mirroring AEAT display text would silently re-introduce
    uppercase, which passes the _temporal.py case-insensitive mask but breaks
    _active_036_ownership_from_registry whose equality guard is case-sensitive.
    History: commit 33783e00c (drift introduced), 472de9c02 (reverted, 21 min later).
    """
    non_lowercase = [p for p in periods if p != p.lower()]
    assert not non_lowercase, (
        f"{label}: period values must be lowercase canonical "
        f"(CENSO_MODELO_EVENT_KINDS = {('alta', 'modificacion', 'baja')!r}); "
        f"found non-lowercase: {non_lowercase!r}. "
        "Registry authors: do not mirror AEAT Anexo 3 HTML display casing."
    )


def test_m036_revision_periods_are_lowercase_canonical() -> None:
    """Guard against re-introduction of uppercase ALTA/MODIFICACION/BAJA in M036 TOML.

    AEAT publishes period values uppercase in Anexo 3 HTML tables, but the domain
    layer CENSO_MODELO_EVENT_KINDS canonicalises them lowercase. A registry author
    mirroring AEAT display text would re-introduce uppercase (history: commit
    33783e00c, fixed 21 min later in 472de9c02). _active_036_ownership_from_registry
    has a case-sensitive equality guard that the _temporal.py case-insensitive mask
    does not protect, so this lint must fire at snapshot build.

    Loads M036 in isolation via load_modelo_directory so the lint is not affected
    by unrelated registry failures in other modelo directories.
    """
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "036"))

    for revision_id, revision in modelo.revisions.items():
        label_prefix = f"M036 revision {revision_id!r}"

        _assert_periods_lowercase(
            f"{label_prefix} period_selector.periods",
            revision.period_selector.periods,
        )

        for schedule in revision.filing_schedules:
            _assert_periods_lowercase(
                f"{label_prefix} filing_schedule {schedule.id!r}.periods",
                schedule.periods,
            )


def test_m036_period_case_lint_detects_uppercase_drift() -> None:
    """Prove the lint fires on uppercase ALTA/MODIFICACION/BAJA.

    This is the anti-evasion proof: if _assert_periods_lowercase passes
    silently for uppercase inputs, every test in this module is tautological.
    Mixed-case ("Alta") is also covered because the check uses p != p.lower().
    """
    import pytest as _pytest

    with _pytest.raises(AssertionError, match="non-lowercase"):
        _assert_periods_lowercase("proof", ("ALTA", "MODIFICACION", "BAJA"))

    with _pytest.raises(AssertionError, match="non-lowercase"):
        _assert_periods_lowercase("proof-mixed", ("Alta", "modificacion", "Baja"))
