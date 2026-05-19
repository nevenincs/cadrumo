"""Composition root for the end-user composite workflow engine.

:class:`WorkflowEngine` walks the filing pipeline in strict linear order. Every
stage lives in its own small ``_stage_*`` method so the bailout matrix
is trivially auditable — a reader drops into a single stage method to
see exactly which abort reasons it can produce.

Safety invariants enforced by this module:

- The engine never touches AEAT-side state directly; every boundary
  call flows through an injected Protocol or callable seam.
"""

from __future__ import annotations

from ...core.errors import BaseSeverity
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, NoReturn

from ...adapters.outbound.aeat import sede as _sede
from ...adapters.outbound.aeat.auth import CertificateHealthSeverity
from ...adapters.outbound.aeat.export import ModeloDraftStatus
from ...adapters.outbound.aeat.sede import Expediente, NotificationsSnapshot
from ...application.auth import describe_provider_operator_impact

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth import AeatSession
from ...core.config import Settings
from ...core.errors import SiteHealthError
from ...core.logging import get_logger
from ...domain.deadlines import AutonomoProfile, ModeloDeadline, Schedule, next_deadline
from ...domain.filing import ModeloBuilderError
from ...domain.submission import SubmissionPreflightError
from ..filing.runtime import build_runtime_schema_provider
from ._errors import WorkflowAbortSignalError, WorkflowComponentError, WorkflowError
from ._models import (
    DeclaracionPointer,
    SiteHealthAlert,
    WorkflowAbortReason,
    WorkflowResult,
    WorkflowStage,
    WorkflowState,
    WorkflowStep,
    compute_run_id,
)
from ._protocols import (
    CertificateBundleProtocol,
    DeadlineEngineProtocol,
    FilingDraftBuilderProtocol,
    FilingInputsProviderProtocol,
    RegistryFilingDraftProtocol,
    SubmissionEngineProtocol,
)

ExpedientesSource = Callable[["AeatSession", str | None], Awaitable[tuple[Expediente, ...]]]
"""Async callable that returns expedientes for a session, optionally filtered by ``modelo``."""

NotificationsSource = Callable[["AeatSession"], Awaitable[NotificationsSnapshot]]
"""Async callable that returns the full notifications snapshot for a session."""


async def _default_expedientes_source(
    session: AeatSession,
    modelo: str | None,
) -> tuple[Expediente, ...]:
    """Default seam: forward to the live :func:`aeat.adapters.outbound.aeat.sede.walk_expedientes_tree`."""
    return await _sede.walk_expedientes_tree(session, modelo=modelo)


async def _default_notifications_source(session: AeatSession) -> NotificationsSnapshot:
    """Default seam: forward to the live :func:`aeat.adapters.outbound.aeat.sede.fetch_notifications_query`."""
    return await _sede.fetch_notifications_query(session)


def _period_to_year(period: str) -> int | None:
    """Extract the leading 4-digit calendar year from a period string.

    Period strings used in the deadline engine carry the year as the
    first four digits — ``"2026"`` (annual), ``"2026Q1"`` (quarterly),
    ``"2026M3"`` (monthly). The expediente record carries
    :attr:`aeat.adapters.outbound.aeat.sede.Expediente.ejercicio` as a separate integer year,
    so the workflow's "already filed" gate matches modelo + year.
    """
    head = period[:4]
    if not head.isdigit():
        return None
    return int(head)


def _registry_period_token(period: str) -> tuple[int, str]:
    year = _period_to_year(period)
    if year is None:
        raise WorkflowError(f"cannot derive registry year from workflow period {period!r}")
    if period == str(year) or period == f"{year}A":
        return year, "0A"
    if len(period) == 6 and period.startswith(f"{year}Q") and period[-1] in "1234":
        return year, f"{period[-1]}T"
    if period.startswith(f"{year}M") and period[5:].isdigit():
        month = int(period[5:])
        if 1 <= month <= 12:
            return year, f"{month:02d}"
    if len(period) == 7 and period.startswith(f"{year}-"):
        return year, period[-2:]
    raise WorkflowError(f"cannot map workflow period {period!r} to a registry period")


_logger = get_logger(__name__)


def _utcnow() -> datetime:
    """Return current UTC time. Factored for test determinism hooks."""
    return datetime.now(tz=UTC)


def _classify_cert_expiry(
    *,
    not_after: date,
    today: date,
    warn_days: int,
    critical_days: int,
) -> tuple[CertificateHealthSeverity, int]:
    """Classify a certificate's expiry window against operator thresholds.

    Operates on the provider description's expiry date rather than the
    rich :class:`aeat.adapters.outbound.aeat.auth.LoadedCertificate`, so it can be called from
    the workflow engine without forcing certificate-only types into the
    workflow boundary. Boundary semantics match
    :func:`aeat.adapters.outbound.aeat.auth.evaluate_loaded_certificate_health`:
    exactly ``critical_days`` remaining is CRITICAL (inclusive), and
    exactly ``warn_days`` remaining is WARN (inclusive).

    Args:
        not_after: The certificate's expiry date.
        today: Reference date (usually the workflow ``today`` arg).
        warn_days: Warning threshold in days.
        critical_days: Critical threshold in days.

    Returns:
        A ``(severity, days_until_expiry)`` tuple.
    """
    days_until_expiry = (not_after - today).days
    if days_until_expiry <= 0:
        return (CertificateHealthSeverity.EXPIRED, days_until_expiry)
    if days_until_expiry <= critical_days:
        return (CertificateHealthSeverity.CRITICAL, days_until_expiry)
    if days_until_expiry <= warn_days:
        return (CertificateHealthSeverity.WARN, days_until_expiry)
    return (CertificateHealthSeverity.OK, days_until_expiry)


def _summary_text(en: str) -> str:
    """Build a workflow summary string."""
    return en


def _enum_value(value: object) -> str:
    """Return ``Enum.value`` when present, otherwise ``str(value)``."""
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return str(raw)


class WorkflowEngine:
    """Ordered orchestrator across every AEAT building block.

    Construction takes one Protocol handle per component. The
    authenticated AEAT session and the certificate bundle are
    optional: when ``None``, the stages that consume them run in skip
    mode and surface a diagnostic instead of failing.
    """

    def __init__(
        self,
        *,
        deadline_engine: DeadlineEngineProtocol,
        filing_draft_builder: FilingDraftBuilderProtocol,
        submission_engine: SubmissionEngineProtocol,
        session: AeatSession | None,
        certificate_bundle: CertificateBundleProtocol | None,
        inputs_provider: FilingInputsProviderProtocol,
        settings: Settings,
        expedientes_source: ExpedientesSource | None = None,
        notifications_source: NotificationsSource | None = None,
    ) -> None:
        """Construct a :class:`WorkflowEngine`.

        Args:
            deadline_engine: Protocol over :class:`aeat.domain.deadlines.DeadlineEngine`.
            filing_draft_builder: Protocol over :func:`aeat.application.filing.build_draft`.
            submission_engine: Protocol over :class:`aeat.adapters.outbound.aeat.export.SubmissionEngine`.
            session: Optional authenticated :class:`aeat.adapters.outbound.aeat.auth.AeatSession`
                used to drive the live :mod:`aeat.adapters.outbound.aeat.sede` reader. ``None``
                skips both the inbox probe and the already-filed probe.
            certificate_bundle: Optional Protocol over the certificate
                backend. ``None`` skips the cert load probe.
            inputs_provider: Protocol that supplies casilla inputs for
                the draft stage.
            settings: Application :class:`Settings` instance.
            expedientes_source: Test seam over
                :func:`aeat.adapters.outbound.aeat.sede.walk_expedientes_tree`. Defaults to the
                live walker.
            notifications_source: Test seam over
                :func:`aeat.adapters.outbound.aeat.sede.fetch_notifications_query`. Defaults to
                the live fetcher.
        """
        self._deadline_engine = deadline_engine
        self._filing_draft_builder = filing_draft_builder
        self._submission_engine = submission_engine
        self._session = session
        self._certificate_bundle = certificate_bundle
        self._inputs_provider = inputs_provider
        self._settings = settings
        self._expedientes_source: ExpedientesSource = expedientes_source or _default_expedientes_source
        self._notifications_source: NotificationsSource = notifications_source or _default_notifications_source
        # Lazy run-id recomputation state. These are set at the start
        # of every ``_drive`` call and consumed by
        # ``_record_site_unavailable`` so an alert raised *after* the
        # obligation has been resolved carries a ``run_id`` that
        # matches the final :class:`WorkflowResult.run_id`. When no
        # obligation is known yet (e.g. ``SiteHealthError`` from the
        # deadline stage of an open-ended ``run_next`` call)
        # the ``-`` placeholders are expected and match the
        # placeholders in the final result.
        self._run_tax_id: str | None = None
        self._run_started_at: datetime | None = None
        self._run_target_modelo: str | None = None
        self._run_target_period: str | None = None
        self._run_obligation: ModeloDeadline | None = None

    # ------------------------------------------------------------------ public

    async def run_next(
        self,
        profile: AutonomoProfile,
        *,
        fail_on_warning: bool = False,
        today: date | None = None,
    ) -> WorkflowResult:
        """Drive the workflow for the caller's next obligation.

        Args:
            profile: The :class:`AutonomoProfile` to run for.
            fail_on_warning: Forwarded to the filing draft builder.
            today: Reference date for deadline / preflight checks.
                Defaults to :meth:`date.today`.

        Returns:
            A fully populated :class:`WorkflowResult`.
        """
        return await self._drive(
            profile=profile,
            target_modelo=None,
            target_period=None,
            fail_on_warning=fail_on_warning,
            today=today,
        )

    async def run_for_period(
        self,
        profile: AutonomoProfile,
        modelo: str,
        period: str,
        *,
        fail_on_warning: bool = False,
        today: date | None = None,
        resumed_from: str | None = None,
    ) -> WorkflowResult:
        """Drive the workflow for a caller-specified ``(modelo, period)``.

        Args:
            profile: The :class:`AutonomoProfile` to run for.
            modelo: Target modelo identifier.
            period: Target period identifier.
            fail_on_warning: See :meth:`run_next`.
            today: See :meth:`run_next`.
            resumed_from: Optional prior workflow ``run_id`` that this
                invocation continues. When set, the produced
                :class:`WorkflowResult` carries the linkage so callers
                can trace the resume chain. The engine does not validate
                the prior run by itself; the upstream resume action
                resolves and gates the prior context before invoking.

        Returns:
            A fully populated :class:`WorkflowResult`.
        """
        if resumed_from is not None:
            stripped = resumed_from.strip()
            if len(stripped) != 16 or any(c not in "0123456789abcdef" for c in stripped):
                raise ValueError(
                    "resumed_from must be a 16-character lowercase hex run id; "
                    f"got {resumed_from!r}",
                )
            resumed_from = stripped
        return await self._drive(
            profile=profile,
            target_modelo=modelo,
            target_period=period,
            fail_on_warning=fail_on_warning,
            today=today,
            resumed_from=resumed_from,
        )

    # ------------------------------------------------------------------ driver

    async def _drive(
        self,
        *,
        profile: AutonomoProfile,
        target_modelo: str | None,
        target_period: str | None,
        fail_on_warning: bool,
        today: date | None,
        resumed_from: str | None = None,
    ) -> WorkflowResult:
        """Linearly walk the read-only stages, bailing on the first failure."""
        started_at = _utcnow()
        reference_today = today or date.today()

        # Record run context so ``_record_site_unavailable`` can lazily
        # recompute the run_id from whichever information is latest
        # (preferring a resolved obligation over caller targets).
        self._run_tax_id = profile.tax_id
        self._run_started_at = started_at
        self._run_target_modelo = target_modelo
        self._run_target_period = target_period
        self._run_obligation = None

        steps: list[WorkflowStep] = []
        obligation: ModeloDeadline | None = None
        draft: RegistryFilingDraftProtocol | None = None
        final_stage: WorkflowStage = WorkflowStage.ABORTED
        aborted_reason: WorkflowAbortReason | None = None
        abort_summary: str | None = None

        try:
            self._stage_loading_profile(profile, steps)
            obligation = self._stage_computing_deadlines(
                profile=profile,
                target_modelo=target_modelo,
                target_period=target_period,
                today=reference_today,
                steps=steps,
            )
            self._run_obligation = obligation
            await self._stage_checking_inbox(
                profile=profile,
                obligation=obligation,
                steps=steps,
            )
            draft = await self._stage_building_draft(
                profile=profile,
                obligation=obligation,
                fail_on_warning=fail_on_warning,
                steps=steps,
            )
            self._stage_validating_draft(draft=draft, steps=steps)
            self._stage_running_preflight(
                draft=draft,
                today=reference_today,
                steps=steps,
            )
            final_stage = WorkflowStage.DONE
        except WorkflowAbortSignalError as abort:
            aborted_reason = abort.reason
            abort_summary = abort.summary
            _abort_stage = steps[-1].stage if steps else "?"
            if abort.reason is WorkflowAbortReason.UNHANDLED_EXCEPTION:
                _logger.error(
                    "workflow: aborted at stage=%s reason=%s",
                    _abort_stage,
                    abort.reason,
                    exc_info=True,
                )
            elif abort.reason in (
                WorkflowAbortReason.SITE_UNAVAILABLE,
                WorkflowAbortReason.CERT_INVALID,
                WorkflowAbortReason.PREFLIGHT_FAILED,
                WorkflowAbortReason.INBOX_BLOCKING_REQUERIMIENTO,
                WorkflowAbortReason.DRAFT_HAS_ERRORS,
            ):
                _logger.warning(
                    "workflow: aborted at stage=%s reason=%s",
                    _abort_stage,
                    abort.reason,
                )
            else:
                _logger.info(
                    "workflow: aborted at stage=%s reason=%s",
                    _abort_stage,
                    abort.reason,
                )

        ended_at = _utcnow()
        self._run_tax_id = None
        self._run_started_at = None
        self._run_target_modelo = None
        self._run_target_period = None
        self._run_obligation = None
        modelo_for_hash = target_modelo or (obligation.modelo if obligation is not None else "-")
        period_for_hash = target_period or (obligation.period if obligation is not None else "-")
        run_id = compute_run_id(
            tax_id=profile.tax_id,
            modelo=modelo_for_hash,
            period=period_for_hash,
            started_at=started_at,
        )

        summary: str
        if final_stage is WorkflowStage.DONE:
            summary = _summary_text(f"Workflow completed: modelo={modelo_for_hash} period={period_for_hash}")
        elif abort_summary is not None:
            summary = abort_summary
        else:
            reason_text = aborted_reason.value if aborted_reason is not None else "unknown"
            summary = _summary_text(f"Workflow aborted: {reason_text}")

        return WorkflowResult(
            run_id=run_id,
            started_at=started_at,
            ended_at=ended_at,
            final_stage=final_stage,
            aborted_reason=aborted_reason,
            obligation=obligation,
            draft_id=draft.draft_id if draft is not None else None,
            submission_id=None,
            steps=tuple(steps),
            summary=summary,
            resumed_from=resumed_from,
        )

    # ------------------------------------------------------------------ stages

    def _stage_loading_profile(
        self,
        profile: AutonomoProfile,
        steps: list[WorkflowStep],
    ) -> None:
        """Validate the incoming profile.

        The profile is already a strict pydantic model, so this stage
        is mostly an audit log. It still exists as a distinct step so
        the workflow contract is visible in every result.
        """
        started = _utcnow()
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.LOADING_PROFILE,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary=_summary_text(f"Loaded profile tax_id={profile.tax_id}"),
            )
        )

    def _stage_computing_deadlines(
        self,
        *,
        profile: AutonomoProfile,
        target_modelo: str | None,
        target_period: str | None,
        today: date,
        steps: list[WorkflowStep],
    ) -> ModeloDeadline:
        """Stage 3 — compute the target obligation.

        Aborts with ``NO_PENDING_OBLIGATION`` when the schedule is
        empty or the narrow-target is absent, and with
        ``DEADLINE_PASSED`` when the selected obligation has already
        closed against ``today``.
        """
        started = _utcnow()
        try:
            schedule: Schedule = self._deadline_engine.compute(profile, today.year, today=today)
        except SiteHealthError as exc:
            self._record_site_unavailable(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started=started,
                exc=exc,
                steps=steps,
            )
        except Exception as exc:
            self._record_unhandled(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started=started,
                exc=exc,
                steps=steps,
            )

        obligation: ModeloDeadline | None
        if target_modelo is not None and target_period is not None:
            matches = [o for o in schedule.obligations if o.modelo == target_modelo and o.period == target_period]
            obligation = matches[0] if matches else None
        else:
            obligation = next_deadline(schedule, today=today)

        if obligation is None:
            no_summary = _summary_text("No pending filing obligation for this profile")
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.COMPUTING_DEADLINES,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary=no_summary,
                )
            )
            raise WorkflowAbortSignalError(
                reason=WorkflowAbortReason.NO_PENDING_OBLIGATION,
                summary=no_summary,
            )

        if obligation.closes_on < today:
            closed_summary = _summary_text(
                f"Deadline for modelo={obligation.modelo} "
                f"period={obligation.period} closed on {obligation.closes_on.isoformat()}"
            )
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.COMPUTING_DEADLINES,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary=closed_summary,
                    details={
                        "modelo": obligation.modelo,
                        "period": obligation.period,
                        "closes_on": obligation.closes_on.isoformat(),
                    },
                )
            )
            raise WorkflowAbortSignalError(
                reason=WorkflowAbortReason.DEADLINE_PASSED,
                summary=closed_summary,
            )

        steps.append(
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary=_summary_text(
                    f"Next obligation modelo={obligation.modelo} "
                    f"period={obligation.period} closes_on={obligation.closes_on.isoformat()}"
                ),
                details={
                    "modelo": obligation.modelo,
                    "period": obligation.period,
                    "closes_on": obligation.closes_on.isoformat(),
                },
            )
        )
        return obligation

    async def _stage_checking_inbox(
        self,
        *,
        profile: AutonomoProfile,
        obligation: ModeloDeadline,
        steps: list[WorkflowStep],
    ) -> None:
        """Stage 4 — probe the notifications inbox for blocking requerimientos.

        A row blocks submission when AEAT marks it as a formal
        ``Notificación`` (``tipo == "notificacion"``) AND the row has
        not been read (``leida`` is ``False`` or ``None``). The
        ``concepto`` carries the free-text subject line of the row.
        """
        del profile  # session identity is implicit; tax_id no longer crosses the boundary.
        started = _utcnow()
        if self._session is None:
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.CHECKING_INBOX,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=True,
                    summary=_summary_text("Inbox skipped (not wired)"),
                    details={"skipped": "not_wired"},
                )
            )
            return
        try:
            snapshot = await self._notifications_source(self._session)
        except SiteHealthError as exc:
            self._record_site_unavailable(
                stage=WorkflowStage.CHECKING_INBOX,
                started=started,
                exc=exc,
                steps=steps,
            )
        except Exception as exc:
            self._record_unhandled(
                stage=WorkflowStage.CHECKING_INBOX,
                started=started,
                exc=exc,
                steps=steps,
            )
        blockers = tuple(n for n in snapshot.rows if n.tipo == "notificacion" and n.leida is not True)
        if blockers:
            blocked_summary = _summary_text(
                f"Inbox has {len(blockers)} blocking requerimiento(s) for modelo={obligation.modelo}"
            )
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.CHECKING_INBOX,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary=blocked_summary,
                    details={
                        "blocker_count": str(len(blockers)),
                        "first_notificacion_id": blockers[0].certificado_id,
                        "first_concepto": blockers[0].concepto,
                    },
                )
            )
            raise WorkflowAbortSignalError(
                reason=WorkflowAbortReason.INBOX_BLOCKING_REQUERIMIENTO,
                summary=blocked_summary,
            )
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.CHECKING_INBOX,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary=_summary_text("Inbox clear"),
            )
        )

    async def _stage_building_draft(
        self,
        *,
        profile: AutonomoProfile,
        obligation: ModeloDeadline,
        fail_on_warning: bool,
        steps: list[WorkflowStep],
    ) -> RegistryFilingDraftProtocol:
        """Stage 5 — consult the status reader, load inputs, build the draft.

        Aborts with ``ALREADY_FILED`` if the (optional) status reader
        reports an existing expediente for the same
        ``(modelo, period)``. Aborts with ``DRAFT_HAS_ERRORS`` if the
        builder refuses to promote the draft to ``READY_TO_SUBMIT``.
        Any unexpected exception lands as ``UNHANDLED_EXCEPTION``.
        """
        started = _utcnow()

        if self._session is not None:
            try:
                expedientes = await self._expedientes_source(self._session, obligation.modelo)
            except SiteHealthError as exc:
                self._record_site_unavailable(
                    stage=WorkflowStage.BUILDING_DRAFT,
                    started=started,
                    exc=exc,
                    steps=steps,
                )
            except Exception as exc:
                self._record_unhandled(
                    stage=WorkflowStage.BUILDING_DRAFT,
                    started=started,
                    exc=exc,
                    steps=steps,
                )
            target_year = _period_to_year(obligation.period)
            already = tuple(
                e
                for e in expedientes
                if e.modelo == obligation.modelo and (target_year is None or e.ejercicio == target_year)
            )
            if already:
                _logger.debug(
                    "already-filed gate triggered modelo=%s period=%s expediente_count=%d",
                    obligation.modelo,
                    obligation.period,
                    len(already),
                )
                already_summary = _summary_text(f"Already filed: modelo={obligation.modelo} period={obligation.period}")
                steps.append(
                    WorkflowStep(
                        stage=WorkflowStage.BUILDING_DRAFT,
                        started_at=started,
                        ended_at=_utcnow(),
                        success=False,
                        summary=already_summary,
                        details={
                            "modelo": obligation.modelo,
                            "period": obligation.period,
                            "expediente_count": str(len(already)),
                        },
                    )
                )
                raise WorkflowAbortSignalError(
                    reason=WorkflowAbortReason.ALREADY_FILED,
                    summary=already_summary,
                )

        try:
            inputs: Mapping[str, object] = self._inputs_provider.load_inputs(
                modelo=obligation.modelo,
                period=obligation.period,
                profile=profile,
            )
        except SiteHealthError as exc:
            self._record_site_unavailable(
                stage=WorkflowStage.BUILDING_DRAFT,
                started=started,
                exc=exc,
                steps=steps,
            )
        except Exception as exc:
            self._record_unhandled(
                stage=WorkflowStage.BUILDING_DRAFT,
                started=started,
                exc=exc,
                steps=steps,
            )
        try:
            draft = self._filing_draft_builder.build(
                modelo=obligation.modelo,
                period=obligation.period,
                profile=profile,
                inputs=inputs,
                fail_on_warning=fail_on_warning,
            )
        except SiteHealthError as exc:
            self._record_site_unavailable(
                stage=WorkflowStage.BUILDING_DRAFT,
                started=started,
                exc=exc,
                steps=steps,
            )
        except Exception as exc:
            self._record_unhandled(
                stage=WorkflowStage.BUILDING_DRAFT,
                started=started,
                exc=exc,
                steps=steps,
            )
        self._require_registry_draft_for_obligation(
            draft=draft,
            obligation=obligation,
            profile=profile,
            started=started,
            steps=steps,
        )
        ready_statuses = {
            ModeloDraftStatus.LISTO_PARA_PRESENTAR.value,
            ModeloDraftStatus.APROBADO.value,
        }
        if _enum_value(draft.status) not in ready_statuses:
            status_value = _enum_value(draft.status)
            status_summary = _summary_text(f"Draft {draft.draft_id} not ready: status={status_value}")
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.BUILDING_DRAFT,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary=status_summary,
                    details={"draft_id": draft.draft_id, "status": status_value},
                )
            )
            raise WorkflowAbortSignalError(
                reason=WorkflowAbortReason.DRAFT_HAS_ERRORS,
                summary=status_summary,
            )

        steps.append(
            WorkflowStep(
                stage=WorkflowStage.BUILDING_DRAFT,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary=_summary_text(f"Draft built draft_id={draft.draft_id}"),
                details={"draft_id": draft.draft_id},
            )
        )
        return draft

    def _require_registry_draft_for_obligation(
        self,
        *,
        draft: RegistryFilingDraftProtocol,
        obligation: ModeloDeadline,
        profile: AutonomoProfile,
        started: datetime,
        steps: list[WorkflowStep],
    ) -> None:
        mismatches: dict[str, str] = {}
        if draft.modelo != obligation.modelo:
            mismatches["modelo"] = f"{draft.modelo} != {obligation.modelo}"
        if draft.period != obligation.period:
            mismatches["period"] = f"{draft.period} != {obligation.period}"
        if draft.profile_tax_id != profile.tax_id:
            mismatches["profile_tax_id"] = f"{draft.profile_tax_id} != {profile.tax_id}"
        try:
            expected_schema_version = self._active_registry_schema_version(obligation)
        except (ModeloBuilderError, ValueError) as exc:
            mismatches["schema_version"] = f"{draft.schema_version}; active registry schema unavailable: {exc}"
        else:
            if draft.schema_version != expected_schema_version:
                mismatches["schema_version"] = f"{draft.schema_version} != {expected_schema_version}"
        if not mismatches:
            return

        summary = _summary_text(f"Draft {draft.draft_id} does not match registry-backed workflow obligation")
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.BUILDING_DRAFT,
                started_at=started,
                ended_at=_utcnow(),
                success=False,
                summary=summary,
                details={"draft_id": draft.draft_id, **mismatches},
            )
        )
        raise WorkflowAbortSignalError(
            reason=WorkflowAbortReason.DRAFT_HAS_ERRORS,
            summary=summary,
        )

    def _active_registry_schema_version(self, obligation: ModeloDeadline) -> str:
        filing_year, registry_period = _registry_period_token(obligation.period)
        provider = build_runtime_schema_provider(
            filing_year=filing_year,
            period=registry_period,
            modelos=(obligation.modelo,),
        )
        return provider.get_subview(obligation.modelo).schema_version

    def _stage_validating_draft(
        self,
        *,
        draft: RegistryFilingDraftProtocol,
        steps: list[WorkflowStep],
    ) -> None:
        """Stage 6 — re-scan the built draft for ERROR-severity findings."""
        started = _utcnow()
        error_findings = tuple(
            f for f in draft.findings if _enum_value(getattr(f, "severity", None)) == BaseSeverity.ERROR
        )
        if error_findings:
            errors_summary = _summary_text(f"Draft {draft.draft_id} has {len(error_findings)} ERROR finding(s)")
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.VALIDATING_DRAFT,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary=errors_summary,
                    details={"error_count": str(len(error_findings))},
                )
            )
            raise WorkflowAbortSignalError(
                reason=WorkflowAbortReason.DRAFT_HAS_ERRORS,
                summary=errors_summary,
            )
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.VALIDATING_DRAFT,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary=_summary_text("Draft validation clean"),
            )
        )

    def _stage_running_preflight(
        self,
        *,
        draft: RegistryFilingDraftProtocol,
        today: date,
        steps: list[WorkflowStep],
    ) -> None:
        """Stage 7 — run preflight gates and verify the auth provider.

        Aborts with ``CERT_INVALID`` if the auth-provider Protocol
        raises, and with ``PREFLIGHT_FAILED`` on any
        :class:`aeat.adapters.outbound.aeat.export.SubmissionPreflightError`.
        """
        started = _utcnow()
        cert_details: dict[str, str]
        if self._certificate_bundle is not None:
            try:
                certificate = self._certificate_bundle.describe()
            except Exception as exc:
                cert_summary = _summary_text(f"Certificate load failed: {type(exc).__name__}")
                steps.append(
                    WorkflowStep(
                        stage=WorkflowStage.RUNNING_PREFLIGHT,
                        started_at=started,
                        ended_at=_utcnow(),
                        success=False,
                        summary=cert_summary,
                        details={
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                        },
                    )
                )
                raise WorkflowAbortSignalError(
                    reason=WorkflowAbortReason.CERT_INVALID,
                    summary=cert_summary,
                ) from exc
            cert_details = {
                "provider_kind": certificate.kind.value,
                "provider_operator_impact": describe_provider_operator_impact(certificate),
            }
            if not certificate.configured or not certificate.available:
                provider_summary = _summary_text(
                    f"Auth provider unavailable: kind={certificate.kind.value} "
                    f"configured={certificate.configured} available={certificate.available}. "
                    f"{describe_provider_operator_impact(certificate)}"
                )
                steps.append(
                    WorkflowStep(
                        stage=WorkflowStage.RUNNING_PREFLIGHT,
                        started_at=started,
                        ended_at=_utcnow(),
                        success=False,
                        summary=provider_summary,
                        details=cert_details,
                    )
                )
                raise WorkflowAbortSignalError(
                    reason=WorkflowAbortReason.CERT_INVALID,
                    summary=provider_summary,
                )
            if certificate.expires_on is not None:
                cert_severity, days_until_expiry = _classify_cert_expiry(
                    not_after=certificate.expires_on,
                    today=today,
                    warn_days=self._settings.aeat_cert_warn_days,
                    critical_days=self._settings.aeat_cert_critical_days,
                )
                cert_details["cert_not_after"] = certificate.expires_on.isoformat()
                cert_details["cert_severity"] = cert_severity.value
                cert_details["cert_days_until_expiry"] = str(days_until_expiry)
            else:
                cert_severity = None
                days_until_expiry = None
            if (
                cert_severity
                in (
                    CertificateHealthSeverity.EXPIRED,
                    CertificateHealthSeverity.CRITICAL,
                )
                and cert_severity is not None
            ):
                expiry_summary = _summary_text(
                    f"Certificate pre-expiry gate: severity={cert_severity.value} "
                    f"days_until_expiry={days_until_expiry} "
                    f"kind={certificate.kind.value}"
                )
                steps.append(
                    WorkflowStep(
                        stage=WorkflowStage.RUNNING_PREFLIGHT,
                        started_at=started,
                        ended_at=_utcnow(),
                        success=False,
                        summary=expiry_summary,
                        details=cert_details,
                    )
                )
                raise WorkflowAbortSignalError(
                    reason=WorkflowAbortReason.CERT_INVALID,
                    summary=expiry_summary,
                )
            if cert_severity is CertificateHealthSeverity.WARN:
                _logger.warning(
                    "workflow: certificate nearing expiry kind=%s days=%d",
                    certificate.kind.value,
                    days_until_expiry,
                )
        else:
            cert_details = {"cert_skipped": "not_wired"}

        try:
            self._submission_engine.preflight(draft, today=today)
        except SiteHealthError as exc:
            self._record_site_unavailable(
                stage=WorkflowStage.RUNNING_PREFLIGHT,
                started=started,
                exc=exc,
                steps=steps,
            )
        except SubmissionPreflightError as exc:
            preflight_summary = _summary_text(f"Preflight failed: {exc}")
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.RUNNING_PREFLIGHT,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary=preflight_summary,
                    details={**cert_details, "error_message": str(exc)},
                )
            )
            raise WorkflowAbortSignalError(
                reason=WorkflowAbortReason.PREFLIGHT_FAILED,
                summary=preflight_summary,
            ) from exc
        except Exception as exc:
            self._record_unhandled(
                stage=WorkflowStage.RUNNING_PREFLIGHT,
                started=started,
                exc=exc,
                steps=steps,
            )

        steps.append(
            WorkflowStep(
                stage=WorkflowStage.RUNNING_PREFLIGHT,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary=_summary_text("Preflight OK"),
                details=cert_details,
            )
        )

    # ---------------------------------------------------------------- helpers

    def _compute_current_run_id(self) -> str | None:
        """Return the run_id for the currently-in-flight ``_drive`` call.

        Prefers a resolved obligation's ``modelo``/``period`` over the
        caller-supplied targets so a site-health alert raised after
        ``COMPUTING_DEADLINES`` has resolved an obligation carries the
        same hash as the final :class:`WorkflowResult.run_id`. Returns
        ``None`` when called outside an active ``_drive`` call.
        """
        if self._run_tax_id is None or self._run_started_at is None:
            return None
        obligation = self._run_obligation
        modelo = self._run_target_modelo or (obligation.modelo if obligation is not None else "-")
        period = self._run_target_period or (obligation.period if obligation is not None else "-")
        return compute_run_id(
            tax_id=self._run_tax_id,
            modelo=modelo,
            period=period,
            started_at=self._run_started_at,
        )

    def _record_unhandled(
        self,
        *,
        stage: WorkflowStage,
        started: datetime,
        exc: BaseException,
        steps: list[WorkflowStep],
    ) -> NoReturn:
        """Record a failed step and raise ``WorkflowAbortSignalError(UNHANDLED_EXCEPTION)``.

        Centralises the wrap-and-record ritual so every stage method
        surfaces an unexpected exception identically.
        """
        _logger.warning(
            "workflow stage raised an unhandled exception stage=%s",
            stage.value,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        unhandled_summary = _summary_text(f"Unhandled {type(exc).__name__} at stage={stage.value}: {exc}")
        steps.append(
            WorkflowStep(
                stage=stage,
                started_at=started,
                ended_at=_utcnow(),
                success=False,
                summary=unhandled_summary,
                details={
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
        )
        wrapped = WorkflowComponentError(f"{stage.value} component raised {type(exc).__name__}: {exc}")
        wrapped.__cause__ = exc
        raise WorkflowAbortSignalError(
            reason=WorkflowAbortReason.UNHANDLED_EXCEPTION,
            summary=unhandled_summary,
        ) from wrapped

    def _record_site_unavailable(
        self,
        *,
        stage: WorkflowStage,
        started: datetime,
        exc: SiteHealthError,
        steps: list[WorkflowStep],
    ) -> NoReturn:
        """Record a site-health failure and abort with ``SITE_UNAVAILABLE``."""

        alert_run_id = self._compute_current_run_id() or "-"
        summary = _summary_text(f"AEAT site unavailable at stage={stage.value}: {exc.status.state.value}")
        steps.append(
            WorkflowStep(
                stage=stage,
                started_at=started,
                ended_at=_utcnow(),
                success=False,
                summary=summary,
                site_health_alert=SiteHealthAlert(
                    stage=stage,
                    status=exc.status,
                    run_id=alert_run_id,
                ),
            )
        )
        raise WorkflowAbortSignalError(
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            summary=summary,
        ) from exc


def declaration_key(modelo: str, period: str) -> str:
    """Return the stable dictionary key for a modelo/period pair."""
    return f"{modelo.strip()}:{period.strip().upper()}"


def update_declaration_pointer(
    state: WorkflowState,
    *,
    modelo: str,
    period: str,
    draft_id: str | None = None,
    status: str | None = None,
    exported_path: str | None = None,
) -> WorkflowState:
    """Return a copy of ``state`` with an updated declaration pointer.

    Upserts a :class:`DeclaracionPointer` into the ``declarations``
    registry. If a pointer already exists for the key, its fields are
    updated with the supplied values.
    """
    key = declaration_key(modelo, period)
    current = state.declarations.get(key)
    if current is None:
        updated = DeclaracionPointer(
            modelo=modelo,
            period=period,
            draft_id=draft_id,
            status=status,
            exported_path=exported_path,
        )
    else:
        updated = current.model_copy(
            update={
                k: v
                for k, v in {
                    "draft_id": draft_id,
                    "status": status,
                    "exported_path": exported_path,
                }.items()
                if v is not None
            }
        )

    new_declarations = dict(state.declarations)
    new_declarations[key] = updated
    return state.model_copy(update={"declarations": new_declarations})


__all__ = [
    "ExpedientesSource",
    "NotificationsSource",
    "WorkflowEngine",
    "declaration_key",
    "update_declaration_pointer",
]