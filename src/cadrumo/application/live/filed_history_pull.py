"""Pull and reconcile the discovered filed-history grid through its staged sources."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
    from ..auth.protocols import BrowserSessionFactoryPort
    from .iva_remote_state_ports import IvaRemoteStatePort


from ...core.async_cleanup import has_async_cleanup_failure
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import InternalInvariantError
from ...core.period import Period
from ..auth.operator_scope_ports import OperatorScopePorts
from ..runtime.contracts import RuntimeRefusalError
from ..storage.sync_runs.records import (
    SyncRunRecordRepositoryProtocol,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from ..user_profile.automation_custody_port import AutomationCustodyError
from .filed_data_capture import capture_filed_data_bulk
from .filed_data_ports import (
    FiledDataCapturePort,
    FiledEffectGuard,
    LocalEffectTracker,
)
from .filed_history_discovery import (
    FiledHistoryDiscoveryPair,
    FiledHistoryDiscoveryReport,
    FiledHistoryOnboardingRun,
    FiledHistoryPairOutcome,
    discover_filed_history,
)
from .filed_history_events import (
    FILED_HISTORY_DISCOVERY_REFUSAL_CODE,
    FILED_HISTORY_IVA_WALLET_REFUSAL_CODE,
    FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE,
    FILED_HISTORY_PHASE_DISCOVERY,
    FILED_HISTORY_PHASE_IVA_WALLET,
    FILED_HISTORY_PHASE_NOTIFICATIONS,
    FiledHistoryEventSink,
    emit_filed_history_phase,
    emit_filed_history_refusal,
)
from .filed_observation_ports import FiledObservationPersistencePorts
from .notification_ports import NotificationsPorts
from .remote_state_models import (
    BulkFiledDataCaptureReport,
    FiledCapturePairOutcome,
    FiledDataCaptureFailureRow,
)
from .remote_state_outcomes import bounded_context_text
from .session import SessionWriteReporter

if TYPE_CHECKING:
    from datetime import date

    from ...domain.deadlines.models import TaxpayerProfile


class FiledHistoryDiscoveryPort(Protocol):
    """The discovery step :func:`pull_filed_history` sequences, as a port.

    Exists so the COMPOSITION can be exercised. :func:`discover_filed_history`
    brings up a verified authenticated session, and it is the composition's first
    stage, so reaching for it directly made the sequencing, the failure
    propagation and the notice plumbing unreachable without a certificate. None of
    those need AEAT — only the discovery step does — and a test whose safety
    depends on the machine having no certificate configured is not a test: on a
    box that HAS one it stops refusing and makes a real authenticated call.

    Narrow on purpose. One boundary, shaped exactly like the function it defaults
    to, rather than a general indirection layer over every stage.
    """

    async def __call__(
        self,
        *,
        filed_data_port: FiledDataCapturePort,
        profile: TaxpayerProfile | None = None,
        today: date | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> FiledHistoryDiscoveryReport: ...


def _filed_history_pair_outcomes(
    discovery: FiledHistoryDiscoveryReport,
    capture: BulkFiledDataCaptureReport,
) -> tuple[FiledHistoryPairOutcome, ...]:
    """Join the bulk capture's failure and observation facts onto every discovered pair."""
    capture.require_consistent()
    failures_by_pair: dict[tuple[str, int], FiledDataCaptureFailureRow] = {}
    for failure in capture.failures:
        failures_by_pair.setdefault((failure.modelo, failure.year), failure)
    capture_by_pair = {(pair.modelo, pair.year): pair for pair in capture.pair_outcomes}
    return tuple(_filed_history_pair_outcome(pair, failures_by_pair, capture_by_pair) for pair in discovery.pairs)


def _filed_history_pair_outcome(
    pair: FiledHistoryDiscoveryPair,
    failures_by_pair: Mapping[tuple[str, int], FiledDataCaptureFailureRow],
    capture_by_pair: Mapping[tuple[str, int], FiledCapturePairOutcome],
) -> FiledHistoryPairOutcome:
    """Project one discovery pair without conflating a typed refusal with a zero row count."""
    coordinate = (pair.modelo, pair.ejercicio)
    failure = failures_by_pair.get(coordinate)
    capture = capture_by_pair.get(coordinate)
    if capture is None:
        raise InternalInvariantError("filed-history discovery coordinate has no planned capture accounting")
    outcome = FiledHistoryPairOutcome(
        modelo=pair.modelo,
        ejercicio=pair.ejercicio,
        signals=pair.signals,
        walk_attempted=capture.walk_attempted,
        walk_completed=capture.walk_completed,
        row_count=capture.row_count,
        reached_count=capture.reached_count,
        captured_count=capture.captured_count,
        refused=failure is not None,
        failure_type=failure.error_type if failure is not None else None,
        failure_message=failure.message if failure is not None else None,
    )
    outcome.require_consistent()
    return outcome


async def _capture_discovered_filed_history(
    walk_pairs: Sequence[tuple[str, int]],
    *,
    filed_data_port: FiledDataCapturePort,
    output_root: Path,
    ports: FiledObservationPersistencePorts,
    limit: int | None,
    dry_run: bool,
    sync_run_repository: SyncRunRecordRepositoryProtocol | None,
    effect_guard: FiledEffectGuard | None = None,
    on_session_write: SessionWriteReporter | None = None,
    events: FiledHistoryEventSink | None = None,
) -> BulkFiledDataCaptureReport:
    """Capture the discovered grid with its original modelo order and year span."""
    modelos = tuple(dict.fromkeys(modelo for modelo, _year in walk_pairs))
    years = tuple(year for _modelo, year in walk_pairs)
    return await capture_filed_data_bulk(
        filed_data_port=filed_data_port,
        year_from=min(years),
        year_to=max(years),
        output_root=output_root,
        ports=ports,
        modelos=modelos,
        limit=limit,
        dry_run=dry_run,
        sync_run_repository=sync_run_repository,
        effect_guard=effect_guard,
        on_session_write=on_session_write,
        events=events,
    )


@dataclass(frozen=True, slots=True)
class _FiledHistoryIvaWalletStage:
    status: str
    divergence: str | None
    blocked: bool
    failure: str | None = None


async def _capture_filed_history_iva_wallet(
    *,
    iva_remote_state_port: IvaRemoteStatePort,
    resolved_today: date,
    output_root: Path,
    effect_guard: FiledEffectGuard | None = None,
    on_session_write: SessionWriteReporter | None = None,
    events: FiledHistoryEventSink | None = None,
) -> _FiledHistoryIvaWalletStage:
    """Capture the independent IVA wallet stage, retaining its typed partial-failure boundary."""
    tracker = LocalEffectTracker(effect_guard) if effect_guard is not None else None
    try:
        from .iva_remote_state import capture_iva_compensation_wallet

        wallet = await capture_iva_compensation_wallet(
            ports=iva_remote_state_port,
            target_year=resolved_today.year,
            target_period=Period.from_year_and_code(resolved_today.year, "1T"),
            output_root=output_root,
            effect_guard=tracker.enter if tracker is not None else None,
            on_session_write=on_session_write,
        )
    except (ProfileAccessRefusedError, AutomationCustodyError, RuntimeRefusalError):
        raise
    except Exception as exc:
        if has_async_cleanup_failure(exc) or (tracker is not None and (tracker.started or tracker.failed)):
            raise
        await emit_filed_history_refusal(events, FILED_HISTORY_IVA_WALLET_REFUSAL_CODE)
        return _FiledHistoryIvaWalletStage(
            status="failed",
            divergence=None,
            blocked=False,
            failure=f"iva_wallet: {bounded_context_text(exc)}",
        )
    return _FiledHistoryIvaWalletStage(
        status="reconciled",
        divergence=wallet.divergence,
        blocked=wallet.blocked,
    )


@dataclass(frozen=True, slots=True)
class _FiledHistoryNotificationsStage:
    status: str
    row_count: int
    failure: str | None = None


async def _capture_filed_history_notifications(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    notifications_ports: NotificationsPorts,
    operator_scope_ports: OperatorScopePorts,
    effect_guard: FiledEffectGuard | None = None,
    on_session_write: SessionWriteReporter | None = None,
    events: FiledHistoryEventSink | None = None,
) -> _FiledHistoryNotificationsStage:
    """Capture notifications without allowing an independent failure to erase filed history."""
    tracker = LocalEffectTracker(effect_guard) if effect_guard is not None else None
    try:
        from .notifications import capture_notifications

        snapshot = await capture_notifications(
            bucket_id=require_active_bucket_id(),
            ports=notifications_ports,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            browser_session_factory=browser_session_factory,
            operator_scope_ports=operator_scope_ports,
            effect_guard=tracker.enter if tracker is not None else None,
            on_session_write=on_session_write,
        )
    except (ProfileAccessRefusedError, AutomationCustodyError, RuntimeRefusalError):
        raise
    except Exception as exc:
        if has_async_cleanup_failure(exc) or (tracker is not None and (tracker.started or tracker.failed)):
            raise
        await emit_filed_history_refusal(events, FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE)
        return _FiledHistoryNotificationsStage(
            status="failed",
            row_count=0,
            failure=f"notificaciones: {bounded_context_text(exc)}",
        )
    return _FiledHistoryNotificationsStage(
        status="captured",
        row_count=len(snapshot.rows),
    )


async def pull_filed_history(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
    filed_data_port: FiledDataCapturePort,
    iva_remote_state_port: IvaRemoteStatePort,
    notifications_ports: NotificationsPorts,
    ports: FiledObservationPersistencePorts,
    output_root: Path,
    profile: TaxpayerProfile | None = None,
    today: date | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    discover: FiledHistoryDiscoveryPort = discover_filed_history,
    sync_run_repository: SyncRunRecordRepositoryProtocol | None = None,
    events: FiledHistoryEventSink | None = None,
    effect_guard: FiledEffectGuard | None = None,
    on_session_write: SessionWriteReporter | None = None,
) -> FiledHistoryOnboardingRun:
    """Sequence discovery, bulk filed capture, IVA wallet and notificaciones.

    Composes existing primitives and adds no capture mechanism of its own. In
    particular it does NOT wrap the register walk in its own error handling: the
    bulk sweep already absorbs any walk failure — including the truncated-page
    refusal — into a typed failure row and continues to the next pair. Wrapping it
    again would duplicate that authority and could swallow the very failure row
    the taxonomy exists to produce.

    Each later stage is guarded separately so a partial run reports which stage
    failed rather than collapsing into one error. That matters because these
    stages are independent: a notificaciones timeout says nothing about whether
    the filed capture succeeded, and losing the capture report to an unrelated
    failure would waste a long authenticated sweep.

    Args:
        certificate_secret_backend_factory: Creates the secure certificate-secret backend.
        browser_session_factory: Creates the authenticated browser session.
        operator_scope_ports: Operator-scope capabilities used by authenticated stages.
        iva_remote_state_port: Composed IVA wallet acquisition and persistence port.
        notifications_ports: Composed notifications query and snapshot persistence bundle.
        output_root: Root the capture writes its encrypted stores under.
        ports: Composed filed-observation persistence and transformation ports.
        profile: The taxpayer's declared :class:`TaxpayerProfile`, supplying the load-bearing
            discovery signal. ``None`` yields a run with no taxpayer-specific
            denominator, reported as such.
        today: Reference date for applicability and the year span.
        limit: Optional cap on captured declaraciones, forwarded unchanged.
        dry_run: Read the discovered filed-declaration scope without persisting
            observations, evidence, calculation observations, or a sync-run
            provenance record. IVA-wallet and notification captures are omitted
            because they are separate persisted remote-state stages.
        discover: The discovery step to sequence, defaulting to
            :func:`discover_filed_history`. Injected so the composition itself is
            reachable without an authenticated session; production never passes it.
        filed_data_port: Composed filed-data acquisition capability. The same
            bundle is used for discovery, register walks, and source capture.
        sync_run_repository: Completed-run persistence port forwarded to the
            bulk capture after discovery finds a supported pair.
        events: Optional operation event emitter that receives only stable stage
            identifiers, safe unit counters, and stable refusal scopes.
        effect_guard: Optional authorization fence around each local persisted effect.
        on_session_write: Record provider session writes from each authenticated stage.

    Returns:
        The composed :class:`FiledHistoryOnboardingRun`.
    """
    from ...core.time.clock import today_madrid

    resolved_today = today or today_madrid()
    await emit_filed_history_phase(events, FILED_HISTORY_PHASE_DISCOVERY)
    discovery = await discover(
        filed_data_port=filed_data_port,
        profile=profile,
        today=resolved_today,
        effect_guard=effect_guard,
        on_session_write=on_session_write,
    )
    walk_pairs = discovery.walk_pairs
    if not walk_pairs:
        await emit_filed_history_refusal(events, FILED_HISTORY_DISCOVERY_REFUSAL_CODE)
        return FiledHistoryOnboardingRun(
            pairs=(),
            dry_run=dry_run,
            carries_a_taxpayer_specific_denominator=discovery.carries_a_taxpayer_specific_denominator,
            scoping_signal=discovery.scoping_signal,
            stage_failures=("discovery: no modelo/ejercicio pair to walk",),
        )

    capture = await _capture_discovered_filed_history(
        walk_pairs,
        filed_data_port=filed_data_port,
        output_root=output_root,
        ports=ports,
        limit=limit,
        dry_run=dry_run,
        sync_run_repository=sync_run_repository,
        effect_guard=effect_guard,
        on_session_write=on_session_write,
        events=events,
    )
    pairs = _filed_history_pair_outcomes(discovery, capture)
    if dry_run:
        iva_wallet = _FiledHistoryIvaWalletStage(status="not_attempted", divergence=None, blocked=False)
        notifications = _FiledHistoryNotificationsStage(status="not_attempted", row_count=0)
    else:
        if profile is not None:
            await emit_filed_history_phase(events, FILED_HISTORY_PHASE_IVA_WALLET)
            iva_wallet = await _capture_filed_history_iva_wallet(
                iva_remote_state_port=iva_remote_state_port,
                resolved_today=resolved_today,
                output_root=output_root,
                effect_guard=effect_guard,
                on_session_write=on_session_write,
                events=events,
            )
        else:
            iva_wallet = _FiledHistoryIvaWalletStage(status="not_attempted", divergence=None, blocked=False)
        await emit_filed_history_phase(events, FILED_HISTORY_PHASE_NOTIFICATIONS)
        notifications = await _capture_filed_history_notifications(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            browser_session_factory=browser_session_factory,
            notifications_ports=notifications_ports,
            operator_scope_ports=operator_scope_ports,
            effect_guard=effect_guard,
            on_session_write=on_session_write,
            events=events,
        )
    nominated_coordinates = set(walk_pairs)
    # Keep rectangular capture refusals that have no discovered pair to carry them.
    capture_stage_failures = tuple(
        f"filed_capture: modelo {failure.modelo} ejercicio {failure.year}: {failure.error_type}"
        for failure in capture.failures
        if (failure.modelo, failure.year) not in nominated_coordinates
    )
    stage_failures = capture_stage_failures + tuple(
        failure for failure in (iva_wallet.failure, notifications.failure) if failure is not None
    )

    return FiledHistoryOnboardingRun(
        pairs=pairs,
        dry_run=dry_run,
        captured_count=capture.captured_count,
        reached_count=capture.reached_count,
        scoping_signal=discovery.scoping_signal,
        carries_a_taxpayer_specific_denominator=discovery.carries_a_taxpayer_specific_denominator,
        iva_wallet_status=iva_wallet.status,
        iva_wallet_divergence=iva_wallet.divergence,
        iva_wallet_blocked=iva_wallet.blocked,
        notificaciones_status=notifications.status,
        notificaciones_row_count=notifications.row_count,
        stage_failures=stage_failures,
        sync_run_ref=capture.sync_run_ref,
        evidence_notices=capture.evidence_notices,
        recapture_notices=capture.recapture_notices,
    )


__all__ = ["pull_filed_history"]
