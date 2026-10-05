"""Recorded supervision for the canonical filed-history pull composition.

Core types:
:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
from datetime import date
from pathlib import Path
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from ...core.bucket_pointer import require_active_bucket_id
from ...core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from ...core.filing_year import FilingYear
from ...core.identity.profile import canonical_profile_bucket_id
from ...core.json_contract import Notice, NoticeSeverity
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.register_scoping_signal import RegisterScopingSignal
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.deadlines.models import TaxpayerProfile
from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
from ..auth.operator_scope_ports import OperatorScopePorts
from ..auth.protocols import BrowserSessionFactoryPort
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition
from ..operations.owner import OperationEventEmitter, OperationExecutorContext, retain_failed_operation_resources
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from ..operator_actions.models import ActionReference
from ..storage.sync_runs.records import SyncRunRecordReference, SyncRunRecordRepositoryProtocol
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_data_ports import FiledDataCapturePort, FiledEffectGuard
from .filed_history_discovery import FiledHistoryOnboardingRun, FiledHistoryPairOutcome
from .filed_history_events import (
    FILED_HISTORY_PHASE_DECLARATION_CAPTURE,
    FILED_HISTORY_PHASE_DISCOVERY,
    FILED_HISTORY_PHASE_FINALIZATION,
    FILED_HISTORY_PHASE_IVA_WALLET,
    FILED_HISTORY_PHASE_NOTIFICATIONS,
    FILED_HISTORY_PHASE_PAIR_WALK,
    FILED_HISTORY_PHASE_PERSISTENCE,
    FILED_HISTORY_PHASE_PROVENANCE,
    FILED_HISTORY_PHASE_REGISTER_ACCESS,
    FiledHistoryEventSink,
)
from .filed_history_pull import pull_filed_history
from .filed_observation_ports import FiledObservationPersistencePorts
from .iva_remote_state_ports import IvaRemoteStatePort
from .live_operation_registration import build_live_operation_definition, resolve_whole_profile_capture_access
from .notification_ports import NotificationsPorts
from .session import LiveSessionWriteReceipt, SessionWriteReporter

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

    profile_id: UUID
    output_root: Path
    today: date | None = None
    limit: int | None = Field(default=None, ge=1)
    dry_run: bool = False


class FiledHistoryComposition(Protocol):
    """Outer-composed dependencies for one filed-history operation scope."""

    @property
    def ports(self) -> FiledObservationPersistencePorts:
        """Return the immutable filed-observation persistence bundle."""
        ...

    @property
    def iva_remote_state_port(self) -> IvaRemoteStatePort:
        """Return the composed IVA remote-state application port."""
        ...

    @property
    def notifications_ports(self) -> NotificationsPorts:
        """Return the composed notifications query/persistence bundle."""
        ...

    @property
    def filed_data_port(self) -> FiledDataCapturePort:
        """Return the composed filed-data acquisition port."""
        ...

    @property
    def certificate_secret_backend_factory(self) -> CertificateSecretBackendFactory:
        """Return the composed certificate-secret capability factory."""
        ...

    @property
    def browser_session_factory(self) -> BrowserSessionFactoryPort:
        """Return the composed browser-session capability factory."""
        ...

    @property
    def operator_scope_ports(self) -> OperatorScopePorts:
        """Return the composed operator-auth storage-scope capability."""
        ...


type FiledHistoryPull = Callable[
    [
        FiledHistoryOperationRequest,
        TaxpayerProfile | None,
        SyncRunRecordRepositoryProtocol,
        OperationEventEmitter,
        FiledObservationPersistencePorts,
        FiledDataCapturePort,
        IvaRemoteStatePort,
        NotificationsPorts,
        CertificateSecretBackendFactory,
        BrowserSessionFactoryPort,
        OperatorScopePorts,
        FiledEffectGuard,
        SessionWriteReporter,
    ],
    Awaitable[FiledHistoryOnboardingRun],
]


class SharedFiledHistoryPull(Protocol):
    """Positional contract of a composition-owned filed-history pull callback.

    The composing entrypoint supplies its shared pull through this contract and
    :func:`bind_shared_filed_history_pull` adapts it to :data:`FiledHistoryPull`,
    so the entrypoint never depends on the executor-owned emitter contract.
    """

    def __call__(
        self,
        payload: FiledHistoryOperationRequest,
        profile: TaxpayerProfile | None,
        repository: SyncRunRecordRepositoryProtocol | None,
        events: FiledHistoryEventSink | None,
        ports: FiledObservationPersistencePorts,
        filed_data_port: FiledDataCapturePort,
        iva_remote_state_port: IvaRemoteStatePort,
        notifications_ports: NotificationsPorts,
        certificate_secret_backend_factory: CertificateSecretBackendFactory,
        browser_session_factory: BrowserSessionFactoryPort,
        operator_scope_ports: OperatorScopePorts,
        effect_guard: FiledEffectGuard,
        on_session_write: SessionWriteReporter,
        /,
    ) -> Awaitable[object]:
        """Run one filed-history pull with the supplied composed dependencies."""
        ...


def bind_shared_filed_history_pull(shared_pull: SharedFiledHistoryPull) -> FiledHistoryPull:
    """Adapt a shared composition callback to the operation's typed pull contract.

    The submitted request already carries the payload fields the shared pull
    reads, so it is forwarded unchanged; a result other than the canonical
    :class:`FiledHistoryOnboardingRun` is refused rather than settled.
    """

    async def pull(
        payload: FiledHistoryOperationRequest,
        profile: TaxpayerProfile | None,
        repository: SyncRunRecordRepositoryProtocol,
        events: OperationEventEmitter,
        ports: FiledObservationPersistencePorts,
        filed_data_port: FiledDataCapturePort,
        iva_remote_state_port: IvaRemoteStatePort,
        notifications_ports: NotificationsPorts,
        certificate_secret_backend_factory: CertificateSecretBackendFactory,
        browser_session_factory: BrowserSessionFactoryPort,
        operator_scope_ports: OperatorScopePorts,
        effect_guard: FiledEffectGuard,
        on_session_write: SessionWriteReporter,
    ) -> FiledHistoryOnboardingRun:
        result = await shared_pull(
            payload,
            profile,
            repository,
            events,
            ports,
            filed_data_port,
            iva_remote_state_port,
            notifications_ports,
            certificate_secret_backend_factory,
            browser_session_factory,
            operator_scope_ports,
            effect_guard,
            on_session_write,
        )
        if not isinstance(result, FiledHistoryOnboardingRun):
            raise TypeError("shared filed-history composition returned an invalid result")
        return result

    return pull


type FiledHistoryProfileResolver = Callable[[PinnedAuthorityOperation], TaxpayerProfile | None]
type FiledHistorySyncRunRepositoryFactory = Callable[[], SyncRunRecordRepositoryProtocol]


class FiledHistoryCompositionFactory(Protocol):
    """Compose one live-state bundle under the operation's held authority pin."""

    def __call__(self, output_root: Path, *, operation: PinnedAuthorityOperation) -> FiledHistoryComposition:
        """Return all filed-history persistence and live-state ports for this operation."""
        ...


type FiledHistoryProviderPreflight = Callable[[UUID, PinnedAuthorityOperation], None]


class FiledHistoryBrowserResources(Protocol):
    """Operation-owned browser subprocess cleanup with a scoped launch context."""

    def activate(self) -> AbstractContextManager[None]:
        """Attribute Playwright runtimes created in this execution to the owner."""
        ...

    async def close(self) -> None:
        """Settle every browser process before the operation becomes terminal."""
        ...


type FiledHistoryBrowserResourcesFactory = Callable[[], FiledHistoryBrowserResources]


def _unconfigured_provider_preflight(profile_id: UUID, operation: PinnedAuthorityOperation) -> None:
    del profile_id, operation
    raise ProfileAccessRefusedError(AccessDenialCode.PROVIDER_REQUIRED)


def _resolve_active_filed_history_profile(operation: PinnedAuthorityOperation) -> TaxpayerProfile | None:
    """Load the selected profile through its canonical internal projection."""
    from ..wizard.status import WizardStatusError, load_active_taxpayer_profile
    from ..workflow.persistence import workflow_state_repository

    try:
        return load_active_taxpayer_profile(workflow_state_repository().load(), schema=operation.profile_schema())
    except WizardStatusError:
        # Filed history still has a truthful AEAT register-options path when the
        # active profile has not declared sufficient taxpayer facts yet.
        return None


async def _pull_recorded_filed_history(
    payload: FiledHistoryOperationRequest,
    profile: TaxpayerProfile | None,
    repository: SyncRunRecordRepositoryProtocol,
    events: OperationEventEmitter,
    ports: FiledObservationPersistencePorts,
    filed_data_port: FiledDataCapturePort,
    iva_remote_state_port: IvaRemoteStatePort,
    notifications_ports: NotificationsPorts,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
    effect_guard: FiledEffectGuard,
    on_session_write: SessionWriteReporter,
) -> FiledHistoryOnboardingRun:
    """Delegate every domain stage and write to the existing composition."""
    return await pull_filed_history(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        browser_session_factory=browser_session_factory,
        operator_scope_ports=operator_scope_ports,
        filed_data_port=filed_data_port,
        iva_remote_state_port=iva_remote_state_port,
        notifications_ports=notifications_ports,
        ports=ports,
        output_root=payload.output_root,
        profile=profile,
        today=payload.today,
        limit=payload.limit,
        dry_run=payload.dry_run,
        sync_run_repository=repository,
        events=events,
        effect_guard=effect_guard,
        on_session_write=on_session_write,
    )


def settled_filed_history_effect(run: FiledHistoryOnboardingRun) -> OperationEffect:
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
    async with context.cancellation.irreversible_section():
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
    walk_attempted: bool
    walk_completed: bool
    row_count: NonNegativeInt
    reached_count: NonNegativeInt
    captured_count: NonNegativeInt
    refused: bool
    failure_type: str | None = Field(default=None, min_length=1, max_length=128)
    failure_message: str | None = Field(default=None, min_length=1, max_length=2048)


def _project_pair_outcome(pair: FiledHistoryPairOutcome) -> FiledHistoryPairOutcomePublicV1:
    pair.require_consistent()
    return FiledHistoryPairOutcomePublicV1(
        modelo=pair.modelo,
        ejercicio=pair.ejercicio,
        signals=pair.signals,
        walk_attempted=pair.walk_attempted,
        walk_completed=pair.walk_completed,
        row_count=pair.row_count,
        reached_count=pair.reached_count,
        captured_count=pair.captured_count,
        refused=pair.refused,
        failure_type=pair.failure_type,
        failure_message=pair.failure_message,
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
    captured_count: NonNegativeInt
    reached_count: NonNegativeInt
    scoping_signal: RegisterScopingSignal
    carries_a_taxpayer_specific_denominator: bool
    denominator_note: str
    iva_wallet_status: str = Field(min_length=1, max_length=64)
    iva_wallet_divergence: str | None = Field(default=None, min_length=1, max_length=64)
    iva_wallet_blocked: bool
    notificaciones_status: str = Field(min_length=1, max_length=64)
    notificaciones_row_count: NonNegativeInt
    stage_failures: tuple[str, ...]
    sync_run_ref: SyncRunRecordReference | None
    evidence_notices: tuple[FiledHistoryEvidenceNoticeV1, ...]
    recapture_notices: tuple[FiledHistoryEvidenceNoticeV1, ...]
    pairs: tuple[FiledHistoryPairOutcomePublicV1, ...]


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
    )


class FiledHistoryOperationExecutor:
    """Run the existing filed-history service under one recorded identity."""

    def __init__(
        self,
        *,
        sync_run_repository: SyncRunRecordRepositoryProtocol,
        composition_factory: FiledHistoryCompositionFactory,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        pull: FiledHistoryPull = _pull_recorded_filed_history,
        profile_resolver: FiledHistoryProfileResolver = _resolve_active_filed_history_profile,
        provider_preflight: FiledHistoryProviderPreflight = _unconfigured_provider_preflight,
    ) -> None:
        """Initialize this public contract."""
        self._sync_run_repository = sync_run_repository
        self._composition_factory = composition_factory
        self._browser_resources_factory = browser_resources_factory
        self._pull = pull
        self._profile_resolver = profile_resolver
        self._provider_preflight = provider_preflight

    async def execute(
        self,
        request: OperationRequest[FiledHistoryOperationRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Execute this public contract operation."""
        profile_id = canonical_profile_bucket_id(request.payload.profile_id)
        if require_active_bucket_id() != profile_id or request.subject_ref != profile_operation_subject(profile_id):
            raise ValueError("filed-history operation subject must identify the active profile")
        await context.events.phase(FILED_HISTORY_PHASE_PREFLIGHT)
        self._provider_preflight(request.payload.profile_id, context.authority_operation)
        profile = self._profile_resolver(context.authority_operation)
        await context.events.phase(FILED_HISTORY_PHASE_EXECUTION)
        # The delegated service contains several atomic secure writes. Until it
        # returns its typed accounting, an unexpected interruption cannot prove
        # whether none or some of those writes committed.
        if not request.payload.dry_run:
            await context.events.effect(OperationEffect.UNKNOWN)
        composition = self._composition_factory(request.payload.output_root, operation=context.authority_operation)
        browser_resources = self._browser_resources_factory()
        context.cleanup.own(browser_resources, family=OperationOwnedResource.PROCESS)
        session_receipt = LiveSessionWriteReceipt(context.events.effect)
        with (
            retain_failed_operation_resources(context.cleanup, family=OperationOwnedResource.PROCESS),
            browser_resources.activate(),
        ):
            run = await self._pull(
                request.payload,
                profile,
                self._sync_run_repository,
                context.events,
                composition.ports,
                composition.filed_data_port,
                composition.iva_remote_state_port,
                composition.notifications_ports,
                composition.certificate_secret_backend_factory,
                composition.browser_session_factory,
                composition.operator_scope_ports,
                context.cancellation.irreversible_section,
                session_receipt,
            )
        await context.events.phase(FILED_HISTORY_PHASE_RESULT)
        await context.events.phase(FILED_HISTORY_PHASE_CLEANUP)
        await context.events.effect(session_receipt.combine(settled_filed_history_effect(run)))
        await context.events.phase(FILED_HISTORY_PHASE_SETTLEMENT)
        return await _settlement_reference(run, context)


def build_filed_history_operation_definition(
    *,
    sync_run_repository_factory: FiledHistorySyncRunRepositoryFactory,
    composition_factory: FiledHistoryCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    pull: FiledHistoryPull = _pull_recorded_filed_history,
    profile_resolver: FiledHistoryProfileResolver = _resolve_active_filed_history_profile,
    provider_preflight: FiledHistoryProviderPreflight = _unconfigured_provider_preflight,
) -> OperationDefinition:
    """Bind entrypoint-owned persistence to the canonical operation contract."""

    def build() -> FiledHistoryOperationExecutor:
        return FiledHistoryOperationExecutor(
            sync_run_repository=sync_run_repository_factory(),
            composition_factory=composition_factory,
            browser_resources_factory=browser_resources_factory,
            pull=pull,
            profile_resolver=profile_resolver,
            provider_preflight=provider_preflight,
        )

    return build_live_operation_definition(
        definition_id=FILED_HISTORY_OPERATION_DEFINITION_ID,
        request_type=FiledHistoryOperationRequest,
        result_type=FiledHistoryOnboardingRun,
        executor_type=FiledHistoryOperationExecutor,
        build=build,
        phase_codes=_FILED_HISTORY_PHASES,
        action_reference=ActionReference(
            action_id=OPERATOR_ACTION_CATALOGUE.lookup("operator.live.filed.pull_all").action_id
        ),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset({OperationOwnedResource.PROCESS}),
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
    )


def resolve_filed_history_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact-profile, all-period discovery and a fresh local commit fence.

    Provider readiness is checked by the bound worker before browser I/O; the
    runtime's access policy cannot infer it from an agent request.
    """
    return resolve_whole_profile_capture_access(
        request,
        context,
        definition_id=FILED_HISTORY_OPERATION_DEFINITION_ID,
        payload_type=FiledHistoryOperationRequest,
    )


def build_filed_history_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the filed-history definition to its stable public schemas.

    The public result schema is :class:`FiledHistoryPublicResultV1`, a
    distinct projection resolved through the registered result projector --
    never the private :class:`FiledHistoryOnboardingRun` itself.
    """
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=FiledHistoryPublicResultV1,
        result_projector=_project_filed_history_result,
        access_resolver=resolve_filed_history_access,
    )


__all__ = [
    "FILED_HISTORY_OPERATION_DEFINITION_ID",
    "FILED_HISTORY_PHASE_CLEANUP",
    "FILED_HISTORY_PHASE_EXECUTION",
    "FILED_HISTORY_PHASE_PREFLIGHT",
    "FILED_HISTORY_PHASE_RESULT",
    "FILED_HISTORY_PHASE_SETTLEMENT",
    "FiledHistoryComposition",
    "FiledHistoryCompositionFactory",
    "FiledHistoryEvidenceNoticeV1",
    "FiledHistoryOperationExecutor",
    "FiledHistoryOperationRequest",
    "FiledHistoryPairOutcomePublicV1",
    "FiledHistoryProviderPreflight",
    "FiledHistoryPublicResultV1",
    "FiledHistoryPull",
    "FiledHistorySyncRunRepositoryFactory",
    "SharedFiledHistoryPull",
    "bind_shared_filed_history_pull",
    "build_filed_history_operation_definition",
    "build_filed_history_operation_registration",
    "resolve_filed_history_access",
]
