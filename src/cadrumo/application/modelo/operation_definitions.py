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
    :func:`~cadrumo.application.modelo.work_lifecycle.rename_work_unit`
        The single writer this operation supervises.
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, StringConstraints, TypeAdapter, model_validator

from ...core.country_code import CountryCodeAlpha2
from ...core.errors.hierarchy import CadrumoError
from ...core.filing_year import FilingYear
from ...core.identity import (
    BucketId,
    CalculationRevisionId,
    ContentDigest,
    ModeloEditBaselineId,
    WorkUnitId,
)
from ...core.irnr import M210PayerMode
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ...core.payment_election import PaymentElection
from ...core.period import Period
from ...core.refund_election import RefundElection
from ...domain.calculations.registry.ids import RevisionId
from ...domain.modelos.calculation_revision import CalculationRevisionAmendmentKind
from ...domain.modelos.calculation_revision_amendment import M303RectificativaMotive
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.row_models import (
    M184Clave,
    M184ClaveDeclarado,
    M184NaturalezaInmueble,
    M184SituacionInmueble,
    M184Subclave,
    Modelo184MemberRow,
    Modelo210AgrupacionRentaRow,
    Modelo232VinculadaRow,
    Modelo347ContraparteRow,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
)
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.financial_operand import OperationTransientFinancialOperandDeclaration
from ..operations.models import CredentialFreeOperationRequest, OperationTerminalReceipt
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ._amendment_actions import amend_modelo_revision
from ._edit_execution import apply_modelo_edit
from ._edit_models import (
    ModeloBindingEditIntentV1,
    ModeloDetailRowEditIntentV1,
    ModeloEditApplyRequestV1,
    ModeloEditBaselineV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditDetailRowAddressV1,
    ModeloEditDetailRowIntentKind,
    ModeloEditExecutionNoEffectV1,
    ModeloEditMutationFamily,
    ModeloEditMutationResultReceiptV1,
    ModeloEditPermittedSurfaceEntryV1,
    ModeloEditRowAddressV1,
    ModeloEditRowIntentKind,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSchemaIdentityV1,
    ModeloEditSubmissionV1,
    ModeloRowEditIntentV1,
    ModeloScalarEditIntentV1,
)
from ._edit_services import DETAIL_ROW_NATURAL_KEY_SEPARATOR
from ._export import ModeloExportCommand, export_modelo_revision
from ._filing_actions import file_modelo_revision
from ._verification_actions import verify_modelo_revision
from .edit_contract import ModeloEditCompatibilityTupleV1
from .work_lifecycle import discard_work_unit, get_work_unit, rename_work_unit
from .workspace_models import ModeloWorkspaceRefreshTargetV1

if TYPE_CHECKING:
    from ...domain.deadlines.models import TaxpayerProfile
    from ...domain.modelos.verification_report import VerificationReport
    from ..operations.models import OperationRequest
    from ..operations.owner import OperationExecutorContext
    from ._export import ModeloExportResult

MODELO_WORK_RENAME_OPERATION_DEFINITION_ID = "modelo.work.rename"
MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID = "modelo.work.discard"
MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID = "modelo.work.verify"
MODELO_WORK_FILE_OPERATION_DEFINITION_ID = "modelo.work.file"
MODELO_EXPORT_OPERATION_DEFINITION_ID = "modelo.export"
MODELO_WORK_AMEND_OPERATION_DEFINITION_ID = "modelo.work.amend"
MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID = "modelo.edit.apply"
MODELO_WORK_VERIFY_PROGRESS_UNIT = "casilla"

#: ``pattern=r"\S"`` refuses an all-whitespace id, which ``min_length`` alone
#: admits. An identifier is NOT stripped -- unlike a display name, altering it
#: would change what it addresses -- so the guard requires a non-whitespace
#: character and otherwise leaves the value exactly as given. Without it a
#: request naming "   " is journalled, takes a lease, and is scheduled before
#: failing to resolve at execution: real platform work for something that can
#: never settle.
_WORK_UNIT_ID = Annotated[str, Field(min_length=1, max_length=128, pattern=r"\S")]
#: Mirrors the DOMAIN's own display-name constraint, whitespace stripping
#: included. Without the strip this request type is LOOSER than the type it
#: feeds: "   " passes ``min_length=1`` here and then fails the domain's
#: stripped check at the writer -- so the platform journals a request, takes a
#: lease and schedules work for a rename that can never settle. Matching the
#: domain means the request carries exactly what the domain will store.
_WORK_UNIT_NAME = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]

#: Suffix appended to a definition id to name that enrolment's refresh-target
#: schema. Every Modelo enrolment binds the SAME target model, but each needs
#: its own schema identity: the registry resolves a schema binding by scanning
#: every registration and taking the first identity match, so one id shared
#: across enrolments would stop that lookup being definition-scoped.
MODELO_WORKSPACE_REFRESH_TARGET_SCHEMA_SUFFIX = "workspace_refresh_target"


class _WorkUnitSubject(BaseModel):
    """Validate an operation subject reference as a real work-unit identifier."""

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: WorkUnitId


def resolve_modelo_work_unit_refresh_target(
    terminal_receipt: OperationTerminalReceipt,
    /,
) -> ModeloWorkspaceRefreshTargetV1:
    """Derive the workspace read one settled Modelo work operation invalidates.

    Every definition below addresses one work unit, so the settled receipt's
    ``subject_ref`` is that unit's identifier. It is validated here rather
    than trusted: a subject that is not a well-formed
    :data:`~cadrumo.core.identity.WorkUnitId` raises, and the resolving
    service turns that into a typed refusal instead of handing a frontend a
    target it cannot read.
    """
    return ModeloWorkspaceRefreshTargetV1(
        work_unit_id=_WorkUnitSubject(work_unit_id=terminal_receipt.identity.subject_ref).work_unit_id,
    )


def _modelo_workspace_refresh_target_binding(definition_id: str) -> OperationSchemaBindingV1:
    """Bind one enrolment's refresh-target schema to the shared target model."""
    return OperationSchemaBindingV1.bind(
        schema_id=f"{definition_id}.{MODELO_WORKSPACE_REFRESH_TARGET_SCHEMA_SUFFIX}",
        schema_version=1,
        model_type=ModeloWorkspaceRefreshTargetV1,
    )


class ModeloWorkRenameRequest(CredentialFreeOperationRequest):
    """The addressed unit and the display name to give it.

    Credential-free by construction: a rename names a unit and a label, so the
    request carries nothing that would be unsafe to journal.
    """

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: _WORK_UNIT_ID
    new_name: _WORK_UNIT_NAME

    #: The operator this invocation acts as. The platform binds an actor at
    #: submission, never at composition, so baking one into a definition would
    #: make the production registry per-actor.
    actor: Annotated[str, Field(min_length=1, max_length=128)]


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

    async def execute(
        self,
        request: OperationRequest[ModeloWorkRenameRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to the single writer and return the renamed unit's id.

        The writer owns the atomic write set - the work-unit catalogue and the
        bucket lifecycle event co-commit inside it - so nothing here opens a
        second write path around them.

        The declared phase is published BEFORE delegating, because a phase
        marks entering a stage rather than finishing one: an observer watching
        this operation should see it start, not learn of it only once the
        write has already landed. Without this the definition advertises a
        phase no surface can ever show.
        """
        await context.events.phase(MODELO_WORK_RENAME_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.UNKNOWN)
        renamed = rename_work_unit(
            request.payload.work_unit_id,
            request.payload.new_name,
            actor=request.payload.actor,
        )
        await context.events.effect(OperationEffect.UPDATED)
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

    #: The operator this invocation acts as. The platform binds an actor at
    #: submission, never at composition, so baking one into a definition would
    #: make the production registry per-actor.
    actor: Annotated[str, Field(min_length=1, max_length=128)]


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

        The declared phase is published before the approval check, so a
        REFUSED discard is still observably a discard that started. Emitting
        only on success would make a stale-approval refusal indistinguishable
        from an operation that never ran.
        """
        await context.events.phase(MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID)
        # UNKNOWN while the approval is still being judged: a stale-approval
        # refusal below leaves the unit untouched, and claiming UPDATED before
        # the write would tell an observer a discard landed that never did.
        await context.events.effect(OperationEffect.UNKNOWN)
        baseline = request.payload.baseline
        current = get_work_unit(baseline.work_unit_id)
        if current.updated_at != baseline.observed_updated_at or current.name != baseline.name:
            raise ModeloWorkDiscardApprovalStaleError(
                translated_message="errors.refused.modelo_work_discard_approval_stale",
                context={"work_unit_id": baseline.work_unit_id},
            )
        discarded = discard_work_unit(
            baseline.work_unit_id,
            actor=request.payload.actor,
            reason=request.payload.reason,
        )
        await context.events.effect(OperationEffect.UPDATED)
        return discarded.work_unit_id


def build_modelo_work_discard_definition() -> OperationDefinition:
    """Bind the discard writer to its registered operation contract."""

    def build() -> ModeloWorkDiscardExecutor:
        return ModeloWorkDiscardExecutor()

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
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
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
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
    )


type ModeloWorkVerifyProfileResolver = Callable[[], TaxpayerProfile]


def resolve_active_workflow_profile() -> TaxpayerProfile:
    """Resolve the active taxpayer profile when an operation actually runs.

    Injected as a strategy rather than a value: a definition composed into the
    production registry must not close over whichever profile happened to be
    active when the registry was built.
    """
    from ..wizard.status import load_active_taxpayer_profile
    from ..workflow.persistence import workflow_state_repository

    return load_active_taxpayer_profile(workflow_state_repository().load())


class ModeloWorkVerifyRequest(CredentialFreeOperationRequest):
    """The calculation revision to verify.

    The taxpayer profile the gates are evaluated against is deliberately NOT
    carried here. It is resolved at execution from live state, so a request
    replayed later cannot verify against a profile the taxpayer has since
    changed.
    """

    model_config = STRICT_FROZEN_CONFIG

    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128, pattern=r"\S")]

    #: The operator this invocation acts as. The platform binds an actor at
    #: submission, never at composition, so baking one into a definition would
    #: make the production registry per-actor.
    actor: Annotated[str, Field(min_length=1, max_length=128, pattern=r"\S")]


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
    finding_count: NonNegativeInt
    missing_required_casilla_count: NonNegativeInt


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


# DELEGATED PHASE REPORTING, stated once for every executor in this module that
# delegates to an authority.
#
# Each such executor declares two phases -- an entry stage and an inner one --
# but hands the whole job to an authority that performs both inside a single
# call. The entry phase IS observable from here and is published before
# delegating. The inner phase is NOT: the transition to it happens inside the
# authority, invisible from outside, and emitting it after the call returns
# would mark ENTERING a stage that had already finished. An observer would read
# a phase that never bracketed any work, which is a worse report than silence.
#
# That leaves one declared code per such executor unbacked. It is a real gap,
# not an accepted one, and it closes in one of two ways: the authority receives
# the operation context and publishes the transition it can actually see, or
# the definition stops declaring a phase nobody can honestly emit. Both are
# decisions for the authority's owner rather than repairs to make from here.
#
# Effects follow the progression the other executor families use: UNKNOWN on
# entry, UPDATED once the write has landed. Reporting neither -- which this
# whole family did until 2026-08-31 -- makes the platform state that a filing
# operation changed nothing, which is a false claim rather than a silence.


_MODELO_WORK_VERIFY_GATES_PHASE = "modelo.work.verify.gates"
"""The one verify phase an executor outside the authority can honestly observe.

Declared here and used by both the definition's `phase_codes` and the emission,
so the code cannot be published under a spelling the definition does not
declare -- the execution context refuses an undeclared code, and a literal
repeated in two places is one typo away from that refusal at runtime.
"""


class ModeloWorkVerifyExecutor:
    """Run the existing verification authority under a recorded identity."""

    def __init__(self, *, profile_resolver: ModeloWorkVerifyProfileResolver) -> None:
        """Bind the live profile the gates are evaluated against."""
        self._profile_resolver = profile_resolver

    async def execute(
        self,
        request: OperationRequest[ModeloWorkVerifyRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to the verification authority and return its report id.

        The authority owns the guarded persistence and the events it emits;
        nothing here writes a report or decides completeness.

        Publishes its entry phase only -- see DELEGATED PHASE REPORTING above.
        """
        await context.events.phase(_MODELO_WORK_VERIFY_GATES_PHASE)
        await context.events.effect(OperationEffect.UNKNOWN)
        report = await asyncio.to_thread(
            functools.partial(
                verify_modelo_revision,
                request.payload.calculation_revision_id,
                actor=request.payload.actor,
                workflow_profile=self._profile_resolver(),
            )
        )
        await context.events.effect(OperationEffect.UPDATED)
        return str(report.verification_report_id)


def build_modelo_work_verify_definition(
    *,
    profile_resolver: ModeloWorkVerifyProfileResolver = resolve_active_workflow_profile,
) -> OperationDefinition:
    """Bind the verification authority to its registered operation contract."""

    def build() -> ModeloWorkVerifyExecutor:
        return ModeloWorkVerifyExecutor(profile_resolver=profile_resolver)

    return OperationDefinition(
        definition_id=MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkVerifyRequest,
        result_type=ModeloWorkVerifyPublicResultV1,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkVerifyRequest,
            executor_type=ModeloWorkVerifyExecutor,
            build=build,
        ),
        phase_codes=(_MODELO_WORK_VERIFY_GATES_PHASE, "modelo.work.verify.persist"),
        # No REVIEW: the platform's review contract means the executor presents a
        # reviewed operand and settles on the operator's verdict. These run
        # straight through, so claiming REVIEW would declare an interaction that
        # never happens.
        interaction_kinds=frozenset[OperationInteractionKind](),
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
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
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
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
    )


class ModeloWorkFileApproval(BaseModel):
    """The exact verified revision an operator approved for local filing.

    Filing is a durable declaration of what the taxpayer intends to submit, so
    approval names the revision AND the verification that justified it. A
    revision re-verified since approval is a different fact, and filing it on
    the strength of the older look would record an intent nobody formed.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]
    verification_report_id: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkFileRequest(CredentialFreeOperationRequest):
    """The approved revision and the operator's declared election choices."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    approval: ModeloWorkFileApproval
    refund_election: RefundElection = RefundElection.COMPENSAR
    payment_election: PaymentElection = PaymentElection.INGRESO
    notes: Annotated[str, Field(min_length=1, max_length=500)] | None = None

    #: The operator this invocation acts as. The platform binds an actor at
    #: submission, never at composition, so baking one into a definition would
    #: make the production registry per-actor.
    actor: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkFilePublicResultV1(BaseModel):
    """The recorded local filing, as a caller outside this package may see it.

    ``handoff_required`` is always true and is part of the contract, not a
    computed field: this operation records a filing locally and hands the
    operator the artefacts to submit themselves. Nothing here reaches AEAT.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    result_version: int = 1
    filing_record_id: Annotated[str, Field(min_length=1, max_length=128)]
    work_unit_id: _WORK_UNIT_ID
    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]
    handoff_required: bool = True


# SYNC DOMAIN CALLS RUN OFF THE EVENT LOOP
#
# The modelo authorities are synchronous, and two of them (`verify` and `file`)
# run a workflow preflight gate that calls `asyncio.run` internally. Calling
# them directly from an `async` executor is therefore not merely impolite, it
# RAISES: `asyncio.run()` cannot be called from a running event loop, and the
# supervisor records the resulting RuntimeError as an opaque diagnostic digest
# with no message. `verify` only reached that gate once its revision was
# verified-complete, so the defect stayed invisible while its fixture refused.
#
# `asyncio.to_thread` gives the callee a thread with no running loop, so its
# internal `asyncio.run` is legal again, and it copies the current context, so
# the bound repositories and profile resolve exactly as they do on the CLI. It
# also keeps a multi-second filing off the supervisor's loop, which a blocking
# bridge in the callee would not.


class ModeloWorkFileExecutor:
    """Record one local filing through the existing filing authority.

    This never submits to AEAT and never can: it calls the local filing
    authority and returns its record id. Live submission is prohibited, so the
    operation's whole output is a local record plus the operator's handoff.
    """

    def __init__(self, *, profile_resolver: ModeloWorkVerifyProfileResolver) -> None:
        """Bind the live profile the filing gates are judged against."""
        self._profile_resolver = profile_resolver

    async def execute(
        self,
        request: OperationRequest[ModeloWorkFileRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to the filing authority and return its record id.

        Every precondition - verification state, cross-period cleanliness,
        election legality - belongs to that authority and refuses there.

        Publishes its entry phase only -- see DELEGATED PHASE REPORTING above.
        """
        await context.events.phase("modelo.work.file.preconditions")
        await context.events.effect(OperationEffect.UNKNOWN)
        payload = request.payload
        record = await asyncio.to_thread(
            functools.partial(
                file_modelo_revision,
                payload.approval.calculation_revision_id,
                actor=request.payload.actor,
                workflow_profile=self._profile_resolver(),
                notes=payload.notes,
                refund_election=payload.refund_election,
                payment_election=payload.payment_election,
            )
        )
        await context.events.effect(OperationEffect.UPDATED)
        return str(record.filing_record_id)


def build_modelo_work_file_definition(
    *,
    profile_resolver: ModeloWorkVerifyProfileResolver = resolve_active_workflow_profile,
) -> OperationDefinition:
    """Bind the local filing authority to its registered operation contract."""

    def build() -> ModeloWorkFileExecutor:
        return ModeloWorkFileExecutor(profile_resolver=profile_resolver)

    return OperationDefinition(
        definition_id=MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkFileRequest,
        result_type=ModeloWorkFilePublicResultV1,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkFileRequest,
            executor_type=ModeloWorkFileExecutor,
            build=build,
        ),
        phase_codes=("modelo.work.file.preconditions", "modelo.work.file.record"),
        # No REVIEW: the platform's review contract means the executor presents a
        # reviewed operand and settles on the operator's verdict. These run
        # straight through, so claiming REVIEW would declare an interaction that
        # never happens.
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
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_file_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the local filing definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.file.request",
            schema_version=1,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.file.result",
            schema_version=1,
            model_type=ModeloWorkFilePublicResultV1,
        ),
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
    )


class ModeloExportRequest(CredentialFreeOperationRequest):
    """The revision to export and where the operator wants the artefact.

    The path is the operator's chosen destination, journalled because it is a
    location rather than content. The exported bytes never enter the request
    or the result.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]
    #: ``pattern=r"\S"`` refuses an all-whitespace destination, which
    #: ``min_length`` alone admits. NOT stripped: a path must stay byte-exact,
    #: and silently trimming one would mask a typo rather than surface it.
    output_path: Annotated[str, Field(min_length=1, max_length=4096, pattern=r"\S")]

    #: The operator this invocation acts as; stamped onto the exported
    #: artefact through the command built from this request.
    actor: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloExportPublicResultV1(BaseModel):
    """Evidence that one export happened, without the exported material.

    Custody of the artefact is the operator's from the moment it lands: this
    result names the file and fingerprints it so a later reader can prove which
    bytes were produced, and carries none of them.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    result_version: int = 1
    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]
    #: ``pattern=r"\S"`` refuses an all-whitespace destination, which
    #: ``min_length`` alone admits. NOT stripped: a path must stay byte-exact,
    #: and silently trimming one would mask a typo rather than surface it.
    output_path: Annotated[str, Field(min_length=1, max_length=4096, pattern=r"\S")]
    byte_size: NonNegativeInt
    file_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    export_format: Annotated[str, Field(min_length=1, max_length=64)]
    handoff_required: bool = True


def project_modelo_export_result(result: ModeloExportResult) -> ModeloExportPublicResultV1:
    """Project one export outcome onto the safe public result."""
    return ModeloExportPublicResultV1(
        calculation_revision_id=str(result.calculation_revision_id),
        output_path=str(result.output_path),
        byte_size=result.byte_size,
        file_sha256=str(result.file_sha256),
        export_format=str(result.format),
    )


class ModeloExportExecutor:
    """Export one revision through the existing authority, locally only.

    The authority is local by construction and never contacts AEAT; this
    enrolment adds no transport of its own, so an exported artefact reaches
    the tax authority only when a human carries it there.
    """

    def __init__(self, *, profile_resolver: ModeloWorkVerifyProfileResolver) -> None:
        """Bind the live profile the export gates are judged against."""
        self._profile_resolver = profile_resolver

    async def execute(
        self,
        request: OperationRequest[ModeloExportRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to the export authority and return the artefact digest.

        The command is built from the journalled request, so the identity an
        artefact is stamped with is the one this invocation recorded rather
        than whatever a closure happened to hold when the definition was built.

        Publishes its entry phase only -- see DELEGATED PHASE REPORTING above.
        """
        await context.events.phase("modelo.export.preconditions")
        await context.events.effect(OperationEffect.UNKNOWN)
        payload = request.payload
        command = ModeloExportCommand(
            calculation_revision_id=payload.calculation_revision_id,
            output_path=Path(payload.output_path),
            actor=payload.actor,
        )
        result = export_modelo_revision(command, workflow_profile=self._profile_resolver())
        await context.events.effect(OperationEffect.UPDATED)
        return str(result.file_sha256)


def build_modelo_export_definition(
    *,
    profile_resolver: ModeloWorkVerifyProfileResolver = resolve_active_workflow_profile,
) -> OperationDefinition:
    """Bind the export authority to its registered operation contract."""

    def build() -> ModeloExportExecutor:
        return ModeloExportExecutor(profile_resolver=profile_resolver)

    return OperationDefinition(
        definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
        request_type=ModeloExportRequest,
        result_type=ModeloExportPublicResultV1,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloExportRequest,
            executor_type=ModeloExportExecutor,
            build=build,
        ),
        phase_codes=("modelo.export.preconditions", "modelo.export.render"),
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.REQUEST_BOUND,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_export_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the export definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.export.request",
            schema_version=1,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.export.result",
            schema_version=1,
            model_type=ModeloExportPublicResultV1,
        ),
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
    )


class ModeloWorkAmendBaseline(BaseModel):
    """The externally filed return an amendment corrects.

    An amendment is only meaningful against a specific filed baseline, so the
    request names that record rather than a work unit: the baseline supplies
    the full casilla map, and the overrides replace only what changed.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    from_filing_record_id: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkAmendOverride(BaseModel):
    """One corrected casilla and the value that replaces it.

    The value crosses as an exact decimal STRING rather than a number. A public
    operation schema must validate and serialize to the same shape, and a bare
    Decimal does not: it accepts number-or-string and emits string. Carrying the
    digits avoids that asymmetry and any float coercion on the way.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    casilla_id: Annotated[str, Field(min_length=1, max_length=64)]
    value: Annotated[str, Field(pattern=r"^-?\d{1,15}(?:\.\d{1,6})?$")]

    def as_decimal(self) -> Decimal:
        """Return the exact value this override carries."""
        return Decimal(self.value)


class ModeloWorkAmendRequest(CredentialFreeOperationRequest):
    """One amendment: which baseline, which corrections, and why.

    ``reason`` is required because an amendment is a declaration to the tax
    authority that a previously filed figure was wrong; a correction with no
    stated reason is not something the operator should be able to file.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    baseline: ModeloWorkAmendBaseline
    amendment_kind: CalculationRevisionAmendmentKind
    overrides: Annotated[tuple[ModeloWorkAmendOverride, ...], Field(min_length=1, max_length=500)]
    reason: Annotated[str, Field(min_length=1, max_length=500)]
    m303_rectificativa_motive: M303RectificativaMotive | None = None

    #: The operator this invocation acts as. The platform binds an actor at
    #: submission, never at composition, so baking one into a definition would
    #: make the production registry per-actor.
    actor: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkAmendPublicResultV1(BaseModel):
    """The recorded amendment, as a caller outside this package may see it."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    result_version: int = 1
    filing_record_id: Annotated[str, Field(min_length=1, max_length=128)]
    amended_from_filing_record_id: Annotated[str, Field(min_length=1, max_length=128)]
    amendment_kind: CalculationRevisionAmendmentKind
    corrected_casilla_count: NonNegativeInt
    handoff_required: bool = True


class ModeloWorkAmendExecutor:
    """Record one amendment through the existing amendment authority.

    Like the filing enrolment this is local: an amendment is built and
    recorded here, and the operator submits it themselves.
    """

    async def execute(
        self,
        request: OperationRequest[ModeloWorkAmendRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to the amendment authority and return its record id.

        Which overrides are legal, which kinds a modelo admits, and whether the
        baseline is AEAT-attested are all the authority's decisions.

        Publishes its entry phase only -- see DELEGATED PHASE REPORTING above.
        """
        await context.events.phase("modelo.work.amend.baseline")
        await context.events.effect(OperationEffect.UNKNOWN)
        payload = request.payload
        record = amend_modelo_revision(
            from_filing_record_id=payload.baseline.from_filing_record_id,
            overrides={override.casilla_id: override.as_decimal() for override in payload.overrides},
            amendment_kind=payload.amendment_kind,
            m303_rectificativa_motive=payload.m303_rectificativa_motive,
            reason=payload.reason,
            actor=request.payload.actor,
        )
        await context.events.effect(OperationEffect.UPDATED)
        return str(record.filing_record_id)


def build_modelo_work_amend_definition() -> OperationDefinition:
    """Bind the amendment authority to its registered operation contract."""

    def build() -> ModeloWorkAmendExecutor:
        return ModeloWorkAmendExecutor()

    return OperationDefinition(
        definition_id=MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkAmendRequest,
        result_type=ModeloWorkAmendPublicResultV1,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkAmendRequest,
            executor_type=ModeloWorkAmendExecutor,
            build=build,
        ),
        phase_codes=("modelo.work.amend.baseline", "modelo.work.amend.record"),
        # No REVIEW: the platform's review contract means the executor presents a
        # reviewed operand and settles on the operator's verdict. These run
        # straight through, so claiming REVIEW would declare an interaction that
        # never happens.
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
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_amend_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the amendment definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.amend.request",
            schema_version=1,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.amend.result",
            schema_version=1,
            model_type=ModeloWorkAmendPublicResultV1,
        ),
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
    )


_MODELO_EDIT_MANUAL_OVERRIDE_OPERAND_KIND = "modelo.edit.manual_casilla_override"

#: Declared but not yet reachable from inside the executor: the manual
#: override amount already crosses fully typed and pre-admitted as part of
#: ModeloEditSubmissionV1 (the Edit Contract admission phase already
#: validated it), so nothing here asks the operator for it mid-flight today.
#: The declaration documents the operand this family is defined over and lets
#: a future mid-flight ask enroll under it. The broker side is reachable:
#: OperationExecutorContext exposes a financial_operand accessor, so an
#: executor that needs a mid-flight amount can ask for one under this kind.
_MODELO_EDIT_MANUAL_OVERRIDE_OPERAND = OperationTransientFinancialOperandDeclaration(
    operand_kind=_MODELO_EDIT_MANUAL_OVERRIDE_OPERAND_KIND,
    currency="EUR",
    scale=2,
    minimum=Decimal("-999999999999.99"),
    maximum=Decimal("999999999999.99"),
    lifetime=timedelta(minutes=5),
)


class ModeloEditApplyBaselineV1(BaseModel):
    """Wire mirror of ModeloEditBaselineV1 with a plain-string modelo code.

    Every field of ModeloEditBaselineV1 except ``modelo`` already crosses an
    operation payload safely: Hex64Str, bounded Annotated str, Period and the
    permitted-surface union are all plain Pydantic shapes with no custom core
    schema. Only ``modelo: ModeloCode`` does - it is a str subclass that
    customises its Pydantic core schema, which the operations payload-graph
    gate refuses inside a registered request payload - so only that one field
    is mirrored here. ``to_baseline`` re-validates it through the real type.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    compatibility: ModeloEditCompatibilityTupleV1
    bucket_id: BucketId
    modelo: Annotated[str, Field(min_length=3, max_length=3, pattern=r"^\d{3}$")]
    filing_year: FilingYear
    period_filing_year: FilingYear
    period_code: Annotated[str, Field(min_length=1, max_length=16)]
    work_unit_id: WorkUnitId
    work_catalogue_revision: ContentDigest
    calculation_catalogue_revision: ContentDigest
    current_calculation_revision_id: CalculationRevisionId | None
    law_selected_revision_id: RevisionId
    schema_identity: ModeloEditSchemaIdentityV1
    schema_version: Annotated[int, Field(ge=1)]
    permitted_surface: Annotated[tuple[ModeloEditPermittedSurfaceEntryV1, ...], Field(max_length=2000)]
    permitted_surface_digest: ContentDigest
    mutation_family: ModeloEditMutationFamily
    issued_at: datetime
    expires_at: datetime
    baseline_id: ModeloEditBaselineId

    def to_baseline(self) -> ModeloEditBaselineV1:
        """Translate back to the real, fully re-validated domain baseline.

        ``period`` is mirrored the same way as ``modelo``: ``Period`` is a
        core ``BaseModel`` that does not declare ``strict=True``, which the
        operations payload-graph gate also refuses, so the wire form carries
        its two source fields and reconstructs the real type here.
        """
        data = self.model_dump(mode="python")
        data["modelo"] = ModeloCode(data["modelo"])
        period_filing_year = data.pop("period_filing_year")
        period_code = data.pop("period_code")
        data["period"] = Period.from_year_and_code(period_filing_year, period_code)
        return ModeloEditBaselineV1.model_validate(data)

    @classmethod
    def from_baseline(cls, baseline: ModeloEditBaselineV1) -> ModeloEditApplyBaselineV1:
        """Mirror a domain baseline onto the wire form ``to_baseline`` reverses.

        Kept beside its inverse so the two directions cannot drift into
        disagreeing about which fields are mirrored: adding a field to the
        wire type without teaching this method is a validation error here, not
        a silently dropped coordinate.
        """
        data = baseline.model_dump(mode="python")
        period = data.pop("period")
        # The wire baseline does not restate the contract version: the enclosing
        # ModeloEditApplySubmissionV1 already carries it, and declaring it twice
        # would let the two disagree.
        data.pop("edit_contract_version", None)
        data["modelo"] = str(baseline.modelo)
        data["period_filing_year"] = period["filing_year"]
        data["period_code"] = period["code"]
        return cls.model_validate(data)


#: Wire-safe mirror of ``ModeloScalar`` (``Decimal | int | str | bool | date | None``).
#: ``Decimal`` validates from a JSON number OR a pattern-matched string but
#: always SERIALIZES back to a string, so a field typed ``ModeloScalar``
#: fails the operations payload-graph gate's validation/serialization
#: schema-identity check. Dropping the raw ``Decimal`` input option and
#: requiring a decimal amount to arrive as a string - exactly what
#: serialization already produces, and what real fixtures already pass
#: (``value="150.00"``) - removes the asymmetry with no loss of expressible
#: values, though NOT where this once said. ``to_submission`` does not restore
#: the ``Decimal``: ``ModeloScalar`` is a plain union and ``_EditModel`` is
#: strict, so a string crosses back as a string. The reconstruction happens one
#: layer further in, at the execution boundary, which coerces with
#: ``Decimal(str(value))`` keyed on the CASILLA'S DECLARED ``data_type`` from
#: the registry rather than on the value's Python type. That is the stronger
#: guarantee -- the registry decides what a casilla holds, not the wire -- but
#: it does mean a round trip through this mirror is not an identity for
#: ``Decimal``, and a test asserting that it is will fail correctly.
type _ModeloEditApplyScalarValue = int | str | bool | date | None


def _wire_scalar_value(value: object) -> _ModeloEditApplyScalarValue:
    """Mirror one domain ``ModeloScalar`` onto the payload-safe wire union.

    Only ``Decimal`` needs mirroring, and it becomes the exact characters
    ``str`` produces -- which is precisely what serialization already emits
    and what ``to_intent`` parses back. Every other member of ``ModeloScalar``
    is already a member of the wire union and crosses unchanged.

    Not a total inverse of the round trip, deliberately. ``ModeloScalar``
    admits a plain ``str``, so a string that spells a number is
    indistinguishable on the wire from a ``Decimal`` and comes back as a
    ``str``. Nothing is lost by that: the execution boundary reconstructs the
    amount with ``Decimal(str(value))`` according to the casilla's declared
    registry ``data_type``, so what a casilla holds is decided by the registry
    rather than by which Python type happened to survive the trip.
    """
    return str(value) if isinstance(value, Decimal) else value  # type: ignore[return-value]


class ModeloEditApplyScalarIntentV1(BaseModel):
    """Wire mirror of ModeloScalarEditIntentV1 with a payload-safe value."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    address: ModeloEditScalarAddressV1
    kind: ModeloEditScalarIntentKind
    value: _ModeloEditApplyScalarValue = None

    def to_intent(self) -> ModeloScalarEditIntentV1:
        """Translate back to the real, fully re-validated domain intent."""
        return ModeloScalarEditIntentV1(address=self.address, kind=self.kind, value=self.value)

    @classmethod
    def from_intent(cls, intent: ModeloScalarEditIntentV1) -> ModeloEditApplyScalarIntentV1:
        """Mirror a domain scalar intent onto the wire form ``to_intent`` reverses."""
        return cls(address=intent.address, kind=intent.kind, value=_wire_scalar_value(intent.value))


class ModeloEditApplyBindingIntentV1(BaseModel):
    """Wire mirror of ModeloBindingEditIntentV1 with a payload-safe value."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    address: ModeloEditBindingAddressV1
    kind: ModeloEditBindingIntentKind
    value: _ModeloEditApplyScalarValue = None

    def to_intent(self) -> ModeloBindingEditIntentV1:
        """Translate back to the real, fully re-validated domain intent."""
        return ModeloBindingEditIntentV1(address=self.address, kind=self.kind, value=self.value)

    @classmethod
    def from_intent(cls, intent: ModeloBindingEditIntentV1) -> ModeloEditApplyBindingIntentV1:
        """Mirror a domain binding intent onto the wire form ``to_intent`` reverses."""
        return cls(address=intent.address, kind=intent.kind, value=_wire_scalar_value(intent.value))


class ModeloEditApplyRowIntentV1(BaseModel):
    """Wire mirror of ModeloRowEditIntentV1 with payload-safe row values."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    address: ModeloEditRowAddressV1
    kind: ModeloEditRowIntentKind
    row: Annotated[tuple[ModeloEditApplyScalarIntentV1, ...], Field(max_length=200)] | None = None
    move_to_index: Annotated[int, Field(ge=1)] | None = None

    def to_intent(self) -> ModeloRowEditIntentV1:
        """Translate back to the real, fully re-validated domain intent."""
        return ModeloRowEditIntentV1(
            address=self.address,
            kind=self.kind,
            row=None if self.row is None else tuple(entry.to_intent() for entry in self.row),
            move_to_index=self.move_to_index,
        )

    @classmethod
    def from_intent(cls, intent: ModeloRowEditIntentV1) -> ModeloEditApplyRowIntentV1:
        """Mirror a domain row intent, including each of its scalar entries."""
        return cls(
            address=intent.address,
            kind=intent.kind,
            row=(
                None
                if intent.row is None
                else tuple(ModeloEditApplyScalarIntentV1.from_intent(entry) for entry in intent.row)
            ),
            move_to_index=intent.move_to_index,
        )


def _amount_within_declared_operand_bounds(value: _ModeloEditApplyScalarValue) -> bool:
    """Report whether a wire scalar value that parses as a decimal amount stays in bounds.

    A value that is not decimal-shaped (an integer, a plain non-numeric
    string, a boolean, or a date) carries no financial-operand meaning and is
    left to whatever business validation the domain reconstruction applies.
    """
    if not isinstance(value, str):
        return True
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return True
    return _MODELO_EDIT_MANUAL_OVERRIDE_OPERAND.admits(amount)


_WIRE_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

type _WireAmount = Annotated[str, Field(min_length=1, max_length=40)]
"""One decimal amount as the exact characters submitted.

``Decimal`` validates from a number or a string but always serializes to a
string, so a ``Decimal`` field fails the operations payload-graph gate's
validation/serialization schema-identity check. Carrying the characters
verbatim also keeps translation honest: the real row type parses them with the
same code the CLI path uses, so an amount the CLI would refuse is refused here
too rather than being pre-normalised into acceptability.
"""

type _WireOptionalAmount = _WireAmount | None

type _WireCode = Annotated[str, Field(max_length=40)]
"""One registry code exactly as supplied, left unhydrated on purpose.

The M232 row type hydrates its own codes through ``BeforeValidator`` metadata.
Mirroring a hydrated enum here would put a second hydration on the wire path,
free to drift until the wire accepts a code the CLI refuses. Carrying the raw
characters instead means translation hands them to the row type's own
constructor and the existing hydration runs unchanged - not a delegating copy,
no copy at all.
"""


def _optional_decimal(value: str | None) -> Decimal | None:
    """Parse one optional wire amount, leaving an absent value absent."""
    return None if value is None else Decimal(value)


def _wire_row_payload(row: BaseModel) -> dict[str, object]:
    """Dump one domain detail row with its amounts as their exact characters."""
    return {
        key: str(value) if isinstance(value, Decimal) else value for key, value in row.model_dump(mode="python").items()
    }


class _WireDetailRowMirror(BaseModel):
    """Shared inverse for the per-modelo detail-row wire mirrors.

    Each of the six mirrors hand-writes its own ``to_row``, because the
    domain constructors differ. The direction BACK does not differ: every
    field crosses unchanged except a ``Decimal``, which becomes the exact
    characters it already serializes to. Written once here rather than six
    times, so the mirrors cannot drift into disagreeing about what a total
    translation means.

    Total by construction rather than by inspection. The row is dumped whole,
    so a field added to the domain row is carried automatically; and because
    every mirror forbids extras, a field the wire type does NOT declare raises
    here instead of being silently dropped on its way to the payload.
    """

    model_config = _WIRE_CONFIG

    @classmethod
    def from_row(cls, row: BaseModel) -> Self:
        """Mirror one domain detail row onto its wire form."""
        return cls.model_validate(_wire_row_payload(row))


class ModeloEditApply184MemberRowV1(_WireDetailRowMirror):
    """Wire mirror of Modelo184MemberRow with decimal amounts as characters."""

    model_config = _WIRE_CONFIG

    row_type: Literal["miembro"] = "miembro"
    nif: Annotated[str, Field(min_length=1, max_length=20)]
    nombre: Annotated[str, Field(max_length=200)] = ""
    pais: CountryCodeAlpha2 | None = None
    porcentaje: _WireAmount
    importe: _WireAmount
    clave: M184Clave
    subclave: M184Subclave | None = None
    codigo_provincia: Annotated[str, Field(max_length=2)] | None = None
    miembro_a_31_diciembre: bool | None = None
    dias_miembro: Annotated[int, Field(ge=0, le=366)] | None = None
    domicilio_fiscal: Annotated[str, Field(max_length=40)] | None = None
    naturaleza_inmueble: M184NaturalezaInmueble | None = None
    situacion_inmueble: M184SituacionInmueble | None = None
    referencia_catastral: Annotated[str, Field(max_length=20)] | None = None
    clave_declarado: M184ClaveDeclarado | None = None
    porcentaje_titularidad_inmueble: _WireOptionalAmount = None
    dias_arrendamiento: Annotated[int, Field(ge=0, le=366)] | None = None
    reduccion: _WireOptionalAmount = None
    rendimiento_neto_previo_eo: _WireOptionalAmount = None
    rendimiento_neto_minorado_agricola_eo: _WireOptionalAmount = None

    def to_row(self) -> Modelo184MemberRow:
        """Translate back to the real, fully re-validated domain row."""
        return Modelo184MemberRow(
            nif=self.nif,
            nombre=self.nombre,
            pais=self.pais,
            porcentaje=Decimal(self.porcentaje),
            importe=Decimal(self.importe),
            clave=self.clave,
            subclave=self.subclave,
            codigo_provincia=self.codigo_provincia,
            miembro_a_31_diciembre=self.miembro_a_31_diciembre,
            dias_miembro=self.dias_miembro,
            domicilio_fiscal=self.domicilio_fiscal,
            naturaleza_inmueble=self.naturaleza_inmueble,
            situacion_inmueble=self.situacion_inmueble,
            referencia_catastral=self.referencia_catastral,
            clave_declarado=self.clave_declarado,
            porcentaje_titularidad_inmueble=_optional_decimal(self.porcentaje_titularidad_inmueble),
            dias_arrendamiento=self.dias_arrendamiento,
            reduccion=_optional_decimal(self.reduccion),
            rendimiento_neto_previo_eo=_optional_decimal(self.rendimiento_neto_previo_eo),
            rendimiento_neto_minorado_agricola_eo=_optional_decimal(self.rendimiento_neto_minorado_agricola_eo),
        )


class ModeloEditApply232VinculadaRowV1(_WireDetailRowMirror):
    """Wire mirror of Modelo232VinculadaRow carrying its codes unhydrated."""

    model_config = _WIRE_CONFIG

    row_type: Literal["vinculada"] = "vinculada"
    nif: Annotated[str, Field(min_length=1, max_length=20)]
    nombre: Annotated[str, Field(max_length=200)] = ""
    pais: CountryCodeAlpha2
    tipo_vinculacion: _WireCode = ""
    tipo_operacion: _WireCode = ""
    metodo: _WireCode = ""
    importe: _WireAmount

    def to_row(self) -> Modelo232VinculadaRow:
        """Translate back through the row type's own code hydration."""
        return Modelo232VinculadaRow(
            nif=self.nif,
            nombre=self.nombre,
            pais=self.pais,
            tipo_vinculacion=self.tipo_vinculacion,
            tipo_operacion=self.tipo_operacion,
            metodo=self.metodo,
            importe=Decimal(self.importe),
        )


class ModeloEditApply349OperadorRowV1(_WireDetailRowMirror):
    """Wire mirror of Modelo349OperadorRow with its importe as characters."""

    model_config = _WIRE_CONFIG

    row_type: Literal["operador"] = "operador"
    codigo_pais: CountryCodeAlpha2
    nif_comunitario: Annotated[str, Field(min_length=1, max_length=20)]
    razon_social: Annotated[str, Field(min_length=1, max_length=200)]
    clave_operacion: Literal["E", "M", "H", "A", "T", "S", "I", "R", "D", "C"]
    importe: _WireAmount

    def to_row(self) -> Modelo349OperadorRow:
        """Translate back to the real, fully re-validated domain row."""
        return Modelo349OperadorRow(
            codigo_pais=self.codigo_pais,
            nif_comunitario=self.nif_comunitario,
            razon_social=self.razon_social,
            clave_operacion=self.clave_operacion,
            importe=Decimal(self.importe),
        )


class ModeloEditApply349RectificacionRowV1(_WireDetailRowMirror):
    """Wire mirror of Modelo349RectificacionRow with its bases as characters."""

    model_config = _WIRE_CONFIG

    row_type: Literal["rectificacion"] = "rectificacion"
    codigo_pais: CountryCodeAlpha2
    nif_comunitario: Annotated[str, Field(min_length=1, max_length=20)]
    razon_social: Annotated[str, Field(min_length=1, max_length=200)]
    clave_operacion: Literal["E", "M", "H", "A", "T", "S", "I", "R", "D", "C"]
    ejercicio: Annotated[str, Field(min_length=4, max_length=4)]
    periodo: Annotated[str, Field(min_length=1, max_length=2)]
    base_rectificada: _WireAmount
    base_anterior: _WireAmount

    def to_row(self) -> Modelo349RectificacionRow:
        """Translate back through the row type's own periodo normalisation."""
        return Modelo349RectificacionRow(
            codigo_pais=self.codigo_pais,
            nif_comunitario=self.nif_comunitario,
            razon_social=self.razon_social,
            clave_operacion=self.clave_operacion,
            ejercicio=self.ejercicio,
            periodo=self.periodo,
            base_rectificada=Decimal(self.base_rectificada),
            base_anterior=Decimal(self.base_anterior),
        )


class ModeloEditApply347ContraparteRowV1(_WireDetailRowMirror):
    """Wire mirror of Modelo347ContraparteRow with quarterly amounts as characters."""

    model_config = _WIRE_CONFIG

    row_type: Literal["contraparte"] = "contraparte"
    nif: Annotated[str, Field(min_length=1, max_length=20)]
    nombre: Annotated[str, Field(max_length=200)] = ""
    importe_Q1: _WireAmount = "0"
    importe_Q2: _WireAmount = "0"
    importe_Q3: _WireAmount = "0"
    importe_Q4: _WireAmount = "0"
    clave_operacion: Literal["A", "B", "C", "D", "E", "F", "G"] = "A"
    pais_codigo: CountryCodeAlpha2 | None = None

    def to_row(self) -> Modelo347ContraparteRow:
        """Translate back to the real, fully re-validated domain row."""
        return Modelo347ContraparteRow(
            nif=self.nif,
            nombre=self.nombre,
            importe_Q1=Decimal(self.importe_Q1),
            importe_Q2=Decimal(self.importe_Q2),
            importe_Q3=Decimal(self.importe_Q3),
            importe_Q4=Decimal(self.importe_Q4),
            clave_operacion=self.clave_operacion,
            pais_codigo=self.pais_codigo,
        )


class ModeloEditApply210AgrupacionRentaRowV1(_WireDetailRowMirror):
    """Wire mirror of Modelo210AgrupacionRentaRow with its rates as characters."""

    model_config = _WIRE_CONFIG

    row_type: Literal["agrupacion_renta"] = "agrupacion_renta"
    source_id: Annotated[str, Field(min_length=1, max_length=200)]
    tipo_renta_code: Annotated[str, Field(min_length=2, max_length=2)]
    importe: _WireAmount
    tipo_gravamen: _WireAmount
    pagador_mode: M210PayerMode
    pagador_id: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    deriva_de_bien_derecho: bool
    bien_derecho_id: Annotated[str, Field(min_length=1, max_length=200)] | None = None

    def to_row(self) -> Modelo210AgrupacionRentaRow:
        """Translate back to the real, fully re-validated domain row."""
        return Modelo210AgrupacionRentaRow(
            source_id=self.source_id,
            tipo_renta_code=self.tipo_renta_code,
            importe=Decimal(self.importe),
            tipo_gravamen=Decimal(self.tipo_gravamen),
            pagador_mode=self.pagador_mode,
            pagador_id=self.pagador_id,
            deriva_de_bien_derecho=self.deriva_de_bien_derecho,
            bien_derecho_id=self.bien_derecho_id,
        )


type ModeloEditApplyDetailRowV1 = Annotated[
    ModeloEditApply184MemberRowV1
    | ModeloEditApply232VinculadaRowV1
    | ModeloEditApply349OperadorRowV1
    | ModeloEditApply349RectificacionRowV1
    | ModeloEditApply347ContraparteRowV1
    | ModeloEditApply210AgrupacionRentaRowV1,
    Field(discriminator="row_type"),
]
"""The wire mirror of the per-modelo detail-row union, discriminated as it is."""


_DETAIL_ROW_ADAPTER: Final = TypeAdapter(ModeloEditApplyDetailRowV1)


def wire_detail_row(row: BaseModel) -> ModeloEditApplyDetailRowV1:
    """Mirror any domain detail row onto the discriminated wire union.

    Dispatches through the union's own ``row_type`` discriminator rather than
    a hand-written row-type-to-class map. A map would be a second declaration
    of which shapes exist, free to fall behind the union it mirrors; adding a
    seventh row kind should not require remembering this site.
    """
    return _DETAIL_ROW_ADAPTER.validate_python(_wire_row_payload(row))


class ModeloEditApplyDetailRowAddressV1(BaseModel):
    """Wire mirror of ModeloEditDetailRowAddressV1 carrying the key's components.

    The domain address holds a ``natural_key``: the row's own identity fields
    joined with ``|``. That joined string is a bounded free-form string, which
    is the same shape a passphrase has, so the credential-free journal check
    refuses it on the ``key`` token in its name and no schema predicate could
    tell the two apart.

    Nothing is exempted to get around that. The joined string is a derived
    convenience rather than information: every component is one of the row's
    own declared identity fields, already carried in the clear by the row
    mirrors in this module and already admitted by the same check. So the
    components cross instead, and ``to_address`` derives the key exactly as the
    domain type expects it.

    Carrying the components is also strictly less ambiguous than carrying the
    join, because a component that itself contains the separator is
    indistinguishable from a boundary once joined.
    """

    model_config = _WIRE_CONFIG

    kind: Literal["detail_row"] = "detail_row"
    detail_row_kind: Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")]
    identity_components: Annotated[
        tuple[Annotated[str, Field(min_length=1, max_length=200)], ...],
        Field(min_length=1, max_length=8),
    ]

    def to_address(self) -> ModeloEditDetailRowAddressV1:
        """Derive the domain address by joining the components it was built from."""
        return ModeloEditDetailRowAddressV1(
            detail_row_kind=self.detail_row_kind,
            natural_key=DETAIL_ROW_NATURAL_KEY_SEPARATOR.join(self.identity_components),
        )


class ModeloEditApplyDetailRowIntentV1(BaseModel):
    """Wire mirror of ModeloDetailRowEditIntentV1 with a payload-safe row."""

    model_config = _WIRE_CONFIG

    address: ModeloEditApplyDetailRowAddressV1
    kind: ModeloEditDetailRowIntentKind
    row: ModeloEditApplyDetailRowV1 | None = None

    def to_intent(self) -> ModeloDetailRowEditIntentV1:
        """Translate back to the real, fully re-validated domain intent."""
        return ModeloDetailRowEditIntentV1(
            address=self.address.to_address(),
            kind=self.kind,
            row=None if self.row is None else self.row.to_row(),
        )


class ModeloEditApplySubmissionV1(BaseModel):
    """Wire mirror of ModeloEditSubmissionV1 carrying a payload-safe baseline.

    Scalar, binding and row intents are mirrored only for their ``value``
    field: ``ModeloScalar`` (``Decimal | int | str | bool | date | None``)
    fails the operations payload-graph gate's validation/serialization
    schema-identity check, because ``Decimal`` validates from a number or a
    string but always serializes to a string. Every other field of these
    three families - addresses, intent kinds, ``move_to_index`` - is already
    payload-safe and carried through unchanged. This is a total translation:
    every field of every mirrored intent converts, nothing is dropped.

    ``detail_row_intents`` is carried, one wire type per per-modelo row kind.
    Each mirrors its row's ``Decimal`` fields as the exact characters
    submitted, and the two kinds that hydrate registry codes carry them raw so
    the real row type runs its own hydration during translation - one
    hydration shared with the CLI ``--row key=value`` path rather than a second
    copy free to drift.

    The address is mirrored too, and deliberately not by mirroring its
    ``natural_key``: see :class:`ModeloEditApplyDetailRowAddressV1` for why the
    components cross instead of the string derived from them.

    The mirrored payload is INPUT, not authority: ``apply_modelo_edit``
    re-resolves and independently re-validates every coordinate at the
    guarded commit point regardless of what this wire type carried, so a
    stale or forged mirror cannot be believed - a mismatch surfaces as the
    typed no-effect result, never a bad write.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    edit_contract_version: Literal[1] = 1
    baseline: ModeloEditApplyBaselineV1
    mutation_family: ModeloEditMutationFamily
    scalar_intents: Annotated[tuple[ModeloEditApplyScalarIntentV1, ...], Field(max_length=500)] = ()
    binding_intents: Annotated[tuple[ModeloEditApplyBindingIntentV1, ...], Field(max_length=500)] = ()
    row_intents: Annotated[tuple[ModeloEditApplyRowIntentV1, ...], Field(max_length=500)] = ()
    detail_row_intents: Annotated[tuple[ModeloEditApplyDetailRowIntentV1, ...], Field(max_length=500)] = ()

    @model_validator(mode="after")
    def _require_scalar_amounts_within_declared_operand_bounds(self) -> ModeloEditApplySubmissionV1:
        """Enforce the manual-override operand's own declared currency, scale and range.

        The broker path (`OperationTransientFinancialOperandProtocolV1`) that
        would normally enforce `_MODELO_EDIT_MANUAL_OVERRIDE_OPERAND` is not
        reachable from any executor today (`OperationExecutorContext` has no
        accessor for it). The manual-override amount instead arrives here,
        through the already-admitted scalar intent value, so this duplicates
        the bounds the declaration promises rather than leaving them
        unenforced. It should collapse into the broker once that wire lands.
        """
        for intent in self.scalar_intents:
            if not _amount_within_declared_operand_bounds(intent.value):
                raise ValueError(
                    "scalar edit intent amount is outside the declared manual-override financial operand bounds"
                )
        return self

    def to_submission(self) -> ModeloEditSubmissionV1:
        """Translate back to the real, fully re-validated domain submission."""
        return ModeloEditSubmissionV1(
            baseline=self.baseline.to_baseline(),
            mutation_family=self.mutation_family,
            scalar_intents=tuple(intent.to_intent() for intent in self.scalar_intents),
            binding_intents=tuple(intent.to_intent() for intent in self.binding_intents),
            row_intents=tuple(intent.to_intent() for intent in self.row_intents),
            detail_row_intents=tuple(intent.to_intent() for intent in self.detail_row_intents),
        )

    @classmethod
    def from_submission(cls, submission: ModeloEditSubmissionV1) -> ModeloEditApplySubmissionV1:
        """Mirror a domain submission onto the wire form the operation accepts.

        This is the direction an operator surface needs. The executor already
        owned wire-to-domain; without its inverse the registered apply
        operation had no caller outside this package's own tests, because a
        frontend that stages domain intents had no way to reach it.

        REFUSES A SUBMISSION CARRYING DETAIL ROWS, and the refusal is the
        honest answer rather than a gap. A domain
        :class:`ModeloEditDetailRowAddressV1` holds only the JOINED
        ``natural_key``, while the wire form carries the identity components
        that were joined to make it -- deliberately, per
        :class:`ModeloEditApplyDetailRowAddressV1`, because a component
        containing the separator is indistinguishable from a boundary once
        joined. Splitting the key here would reconstruct the components by
        guessing, and would guess wrong exactly when a taxpayer's own
        identifier contains the separator. A caller staging detail rows still
        holds the components and must build the wire address from those; it
        does not come back out of the domain address.
        """
        if submission.detail_row_intents:
            raise ValueError(
                "detail-row intents cannot be mirrored from a domain submission: the domain address "
                "carries only the joined natural key, and splitting it would guess the identity "
                "components. Build the wire detail-row address from the components at the point they "
                "were staged."
            )
        return cls(
            baseline=ModeloEditApplyBaselineV1.from_baseline(submission.baseline),
            mutation_family=submission.mutation_family,
            scalar_intents=tuple(
                ModeloEditApplyScalarIntentV1.from_intent(intent) for intent in submission.scalar_intents
            ),
            binding_intents=tuple(
                ModeloEditApplyBindingIntentV1.from_intent(intent) for intent in submission.binding_intents
            ),
            row_intents=tuple(ModeloEditApplyRowIntentV1.from_intent(intent) for intent in submission.row_intents),
        )


class ModeloEditApplyOperationRequestV1(CredentialFreeOperationRequest):
    """The admitted Edit Contract submission this operation is authorized to apply.

    Credential-free by construction: every field is a pre-validated,
    pre-admitted coordinate or typed value the Edit Contract admission
    phase already produced, so nothing here is unsafe to journal.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    submission: ModeloEditApplySubmissionV1


class ModeloEditApplyPublicResultV1(BaseModel):
    """The settled receipt id a caller outside this package may see.

    Only the id: the full receipt is the domain record of truth, addressable
    through ModeloEditReceiptRepository, and this result exists to confirm
    which one a submission produced.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    result_version: int = 1
    receipt_id: Annotated[str, Field(min_length=1, max_length=128)]
    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]


def project_modelo_edit_apply_result(receipt: ModeloEditMutationResultReceiptV1) -> ModeloEditApplyPublicResultV1:
    """Project one settled receipt onto the safe public result."""
    return ModeloEditApplyPublicResultV1(
        receipt_id=str(receipt.receipt_id),
        calculation_revision_id=str(receipt.calculation_revision_id),
    )


class ModeloEditApplyExecutor:
    """Run the Edit Contract's guarded compare-and-swap apply under one recorded identity.

    apply_modelo_edit already owns the commit-point baseline recheck, the
    calculate/recalculate discrimination (recalculate refuses honestly, by
    design, until it is wired) and the co-committed result receipt; this only
    binds the running operation's own identity to that call and re-implements
    no lifecycle policy.
    """

    async def execute(
        self,
        request: OperationRequest[ModeloEditApplyOperationRequestV1],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to apply_modelo_edit and return the settled receipt id.

        A failed compare-and-swap is a typed domain fact
        (ModeloEditExecutionNoEffectV1), not an unexpected error, but the
        executor protocol this method implements returns only an optional
        reference. No channel exists yet to carry the typed refusal back to a
        caller outside this package through the operation result path, so it
        is reported here as a no-effect None rather than fabricated into an
        exception the refusal was deliberately designed not to be.

        Unlike its delegating siblings this executor declares ONE phase and
        publishes it, because there is no inner transition it cannot see.
        """
        await context.events.phase(MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.UNKNOWN)
        submission = request.payload.submission.to_submission()
        baseline = submission.baseline
        apply_request = ModeloEditApplyRequestV1(
            operation_id=context.identity.operation_id,
            submission=submission,
        )
        outcome = apply_modelo_edit(
            apply_request,
            now=datetime.now(UTC),
            result_destination=f"modelo/{baseline.modelo}/{baseline.filing_year}/{baseline.period}/edit-result",
        )
        if isinstance(outcome, ModeloEditExecutionNoEffectV1):
            # A failed compare-and-swap changed nothing, and NONE is the
            # truthful report of that -- distinct from the UNKNOWN carried
            # while the outcome was still open.
            await context.events.effect(OperationEffect.NONE)
            return None
        await context.events.effect(OperationEffect.UPDATED)
        return str(outcome.receipt.receipt_id)


def build_modelo_edit_apply_definition() -> OperationDefinition:
    """Bind the Edit Contract's guarded apply path to its registered operation contract."""

    def build() -> ModeloEditApplyExecutor:
        return ModeloEditApplyExecutor()

    return OperationDefinition(
        definition_id=MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
        request_type=ModeloEditApplyOperationRequestV1,
        result_type=ModeloEditApplyPublicResultV1,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloEditApplyOperationRequestV1,
            executor_type=ModeloEditApplyExecutor,
            build=build,
        ),
        phase_codes=("modelo.edit.apply",),
        interaction_kinds=frozenset({OperationInteractionKind.INPUT}),
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
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
        transient_financial_operands=(_MODELO_EDIT_MANUAL_OVERRIDE_OPERAND,),
    )


def build_modelo_edit_apply_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the edit-apply definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.edit.apply.request",
            schema_version=1,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.edit.apply.result",
            schema_version=1,
            model_type=ModeloEditApplyPublicResultV1,
        ),
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
    )


def build_modelo_work_rename_definition() -> OperationDefinition:
    """Bind the rename writer to its registered operation contract."""

    def build() -> ModeloWorkRenameExecutor:
        return ModeloWorkRenameExecutor()

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
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
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
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
    )


__all__ = [
    "MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID",
    "MODELO_EXPORT_OPERATION_DEFINITION_ID",
    "MODELO_WORK_AMEND_OPERATION_DEFINITION_ID",
    "MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID",
    "MODELO_WORK_FILE_OPERATION_DEFINITION_ID",
    "MODELO_WORK_RENAME_OPERATION_DEFINITION_ID",
    "MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID",
    "MODELO_WORK_VERIFY_PROGRESS_UNIT",
    "ModeloEditApplyExecutor",
    "ModeloEditApplyOperationRequestV1",
    "ModeloEditApplyPublicResultV1",
    "ModeloExportExecutor",
    "ModeloExportPublicResultV1",
    "ModeloExportRequest",
    "ModeloWorkAmendBaseline",
    "ModeloWorkAmendExecutor",
    "ModeloWorkAmendOverride",
    "ModeloWorkAmendPublicResultV1",
    "ModeloWorkAmendRequest",
    "ModeloWorkDiscardApprovalStaleError",
    "ModeloWorkDiscardBaseline",
    "ModeloWorkDiscardExecutor",
    "ModeloWorkDiscardPublicResultV1",
    "ModeloWorkDiscardRequest",
    "ModeloWorkFileApproval",
    "ModeloWorkFileExecutor",
    "ModeloWorkFilePublicResultV1",
    "ModeloWorkFileRequest",
    "ModeloWorkRenameExecutor",
    "ModeloWorkRenamePublicResultV1",
    "ModeloWorkRenameRequest",
    "ModeloWorkVerifyExecutor",
    "ModeloWorkVerifyPublicResultV1",
    "ModeloWorkVerifyRequest",
    "build_modelo_edit_apply_definition",
    "build_modelo_edit_apply_registration",
    "build_modelo_export_definition",
    "build_modelo_export_registration",
    "build_modelo_lifecycle_operation_definitions",
    "build_modelo_lifecycle_operation_registrations",
    "build_modelo_work_amend_definition",
    "build_modelo_work_amend_registration",
    "build_modelo_work_discard_definition",
    "build_modelo_work_discard_registration",
    "build_modelo_work_file_definition",
    "build_modelo_work_file_registration",
    "build_modelo_work_rename_definition",
    "build_modelo_work_rename_registration",
    "build_modelo_work_verify_definition",
    "build_modelo_work_verify_registration",
    "project_modelo_edit_apply_result",
    "project_modelo_export_result",
    "project_modelo_work_verify_result",
]


def build_modelo_lifecycle_operation_definitions() -> tuple[OperationDefinition, ...]:
    """Return the one canonical modelo lifecycle operation population.

    Every definition this module exports belongs here. A definition that is
    exported and never composed is capacity nothing can reach, which is the
    shape this population exists to make impossible to ship.
    """
    return (
        build_modelo_edit_apply_definition(),
        build_modelo_export_definition(),
        build_modelo_work_amend_definition(),
        build_modelo_work_discard_definition(),
        build_modelo_work_file_definition(),
        build_modelo_work_rename_definition(),
        build_modelo_work_verify_definition(),
    )


def build_modelo_lifecycle_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind each lifecycle definition to its stable public schemas."""
    builders = {
        MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID: build_modelo_edit_apply_registration,
        MODELO_EXPORT_OPERATION_DEFINITION_ID: build_modelo_export_registration,
        MODELO_WORK_AMEND_OPERATION_DEFINITION_ID: build_modelo_work_amend_registration,
        MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID: build_modelo_work_discard_registration,
        MODELO_WORK_FILE_OPERATION_DEFINITION_ID: build_modelo_work_file_registration,
        MODELO_WORK_RENAME_OPERATION_DEFINITION_ID: build_modelo_work_rename_registration,
        MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID: build_modelo_work_verify_registration,
    }
    return tuple(builders[definition.definition_id](definition) for definition in definitions)
