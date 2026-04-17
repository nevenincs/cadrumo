"""Composition root for the end-user composite workflow engine.

:class:`WorkflowEngine` walks the ten stages defined in
[[2026-04-12-workflow-engine-adr]] in strict linear order. Every
stage lives in its own small ``_stage_*`` method so the bailout
matrix is trivially auditable — a reader drops into a single stage
method to see exactly which abort reasons it can produce.

Safety invariants enforced by this module:

- Callers must spell out ``dry_run=...`` at the API level.
- The engine never touches AEAT-side state directly; every boundary
  call flows through an injected Protocol.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import NoReturn, cast

from ..auth import CertificateHealthSeverity
from ..config import Settings
from ..deadlines import AutonomoProfile, FilingObligation, Schedule, next_deadline
from ..errors import SiteHealthError
from ..i18n import Translatable
from ..logging import get_logger
from ..status import SiteHealthAlert
from ..submission import (
    DraftStatus,
    FilingDraftLike,
    FilingFindingSeverity,
    SubmissionPreflightError,
)
from ._errors import WorkflowComponentError
from ._models import (
    WorkflowAbortReason,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
    compute_run_id,
)
from ._protocols import (
    CertificateBundleProtocol,
    DeadlineEngineProtocol,
    FilingDraftBuilderProtocol,
    FilingInputsProviderProtocol,
    InboxProtocol,
    StatusReaderProtocol,
    SubmissionEngineProtocol,
    SubmittedFilingLike,
    SyncRunnerProtocol,
)

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

    Operates on the narrow :class:`aeat.submission.LoadedCertificate`
    stub surface (``not_after: date``) rather than the rich
    :class:`aeat.auth.LoadedCertificate`, so it can be called from the
    workflow engine without forcing a sibling-branch rebase. Boundary
    semantics match :func:`aeat.auth.evaluate_loaded_certificate_health`:
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


def _t(en: str) -> Translatable:
    """Build a :class:`Translatable` carrying a single English message."""
    return cast(Translatable, {"en": en})


def _enum_value(value: object) -> str:
    """Return ``Enum.value`` when present, otherwise ``str(value)``."""
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return str(raw)


class _AbortError(Exception):
    """Internal signal raised by a stage method to trigger a bailout.

    Never propagates outside :class:`WorkflowEngine` — :meth:`_drive`
    always catches it and materialises the :class:`WorkflowResult`.
    """

    def __init__(
        self,
        *,
        reason: WorkflowAbortReason,
        summary: Translatable,
    ) -> None:
        super().__init__(reason.value)
        self.reason = reason
        self.summary = summary


class WorkflowEngine:
    """Ordered orchestrator across every AEAT building block.

    Construction takes one Protocol handle per component. The status
    reader, inbox, and certificate bundle are optional: when ``None``,
    their stages run in skip mode and surface a diagnostic instead of
    failing. See [[2026-04-12-workflow-engine-plan]] for the
    degradation rules.
    """

    def __init__(
        self,
        *,
        deadline_engine: DeadlineEngineProtocol,
        filing_draft_builder: FilingDraftBuilderProtocol,
        submission_engine: SubmissionEngineProtocol,
        sync_runner: SyncRunnerProtocol | None,
        status_reader: StatusReaderProtocol | None,
        inbox: InboxProtocol | None,
        certificate_bundle: CertificateBundleProtocol | None,
        inputs_provider: FilingInputsProviderProtocol,
        settings: Settings,
    ) -> None:
        """Construct a :class:`WorkflowEngine`.

        Args:
            deadline_engine: Protocol over :class:`aeat.deadlines.DeadlineEngine`.
            filing_draft_builder: Protocol over :func:`aeat.filing.build_draft`.
            submission_engine: Protocol over :class:`aeat.submission.SubmissionEngine`.
            sync_runner: Optional Protocol over the sync runner. ``None``
                causes the ``SYNCING_CATALOGUES`` stage to skip.
            status_reader: Optional Protocol over the status reader
                (#43, in flight). ``None`` skips the already-filed probe.
            inbox: Optional Protocol over the notifications inbox
                (#46, in flight). ``None`` skips the requerimiento probe.
            certificate_bundle: Optional Protocol over the certificate
                backend (#8, in flight). ``None`` skips the cert load probe.
            inputs_provider: Protocol that supplies casilla inputs for
                the draft stage.
            settings: Application :class:`Settings` instance.
        """
        self._deadline_engine = deadline_engine
        self._filing_draft_builder = filing_draft_builder
        self._submission_engine = submission_engine
        self._sync_runner = sync_runner
        self._status_reader = status_reader
        self._inbox = inbox
        self._certificate_bundle = certificate_bundle
        self._inputs_provider = inputs_provider
        self._settings = settings
        # Lazy run-id recomputation state. These are set at the start
        # of every ``_drive`` call and consumed by
        # ``_record_site_unavailable`` so an alert raised *after* the
        # obligation has been resolved carries a ``run_id`` that
        # matches the final :class:`WorkflowResult.run_id`. When no
        # obligation is known yet (e.g. ``SiteHealthError`` from the
        # sync or deadline stage of an open-ended ``run_next`` call)
        # the ``-`` placeholders are expected and match the
        # placeholders in the final result.
        self._run_tax_id: str | None = None
        self._run_started_at: datetime | None = None
        self._run_target_modelo: str | None = None
        self._run_target_period: str | None = None
        self._run_obligation: FilingObligation | None = None

    # ------------------------------------------------------------------ public

    async def run_next(
        self,
        profile: AutonomoProfile,
        *,
        dry_run: bool,
        sync_first: bool | None = None,
        fail_on_warning: bool = False,
        today: date | None = None,
    ) -> WorkflowResult:
        """Drive the workflow for the caller's next obligation.

        Args:
            profile: The :class:`AutonomoProfile` to run for.
            dry_run: When ``True`` the dry-run submit leg is taken; no
                live AEAT submission is attempted.
            sync_first: Whether to run the sync runner before the
                deadline computation. ``None`` means "use the
                ``AEAT_WORKFLOW_SYNC_FIRST_DEFAULT`` setting".
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
            dry_run=dry_run,
            sync_first=sync_first,
            fail_on_warning=fail_on_warning,
            today=today,
        )

    async def run_for_period(
        self,
        profile: AutonomoProfile,
        modelo: str,
        period: str,
        *,
        dry_run: bool,
        sync_first: bool | None = None,
        fail_on_warning: bool = False,
        today: date | None = None,
    ) -> WorkflowResult:
        """Drive the workflow for a caller-specified ``(modelo, period)``.

        Args:
            profile: The :class:`AutonomoProfile` to run for.
            modelo: Target modelo identifier.
            period: Target period identifier.
            dry_run: See :meth:`run_next`.
            sync_first: See :meth:`run_next`.
            fail_on_warning: See :meth:`run_next`.
            today: See :meth:`run_next`.

        Returns:
            A fully populated :class:`WorkflowResult`.
        """
        return await self._drive(
            profile=profile,
            target_modelo=modelo,
            target_period=period,
            dry_run=dry_run,
            sync_first=sync_first,
            fail_on_warning=fail_on_warning,
            today=today,
        )

    # ------------------------------------------------------------------ driver

    async def _drive(
        self,
        *,
        profile: AutonomoProfile,
        target_modelo: str | None,
        target_period: str | None,
        dry_run: bool,
        sync_first: bool | None,
        fail_on_warning: bool,
        today: date | None,
    ) -> WorkflowResult:
        """Linearly walk the ten stages, bailing on the first failure."""
        started_at = _utcnow()
        reference_today = today or date.today()
        should_sync = sync_first if sync_first is not None else self._settings.aeat_workflow_sync_first_default

        # Record run context so ``_record_site_unavailable`` can lazily
        # recompute the run_id from whichever information is latest
        # (preferring a resolved obligation over caller targets).
        self._run_tax_id = profile.tax_id
        self._run_started_at = started_at
        self._run_target_modelo = target_modelo
        self._run_target_period = target_period
        self._run_obligation = None

        steps: list[WorkflowStep] = []
        obligation: FilingObligation | None = None
        draft: FilingDraftLike | None = None
        submission: SubmittedFilingLike | None = None
        final_stage: WorkflowStage = WorkflowStage.ABORTED
        aborted_reason: WorkflowAbortReason | None = None
        abort_summary: Translatable | None = None

        try:
            self._stage_loading_profile(profile, steps)
            await self._stage_syncing_catalogues(
                should_sync=should_sync,
                target_modelo=target_modelo,
                target_period=target_period,
                steps=steps,
            )
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
            submission = await self._stage_dry_run_submit(
                draft=draft,
                dry_run=dry_run,
                today=reference_today,
                steps=steps,
            )
            final_stage = WorkflowStage.DONE
        except _AbortError as abort:
            aborted_reason = abort.reason
            abort_summary = abort.summary
            _logger.info(
                "workflow: aborted at stage=%s reason=%s",
                steps[-1].stage if steps else "?",
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

        summary: Translatable
        if final_stage is WorkflowStage.DONE:
            summary = _t(f"Workflow completed: modelo={modelo_for_hash} period={period_for_hash}")
        elif abort_summary is not None:
            summary = abort_summary
        else:
            reason_text = aborted_reason.value if aborted_reason is not None else "unknown"
            summary = _t(f"Workflow aborted: {reason_text}")

        return WorkflowResult(
            run_id=run_id,
            started_at=started_at,
            ended_at=ended_at,
            final_stage=final_stage,
            aborted_reason=aborted_reason,
            obligation=obligation,
            draft_id=draft.draft_id if draft is not None else None,
            submission_id=submission.submission_id if submission is not None else None,
            steps=tuple(steps),
            summary=summary,
        )

    # ------------------------------------------------------------------ stages

    def _stage_loading_profile(
        self,
        profile: AutonomoProfile,
        steps: list[WorkflowStep],
    ) -> None:
        """Stage 1 — validate the incoming profile.

        The profile is already a strict pydantic model, so this stage
        is mostly an audit log. It still exists as a distinct step so
        the ten-stage contract is visible in every result.
        """
        started = _utcnow()
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.LOADING_PROFILE,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary=_t(f"Loaded profile tax_id={profile.tax_id}"),
            )
        )

    async def _stage_syncing_catalogues(
        self,
        *,
        should_sync: bool,
        target_modelo: str | None,
        target_period: str | None,
        steps: list[WorkflowStep],
    ) -> None:
        """Stage 2 — run the self-healing sync runner if configured."""
        started = _utcnow()
        if not should_sync:
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.SYNCING_CATALOGUES,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=True,
                    summary=_t("Sync skipped (sync_first=False)"),
                    details={"skipped": "sync_first_false"},
                )
            )
            return
        if self._sync_runner is None:
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.SYNCING_CATALOGUES,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=True,
                    summary=_t("Sync skipped (runner not wired)"),
                    details={"skipped": "not_wired"},
                )
            )
            return
        try:
            summary_result = await self._sync_runner.run(
                modelo=target_modelo,
                period=target_period,
                auto_heal=False,
            )
        except SiteHealthError as exc:
            self._record_site_unavailable(
                stage=WorkflowStage.SYNCING_CATALOGUES,
                started=started,
                exc=exc,
                steps=steps,
            )
        except Exception as exc:
            self._record_unhandled(
                stage=WorkflowStage.SYNCING_CATALOGUES,
                started=started,
                exc=exc,
                steps=steps,
            )
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.SYNCING_CATALOGUES,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary=_t(f"Sync OK divergences={summary_result.divergence_count}"),
                details={
                    "divergence_count": str(summary_result.divergence_count),
                    "auto_healed_count": str(summary_result.auto_healed_count),
                    "escalated_count": str(summary_result.escalated_count),
                },
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
    ) -> FilingObligation:
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

        obligation: FilingObligation | None
        if target_modelo is not None and target_period is not None:
            matches = [o for o in schedule.obligations if o.modelo == target_modelo and o.period == target_period]
            obligation = matches[0] if matches else None
        else:
            obligation = next_deadline(schedule, today=today)

        if obligation is None:
            no_summary = _t("No pending filing obligation for this profile")
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.COMPUTING_DEADLINES,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary=no_summary,
                )
            )
            raise _AbortError(
                reason=WorkflowAbortReason.NO_PENDING_OBLIGATION,
                summary=no_summary,
            )

        if obligation.closes_on < today:
            closed_summary = _t(
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
            raise _AbortError(
                reason=WorkflowAbortReason.DEADLINE_PASSED,
                summary=closed_summary,
            )

        steps.append(
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary=_t(
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
        obligation: FilingObligation,
        steps: list[WorkflowStep],
    ) -> None:
        """Stage 4 — probe the notifications inbox for blocking requerimientos."""
        started = _utcnow()
        if self._inbox is None:
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.CHECKING_INBOX,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=True,
                    summary=_t("Inbox skipped (not wired)"),
                    details={"skipped": "not_wired"},
                )
            )
            return
        try:
            requerimientos = await self._inbox.fetch_blocking_requerimientos(
                tax_id=profile.tax_id,
                modelo=obligation.modelo,
            )
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
        blockers = tuple(r for r in requerimientos if r.blocks_submission)
        if blockers:
            blocked_summary = _t(f"Inbox has {len(blockers)} blocking requerimiento(s) for modelo={obligation.modelo}")
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.CHECKING_INBOX,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary=blocked_summary,
                    details={
                        "blocker_count": str(len(blockers)),
                        "first_notificacion_id": blockers[0].notificacion_id,
                    },
                )
            )
            raise _AbortError(
                reason=WorkflowAbortReason.INBOX_BLOCKING_REQUERIMIENTO,
                summary=blocked_summary,
            )
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.CHECKING_INBOX,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary=_t("Inbox clear"),
            )
        )

    async def _stage_building_draft(
        self,
        *,
        profile: AutonomoProfile,
        obligation: FilingObligation,
        fail_on_warning: bool,
        steps: list[WorkflowStep],
    ) -> FilingDraftLike:
        """Stage 5 — consult the status reader, load inputs, build the draft.

        Aborts with ``ALREADY_FILED`` if the (optional) status reader
        reports an existing expediente for the same
        ``(modelo, period)``. Aborts with ``DRAFT_HAS_ERRORS`` if the
        builder refuses to promote the draft to ``READY_TO_SUBMIT``.
        Any unexpected exception lands as ``UNHANDLED_EXCEPTION``.
        """
        started = _utcnow()

        if self._status_reader is not None:
            try:
                expedientes = await self._status_reader.fetch_expedientes(tax_id=profile.tax_id)
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
            already = tuple(e for e in expedientes if e.modelo == obligation.modelo and e.period == obligation.period)
            if already:
                already_summary = _t(f"Already filed: modelo={obligation.modelo} period={obligation.period}")
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
                raise _AbortError(
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
        if _enum_value(draft.status) != DraftStatus.READY_TO_SUBMIT.value:
            status_value = _enum_value(draft.status)
            status_summary = _t(f"Draft {draft.draft_id} not ready: status={status_value}")
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
            raise _AbortError(
                reason=WorkflowAbortReason.DRAFT_HAS_ERRORS,
                summary=status_summary,
            )

        steps.append(
            WorkflowStep(
                stage=WorkflowStage.BUILDING_DRAFT,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary=_t(f"Draft built draft_id={draft.draft_id}"),
                details={"draft_id": draft.draft_id},
            )
        )
        return draft

    def _stage_validating_draft(
        self,
        *,
        draft: FilingDraftLike,
        steps: list[WorkflowStep],
    ) -> None:
        """Stage 6 — re-scan the built draft for ERROR-severity findings."""
        started = _utcnow()
        error_findings = tuple(
            f for f in draft.findings if _enum_value(getattr(f, "severity", None)) == FilingFindingSeverity.ERROR
        )
        if error_findings:
            errors_summary = _t(f"Draft {draft.draft_id} has {len(error_findings)} ERROR finding(s)")
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
            raise _AbortError(
                reason=WorkflowAbortReason.DRAFT_HAS_ERRORS,
                summary=errors_summary,
            )
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.VALIDATING_DRAFT,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary=_t("Draft validation clean"),
            )
        )

    def _stage_running_preflight(
        self,
        *,
        draft: FilingDraftLike,
        today: date,
        steps: list[WorkflowStep],
    ) -> None:
        """Stage 7 — run preflight gates and verify the certificate.

        Aborts with ``CERT_INVALID`` if the certificate bundle Protocol
        raises, and with ``PREFLIGHT_FAILED`` on any
        :class:`aeat.submission.SubmissionPreflightError`.
        """
        started = _utcnow()
        cert_details: dict[str, str]
        if self._certificate_bundle is not None:
            try:
                certificate = self._certificate_bundle.load()
            except Exception as exc:
                cert_summary = _t(f"Certificate load failed: {type(exc).__name__}")
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
                raise _AbortError(
                    reason=WorkflowAbortReason.CERT_INVALID,
                    summary=cert_summary,
                ) from exc
            cert_severity, days_until_expiry = _classify_cert_expiry(
                not_after=certificate.not_after,
                today=today,
                warn_days=self._settings.aeat_cert_warn_days,
                critical_days=self._settings.aeat_cert_critical_days,
            )
            cert_details = {
                "cert_subject": certificate.subject,
                "cert_not_after": certificate.not_after.isoformat(),
                "cert_severity": cert_severity.value,
                "cert_days_until_expiry": str(days_until_expiry),
            }
            if cert_severity in (
                CertificateHealthSeverity.EXPIRED,
                CertificateHealthSeverity.CRITICAL,
            ):
                expiry_summary = _t(
                    f"Certificate pre-expiry gate: severity={cert_severity.value} "
                    f"days_until_expiry={days_until_expiry} "
                    f"subject={certificate.subject}"
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
                raise _AbortError(
                    reason=WorkflowAbortReason.CERT_INVALID,
                    summary=expiry_summary,
                )
            if cert_severity is CertificateHealthSeverity.WARN:
                _logger.warning(
                    "workflow: certificate nearing expiry subject=%s days=%d",
                    certificate.subject,
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
            preflight_summary = _t(f"Preflight failed: {exc}")
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
            raise _AbortError(
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
                summary=_t("Preflight OK"),
                details=cert_details,
            )
        )

    async def _stage_dry_run_submit(
        self,
        *,
        draft: FilingDraftLike,
        dry_run: bool,
        today: date,
        steps: list[WorkflowStep],
    ) -> SubmittedFilingLike:
        """Stage 8 — dispatch to the submission engine.

        The submission engine owns the live-write refusal gates and
        confirmation hook; workflow only forwards the explicit mode.
        """
        started = _utcnow()
        try:
            submission = await self._submission_engine.submit_draft(
                draft,
                dry_run=dry_run,
                today=today,
            )
        except SiteHealthError as exc:
            self._record_site_unavailable(
                stage=WorkflowStage.DRY_RUN_SUBMIT,
                started=started,
                exc=exc,
                steps=steps,
            )
        except SubmissionPreflightError as exc:
            preflight_summary = _t(f"Preflight failed: {exc}")
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.DRY_RUN_SUBMIT,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary=preflight_summary,
                    details={"dry_run": str(dry_run), "error_message": str(exc)},
                )
            )
            raise _AbortError(
                reason=WorkflowAbortReason.PREFLIGHT_FAILED,
                summary=preflight_summary,
            ) from exc
        except Exception as exc:
            self._record_unhandled(
                stage=WorkflowStage.DRY_RUN_SUBMIT,
                started=started,
                exc=exc,
                steps=steps,
            )
        mode_label = "dry-run" if dry_run else "LIVE"
        submit_summary = _t(f"Submit {mode_label} OK submission_id={submission.submission_id}")
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.DRY_RUN_SUBMIT,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary=submit_summary,
                details={
                    "submission_id": submission.submission_id,
                    "status": str(submission.status),
                    "dry_run": str(dry_run),
                },
            )
        )
        return submission

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
        """Record a failed step and raise ``_AbortError(UNHANDLED_EXCEPTION)``.

        Centralises the wrap-and-record ritual so every stage method
        surfaces an unexpected exception identically.
        """
        unhandled_summary = _t(f"Unhandled {type(exc).__name__} at stage={stage.value}: {exc}")
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
        raise _AbortError(
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
        """Record a typed site-health alert and raise ``SITE_UNAVAILABLE``.

        Invoked from the ``except SiteHealthError`` arm inserted
        strictly *before* the generic ``except Exception`` catch in
        every stage method that wraps a component call. The helper
        composes a :class:`aeat.status.SiteHealthAlert` around the
        caught error, appends a failed :class:`WorkflowStep` carrying
        the alert, and raises
        ``_AbortError(reason=WorkflowAbortReason.SITE_UNAVAILABLE)``
        so the collapse to ``UNHANDLED_EXCEPTION`` never fires.
        """
        run_id = self._compute_current_run_id() or "unassigned"
        alert = SiteHealthAlert(
            stage=stage,
            status=exc.status,
            run_id=run_id,
        )
        state_label = exc.status.state.value
        summary = _t(f"Site unavailable at stage={stage.value}: {state_label}")
        steps.append(
            WorkflowStep(
                stage=stage,
                started_at=started,
                ended_at=_utcnow(),
                success=False,
                summary=summary,
                details={
                    "site_health_state": state_label,
                    "http_status": str(exc.status.evidence.http_status),
                },
                site_health_alert=alert,
            )
        )
        raise _AbortError(
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            summary=summary,
        ) from exc
