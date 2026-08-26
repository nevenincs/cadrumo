"""Registered modelo work-lifecycle operations composed from existing writers.

Each definition here supervises a lifecycle writer that already exists; none
of them re-implements lifecycle policy. ``rename_work_unit`` already decides
what a rename means - that a discarded unit is immutable, that the
content-addressed id survives, that the catalogue and its lifecycle event
co-commit - and this module's only job is to run that decision under a
recorded operation identity.

That separation is the point. An enrolment that re-derived the rules would
give the supervised path different behaviour from the direct one, and the
lifecycle refusal an operator sees would depend on which door they came
through.

See Also:
    :func:`~cadrumo.application.modelo._work_lifecycle.rename_work_unit`
        The single writer this operation supervises.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field

from ...core import (
    STRICT_FROZEN_CONFIG,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ...core.errors import CadrumoError
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import CredentialFreeOperationRequest
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ._verification_actions import verify_modelo_revision
from ._work_lifecycle import discard_work_unit, get_work_unit, rename_work_unit

if TYPE_CHECKING:
    from ...domain.deadlines import TaxpayerProfile
    from ...domain.modelos import VerificationReport
    from ..operations.models import OperationRequest
    from ..operations.owner import OperationExecutorContext

MODELO_WORK_RENAME_OPERATION_DEFINITION_ID = "modelo.work.rename"
MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID = "modelo.work.discard"
MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID = "modelo.work.verify"
MODELO_WORK_VERIFY_PROGRESS_UNIT = "casilla"

_WORK_UNIT_ID = Annotated[str, Field(min_length=1, max_length=128)]
_WORK_UNIT_NAME = Annotated[str, Field(min_length=1, max_length=200)]


class ModeloWorkRenameRequest(CredentialFreeOperationRequest):
    """The addressed unit and the display name to give it.

    Credential-free by construction: a rename names a unit and a label, so the
    request carries nothing that would be unsafe to journal.
    """

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: _WORK_UNIT_ID
    new_name: _WORK_UNIT_NAME


class ModeloWorkRenamePublicResultV1(BaseModel):
    """The settled rename, as a caller outside this package may see it.

    A distinct projection rather than the WorkUnit itself: the stored record
    carries lifecycle state a result consumer has no business depending on.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    result_version: int = 1
    work_unit_id: _WORK_UNIT_ID
    name: _WORK_UNIT_NAME
    bucket_id: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkRenameExecutor:
    """Run the existing rename writer under one recorded operation identity."""

    def __init__(self, *, actor: str) -> None:
        """Bind the actor whose rename event this operation will emit."""
        self._actor = actor

    async def execute(
        self,
        request: OperationRequest[ModeloWorkRenameRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to the single writer and return the renamed unit's id.

        The writer owns the atomic write set - the work-unit catalogue and the
        bucket lifecycle event co-commit inside it - so nothing here opens a
        second write path around them.
        """
        del context
        renamed = rename_work_unit(
            request.payload.work_unit_id,
            request.payload.new_name,
            actor=self._actor,
        )
        return renamed.work_unit_id


class ModeloWorkDiscardBaseline(BaseModel):
    """The exact unit an operator approved for discard.

    Discard is destructive, so approval is bound to a state rather than to an
    id: the unit must still be the one that was shown. Carrying the observed
    ``updated_at`` is what makes a stale approval refusable instead of silently
    discarding a unit that moved after the operator looked at it.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    work_unit_id: _WORK_UNIT_ID
    name: _WORK_UNIT_NAME
    observed_updated_at: datetime


class ModeloWorkDiscardRequest(CredentialFreeOperationRequest):
    """The approved unit and the reason recorded against its discard."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    baseline: ModeloWorkDiscardBaseline
    reason: Annotated[str, Field(min_length=1, max_length=500)] | None = None


class ModeloWorkDiscardPublicResultV1(BaseModel):
    """The settled discard, as a caller outside this package may see it."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    result_version: int = 1
    work_unit_id: _WORK_UNIT_ID
    bucket_id: Annotated[str, Field(min_length=1, max_length=128)]
    discarded: bool


class ModeloWorkDiscardApprovalStaleError(CadrumoError, RuntimeError):
    """Raised when the approved unit is no longer the unit on disk."""


class ModeloWorkDiscardExecutor:
    """Run the existing discard writer against an exactly approved unit."""

    def __init__(self, *, actor: str) -> None:
        """Bind the actor whose discard event this operation will emit."""
        self._actor = actor

    async def execute(
        self,
        request: OperationRequest[ModeloWorkDiscardRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Verify the approval still holds, then delegate to the single writer.

        The approval check is about freshness, not lifecycle: whether a
        discarded unit may be discarded again is the writer's rule, and it
        refuses that itself with no effect. This only refuses acting on a unit
        the operator did not actually see.
        """
        del context
        baseline = request.payload.baseline
        current = get_work_unit(baseline.work_unit_id)
        if current.updated_at != baseline.observed_updated_at or current.name != baseline.name:
            raise ModeloWorkDiscardApprovalStaleError(
                translated_message="errors.refused.modelo_work_discard_approval_stale",
                context={"work_unit_id": baseline.work_unit_id},
            )
        discarded = discard_work_unit(
            baseline.work_unit_id,
            actor=self._actor,
            reason=request.payload.reason,
        )
        return discarded.work_unit_id


def build_modelo_work_discard_definition(*, actor: str) -> OperationDefinition:
    """Bind the discard writer to its registered operation contract."""

    def build() -> ModeloWorkDiscardExecutor:
        return ModeloWorkDiscardExecutor(actor=actor)

    return OperationDefinition(
        definition_id=MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkDiscardRequest,
        result_type=ModeloWorkDiscardPublicResultV1,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkDiscardRequest,
            executor_type=ModeloWorkDiscardExecutor,
            build=build,
        ),
        phase_codes=("modelo.work.discard",),
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.EXACT_APPROVAL,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_discard_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the discard definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.discard.request",
            schema_version=1,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.discard.result",
            schema_version=1,
            model_type=ModeloWorkDiscardPublicResultV1,
        ),
    )


type ModeloWorkVerifyProfileResolver = Callable[[], TaxpayerProfile]


class ModeloWorkVerifyRequest(CredentialFreeOperationRequest):
    """The calculation revision to verify.

    The taxpayer profile the gates are evaluated against is deliberately NOT
    carried here. It is resolved at execution from live state, so a request
    replayed later cannot verify against a profile the taxpayer has since
    changed.
    """

    model_config = STRICT_FROZEN_CONFIG

    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkVerifyPublicResultV1(BaseModel):
    """The settled verification outcome a caller outside this package may see.

    Counts rather than casilla id lists: a result consumer needs to know
    whether the revision is complete and how much is outstanding, and shipping
    the resolved ids would put a filing-shaped payload in the operation result
    where the verification report is the record of truth.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    result_version: int = 1
    verification_report_id: Annotated[str, Field(min_length=1, max_length=128)]
    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]
    completeness_status: Annotated[str, Field(min_length=1, max_length=64)]
    granted_verificado_completo: bool
    finding_count: Annotated[int, Field(ge=0)]
    missing_required_casilla_count: Annotated[int, Field(ge=0)]


def project_modelo_work_verify_result(report: VerificationReport) -> ModeloWorkVerifyPublicResultV1:
    """Project one persisted report onto the safe public result."""
    return ModeloWorkVerifyPublicResultV1(
        verification_report_id=str(report.verification_report_id),
        calculation_revision_id=str(report.calculation_revision_id),
        completeness_status=str(report.completeness_status),
        granted_verificado_completo=report.granted_verificado_completo,
        finding_count=len(report.findings),
        missing_required_casilla_count=len(report.missing_required_casilla_ids),
    )


class ModeloWorkVerifyExecutor:
    """Run the existing verification authority under a recorded identity."""

    def __init__(self, *, actor: str, profile_resolver: ModeloWorkVerifyProfileResolver) -> None:
        """Bind the actor and the live profile the gates are evaluated against."""
        self._actor = actor
        self._profile_resolver = profile_resolver

    async def execute(
        self,
        request: OperationRequest[ModeloWorkVerifyRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to the verification authority and return its report id.

        The authority owns the guarded persistence and the events it emits;
        nothing here writes a report or decides completeness.
        """
        del context
        report = verify_modelo_revision(
            request.payload.calculation_revision_id,
            actor=self._actor,
            workflow_profile=self._profile_resolver(),
        )
        return str(report.verification_report_id)


def build_modelo_work_verify_definition(
    *,
    actor: str,
    profile_resolver: ModeloWorkVerifyProfileResolver,
) -> OperationDefinition:
    """Bind the verification authority to its registered operation contract."""

    def build() -> ModeloWorkVerifyExecutor:
        return ModeloWorkVerifyExecutor(actor=actor, profile_resolver=profile_resolver)

    return OperationDefinition(
        definition_id=MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkVerifyRequest,
        result_type=ModeloWorkVerifyPublicResultV1,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkVerifyRequest,
            executor_type=ModeloWorkVerifyExecutor,
            build=build,
        ),
        phase_codes=("modelo.work.verify.gates", "modelo.work.verify.persist"),
        interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.COOPERATIVE,
            deadline=OperationDeadline.COOPERATIVE,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.REQUEST_BOUND,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.REQUEST_CANCEL,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_verify_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the verify definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.verify.request",
            schema_version=1,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.verify.result",
            schema_version=1,
            model_type=ModeloWorkVerifyPublicResultV1,
        ),
    )


def build_modelo_work_rename_definition(*, actor: str) -> OperationDefinition:
    """Bind the rename writer to its registered operation contract."""

    def build() -> ModeloWorkRenameExecutor:
        return ModeloWorkRenameExecutor(actor=actor)

    return OperationDefinition(
        definition_id=MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkRenameRequest,
        result_type=ModeloWorkRenamePublicResultV1,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkRenameRequest,
            executor_type=ModeloWorkRenameExecutor,
            build=build,
        ),
        phase_codes=("modelo.work.rename",),
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_rename_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the rename definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.rename.request",
            schema_version=1,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.rename.result",
            schema_version=1,
            model_type=ModeloWorkRenamePublicResultV1,
        ),
    )


__all__ = [
    "MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID",
    "MODELO_WORK_RENAME_OPERATION_DEFINITION_ID",
    "MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID",
    "MODELO_WORK_VERIFY_PROGRESS_UNIT",
    "ModeloWorkDiscardApprovalStaleError",
    "ModeloWorkDiscardBaseline",
    "ModeloWorkDiscardExecutor",
    "ModeloWorkDiscardPublicResultV1",
    "ModeloWorkDiscardRequest",
    "ModeloWorkRenameExecutor",
    "ModeloWorkRenamePublicResultV1",
    "ModeloWorkRenameRequest",
    "ModeloWorkVerifyExecutor",
    "ModeloWorkVerifyPublicResultV1",
    "ModeloWorkVerifyRequest",
    "build_modelo_work_discard_definition",
    "build_modelo_work_discard_registration",
    "build_modelo_work_rename_definition",
    "build_modelo_work_rename_registration",
    "build_modelo_work_verify_definition",
    "build_modelo_work_verify_registration",
    "project_modelo_work_verify_result",
]
