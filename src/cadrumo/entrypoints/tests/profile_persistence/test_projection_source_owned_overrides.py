"""The Modelo 100 projection refuses caller figures for suffered-withholding credits.

The credits on 0596, 0597 and 0603 are owned by the taxpayer's payer records and
absence attestations. The calculation refuses a caller value for them, so the
projection, a planning estimate, refuses one the same way and under its own
command leaf. These run the real projection service over a seeded encrypted
profile, so the refusal comes from the service rather than a helper.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from cadrumo.application.modelo.action_errors import ModeloAggregationBindingError
from cadrumo.application.modelo.projection import ModeloProjectServiceResult, project_modelo_100_from_m130
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.retencion_soportada_bindings import retencion_soportada_bindings
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from cadrumo.entrypoints.adapter_composition_work_ports import (
    build_calculation_action_ports,
    build_work_lifecycle_ports,
)

from .general_iva_profile_facts_support import general_iva_profile_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_T0 = datetime(2026, 2, 2, 9, 0, tzinfo=UTC)
_BUCKET_ID = "59659659-0596-4596-8596-596596596596"
_YEAR = 2025
_M130_REVISION_ID = "2019-y-siguientes"
# The four Modelo 130 boxes the projection reads: cumulative ingresos, gastos and
# rendimiento neto, and the quarter's final result.
_M130_Q1_VALUES: dict[CasillaId, Decimal] = {
    validated_casilla_id("01", surface="projection guard test"): Decimal("10000.00"),
    validated_casilla_id("02", surface="projection guard test"): Decimal("4000.00"),
    validated_casilla_id("03", surface="projection guard test"): Decimal("6000.00"),
    validated_casilla_id("19", surface="projection guard test"): Decimal("1200.00"),
}
_CREDIT_CASILLAS = ("0596", "0597", "0603")
# A manual money box no source resolver owns (cash employment pay), and the
# computed employment-income total it is the only supplied addend of.
_UNRELATED_CASILLA = "0003"
_EMPLOYMENT_INCOME_TOTAL = "0012"


def _seed_profile(profile_id: str) -> None:
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=profile_id,
            facts=(
                *general_iva_profile_facts(tax_id="12345678Z", activity_start_date="2020-01-01"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="renta_filing.declaration_type", value="1"),
                UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
            context=_profile_creation_context_for_test(),
        ),
    )


def _seed_first_quarter(profile: TestRuntimeProfile, operation: PinnedAuthorityOperation) -> None:
    """Store one Modelo 130 1T draft revision carrying the boxes the projection reads."""
    work_unit = create_work_unit(
        bucket_id=profile.bucket_id,
        modelo="130",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "1T"),
        revision_id=_M130_REVISION_ID,
        ports=build_work_lifecycle_ports(bucket_id=profile.bucket_id),
        clock=_T0,
        operation=operation,
    )
    inputs = {casilla_id: str(value) for casilla_id, value in _M130_Q1_VALUES.items()}
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id=inputs,
            binding_overrides={},
            casilla_values=_M130_Q1_VALUES,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=inputs,
        binding_overrides={},
        casilla_values=_M130_Q1_VALUES,
        observations=registry_grounded_observations(
            modelo="130",
            filing_year=_YEAR,
            period="1T",
            casilla_values=_M130_Q1_VALUES,
        ),
        created_at=_T0,
        updated_at=_T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
    repository.save(upsert_calculation_revision(repository.load(), revision))


def _project(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    *,
    casilla_overrides: dict[str, str] | None = None,
    binding_overrides: dict[str, str] | None = None,
) -> ModeloProjectServiceResult:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_profile(profile.bucket_id)
        _seed_first_quarter(profile, operation)
        with bundled_indexed_authority().operation() as projection_operation:
            return project_modelo_100_from_m130(
                year=_YEAR,
                ccaa="madrid",
                bucket_id=profile.bucket_id,
                ports=build_calculation_action_ports(bucket_id=profile.bucket_id, operation=projection_operation),
                operation=projection_operation,
                casilla_overrides=casilla_overrides,
                binding_overrides=binding_overrides,
            )


def _family_binding_ids(operation: PinnedAuthorityOperation) -> tuple[str, ...]:
    revision = operation.snapshot("100", filing_year=_YEAR, period="0A").revision
    return tuple(sorted(binding.id for binding, _provider in retencion_soportada_bindings(revision)))


def test_the_family_binding_ids_are_the_revisions_own_declarations(*, operation: PinnedAuthorityOperation) -> None:
    """Anchor the ids so a renamed binding fails here instead of passing vacuously below."""
    assert _family_binding_ids(operation) == (
        "renta-retencion-soportada-capital-mobiliario",
        "renta-retencion-soportada-ganancia-patrimonial",
        "renta-retencion-soportada-trabajo",
    )


@pytest.mark.parametrize("casilla", _CREDIT_CASILLAS)
def test_a_caller_figure_on_a_credit_casilla_is_refused_under_the_projection_leaf(
    tmp_path: Path, casilla: str, *, operation: PinnedAuthorityOperation
) -> None:
    with pytest.raises(ModeloAggregationBindingError) as refused:
        _project(tmp_path, operation, casilla_overrides={casilla: "1950.00"})

    assert refused.value.translated_message == "application.modelo.errors.caller_casilla_source_binding_conflict"
    assert refused.value.context == {"casillas": [casilla]}
    failure = refused.value.precondition_failure
    assert failure is not None
    assert failure.identity == (
        "modelo.project",
        "modelo.project.source_inputs.unowned",
        "modelo.project.source_inputs.casilla_override_rejected",
    )


@pytest.mark.parametrize(
    "binding_id",
    [
        "renta-retencion-soportada-trabajo",
        "renta-retencion-soportada-capital-mobiliario",
        "renta-retencion-soportada-ganancia-patrimonial",
    ],
)
def test_a_caller_figure_on_a_credit_binding_is_refused_under_the_projection_leaf(
    tmp_path: Path, binding_id: str, *, operation: PinnedAuthorityOperation
) -> None:
    with pytest.raises(ModeloAggregationBindingError) as refused:
        _project(tmp_path, operation, binding_overrides={binding_id: "750.00"})

    assert refused.value.context == {"rejected_binding_ids": [binding_id]}
    failure = refused.value.precondition_failure
    assert failure is not None
    assert failure.identity == (
        "modelo.project",
        "modelo.project.source_inputs.unowned",
        "modelo.project.source_inputs.binding_override_rejected",
    )


def test_a_casilla_no_source_owns_is_still_accepted(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> None:
    """The guard is scoped to the credit family: an ordinary manual box still reaches the engine."""
    baseline = _project(tmp_path / "baseline", operation)
    overridden = _project(tmp_path / "overridden", operation, casilla_overrides={_UNRELATED_CASILLA: "1000.00"})

    def employment_income_total(result: ModeloProjectServiceResult) -> Decimal:
        return next(row.value for row in result.casilla_observations if row.casilla_id == _EMPLOYMENT_INCOME_TOTAL)

    assert employment_income_total(baseline) == Decimal("0.00")
    assert employment_income_total(overridden) == Decimal("1000.00")
