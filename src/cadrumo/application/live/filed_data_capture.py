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

import asyncio
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from ...core.async_cleanup import has_async_cleanup_failure
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import InternalInvariantError
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.period import Period
from ...core.sync_surface import SyncSurface
from ...core.time.clock import now
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.schema import (
    ModeloRevision,
)
from ..modelo.filing_chain_reconciliation import FilingReconciliationResult
from ..runtime.contracts import RuntimeRefusalError
from ..storage.sync_runs.persist import record_sync_run
from ..storage.sync_runs.records import (
    SyncRunRecordRepositoryProtocol,
    bounded_scope_description,
    coverage_of,
    sync_run_record_key,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from ..user_profile.automation_custody_port import AutomationCustodyError
from .errors import LiveApplicationInputError, LiveIvaSurfaceTimeoutError
from .filed_capture_finalizer import FiledCaptureFailurePolicy, finalize_filed_capture
from .filed_data import (
    BulkFiledDataListingReport,
    FiledDataListingReport,
    FiledDataListingRow,
    filed_data_listing_row,
    select_declarations_for_capture,
)
from .filed_data_ports import (
    DeferredFiledObservation,
    FiledDataCapturePort,
    FiledDataRegisterPort,
    FiledEffectGuard,
    FiledRegisterDeclarationProtocol,
)
from .filed_history_discovery import recapture_divergence_notices
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
from .filed_observation_persistence import (
    enroll_filed_justificante_evidence,
    filed_observation_identity_key,
)
from .filed_observation_ports import FiledObservationPersistencePorts, FiledObservationProtocol
from .remote_state_models import (
    BulkFiledDataCaptureReport,
    FiledCapturePairOutcome,
    FiledDataCaptureFailureRow,
    FiledDataCaptureReport,
    SourceFiledDataCaptureReport,
)
from .remote_state_outcomes import bounded_context_text
from .session import SessionWriteReporter

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


def filed_data_capture_failure_row(
    *,
    modelo: str,
    year: int,
    error: BaseException,
    declaration: FiledRegisterDeclarationProtocol | None = None,
) -> FiledDataCaptureFailureRow:
    """Map one failed capture into a :class:`FiledDataCaptureFailureRow`."""
    failed_period = declaration.period if declaration is not None else None
    return FiledDataCaptureFailureRow(
        modelo=declaration.modelo if declaration is not None else modelo,
        year=declaration.ejercicio if declaration is not None else year,
        period=failed_period,
        expediente_id=declaration.expediente_id if declaration is not None else None,
        error_type=error.__class__.__name__,
        message=bounded_context_text(error),
    )


def _unsupported_filed_capture_failure_row(
    *,
    modelo: str,
    year: int,
    reason: str,
) -> FiledDataCaptureFailureRow:
    return FiledDataCaptureFailureRow(
        modelo=modelo,
        year=year,
        error_type="LiveApplicationInputError",
        message=reason,
    )


def _filed_capture_revisions_for_year(
    revisions: Sequence[ModeloRevision],
    *,
    year: int,
) -> tuple[ModeloRevision, ...]:
    """Return this modelo's revisions that cover the requested filing year."""
    return tuple(revision for revision in revisions if revision.period_selector.includes_year(year))


def _declares_filed_declarations_read_surface(revisions: Sequence[ModeloRevision]) -> bool:
    """Whether a covering registry revision authorizes the declarations-register read."""
    return any(
        ref.surface == "authenticated_read_surface" and ref.id.endswith("filed-declarations-read")
        for revision in revisions
        for ref in revision.live_cross_references
    )


def _registered_modelo_revisions(
    modelo: str,
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[ModeloRevision, ...] | None:
    """Load the explicitly enumerated revisions for one registry modelo."""
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return _registered_modelo_revisions(modelo, operation=indexed_operation)
    try:
        directory = operation.modelo_directory(modelo)
        revisions = tuple(operation.revision(modelo, str(metadata.id)) for metadata in directory.revisions)
    except (RegistrySnapshotError, ValueError):
        return None
    return revisions or None


def _filed_capture_unsupported_reason(
    *,
    modelo: str,
    year: int,
    operation: PinnedAuthorityOperation | None = None,
) -> str | None:
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return _filed_capture_unsupported_reason(modelo=modelo, year=year, operation=indexed_operation)
    revisions = _registered_modelo_revisions(modelo, operation=operation)
    if revisions is None:
        return f"registry has no modelo definition for {modelo!r}"
    revisions = _filed_capture_revisions_for_year(revisions, year=year)
    if not revisions:
        return f"registry has no revision for modelo {modelo!r} filing year {year}"
    if _declares_filed_declarations_read_surface(revisions):
        return None
    # States only what is knowable here. Whether AEAT serves a modelo at the
    # consulta view is not derivable from our own registry's silence, and the
    # previous wording asserted it was, so an operator read a claim about AEAT's
    # coverage that nothing in this tree supports. The register's own modelo
    # combobox is the authority, and the discovery verb reads it.
    return (
        f"modelo {modelo!r} declares no authenticated filed-declarations read surface in this "
        "deployment's registry, so the declarations register was not queried for it. Whether AEAT "
        "serves this modelo at the consulta view is not recorded here. Run "
        "`aeat app live filed discover` to read the register's own modelo list and settle it"
    )


def _plan_filed_capture_queries(
    resolved_modelos: Sequence[str],
    *,
    year_from: int,
    year_to: int,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[list[tuple[str, int]], list[FiledDataCaptureFailureRow]]:
    """Plan the ``(modelo, year)`` pairs a bulk filed-data walk should query.

    Shared by :func:`list_filed_data_bulk` and :func:`capture_filed_data_bulk`:
    walks each requested modelo across the year range newest-first and diverts
    any pair the declarations register cannot serve into a typed unsupported
    failure row instead of querying it, so an unserviceable modelo/year is
    reported rather than silently dropped.

    Returns:
        The queryable ``(modelo, year)`` pairs and the unsupported failure rows,
        each in walk order.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return _plan_filed_capture_queries(
                resolved_modelos,
                year_from=year_from,
                year_to=year_to,
                operation=indexed_operation,
            )
    query_pairs: list[tuple[str, int]] = []
    failures: list[FiledDataCaptureFailureRow] = []
    for code in resolved_modelos:
        for year in range(year_to, year_from - 1, -1):
            unsupported_reason = _filed_capture_unsupported_reason(modelo=code, year=year, operation=operation)
            if unsupported_reason is not None:
                failures.append(
                    _unsupported_filed_capture_failure_row(modelo=code, year=year, reason=unsupported_reason),
                )
                continue
            query_pairs.append((code, year))
    return query_pairs, failures


async def _await_filed_register_walk(
    awaitable: Awaitable[tuple[FiledRegisterDeclarationProtocol, ...]],
    *,
    modelo: str,
    year: int,
    timeout_ms: int,
) -> tuple[FiledRegisterDeclarationProtocol, ...]:
    """Bound one AEAT filed-register modelo/year query."""
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_ms / 1000)
    except TimeoutError as exc:
        raise LiveIvaSurfaceTimeoutError(
            f"live filed declaration register query for modelo {modelo} year {year} did not complete "
            f"within {timeout_ms} ms",
            surface="filed_declarations_register_walk",
            timeout_ms=timeout_ms,
            progress_context={"modelo": modelo, "year": year},
        ) from exc


async def _walk_or_failure_row(
    awaitable: Awaitable[tuple[FiledRegisterDeclarationProtocol, ...]],
    *,
    modelo: str,
    year: int,
    timeout_ms: int,
    failures: list[FiledDataCaptureFailureRow],
) -> tuple[FiledRegisterDeclarationProtocol, ...] | None:
    """Absorb one modelo/year register query's failure into a row, or return its rows.

    Takes the walk awaitable rather than the register that produces it: the
    register was only ever used to build this one coroutine, so the narrower
    parameter drops a dependency the helper never needed and lets the absorption
    arm be exercised with a real coroutine, the way the sibling
    :func:`_await_filed_register_walk` already is.

    Shared bulk-path arm behind :func:`list_filed_data_bulk` and
    :func:`capture_filed_data_bulk`: on a remote walk failure the exception is folded
    into ``failures`` as a :class:`FiledDataCaptureFailureRow` and ``None`` is
    returned so the caller can skip the pair.

    A register page whose grid declares more records than it rendered is refused
    by the walker rather than returned short, and that refusal arrives here like
    any other walk failure — one pair reported as failed while the sweep
    continues. Truncation deliberately gets no bulk-level mechanism of its own:
    a second reporting channel would let a partial capture be counted as a
    success on one path and a failure on the other.
    """
    try:
        return await _await_filed_register_walk(
            awaitable,
            modelo=modelo,
            year=year,
            timeout_ms=timeout_ms,
        )
    except (ProfileAccessRefusedError, AutomationCustodyError, RuntimeRefusalError):
        raise
    except Exception as exc:
        if has_async_cleanup_failure(exc):
            raise
        failures.append(filed_data_capture_failure_row(modelo=modelo, year=year, error=exc))
        return None


FILED_SUBMITTED_FILE_EXTRACTION_NOTICE_CODE = "live.filed.pull.submitted_file_extraction_failed"
_SUBMITTED_FILE_EXTRACTION_ERROR_METADATA_KEY = "submitted_file_extraction_error"


def submitted_file_extraction_notices(observation: FiledObservationProtocol) -> tuple[Notice, ...]:
    """Project a recorded submitted-file layout refusal onto the notice channel.

    The Sede adapter is the authority for both parsing and the persisted error
    text. It records a refusal under ``submitted_file_extraction_error`` and
    preserves its declaration-PDF fallback without trying to reinterpret either
    one here. This projection only makes that already-recorded fact visible to
    the operator, retaining the parser's own reason and the filed record that
    needs follow-up. A clean capture has no metadata key and therefore no
    advisory.
    """
    reason = observation.metadata.get(_SUBMITTED_FILE_EXTRACTION_ERROR_METADATA_KEY, "").strip()
    if not reason:
        return ()
    return (
        Notice(
            severity=NoticeSeverity.WARNING,
            code=FILED_SUBMITTED_FILE_EXTRACTION_NOTICE_CODE,
            message=tr(
                "live.filed.pull.submitted_file_extraction_failed",
                modelo=observation.modelo,
                period=observation.period.registry_token,
                ejercicio=observation.ejercicio,
                expediente_id=observation.expediente_id,
                reason=reason,
            ),
            context={
                "modelo": observation.modelo,
                "filing_year": str(observation.ejercicio),
                "period": observation.period.registry_token,
                "expediente_id": observation.expediente_id,
                "reason": reason,
            },
        ),
    )


class _CaptureReportFields(TypedDict):
    """Deduped report fields shared by every filed-declaration capture report."""

    captured_count: int
    reached_count: int
    observation_paths: tuple[str, ...]
    artefact_refs: tuple[str, ...]
    justificante_metadata_count: int
    justificante_csvs: tuple[str, ...]
    filing_evidence_stamped_count: int
    filing_record_ids: tuple[str, ...]
    filing_evidence_conflict_count: int
    filing_evidence_conflict_record_ids: tuple[str, ...]
    evidence_notices: tuple[Notice, ...]
    casilla_count: int
    reconciliation_results: tuple[FilingReconciliationResult, ...]


@dataclass(slots=True)
class FiledCaptureAccumulator:
    """Mutable accumulator for one filed-declaration capture run.

    Holds the persisted-artefact ledgers shared by the single-shot, bulk, and
    source capture paths. :meth:`absorb` folds one captured observation into the
    run (persist manifest, collect artefact refs, enrol justificante evidence,
    reconcile the filing chain); :meth:`capture_report_fields` projects the deduped
    report fields every capture report shares. The ``dict.fromkeys`` dedup
    ordering is preserved verbatim so report values stay byte-identical.
    """

    operation: PinnedAuthorityOperation | None = None
    observation_paths: list[str] = field(default_factory=list)
    artefact_refs: list[str] = field(default_factory=list)
    justificante_csvs: list[str] = field(default_factory=list)
    filing_record_ids: list[str] = field(default_factory=list)
    conflicting_filing_record_ids: list[str] = field(default_factory=list)
    reconciliation_results: list[FilingReconciliationResult] = field(default_factory=list)
    observations_for_calculation: list[FiledObservationProtocol] = field(default_factory=list)
    evidence_notices: list[Notice] = field(default_factory=list)
    #: Recapture-divergence advisories, one per re-captured filing whose casilla
    #: values this sweep changed. Read before each upsert, never after.
    recapture_notices: list[Notice] = field(default_factory=list)
    justificante_csvs_by_observation: dict[tuple[str, int, str, str], tuple[str, ...]] = field(default_factory=dict)
    casilla_count: int = 0
    #: Observations folded in, counted in every mode. ``observation_paths``
    #: cannot serve as the tally because a preview persists nothing and would
    #: leave it empty, which would silently uncap a limited sweep.
    absorbed_count: int = 0

    @property
    def reached_count(self) -> int:
        """Units this run REACHED, answering :class:`SyncRunCoverageSource`.

        The surface-neutral name the sync-run store asks for, mapped onto this
        sweep's own tally. Both coverage counts are read off this one object so
        they cannot be drawn from different populations.
        """
        return self.absorbed_count

    @property
    def divergences(self) -> Sequence[Notice]:
        """Divergences found among the reached units, one entry each.

        Bounded by :attr:`reached_count` by construction: :meth:`absorb` appends
        at most one advisory per observation and increments the tally on the
        same pass, so the sync-run coverage bound cannot be violated from here.
        """
        return self.recapture_notices

    def absorb(
        self,
        observation: FiledObservationProtocol,
        *,
        ports: FiledObservationPersistencePorts,
        bucket_id: str,
        output_root: Path,
        dry_run: bool = False,
    ) -> None:
        """Persist one captured observation and fold its artefacts into the run.

        With ``dry_run`` the divergence read still happens and every write is
        skipped: no observation is persisted, no justificante evidence is
        enrolled, and nothing is queued for the calculation-observation write
        downstream. The preview therefore runs the real funnel minus its
        writes, rather than a parallel implementation that could drift from it.
        """
        # Read the recapture divergence BEFORE the upsert, because a re-capture
        # is an unconditional upsert and afterwards the prior values are gone.
        # This is the only ordering that can answer "what did this sweep change";
        # the advisory it produces was built and exported but never called from
        # any production path, so a corrected filing silently overwrote the
        # previously observed values and the operator was never told.
        self.recapture_notices.extend(
            recapture_divergence_notices(
                (observation,),
                repository=ports.calculation_repository,
                operation=self.operation,
            )
        )
        # The Sede capture deliberately preserves a submitted-file layout
        # refusal as observation metadata and then keeps the declaration-PDF
        # fallback available. Metadata alone is not an operator surface,
        # though: fold the recorded refusal into the one capture advisory lane
        # before persistence so every capture mode can forward it verbatim.
        self.evidence_notices.extend(submitted_file_extraction_notices(observation))
        self.absorbed_count += 1
        if dry_run:
            # Everything past this point writes. The divergence read above is
            # the preview's whole answer and it has already happened.
            return
        manifest_path = ports.observation_persistence.persist_observation(observation)
        self.observation_paths.append(capture_report_path(manifest_path, output_root=output_root))
        self.artefact_refs.extend(
            storage_ref
            for artefact in observation.artefacts
            for storage_ref in (artefact.storage_ref,)
            if storage_ref is not None
        )
        enrollment = enroll_filed_justificante_evidence(observation, ports=ports, bucket_id=bucket_id)
        self.justificante_csvs.extend(enrollment.justificante_csvs)
        self.justificante_csvs_by_observation[filed_observation_identity_key(observation)] = (
            enrollment.justificante_csvs
        )
        self.filing_record_ids.extend(enrollment.filing_record_ids)
        self.conflicting_filing_record_ids.extend(enrollment.conflicting_filing_record_ids)
        self.reconciliation_results.extend(enrollment.reconciliation_results)
        # The enrolment already produced one typed WARNING per artefact that
        # yielded no evidence, each naming its own reason. They were being
        # discarded here, which is what let a capture extract casillas and report
        # zero justificante evidence with no visible cause. Collected verbatim --
        # never merged -- because two distinguishable dead ends folded into one
        # notice recreates the collapse the reasons exist to undo.
        self.evidence_notices.extend(enrollment.notices)
        self.casilla_count += len(observation.casillas)
        self.observations_for_calculation.append(observation)

    def capture_report_fields(self) -> _CaptureReportFields:
        """Return the deduped report fields shared by every filed-capture report."""
        return {
            "captured_count": len(self.observation_paths),
            "reached_count": self.reached_count,
            "observation_paths": tuple(self.observation_paths),
            "artefact_refs": tuple(self.artefact_refs),
            "justificante_metadata_count": len(tuple(dict.fromkeys(self.justificante_csvs))),
            "justificante_csvs": tuple(dict.fromkeys(self.justificante_csvs)),
            "filing_evidence_stamped_count": len(tuple(dict.fromkeys(self.filing_record_ids))),
            "filing_record_ids": tuple(dict.fromkeys(self.filing_record_ids)),
            "filing_evidence_conflict_count": len(tuple(dict.fromkeys(self.conflicting_filing_record_ids))),
            "filing_evidence_conflict_record_ids": tuple(dict.fromkeys(self.conflicting_filing_record_ids)),
            "evidence_notices": tuple(self.evidence_notices),
            "casilla_count": self.casilla_count,
            "reconciliation_results": tuple(self.reconciliation_results),
        }


async def list_filed_data(
    *,
    filed_data_port: FiledDataCapturePort,
    modelo: str,
    year_from: int,
    year_to: int,
    authority_operation: PinnedAuthorityOperation | None = None,
    effect_guard: FiledEffectGuard | None = None,
    on_session_write: SessionWriteReporter | None = None,
) -> FiledDataListingReport:
    """List declarations via AEAT and return a :class:`FiledDataListingReport`."""
    if year_from > year_to:
        raise LiveApplicationInputError(
            translated_message="live.errors.year_range_invalid",
        )

    rows: list[FiledDataListingRow] = []
    register_scope = (
        filed_data_port.open_register(
            operation="live-expedientes-read",
            authority_operation=authority_operation,
            effect_guard=effect_guard,
            on_session_write=on_session_write,
        )
        if authority_operation is not None
        else filed_data_port.open_register(
            operation="live-expedientes-read", effect_guard=effect_guard, on_session_write=on_session_write
        )
    )
    async with register_scope as register:
        for year in range(year_to, year_from - 1, -1):
            declarations = await _await_filed_register_walk(
                register.walk(modelo=modelo, ejercicio=year),
                modelo=modelo,
                year=year,
                timeout_ms=register.walk_timeout_ms,
            )
            rows.extend(filed_data_listing_row(declaration) for declaration in declarations)
    return FiledDataListingReport(
        modelo=modelo,
        year_from=year_from,
        year_to=year_to,
        row_count=len(rows),
        rows=tuple(rows),
    )


async def list_filed_data_bulk(
    *,
    filed_data_port: FiledDataCapturePort,
    year_from: int,
    year_to: int,
    modelos: tuple[str, ...] | None = None,
    operation: PinnedAuthorityOperation | None = None,
    effect_guard: FiledEffectGuard | None = None,
    on_session_write: SessionWriteReporter | None = None,
) -> BulkFiledDataListingReport:
    """List filed declarations across modelos with one authenticated register session.

    Args:
        year_from: First filing year to query.
        year_to: Last filing year to query.
        modelos: Modelo codes to walk; every registry modelo when omitted.
        operation: Caller-held generation-pinned authority operation; opened from
            the indexed bundled authority when omitted.
        filed_data_port: Composed register acquisition capability. Its outer
            implementation owns session and browser lifecycles.
        effect_guard: Commit guard for encrypted session writes during authentication.
        on_session_write: Effect receipt callback for a published session write.

    Returns:
        A :class:`BulkFiledDataListingReport` of the per-modelo rows and failures.
    """
    if year_from > year_to:
        raise LiveApplicationInputError(
            translated_message="live.errors.year_range_invalid",
        )

    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return await list_filed_data_bulk(
                filed_data_port=filed_data_port,
                year_from=year_from,
                year_to=year_to,
                modelos=modelos,
                operation=indexed_operation,
                effect_guard=effect_guard,
                on_session_write=on_session_write,
            )
    resolved_modelos = modelos if modelos is not None else operation.modelo_ids()
    rows: list[FiledDataListingRow] = []
    query_pairs, failures = _plan_filed_capture_queries(
        resolved_modelos,
        year_from=year_from,
        year_to=year_to,
        operation=operation,
    )

    if not query_pairs:
        return BulkFiledDataListingReport(
            modelos=tuple(resolved_modelos),
            year_from=year_from,
            year_to=year_to,
            row_count=0,
            failed_count=len(failures),
            rows=(),
            failures=tuple(failures),
        )

    async with filed_data_port.open_register(
        operation="live-expedientes-read",
        authority_operation=operation,
        effect_guard=effect_guard,
        on_session_write=on_session_write,
    ) as register:
        for code, year in query_pairs:
            declarations = await _walk_or_failure_row(
                register.walk(modelo=code, ejercicio=year),
                modelo=code,
                year=year,
                timeout_ms=register.walk_timeout_ms,
                failures=failures,
            )
            if declarations is None:
                continue
            rows.extend(filed_data_listing_row(declaration) for declaration in declarations)

    return BulkFiledDataListingReport(
        modelos=tuple(resolved_modelos),
        year_from=year_from,
        year_to=year_to,
        row_count=len(rows),
        failed_count=len(failures),
        rows=tuple(rows),
        failures=tuple(failures),
    )


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
        declarations = await _await_filed_register_walk(
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
    except (ProfileAccessRefusedError, AutomationCustodyError, RuntimeRefusalError):
        raise
    except Exception as exc:
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
    declarations = await _walk_or_failure_row(
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
    query_pairs, failures = _plan_filed_capture_queries(
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


def capture_report_path(path: Path, *, output_root: Path) -> str:
    """Return a stable report path relative to the configured output root when possible."""
    try:
        return path.relative_to(output_root).as_posix()
    except ValueError:
        return str(path)


__all__ = [
    "FiledCaptureAccumulator",
    "capture_filed_data",
    "capture_filed_data_bulk",
    "capture_report_path",
    "capture_source_filed_data",
    "filed_data_capture_failure_row",
    "list_filed_data",
    "list_filed_data_bulk",
    "submitted_file_extraction_notices",
]
