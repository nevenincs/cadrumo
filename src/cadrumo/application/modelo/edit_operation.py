"""Register modelo lifecycle operations using their canonical writers and public contracts.

Core types: :class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`,
:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from ...core.async_cleanup import await_cancellation_complete
from ...core.logging import get_logger
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ...core.time.clock import now as _utc_now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..operations.access_port import OperationAccessResolver
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operations.subject_reference import OperationSubjectReferenceV1
from ._edit_execution import apply_modelo_edit
from .action_errors import (
    modelo_edit_refusal_error,
)
from .calculation_action_ports import CalculationActionPortsFactory
from .edit_apply_contracts import ModeloEditApplyPublicResultV1
from .edit_baseline_projection import ModeloEditApplyBaselineV1
from .edit_models import (
    ModeloEditApplyRequestV1,
    ModeloEditDomainRefusalV1,
    ModeloEditExecutionNoEffectV1,
    ModeloEditExecutionResultV1,
    ModeloEditRefusalV1,
    ModeloEditScalarAddressV1,
    ModeloEditSubmissionV1,
)
from .edit_operation_requests import ModeloEditApplyOperationRequestV2
from .edit_receipt_ports import ModeloEditReceiptRepositoryFactory
from .edit_refusal_projection import ModeloEditCalculationPrerequisiteV1, ModeloEditPrerequisiteObserver
from .edit_transient_operand import modelo_edit_financial_operand

if TYPE_CHECKING:
    from ..operations.models import OperationRequest
    from ..operations.owner import OperationExecutorContext


from .operation_shared import (
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
    modelo_workspace_refresh_target_binding,
    resolve_modelo_work_unit_refresh_target,
)


class ModeloEditApplyExecutor:
    """Run the Edit Contract's guarded compare-and-swap apply under one recorded identity.

    apply_modelo_edit already owns the commit-point baseline recheck, the
    calculate/recalculate discrimination (recalculate refuses honestly, by
    design, until it is wired) and the co-committed result receipt; this only
    binds the running operation's own identity to that call and re-implements
    no lifecycle policy.
    """

    def __init__(
        self,
        *,
        calculation_action_ports_factory: CalculationActionPortsFactory,
        receipt_repository_factory: ModeloEditReceiptRepositoryFactory,
        prerequisite_observer: ModeloEditPrerequisiteObserver | None = None,
    ) -> None:
        """Bind the calculation authorities supplied by the composition root."""
        self._calculation_action_ports_factory = calculation_action_ports_factory
        self._receipt_repository_factory = receipt_repository_factory
        self._prerequisite_observer = prerequisite_observer

    async def execute(
        self,
        request: OperationRequest[ModeloEditApplyOperationRequestV2],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to apply_modelo_edit and return the settled receipt id.

        A refused edit (ModeloEditExecutionNoEffectV1) changed nothing: the
        effect is reported as NONE, then the refusal is raised as the
        registered refusal error of its family, which the supervisor settles
        as REFUSED under that error's code. Only the family travels; the
        typed refusal's addresses, facts, and evidence stay out of the
        operation's persisted record.

        Unlike its delegating siblings this executor declares ONE phase and
        publishes it, because there is no inner transition it cannot see.
        """
        await context.events.phase(MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID)
        operation = context.authority_operation

        def apply(submission: ModeloEditSubmissionV1) -> ModeloEditExecutionResultV1:
            with validating_governed_facts(operation):
                baseline = submission.baseline
                return apply_modelo_edit(
                    ModeloEditApplyRequestV1(operation_id=context.identity.operation_id, submission=submission),
                    ports=self._calculation_action_ports_factory(bucket_id=baseline.bucket_id, operation=operation),
                    receipt_repository=self._receipt_repository_factory(bucket_id=baseline.bucket_id),
                    now=_utc_now(),
                    result_destination=f"modelo/{baseline.modelo}/{baseline.filing_year}/{baseline.period}/edit-result",
                )

        async def publish(submission: ModeloEditSubmissionV1) -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                outcome = await asyncio.to_thread(apply, submission)
                if isinstance(outcome, ModeloEditExecutionNoEffectV1):
                    # A refused edit changed nothing, and NONE is the truthful report
                    # of that -- distinct from the UNKNOWN carried while the outcome
                    # was still open -- recorded before the refusal settles it.
                    await context.events.effect(OperationEffect.NONE)
                    self._deliver_prerequisite(
                        outcome.refusal,
                        operation_id=context.identity.operation_id,
                        baseline=ModeloEditApplyBaselineV1.from_baseline(submission.baseline),
                    )
                    raise modelo_edit_refusal_error(outcome.refusal)
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(
                    ModeloEditApplyPublicResultV1(
                        receipt_id=outcome.receipt.receipt_id,
                        calculation_revision_id=outcome.receipt.calculation_revision_id,
                    ),
                    written_at=_utc_now(),
                )

        async with context.typed_financial_operand.consume(ModeloEditSubmissionV1) as submission:
            try:
                return await await_cancellation_complete(publish(submission), task_name="modelo-edit-apply-publication")
            finally:
                del submission

    def _deliver_prerequisite(
        self, refusal: ModeloEditRefusalV1, *, operation_id: str, baseline: ModeloEditApplyBaselineV1
    ) -> None:
        """Hand a calculation source the refused Apply named to the private observer, if any.

        Private diagnostics never enter the operation record, and delivery cannot
        change the truthful NONE effect or the refusal that settles the operation.
        """
        observer = self._prerequisite_observer
        if (
            observer is None
            or not isinstance(refusal, ModeloEditDomainRefusalV1)
            or not isinstance(refusal.address, ModeloEditScalarAddressV1)
            or "calculation_source_unresolved" not in refusal.facts
        ):
            return
        try:
            observer(
                ModeloEditCalculationPrerequisiteV1(
                    operation_id=operation_id,
                    work_unit_id=baseline.work_unit_id,
                    baseline_id=baseline.baseline_id,
                    calculation_revision_id=baseline.current_calculation_revision_id,
                    casilla_id=refusal.address.casilla_id,
                    binding_ids=refusal.evidence,
                )
            )
        except Exception:
            get_logger(__name__).warning("private edit diagnostic delivery was unavailable")


def build_modelo_edit_apply_definition(
    *,
    calculation_action_ports_factory: CalculationActionPortsFactory,
    receipt_repository_factory: ModeloEditReceiptRepositoryFactory,
    prerequisite_observer: ModeloEditPrerequisiteObserver | None = None,
) -> OperationDefinition:
    """Bind the Edit Contract's guarded apply path to its registered operation contract."""

    def build() -> ModeloEditApplyExecutor:
        return ModeloEditApplyExecutor(
            calculation_action_ports_factory=calculation_action_ports_factory,
            receipt_repository_factory=receipt_repository_factory,
            prerequisite_observer=prerequisite_observer,
        )

    return OperationDefinition(
        definition_id=MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
        request_type=ModeloEditApplyOperationRequestV2,
        subject_reference=OperationSubjectReferenceV1.payload_field("work_unit_id"),
        result_type=ModeloEditApplyPublicResultV1,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloEditApplyOperationRequestV2,
            executor_type=ModeloEditApplyExecutor,
            build=build,
        ),
        phase_codes=("modelo.edit.apply",),
        interaction_kinds=frozenset({OperationInteractionKind.INPUT}),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.NONE,
            baseline=OperationBaselinePolicy.EXACT_APPROVAL,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        transient_financial_operand=modelo_edit_financial_operand(receipt_repository_factory),
        public_error_detail=False,
    )


def build_modelo_edit_apply_registration(
    definition: OperationDefinition,
    *,
    access_resolver: OperationAccessResolver | None = None,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the edit-apply definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.edit.apply.request",
            schema_version=2,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.edit.apply.result",
            schema_version=1,
            model_type=ModeloEditApplyPublicResultV1,
        ),
        workspace_refresh_target_schema=modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
        access_resolver=access_resolver,
    )
