"""Filed-declaration capture services for live AEAT workflows.

The listing helpers read AEAT declaration-register rows without downloading
artefacts. The capture helpers download the selected filed-declaration artefacts
through the authenticated Sede adapter, persist encrypted
:class:`~cadrumo.adapters.outbound.aeat.sede.FiledDeclaracionObservation`
payloads and artefacts, promote extracted casillas into registry-grounded
calculation observations, and attempt to stamp matching current
:class:`~ModeloRecord` filings with live
:class:`~ExternalEvidence`.

Source capture resolves a law-determined
:class:`~cadrumo.domain.calculations.registry.ModeloRevision` (via
:func:`~cadrumo.domain.calculations.registry.load_registry_tree` and
:func:`~cadrumo.domain.calculations.registry.select_revision`, never a filing-grade
:class:`~cadrumo.domain.calculations.registry.ValidatedRegistryAuthority`) before
asking the Sede adapter which prior declarations a target filing needs, so
cross-period inputs remain registry-authored rather than adapter-inferred. The
module never creates a remote submission or mutates AEAT state; filing-record
stamping is local evidence enrollment against an existing current record.

See Also:
    :func:`cadrumo.application.live.session.active_verified_session`
        Enforces the read-only live gate before the register walker is opened.
    :func:`cadrumo.application.live.filed_capture_finalizer.finalize_filed_capture`
        Persists the latest captured filed observations as calculation-history
        evidence, and is the function this module actually calls. Each
        registry-enrollment refusal becomes a typed
        :class:`~application.live.FiledDataCaptureFailureRow`, raised under
        ``FAIL_FAST`` and reported under ``BEST_EFFORT``.
    :func:`cadrumo.application.live.filed_observation_persistence.enroll_filed_justificante_evidence`
        Persists matching justificante metadata and stamps current filing
        records when the receipt matches.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypedDict

from pydantic import BaseModel, Field, field_validator

from ...adapters.outbound.aeat.sede.declarations import DeclaracionesRegisterSession, capture_previous_filing_observations, capture_relation_source_observations, discover_filed_declaration_availability, open_declarations_register, shared_playwright
from ...adapters.outbound.aeat.sede.declarations_schema import Declaracion
from ...adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
from ...adapters.outbound.aeat.sede.schema import FiledDeclaracionObservation, FiledDeclarationAvailabilityReport
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import CasillaValueKind, FiledHistoryDiscoverySignal, RegisterScopingSignal, SyncSurface
from ...core.period import Period
from ...core.casilla_id import CasillaId
from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import load_settings
from ...core.errors.hierarchy import CadrumoError
from ...core.filing_year import FilingYear
from ...core.i18n import tr
from ...core.identity import AeatExpedienteId
from ...core.json_contract import Notice, NoticeSeverity
from ...core.resources import bundled_path
from ...core.time import now
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.bindings import RegistryModeloObservation
from ...domain.calculations.registry.loader import load_registry_tree
from ...domain.calculations.registry.schema import (
    ModeloDefinition,
    ModeloRevision,
)
from ...domain.calculations.registry.temporal import select_revision
from ...domain.calculations.registry.verification_tolerance import verification_tolerance_or_exact
from ..operations.events import OperationLogSeverity
from ..operations.owner import OperationEventEmitter
from ..storage.sync_runs import (
    SyncRunRecordReference,
    SyncRunRecordRepositoryProtocol,
    bounded_scope_description,
    coverage_of,
    record_sync_run,
    sync_run_record_key,
)
from .errors import LiveApplicationInputError, LiveIvaSurfaceTimeoutError
from .filed_capture_finalizer import FiledCaptureFailurePolicy, finalize_filed_capture
from .filed_data import (
    BulkFiledDataListingReport,
    FiledDataListingReport,
    FiledDataListingRow,
    filed_data_listing_row,
    select_declarations_for_capture,
)
from .filed_observation_persistence import (
    enroll_filed_justificante_evidence,
    filed_observation_identity_key,
    import_complete_filed_observation_baseline,
)
from .remote_state_models import (
    BulkFiledDataCaptureReport,
    FiledDataCaptureFailureRow,
    FiledDataCaptureReport,
    SourceFiledDataCaptureReport,
)
from .remote_state_outcomes import bounded_context_text
from .session import active_verified_session

if TYPE_CHECKING:
    from datetime import date

    from ...domain.deadlines.models import TaxpayerProfile
    from ..calculations import CalculationObservationRepository


FILED_HISTORY_PHASE_DISCOVERY = "filed-history.discovery"
FILED_HISTORY_PHASE_REGISTER_ACCESS = "filed-history.register-access"
FILED_HISTORY_PHASE_PAIR_WALK = "filed-history.pair-walk"
FILED_HISTORY_PHASE_DECLARATION_CAPTURE = "filed-history.declaration-capture"
FILED_HISTORY_PHASE_PERSISTENCE = "filed-history.persistence"
FILED_HISTORY_PHASE_FINALIZATION = "filed-history.finalization"
FILED_HISTORY_PHASE_PROVENANCE = "filed-history.provenance"
FILED_HISTORY_PHASE_IVA_WALLET = "filed-history.iva-wallet"
FILED_HISTORY_PHASE_NOTIFICATIONS = "filed-history.notifications"
FILED_HISTORY_PAIR_PROGRESS_UNIT = "filed-history.pair"
FILED_HISTORY_DECLARATION_PROGRESS_UNIT = "filed-history.declaration"
FILED_HISTORY_PAIR_REFUSAL_CODE = "filed-history.refusal.pair"
FILED_HISTORY_DECLARATION_REFUSAL_CODE = "filed-history.refusal.declaration"
FILED_HISTORY_DISCOVERY_REFUSAL_CODE = "filed-history.refusal.discovery"
FILED_HISTORY_IVA_WALLET_REFUSAL_CODE = "filed-history.refusal.iva-wallet"
FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE = "filed-history.refusal.notifications"
FILED_HISTORY_STAGE_REFUSAL_CODE = "filed-history.refusal.stage"


async def _emit_filed_history_phase(events: OperationEventEmitter | None, phase: str) -> None:
    """Publish one operation-declared phase when the composed pull is supervised."""
    if events is not None:
        await events.phase(phase)


async def _emit_filed_history_progress(
    events: OperationEventEmitter | None,
    *,
    completed: int,
    total: int,
    unit_code: str,
) -> None:
    """Publish one bounded safe unit counter without retaining filing identity."""
    if events is not None:
        await events.progress(completed=completed, total=total, unit_code=unit_code)


async def _emit_filed_history_refusal(events: OperationEventEmitter | None, code: str) -> None:
    """Publish only a stable failure scope, never local exception prose."""
    if events is not None:
        await events.log(code=code, severity=OperationLogSeverity.WARNING)


def filed_data_capture_failure_row(
    *,
    modelo: str,
    year: int,
    error: BaseException,
    declaration: Declaracion | None = None,
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
    definition: ModeloDefinition,
    *,
    year: int,
) -> tuple[ModeloRevision, ...]:
    """Return this modelo's revisions that cover the requested filing year."""
    return tuple(revision for revision in definition.revisions.values() if revision.period_selector.includes_year(year))


def _declares_filed_declarations_read_surface(revisions: Sequence[ModeloRevision]) -> bool:
    """Whether a covering registry revision authorizes the declarations-register read."""
    return any(
        ref.surface == "authenticated_read_surface" and ref.id.endswith("filed-declarations-read")
        for revision in revisions
        for ref in revision.live_cross_references
    )


def _registered_modelo_definition(modelo: str) -> ModeloDefinition | None:
    """Look up a registry modelo with the registry's existing duplicate-key resolution."""
    return {str(definition.id): definition for definition in bundled_authority().modelos}.get(modelo)


def _filed_capture_unsupported_reason(*, modelo: str, year: int) -> str | None:
    definition = _registered_modelo_definition(modelo)
    if definition is None:
        return f"registry has no modelo definition for {modelo!r}"
    revisions = _filed_capture_revisions_for_year(definition, year=year)
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
    query_pairs: list[tuple[str, int]] = []
    failures: list[FiledDataCaptureFailureRow] = []
    for code in resolved_modelos:
        for year in range(year_to, year_from - 1, -1):
            unsupported_reason = _filed_capture_unsupported_reason(modelo=code, year=year)
            if unsupported_reason is not None:
                failures.append(
                    _unsupported_filed_capture_failure_row(modelo=code, year=year, reason=unsupported_reason),
                )
                continue
            query_pairs.append((code, year))
    return query_pairs, failures


async def _await_filed_register_walk(
    awaitable: Awaitable[tuple[Declaracion, ...]],
    *,
    modelo: str,
    year: int,
    timeout_ms: int,
) -> tuple[Declaracion, ...]:
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


@asynccontextmanager
async def _resolved_declarations_register(
    register: DeclaracionesRegisterSession | None,
    *,
    operation: str,
) -> AsyncGenerator[tuple[DeclaracionesRegisterSession, int]]:
    """Yield an open register plus its walk timeout, resolving a session only when needed.

    Shared by :func:`list_filed_data_bulk` and :func:`capture_filed_data_bulk`.
    With no ``register`` supplied this is exactly what both functions did inline:
    resolve a verified session, amortise one Playwright instance across the sweep,
    and open the register against it.

    An already-open register short-circuits SESSION RESOLUTION, which is the only
    thing it can usefully bypass. The browser itself is reachable offline through
    route interception with no production change at all; what is not reachable is
    :func:`active_verified_session`, because it runs the live-read access gate and
    then drives the central live-session writer, which wants an active bucket and
    real credentials. Satisfying that gate to reach this code would ARM real AEAT
    access, so the seam exists to let a caller never request live access at all.
    The walk timeout still comes from :func:`load_settings`, which reads local
    deployment configuration and contacts nothing.
    """
    if register is not None:
        yield register, load_settings().cadrumo_live_filed_register_walk_timeout_ms
        return
    session, settings = await active_verified_session(operation=operation)
    async with (
        shared_playwright(session) as playwright,
        open_declarations_register(session, settings=settings, playwright=playwright) as opened,
    ):
        yield opened, settings.cadrumo_live_filed_register_walk_timeout_ms


async def _walk_or_failure_row(
    awaitable: Awaitable[tuple[Declaracion, ...]],
    *,
    modelo: str,
    year: int,
    timeout_ms: int,
    failures: list[FiledDataCaptureFailureRow],
) -> tuple[Declaracion, ...] | None:
    """Absorb one modelo/year register query's failure into a row, or return its rows.

    Takes the walk awaitable rather than the register that produces it: the
    register was only ever used to build this one coroutine, so the narrower
    parameter drops a dependency the helper never needed and lets the absorption
    arm be exercised with a real coroutine, the way the sibling
    :func:`_await_filed_register_walk` already is.

    Shared bulk-path arm behind :func:`list_filed_data_bulk` and
    :func:`capture_filed_data_bulk`: on any walk failure the exception is folded
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
    except Exception as exc:
        failures.append(filed_data_capture_failure_row(modelo=modelo, year=year, error=exc))
        return None


FILED_SUBMITTED_FILE_EXTRACTION_NOTICE_CODE = "live.filed.pull.submitted_file_extraction_failed"
_SUBMITTED_FILE_EXTRACTION_ERROR_METADATA_KEY = "submitted_file_extraction_error"


def submitted_file_extraction_notices(observation: FiledDeclaracionObservation) -> tuple[Notice, ...]:
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
                default=(
                    "Modelo {modelo} filing {period} {ejercicio} (expediente {expediente_id}) could not be "
                    "read through its submitted-file layout. The declaration-PDF fallback, if AEAT provided it, "
                    "remains the only extraction path. Parser reason: {reason}"
                ),
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


@dataclass(slots=True)
class _CaptureAccumulator:
    """Mutable accumulator for one filed-declaration capture run.

    Holds the persisted-artefact ledgers shared by the single-shot, bulk, and
    source capture paths. :meth:`absorb` folds one captured observation into the
    run (persist manifest, collect artefact refs, enrol justificante evidence,
    stamp filing records); :meth:`capture_report_fields` projects the deduped
    report fields every capture report shares. The ``dict.fromkeys`` dedup
    ordering is preserved verbatim so report values stay byte-identical.
    """

    observation_paths: list[str] = field(default_factory=list)
    artefact_refs: list[str] = field(default_factory=list)
    justificante_csvs: list[str] = field(default_factory=list)
    filing_record_ids: list[str] = field(default_factory=list)
    conflicting_filing_record_ids: list[str] = field(default_factory=list)
    observations_for_calculation: list[FiledDeclaracionObservation] = field(default_factory=list)
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
        observation: FiledDeclaracionObservation,
        *,
        store: FiledDeclaracionObservationStore,
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
        self.recapture_notices.extend(recapture_divergence_notices((observation,)))
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
        manifest_path = store.persist_observation(observation)
        self.observation_paths.append(capture_report_path(manifest_path, output_root=output_root))
        self.artefact_refs.extend(
            storage_ref
            for artefact in observation.artefacts
            for storage_ref in (artefact.storage_ref,)
            if storage_ref is not None
        )
        enrollment = enroll_filed_justificante_evidence(observation, store=store, bucket_id=bucket_id)
        self.justificante_csvs.extend(enrollment.justificante_csvs)
        self.justificante_csvs_by_observation[filed_observation_identity_key(observation)] = (
            enrollment.justificante_csvs
        )
        self.filing_record_ids.extend(enrollment.filing_record_ids)
        self.conflicting_filing_record_ids.extend(enrollment.conflicting_filing_record_ids)
        # The enrolment already produced one typed WARNING per artefact that
        # yielded no evidence, each naming its own reason. They were being
        # discarded here, which is what let a capture extract casillas and report
        # zero justificante evidence with no visible cause. Collected verbatim --
        # never merged -- because two distinguishable dead ends folded into one
        # notice recreates the collapse the reasons exist to undo.
        self.evidence_notices.extend(enrollment.notices)
        imported_baseline = import_complete_filed_observation_baseline(
            observation,
            bucket_id=bucket_id,
            justificante_csvs=enrollment.justificante_csvs,
        )
        if imported_baseline is not None:
            self.filing_record_ids.append(imported_baseline.filing_record_id)
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
        }


async def list_filed_data(
    *,
    modelo: str,
    year_from: int,
    year_to: int,
) -> FiledDataListingReport:
    """List declarations via AEAT and return a :class:`FiledDataListingReport`."""
    if year_from > year_to:
        raise LiveApplicationInputError(
            translated_message="live.errors.year_range_invalid",
        )

    session, settings = await active_verified_session(operation="live-expedientes-read")
    walk_timeout_ms = settings.cadrumo_live_filed_register_walk_timeout_ms
    rows: list[FiledDataListingRow] = []
    async with (
        shared_playwright(session) as playwright,
        open_declarations_register(
            session,
            settings=settings,
            playwright=playwright,
        ) as register,
    ):
        for year in range(year_to, year_from - 1, -1):
            declarations = await _await_filed_register_walk(
                register.walk(modelo=modelo, ejercicio=year),
                modelo=modelo,
                year=year,
                timeout_ms=walk_timeout_ms,
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
    year_from: int,
    year_to: int,
    modelos: tuple[str, ...] | None = None,
    register: DeclaracionesRegisterSession | None = None,
) -> BulkFiledDataListingReport:
    """List filed declarations across modelos with one authenticated register session.

    Args:
        year_from: First filing year to query.
        year_to: Last filing year to query.
        modelos: Modelo codes to walk; every registry modelo when omitted.
        register: An already-open register to walk instead of resolving a session,
            per :func:`_resolved_declarations_register`. Omitted by every
            production caller, which keeps the session-resolving path.

    Returns:
        A :class:`BulkFiledDataListingReport` of the per-modelo rows and failures.
    """
    if year_from > year_to:
        raise LiveApplicationInputError(
            translated_message="live.errors.year_range_invalid",
        )

    resolved_modelos = modelos if modelos is not None else tuple(str(m.id) for m in bundled_authority().modelos)
    rows: list[FiledDataListingRow] = []
    query_pairs, failures = _plan_filed_capture_queries(resolved_modelos, year_from=year_from, year_to=year_to)

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

    async with _resolved_declarations_register(register, operation="live-expedientes-read") as (
        opened_register,
        walk_timeout_ms,
    ):
        for code, year in query_pairs:
            declarations = await _walk_or_failure_row(
                opened_register.walk(modelo=code, ejercicio=year),
                modelo=code,
                year=year,
                timeout_ms=walk_timeout_ms,
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
    modelo: str,
    year: int,
    output_root: Path,
    period: Period | None = None,
    expediente_id: str | None = None,
    limit: int | None = None,
) -> FiledDataCaptureReport:
    """Capture filed-declaration artefacts and return a :class:`FiledDataCaptureReport`.

    The report accounts for persisted observation manifests, encrypted artefact
    references, saved justificante CSVs, stamped
    :class:`~ModeloRecord` ids, conflicts, and calculation
    observation keys produced from the captured AEAT rows.
    """
    session, settings = await active_verified_session()
    walk_timeout_ms = settings.cadrumo_live_filed_register_walk_timeout_ms
    store = FiledDeclaracionObservationStore(output_root)
    accumulator = _CaptureAccumulator()
    bucket_id = require_active_bucket_id()

    async with (
        shared_playwright(session) as playwright,
        open_declarations_register(
            session,
            playwright=playwright,
        ) as register,
    ):
        declarations = await _await_filed_register_walk(
            register.walk(modelo=modelo, ejercicio=year),
            modelo=modelo,
            year=year,
            timeout_ms=walk_timeout_ms,
        )
        selected = select_declarations_for_capture(
            declarations,
            period=period,
            expediente_id=expediente_id,
            limit=limit,
        )
        for declaration in selected:
            observation = await register.capture_observation(
                declaration,
                artefact_sink=store.persist_artefact,
            )
            accumulator.absorb(observation, store=store, bucket_id=bucket_id, output_root=output_root)

    finalization = finalize_filed_capture(
        tuple(accumulator.observations_for_calculation),
        justificante_csvs_by_observation=accumulator.justificante_csvs_by_observation,
        policy=FiledCaptureFailurePolicy.FAIL_FAST,
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
    declarations: tuple[Declaracion, ...],
    *,
    limit: int | None,
    reached_count: int,
) -> tuple[Declaracion, ...] | None:
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


async def _absorb_declarations(
    declarations: tuple[Declaracion, ...],
    *,
    opened_register: DeclaracionesRegisterSession,
    accumulator: _CaptureAccumulator,
    store: FiledDeclaracionObservationStore,
    bucket_id: str,
    output_root: Path,
    dry_run: bool,
    modelo: str,
    year: int,
    failures: list[FiledDataCaptureFailureRow],
    events: OperationEventEmitter | None = None,
) -> None:
    """Capture and absorb one batch, recording a per-declaration failure as a row.

    One declaration's capture failure is absorbed into ``failures`` and the walk
    continues: a single unreadable expediente must not abandon the rest of the
    sweep.
    """
    declaration_total = len(declarations)
    if not declaration_total:
        return
    await _emit_filed_history_progress(
        events,
        completed=0,
        total=declaration_total,
        unit_code=FILED_HISTORY_DECLARATION_PROGRESS_UNIT,
    )
    for declaration_completed, declaration in enumerate(declarations, start=1):
        try:
            observation = await opened_register.capture_observation(
                declaration,
                artefact_sink=None if dry_run else store.persist_artefact,
            )
        except Exception as exc:
            failures.append(
                filed_data_capture_failure_row(
                    modelo=modelo,
                    year=year,
                    declaration=declaration,
                    error=exc,
                ),
            )
            await _emit_filed_history_refusal(events, FILED_HISTORY_DECLARATION_REFUSAL_CODE)
        else:
            accumulator.absorb(
                observation,
                store=store,
                bucket_id=bucket_id,
                output_root=output_root,
                dry_run=dry_run,
            )
        await _emit_filed_history_progress(
            events,
            completed=declaration_completed,
            total=declaration_total,
            unit_code=FILED_HISTORY_DECLARATION_PROGRESS_UNIT,
        )


def _empty_bulk_filed_capture_report(
    *,
    output_root: Path,
    modelos: Sequence[str],
    year_from: int,
    year_to: int,
    failures: Sequence[FiledDataCaptureFailureRow],
) -> BulkFiledDataCaptureReport:
    """Build the local-boundary result when no pair can reach the register."""
    return BulkFiledDataCaptureReport(
        output_root=str(output_root),
        modelos=tuple(modelos),
        year_from=year_from,
        year_to=year_to,
        captured_count=0,
        reached_count=0,
        failed_count=len(failures),
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
    )


async def _capture_filed_data_query_pairs(
    query_pairs: Sequence[tuple[str, int]],
    *,
    register: DeclaracionesRegisterSession | None,
    accumulator: _CaptureAccumulator,
    store: FiledDeclaracionObservationStore,
    bucket_id: str,
    output_root: Path,
    limit: int | None,
    dry_run: bool,
    failures: list[FiledDataCaptureFailureRow],
    events: OperationEventEmitter | None = None,
    pair_completed: int = 0,
    pair_total: int | None = None,
) -> int:
    """Walk, cap, and absorb every queryable pair in canonical sweep order."""
    total = pair_total if pair_total is not None else len(query_pairs)
    await _emit_filed_history_phase(events, FILED_HISTORY_PHASE_REGISTER_ACCESS)
    await _emit_filed_history_phase(events, FILED_HISTORY_PHASE_PAIR_WALK)
    declaration_capture_started = False
    persistence_started = False
    async with _resolved_declarations_register(register, operation="live-expedientes-read") as (
        opened_register,
        walk_timeout_ms,
    ):
        for code, year in query_pairs:
            declarations = await _walk_or_failure_row(
                opened_register.walk(modelo=code, ejercicio=year),
                modelo=code,
                year=year,
                timeout_ms=walk_timeout_ms,
                failures=failures,
            )
            pair_completed += 1
            if declarations is None:
                await _emit_filed_history_refusal(events, FILED_HISTORY_PAIR_REFUSAL_CODE)
            await _emit_filed_history_progress(
                events,
                completed=pair_completed,
                total=total,
                unit_code=FILED_HISTORY_PAIR_PROGRESS_UNIT,
            )
            if declarations is None:
                continue
            within_limit = _declarations_within_limit(
                declarations,
                limit=limit,
                reached_count=accumulator.reached_count,
            )
            if within_limit is None:
                return pair_completed
            if within_limit:
                if not declaration_capture_started:
                    await _emit_filed_history_phase(events, FILED_HISTORY_PHASE_DECLARATION_CAPTURE)
                    declaration_capture_started = True
                if not dry_run and not persistence_started:
                    await _emit_filed_history_phase(events, FILED_HISTORY_PHASE_PERSISTENCE)
                    persistence_started = True
            await _absorb_declarations(
                within_limit,
                opened_register=opened_register,
                accumulator=accumulator,
                store=store,
                bucket_id=bucket_id,
                output_root=output_root,
                dry_run=dry_run,
                modelo=code,
                year=year,
                failures=failures,
                events=events,
            )
            if limit is not None and accumulator.reached_count >= limit:
                return pair_completed
    return pair_completed


def _dry_run_bulk_filed_capture_report(
    *,
    output_root: Path,
    modelos: Sequence[str],
    year_from: int,
    year_to: int,
    accumulator: _CaptureAccumulator,
    failures: Sequence[FiledDataCaptureFailureRow],
) -> BulkFiledDataCaptureReport:
    """Project the read-only bulk result without reaching any persistence finalizer."""
    return BulkFiledDataCaptureReport(
        output_root=str(output_root),
        modelos=tuple(modelos),
        year_from=year_from,
        year_to=year_to,
        failed_count=len(failures),
        **accumulator.capture_report_fields(),
        calculation_observation_count=0,
        calculation_observation_keys=(),
        failures=tuple(failures),
        recapture_notices=tuple(accumulator.recapture_notices),
        dry_run=True,
    )


def _persisted_bulk_filed_capture_report(
    *,
    output_root: Path,
    modelos: Sequence[str],
    year_from: int,
    year_to: int,
    accumulator: _CaptureAccumulator,
    failures: list[FiledDataCaptureFailureRow],
    bucket_id: str,
    sync_run_repository: SyncRunRecordRepositoryProtocol,
) -> BulkFiledDataCaptureReport:
    """Finalize persisted observations, then record the completed sweep provenance."""
    finalization = finalize_filed_capture(
        tuple(accumulator.observations_for_calculation),
        justificante_csvs_by_observation=accumulator.justificante_csvs_by_observation,
        policy=FiledCaptureFailurePolicy.BEST_EFFORT,
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
    return BulkFiledDataCaptureReport(
        output_root=str(output_root),
        modelos=tuple(modelos),
        year_from=year_from,
        year_to=year_to,
        failed_count=len(failures),
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


async def capture_filed_data_bulk(
    *,
    year_from: int,
    year_to: int,
    output_root: Path,
    modelos: tuple[str, ...] | None = None,
    limit: int | None = None,
    register: DeclaracionesRegisterSession | None = None,
    dry_run: bool = False,
    sync_run_repository: SyncRunRecordRepositoryProtocol | None = None,
    events: OperationEventEmitter | None = None,
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
        modelos: Modelo codes to walk; every registry modelo when omitted.
        limit: Cap on captured observations; unbounded when omitted.
        register: An already-open register to walk instead of resolving a session,
            per :func:`_resolved_declarations_register`. Omitted by every
            production caller, which keeps the session-resolving path.
        dry_run: Preview the sweep. AEAT is still read and the divergence set
            the upsert would introduce is still computed, but nothing is
            written: no observation persisted, no justificante evidence
            enrolled, no calculation observation finalized. The report carries
            ``dry_run=True`` and the divergences as its primary result.
        sync_run_repository: Persistence port for the completed-run provenance
            record. Required for a non-preview capture that reaches a supported
            query pair; the outer entrypoint composes the concrete adapter.
        events: Optional operation event emitter. The composed filed-history
            pull supplies it to publish phase, safe unit-count, and refusal-scope
            facts at the canonical workflow boundaries.
    """
    if year_from > year_to:
        raise LiveApplicationInputError(
            translated_message="live.errors.year_range_invalid",
        )

    resolved_modelos = modelos if modelos is not None else tuple(str(m.id) for m in bundled_authority().modelos)
    store = FiledDeclaracionObservationStore(output_root)
    accumulator = _CaptureAccumulator()
    query_pairs, failures = _plan_filed_capture_queries(resolved_modelos, year_from=year_from, year_to=year_to)
    pair_total = len(query_pairs) + len(failures)
    if pair_total:
        await _emit_filed_history_progress(
            events,
            completed=0,
            total=pair_total,
            unit_code=FILED_HISTORY_PAIR_PROGRESS_UNIT,
        )
    for _failure in failures:
        await _emit_filed_history_refusal(events, FILED_HISTORY_PAIR_REFUSAL_CODE)
    if failures:
        await _emit_filed_history_progress(
            events,
            completed=len(failures),
            total=pair_total,
            unit_code=FILED_HISTORY_PAIR_PROGRESS_UNIT,
        )

    if not query_pairs:
        return _empty_bulk_filed_capture_report(
            output_root=output_root,
            modelos=resolved_modelos,
            year_from=year_from,
            year_to=year_to,
            failures=failures,
        )

    if not dry_run and sync_run_repository is None:
        raise LiveApplicationInputError(
            translated_message="application.live.filed_data.errors.sync_run_repository_required",
            context={"dry_run": dry_run, "sync_run_repository_present": False},
        )

    bucket_id = require_active_bucket_id()

    await _capture_filed_data_query_pairs(
        query_pairs,
        register=register,
        accumulator=accumulator,
        store=store,
        bucket_id=bucket_id,
        output_root=output_root,
        limit=limit,
        dry_run=dry_run,
        failures=failures,
        events=events,
        pair_completed=len(failures),
        pair_total=pair_total,
    )

    if dry_run:
        return _dry_run_bulk_filed_capture_report(
            output_root=output_root,
            modelos=resolved_modelos,
            year_from=year_from,
            year_to=year_to,
            accumulator=accumulator,
            failures=failures,
        )
    if sync_run_repository is None:
        raise LiveApplicationInputError(
            translated_message="application.live.filed_data.errors.sync_run_repository_required",
            context={"dry_run": dry_run, "sync_run_repository_present": False},
        )
    await _emit_filed_history_phase(events, FILED_HISTORY_PHASE_FINALIZATION)
    await _emit_filed_history_phase(events, FILED_HISTORY_PHASE_PROVENANCE)
    return _persisted_bulk_filed_capture_report(
        output_root=output_root,
        modelos=resolved_modelos,
        year_from=year_from,
        year_to=year_to,
        accumulator=accumulator,
        failures=failures,
        bucket_id=bucket_id,
        sync_run_repository=sync_run_repository,
    )


async def capture_source_filed_data(
    *,
    modelo: str,
    year: int,
    period: Period,
    output_root: Path,
    registry_root: Path | None = None,
    source_root: Path | None = None,
) -> SourceFiledDataCaptureReport:
    """Capture source observations and return a :class:`SourceFiledDataCaptureReport`.

    Reads the target revision structurally (:func:`load_registry_tree` +
    :func:`select_revision`) rather than through
    :class:`~cadrumo.domain.calculations.registry.ValidatedRegistryAuthority`:
    this capture only ever needs the revision's declared casilla/binding
    structure, never a filing-grade admission. ``source_root`` is accepted for
    caller-signature compatibility but is unused here -- the structural read
    resolves no evidence catalogue and never needed it.
    """
    session, settings = await active_verified_session()
    modelos, _catalogues = load_registry_tree(registry_root or bundled_path("registry", "aeat"))
    modelo_definition = next(candidate for candidate in modelos if candidate.id == modelo)
    revision = select_revision(
        modelo_definition,
        filing_year=year,
        period=period.registry_token,
    )
    store = FiledDeclaracionObservationStore(output_root)
    accumulator = _CaptureAccumulator()
    seen: set[tuple[str, int, str, str]] = set()
    bucket_id = require_active_bucket_id()

    async with shared_playwright(session) as playwright:
        observations = (
            await capture_previous_filing_observations(
                session,
                revision,
                filing_year=year,
                period=period,
                settings=settings,
                playwright=playwright,
                artefact_sink=store.persist_artefact,
            )
        ) + (
            await capture_relation_source_observations(
                session,
                revision,
                filing_year=year,
                period=period,
                settings=settings,
                playwright=playwright,
                artefact_sink=store.persist_artefact,
            )
        )
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
        accumulator.absorb(observation, store=store, bucket_id=bucket_id, output_root=output_root)

    finalization = finalize_filed_capture(
        tuple(accumulator.observations_for_calculation),
        justificante_csvs_by_observation=accumulator.justificante_csvs_by_observation,
        policy=FiledCaptureFailurePolicy.FAIL_FAST,
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


async def discover_filed_history(
    *,
    profile: TaxpayerProfile | None = None,
    today: date | None = None,
) -> FiledHistoryDiscoveryReport:
    """Discover what history to walk, unioning both signals into one grid.

    Reads the register's offered option lists through the SAME verified-session
    bring-up every filed-capture path uses, so a missing or unverified auth
    session refuses here exactly as it does on the capture path rather than with
    a discovery-specific error nobody has seen before.

    Nothing is persisted and no pair is queried: this is a read of the register's
    own controls plus a pure derivation over already-persisted profile data.

    ``profile`` is optional so the register-options read can be exercised on its
    own, but omitting it means the report carries NO taxpayer-specific
    denominator — see
    :attr:`FiledHistoryDiscoveryReport.carries_a_taxpayer_specific_denominator`,
    which is the flag a caller must check before making any coverage claim.

    Args:
        profile: The taxpayer's declared :class:`TaxpayerProfile`, supplying the load-bearing
            :attr:`~core.FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY`
            signal. ``None`` yields a register-options-only report.
        today: Reference date for applicability and the year span's upper bound.
            Defaults to the Madrid civil date the rest of the CLI resolves
            filing dates against.

    Returns:
        The union :class:`FiledHistoryDiscoveryReport`.

    Raises:
        SedeNavigationError: When the session carries no persisted browser state,
            propagated unchanged from the shared register bring-up.
    """
    from ...core.time import today_madrid

    session, settings = await active_verified_session(operation="live-expedientes-read")
    async with shared_playwright(session) as playwright:
        availability = await discover_filed_declaration_availability(
            session,
            settings=settings,
            playwright=playwright,
        )
    expected = (
        expected_filed_declaration_grid(profile, today=today or today_madrid())
        if profile is not None
        else ExpectedFiledDeclarationGrid()
    )
    return filed_history_discovery_report(expected=expected, availability=availability)


class ExpectedFiledDeclarationGrid(BaseModel):
    """The ``(modelo, ejercicio)`` pairs the taxpayer's OWN declared facts expect.

    Tagged :attr:`~core.FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY`. This
    is the load-bearing denominator: every value in it comes from data the
    taxpayer declared during setup, walked through the same applicability
    machinery the overview calendar already reconciles obligations with, so it is
    taxpayer-specific by construction and needs no authenticated session.

    Attributes:
        modelos: Registry modelos this profile's declared facts do not rule out,
            in sorted order. A modelo the applicability engine positively
            answers "no" for is absent, and so is one the registry does not model
            at all — the latter because no declared fact feeds a verdict for it,
            so nominating it would manufacture an expectation the profile never
            made.
        ejercicios: The filing years spanned by the declared activity dates,
            newest first.
        activity_start_declared: Whether the profile declared an
            ``activity_start_date``. When ``False``, ``ejercicios`` is EMPTY and
            this grid makes no claim: it is "cannot say", never "nothing
            expected". A consumer must surface that distinction rather than
            reporting a clean zero, because a silently empty profile signal
            leaves only the signal whose informativeness is unconfirmed.
        activity_end_declared: Whether the profile declared an
            ``activity_end_date``, which caps the span. A taxpayer who ceased
            activity is not expected to have filed afterwards, and flagging
            those years as expected-but-not-found would be a false anomaly.
    """

    model_config = _STRICT_FROZEN

    modelos: tuple[str, ...] = ()
    ejercicios: tuple[int, ...] = ()
    activity_start_declared: bool = False
    activity_end_declared: bool = False

    @property
    def pairs(self) -> tuple[tuple[str, int], ...]:
        """Return every expected ``(modelo, ejercicio)`` pair, newest year first."""
        return tuple((modelo, ejercicio) for modelo in self.modelos for ejercicio in self.ejercicios)


class FiledHistoryDiscoveryPair(BaseModel):
    """One ``(modelo, ejercicio)`` pair to walk, carrying which signal nominated it.

    The signal set is what makes a zero-row outcome readable, so it travels with
    the pair rather than being discarded once the union is built. The two
    predicates below exist so no consumer re-derives the asymmetry: a caller asks
    the pair whether a zero-row result is an anomaly instead of re-checking tags
    and possibly getting the rule wrong in one of several places.

    Attributes:
        modelo: Modelo code.
        ejercicio: Filing year.
        signals: Every signal that nominated this pair, in the canonical enum
            declaration order, deduplicated. Never empty — a pair nominated by
            nothing is not walked.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    ejercicio: FilingYear
    signals: tuple[FiledHistoryDiscoverySignal, ...] = Field(min_length=1)

    @field_validator("signals")
    @classmethod
    def _canonical_signal_order(
        cls,
        value: tuple[FiledHistoryDiscoverySignal, ...],
    ) -> tuple[FiledHistoryDiscoverySignal, ...]:
        """Dedup and canonicalise the signal set so equal nominations compare equal."""
        seen = set(value)
        return tuple(signal for signal in FiledHistoryDiscoverySignal if signal in seen)

    @property
    def expected_by_profile(self) -> bool:
        """Whether the taxpayer's own declared facts expected a filing for this pair."""
        return FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY in self.signals

    @property
    def zero_rows_is_an_anomaly(self) -> bool:
        """Whether finding no declaración for this pair is worth an advisory.

        True only when the profile signal nominated the pair: the taxpayer's own
        declared facts expected a filing that was not found. A pair nominated
        ONLY by the register's option list is a plain negative however empty it
        comes back, because whether that list is scoped to this NIF at all is
        unconfirmed — treating its emptiness as a finding would raise an alert
        from a signal that may carry no information about this taxpayer.
        """
        return self.expected_by_profile


class FiledHistoryDiscoveryReport(BaseModel):
    """The union walk grid, with every pair tagged by the signal(s) behind it.

    The union is deliberately additive: the register's offered option set can
    only ever WIDEN the grid the profile expects, never narrow it and never
    substitute for it. That is why a pair present in only one signal is still
    walked, while only the profile-nominated ones can produce an anomaly.

    Attributes:
        pairs: Every pair to walk, sorted by modelo then descending ejercicio so
            recent filings are reached first.
        profile_year_span_determined: Whether the profile declared the activity
            start date the year axis needs. When ``False`` the profile signal
            contributed nothing and the report says so, rather than presenting a
            register-options-only grid as though both signals had agreed.
        register_options_read: Whether the register's option lists were read at
            all. ``False`` on the profile-only path (no live session), which is
            not a failure — the design ships fully functional without it.
    """

    model_config = _STRICT_FROZEN

    pairs: tuple[FiledHistoryDiscoveryPair, ...] = ()
    profile_year_span_determined: bool = False
    register_options_read: bool = False

    @property
    def walk_pairs(self) -> tuple[tuple[str, int], ...]:
        """Return the plain ``(modelo, ejercicio)`` pairs to query, in walk order."""
        return tuple((pair.modelo, pair.ejercicio) for pair in self.pairs)

    @property
    def profile_expected_pairs(self) -> tuple[FiledHistoryDiscoveryPair, ...]:
        """Return only the pairs the taxpayer's declared facts expected a filing for."""
        return tuple(pair for pair in self.pairs if pair.expected_by_profile)

    @property
    def register_options_only_pairs(self) -> tuple[FiledHistoryDiscoveryPair, ...]:
        """Return the pairs nominated ONLY by the unconfirmed register option list."""
        return tuple(pair for pair in self.pairs if not pair.expected_by_profile)

    @property
    def carries_a_taxpayer_specific_denominator(self) -> bool:
        """Whether any coverage claim this report supports rests on taxpayer facts.

        ``False`` means every walked pair came from the register's offered option
        list, whose scoping is unconfirmed, so the report supports NO completeness
        claim at all — only a record of what was queried.
        """
        return bool(self.profile_expected_pairs)


def expected_filed_declaration_grid(
    profile: TaxpayerProfile,
    *,
    today: date,
) -> ExpectedFiledDeclarationGrid:
    """Derive the taxpayer-specific candidate grid from the profile's declared facts.

    The modelo axis reuses
    :func:`~application.overview.build_obligation_coverage`, which already
    partitions the whole AEAT obligation universe against a
    :class:`~domain.deadlines.TaxpayerProfile` into surfaced / confidently
    excluded / advised / out-of-scope. Nothing is re-derived here: a modelo is a
    candidate when that partition does NOT place it in a confident negative or
    out of scope.

    Two exclusions are deliberate. A modelo the registry does not model at all
    is dropped, because no declared fact produced its verdict — nominating it
    would invent an expectation the taxpayer never made and then report the
    inevitable zero rows as an anomaly. And the year axis is capped by a declared
    ``activity_end_date``, because a taxpayer who ceased activity is not expected
    to have filed afterwards.

    ``surfaced_modelos`` is passed empty on purpose. The partition is total, so
    with nothing surfaced every non-negative verdict lands in ``advised``; the
    union taken below covers both tuples anyway, so the result does not depend on
    which side a candidate falls out of.

    Args:
        profile: The taxpayer's declared three-axis :class:`TaxpayerProfile`.
        today: Reference date for applicability evaluation and the year span's
            upper bound.

    Returns:
        The :class:`ExpectedFiledDeclarationGrid`. When the profile declared no
        activity start date the grid carries no ejercicios and says so through
        ``activity_start_declared``.
    """
    # Deferred to keep application.live's import-time graph free of the overview
    # package, which reaches back into this package for its evidence snapshots.
    # The same reason _coverage.py defers its own application.modelo lookup.
    from ..overview.coverage import CoverageAdviceReason, build_obligation_coverage

    coverage = build_obligation_coverage(profile, (), today=today)
    candidates = {
        *coverage.surfaced,
        *(item.modelo for item in coverage.advised if item.reason is not CoverageAdviceReason.REGISTRY_UNMODELED),
    }

    start = profile.activity_start_date
    end = profile.activity_end_date
    if start is None:
        ejercicios: tuple[int, ...] = ()
    else:
        last_year = min(today.year, end.year) if end is not None else today.year
        ejercicios = tuple(range(last_year, start.year - 1, -1))

    return ExpectedFiledDeclarationGrid(
        modelos=tuple(sorted(candidates)),
        ejercicios=ejercicios,
        activity_start_declared=start is not None,
        activity_end_declared=end is not None,
    )


class FiledPeriodSelectionRow(BaseModel):
    """How many register rows one period offered, versus the one that was kept.

    The register can carry several filings for a single period -- an original and
    its later amendments -- and exactly one is promoted to calculation history by
    the shared selection authority. That collapse is correct and is not reported
    anywhere today, so an operator seeing one persisted observation cannot tell
    whether AEAT held one filing or four.

    Computed from the tuples the sweep already holds before finalisation, so it
    touches no persistence boundary and adds no read.

    Attributes:
        modelo: Modelo code.
        ejercicio: Filing year.
        period: Registry period token.
        raw_row_count: Rows the register returned for the period.
        selected_count: Observations actually captured from them.
        winning_expediente_id: The expediente whose filing was kept, when known.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    ejercicio: FilingYear
    period: str = Field(min_length=1, max_length=8)
    raw_row_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    winning_expediente_id: AeatExpedienteId | None = None

    @property
    def held_more_than_one_filing(self) -> bool:
        """Whether the register itself offered more than one filing for this period.

        Keyed on the RAW count alone, deliberately. Deriving it from
        ``raw_row_count - selected_count`` conflates two different facts: a period
        AEAT held several filings for, and a period whose single filing was not
        captured (a per-row failure, or a ``limit`` cut). The second is not
        supersession, and reporting it as such would tell the operator their
        filing was superseded by one that never existed.
        """
        return self.raw_row_count > 1

    @property
    def superseded_count(self) -> int:
        """Return how many of the period's filings the kept one displaced.

        Zero when nothing was captured: with no winner, no filing was superseded
        — the rows are simply unaccounted for, which the count mismatch between
        :attr:`raw_row_count` and :attr:`selected_count` already shows.
        """
        if self.selected_count == 0:
            return 0
        return max(self.raw_row_count - self.selected_count, 0)

    @property
    def rows_not_accounted_for(self) -> int:
        """Return rows the register returned that produced no observation at all.

        Distinct from :attr:`superseded_count`: this is the count that needs
        explaining, not the count the selection authority deliberately collapsed.
        """
        return max(self.raw_row_count - self.selected_count, 0) if self.selected_count == 0 else 0


def filed_period_selection_rows(
    declarations_by_pair: Mapping[tuple[str, int], tuple[Declaracion, ...]],
    selected: tuple[FiledDeclaracionObservation, ...],
) -> tuple[FiledPeriodSelectionRow, ...]:
    """Project raw register rows against the observations actually captured.

    Keyed on ``(modelo, ejercicio, period)`` because the collapse the sweep
    performs is per PERIOD, not per pair: one ``(modelo, ejercicio)`` query can
    return several periods, each with its own duplicate count.

    Args:
        declarations_by_pair: The register rows each walked pair returned.
        selected: The observations captured from them.

    Returns:
        One row per period the register returned rows for, in modelo then
        descending-ejercicio then period order.
    """
    raw: dict[tuple[str, int, str], int] = {}
    for (modelo, ejercicio), declarations in declarations_by_pair.items():
        for declaration in declarations:
            raw[(modelo, ejercicio, declaration.period.registry_token)] = (
                raw.get((modelo, ejercicio, declaration.period.registry_token), 0) + 1
            )
    kept: dict[tuple[str, int, str], list[FiledDeclaracionObservation]] = {}
    for observation in selected:
        kept.setdefault(
            (observation.modelo, observation.ejercicio, observation.period.registry_token),
            [],
        ).append(observation)

    return tuple(
        FiledPeriodSelectionRow(
            modelo=modelo,
            ejercicio=ejercicio,
            period=period,
            raw_row_count=count,
            selected_count=len(kept.get((modelo, ejercicio, period), ())),
            winning_expediente_id=(
                kept[(modelo, ejercicio, period)][0].expediente_id if (modelo, ejercicio, period) in kept else None
            ),
        )
        for (modelo, ejercicio, period), count in sorted(
            raw.items(), key=lambda item: (item[0][0], -item[0][1], item[0][2])
        )
    )


def casillas_a_recapture_would_change(
    fresh: FiledDeclaracionObservation,
    stored: RegistryModeloObservation,
    *,
    tolerance: Decimal = Decimal("0"),
) -> tuple[CasillaId, ...]:
    """Return every casilla whose freshly captured value disagrees with the stored one.

    Derived from the observed casilla set rather than from a hand-listed field
    list, for the same reason the invoice reconfirm diff is: the failure this
    exists to catch is a comparison that OMITS a casilla, and a hand-listed set is
    precisely how that omission arrives. A newly-extracted casilla is compared the
    moment it is captured.

    Only casillas present on BOTH sides are compared. A casilla the fresh capture
    read and the stored revision never held is not a changed value -- it is a
    wider extraction -- and reporting it as a divergence would fire the advisory
    on every extraction improvement.

    NOT substitutable with the tree's other per-casilla comparators, and the
    intersection rule above is why. ``detect_casilla_divergences`` and
    ``compare_calculation_to_filed_observation`` both REPORT absence, as
    missing-on-one-side rows, and the revision-vs-revision delta in
    ``application/modelo/_projection.py`` treats an absent casilla as zero.
    All three of those contracts would fire this advisory on an extraction
    improvement, which is the one thing it must never do. The absence contract
    is the discriminator, not the tolerance.

    Args:
        fresh: The newly captured observation.
        stored: The prior stamped registry observation for the same key.
        tolerance: Maximum absolute delta that does not count as a change. The
            registry owns this value through
            :func:`~cadrumo.domain.calculations.registry.verification_tolerance_or_exact`.
            The default is exact equality, matching the caller's resolved
            fallback for a triple with no published contract.

    Returns:
        The changed casilla ids, sorted, so the notice text is deterministic.
    """
    # Both sides already carry the typed CasillaId, so neither is stringified:
    # erasing the alias at this boundary was drift, not normalisation.
    stored_values = {observation.casilla_id: observation.value for observation in stored.observations}
    changed: set[CasillaId] = set()
    for observed in fresh.casillas:
        casilla_id = observed.casilla_id
        if casilla_id not in stored_values:
            continue
        if observed.value_kind is not CasillaValueKind.NUMERIC:
            continue
        try:
            fresh_value = observed.decimal_value()
        except InvalidOperation:
            # An unreadable fresh token is not evidence of a CHANGED value, and
            # claiming one would put a false amendment in front of the operator.
            # The kind check above is what makes InvalidOperation the only
            # reachable failure here: a non-numeric casilla never reaches the
            # conversion, so its own refusal cannot arrive.
            continue
        stored_value = stored_values[casilla_id]
        if not isinstance(stored_value, Decimal):
            continue
        if abs(fresh_value - stored_value) > tolerance:
            changed.add(casilla_id)
    return tuple(sorted(changed))


def classify_register_scoping_signal(
    profile: TaxpayerProfile,
    availability: FiledDeclarationAvailabilityReport,
    *,
    today: date,
) -> RegisterScopingSignal:
    """Say what the offered modelo set SUGGESTS about its own scoping, for free.

    The question this addresses -- is the declaraciones register's option list
    scoped to the authenticated NIF, or a static universal catalogue -- cannot be
    settled without an authorised live probe against an account with real filing
    history. Nobody has authorised one, and the design never depended on it
    resolving. What it does have is a cheap, offline, taxpayer-specific
    discriminator nobody was reading: if the register offers a modelo the
    taxpayer's own declared facts positively EXCLUDE, the list is offering
    something this taxpayer cannot have filed, which is what a universal
    catalogue looks like.

    The result is advisory only and changes nothing about what is walked. The
    offered set is unioned in additively either way, so a reading here can
    neither widen nor narrow the grid, and it MUST NOT be rendered as a settled
    answer -- see :class:`~core.RegisterScopingSignal`, whose members are all
    hedges precisely so that it cannot be.

    The evidence is asymmetric, and so is the confidence.
    :attr:`~core.RegisterScopingSignal.LIKELY_UNIVERSAL` is a positive
    observation: an excluded modelo was offered. Its counterpart is only ever the
    ABSENCE of that observation, which a universal catalogue also produces for a
    taxpayer whose profile excludes nothing the register lists -- so it stays
    ``LIKELY_NIF_SCOPED``, never confirmation.

    Args:
        profile: The taxpayer's declared :class:`TaxpayerProfile`, supplying the
            positively-excluded modelo set.
        availability: The register's offered option set.
        today: Reference date for applicability evaluation.

    Returns:
        The :class:`~core.RegisterScopingSignal` reading.
        :attr:`~core.RegisterScopingSignal.INCONCLUSIVE` when either side of the
        comparison is empty, because then the comparison discriminates nothing.
    """
    from ..overview.coverage import build_obligation_coverage

    offered = {item.modelo for item in availability.items}
    excluded = set(build_obligation_coverage(profile, (), today=today).confidently_excluded)
    if not offered or not excluded:
        return RegisterScopingSignal.INCONCLUSIVE
    if offered & excluded:
        return RegisterScopingSignal.LIKELY_UNIVERSAL
    return RegisterScopingSignal.LIKELY_NIF_SCOPED


def filed_history_discovery_report(
    *,
    expected: ExpectedFiledDeclarationGrid,
    availability: FiledDeclarationAvailabilityReport | None = None,
) -> FiledHistoryDiscoveryReport:
    """Union the two discovery signals into one provenance-tagged walk grid.

    A pair nominated by both signals carries both tags; a pair nominated by one
    carries only that one. The union never drops a pair either signal offered,
    which is what makes the register's contribution purely coverage-widening: it
    cannot remove anything the profile expected, and it cannot lend its own pairs
    the profile signal's standing.

    Args:
        expected: The taxpayer-specific grid from
            :func:`expected_filed_declaration_grid`.
        availability: The register's offered option set, or ``None`` when the
            option lists were not read (no live session). ``None`` is a supported
            mode, not a degraded one.

    Returns:
        The :class:`FiledHistoryDiscoveryReport` walk grid.
    """
    signals_by_pair: dict[tuple[str, int], set[FiledHistoryDiscoverySignal]] = {}
    for pair in expected.pairs:
        signals_by_pair.setdefault(pair, set()).add(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY)
    if availability is not None:
        for pair in availability.offered_pairs:
            signals_by_pair.setdefault(pair, set()).add(FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS)

    return FiledHistoryDiscoveryReport(
        pairs=tuple(
            FiledHistoryDiscoveryPair(modelo=modelo, ejercicio=ejercicio, signals=tuple(signals))
            for (modelo, ejercicio), signals in sorted(
                signals_by_pair.items(),
                key=lambda item: (item[0][0], -item[0][1]),
            )
        ),
        profile_year_span_determined=expected.activity_start_declared,
        register_options_read=availability is not None,
    )


class FiledHistoryPairOutcome(BaseModel):
    """What one walked pair produced, keeping a refusal distinct from a zero.

    ``refused`` is not derivable from ``row_count``. The register walker refuses a
    page whose grid declares more records than it rendered, and that refusal is
    absorbed into a failure row upstream — so a refused pair also reports zero
    rows. Reading the zero as "nothing filed" is precisely the silent
    under-report this feature exists to remove, which is why the refusal is its
    own field and why the notices below branch on it.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    ejercicio: FilingYear
    signals: tuple[FiledHistoryDiscoverySignal, ...] = Field(min_length=1)
    row_count: int = Field(default=0, ge=0)
    captured_count: int = Field(default=0, ge=0)
    refused: bool = False
    failure_type: str | None = Field(default=None, min_length=1, max_length=128)
    failure_message: str | None = Field(default=None, min_length=1, max_length=2048)

    @property
    def expected_by_profile(self) -> bool:
        """Whether the taxpayer's own declared facts expected a filing here."""
        return FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY in self.signals

    @property
    def is_a_genuine_empty(self) -> bool:
        """Whether this pair answered, and the answer was no filings.

        False for a refused pair however few rows it reported: a refusal is not
        an answer, so it is not an empty one either.
        """
        return not self.refused and self.row_count == 0


class FiledHistoryOnboardingRun(BaseModel):
    """One history-onboarding sweep: what was walked, captured and reconciled.

    Carries no completeness ratio, deliberately. Part of the walked grid comes
    from AEAT's offered option list, whose scoping to this NIF is unconfirmed, so
    any fraction over the grid would look like coverage while resting on a
    denominator that may have nothing to do with this taxpayer.
    :attr:`denominator_note` states in prose what the denominator was — the
    honest form of the same information.
    """

    model_config = _STRICT_FROZEN

    pairs: tuple[FiledHistoryPairOutcome, ...] = ()
    selection_rows: tuple[FiledPeriodSelectionRow, ...] = ()
    dry_run: bool = False
    captured_count: int = Field(default=0, ge=0)
    #: Units this sweep REACHED, from the accumulator tally counted in every
    #: mode. Carried separately from ``captured_count`` because that one is
    #: ``len(observation_paths)``, which a preview leaves empty -- so it
    #: cannot answer "was this sweep truncated" on the very path where the
    #: question matters most.
    reached_count: int = Field(default=0, ge=0)
    scoping_signal: RegisterScopingSignal = RegisterScopingSignal.INCONCLUSIVE
    carries_a_taxpayer_specific_denominator: bool = False
    iva_wallet_status: str = Field(default="not_attempted", min_length=1, max_length=64)
    iva_wallet_divergence: str | None = Field(default=None, min_length=1, max_length=64)
    iva_wallet_blocked: bool = False
    notificaciones_status: str = Field(default="not_attempted", min_length=1, max_length=64)
    notificaciones_row_count: int = Field(default=0, ge=0)
    stage_failures: tuple[str, ...] = ()
    sync_run_ref: SyncRunRecordReference | None = None
    evidence_notices: tuple[Notice, ...] = ()
    #: One advisory per re-captured filing whose casilla values this sweep
    #: changed, forwarded from the capture that read them before its upsert.
    recapture_notices: tuple[Notice, ...] = ()
    """Per-artefact evidence advisories raised during capture, each keeping its own reason."""

    @property
    def refused_pairs(self) -> tuple[FiledHistoryPairOutcome, ...]:
        """Return pairs that produced a failure row instead of an answer."""
        return tuple(pair for pair in self.pairs if pair.refused)

    @property
    def genuinely_empty_pairs(self) -> tuple[FiledHistoryPairOutcome, ...]:
        """Return pairs that answered with no filings."""
        return tuple(pair for pair in self.pairs if pair.is_a_genuine_empty)

    @property
    def denominator_note(self) -> str:
        """State what the coverage denominator was, and what it does not establish."""
        expected = sum(1 for pair in self.pairs if pair.expected_by_profile)
        offered_only = len(self.pairs) - expected
        if not expected:
            return tr(
                "live.filed.pull_all.denominator_note_register_only",
                default=(
                    "No taxpayer-specific denominator: all {offered_only} walked pair(s) came from AEAT's "
                    "offered option list, whose scoping to this NIF is unconfirmed. This run measures nothing."
                ),
                offered_only=offered_only,
            )
        return tr(
            "live.filed.pull_all.denominator_note_profile",
            default=(
                "Measured against {expected} pair(s) the taxpayer's own declared facts expect. A further "
                "{offered_only} pair(s) came only from AEAT's offered option list and support no coverage claim."
            ),
            expected=expected,
            offered_only=offered_only,
        )


def expected_but_not_found_notice(run: FiledHistoryOnboardingRun) -> Notice | None:
    """Warn for every pair the profile expected that produced no declaración.

    Fires ONLY for pairs carrying
    :attr:`~core.FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY`. A pair
    nominated only by the register's option list is never named here however
    empty it came back, because that list's informativeness for this taxpayer is
    unconfirmed — an alert raised from it could be pure noise, and an advisory
    only earns trust if every firing is a real finding.

    A REFUSED pair is also never named. It did not answer, so "the profile
    expected a filing that was not found" is not what happened; the refusal
    travels as its own failure row and its own reporting.

    Returns ``None`` when nothing qualifies, so a clean run stays quiet.
    """
    missing = tuple(pair for pair in run.pairs if pair.expected_by_profile and pair.is_a_genuine_empty)
    if not missing:
        return None
    named = ", ".join(f"{pair.modelo}/{pair.ejercicio}" for pair in missing)
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="live.filed.pull_all.expected_but_not_found",
        message=tr(
            "live.filed.pull_all.expected_but_not_found",
            default=(
                "Your declared profile expects a filing for {count} modelo/ejercicio pair(s) where AEAT's "
                "register returned none: {pairs}. Check whether these were filed."
            ),
            count=len(missing),
            pairs=named,
        ),
        context={
            "missing_count": str(len(missing)),
            "pairs": named,
            "signal": FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY.value,
        },
    )


def found_more_than_expected_notices(run: FiledHistoryOnboardingRun) -> tuple[Notice, ...]:
    """Inform for every period the register held more than one filing for.

    INFO rather than WARNING, and that is the whole judgement. Several filings
    for one period is the NORMAL shape of a corrected return: AEAT itself permits
    a complementaria, so the operator is being told what their own history looks
    like, not that something is wrong. Raising it as a warning would put a red
    flag on lawful behaviour.

    This composes with the re-capture divergence diff rather than duplicating it.
    They answer different questions: this one says the register held more filings
    than were kept for a period, the diff says a kept value CHANGED between two
    captures of the same filing. A period can trigger either, both, or neither.
    """
    return tuple(
        Notice(
            severity=NoticeSeverity.INFO,
            code="live.filed.pull_all.found_more_than_expected",
            message=tr(
                "live.filed.pull_all.found_more_than_expected",
                default=(
                    "AEAT's register holds {raw_count} filings for modelo {modelo} {period} {ejercicio}; "
                    "the most recent registration ({expediente}) was kept and {superseded} earlier one(s) "
                    "were superseded."
                ),
                raw_count=row.raw_row_count,
                modelo=row.modelo,
                period=row.period,
                ejercicio=row.ejercicio,
                expediente=row.winning_expediente_id or "unknown",
                superseded=row.superseded_count,
            ),
            context={
                "modelo": row.modelo,
                "ejercicio": str(row.ejercicio),
                "period": row.period,
                "raw_row_count": str(row.raw_row_count),
                "selected_count": str(row.selected_count),
                "superseded_count": str(row.superseded_count),
                "winning_expediente_id": row.winning_expediente_id or "",
            },
        )
        for row in run.selection_rows
        if row.held_more_than_one_filing
    )


def recapture_divergence_notices(
    captured: tuple[FiledDeclaracionObservation, ...],
    *,
    repository: CalculationObservationRepository | None = None,
) -> tuple[Notice, ...]:
    """Warn for every re-captured filing whose casilla values changed.

    A re-capture is an unconditional upsert, so without this a corrected filing
    silently overwrites the previously observed values and the operator never
    learns their history changed. Refusing the write outright would be wrong —
    AEAT legitimately permits a complementaria — so this mirrors the shipped
    censo-divergence shape: a standing advisory, never a silent auto-resolve.

    Read BEFORE the capture is persisted; afterwards the prior values are gone.
    """
    from ..calculations import CalculationObservationRepository as _Repository

    repo = repository if repository is not None else _Repository()
    notices: list[Notice] = []
    for observation in captured:
        stored = repo.load_observation(observation.modelo, observation.period)
        if stored is None:
            continue
        try:
            snapshot = bundled_authority().snapshot(
                observation.modelo,
                filing_year=observation.ejercicio,
                period=observation.period.registry_token,
            )
        except (LookupError, KeyError, AttributeError, ValueError, CadrumoError):
            tolerance = Decimal("0")
        else:
            tolerance = verification_tolerance_or_exact(snapshot)
        changed = casillas_a_recapture_would_change(observation, stored.observation, tolerance=tolerance)
        if not changed:
            continue
        named = ", ".join(changed)
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="live.filed.pull_all.recapture_divergence",
                message=tr(
                    "live.filed.pull_all.recapture_divergence",
                    default=(
                        "Re-capturing modelo {modelo} {period} {ejercicio} changed {count} previously "
                        "observed casilla value(s): {casillas}. AEAT may hold a corrected filing."
                    ),
                    modelo=observation.modelo,
                    period=observation.period.registry_token,
                    ejercicio=observation.ejercicio,
                    count=len(changed),
                    casillas=named,
                ),
                context={
                    "modelo": observation.modelo,
                    "ejercicio": str(observation.ejercicio),
                    "period": observation.period.registry_token,
                    "changed_casillas": named,
                    "expediente_id": observation.expediente_id,
                },
            ),
        )
    return tuple(notices)


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
        profile: TaxpayerProfile | None = None,
        today: date | None = None,
    ) -> FiledHistoryDiscoveryReport: ...


def _filed_history_pair_outcomes(
    discovery: FiledHistoryDiscoveryReport,
    capture: BulkFiledDataCaptureReport,
) -> tuple[FiledHistoryPairOutcome, ...]:
    """Join the bulk capture's failure and observation facts onto every discovered pair."""
    failures_by_pair: dict[tuple[str, int], FiledDataCaptureFailureRow] = {}
    for failure in capture.failures:
        failures_by_pair.setdefault((failure.modelo, failure.year), failure)
    captured_by_pair: dict[tuple[str, int], int] = {}
    for key in capture.calculation_observation_keys:
        modelo, year_text, _period = key.split(":", 2)
        coordinate = (modelo, int(year_text))
        captured_by_pair[coordinate] = captured_by_pair.get(coordinate, 0) + 1
    return tuple(_filed_history_pair_outcome(pair, failures_by_pair, captured_by_pair) for pair in discovery.pairs)


def _filed_history_pair_outcome(
    pair: FiledHistoryDiscoveryPair,
    failures_by_pair: Mapping[tuple[str, int], FiledDataCaptureFailureRow],
    captured_by_pair: Mapping[tuple[str, int], int],
) -> FiledHistoryPairOutcome:
    """Project one discovery pair without conflating a typed refusal with a zero row count."""
    coordinate = (pair.modelo, pair.ejercicio)
    failure = failures_by_pair.get(coordinate)
    captured_count = captured_by_pair.get(coordinate, 0)
    return FiledHistoryPairOutcome(
        modelo=pair.modelo,
        ejercicio=pair.ejercicio,
        signals=pair.signals,
        row_count=captured_count,
        captured_count=captured_count,
        refused=failure is not None,
        failure_type=failure.error_type if failure is not None else None,
        failure_message=failure.message if failure is not None else None,
    )


async def _capture_discovered_filed_history(
    walk_pairs: Sequence[tuple[str, int]],
    *,
    output_root: Path,
    limit: int | None,
    dry_run: bool,
    register: DeclaracionesRegisterSession | None,
    sync_run_repository: SyncRunRecordRepositoryProtocol | None,
    events: OperationEventEmitter | None = None,
) -> BulkFiledDataCaptureReport:
    """Capture the discovered grid with its original modelo order and year span."""
    modelos = tuple(dict.fromkeys(modelo for modelo, _year in walk_pairs))
    years = tuple(year for _modelo, year in walk_pairs)
    return await capture_filed_data_bulk(
        year_from=min(years),
        year_to=max(years),
        output_root=output_root,
        modelos=modelos,
        limit=limit,
        register=register,
        dry_run=dry_run,
        sync_run_repository=sync_run_repository,
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
    resolved_today: date,
    output_root: Path,
    events: OperationEventEmitter | None = None,
) -> _FiledHistoryIvaWalletStage:
    """Capture the independent IVA wallet stage, retaining its typed partial-failure boundary."""
    try:
        from .iva_remote_state import capture_iva_compensation_wallet

        wallet = await capture_iva_compensation_wallet(
            target_year=resolved_today.year,
            target_period=Period.from_year_and_code(resolved_today.year, "1T"),
            output_root=output_root,
        )
    except Exception as exc:
        await _emit_filed_history_refusal(events, FILED_HISTORY_IVA_WALLET_REFUSAL_CODE)
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
    events: OperationEventEmitter | None = None,
) -> _FiledHistoryNotificationsStage:
    """Capture notifications without allowing an independent failure to erase filed history."""
    try:
        from .notifications import capture_notifications

        snapshot = await capture_notifications(bucket_id=require_active_bucket_id())
    except Exception as exc:
        await _emit_filed_history_refusal(events, FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE)
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
    output_root: Path,
    profile: TaxpayerProfile | None = None,
    today: date | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    discover: FiledHistoryDiscoveryPort = discover_filed_history,
    register: DeclaracionesRegisterSession | None = None,
    sync_run_repository: SyncRunRecordRepositoryProtocol | None = None,
    events: OperationEventEmitter | None = None,
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
        output_root: Root the capture writes its encrypted stores under.
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
        register: An already-open declarations register forwarded to the bulk
            capture boundary. Production omits it; deterministic composition
            proofs supply it to avoid live access and browser lifecycle.
        sync_run_repository: Completed-run persistence port forwarded to the
            bulk capture after discovery finds a supported pair.
        events: Optional operation event emitter that receives only stable stage
            identifiers, safe unit counters, and stable refusal scopes.

    Returns:
        The composed :class:`FiledHistoryOnboardingRun`.
    """
    from ...core.time import today_madrid

    resolved_today = today or today_madrid()
    await _emit_filed_history_phase(events, FILED_HISTORY_PHASE_DISCOVERY)
    discovery = await discover(profile=profile, today=resolved_today)
    walk_pairs = discovery.walk_pairs
    if not walk_pairs:
        await _emit_filed_history_refusal(events, FILED_HISTORY_DISCOVERY_REFUSAL_CODE)
        return FiledHistoryOnboardingRun(
            pairs=(),
            dry_run=dry_run,
            carries_a_taxpayer_specific_denominator=discovery.carries_a_taxpayer_specific_denominator,
            scoping_signal=RegisterScopingSignal.INCONCLUSIVE,
            stage_failures=("discovery: no modelo/ejercicio pair to walk",),
        )

    capture = await _capture_discovered_filed_history(
        walk_pairs,
        output_root=output_root,
        limit=limit,
        dry_run=dry_run,
        register=register,
        sync_run_repository=sync_run_repository,
        events=events,
    )
    pairs = _filed_history_pair_outcomes(discovery, capture)
    if dry_run:
        iva_wallet = _FiledHistoryIvaWalletStage(status="not_attempted", divergence=None, blocked=False)
        notifications = _FiledHistoryNotificationsStage(status="not_attempted", row_count=0)
    else:
        if profile is not None:
            await _emit_filed_history_phase(events, FILED_HISTORY_PHASE_IVA_WALLET)
            iva_wallet = await _capture_filed_history_iva_wallet(
                resolved_today=resolved_today,
                output_root=output_root,
                events=events,
            )
        else:
            iva_wallet = _FiledHistoryIvaWalletStage(status="not_attempted", divergence=None, blocked=False)
        await _emit_filed_history_phase(events, FILED_HISTORY_PHASE_NOTIFICATIONS)
        notifications = await _capture_filed_history_notifications(events=events)
    stage_failures = tuple(failure for failure in (iva_wallet.failure, notifications.failure) if failure is not None)

    return FiledHistoryOnboardingRun(
        pairs=pairs,
        dry_run=dry_run,
        captured_count=capture.captured_count,
        reached_count=capture.reached_count,
        scoping_signal=RegisterScopingSignal.INCONCLUSIVE,
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


def capture_report_path(path: Path, *, output_root: Path) -> str:
    """Return a stable report path relative to the configured output root when possible."""
    try:
        return path.relative_to(output_root).as_posix()
    except ValueError:
        return str(path)


__all__ = [
    "ExpectedFiledDeclarationGrid",
    "FiledHistoryDiscoveryPair",
    "FiledHistoryDiscoveryReport",
    "FiledHistoryOnboardingRun",
    "FiledHistoryPairOutcome",
    "FiledPeriodSelectionRow",
    "capture_filed_data",
    "capture_filed_data_bulk",
    "capture_report_path",
    "capture_source_filed_data",
    "casillas_a_recapture_would_change",
    "classify_register_scoping_signal",
    "discover_filed_history",
    "expected_but_not_found_notice",
    "expected_filed_declaration_grid",
    "filed_data_capture_failure_row",
    "filed_history_discovery_report",
    "filed_period_selection_rows",
    "found_more_than_expected_notices",
    "list_filed_data",
    "list_filed_data_bulk",
    "pull_filed_history",
    "recapture_divergence_notices",
    "submitted_file_extraction_notices",
]
