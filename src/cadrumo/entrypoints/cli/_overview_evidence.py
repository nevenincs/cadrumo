"""Local evidence loaders for the ``aeat app overview`` calendar, status and backlog surfaces.

Every loader here reads bucket-scoped persistence (live-capture snapshots, local
modelo filing records, filed-declaration observations, calculation observations,
work-unit catalogues) to ENRICH a schedule-derived overview surface with
observed evidence. None of them is the source of truth for what is due — the
deadline schedule plus obligation applicability is — so every loader DEGRADES to
an empty result plus a WARNING :class:`Notice` (or, for
:func:`overview_no_aeat_history_notice`, no advisory at all) on failure rather
than refusing the whole overview. Shared by :mod:`._overview`'s single-profile
``calendar`` command, its ``--all-profiles`` multi-profile scan, the ``backlog``
command's work-unit enrichment, the ``status`` command's no-AEAT-history
advisory, and the ``config profile status`` full-screen surface — so the
CLI envelope and the TUI cannot silently diverge on when that advisory fires.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from ...application.overview.calendar import build_overview_calendar_events, calendar_events_from_modelo_records
from ...application.overview.calendar_evidence import calendar_filing_evidence_from_sources, no_aeat_history_notice
from ...application.overview.calendar_models import (
    OverviewCalendarEvent,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
)
from ...core.hashing import sha256_hex
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.logging import get_logger
from ...domain.modelos.work_unit import WorkUnit
from ._common import resolve_notice_action

if TYPE_CHECKING:
    from ...domain.calculations.registry.applicability_routes import TaxRoute
    from ...domain.user_profile.values import UserProfileRecord

logger = get_logger(__name__)


def _calendar_evidence_notice(code: str, message_key: str) -> Notice:
    """A WARNING notice for an optional calendar-evidence enrichment that failed to load.

    The persisted event / filing evidence rows only ANNOTATE the calendar's
    schedule-derived obligations (as observed AEAT events, or as filed). When a
    loader cannot read them the calendar must DEGRADE to a schedule-only view —
    over-reporting an obligation as still due, the safe direction — rather than
    refusing the whole calendar. Refusing left a never-filed taxpayer (who has no
    persisted evidence at all) unable to see the calendar of what they owe.
    """
    return Notice(severity=NoticeSeverity.WARNING, code=code, message=tr(message_key), context={})


def _local_live_calendar_events(
    bucket_id: str,
    rng: OverviewCalendarRange,
    *,
    as_of: date,
    expected_tax_id: str | None = None,
) -> tuple[tuple[OverviewCalendarEvent, ...], Notice | None]:
    """Return ``(persisted-live event rows, degradation-notice-or-None)``.

    The CLI owns the bucket-scoped repository reads; the pure
    :func:`build_overview_calendar_events` builder performs the projection
    without contacting AEAT. A load failure degrades to no live-event rows plus a
    WARNING notice rather than refusing the whole calendar.

    Args:
        bucket_id: Active profile bucket to read evidence from.
        rng: Inclusive calendar window.
        as_of: Date the notification service-state window is evaluated against.
            The command body owns the clock and passes it in; this loader never
            reads one, so the projection stays reproducible.
        expected_tax_id: Taxpayer identity rows must match, when known.
    """
    from ...adapters.persistence.profile.justificante import JustificanteRepository
    from ...application.live.expedientes import ExpedientesService
    from ...application.live.justificante import JustificanteCaptureSnapshotService
    from ...application.live.notifications import NotificationsService

    try:
        expedientes = ExpedientesService().list_snapshots(bucket_id=bucket_id)
        notifications = NotificationsService().list_snapshots(bucket_id=bucket_id)
        justificante_captures = JustificanteCaptureSnapshotService(bucket_id=bucket_id).list_snapshots()
        justificantes = tuple(JustificanteRepository().iter_justificantes())
    except Exception:
        logger.warning(
            "overview calendar: live-event evidence unavailable for bucket %s; deriving from schedule only",
            bucket_id,
            exc_info=True,
        )
        return (), _calendar_evidence_notice(
            "overview.calendar_live_events_degraded",
            message_key="cli.overview.calendar_local_live_events_unavailable",
        )
    events = build_overview_calendar_events(
        calendar_range=rng,
        as_of=as_of,
        expedientes_snapshots=tuple(expedientes),
        notification_snapshots=tuple(notifications),
        justificante_capture_snapshots=tuple(justificante_captures),
        justificantes=justificantes,
        expected_tax_id=expected_tax_id,
    )
    return events, None


def _local_modelo_record_calendar_events(
    bucket_id: str,
    rng: OverviewCalendarRange,
    *,
    expected_tax_id: str | None = None,
) -> tuple[tuple[OverviewCalendarEvent, ...], Notice | None]:
    """Return ``(local-record event rows, degradation-notice-or-None)``.

    Delegates the DTO conversion to
    :func:`calendar_events_from_modelo_records` after loading bucket-local
    filing records and justificante metadata. A load failure degrades to no
    filing-event rows plus a WARNING notice rather than refusing the whole
    calendar.
    """
    try:
        from ...adapters.persistence.profile.justificante import JustificanteRepository
        from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository

        filing_records = tuple(ModeloRecordCatalogueRepository(bucket_id=bucket_id).load().values())
        justificantes = tuple(JustificanteRepository().iter_justificantes())
    except Exception:
        logger.warning(
            "overview calendar: modelo filing-event evidence unavailable for bucket %s; deriving from schedule only",
            bucket_id,
            exc_info=True,
        )
        return (), _calendar_evidence_notice(
            "overview.calendar_modelo_events_degraded",
            message_key="cli.overview.calendar_local_modelo_events_unavailable",
        )
    events = calendar_events_from_modelo_records(
        filing_records,
        rng,
        justificantes=justificantes,
        expected_tax_id=expected_tax_id,
    )
    return events, None


def _local_modelo_work_units(bucket_id: str) -> tuple[tuple[WorkUnit, ...], Notice | None]:
    """Return ``(active work units, degradation notice-or-None)``.

    Work units are an OPTIONAL enrichment of the overview surfaces: they annotate
    schedule-derived entries as in-progress and widen the lookback window back to
    the oldest in-progress draft. The backlog and calendar themselves derive from
    the deadline schedule plus obligation applicability, so a work-unit load
    failure must DEGRADE the surface — proceed schedule-only — not refuse the
    whole answer.

    A fresh profile with no catalogue loads as empty (no failure). The failure
    path is a genuine work-unit-subsystem fault; degrading over-reports an
    in-progress draft as still-due (the safe direction — it surfaces more, never
    hides a due obligation) and only narrows the lookback to the default window.
    Refusing the entire overview because this optional enrichment failed left a
    behind-but-fresh taxpayer — the exact ``regularizar-atrasos`` persona — unable
    to answer "what have I missed"; the WARNING notice discloses the degradation
    instead.
    """
    try:
        from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
        from ...application.modelo.work_lifecycle import list_work_units

        repository = WorkUnitCatalogueRepository(bucket_id=bucket_id)
        return list_work_units(bucket_id=bucket_id, include_discarded=False, repository=repository), None
    except Exception:
        logger.warning(
            "overview: work-unit enrichment unavailable for bucket %s; deriving from schedule only",
            bucket_id,
            exc_info=True,
        )
        notice = Notice(
            severity=NoticeSeverity.WARNING,
            code="overview.work_units_degraded",
            message=tr(
                "cli.overview.local_work_units_unavailable",
                default=(
                    "Local Modelo work-unit state could not be loaded; this overview is "
                    "derived from the deadline schedule and may over-report an in-progress "
                    "draft as still due or omit older in-progress drafts."
                ),
            ),
            context={},
        )
        return (), notice


def overview_no_aeat_history_notice(*, tax_route: TaxRoute | None) -> Notice | None:
    """Project the no-AEAT-history advisory onto the live envelope notice channel.

    Reads persisted calculation observations across every modelo — the profile
    as a whole, not one filing — through the same
    :meth:`~cadrumo.application.calculations.CalculationObservationRepository.iter_records`
    read the ``config profile status`` full-screen surface already uses, and
    projects the application
    :func:`~cadrumo.application.overview.no_aeat_history_notice` advisory
    through the live action resolver so its ``cli_path`` is populated the way
    every other envelope notice's action is (the application layer's bare
    :func:`~cadrumo.application.operator_actions.next_action` carries only the
    action id). The one shared function keeps the CLI envelope and the TUI
    from silently diverging on when this advisory fires or what it suggests.

    A read failure degrades to no advisory, matching every other loader in
    this module: this is an overview ENRICHMENT, never something the whole
    command should fail over.
    """
    from ...application.calculations.observations_repository import CalculationObservationRepository
    from ...application.operator_actions.models import ActionReference
    from ...core.json_contract import ResolvedNoticeAction

    try:
        observations = tuple(CalculationObservationRepository().iter_records())
    except Exception:
        logger.warning(
            "overview: AEAT-history evidence unavailable; no-history advisory skipped",
            exc_info=True,
        )
        return None
    notice = no_aeat_history_notice(
        tuple(payload.source_kind for payload in observations),
        tax_route=tax_route,
    )
    if notice is None or not isinstance(notice.action, ResolvedNoticeAction):
        return notice
    return notice.model_copy(
        update={
            "action": resolve_notice_action(
                action=ActionReference(action_id=notice.action.action.action_id),
            ),
        },
    )


def _live_censo_verified_profile_keys(record: UserProfileRecord | None) -> tuple[str, ...]:
    """Return profile paths whose current value was stamped from live censo sync."""
    if record is None:
        return ()
    from ...application.user_profile.censo_sync import CENSO_SOURCE_TAG

    verified_sources = {CENSO_SOURCE_TAG}
    return tuple(
        sorted(
            {fact.path for fact in record.facts if fact.path.strip() and fact.source in verified_sources},
        ),
    )


def _local_calendar_filing_evidence(
    bucket_id: str,
    events: tuple[OverviewCalendarEvent, ...],
    *,
    expected_tax_id: str | None = None,
) -> tuple[tuple[OverviewCalendarFilingEvidence, ...], Notice | None]:
    """Return ``(local/AEAT filing evidence rows, degradation-notice-or-None)``.

    The resulting :class:`OverviewCalendarFilingEvidence` rows feed
    :class:`OverviewCalendar` without treating a local filing record as proof of
    AEAT submission. A load failure degrades to no filing-evidence rows plus a
    WARNING notice rather than refusing the whole calendar.
    """
    try:
        from ...adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
        from ...adapters.persistence.profile.justificante import JustificanteRepository
        from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
        from ...application.calculations.observations_repository import CalculationObservationRepository
        from ...application.live.justificante import JustificanteCaptureSnapshotService

        filing_records = tuple(ModeloRecordCatalogueRepository(bucket_id=bucket_id).load().values())
        justificantes = tuple(JustificanteRepository().iter_justificantes())
        justificante_captures = JustificanteCaptureSnapshotService(bucket_id=bucket_id).list_snapshots()
        # Enrolled data-root location, not a hardcoded literal: this store holds
        # filed-declaration evidence and must move with the operator's
        # CADRUMO_LOCAL_STORAGE_ROOT like every other durable output.
        from ...core.config import load_settings

        filed_observation_store = FiledDeclaracionObservationStore(
            load_settings().cadrumo_filed_declarations_dir,
        )
        filed_declaration_observations, verified_filed_artefact_csvs = (
            _calendar_verified_filed_declaration_observations(
                filed_observation_store,
                expected_tax_id=expected_tax_id,
            )
        )
        calculation_observations = tuple(CalculationObservationRepository().iter_records())
    except Exception:
        logger.warning(
            "overview calendar: filing evidence unavailable for bucket %s; deriving from schedule only",
            bucket_id,
            exc_info=True,
        )
        return (), _calendar_evidence_notice(
            "overview.calendar_filing_evidence_degraded",
            message_key="cli.overview.calendar_local_filing_evidence_unavailable",
        )
    evidence = calendar_filing_evidence_from_sources(
        filing_records=filing_records,
        observed_events=events,
        filed_declaration_observations=tuple(filed_declaration_observations),
        verified_filed_declaration_artefact_refs=tuple(verified_filed_artefact_csvs),
        verified_filed_declaration_artefact_csvs=verified_filed_artefact_csvs,
        calculation_observations=calculation_observations,
        justificante_capture_snapshots=tuple(justificante_captures),
        justificantes=justificantes,
        expected_tax_id=expected_tax_id,
    )
    return evidence, None


def _calendar_verified_filed_declaration_observations(
    store,
    *,
    expected_tax_id: str | None = None,
):
    """Return filed observations with justificante PDF refs proven parseable and matching."""
    verified_observations = []
    verified_artefact_csvs: dict[str, str] = {}
    for observation in store.list_observations():
        verified_artefacts = []
        for artefact in observation.artefacts:
            if artefact.kind != "justificante_pdf":
                verified_artefacts.append(artefact)
                continue
            csv = _stored_filed_artefact_matching_observation_csv(
                store,
                artefact,
                observation,
                expected_tax_id=expected_tax_id,
            )
            if csv is not None:
                if artefact.storage_ref is not None:
                    verified_artefact_csvs[artefact.storage_ref] = csv
                verified_artefacts.append(artefact)
                continue
            verified_artefacts.append(artefact.model_copy(update={"storage_ref": None}))
        verified_observations.append(observation.model_copy(update={"artefacts": tuple(verified_artefacts)}))
    return tuple(verified_observations), dict(sorted(verified_artefact_csvs.items()))


def _stored_filed_artefact_matching_observation_csv(
    store,
    artefact,
    observation,
    *,
    expected_tax_id: str | None,
) -> str | None:
    storage_ref = artefact.storage_ref
    if not storage_ref:
        return None
    try:
        body = store.load_artefact(storage_ref)
    except Exception:
        logger.warning(
            "overview calendar: ignored unreadable filed-declaration artefact %s",
            storage_ref,
            exc_info=True,
        )
        return None
    if len(body) != artefact.byte_count or sha256_hex(body) != artefact.sha256:
        return None
    return _stored_filed_justificante_matching_observation_csv(
        body,
        observation,
        storage_ref=storage_ref,
        expected_tax_id=expected_tax_id,
    )


def _stored_filed_justificante_matching_observation_csv(
    body: bytes,
    observation,
    *,
    storage_ref: str,
    expected_tax_id: str | None,
) -> str | None:
    from ...adapters.inbound.justificante.parser import parse_justificante_bytes

    try:
        justificante = parse_justificante_bytes(body)
    except Exception:
        logger.warning(
            "overview calendar: ignored unparsable filed-declaration justificante artefact %s",
            storage_ref,
            exc_info=True,
        )
        return None

    expected = (expected_tax_id or observation.authenticated_identity or "").strip()
    if not expected:
        return None
    if justificante.matches_filing_target(
        modelo=observation.modelo,
        filing_year=observation.ejercicio,
        period=observation.period,
        tax_id=expected,
    ):
        return justificante.csv
    return None
