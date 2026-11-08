"""Registered calculation binds real encrypted M303 evidence to a real revision."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.taxpayer_persona_support import seed_modelo_ready_profile
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.action_errors import ModeloCrossPeriodCleanStateError
from cadrumo.application.modelo.calculation_operation import ModeloWorkCalculateExecutor
from cadrumo.application.modelo.calculation_request_fields import (
    ModeloCalculationInputFieldsV1,
    ModeloCalculationOverride,
)
from cadrumo.application.modelo.m303_exonerado_390_applicability_attestation import (
    M303Exonerado390ApplicabilityAttestationRequest,
    admit_m303_exonerado_390_applicability_attestation,
)
from cadrumo.application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateCallerContext,
    ModeloWorkCalculateOrdinaryM303EvidenceRequestV2,
    ModeloWorkCalculatePublicResultV3,
    ModeloWorkCalculateRequest,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.workbench_projection import project_modelo_workbench_form
from cadrumo.application.modelo.workbench_read import read_modelo_workbench_form
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.next_step import (
    OperationCreateWorkStepV1,
    OperationOpenWorkStepV1,
)
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.core.errors.error_codes import ErrorCategory, get_registered_error_code
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.operations import OperationEffect
from cadrumo.core.period import Period
from cadrumo.domain.attachments.m303_filing_evidence import M303Exonerado390ApplicabilityAssertion
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.entrypoints.adapter_composition_work_ports import build_calculation_action_ports
from cadrumo.entrypoints.operation_composition_inputs import build_modelo_workbench_read_ports
from cadrumo.entrypoints.tests.production_operation_registry import production_operation_registry

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "3a1f0b2c-4d5e-4f60-8a71-92b3c4d5e6f7"
_CLOCK = datetime(2026, 1, 2, 10, tzinfo=UTC)
_OBSERVED_AT = datetime(2025, 12, 31, 12, tzinfo=UTC)


class _Events:
    """Capture effect statements made around the real encrypted writer."""

    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Cancellation:
    """Grant the irreversible section without replacing the calculation writer."""

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        yield


class _Context:
    """Supply only executor capabilities exercised by this admission path."""

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self.authority_operation = operation
        self.events = _Events()
        self.cancellation = _Cancellation()
        self.operands = operation_secure_reference_repository()


def _work_unit(operation: PinnedAuthorityOperation, *, modelo: str, period: Period) -> WorkUnit:
    snapshot = operation.snapshot(modelo, filing_year=2025, period=period.registry_token)
    ports = build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation)
    return create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo=modelo,
        filing_year=2025,
        period=period,
        revision_id=snapshot.revision.id,
        ports=ports.work_lifecycle_ports,
        clock=_CLOCK,
        operation=operation,
    )


def _attestation(
    operation: PinnedAuthorityOperation, store: AttachmentStore
) -> ModeloWorkCalculateOrdinaryM303EvidenceRequestV2:
    admission = admit_m303_exonerado_390_applicability_attestation(
        bucket_id=_PROFILE_ID,
        request=M303Exonerado390ApplicabilityAttestationRequest(
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            asserted_value=M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
            observed_at=_OBSERVED_AT,
        ),
        actor="operator",
        operation=operation,
        store=store,
        clock=lambda: _CLOCK,
    )
    return ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
        joint_return_elected=False,
        m303_exonerado_390_attachment_id=admission.attachment_id,
        m303_exonerado_390_sha256=admission.sha256,
    )


def _execute(
    *,
    work_unit: WorkUnit,
    evidence: ModeloWorkCalculateOrdinaryM303EvidenceRequestV2 | None,
    operation: PinnedAuthorityOperation,
    store: AttachmentStore,
    inputs: ModeloCalculationInputFieldsV1 | None = None,
    context: _Context | None = None,
) -> tuple[ModeloWorkCalculatePublicResultV3, _Events]:
    context = context or _Context(operation)
    executor = ModeloWorkCalculateExecutor(
        calculation_action_ports_factory=build_calculation_action_ports,
        attachment_store_factory=lambda _bucket_id: store,
    )
    request = OperationRequest(
        definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        subject_ref=work_unit.work_unit_id,
        payload=ModeloWorkCalculateRequest(
            work_unit_id=work_unit.work_unit_id,
            actor="operator",
            ordinary_m303_filing_evidence=evidence,
            caller_context=ModeloWorkCalculateCallerContext.EXPLICIT,
            inputs=inputs or ModeloCalculationInputFieldsV1(),
        ),
    )

    async def run() -> ModeloWorkCalculatePublicResultV3:
        reference = await executor.execute(request, cast(OperationExecutorContext, context))
        assert reference is not None
        return await context.operands.resolve(reference, ModeloWorkCalculatePublicResultV3)

    return asyncio.run(run()), context.events


@pytest.mark.parametrize(
    ("period_code", "election"),
    (("4T", False), ("1T", True)),
)
def test_m303_calculation_persists_exact_authored_evidence(
    period_code: str,
    election: bool,
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> None:
    period = Period.from_year_and_code(2025, period_code)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        seed_modelo_ready_profile(bucket_id=_PROFILE_ID, at=_CLOCK)
        # This synthetic taxpayer's declared activity begins in the selected
        # quarter; the canonical wallet gate can prove no earlier IVA period.
        upsert_test_profile_facts(
            _PROFILE_ID,
            (
                UserProfileFact(
                    path="censo.activity_start_date", value="2025-10-01" if period_code == "4T" else "2025-01-01"
                ),
            ),
        )
        with bound_test_profile_record(_PROFILE_ID):
            work_unit = _work_unit(operation, modelo="303", period=period)
            store = AttachmentStore()
            evidence = (
                _attestation(operation, store)
                if period_code == "4T"
                else ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(joint_return_elected=True)
            )
            result, events = _execute(work_unit=work_unit, evidence=evidence, operation=operation, store=store)
            revision = (
                CalculationRevisionCatalogueRepository(bucket_id=_PROFILE_ID)
                .load(operation=operation)
                .revisions[result.calculation_revision_id]
            )

    authored = cast(FilingInstanceEvidence, revision.filing_instance_evidence)
    assert authored.m303.period == period
    assert authored.m303.joint_return_elected is election
    assert authored.m303.annual_volume_nonzero is None
    assert (authored.m303.exonerado_390 is not None) is (period_code == "4T")
    assert result.work_unit_id == work_unit.work_unit_id
    assert result.revision_published is True
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]


def test_other_modelo_calculates_without_m303_evidence(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        seed_modelo_ready_profile(bucket_id=_PROFILE_ID, at=_CLOCK)
        with bound_test_profile_record(_PROFILE_ID):
            work_unit = _work_unit(operation, modelo="130", period=Period.from_year_and_code(2025, "1T"))
            # First-quarter prior-period answers are genuinely zero for this
            # new synthetic activity, and the registry requires them explicitly.
            inputs = ModeloCalculationInputFieldsV1(
                binding_overrides=tuple(
                    ModeloCalculationOverride(key=key, value="0")
                    for key in (
                        "irpf.previous_year_economic_activity_net_income",
                        "modelo-130-resultados-negativos-anteriores",
                        "modelo-130-pagos-fraccionados-anteriores",
                    )
                )
            )
            result, events = _execute(
                work_unit=work_unit,
                evidence=None,
                operation=operation,
                store=AttachmentStore(),
                inputs=inputs,
            )
            revision = (
                CalculationRevisionCatalogueRepository(bucket_id=_PROFILE_ID)
                .load(operation=operation)
                .revisions[result.calculation_revision_id]
            )

    assert revision.filing_instance_evidence is None
    assert result.work_unit_id == work_unit.work_unit_id
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]


def test_a_calculation_refused_before_any_write_reports_no_effect(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> None:
    """A Modelo 390 with no Modelo 303 quarter behind it is refused before anything is saved.

    The refusal comes after the calculation has run, because only its figures
    show which reconciliation boxes would be saved as an unproven zero. Nothing
    was written by then, so the operation must not say records may have changed.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        seed_modelo_ready_profile(bucket_id=_PROFILE_ID, at=_CLOCK)
        with bound_test_profile_record(_PROFILE_ID):
            work_unit = _work_unit(operation, modelo="390", period=Period.from_year_and_code(2025, "0A"))
            inputs = ModeloCalculationInputFieldsV1(
                binding_overrides=(
                    ModeloCalculationOverride(key="modelo-390-prorrata-regularizacion-anual", value="0"),
                )
            )
            context = _Context(operation)
            with pytest.raises(ModeloCrossPeriodCleanStateError) as refused:
                _execute(
                    work_unit=work_unit,
                    evidence=None,
                    operation=operation,
                    store=AttachmentStore(),
                    inputs=inputs,
                    context=context,
                )
            revisions = (
                CalculationRevisionCatalogueRepository(bucket_id=_PROFILE_ID).load(operation=operation).revisions
            )

    assert get_registered_error_code(refused.value).category is ErrorCategory.REFUSED
    assert not revisions
    assert context.events.effects == []
    assert refused.value.context is not None
    assert refused.value.context["missing_303_periods"] == ("1T", "2T", "3T", "4T")


def test_a_refused_annual_summary_names_where_each_quarter_stands_and_offers_the_first_step(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> None:
    """The Modelo 390 refusal says, per Modelo 303 quarter, why its filed figures are not there yet.

    The first quarter is calculated and not checked, the second exists without
    a calculation, and the last two do not exist. The refusal names each in
    order and offers opening the first quarter, whose own form says what is left.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID):
        seed_modelo_ready_profile(bucket_id=_PROFILE_ID, at=_CLOCK)
        upsert_test_profile_facts(_PROFILE_ID, (UserProfileFact(path="censo.activity_start_date", value="2025-01-01"),))
        with bound_test_profile_record(_PROFILE_ID):
            first = _work_unit(operation, modelo="303", period=Period.from_year_and_code(2025, "1T"))
            _execute(
                work_unit=first,
                evidence=ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(joint_return_elected=True),
                operation=operation,
                store=AttachmentStore(),
            )
            second = _work_unit(operation, modelo="303", period=Period.from_year_and_code(2025, "2T"))
            annual = _work_unit(operation, modelo="390", period=Period.from_year_and_code(2025, "0A"))
            with pytest.raises(ModeloCrossPeriodCleanStateError) as refused:
                _execute(
                    work_unit=annual,
                    evidence=None,
                    operation=operation,
                    store=AttachmentStore(),
                    inputs=ModeloCalculationInputFieldsV1(
                        binding_overrides=(
                            ModeloCalculationOverride(key="modelo-390-prorrata-regularizacion-anual", value="0"),
                        )
                    ),
                )
            pending = read_modelo_workbench_form(
                annual.work_unit_id,
                bucket_id=_PROFILE_ID,
                ports=build_modelo_workbench_read_ports(_PROFILE_ID, operation),
                operation=operation,
                operation_contracts=production_operation_registry().public_contract_set,
                language=OutputLanguage.ES,
            )
            projected = project_modelo_workbench_form(UUID(_PROFILE_ID), annual.work_unit_id, pending)

    context = refused.value.context
    assert context is not None
    # The to-do list reads the same answer the refusal names, before any calculation is tried.
    assert tuple(line.words for line in projected.source_requirements) == tuple(str(context["sources"]).split("; "))
    steps = [line.next_step for line in projected.source_requirements]
    assert isinstance(steps[0], OperationOpenWorkStepV1) and steps[0].work_unit_id == first.work_unit_id
    assert isinstance(steps[1], OperationOpenWorkStepV1) and steps[1].work_unit_id == second.work_unit_id
    assert all(isinstance(step, OperationCreateWorkStepV1) for step in steps[2:])
    assert context["missing_303_period_standings"] == ("1T:unverified", "2T:missing", "3T:missing", "4T:missing")
    sources = str(context["sources"])
    assert "calculada, sin comprobar" in sources and "sin calcular" in sources
    assert "{" not in sources
    step = refused.value.operation_next_step(OutputLanguage.ES)
    assert isinstance(step, OperationOpenWorkStepV1)
    assert step.work_unit_id == first.work_unit_id
