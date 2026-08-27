"""Real-behavior coverage for cross-period clean-state dependency proof."""

from __future__ import annotations

from datetime import date
from functools import cache
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....core import Period
from ....domain.calculations.registry.applicability_modelo202 import Modelo202Modality
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.modelos import (
    ModeloRecordCatalogue,
    ModeloRecordStatus,
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    CalculationObservationRepository,
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyOrigin,
    CrossPeriodExpectedMemberSet,
    NoPriorObligationProvenanceKind,
    cross_period_dependency_inventory,
    cross_period_dependency_requirements,
    partition_cross_period_requirements_by_activity_start,
)
from ._cross_period_clean_state_support import (
    BUCKET_ID as _BUCKET_ID,
)
from ._cross_period_clean_state_support import (
    CLOCK as _CLOCK,
)
from ._cross_period_clean_state_support import (
    GROUP_MEMBER_A as _GROUP_MEMBER_A,
)
from ._cross_period_clean_state_support import (
    GROUP_MEMBER_B as _GROUP_MEMBER_B,
)
from ._cross_period_clean_state_support import (
    GROUP_MEMBER_C as _GROUP_MEMBER_C,
)
from ._cross_period_clean_state_support import (
    M353_PERIOD as _M353_PERIOD,
)
from ._cross_period_clean_state_support import (
    M353_YEAR as _M353_YEAR,
)
from ._cross_period_clean_state_support import (
    M390_YEAR as _M390_YEAR,
)
from ._cross_period_clean_state_support import (
    evaluate_clean_state as _evaluate_clean_state,
)
from ._cross_period_clean_state_support import (
    m390_first_quarter_evidence as _m390_first_quarter_evidence,
)
from ._cross_period_clean_state_support import (
    member_fan_in_requirement as _member_fan_in_requirement,
)
from ._cross_period_clean_state_support import (
    persist_justificante_metadata as _persist_justificante_metadata,
)
from ._cross_period_clean_state_support import (
    save_member_322_observation as _save_member_322_observation,
)
from ._cross_period_clean_state_support import (
    seed_member_322_filing as _seed_member_322_filing,
)
from ._cross_period_clean_state_support import (
    seed_official_303_source_filings as _seed_official_303_source_filings,
)
from ._cross_period_clean_state_support import (
    snapshot_353 as _snapshot_353,
)
from ._cross_period_clean_state_support import (
    snapshot_390 as _snapshot_390,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_cross_period_clean_state_blocks_missing_required_prior_filings(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = _evaluate_clean_state(_snapshot_390())

    assert verdict.requires_clean_state is True
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.MISSING_OBSERVATION in verdict.blockers
    assert CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD in verdict.blockers


def test_m100_suffered_retencion_deps_scoped_out_self_filed_enforced(tmp_path: Path) -> None:
    """M100 suffered-retencion deps scope out; self-filed deps still block.

    The grounded payee/payer distinction (``taxpayer_files_source = false`` on the suffered
    classifications) lets a salaried taxpayer reach export, while pagos-fraccionados the taxpayer
    DOES file stay enforced. Classification-driven, not schedule-driven (the reverted Option 1).
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = _evaluate_clean_state(
            bundled_authority().snapshot("100", filing_year=2024, period="0A"),
        )

    # M115 (arrendamiento retenciones) was retired as a dormant M100
    # rental-retention source; the surviving suffered-retencion set is 111/123/193.
    suffered = {"111", "123", "193"}
    scoped_out = {
        item.requirement.source_modelo for item in verdict.dependencies if item.modelo_not_applicable_advisory
    }
    assert suffered <= scoped_out, f"suffered deps must be scoped out, got {scoped_out}"
    assert verdict.has_modelo_not_applicable_advisory is True
    assert all(item.clean for item in verdict.dependencies if item.modelo_not_applicable_advisory)
    assert scoped_out.isdisjoint({"130", "131"}), "self-filed pagos fraccionados must NOT be scoped out"


def test_m100_pagos_fraccionados_conditional_on_economic_activity(tmp_path: Path) -> None:
    """130/131 scope out for a declared employee and stay enforced otherwise."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        snap = bundled_authority().snapshot("100", filing_year=2024, period="0A")

        def evaluate_activity_state(
            taxpayer_files_economic_activity: bool | None,
        ) -> CrossPeriodCleanStateVerdict:
            return _evaluate_clean_state(
                snap,
                taxpayer_files_economic_activity=taxpayer_files_economic_activity,
            )

        employee = evaluate_activity_state(False)
        autonomo = evaluate_activity_state(True)
        undeclared = evaluate_activity_state(None)

    def scoped(verdict: CrossPeriodCleanStateVerdict) -> set[str]:
        return {item.requirement.source_modelo for item in verdict.dependencies if item.modelo_not_applicable_advisory}

    def blocking(verdict: CrossPeriodCleanStateVerdict) -> set[str]:
        return {item.requirement.source_modelo for item in verdict.dependencies if not item.clean}

    # Declared employee (no actividad económica): 130/131 scope out as not-applicable.
    assert {"130", "131"} <= scoped(employee)
    # Autónomo (declares actividad económica): 130/131 stay enforced (still block, never scoped).
    assert scoped(autonomo).isdisjoint({"130", "131"})
    assert {"130", "131"} & blocking(autonomo)
    # Undeclared income categories: fail-closed — 130/131 stay enforced.
    assert scoped(undeclared).isdisjoint({"130", "131"})


def test_m100_pagos_fraccionados_scopes_out_mutually_exclusive_m131(tmp_path: Path) -> None:
    """A direct-estimation autonomo owes M130, not M131, so only M130 stays enforced."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = _evaluate_clean_state(
            bundled_authority().snapshot("100", filing_year=2025, period="0A"),
            taxpayer_files_economic_activity=True,
            not_applicable_source_modelos=frozenset({"131"}),
        )

    scoped = {item.requirement.source_modelo for item in verdict.dependencies if item.modelo_not_applicable_advisory}
    blocking = {item.requirement.source_modelo for item in verdict.dependencies if not item.clean}

    assert "131" in scoped
    assert "130" not in scoped
    assert "130" in blocking


def test_m100_zero_prior_negative_base_carry_scopes_previous_filing_evidence(tmp_path: Path) -> None:
    """An explicit zero prior BIN does not require prior M100 evidence."""
    zero_binding = "renta-2025-base-liquidable-negativa-general-anterior"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        snapshot = bundled_authority().snapshot("100", filing_year=2025, period="0A")
        verdict = _evaluate_clean_state(
            snapshot,
            taxpayer_files_economic_activity=False,
            zero_value_previous_filing_binding_ids=frozenset({zero_binding}),
        )

    zero_carry = next(
        item
        for item in verdict.dependencies
        if item.requirement.origin is CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING
        and item.requirement.origin_ids == (zero_binding,)
    )
    zero_binding_definition = next(binding for binding in snapshot.revision.bindings if binding.id == zero_binding)
    assert zero_carry.clean
    assert zero_carry.zero_value_previous_filing_advisory is True
    assert set(zero_carry.requirement.legal_refs) == set(zero_binding_definition.legal_refs)
    assert set(zero_carry.requirement.source_refs) == set(zero_binding_definition.source_refs)
    assert all(
        item.clean
        for item in verdict.dependencies
        if item.requirement.source_modelo == "100" and item.requirement.filing_year == 2024
    )


def test_cross_period_requirements_include_relation_rollups(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        snapshot = bundled_authority().snapshot("180", filing_year=2026, period="0A")

    requirements = cross_period_dependency_requirements(snapshot)

    relation_requirement = next(
        requirement
        for requirement in requirements
        if requirement.origin is CrossPeriodDependencyOrigin.REGISTRY_RELATION
        and requirement.source_modelo == "115"
        and requirement.period == Period.from_year_and_code(2026, "1T")
    )
    source_relation = next(
        relation for relation in snapshot.revision.relations if relation.id == relation_requirement.origin_ids[0]
    )
    assert set(relation_requirement.legal_refs) == set(source_relation.legal_refs)
    assert set(relation_requirement.source_refs) == set(source_relation.source_refs)


def test_cross_period_requirements_preserve_previous_filing_presence_policy() -> None:
    snapshot = bundled_authority().snapshot("130", filing_year=2026, period="1T")
    binding = next(
        binding
        for binding in snapshot.revision.bindings
        if binding.id == "irpf.previous_year_economic_activity_net_income"
    )
    requirement = next(
        requirement
        for requirement in cross_period_dependency_requirements(snapshot)
        if requirement.origin_ids == (binding.id,)
    )

    assert requirement.required_source_casilla_ids == ()
    assert requirement.source_presence_groups == (requirement.source_casilla_ids,)


def test_cross_period_dependency_inventory_covers_declared_2026_target_modelos(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        inventory = cross_period_dependency_inventory(
            bundled_authority(),
            filing_year=2026,
        )

    assert inventory.target_modelos == (
        "130",
        "131",
        "180",
        "190",
        "193",
        "202",
        "296",
        "303",
        "353",
        "720",
    )
    assert all(item.dependencies for item in inventory.items)
    assert "036" not in inventory.target_modelos
    assert "390" not in inventory.target_modelos
    assert any(
        item.target_modelo == "353"
        and item.target_period == Period.from_year_and_code(2026, "12")
        and item.source_modelos == ("322",)
        for item in inventory.items
    )


def test_cross_period_dependency_inventory_covers_renta_2025_target_modelo(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        inventory = cross_period_dependency_inventory(
            bundled_authority(),
            filing_year=2025,
            modelos=("100",),
        )

    assert inventory.target_modelos == ("100",)
    assert len(inventory.items) == 1
    assert inventory.items[0].target_period == Period.from_year_and_code(2025, "0A")
    # M115 (arrendamiento retenciones) and M180 (retenciones anuales arrendamiento)
    # dependency classifications were retired as dormant M100 rental-retention
    # sources; the surviving suffered-retencion sources are 111/123/193.
    assert set(inventory.items[0].source_modelos) >= {
        "111",
        "123",
        "130",
        "131",
        "184",
        "190",
        "193",
    }


def test_cross_period_dependency_inventory_documents_patrimonio_and_foreign_asset_scope(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        inventories = tuple(
            cross_period_dependency_inventory(
                bundled_authority(),
                filing_year=filing_year,
            )
            for filing_year in (2025, 2026)
        )

    inventories_by_year = {inventory.filing_year: inventory for inventory in inventories}
    inventory_2025 = inventories_by_year[2025]
    inventory_2026 = inventories_by_year[2026]

    m714_items = tuple(item for item in inventory_2025.items if item.target_modelo == "714")
    assert len(m714_items) == 1
    assert m714_items[0].target_period == Period.from_year_and_code(2025, "0A")
    assert m714_items[0].source_modelos == ("100",)
    assert all(requirement.filing_year == 2025 for requirement in m714_items[0].dependencies)
    assert "714" not in inventory_2026.target_modelos

    for inventory in inventories:
        m720_items = tuple(item for item in inventory.items if item.target_modelo == "720")
        assert len(m720_items) == 1
        assert m720_items[0].target_period == Period.from_year_and_code(inventory.filing_year, "0A")
        assert m720_items[0].source_modelos == ("720",)
        assert all(
            requirement.filing_year == inventory.filing_year - 1
            and requirement.period == Period.from_year_and_code(inventory.filing_year - 1, "0A")
            and requirement.origin is CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING
            for requirement in m720_items[0].dependencies
        )

    assert all("721" not in inventory.target_modelos for inventory in inventories)
    assert all("721" not in inventory.source_modelos for inventory in inventories)


def test_cross_period_clean_state_blocks_missing_group_member_sources(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        snapshot = _snapshot_353()

        verdict = _evaluate_clean_state(snapshot)

    assert verdict.requires_clean_state is True
    assert any(evidence.requirement.requires_member_fan_in for evidence in verdict.dependencies)
    assert CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER in verdict.blockers
    assert CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE in verdict.blockers


def test_cross_period_clean_state_blocks_group_member_fan_in_without_expected_roster(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        _save_member_322_observation(
            observation_repository,
            member_nif=_GROUP_MEMBER_A,
            source_casilla_ids=requirement.source_casilla_ids,
        )

        verdict = _evaluate_clean_state(
            _snapshot_353(),
            observation_repository=observation_repository,
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert member_evidence.observed_member_nifs == (_GROUP_MEMBER_A,)
    assert member_evidence.expected_member_nifs == ()
    assert CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER in member_evidence.blockers
    assert CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE in member_evidence.blockers


def test_cross_period_clean_state_blocks_incomplete_expected_group_member_fan_in(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        _save_member_322_observation(
            observation_repository,
            member_nif=_GROUP_MEMBER_A,
            source_casilla_ids=requirement.source_casilla_ids,
        )

        verdict = _evaluate_clean_state(
            _snapshot_353(),
            observation_repository=observation_repository,
            taxpayer_tax_id=None,
            expected_member_sets=(
                CrossPeriodExpectedMemberSet(
                    source_modelo="322",
                    filing_year=_M353_YEAR,
                    period=Period.from_year_and_code(_M353_YEAR, _M353_PERIOD),
                    member_nifs=(_GROUP_MEMBER_A, _GROUP_MEMBER_B),
                ),
            ),
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert member_evidence.observed_member_nifs == (_GROUP_MEMBER_A,)
    assert member_evidence.expected_member_nifs == (_GROUP_MEMBER_A, _GROUP_MEMBER_B)
    assert member_evidence.missing_member_nifs == (_GROUP_MEMBER_B,)
    assert member_evidence.unexpected_member_nifs == ()
    assert CrossPeriodCleanStateBlocker.MISSING_EXPECTED_GROUP_MEMBER_ROSTER not in member_evidence.blockers
    assert CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE in member_evidence.blockers


def test_cross_period_clean_state_blocks_unexpected_group_member_fan_in(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        for member_nif in (_GROUP_MEMBER_A, _GROUP_MEMBER_B, _GROUP_MEMBER_C):
            _save_member_322_observation(
                observation_repository,
                member_nif=member_nif,
                source_casilla_ids=requirement.source_casilla_ids,
            )

        verdict = _evaluate_clean_state(
            _snapshot_353(),
            observation_repository=observation_repository,
            taxpayer_tax_id=None,
            expected_member_sets=(
                CrossPeriodExpectedMemberSet(
                    source_modelo="322",
                    filing_year=_M353_YEAR,
                    period=Period.from_year_and_code(_M353_YEAR, _M353_PERIOD),
                    member_nifs=(_GROUP_MEMBER_A, _GROUP_MEMBER_B),
                ),
            ),
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert member_evidence.observed_member_nifs == (_GROUP_MEMBER_A, _GROUP_MEMBER_B, _GROUP_MEMBER_C)
    assert member_evidence.expected_member_nifs == (_GROUP_MEMBER_A, _GROUP_MEMBER_B)
    assert member_evidence.missing_member_nifs == ()
    assert member_evidence.unexpected_member_nifs == (_GROUP_MEMBER_C,)
    assert CrossPeriodCleanStateBlocker.UNEXPECTED_GROUP_MEMBER_SOURCE in member_evidence.blockers


def test_cross_period_clean_state_accepts_member_scoped_group_filing_records(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        for member_nif in (_GROUP_MEMBER_A, _GROUP_MEMBER_B):
            _seed_member_322_filing(
                observation_repository,
                member_nif=member_nif,
                source_casilla_ids=requirement.source_casilla_ids,
            )

        verdict = _evaluate_clean_state(
            _snapshot_353(),
            observation_repository=observation_repository,
            taxpayer_tax_id=None,
            expected_member_sets=(
                CrossPeriodExpectedMemberSet(
                    source_modelo="322",
                    filing_year=_M353_YEAR,
                    period=Period.from_year_and_code(_M353_YEAR, _M353_PERIOD),
                    member_nifs=(_GROUP_MEMBER_A, _GROUP_MEMBER_B),
                ),
            ),
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert verdict.requires_clean_state is True
    assert verdict.clean is True
    assert member_evidence.clean is True
    assert member_evidence.member_filing_record_ids
    assert len(member_evidence.member_filing_record_ids) == 2
    assert member_evidence.member_calculation_revision_ids
    assert len(member_evidence.member_calculation_revision_ids) == 2


def test_cross_period_clean_state_blocks_member_filing_with_wrong_tax_id_justificante(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        requirement = _member_fan_in_requirement()
        _seed_member_322_filing(
            observation_repository,
            member_nif=_GROUP_MEMBER_A,
            justificante_tax_id=_GROUP_MEMBER_B,
            source_casilla_ids=requirement.source_casilla_ids,
        )

        verdict = _evaluate_clean_state(
            _snapshot_353(),
            observation_repository=observation_repository,
            taxpayer_tax_id=None,
            expected_member_sets=(
                CrossPeriodExpectedMemberSet(
                    source_modelo="322",
                    filing_year=_M353_YEAR,
                    period=Period.from_year_and_code(_M353_YEAR, _M353_PERIOD),
                    member_nifs=(_GROUP_MEMBER_A,),
                ),
            ),
        )

    member_evidence = next(evidence for evidence in verdict.dependencies if evidence.requirement.requires_member_fan_in)
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in member_evidence.blockers


def test_cross_period_clean_state_blocks_taxpayer_filing_with_wrong_tax_id_justificante(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(
            observation_repository=observation_repository,
            omit_justificante_metadata_periods={"1T"},
        )
        _persist_justificante_metadata(
            "JUST00001T",
            modelo="303",
            period="1T",
            filing_year=_M390_YEAR,
            tax_id="B12345674",
        )

        verdict = _evaluate_clean_state(
            _snapshot_390(),
            observation_repository=observation_repository,
        )

    first_quarter = _m390_first_quarter_evidence(verdict)
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_cross_period_clean_state_blocks_superseded_upstream_filing(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(observation_repository=observation_repository)
        filing_repository = ModeloRecordCatalogueRepository()
        catalogue = filing_repository.load()
        source_record = catalogue.current_for(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=_M390_YEAR,
            period=Period.from_year_and_code(_M390_YEAR, "1T"),
        )
        assert source_record is not None
        superseded_record = source_record.model_copy(
            update={
                "status": ModeloRecordStatus.SUPERSEDIDO,
                "superseded_at": _CLOCK,
                "superseded_by_filing_record_id": "f" * 64,
            },
        )
        filing_repository.save(
            ModeloRecordCatalogue(
                records={
                    **dict(catalogue.records),
                    source_record.filing_record_id: superseded_record,
                },
            ),
        )

        verdict = _evaluate_clean_state(
            _snapshot_390(),
            observation_repository=observation_repository,
            filing_repository=filing_repository,
            taxpayer_tax_id=None,
        )

    assert verdict.requires_clean_state is True
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.SUPERSEDED_DEPENDENCY in verdict.blockers
    assert CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD in verdict.blockers


def test_cross_period_clean_state_accepts_aeat_attested_reconciled_sources(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(observation_repository=observation_repository)

        verdict = _evaluate_clean_state(
            _snapshot_390(),
            observation_repository=observation_repository,
        )

    assert verdict.requires_clean_state is True
    assert verdict.clean is True
    assert verdict.blockers == ()


def test_cross_period_clean_state_accepts_matching_aeat_register_observation_provenance(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(
            observation_repository=observation_repository,
            source_metadata_by_period={
                "1T": {
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": "EXP-303-2025-1T",
                    "authenticated_identity": "X1234567L",
                    "aeat_justificante_csv": "JUST00001T",
                },
            },
        )

        verdict = _evaluate_clean_state(
            _snapshot_390(),
            observation_repository=observation_repository,
        )

    first_quarter = _m390_first_quarter_evidence(verdict)
    assert verdict.clean is True
    assert first_quarter.blockers == ()


def test_cross_period_clean_state_accepts_matching_filed_history_justificante_csv_provenance(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(
            observation_repository=observation_repository,
            source_metadata_by_period={
                "1T": {
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": "EXP-303-2025-1T",
                    "authenticated_identity": "X1234567L",
                    "aeat_justificante_csv": "JUST00001T",
                },
            },
        )

        verdict = _evaluate_clean_state(
            _snapshot_390(),
            observation_repository=observation_repository,
        )

    first_quarter = _m390_first_quarter_evidence(verdict)
    assert verdict.clean is True
    assert first_quarter.blockers == ()


def test_cross_period_clean_state_blocks_filed_history_justificante_csv_mismatch(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        observation_repository = CalculationObservationRepository()
        _seed_official_303_source_filings(
            observation_repository=observation_repository,
            source_metadata_by_period={
                "1T": {
                    "aeat_register_status": "ALTA",
                    "aeat_expediente_id": "EXP-303-2025-1T",
                    "authenticated_identity": "X1234567L",
                    "aeat_justificante_csv": "DIFFERENT-JUSTIFICANTE-CSV",
                },
            },
        )

        verdict = _evaluate_clean_state(
            _snapshot_390(),
            observation_repository=observation_repository,
        )

    first_quarter = _m390_first_quarter_evidence(verdict)
    assert verdict.clean is False
    assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in first_quarter.blockers


def test_empty_pre_activity_span_produces_no_cross_period_blocker_for_genuine_first_filer(
    tmp_path: Path,
) -> None:
    """A genuine first filer with no prior obligations verifies clean.

    The M390/2025 target depends on the four 2025 M303 quarters. An activity-start
    date of 2026-01-01 places every dependency strictly before activity start, so
    each is scoped out as no-prior-obligation (absent-by-design). No observation is
    seeded for any quarter; the verdict is fully clean on current-period merits and
    every suppressed dependency carries the typed provenance facet rather than a
    silent omission.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = _evaluate_clean_state(
            _snapshot_390(),
            activity_start_date=date(2026, 1, 1),
        )

    assert verdict.requires_clean_state is True
    assert verdict.clean is True
    assert verdict.blockers == ()
    suppressed = verdict.suppressed_pre_activity_dependencies
    assert len(suppressed) == len(verdict.dependencies)
    assert all(evidence.blockers == () for evidence in suppressed)
    assert all(evidence.no_prior_obligation is not None for evidence in suppressed)
    assert all(
        evidence.no_prior_obligation is not None
        and evidence.no_prior_obligation.activity_start_date == date(2026, 1, 1)
        and evidence.no_prior_obligation.provenance_kind is NoPriorObligationProvenanceKind.OPERATOR_DECLARED
        for evidence in suppressed
    )
    assert verdict.has_operator_declared_suppression_advisory is True


def test_alta_containing_period_stays_in_scope_as_first_obligation(tmp_path: Path) -> None:
    """At the ratified boundary, the alta-CONTAINING period is in scope.

    With activity start on 2025-10-01 (the first day of 4T), the M390/2025
    dependency graph suppresses 1T/2T/3T (strictly prior) but keeps 4T - the
    period that contains the alta - in scope as the first obligation. The
    in-scope 4T dependency is NOT marked suppressed and still demands its filing
    (here unevidenced, so it blocks), proving the alta-period is treated as a real
    obligation rather than scoped away.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = _evaluate_clean_state(
            _snapshot_390(),
            activity_start_date=date(2025, 10, 1),
        )

    fourth_quarter = Period.from_year_and_code(_M390_YEAR, "4T")
    fourth = next(e for e in verdict.dependencies if e.requirement.period == fourth_quarter)
    assert fourth.suppressed_pre_activity is False
    assert fourth.no_prior_obligation is None
    assert CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD in fourth.blockers
    suppressed_periods = {e.requirement.period.registry_token for e in verdict.suppressed_pre_activity_dependencies}
    assert suppressed_periods == {"1T", "2T", "3T"}


def test_activity_start_scoping_applies_to_both_requirement_origins(tmp_path: Path) -> None:
    """Scoping is uniform across previous_filing and relation origins.

    M180/0A derives its prior-quarter dependencies via registry RELATIONS over
    M115; M303/4T derives its prior-quarter dependency via a PREVIOUS_FILING
    binding over M303/3T. Both origins suppress their strictly-prior quarters under
    the same activity-start date, so a first filer is not unblocked on one origin
    while trapped on the other.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        relation_snapshot = bundled_authority().snapshot("180", filing_year=2026, period="0A")
        previous_filing_snapshot = bundled_authority().snapshot("303", filing_year=2026, period="4T")

        relation_verdict = _evaluate_clean_state(
            relation_snapshot,
            activity_start_date=date(2026, 7, 1),
        )
        previous_filing_verdict = _evaluate_clean_state(
            previous_filing_snapshot,
            activity_start_date=date(2026, 10, 15),
        )

    relation_suppressed = relation_verdict.suppressed_pre_activity_dependencies
    assert relation_suppressed
    assert all(e.requirement.origin is CrossPeriodDependencyOrigin.REGISTRY_RELATION for e in relation_suppressed)
    assert {e.requirement.period.registry_token for e in relation_suppressed} == {"1T", "2T"}

    # M303/4T depends on M303/3T (Jul-Sep) via BOTH a previous_filing binding and a
    # self-compensacion registry relation; an alta of 2026-10-15 places 3T strictly
    # before activity start, so BOTH origins suppress it. This proves the scoping is
    # uniform across the two requirement origins on the very same period.
    previous_filing_suppressed = previous_filing_verdict.suppressed_pre_activity_dependencies
    assert previous_filing_suppressed
    assert {e.requirement.period.registry_token for e in previous_filing_suppressed} == {"3T"}
    suppressed_origins = {e.requirement.origin for e in previous_filing_suppressed}
    assert CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING in suppressed_origins
    assert CrossPeriodDependencyOrigin.REGISTRY_RELATION in suppressed_origins


def test_real_prior_filing_post_dating_alta_still_blocks_anti_tautology(tmp_path: Path) -> None:
    """Anti-tautology: a real prior obligation after the alta still blocks.

    The scoping is NOT a vacuous open: a dependency whose period is on or after the
    declared activity-start date stays in scope and still demands official AEAT
    evidence. With activity start on 2025-01-01, every 2025 M303 quarter is in
    scope (none strictly prior); with no AEAT evidence seeded, the gate blocks
    exactly as it does without any activity-start date - proving an operator cannot
    scope away a real obligation that fell on or after the claimed start.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = _evaluate_clean_state(
            _snapshot_390(),
            activity_start_date=date(2025, 1, 1),
        )

    assert verdict.requires_clean_state is True
    assert verdict.clean is False
    assert verdict.suppressed_pre_activity_dependencies == ()
    assert CrossPeriodCleanStateBlocker.MISSING_OBSERVATION in verdict.blockers
    assert CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD in verdict.blockers


@cache
def _snapshot_202() -> RegistrySnapshot:
    return bundled_authority().snapshot("202", filing_year=2026, period="2P")


def test_first_year_modalidad_cuota_suppresses_m202_dependency_through_evaluator(tmp_path: Path) -> None:
    """A first-year modalidad-cuota IS filer clears the M202 cross-period gate.

    The M202/2026/2P snapshot derives a self-prior M202 pago-fraccionado
    dependency. With the derived modality ART_40_2_OPTIONAL and an activity-start
    date inside the target year (first IS year), the source-202 dependencies are
    scoped out as first-year no-fractional-payment obligations: no observation is
    seeded, yet every 202-source dependency is clean and carries the typed facet,
    and the verdict reports the advisory.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = _evaluate_clean_state(
            _snapshot_202(),
            taxpayer_tax_id="B12345674",
            activity_start_date=date(2026, 2, 1),
            modelo_202_modality=Modelo202Modality.ART_40_2_OPTIONAL,
        )

    m202_dependencies = [e for e in verdict.dependencies if e.requirement.source_modelo == "202"]
    assert m202_dependencies, "expected at least one M202-source cross-period dependency"
    assert all(e.suppressed_first_year_fractional for e in m202_dependencies)
    assert all(e.clean for e in m202_dependencies)
    assert all(
        e.no_prior_obligation is not None
        and e.no_prior_obligation.facet_kind
        is NoPriorObligationProvenanceKind.NO_FRACTIONAL_PAYMENT_OBLIGATION_FIRST_YEAR
        for e in m202_dependencies
    )
    assert verdict.has_first_year_fractional_suppression_advisory is True
    suppressed_periods = {
        e.requirement.period.registry_token for e in verdict.suppressed_first_year_fractional_dependencies
    }
    assert suppressed_periods


def test_mandatory_modalidad_base_keeps_m202_dependency_in_scope_through_evaluator(tmp_path: Path) -> None:
    """ART_40_3_MANDATORY keeps the M202 dependency in scope and blocking (fail-closed).

    Under modalidad base the pago fraccionado is owed in the first year, so the
    self-prior M202 dependency is NOT suppressed; with no AEAT evidence seeded it
    blocks exactly as it would without the modality, proving the suppression is
    refused for the mandatory modality.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = _evaluate_clean_state(
            _snapshot_202(),
            taxpayer_tax_id="B12345674",
            activity_start_date=date(2026, 2, 1),
            modelo_202_modality=Modelo202Modality.ART_40_3_MANDATORY,
        )

    m202_dependencies = [e for e in verdict.dependencies if e.requirement.source_modelo == "202"]
    assert m202_dependencies
    assert verdict.suppressed_first_year_fractional_dependencies == ()
    assert verdict.has_first_year_fractional_suppression_advisory is False
    assert any(not e.clean for e in m202_dependencies)


def test_incomplete_modality_keeps_m202_dependency_in_scope_through_evaluator(tmp_path: Path) -> None:
    """INCOMPLETE / unthreaded modality never suppresses the M202 dependency (fail-closed).

    When the modality cannot be derived (or is not threaded), the self-prior M202
    dependency stays in scope and blocks with no evidence seeded — a missing
    modality is never read as 'no obligation'.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        for modality in (Modelo202Modality.INCOMPLETE, None):
            verdict = _evaluate_clean_state(
                _snapshot_202(),
                taxpayer_tax_id="B12345674",
                activity_start_date=date(2026, 2, 1),
                modelo_202_modality=modality,
            )
            assert verdict.suppressed_first_year_fractional_dependencies == ()
            assert verdict.has_first_year_fractional_suppression_advisory is False
            assert verdict.clean is False


def test_non_first_year_keeps_m202_dependency_in_scope_through_evaluator(tmp_path: Path) -> None:
    """An activity-start year before the target year keeps the M202 dependency in scope.

    With activity start in 2025 (a prior IS year exists to provide the cuota
    basis), the modalidad-cuota M202 dependency is NOT suppressed and blocks on
    missing evidence — an operator cannot scope away a real prior obligation by
    declaring modalidad cuota.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        verdict = _evaluate_clean_state(
            _snapshot_202(),
            taxpayer_tax_id="B12345674",
            activity_start_date=date(2025, 6, 1),
            modelo_202_modality=Modelo202Modality.ART_40_2_OPTIONAL,
        )

    assert verdict.suppressed_first_year_fractional_dependencies == ()
    assert verdict.has_first_year_fractional_suppression_advisory is False
    assert verdict.clean is False


def test_partition_keeps_non_calendar_anchors_in_scope(tmp_path: Path) -> None:
    """A dependency with no calendar span is never silently dropped.

    The strictly-before predicate is guarded by Period.has_date_span(); a period
    that cannot be positioned against a date (e.g. an instalment clave) stays in
    scope rather than being silently suppressed. This proves the scoping never
    drops an anchor it cannot legitimately position.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        requirements = cross_period_dependency_requirements(_snapshot_390())

    instalment_period = Period.from_year_and_code(_M390_YEAR, "1P")
    assert instalment_period.has_date_span() is False
    forged = tuple(requirement.model_copy(update={"period": instalment_period}) for requirement in requirements[:1])
    partition = partition_cross_period_requirements_by_activity_start(
        forged,
        activity_start_date=date(2099, 1, 1),
    )
    assert partition.suppressed == ()
    assert partition.in_scope == forged
