"""Register modelo lifecycle operations using their canonical writers and public contracts.

Core types: :class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`,
:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import (
    OperationEffect,
    OperationInteractionKind,
)
from ...core.time.clock import now as _utc_now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.form_codes import form_for_role
from ..operations.access_port import OperationAccessResolver
from ..operations.capabilities import (
    RECORDED_COOPERATIVE_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_UPDATE_CAPABILITIES,
)
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_errors import (
    M303FilingEvidenceError,
)
from .calculation_action_ports import CalculationActionPortsFactory
from .calculation_advisory_projection import ModeloCalculationAdvisories
from .calculation_projection import ModeloCalculationSnapshot
from .m303_filing_evidence import m303_filing_evidence_failure
from .m303_ordinary_filing_evidence_authoring import author_ordinary_m303_evidence_for_work
from .metadata_projection import ModeloWorkMetadataSnapshot
from .work_calculation_contracts import (
    ModeloOperatorEntriesCarry,
    ModeloWorkCalculateCallerContext,
    ModeloWorkCalculatePublicResultV2,
    ModeloWorkCalculateReplacedHead,
    ModeloWorkCalculateRequest,
)

if TYPE_CHECKING:
    from ...domain.attachments.protocols import AttachmentStoreProtocol
    from ...domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
    from ...domain.modelos.work_unit import WorkUnit
    from ..operations.models import OperationRequest
    from ..operations.owner import OperationExecutorContext
    from .calculate_input import ModeloWorkCalculationServiceResult, WorkCalculateInputBundle
    from .calculation_action_ports import CalculationActionPorts


from .operation_shared import (
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    modelo_workspace_refresh_target_binding,
    resolve_modelo_work_unit_refresh_target,
)


def calculation_public_result(
    result: ModeloWorkCalculationServiceResult,
    *,
    operation: PinnedAuthorityOperation,
    replaced_head: ModeloWorkCalculateReplacedHead | None = None,
) -> ModeloWorkCalculatePublicResultV2:
    """Project the exact canonical return without post-publication catalogue reads."""
    return ModeloWorkCalculatePublicResultV2(
        work_unit_id=result.work_unit.work_unit_id,
        calculation_revision_id=result.revision.calculation_revision_id,
        calculation=ModeloCalculationSnapshot.from_revision(
            result.revision, work_unit=result.work_unit, operation=operation
        ),
        advisories=ModeloCalculationAdvisories.from_result(result, operation=operation),
        unit=ModeloWorkMetadataSnapshot.from_work_unit(result.work_unit),
        revision_published=result.revision_published,
        replaced_head=replaced_head,
    )


@dataclass(frozen=True, slots=True)
class PreparedModeloWorkCalculation:
    """One admitted work unit with canonical inputs and calculation authorities."""

    work_unit: WorkUnit
    ports: CalculationActionPorts
    inputs: WorkCalculateInputBundle


async def prepare_modelo_work_calculation(
    payload: ModeloWorkCalculateRequest,
    *,
    operation: PinnedAuthorityOperation,
    calculation_action_ports_factory: CalculationActionPortsFactory,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
) -> PreparedModeloWorkCalculation:
    """Apply the ordinary admission, M303 evidence, and input-channel policy."""
    from ...core.bucket_pointer import require_active_bucket_id
    from .work_lifecycle import ActiveWorkUnitUse, require_active_work_unit

    active_bucket_id = require_active_bucket_id()
    ports = calculation_action_ports_factory(bucket_id=active_bucket_id, operation=operation)
    if ports.work_unit_repository.bucket_id != active_bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    work_unit = require_active_work_unit(
        ports.work_unit_repository.load(),
        work_unit_id=payload.work_unit_id,
        repository_bucket_id=ports.work_unit_repository.bucket_id,
        use=ActiveWorkUnitUse.CALCULATE,
    )
    if work_unit.bucket_id != active_bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if payload.caller_context is ModeloWorkCalculateCallerContext.REPLAY_HEAD:
        replayed = await await_cancellation_complete(
            asyncio.to_thread(
                _replayed_head_inputs,
                payload=payload,
                work_unit=work_unit,
                ports=ports,
                operation=operation,
                attachment_store_factory=attachment_store_factory,
            ),
            task_name="modelo-work-calculate-caller-context-replay",
        )
        return PreparedModeloWorkCalculation(work_unit=work_unit, ports=ports, inputs=replayed)
    filing_instance_evidence = _ordinary_m303_filing_instance_evidence(
        payload=payload,
        work_unit=work_unit,
        operation=operation,
        attachment_store_factory=attachment_store_factory,
    )
    inputs = await await_cancellation_complete(
        asyncio.to_thread(
            payload.inputs.build_bundle,
            work_unit_id=payload.work_unit_id,
            ports=ports,
            profile=None,
            detail_rows=tuple(row.to_row() for row in payload.detail_rows),
            filing_instance_evidence=filing_instance_evidence,
        ),
        task_name="modelo-work-calculate-input-preparation",
    )
    return PreparedModeloWorkCalculation(work_unit=work_unit, ports=ports, inputs=inputs)


def _replayed_head_inputs(
    *,
    payload: ModeloWorkCalculateRequest,
    work_unit: WorkUnit,
    ports: CalculationActionPorts,
    operation: PinnedAuthorityOperation,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
) -> WorkCalculateInputBundle:
    """Project the current head's caller context onto the calculation input channels.

    A head stored before operator layers existed replays no values (they are
    unknown, not empty), and the recalculation records no layer either, so that
    uncertainty is carried rather than silently resolved.
    """
    from ...core.authority_grade import RegistryAuthorityGrade
    from .calculate_input import WorkCalculateInputBundle
    from .caller_context import caller_context_calculation_inputs, caller_context_of

    head = (
        ports.calculation_repository.load(operation=operation).get(work_unit.current_calculation_revision_id)
        if work_unit.current_calculation_revision_id is not None
        else None
    )
    caller_context = caller_context_of(head)
    filing_instance_evidence = _ordinary_m303_filing_instance_evidence(
        payload=payload,
        work_unit=work_unit,
        operation=operation,
        attachment_store_factory=attachment_store_factory,
        replayed=caller_context.filing_instance_evidence,
    )
    replay = caller_context_calculation_inputs(
        caller_context,
        revision=operation.snapshot(
            str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            grade=RegistryAuthorityGrade.CALCULATION,
        ).revision,
    )
    return WorkCalculateInputBundle.build(
        casilla_inputs=replay.casilla_inputs,
        text_casilla_inputs=replay.text_casilla_inputs,
        binding_values=replay.binding_values,
        enum_binding_values=replay.enum_binding_values,
        relation_values={},
        detail_rows=replay.detail_rows,
        borrador_snapshot_id=replay.borrador_snapshot_id,
        filing_instance_evidence=filing_instance_evidence,
        m210_official_tipo_renta_code=replay.m210_official_tipo_renta_code,
        m210_gross_income_source_mode=replay.m210_gross_income_source_mode,
        cleared_casilla_ids=replay.cleared_casilla_ids,
        record_operator_layer=caller_context.operator_layer_known,
    )


def replaced_calculation_head(
    prepared: PreparedModeloWorkCalculation,
    payload: ModeloWorkCalculateRequest,
    returned_unit: WorkUnit,
) -> ModeloWorkCalculateReplacedHead | None:
    """Name the head a calculation replaced and what became of the person's entries in it.

    Read from the unit admitted before the calculation and the unit the writer
    returned, so it states what this calculation did and nothing a later one
    changed.
    """
    earlier = prepared.work_unit.current_calculation_revision_id
    if earlier is None or returned_unit.current_calculation_revision_id == earlier:
        return None
    if payload.caller_context is ModeloWorkCalculateCallerContext.EXPLICIT:
        carry = ModeloOperatorEntriesCarry.REPLACED_BY_REQUEST
    elif prepared.inputs.record_operator_layer:
        carry = ModeloOperatorEntriesCarry.REPLAYED
    else:
        carry = ModeloOperatorEntriesCarry.NOT_RECORDED
    return ModeloWorkCalculateReplacedHead(calculation_revision_id=earlier, operator_entries=carry)


def calculate_prepared_modelo_work(
    prepared: PreparedModeloWorkCalculation, *, actor: str
) -> ModeloWorkCalculationServiceResult:
    """Run the one canonical calculation service for prepared worker inputs."""
    from .calculate_input import calculate_modelo_work_revision

    return calculate_modelo_work_revision(
        work_unit_id=prepared.work_unit.work_unit_id,
        actor=actor,
        inputs=prepared.inputs,
        ports=prepared.ports,
    )


def _ordinary_m303_filing_instance_evidence(
    *,
    payload: ModeloWorkCalculateRequest,
    work_unit: WorkUnit,
    operation: PinnedAuthorityOperation,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
    replayed: FilingInstanceEvidence | None = None,
) -> FilingInstanceEvidence | None:
    """Author the one supported M303 envelope, or replay the head's, before calculation.

    Newly supplied facts are authored and win: the operator answered the
    questions again. Absent a new answer, the head's recorded evidence is
    replayed, because those are the operator's standing filing facts for this
    declaration. Only when neither exists is the evidence missing.
    """
    supplied = payload.ordinary_m303_filing_evidence
    if work_unit.modelo != form_for_role("iva.periodic"):
        if supplied is None:
            return None
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "unsupported_modelo", {"modelo": str(work_unit.modelo), "evidence_present": True}
            )
        )
    if supplied is None and replayed is not None:
        return replayed
    if supplied is None:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "missing", {"modelo": str(work_unit.modelo), "evidence_present": False}
            )
        )
    return author_ordinary_m303_evidence_for_work(
        work_unit=work_unit,
        joint_return_elected=supplied.joint_return_elected,
        exonerado_390_attachment_id=supplied.m303_exonerado_390_attachment_id,
        exonerado_390_sha256=supplied.m303_exonerado_390_sha256,
        operation=operation,
        open_attachment_store=lambda: attachment_store_factory(work_unit.bucket_id),
    )


class ModeloWorkCalculateExecutor:
    """Recalculate a declaration from its ledger under the request's caller context.

    A replaying request is the workspace's Calculate action: it replays the
    caller context of the current calculation head -- the operator's own values
    and overrides, explicit clears, detail rows, Modelo 303 filing evidence,
    Modelo 210 selections and borrador snapshot -- so new ledger data reaches
    the declaration without discarding what the operator entered. A head stored
    before operator layers existed replays no values (they are unknown, not
    empty), and its recalculation records no layer either, so that uncertainty
    is carried rather than silently resolved. An explicit request, such as the
    CLI ``modelo work calculate`` command, keeps its full-specification
    semantics: exactly the inputs and detail rows it carries.
    """

    def __init__(
        self,
        *,
        calculation_action_ports_factory: CalculationActionPortsFactory,
        attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Retain the composition-owned calculation and encrypted-attachment factories."""
        self._calculation_action_ports_factory = calculation_action_ports_factory
        self._attachment_store_factory = attachment_store_factory
        self._execution_caller_reader = execution_caller_reader

    async def execute(
        self,
        request: OperationRequest[ModeloWorkCalculateRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate calculation without reinterpreting ledger or tax inputs."""
        await context.events.phase("modelo.work.calculate.ledger")
        payload = request.payload
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=payload.actor)
        prepared = await prepare_modelo_work_calculation(
            payload=payload,
            operation=context.authority_operation,
            calculation_action_ports_factory=self._calculation_action_ports_factory,
            attachment_store_factory=self._attachment_store_factory,
        )

        async def publish() -> str:
            # The canonical service also owns migrations and IVA decisions.
            # Hold COMMIT across all of it, including cancellation settlement.
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                result = await asyncio.to_thread(
                    calculate_prepared_modelo_work,
                    prepared,
                    actor=actor,
                )
                # A revision no-op alone cannot establish that preparatory
                # migrations and IVA decisions also made no changes.
                if result.revision_published:
                    await context.events.effect(OperationEffect.UPDATED)
                public_result = await asyncio.to_thread(
                    calculation_public_result,
                    result,
                    operation=context.authority_operation,
                    replaced_head=replaced_calculation_head(prepared, payload, result.work_unit),
                )
                return await context.operands.put(public_result, written_at=_utc_now())

        return await await_cancellation_complete(publish(), task_name="modelo-work-calculate-publication")


def build_modelo_work_calculate_definition(
    *,
    calculation_action_ports_factory: CalculationActionPortsFactory,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Bind the canonical calculation service to the shared operation platform."""

    def build() -> ModeloWorkCalculateExecutor:
        return ModeloWorkCalculateExecutor(
            calculation_action_ports_factory=calculation_action_ports_factory,
            attachment_store_factory=attachment_store_factory,
            execution_caller_reader=execution_caller_reader,
        )

    return OperationDefinition(
        definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkCalculateRequest,
        subject_reference=OperationSubjectReferenceV1.payload_field("work_unit_id"),
        result_type=ModeloWorkCalculatePublicResultV2,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkCalculateRequest,
            executor_type=ModeloWorkCalculateExecutor,
            build=build,
        ),
        phase_codes=("modelo.work.calculate.ledger",),
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=RECORDED_COOPERATIVE_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        public_error_detail=True,
    )


def build_modelo_work_calculate_registration(
    definition: OperationDefinition,
    *,
    access_resolver: OperationAccessResolver | None = None,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind calculation to the exact refresh target carried by the receipt."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.calculate.request",
            schema_version=4,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.calculate.result",
            schema_version=2,
            model_type=ModeloWorkCalculatePublicResultV2,
        ),
        workspace_refresh_target_schema=modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
        access_resolver=access_resolver,
    )
