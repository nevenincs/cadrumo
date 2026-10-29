"""Filed-declaration capture services for live AEAT workflows.

The listing helpers read AEAT declaration-register rows without downloading
artefacts. The capture helpers download the selected filed-declaration artefacts
through the authenticated Sede adapter, persist encrypted
:class:`~cadrumo.application.live.filed_observation_ports.FiledObservationProtocol`
payloads and artefacts, promote extracted casillas into registry-grounded
calculation observations, and attempt to stamp matching current
:class:`~ModeloRecord` filings with live
:class:`~ExternalEvidence`.

Source capture resolves a law-determined
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision` through a
generation-pinned registry operation before
asking the Sede adapter which prior declarations a target filing needs, so
cross-period inputs remain registry-authored rather than adapter-inferred. The
module never creates a remote submission or mutates AEAT state; filing-record
stamping is local evidence enrollment against an existing current record.

See Also:
    :class:`~cadrumo.application.live.filed_data_ports.FiledDataCapturePort`
        Supplies the authenticated register and source-capture capabilities.
    :func:`cadrumo.application.live.filed_capture_finalizer.finalize_filed_capture`
        Persists the latest captured filed observations as calculation-history
        evidence, and is the function this module actually calls. Each
        registry-enrollment refusal becomes a typed
        :class:`~application.live.remote_state_models.FiledDataCaptureFailureRow`, raised under
        ``FAIL_FAST`` and reported under ``BEST_EFFORT``.
    :func:`cadrumo.application.live.filed_observation_persistence.enroll_filed_justificante_evidence`
        Persists matching justificante metadata and stamps current filing
        records when the receipt matches.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from cadrumo_client.contracts.automation_codes import AutomationCustodyError
from cadrumo_client.contracts.contracts import RefusalError

from ...core.async_cleanup import has_async_cleanup_failure
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import InternalInvariantError
from ...core.period import Period
from ...core.sync_surface import SyncSurface
from ...core.time.clock import now
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ..storage.sync_runs.persist import record_sync_run
from ..storage.sync_runs.records import (
    SyncRunRecordRepositoryProtocol,
    bounded_scope_description,
    coverage_of,
    sync_run_record_key,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .errors import LiveApplicationInputError, raise_if_aeat_session_ended
from .filed_capture_accumulator import FiledCaptureAccumulator
from .filed_capture_finalizer import FiledCaptureFailurePolicy, finalize_filed_capture
from .filed_capture_queries import (
    await_filed_register_walk,
    filed_data_capture_failure_row,
    plan_filed_capture_queries,
    walk_or_failure_row,
)
from .filed_data import (
    select_declarations_for_capture,
)
from .filed_data_ports import (
    DeferredFiledObservation,
    FiledDataCapturePort,
    FiledDataRegisterPort,
    FiledEffectGuard,
    FiledRegisterDeclarationProtocol,
)
from .filed_history_events import (
    FILED_HISTORY_DECLARATION_PROGRESS_UNIT,
    FILED_HISTORY_DECLARATION_REFUSAL_CODE,
    FILED_HISTORY_PAIR_PROGRESS_UNIT,
    FILED_HISTORY_PAIR_REFUSAL_CODE,
    FILED_HISTORY_PHASE_DECLARATION_CAPTURE,
    FILED_HISTORY_PHASE_FINALIZATION,
    FILED_HISTORY_PHASE_PAIR_WALK,
    FILED_HISTORY_PHASE_PERSISTENCE,
    FILED_HISTORY_PHASE_PROVENANCE,
    FILED_HISTORY_PHASE_REGISTER_ACCESS,
    FiledHistoryEventSink,
    emit_filed_history_phase,
    emit_filed_history_progress,
    emit_filed_history_refusal,
)
from .filed_observation_ports import FiledObservationPersistencePorts, FiledObservationProtocol
from .remote_state_models import (
    BulkFiledDataCaptureReport,
    FiledCapturePairOutcome,
    FiledDataCaptureFailureRow,
    FiledDataCaptureReport,
    SourceFiledDataCaptureReport,
)
from .session import SessionWriteReporter

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


async def capture_filed_data(
    *,
    filed_data_port: FiledDataCapturePort,
    modelo: str,
    year: int,
    output_root: Path,
    ports: FiledObservationPersistencePorts,
    period: Period | None = None,
    expediente_id: str | None = None,
    limit: int | None = None,
    effect_guard: FiledEffectGuard | None = None,
    on_session_write: SessionWriteReporter | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> FiledDataCaptureReport:
    """Capture filed-declaration artefacts and return a :class:`FiledDataCaptureReport`.

    The report accounts for persisted observation manifests, encrypted artefact
    references, saved justificante CSVs, stamped
    :class:`~ModeloRecord` ids, conflicts, and calculation
    observation keys produced from the captured AEAT rows.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return await capture_filed_data(
                filed_data_port=filed_data_port,
                modelo=modelo,
                year=year,
                output_root=output_root,
                ports=ports,
                period=period,
                expediente_id=expediente_id,
                limit=limit,
                effect_guard=effect_guard,
                on_session_write=on_session_write,
                operation=indexed_operation,
            )
    accumulator = FiledCaptureAccumulator(operation=operation)
    bucket_id = require_active_bucket_id()

    async with filed_data_port.open_register(
        operation="live-filed-read", effect_guard=effect_guard, on_session_write=on_session_write
    ) as register:
        declarations = await await_filed_register_walk(
            register.walk(modelo=modelo, ejercicio=year),
            modelo=modelo,
            year=year,
            timeout_ms=register.walk_timeout_ms,
        )
        selected = select_declarations_for_capture(
            declarations,
            period=period,
            expediente_id=expediente_id,
            limit=limit,
        )
        for declaration in selected:
            if effect_guard is None:
                observation = await register.capture_observation(
                    declaration,
                    artefact_sink=ports.observation_persistence.persist_artefact,
                )
                accumulator.absorb(observation, ports=ports, bucket_id=bucket_id, output_root=output_root)
            else:
                # Download remote bytes without holding a commit fence. Persist
                # the artefacts and their local evidence under one fresh fence.
                deferred = await register.capture_observation_deferred(declaration)
                async with effect_guard():
                    observation = deferred.persist_artefacts(ports.observation_persistence.persist_artefact)
                    accumulator.absorb(observation, ports=ports, bucket_id=bucket_id, output_root=output_root)

    if effect_guard is None:
        finalization = finalize_filed_capture(
            tuple(accumulator.observations_for_calculation),
            justificante_csvs_by_observation=accumulator.justificante_csvs_by_observation,
            policy=FiledCaptureFailurePolicy.FAIL_FAST,
            ports=ports,
        )
    else:
        async with effect_guard():
            finalization = finalize_filed_capture(
                tuple(accumulator.observations_for_calculation),
                justificante_csvs_by_observation=accumulator.justificante_csvs_by_observation,
                policy=FiledCaptureFailurePolicy.FAIL_FAST,
                ports=ports,
            )
    calculation_observation_keys = finalization.calculation_observation_keys

    return FiledDataCaptureReport(
        output_root=str(output_root),
        modelo=modelo,
        year=year,
        **accumulator.capture_report_fields(),
        calculation_observation_count=len(calculation_observation_keys),
        calculation_observation_keys=tuple(calculation_observation_keys),
    )


def _declarations_within_limit(
    declarations: tuple[FiledRegisterDeclarationProtocol, ...],
    *,
    limit: int | None,
    reached_count: int,
) -> tuple[FiledRegisterDeclarationProtocol, ...] | None:
    """Narrow one batch to what remains under the cap, or ``None`` once it is met.

    ``None`` means the sweep is finished rather than that this batch is empty:
    an already-met cap stops the walk, so the caller breaks rather than skipping
    to the next modelo/year pair.
    """
    if limit is None:
        return declarations
    remaining = limit - reached_count
    if remaining <= 0:
        return None
    return declarations[:remaining]


@dataclass(frozen=True, slots=True)
class _DeferredFiledDeclarationCapture:
    deferred: DeferredFiledObservation


@dataclass(frozen=True, slots=True)
class _ImmediateFiledDeclarationCapture:
    observation: FiledObservationProtocol


def _require_deferred_filed_capture(
    deferred: DeferredFiledObservation | None,
) -> _DeferredFiledDeclarationCapture:
    if deferred is None:
        raise InternalInvariantError("deferred filed capture was not returned")
    return _DeferredFiledDeclarationCapture(deferred)


def _require_immediate_filed_capture(
    observation: FiledObservationProtocol | None,
) -> _ImmediateFiledDeclarationCapture:
    if observation is None:
        raise InternalInvariantError("filed capture observation was not returned")
    return _ImmediateFiledDeclarationCapture(observation)


async def _record_filed_declaration_capture_failure(
    exc: Exception,
    declaration: FiledRegisterDeclarationProtocol,
    *,
    modelo: str,
    year: int,
    failures: list[FiledDataCaptureFailureRow],
    events: FiledHistoryEventSink | None,
) -> None:
    """Keep cleanup failures fatal; record ordinary declaration failures and their safe scope."""
    if has_async_cleanup_failure(exc):
        raise exc
    failures.append(
        filed_data_capture_failure_row(
            modelo=modelo,
            year=year,
            declaration=declaration,
            error=exc,
        ),
    )
    await emit_filed_history_refusal(events, FILED_HISTORY_DECLARATION_REFUSAL_CODE)


async def _capture_filed_declaration(
    declaration: FiledRegisterDeclarationProtocol,
    *,
    opened_register: FiledDataRegisterPort,
    ports: FiledObservationPersistencePorts,
    dry_run: bool,
    modelo: str,
    year: int,
    failures: list[FiledDataCaptureFailureRow],
    effect_guard: FiledEffectGuard | None,
    events: FiledHistoryEventSink | None,
) -> _DeferredFiledDeclarationCapture | _ImmediateFiledDeclarationCapture | None:
    """Read one declaration, converting ordinary capture errors into failure rows."""
    deferred: DeferredFiledObservation | None = None
    observation: FiledObservationProtocol | None = None
    try:
        if effect_guard is not None and not dry_run:
            deferred = await opened_register.capture_observation_deferred(declaration)
        else:
            observation = await opened_register.capture_observation(
                declaration,
                artefact_sink=None if dry_run else ports.observation_persistence.persist_artefact,
            )
    except (ProfileAccessRefusedError, AutomationCustodyError, RefusalError):
        raise
    except Exception as exc:
        raise_if_aeat_session_ended(exc)
        await _record_filed_declaration_capture_failure(
            exc,
            declaration,
            modelo=modelo,
            year=year,
            failures=failures,
            events=events,
        )
        return None
    else:
        if effect_guard is not None and not dry_run:
            return _require_deferred_filed_capture(deferred)
        return _require_immediate_filed_capture(observation)


async def _absorb_filed_declaration_capture(
    captured: _DeferredFiledDeclarationCapture | _ImmediateFiledDeclarationCapture,
    *,
    accumulator: FiledCaptureAccumulator,
    ports: FiledObservationPersistencePorts,
    bucket_id: str,
    output_root: Path,
    dry_run: bool,
    effect_guard: FiledEffectGuard | None,
) -> None:
    """Persist artefacts under the guard, or absorb the already-read preview."""
    if isinstance(captured, _DeferredFiledDeclarationCapture):
        if effect_guard is None:
            raise InternalInvariantError("deferred filed capture has no effect guard")
        async with effect_guard():
            observation = captured.deferred.persist_artefacts(ports.observation_persistence.persist_artefact)
            accumulator.absorb(
                observation,
                ports=ports,
                bucket_id=bucket_id,
                output_root=output_root,
            )
        return
    accumulator.absorb(
        captured.observation,
        ports=ports,
        bucket_id=bucket_id,
        output_root=output_root,
        dry_run=dry_run,
    )


async def _capture_and_absorb_one_declaration(
    declaration: FiledRegisterDeclarationProtocol,
    *,
    opened_register: FiledDataRegisterPort,
    accumulator: FiledCaptureAccumulator,
    ports: FiledObservationPersistencePorts,
    bucket_id: str,
    output_root: Path,
    dry_run: bool,
    modelo: str,
    year: int,
    failures: list[FiledDataCaptureFailureRow],
    effect_guard: FiledEffectGuard | None,
    events: FiledHistoryEventSink | None,
    declaration_completed: int,
    declaration_total: int,
) -> None:
    """Capture one declaration, persist or preview it, and publish its progress."""
    captured = await _capture_filed_declaration(
        declaration,
        opened_register=opened_register,
        ports=ports,
        dry_run=dry_run,
        modelo=modelo,
        year=year,
        failures=failures,
        effect_guard=effect_guard,
        events=events,
    )
    if captured is not None:
        await _absorb_filed_declaration_capture(
            captured,
            accumulator=accumulator,
            ports=ports,
            bucket_id=bucket_id,
            output_root=output_root,
            dry_run=dry_run,
            effect_guard=effect_guard,
        )
    await emit_filed_history_progress(
        events,
        completed=declaration_completed,
        total=declaration_total,
        unit_code=FILED_HISTORY_DECLARATION_PROGRESS_UNIT,
    )


async def _absorb_declarations(
    declarations: tuple[FiledRegisterDeclarationProtocol, ...],
    *,
    opened_register: FiledDataRegisterPort,
    accumulator: FiledCaptureAccumulator,
    ports: FiledObservationPersistencePorts,
    bucket_id: str,
    output_root: Path,
    dry_run: bool,
    modelo: str,
    year: int,
    failures: list[FiledDataCaptureFailureRow],
    effect_guard: FiledEffectGuard | None = None,
    events: FiledHistoryEventSink | None = None,
) -> None:
    """Capture and absorb one batch, recording a per-declaration failure as a row."""
    declaration_total = len(declarations)
    if not declaration_total:
        return
    await emit_filed_history_progress(
        events,
        completed=0,
        total=declaration_total,
        unit_code=FILED_HISTORY_DECLARATION_PROGRESS_UNIT,
    )
    for declaration_completed, declaration in enumerate(declarations, start=1):
        await _capture_and_absorb_one_declaration(
            declaration,
            opened_register=opened_register,
            accumulator=accumulator,
            ports=ports,
            bucket_id=bucket_id,
            output_root=output_root,
            dry_run=dry_run,
            modelo=modelo,
            year=year,
            failures=failures,
            effect_guard=effect_guard,
            events=events,
            declaration_completed=declaration_completed,
            declaration_total=declaration_total,
        )


def _empty_bulk_filed_capture_report(
    *,
    output_root: Path,
    modelos: Sequence[str],
    year_from: int,
    year_to: int,
    failures: Sequence[FiledDataCaptureFailureRow],
    pair_outcomes: Sequence[FiledCapturePairOutcome],
    dry_run: bool = False,
) -> BulkFiledDataCaptureReport:
    """Build the local-boundary result when no pair can reach the register."""
    report = BulkFiledDataCaptureReport(
        output_root=str(output_root),
        modelos=tuple(modelos),
        year_from=year_from,
        year_to=year_to,
        captured_count=0,
        reached_count=0,
        failed_count=len(failures),
        pair_outcomes=tuple(pair_outcomes),
        observation_paths=(),
        artefact_refs=(),
        justificante_metadata_count=0,
        justificante_csvs=(),
        filing_evidence_stamped_count=0,
        filing_record_ids=(),
        filing_evidence_conflict_count=0,
        filing_evidence_conflict_record_ids=(),
        casilla_count=0,
        calculation_observation_count=0,
        calculation_observation_keys=(),
        failures=tuple(failures),
        dry_run=dry_run,
    )
    report.require_consistent()
    return report


@dataclass(slots=True)
class _CapturePairPhaseState:
    """Track the one-time phases emitted while a bulk capture walks pairs."""

    declaration_capture_started: bool = False
    persistence_started: bool = False


async def _emit_filed_capture_pair_phases(
    *,
    events: FiledHistoryEventSink | None,
    declarations: tuple[FiledRegisterDeclarationProtocol, ...],
    dry_run: bool,
    state: _CapturePairPhaseState,
) -> None:
    """Emit declaration and persistence phases when a pair yields rows."""
    if not declarations:
        return
    if not state.declaration_capture_started:
        await emit_filed_history_phase(events, FILED_HISTORY_PHASE_DECLARATION_CAPTURE)
        state.declaration_capture_started = True
    if dry_run or state.persistence_started:
        return
    await emit_filed_history_phase(events, FILED_HISTORY_PHASE_PERSISTENCE)
    state.persistence_started = True


async def _capture_filed_data_query_pair(
    code: str,
    year: int,
    *,
    opened_register: FiledDataRegisterPort,
    walk_timeout_ms: int,
    accumulator: FiledCaptureAccumulator,
    ports: FiledObservationPersistencePorts,
    bucket_id: str,
    output_root: Path,
    limit: int | None,
    dry_run: bool,
    failures: list[FiledDataCaptureFailureRow],
    effect_guard: FiledEffectGuard | None,
    events: FiledHistoryEventSink | None,
    pair_completed: int,
    pair_total: int,
    phase_state: _CapturePairPhaseState,
    pair_outcomes: dict[tuple[str, int], FiledCapturePairOutcome],
) -> tuple[int, bool]:
    """Walk and absorb one pair, returning progress and whether the cap is met."""
    coordinate = (code, year)
    pair_outcomes[coordinate] = FiledCapturePairOutcome(
        modelo=code,
        year=year,
        walk_attempted=True,
        walk_completed=False,
        row_count=0,
        reached_count=0,
        captured_count=0,
    )
    declarations = await walk_or_failure_row(
        opened_register.walk(modelo=code, ejercicio=year),
        modelo=code,
        year=year,
        timeout_ms=walk_timeout_ms,
        failures=failures,
    )
    pair_completed += 1
    if declarations is None:
        await emit_filed_history_refusal(events, FILED_HISTORY_PAIR_REFUSAL_CODE)
    await emit_filed_history_progress(
        events,
        completed=pair_completed,
        total=pair_total,
        unit_code=FILED_HISTORY_PAIR_PROGRESS_UNIT,
    )
    if declarations is None:
        return pair_completed, False
    pair_outcomes[coordinate] = FiledCapturePairOutcome(
        modelo=code,
        year=year,
        walk_attempted=True,
        walk_completed=True,
        row_count=len(declarations),
        reached_count=0,
        captured_count=0,
    )
    within_limit = _declarations_within_limit(
        declarations,
        limit=limit,
        reached_count=accumulator.reached_count,
    )
    if within_limit is None:
        return pair_completed, True
    reached_before = accumulator.reached_count
    captured_before = len(accumulator.observation_paths)
    await _emit_filed_capture_pair_phases(
        events=events,
        declarations=within_limit,
        dry_run=dry_run,
        state=phase_state,
    )
    await _absorb_declarations(
        within_limit,
        opened_register=opened_register,
        accumulator=accumulator,
        ports=ports,
        bucket_id=bucket_id,
        output_root=output_root,
        dry_run=dry_run,
        modelo=code,
        year=year,
        failures=failures,
        effect_guard=effect_guard,
        events=events,
    )
    outcome = FiledCapturePairOutcome(
        modelo=code,
        year=year,
        walk_attempted=True,
        walk_completed=True,
        row_count=len(declarations),
        reached_count=accumulator.reached_count - reached_before,
        captured_count=len(accumulator.observation_paths) - captured_before,
    )
    outcome.require_consistent()
    pair_outcomes[coordinate] = outcome
    return pair_completed, limit is not None and accumulator.reached_count >= limit


async def _capture_filed_data_query_pairs(
    query_pairs: Sequence[tuple[str, int]],
    *,
    filed_data_port: FiledDataCapturePort,
    accumulator: FiledCaptureAccumulator,
    ports: FiledObservationPersistencePorts,
    bucket_id: str,
    output_root: Path,
    limit: int | None,
    dry_run: bool,
    failures: list[FiledDataCaptureFailureRow],
    pair_outcomes: dict[tuple[str, int], FiledCapturePairOutcome],
    effect_guard: FiledEffectGuard | None = None,
    on_session_write: SessionWriteReporter | None = None,
    events: FiledHistoryEventSink | None = None,
    pair_completed: int = 0,
    pair_total: int | None = None,
) -> int:
    """Walk, cap, and absorb every queryable pair in canonical sweep order."""
    total = pair_total if pair_total is not None else len(query_pairs)
    await emit_filed_history_phase(events, FILED_HISTORY_PHASE_REGISTER_ACCESS)
    await emit_filed_history_phase(events, FILED_HISTORY_PHASE_PAIR_WALK)
    phase_state = _CapturePairPhaseState()
    async with filed_data_port.open_register(
        operation="live-expedientes-read", effect_guard=effect_guard, on_session_write=on_session_write
    ) as opened_register:
        for code, year in query_pairs:
            pair_completed, limit_reached = await _capture_filed_data_query_pair(
                code,
                year,
                opened_register=opened_register,
                walk_timeout_ms=opened_register.walk_timeout_ms,
                accumulator=accumulator,
                ports=ports,
                bucket_id=bucket_id,
                output_root=output_root,
                limit=limit,
                dry_run=dry_run,
                failures=failures,
                effect_guard=effect_guard,
                events=events,
                pair_completed=pair_completed,
                pair_total=total,
                phase_state=phase_state,
                pair_outcomes=pair_outcomes,
            )
            if limit_reached:
                return pair_completed
    return pair_completed


def _dry_run_bulk_filed_capture_report(
    *,
    output_root: Path,
    modelos: Sequence[str],
    year_from: int,
    year_to: int,
    accumulator: FiledCaptureAccumulator,
    failures: Sequence[FiledDataCaptureFailureRow],
    pair_outcomes: Sequence[FiledCapturePairOutcome],
) -> BulkFiledDataCaptureReport:
    """Project the read-only bulk result without reaching any persistence finalizer."""
    report = BulkFiledDataCaptureReport(
        output_root=str(output_root),
        modelos=tuple(modelos),
        year_from=year_from,
        year_to=year_to,
        failed_count=len(failures),
        pair_outcomes=tuple(pair_outcomes),
        **accumulator.capture_report_fields(),
        calculation_observation_count=0,
        calculation_observation_keys=(),
        failures=tuple(failures),
        recapture_notices=tuple(accumulator.recapture_notices),
        dry_run=True,
    )
    report.require_consistent()
    return report


def _persisted_bulk_filed_capture_report(
    *,
    output_root: Path,
    modelos: Sequence[str],
    year_from: int,
    year_to: int,
    accumulator: FiledCaptureAccumulator,
    failures: list[FiledDataCaptureFailureRow],
    bucket_id: str,
    sync_run_repository: SyncRunRecordRepositoryProtocol,
    ports: FiledObservationPersistencePorts,
    pair_outcomes: Sequence[FiledCapturePairOutcome],
) -> BulkFiledDataCaptureReport:
    """Finalize persisted observations, then record the completed sweep provenance."""
    finalization = finalize_filed_capture(
        tuple(accumulator.observations_for_calculation),
        justificante_csvs_by_observation=accumulator.justificante_csvs_by_observation,
        policy=FiledCaptureFailurePolicy.BEST_EFFORT,
        ports=ports,
    )
    calculation_observation_keys = finalization.calculation_observation_keys
    failures.extend(finalization.failures)
    sync_run = record_sync_run(
        bucket_id=bucket_id,
        surface=SyncSurface.FILED_DECLARATIONS,
        resolved_scope=bounded_scope_description(tuple(modelos), suffix=f"{year_from}-{year_to}"),
        succeeded=not failures,
        coverage=coverage_of(accumulator),
        completed_at=now(),
        repository=sync_run_repository,
    )
    report = BulkFiledDataCaptureReport(
        output_root=str(output_root),
        modelos=tuple(modelos),
        year_from=year_from,
        year_to=year_to,
        failed_count=len(failures),
        pair_outcomes=tuple(pair_outcomes),
        sync_run_ref=sync_run_record_key(
            surface=sync_run.surface,
            bucket_event_id=sync_run.bucket_event_id,
        ),
        **accumulator.capture_report_fields(),
        calculation_observation_count=len(calculation_observation_keys),
        calculation_observation_keys=tuple(calculation_observation_keys),
        failures=tuple(failures),
        skipped_casillas=finalization.skipped_casillas,
        recapture_notices=tuple(accumulator.recapture_notices),
    )
    report.require_consistent()
    return report


async def _announce_bulk_capture_plan(
    *,
    query_pairs: Sequence[tuple[str, int]],
    failures: Sequence[FiledDataCaptureFailureRow],
    events: FiledHistoryEventSink | None,
) -> int:
    """Publish initial pair progress and local refusal rows in walk order."""
    pair_total = len(query_pairs) + len(failures)
    if pair_total:
        await emit_filed_history_progress(
            events,
            completed=0,
            total=pair_total,
            unit_code=FILED_HISTORY_PAIR_PROGRESS_UNIT,
        )
    for _failure in failures:
        await emit_filed_history_refusal(events, FILED_HISTORY_PAIR_REFUSAL_CODE)
    if failures:
        await emit_filed_history_progress(
            events,
            completed=len(failures),
            total=pair_total,
            unit_code=FILED_HISTORY_PAIR_PROGRESS_UNIT,
        )
    return pair_total


def _require_bulk_capture_dependencies(
    *,
    dry_run: bool,
    sync_run_repository: SyncRunRecordRepositoryProtocol | None,
) -> str:
    """Validate persistence authority before resolving the active bucket."""
    if not dry_run and sync_run_repository is None:
        raise LiveApplicationInputError(
            translated_message="application.live.filed_data.errors.sync_run_repository_required",
            context={"dry_run": dry_run, "sync_run_repository_present": False},
        )
    return require_active_bucket_id()


async def _settle_bulk_filed_capture_report(
    *,
    output_root: Path,
    modelos: tuple[str, ...],
    year_from: int,
    year_to: int,
    accumulator: FiledCaptureAccumulator,
    failures: list[FiledDataCaptureFailureRow],
    pair_outcomes: tuple[FiledCapturePairOutcome, ...],
    dry_run: bool,
    sync_run_repository: SyncRunRecordRepositoryProtocol | None,
    bucket_id: str,
    ports: FiledObservationPersistencePorts,
    events: FiledHistoryEventSink | None,
    effect_guard: FiledEffectGuard | None,
) -> BulkFiledDataCaptureReport:
    """Settle preview directly, or finalize and persist the completed-run evidence."""
    if dry_run:
        return _dry_run_bulk_filed_capture_report(
            output_root=output_root,
            modelos=modelos,
            year_from=year_from,
            year_to=year_to,
            accumulator=accumulator,
            failures=failures,
            pair_outcomes=pair_outcomes,
        )
    if sync_run_repository is None:
        raise LiveApplicationInputError(
            translated_message="application.live.filed_data.errors.sync_run_repository_required",
            context={"dry_run": dry_run, "sync_run_repository_present": False},
        )
    await emit_filed_history_phase(events, FILED_HISTORY_PHASE_FINALIZATION)
    await emit_filed_history_phase(events, FILED_HISTORY_PHASE_PROVENANCE)
    if effect_guard is not None:
        async with effect_guard():
            return _persisted_bulk_filed_capture_report(
                output_root=output_root,
                modelos=modelos,
                year_from=year_from,
                year_to=year_to,
                accumulator=accumulator,
                failures=failures,
                bucket_id=bucket_id,
                sync_run_repository=sync_run_repository,
                ports=ports,
                pair_outcomes=pair_outcomes,
            )
    return _persisted_bulk_filed_capture_report(
        output_root=output_root,
        modelos=modelos,
        year_from=year_from,
        year_to=year_to,
        accumulator=accumulator,
        failures=failures,
        bucket_id=bucket_id,
        sync_run_repository=sync_run_repository,
        ports=ports,
        pair_outcomes=pair_outcomes,
    )


async def capture_filed_data_bulk(
    *,
    filed_data_port: FiledDataCapturePort,
    year_from: int,
    year_to: int,
    output_root: Path,
    ports: FiledObservationPersistencePorts,
    modelos: tuple[str, ...] | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    sync_run_repository: SyncRunRecordRepositoryProtocol | None = None,
    events: FiledHistoryEventSink | None = None,
    effect_guard: FiledEffectGuard | None = None,
    on_session_write: SessionWriteReporter | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> BulkFiledDataCaptureReport:
    """Capture filed declarations across a year range and return a :class:`BulkFiledDataCaptureReport`.

    Unsupported modelo/year pairs are recorded as failures before live contact.
    Supported pairs share one authenticated register session and then follow the
    same persistence, justificante enrolment, and calculation-observation path as
    :func:`capture_filed_data`.

    Args:
        year_from: First filing year to query.
        year_to: Last filing year to query.
        output_root: Root the captured observations and artefacts persist under.
        ports: Composed filed-observation persistence and transformation ports.
        modelos: Modelo codes to walk; every registry modelo when omitted.
        limit: Cap on captured observations; unbounded when omitted.
        filed_data_port: Composed register acquisition capability. Its outer
            implementation owns session and browser lifecycles.
        dry_run: Preview the sweep. AEAT is still read and the divergence set
            the upsert would introduce is still computed, but nothing is
            written: no observation persisted, no justificante evidence
            enrolled, no calculation observation finalized. The report carries
            ``dry_run=True`` and the divergences as its primary result.
        sync_run_repository: Persistence port for the completed-run provenance
            record. Required for a non-preview capture that reaches a supported
            query pair; the outer entrypoint composes the concrete adapter.
        operation: Caller-held generation-pinned authority operation; opened from
            the indexed bundled authority when omitted.
        events: Optional operation event emitter. The composed filed-history
            pull supplies it to publish phase, safe unit-count, and refusal-scope
            facts at the canonical workflow boundaries.
        effect_guard: Optional authorization fence around each local persisted effect.
        on_session_write: Record a provider session write in the operation receipt.
    """
    if year_from > year_to:
        raise LiveApplicationInputError(
            translated_message="live.errors.year_range_invalid",
        )

    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return await capture_filed_data_bulk(
                filed_data_port=filed_data_port,
                year_from=year_from,
                year_to=year_to,
                output_root=output_root,
                ports=ports,
                modelos=modelos,
                limit=limit,
                dry_run=dry_run,
                sync_run_repository=sync_run_repository,
                events=events,
                effect_guard=effect_guard,
                on_session_write=on_session_write,
                operation=indexed_operation,
            )
    resolved_modelos = modelos if modelos is not None else operation.modelo_ids()
    if len(set(resolved_modelos)) != len(resolved_modelos):
        raise ValueError("filed bulk capture requires unique modelo/year coordinates")
    accumulator = FiledCaptureAccumulator(operation=operation)
    pair_outcomes = {
        (code, year): FiledCapturePairOutcome(
            modelo=code,
            year=year,
            walk_attempted=False,
            walk_completed=False,
            row_count=0,
            reached_count=0,
            captured_count=0,
        )
        for code in resolved_modelos
        for year in range(year_to, year_from - 1, -1)
    }
    query_pairs, failures = plan_filed_capture_queries(
        resolved_modelos,
        year_from=year_from,
        year_to=year_to,
        operation=operation,
    )
    pair_total = await _announce_bulk_capture_plan(
        query_pairs=query_pairs,
        failures=failures,
        events=events,
    )

    if not query_pairs:
        return _empty_bulk_filed_capture_report(
            output_root=output_root,
            modelos=resolved_modelos,
            year_from=year_from,
            year_to=year_to,
            failures=failures,
            pair_outcomes=tuple(pair_outcomes.values()),
            dry_run=dry_run,
        )

    bucket_id = _require_bulk_capture_dependencies(
        dry_run=dry_run,
        sync_run_repository=sync_run_repository,
    )

    await _capture_filed_data_query_pairs(
        query_pairs,
        filed_data_port=filed_data_port,
        accumulator=accumulator,
        ports=ports,
        bucket_id=bucket_id,
        output_root=output_root,
        limit=limit,
        dry_run=dry_run,
        failures=failures,
        effect_guard=effect_guard,
        on_session_write=on_session_write,
        events=events,
        pair_completed=len(failures),
        pair_total=pair_total,
        pair_outcomes=pair_outcomes,
    )

    return await _settle_bulk_filed_capture_report(
        output_root=output_root,
        modelos=resolved_modelos,
        year_from=year_from,
        year_to=year_to,
        accumulator=accumulator,
        failures=failures,
        pair_outcomes=tuple(pair_outcomes.values()),
        dry_run=dry_run,
        sync_run_repository=sync_run_repository,
        bucket_id=bucket_id,
        ports=ports,
        events=events,
        effect_guard=effect_guard,
    )


async def capture_source_filed_data(
    *,
    filed_data_port: FiledDataCapturePort,
    modelo: str,
    year: int,
    period: Period,
    output_root: Path,
    ports: FiledObservationPersistencePorts,
    effect_guard: FiledEffectGuard | None = None,
    on_session_write: SessionWriteReporter | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> SourceFiledDataCaptureReport:
    """Capture source observations and return a :class:`SourceFiledDataCaptureReport`.

    The source relationships are selected from the immutable bundled authority.
    Caller-controlled registry and source roots are deliberately not accepted:
    live evidence capture must use the same validated legal snapshot as filing.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return await capture_source_filed_data(
                filed_data_port=filed_data_port,
                modelo=modelo,
                year=year,
                period=period,
                output_root=output_root,
                ports=ports,
                effect_guard=effect_guard,
                on_session_write=on_session_write,
                operation=indexed_operation,
            )
    revision = operation.snapshot(
        modelo,
        filing_year=year,
        period=period.registry_token,
    ).revision
    accumulator = FiledCaptureAccumulator(operation=operation)
    seen: set[tuple[str, int, str, str]] = set()
    bucket_id = require_active_bucket_id()

    if effect_guard is None:
        observations = await filed_data_port.capture_source_observations(
            revision,
            filing_year=year,
            period=period,
            artefact_sink=ports.observation_persistence.persist_artefact,
            operation="live-filed-read",
        )
    else:
        deferred = await filed_data_port.capture_source_observations_deferred(
            revision,
            filing_year=year,
            period=period,
            operation="live-filed-read",
            effect_guard=effect_guard,
            on_session_write=on_session_write,
        )
        async with effect_guard():
            observations = deferred.persist_artefacts(ports.observation_persistence.persist_artefact)
            for observation in observations:
                key = (
                    observation.modelo,
                    observation.ejercicio,
                    observation.period.registry_token,
                    observation.expediente_id,
                )
                if key in seen:
                    continue
                seen.add(key)
                accumulator.absorb(observation, ports=ports, bucket_id=bucket_id, output_root=output_root)
    if effect_guard is None:
        for observation in observations:
            key = (
                observation.modelo,
                observation.ejercicio,
                observation.period.registry_token,
                observation.expediente_id,
            )
            if key in seen:
                continue
            seen.add(key)
            accumulator.absorb(observation, ports=ports, bucket_id=bucket_id, output_root=output_root)

    if effect_guard is None:
        finalization = finalize_filed_capture(
            tuple(accumulator.observations_for_calculation),
            justificante_csvs_by_observation=accumulator.justificante_csvs_by_observation,
            policy=FiledCaptureFailurePolicy.FAIL_FAST,
            ports=ports,
        )
    else:
        async with effect_guard():
            finalization = finalize_filed_capture(
                tuple(accumulator.observations_for_calculation),
                justificante_csvs_by_observation=accumulator.justificante_csvs_by_observation,
                policy=FiledCaptureFailurePolicy.FAIL_FAST,
                ports=ports,
            )
    calculation_observation_keys = finalization.calculation_observation_keys

    return SourceFiledDataCaptureReport(
        output_root=str(output_root),
        target_modelo=modelo,
        target_year=year,
        target_period=period,
        **accumulator.capture_report_fields(),
        calculation_observation_count=len(calculation_observation_keys),
        calculation_observation_keys=tuple(calculation_observation_keys),
    )
