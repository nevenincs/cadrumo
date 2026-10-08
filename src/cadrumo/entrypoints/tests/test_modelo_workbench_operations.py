"""The workbench's worker reads run their production executors over real encrypted storage.

Each executor runs as the profile worker runs it -- under the pinned authority,
against the profile's repositories -- and hands its typed public result to
operand custody, which is kept in memory here. The supervisor, journal and
transport around them are proven by the registered-executor and native runtime
suites. Every result is shown to survive the registered result schema as JSON
and to restore the canonical read it was projected from.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ...application.modelo.edit_apply_contracts import ModeloEditApplySubmissionV1
from ...application.modelo.edit_baseline_projection import ModeloEditApplyBaselineV1
from ...application.modelo.edit_contract import ModeloEditMutationFamily
from ...application.modelo.edit_models import (
    ModeloEditAdmittedV1,
    ModeloEditPreflightEvaluatedV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditStaleBaselineRefusalV1,
    ModeloEditSubmissionV1,
    ModeloScalarEditIntentV1,
)
from ...application.modelo.edit_operator_input import ModeloEditOperatorInputV2, prepare_modelo_edit_operand
from ...application.modelo.edit_refusal_projection import (
    ModeloEditCalculationPrerequisiteV1,
    ModeloEditRefusalProjectionStore,
)
from ...application.modelo.edit_transient_operand import modelo_edit_financial_operand
from ...application.modelo.work_form_service import load_modelo_work_form
from ...application.modelo.workbench_operations import (
    MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
    MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
    MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID,
    MODELO_WORK_CASILLA_HELP_OPERATION_DEFINITION_ID,
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloCasillaHelpExecutor,
    ModeloCasillaHelpProjectionV1,
    ModeloCasillaHelpRequest,
    ModeloEditApplyPrerequisiteExecutor,
    ModeloEditApplyPrerequisiteProjectionV1,
    ModeloEditApplyPrerequisiteRequest,
    ModeloEditPreflightExecutor,
    ModeloEditPreflightProjectionV1,
    ModeloEditRenewalProjectionV1,
    ModeloEditRenewExecutor,
    ModeloEditRenewRequest,
    ModeloWorkbenchFormExecutor,
    ModeloWorkbenchFormRequest,
)
from ...application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1, restore_modelo_workbench_form
from ...application.modelo.workbench_read import ModeloWorkbenchReadPorts, read_modelo_workbench_form
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.operations.owner import OperationExecutorContext
from ...application.operations.tests.financial_operand_delivery import deliver_financial_operand
from ...application.operations.typed_financial_operand_context import BoundTypedFinancialOperandAccess
from ...core.casilla_id import validated_casilla_id
from ...core.external_constants import OutputLanguage
from ...core.hashing import content_hash_hex
from ...core.operations import OperationEffect
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_repository import CalculationRevisionPersistenceError
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ..adapter_composition import build_calculation_action_ports
from ..operation_composition import build_production_operation_registry
from .modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SET_06 = ModeloScalarEditIntentV1(
    address=ModeloEditScalarAddressV1(casilla_id=validated_casilla_id("06")),
    kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
    value="100",
)


class _Executor(Protocol):
    async def execute(self, request: Any, context: OperationExecutorContext) -> str: ...


class _OperationLoadRepository(Protocol):
    def load(self, *, operation: PinnedAuthorityOperation | None = None) -> Any: ...


@dataclass(slots=True)
class _Events:
    phases: list[str] = field(default_factory=list)
    effects: list[OperationEffect] = field(default_factory=list)

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Cancellation:
    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        yield


@dataclass(slots=True)
class _Operands:
    results: list[BaseModel] = field(default_factory=list)

    async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
        del written_at
        self.results.append(operand)
        return content_hash_hex({"operand": len(self.results)})


@dataclass(frozen=True, slots=True)
class _Context:
    identity: OperationIdentity
    authority_operation: PinnedAuthorityOperation
    events: _Events = field(default_factory=_Events)
    cancellation: _Cancellation = field(default_factory=_Cancellation)
    operands: _Operands = field(default_factory=_Operands)
    typed_financial_operand: BoundTypedFinancialOperandAccess = field(
        default_factory=lambda: BoundTypedFinancialOperandAccess(broker=None, declaration=None, requirement=None)
    )


def _run[ResultT: BaseModel](
    work: SeededOperatorWork,
    executor: _Executor,
    definition_id: str,
    payload: BaseModel,
    result_type: type[ResultT],
) -> tuple[ResultT, _Context]:
    """Run one executor as the worker does, and prove its result survives its public JSON form."""
    context = _Context(
        identity=OperationIdentity(
            operation_id=content_hash_hex({"read": definition_id}),
            definition_id=definition_id,
            subject_ref=work.work_unit_id,
        ),
        authority_operation=work.operation,
    )
    request = OperationRequest(definition_id=definition_id, subject_ref=work.work_unit_id, payload=payload)

    async def execute() -> None:
        nonlocal context
        if isinstance(payload, ModeloEditOperatorInputV2):
            prepared = prepare_modelo_edit_operand(
                definition_id=definition_id,
                profile_id=UUID(work.work_unit.bucket_id),
                subject_ref=work.work_unit_id,
                input_json=payload.model_dump_json(),
            )
            try:
                assert prepared.operand is not None
                async with deliver_financial_operand(
                    identity=context.identity,
                    declaration=modelo_edit_financial_operand(None),
                    operand=prepared.operand,
                ) as access:
                    prepared.release()
                    context = replace(context, typed_financial_operand=access)
                    await executor.execute(
                        OperationRequest(
                            definition_id=definition_id, subject_ref=work.work_unit_id, payload=prepared.request
                        ),
                        cast(OperationExecutorContext, context),
                    )
            finally:
                prepared.release()
        else:
            await executor.execute(request, cast(OperationExecutorContext, context))

    asyncio.run(execute())
    (result,) = context.operands.results
    assert isinstance(result, result_type)
    assert result_type.model_validate_json(result.model_dump_json()) == result
    assert context.events.phases == [definition_id]
    assert context.events.effects == [OperationEffect.NONE]
    return result, context


def _profile_id(work: SeededOperatorWork) -> UUID:
    return UUID(work.work_unit.bucket_id)


@dataclass(slots=True)
class _OperationLoadObservations:
    calculations: list[PinnedAuthorityOperation | None] = field(default_factory=list)
    verifications: list[PinnedAuthorityOperation | None] = field(default_factory=list)


def _observe_repository_load(
    repository: _OperationLoadRepository,
    observed_operations: list[PinnedAuthorityOperation | None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_load = repository.load

    def observe(*, operation: PinnedAuthorityOperation | None = None) -> Any:
        observed_operations.append(operation)
        return original_load(operation=operation)

    monkeypatch.setattr(repository, "load", observe)


def _assert_held_operation(
    observed_operations: list[PinnedAuthorityOperation | None],
    operation: PinnedAuthorityOperation,
) -> None:
    assert observed_operations
    assert all(observed is operation for observed in observed_operations)


def _workbench_read_ports(
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    *,
    observations: _OperationLoadObservations | None = None,
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> ModeloWorkbenchReadPorts:
    ports = build_calculation_action_ports(bucket_id=bucket_id, operation=operation)
    verifications = VerificationReportCatalogueRepository(bucket_id=bucket_id)
    if observations is not None:
        assert monkeypatch is not None
        _observe_repository_load(ports.calculation_repository, observations.calculations, monkeypatch)
        _observe_repository_load(verifications, observations.verifications, monkeypatch)
    return ModeloWorkbenchReadPorts(
        work_units=ports.work_unit_repository,
        calculations=ports.calculation_repository,
        verifications=verifications,
        bucket_events=ports.bucket_event_repository,
    )


def _ports_factory(
    work: SeededOperatorWork,
    *,
    observations: _OperationLoadObservations | None = None,
    monkeypatch: pytest.MonkeyPatch | None = None,
):
    return lambda bucket_id, operation: _workbench_read_ports(
        bucket_id, operation, observations=observations, monkeypatch=monkeypatch
    )


def test_the_form_read_admits_an_edit_and_restores_the_exact_application_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with seeded_operator_work(tmp_path) as work:
        work.recalculate()
        observations = _OperationLoadObservations()
        contracts = build_production_operation_registry().public_contract_set
        executor = ModeloWorkbenchFormExecutor(
            ports_factory=_ports_factory(work, observations=observations, monkeypatch=monkeypatch),
            contracts=lambda: contracts,
        )
        projection, _context = _run(
            work,
            executor,
            MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
            ModeloWorkbenchFormRequest(
                profile_id=_profile_id(work), work_unit_id=work.work_unit_id, output_language=OutputLanguage.EN
            ),
            ModeloWorkbenchFormProjectionV1,
        )
        assert len(observations.calculations) == 2
        restored = restore_modelo_workbench_form(
            ModeloWorkbenchFormProjectionV1.model_validate_json(projection.model_dump_json())
        )
        direct = read_modelo_workbench_form(
            work.work_unit_id,
            bucket_id=work.work_unit.bucket_id,
            ports=_workbench_read_ports(
                work.work_unit.bucket_id,
                work.operation,
                observations=observations,
                monkeypatch=monkeypatch,
            ),
            operation=work.operation,
            operation_contracts=contracts,
            language=OutputLanguage.EN,
        )
        _assert_held_operation(observations.calculations, work.operation)
        _assert_held_operation(observations.verifications, work.operation)
        assert len(observations.calculations) == 4
        standalone = load_modelo_work_form(
            work.work_unit.bucket_id,
            work.work_unit.modelo,
            work.work_unit.filing_year,
            work.work_unit.period,
            operation=work.operation,
            work_unit_repository=work.ports.work_unit_repository,
            calculation_repository=work.ports.calculation_repository,
            verification_repository=VerificationReportCatalogueRepository(bucket_id=work.work_unit.bucket_id),
            admission=direct.admission,
            language=OutputLanguage.EN,
            bucket_events=work.ports.bucket_event_repository,
        )

    assert projection.admitted_baseline is not None and projection.admission_refusal is None
    assert isinstance(restored.admission, ModeloEditAdmittedV1)
    assert restored.load == direct.load
    assert direct.load == standalone
    assert restored.calculation_revision_id == direct.calculation_revision_id
    assert restored.tax_id_format == direct.tax_id_format
    tampered = projection.model_copy(
        update={
            "admitted_baseline": projection.admitted_baseline.model_copy(
                update={"bucket_id": "13000000-0000-4000-8000-000000000999"}
            )
        }
    )
    with pytest.raises(ValidationError, match="admitted baseline belongs to another declaration"):
        ModeloWorkbenchFormProjectionV1.model_validate_json(tampered.model_dump_json())


def test_an_uncalculated_form_keeps_one_encrypted_catalogue_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with seeded_operator_work(tmp_path) as work:
        observations = _OperationLoadObservations()
        result = read_modelo_workbench_form(
            work.work_unit_id,
            bucket_id=work.work_unit.bucket_id,
            ports=_workbench_read_ports(
                work.work_unit.bucket_id, work.operation, observations=observations, monkeypatch=monkeypatch
            ),
            operation=work.operation,
            operation_contracts=build_production_operation_registry().public_contract_set,
            language=OutputLanguage.EN,
        )

    assert result.calculation_revision_id is None
    assert result.load.form.operator_entries_known
    assert observations.calculations == [work.operation]


def test_the_form_keeps_its_final_encrypted_parent_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with seeded_operator_work(tmp_path) as work:
        work.recalculate()
        ports = _workbench_read_ports(work.work_unit.bucket_id, work.operation)
        original_load = ports.calculations.load
        reads = 0

        def read_with_parent_removed(
            *, operation: PinnedAuthorityOperation | None = None
        ) -> CalculationRevisionCatalogue:
            nonlocal reads
            reads += 1
            if reads == 2:
                ports.work_units.save(WorkUnitCatalogue())
            return original_load(operation=operation)

        monkeypatch.setattr(ports.calculations, "load", read_with_parent_removed)
        with pytest.raises(CalculationRevisionPersistenceError) as refused:
            read_modelo_workbench_form(
                work.work_unit_id,
                bucket_id=work.work_unit.bucket_id,
                ports=ports,
                operation=work.operation,
                operation_contracts=build_production_operation_registry().public_contract_set,
                language=OutputLanguage.EN,
            )

    assert reads == 2
    assert refused.value.context is not None
    assert refused.value.context["reason"] == "missing_parent_work_unit"


def test_casilla_help_is_read_for_the_revision_and_calculation_the_form_showed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with seeded_operator_work(tmp_path) as work:
        head = work.recalculate()
        observations = _OperationLoadObservations()
        executor = ModeloCasillaHelpExecutor(
            ports_factory=_ports_factory(work, observations=observations, monkeypatch=monkeypatch)
        )
        projection, _context = _run(
            work,
            executor,
            MODELO_WORK_CASILLA_HELP_OPERATION_DEFINITION_ID,
            ModeloCasillaHelpRequest(
                profile_id=_profile_id(work),
                work_unit_id=work.work_unit_id,
                casilla_id=validated_casilla_id("06"),
                registry_revision_id=str(work.work_unit.revision_id),
                calculation_revision_id=head.calculation_revision_id,
                output_language=OutputLanguage.EN,
            ),
            ModeloCasillaHelpProjectionV1,
        )
        _assert_held_operation(observations.calculations, work.operation)

    assert projection.card.casilla_id == "06"
    assert projection.work_unit_id == work.work_unit_id


def test_renewal_extends_an_unmoved_baseline_and_names_what_moved_otherwise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with seeded_operator_work(tmp_path) as work:
        contracts = build_production_operation_registry().public_contract_set
        observations = _OperationLoadObservations()
        executor = ModeloEditRenewExecutor(
            ports_factory=_ports_factory(work, observations=observations, monkeypatch=monkeypatch),
            contracts=lambda: contracts,
        )
        expired = work.admit(issued_at=datetime.now(UTC) - timedelta(minutes=10))
        assert isinstance(expired, ModeloEditAdmittedV1)
        request = ModeloEditRenewRequest(
            profile_id=_profile_id(work), baseline=ModeloEditApplyBaselineV1.from_baseline(expired.baseline)
        )
        renewed, _ = _run(
            work, executor, MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID, request, ModeloEditRenewalProjectionV1
        )
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, record_operator_layer=True, clock=SEEDED_AT
        )
        moved, _ = _run(
            work, executor, MODELO_EDIT_RENEW_OPERATION_DEFINITION_ID, request, ModeloEditRenewalProjectionV1
        )
        _assert_held_operation(observations.calculations, work.operation)

    assert renewed.renewed_baseline is not None and renewed.refusal is None
    assert renewed.renewed_baseline.expires_at > datetime.now(UTC)
    assert moved.renewed_baseline is None and moved.refusal is not None
    assert isinstance(moved.refusal.refusal, ModeloEditStaleBaselineRefusalV1)


def test_preflight_names_the_address_of_its_findings_without_applying(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with seeded_operator_work(tmp_path) as work:
        before = work.recalculate()
        observations = _OperationLoadObservations()
        admission = work.admit()
        assert isinstance(admission, ModeloEditAdmittedV1)
        submission = ModeloEditSubmissionV1(
            baseline=admission.baseline, mutation_family=ModeloEditMutationFamily.CALCULATE, scalar_intents=(_SET_06,)
        )
        executor = ModeloEditPreflightExecutor(
            ports_factory=_ports_factory(work, observations=observations, monkeypatch=monkeypatch)
        )
        projection, _ = _run(
            work,
            executor,
            MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
            ModeloEditOperatorInputV2(submission=ModeloEditApplySubmissionV1.from_submission(submission)),
            ModeloEditPreflightProjectionV1,
        )
        after = work.require_head()
        _assert_held_operation(observations.calculations, work.operation)

    assert isinstance(projection.outcome, ModeloEditPreflightEvaluatedV1)
    assert all(finding.address in {None, _SET_06.address} for finding in projection.outcome.findings)
    assert after.calculation_revision_id == before.calculation_revision_id


def test_a_retained_prerequisite_is_handed_out_once_to_its_exact_apply(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        head = work.recalculate()
        store = ModeloEditRefusalProjectionStore()
        prerequisite = ModeloEditCalculationPrerequisiteV1(
            operation_id="d" * 64,
            work_unit_id=work.work_unit_id,
            baseline_id="b" * 64,
            calculation_revision_id=head.calculation_revision_id,
            casilla_id=validated_casilla_id("06"),
            binding_ids=(),
        )
        store.retain(prerequisite)
        executor = ModeloEditApplyPrerequisiteExecutor(ports_factory=_ports_factory(work), store=store)
        request = ModeloEditApplyPrerequisiteRequest(
            profile_id=_profile_id(work),
            work_unit_id=work.work_unit_id,
            apply_operation_id="d" * 64,
            baseline_id="b" * 64,
            calculation_revision_id=head.calculation_revision_id,
            registry_revision_id=str(work.work_unit.revision_id),
        )
        first, _ = _run(
            work,
            executor,
            MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
            request,
            ModeloEditApplyPrerequisiteProjectionV1,
        )
        second, _ = _run(
            work,
            executor,
            MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
            request,
            ModeloEditApplyPrerequisiteProjectionV1,
        )
        store.retain(replace(prerequisite, operation_id="e" * 64))
        other_baseline, _ = _run(
            work,
            executor,
            MODELO_EDIT_APPLY_PREREQUISITE_OPERATION_DEFINITION_ID,
            request.model_copy(update={"apply_operation_id": "e" * 64, "baseline_id": "c" * 64}),
            ModeloEditApplyPrerequisiteProjectionV1,
        )

    assert first.prerequisite is not None
    assert first.prerequisite.casilla_id == "06"
    assert first.prerequisite.calculation_revision_id == head.calculation_revision_id
    assert second.prerequisite is None
    assert other_baseline.prerequisite is None
