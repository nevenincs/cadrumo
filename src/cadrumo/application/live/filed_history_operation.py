"""Recorded supervision for the canonical filed-history pull composition."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ...core import FiledHistoryDiscoverySignal, RegisterScopingSignal
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.identity import AeatExpedienteId
from ...core.json_contract import Notice, NoticeSeverity
from ...core.time import now
from ...domain.deadlines.models import TaxpayerProfile
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationEventEmitter, OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..storage.sync_runs import SyncRunRecordReference, SyncRunRecordRepositoryProtocol
from .filed_data_capture import (
    FILED_HISTORY_DECLARATION_PROGRESS_UNIT,
    FILED_HISTORY_DECLARATION_REFUSAL_CODE,
    FILED_HISTORY_DISCOVERY_REFUSAL_CODE,
    FILED_HISTORY_IVA_WALLET_REFUSAL_CODE,
    FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE,
    FILED_HISTORY_PAIR_PROGRESS_UNIT,
    FILED_HISTORY_PAIR_REFUSAL_CODE,
    FILED_HISTORY_PHASE_DECLARATION_CAPTURE,
    FILED_HISTORY_PHASE_DISCOVERY,
    FILED_HISTORY_PHASE_FINALIZATION,
    FILED_HISTORY_PHASE_IVA_WALLET,
    FILED_HISTORY_PHASE_NOTIFICATIONS,
    FILED_HISTORY_PHASE_PAIR_WALK,
    FILED_HISTORY_PHASE_PERSISTENCE,
    FILED_HISTORY_PHASE_PROVENANCE,
    FILED_HISTORY_PHASE_REGISTER_ACCESS,
    FILED_HISTORY_STAGE_REFUSAL_CODE,
    FiledHistoryOnboardingRun,
    FiledHistoryPairOutcome,
    FiledPeriodSelectionRow,
    pull_filed_history,
)

FILED_HISTORY_OPERATION_DEFINITION_ID = "live.filed-history.pull"
FILED_HISTORY_PHASE_PREFLIGHT = "filed-history.preflight"
FILED_HISTORY_PHASE_EXECUTION = "filed-history.execution"
FILED_HISTORY_PHASE_RESULT = "filed-history.result"
FILED_HISTORY_PHASE_CLEANUP = "filed-history.cleanup"
FILED_HISTORY_PHASE_SETTLEMENT = "filed-history.settlement"
_FILED_HISTORY_PHASES = (
    FILED_HISTORY_PHASE_PREFLIGHT,
    FILED_HISTORY_PHASE_EXECUTION,
    FILED_HISTORY_PHASE_DISCOVERY,
    FILED_HISTORY_PHASE_REGISTER_ACCESS,
    FILED_HISTORY_PHASE_PAIR_WALK,
    FILED_HISTORY_PHASE_DECLARATION_CAPTURE,
    FILED_HISTORY_PHASE_PERSISTENCE,
    FILED_HISTORY_PHASE_FINALIZATION,
    FILED_HISTORY_PHASE_PROVENANCE,
    FILED_HISTORY_PHASE_IVA_WALLET,
    FILED_HISTORY_PHASE_NOTIFICATIONS,
    FILED_HISTORY_PHASE_RESULT,
    FILED_HISTORY_PHASE_CLEANUP,
    FILED_HISTORY_PHASE_SETTLEMENT,
)


class FiledHistoryOperationRequest(BaseModel):
    """Immutable scope submitted to one recorded filed-history pull."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    output_root: Path
    today: date | None = None
    limit: int | None = Field(default=None, ge=1)
    dry_run: bool = False


type FiledHistoryPull = Callable[
    [
        FiledHistoryOperationRequest,
        TaxpayerProfile | None,
        SyncRunRecordRepositoryProtocol,
        OperationEventEmitter,
    ],
    Awaitable[FiledHistoryOnboardingRun],
]
type FiledHistoryProfileResolver = Callable[[], TaxpayerProfile | None]
type FiledHistorySyncRunRepositoryFactory = Callable[[], SyncRunRecordRepositoryProtocol]


def _resolve_active_filed_history_profile() -> TaxpayerProfile | None:
    """Load the selected profile through its canonical internal projection."""
    from ..wizard.status import WizardStatusError, load_active_taxpayer_profile
    from ..workflow.persistence import workflow_state_repository

    try:
        return load_active_taxpayer_profile(workflow_state_repository().load())
    except WizardStatusError:
        # Filed history still has a truthful AEAT register-options path when the
        # active profile has not declared sufficient taxpayer facts yet.
        return None


async def _pull_recorded_filed_history(
    payload: FiledHistoryOperationRequest,
    profile: TaxpayerProfile | None,
    repository: SyncRunRecordRepositoryProtocol,
    events: OperationEventEmitter,
) -> FiledHistoryOnboardingRun:
    """Delegate every domain stage and write to the existing composition."""
    return await pull_filed_history(
        output_root=payload.output_root,
        profile=profile,
        today=payload.today,
        limit=payload.limit,
        dry_run=payload.dry_run,
        sync_run_repository=repository,
        events=events,
    )


def _settled_effect(run: FiledHistoryOnboardingRun) -> OperationEffect:
    """Classify only effects the canonical result proves were committed."""
    if run.dry_run:
        return OperationEffect.NONE
    failures = bool(run.refused_pairs or run.stage_failures)
    committed = bool(
        run.sync_run_ref
        or run.captured_count
        or run.genuinely_empty_pairs
        or run.iva_wallet_status == "reconciled"
        or run.notificaciones_status == "captured"
    )
    if committed:
        return OperationEffect.PARTIAL if failures else OperationEffect.UPDATED
    return OperationEffect.NONE


async def _settlement_reference(
    run: FiledHistoryOnboardingRun,
    context: OperationExecutorContext,
) -> str:
    """Persist the full settled result and return its content reference.

    Always stores through the secure operand port, rather than substituting
    the encrypted child's own key when one exists: a result reference that
    sometimes names a sync-run record and sometimes names a stored operand
    cannot be resolved through one typed public door. Child provenance
    (``sync_run_ref``) is preserved -- it travels as a field on
    :class:`FiledHistoryPublicResultV1`, not as the top-level reference.
    """
    return await context.operands.put(run, written_at=now())


class FiledHistoryEvidenceNoticeV1(BaseModel):
    """Safe public projection of one operator-facing :class:`Notice`.

    A narrower sibling of :class:`~core.json_contract.Notice`, not that type
    itself: the operations public-schema contract rejects any model whose
    graph carries a custom serializer (``Notice.context`` declares one), and
    this operation's notices never carry an executable ``action`` in
    practice, so this projection omits that field entirely rather than
    smuggling the incompatible type through under another name.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    severity: NoticeSeverity
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    context: tuple[tuple[str, str], ...] | None = None


def _project_evidence_notice(notice: Notice) -> FiledHistoryEvidenceNoticeV1:
    """Drop the action projection this operation's notices never carry."""
    return FiledHistoryEvidenceNoticeV1(
        severity=notice.severity,
        code=notice.code,
        message=notice.message,
        context=None if notice.context is None else tuple(sorted(notice.context.items())),
    )


class FiledHistoryPairOutcomePublicV1(BaseModel):
    """Safe public projection of one walked modelo/ejercicio pair outcome.

    A distinct sibling of :class:`FiledHistoryPairOutcome`, not that type
    itself: the private row's shared ``STRICT_FROZEN_CONFIG`` does not set
    ``validate_default=True``, which the operations public-schema contract
    requires, and that shared constant is not this Step's to widen.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    modelo: str = Field(min_length=1, max_length=8)
    ejercicio: FilingYear
    signals: tuple[FiledHistoryDiscoverySignal, ...] = Field(min_length=1)
    row_count: int = Field(ge=0)
    captured_count: int = Field(ge=0)
    refused: bool
    failure_type: str | None = Field(default=None, min_length=1, max_length=128)
    failure_message: str | None = Field(default=None, min_length=1, max_length=2048)


def _project_pair_outcome(pair: FiledHistoryPairOutcome) -> FiledHistoryPairOutcomePublicV1:
    return FiledHistoryPairOutcomePublicV1(
        modelo=pair.modelo,
        ejercicio=pair.ejercicio,
        signals=pair.signals,
        row_count=pair.row_count,
        captured_count=pair.captured_count,
        refused=pair.refused,
        failure_type=pair.failure_type,
        failure_message=pair.failure_message,
    )


class FiledPeriodSelectionPublicRowV1(BaseModel):
    """Safe public projection of one period's register-versus-kept row count."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    modelo: str = Field(min_length=1, max_length=8)
    ejercicio: FilingYear
    period: str = Field(min_length=1, max_length=8)
    raw_row_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    winning_expediente_id: AeatExpedienteId | None = None


def _project_selection_row(row: FiledPeriodSelectionRow) -> FiledPeriodSelectionPublicRowV1:
    return FiledPeriodSelectionPublicRowV1(
        modelo=row.modelo,
        ejercicio=row.ejercicio,
        period=row.period,
        raw_row_count=row.raw_row_count,
        selected_count=row.selected_count,
        winning_expediente_id=row.winning_expediente_id,
    )


class FiledHistoryPublicResultV1(BaseModel):
    """Safe public projection of one settled :class:`FiledHistoryOnboardingRun`.

    A distinct type from the private result, not a passthrough: every field
    is independently declared here, so the public contract's shape is owned
    by this module rather than mirrored from the private one it happens to
    resemble today.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    dry_run: bool
    captured_count: int = Field(ge=0)
    reached_count: int = Field(ge=0)
    scoping_signal: RegisterScopingSignal
    carries_a_taxpayer_specific_denominator: bool
    denominator_note: str
    iva_wallet_status: str = Field(min_length=1, max_length=64)
    iva_wallet_divergence: str | None = Field(default=None, min_length=1, max_length=64)
    iva_wallet_blocked: bool
    notificaciones_status: str = Field(min_length=1, max_length=64)
    notificaciones_row_count: int = Field(ge=0)
    stage_failures: tuple[str, ...]
    sync_run_ref: SyncRunRecordReference | None
    evidence_notices: tuple[FiledHistoryEvidenceNoticeV1, ...]
    recapture_notices: tuple[FiledHistoryEvidenceNoticeV1, ...]
    pairs: tuple[FiledHistoryPairOutcomePublicV1, ...]
    selection_rows: tuple[FiledPeriodSelectionPublicRowV1, ...]


def _project_filed_history_result(
    result: BaseModel,
    terminal_receipt: OperationTerminalReceipt,
) -> BaseModel:
    """Project the settled run into its safe public result -- never itself."""
    del terminal_receipt
    run = FiledHistoryOnboardingRun.model_validate(result, strict=True)
    return FiledHistoryPublicResultV1(
        dry_run=run.dry_run,
        captured_count=run.captured_count,
        reached_count=run.reached_count,
        scoping_signal=run.scoping_signal,
        carries_a_taxpayer_specific_denominator=run.carries_a_taxpayer_specific_denominator,
        denominator_note=run.denominator_note,
        iva_wallet_status=run.iva_wallet_status,
        iva_wallet_divergence=run.iva_wallet_divergence,
        iva_wallet_blocked=run.iva_wallet_blocked,
        notificaciones_status=run.notificaciones_status,
        notificaciones_row_count=run.notificaciones_row_count,
        stage_failures=run.stage_failures,
        sync_run_ref=run.sync_run_ref,
        evidence_notices=tuple(_project_evidence_notice(notice) for notice in run.evidence_notices),
        recapture_notices=tuple(_project_evidence_notice(notice) for notice in run.recapture_notices),
        pairs=tuple(_project_pair_outcome(pair) for pair in run.pairs),
        selection_rows=tuple(_project_selection_row(row) for row in run.selection_rows),
    )


class FiledHistoryOperationExecutor:
    """Run the existing filed-history service under one recorded identity."""

    def __init__(
        self,
        *,
        sync_run_repository: SyncRunRecordRepositoryProtocol,
        pull: FiledHistoryPull = _pull_recorded_filed_history,
        profile_resolver: FiledHistoryProfileResolver = _resolve_active_filed_history_profile,
    ) -> None:
        """Initialize this public contract."""
        self._sync_run_repository = sync_run_repository
        self._pull = pull
        self._profile_resolver = profile_resolver

    async def execute(
        self,
        request: OperationRequest[FiledHistoryOperationRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Execute this public contract operation."""
        if require_active_bucket_id() != request.subject_ref:
            raise ValueError("filed-history operation subject must identify the active profile")
        profile = self._profile_resolver()
        await context.events.phase(FILED_HISTORY_PHASE_PREFLIGHT)
        await context.events.phase(FILED_HISTORY_PHASE_EXECUTION)
        # The delegated service contains several atomic secure writes. Until it
        # returns its typed accounting, an unexpected interruption cannot prove
        # whether none or some of those writes committed.
        if not request.payload.dry_run:
            await context.events.effect(OperationEffect.UNKNOWN)
        run = await self._pull(request.payload, profile, self._sync_run_repository, context.events)
        await context.events.phase(FILED_HISTORY_PHASE_RESULT)
        await context.events.phase(FILED_HISTORY_PHASE_CLEANUP)
        await context.events.effect(_settled_effect(run))
        await context.events.phase(FILED_HISTORY_PHASE_SETTLEMENT)
        return await _settlement_reference(run, context)


def build_filed_history_operation_definition(
    *,
    sync_run_repository_factory: FiledHistorySyncRunRepositoryFactory,
    pull: FiledHistoryPull = _pull_recorded_filed_history,
    profile_resolver: FiledHistoryProfileResolver = _resolve_active_filed_history_profile,
) -> OperationDefinition:
    """Bind entrypoint-owned persistence to the canonical operation contract."""

    def build() -> FiledHistoryOperationExecutor:
        return FiledHistoryOperationExecutor(
            sync_run_repository=sync_run_repository_factory(),
            pull=pull,
            profile_resolver=profile_resolver,
        )

    return OperationDefinition(
        definition_id=FILED_HISTORY_OPERATION_DEFINITION_ID,
        request_type=FiledHistoryOperationRequest,
        result_type=FiledHistoryOnboardingRun,
        executor_factory=OperationExecutorFactory(
            request_type=FiledHistoryOperationRequest,
            executor_type=FiledHistoryOperationExecutor,
            build=build,
        ),
        phase_codes=_FILED_HISTORY_PHASES,
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset(
                {
                    OperationEffect.NONE,
                    OperationEffect.UPDATED,
                    OperationEffect.PARTIAL,
                    OperationEffect.UNKNOWN,
                }
            ),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.MCP, OperationFrontendProjection.TUI}
        ),
    )


def build_filed_history_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the filed-history definition to its stable public schemas.

    The public result schema is :class:`FiledHistoryPublicResultV1`, a
    distinct projection resolved through the registered result projector --
    never the private :class:`FiledHistoryOnboardingRun` itself.
    """
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="live.filed-history.pull.request",
            schema_version=1,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="live.filed-history.pull.result",
            schema_version=1,
            model_type=FiledHistoryPublicResultV1,
        ),
        result_projector=_project_filed_history_result,
    )


__all__ = [
    "FILED_HISTORY_DECLARATION_PROGRESS_UNIT",
    "FILED_HISTORY_DECLARATION_REFUSAL_CODE",
    "FILED_HISTORY_DISCOVERY_REFUSAL_CODE",
    "FILED_HISTORY_IVA_WALLET_REFUSAL_CODE",
    "FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE",
    "FILED_HISTORY_OPERATION_DEFINITION_ID",
    "FILED_HISTORY_PAIR_PROGRESS_UNIT",
    "FILED_HISTORY_PAIR_REFUSAL_CODE",
    "FILED_HISTORY_PHASE_CLEANUP",
    "FILED_HISTORY_PHASE_DECLARATION_CAPTURE",
    "FILED_HISTORY_PHASE_DISCOVERY",
    "FILED_HISTORY_PHASE_EXECUTION",
    "FILED_HISTORY_PHASE_FINALIZATION",
    "FILED_HISTORY_PHASE_IVA_WALLET",
    "FILED_HISTORY_PHASE_NOTIFICATIONS",
    "FILED_HISTORY_PHASE_PAIR_WALK",
    "FILED_HISTORY_PHASE_PERSISTENCE",
    "FILED_HISTORY_PHASE_PREFLIGHT",
    "FILED_HISTORY_PHASE_PROVENANCE",
    "FILED_HISTORY_PHASE_REGISTER_ACCESS",
    "FILED_HISTORY_PHASE_RESULT",
    "FILED_HISTORY_PHASE_SETTLEMENT",
    "FILED_HISTORY_STAGE_REFUSAL_CODE",
    "FiledHistoryEvidenceNoticeV1",
    "FiledHistoryOperationExecutor",
    "FiledHistoryOperationRequest",
    "FiledHistoryPairOutcomePublicV1",
    "FiledHistoryPublicResultV1",
    "FiledHistoryPull",
    "FiledHistorySyncRunRepositoryFactory",
    "FiledPeriodSelectionPublicRowV1",
    "build_filed_history_operation_definition",
    "build_filed_history_operation_registration",
]
