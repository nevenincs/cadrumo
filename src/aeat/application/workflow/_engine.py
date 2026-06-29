"""Composition root for the end-user composite workflow engine.

:class:`WorkflowEngine` walks the filing pipeline in strict linear order. Every
stage lives in its own small ``_stage_*`` method so the bailout matrix
is trivially auditable — a reader drops into a single stage method to
see exactly which abort reasons it can produce. The engine derives a
:class:`Schedule` from the injected deadline adapter to gate the filing
window against the active obligation calendar.

Safety invariants enforced by this module:

- The engine never touches AEAT-side state directly; every boundary
  call flows through an injected Protocol or callable seam.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import NoReturn

from ...application.auth import describe_provider_operator_impact
from ...core import Period
from ...core.config import Settings
from ...core.errors import BaseSeverity, SiteHealthError
from ...core.logging import get_logger
from ...core.time import now as _utcnow
from ...domain.deadlines import (
    ModeloDeadline,
    ObligationStatus,
    TaxpayerProfile,
)
from ...domain.filing import ModeloBuilderError
from ...domain.submission import ModeloDraftStatus, SubmissionPreflightError
from ..filing.runtime import build_runtime_schema_provider
from ._deadline_stage import abort_missing_deadline_obligation, resolve_deadline_stage_obligation
from ._engine_helpers import (
    DeadlineRole,
    FilingWindowState,
)
from ._engine_helpers import (
    classify_cert_expiry as _classify_cert_expiry,
)
from ._engine_helpers import (
    draft_blocking_finding_descriptions as _draft_blocking_finding_descriptions,
)
from ._engine_helpers import (
    enum_value as _enum_value,
)
from ._engine_helpers import (
    registry_filing_year as _registry_filing_year,
)
from ._engine_helpers import (
    summary_text as _summary_text,
)
from ._engine_recording import record_site_unavailable, record_unhandled
from ._errors import WorkflowAbortSignalError, WorkflowError, WorkflowInputMismatchError
from ._models import (
    WorkflowAbortReason,
    WorkflowPurpose,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
    compute_run_id,
    declaration_key,
)
from ._protocols import (
    CertificateBundleProtocol,
    DeadlineEngineProtocol,
    ExpedientesSource,
    ModeloDraftBuilderProtocol,
    ModeloInputs,
    ModeloInputsProviderProtocol,
    NotificationsSource,
    RegistryModeloDraftProtocol,
    SubmissionEngineProtocol,
)

_logger = get_logger(__name__)


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
        filing_draft_builder: ModeloDraftBuilderProtocol,
        submission_engine: SubmissionEngineProtocol,
        session: object | None,
        certificate_bundle: CertificateBundleProtocol | None,
        inputs_provider: ModeloInputsProviderProtocol,
        settings: Settings,
        expedientes_source: ExpedientesSource | None = None,
        notifications_source: NotificationsSource | None = None,
    ) -> None:
        """Construct a :class:`WorkflowEngine`.

        Args:
            deadline_engine: Protocol over :class:`aeat.domain.deadlines.DeadlineEngine`.
            filing_draft_builder: Protocol over :func:`aeat.application.filing.build_draft`.
            submission_engine: Protocol over :class:`~aeat.domain.submission.SubmissionEngine`.
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
        self._expedientes_source = expedientes_source
        self._notifications_source = notifications_source
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
        self._run_target_period: Period | None = None
        self._run_obligation: ModeloDeadline | None = None

    # ------------------------------------------------------------------ public

    async def run_next(
        self,
        profile: TaxpayerProfile,
        *,
        fail_on_warning: bool = False,
        today: date | None = None,
    ) -> WorkflowResult:
        """Drive the workflow for the caller's next obligation.

        Args:
            profile: The :class:`TaxpayerProfile` to run for.
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
        profile: TaxpayerProfile,
        modelo: str,
        period: Period,
        *,
        fail_on_warning: bool = False,
        today: date | None = None,
        resumed_from: str | None = None,
        purpose: WorkflowPurpose = WorkflowPurpose.FILE,
    ) -> WorkflowResult:
        """Drive the workflow for a caller-specified ``(modelo, period)``.

        Args:
            profile: The :class:`TaxpayerProfile` to run for.
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
            purpose: Why the run is being driven. ``FILE`` (the
                default) treats the filing-window deadline as an abort
                gate; ``VERIFY`` records it as informational context
                and never aborts on it, so a calculation can be
                verified independently of the AEAT calendar.

        Returns:
            A fully populated :class:`WorkflowResult`.

        Raises:
            WorkflowInputMismatchError: When ``resumed_from`` is supplied
                but is not a valid 16-character lowercase hex run id.
        """
        if resumed_from is not None:
            stripped = resumed_from.strip()
            if len(stripped) != 16 or any(c not in "0123456789abcdef" for c in stripped):
                raise WorkflowInputMismatchError(
                    f"resumed_from must be a 16-character lowercase hex run id; got {resumed_from!r}",
                )
            resumed_from = stripped
        return await self._drive(
            profile=profile,
            target_modelo=modelo,
            target_period=period,
            fail_on_warning=fail_on_warning,
            today=today,
            resumed_from=resumed_from,
            purpose=purpose,
        )

    # ------------------------------------------------------------------ driver

    async def _drive(
        self,
        *,
        profile: TaxpayerProfile,
        target_modelo: str | None,
        target_period: Period | None,
        fail_on_warning: bool,
        today: date | None,
        resumed_from: str | None = None,
        purpose: WorkflowPurpose = WorkflowPurpose.FILE,
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
        draft: RegistryModeloDraftProtocol | None = None
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
                purpose=purpose,
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
                purpose=purpose,
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
        period_for_hash: Period | None = target_period or (obligation.period if obligation is not None else None)
        period_for_summary = str(period_for_hash) if period_for_hash is not None else "-"
        run_id = compute_run_id(
            tax_id=profile.tax_id,
            modelo=modelo_for_hash,
            period=period_for_hash,
            started_at=started_at,
        )

        summary: str
        if final_stage is WorkflowStage.DONE:
            summary = _summary_text(f"Workflow completed: modelo={modelo_for_hash} period={period_for_summary}")
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
        profile: TaxpayerProfile,
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
            ),
        )

    def _stage_computing_deadlines(
        self,
        *,
        profile: TaxpayerProfile,
        target_modelo: str | None,
        target_period: Period | None,
        today: date,
        steps: list[WorkflowStep],
        purpose: WorkflowPurpose = WorkflowPurpose.FILE,
    ) -> ModeloDeadline:
        """Stage 3 — compute the target obligation.

        The schedule is computed through
        :func:`compute_obligation_schedule`, the single producer of the
        pending-obligation datum shared with the operator state
        read-projection, so this gate and ``projection.pending_obligations``
        cannot draw a divergent obligation set. The gate then applies
        its own narrow filtering (``next_deadline`` or per-target
        ``(modelo, period)`` match) over that shared schedule.

        For :attr:`WorkflowPurpose.FILE`, aborts with
        ``NO_PENDING_OBLIGATION`` when the schedule is empty or the
        narrow-target is absent, and with ``DEADLINE_PASSED`` when the
        selected obligation has already closed against ``today``.

        For :attr:`WorkflowPurpose.VERIFY`, neither abort fires:
        verification asserts a calculation is internally sound and has
        no honest dependency on the AEAT filing calendar. The
        filing-window state is recorded as informational step
        ``details`` instead. When no scheduled obligation matches the
        verify target, a context-only :class:`ModeloDeadline` is
        synthesised purely so the downstream draft/validation stages
        have the ``(modelo, period)`` to build against.
        """
        started = _utcnow()
        try:
            obligation = resolve_deadline_stage_obligation(
                self._deadline_engine,
                profile,
                target_modelo=target_modelo,
                target_period=target_period,
                today=today,
                purpose=purpose,
            )
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

        if purpose is WorkflowPurpose.VERIFY:
            return self._record_verify_deadline_context(
                obligation=obligation,
                target_modelo=target_modelo,
                target_period=target_period,
                today=today,
                started=started,
                steps=steps,
            )

        if obligation is None:
            abort_missing_deadline_obligation(started=started, steps=steps)

        if obligation.opens_on > today:
            future_summary = _summary_text(
                f"Filing obligation for modelo={obligation.modelo} "
                f"period={obligation.period} opens on {obligation.opens_on.isoformat()}; "
                "the AEAT filing-obligation window is not open yet. Filing-to-fichero does "
                "not require this step: export the verified-complete revision with "
                "'aeat app modelo export' — that is the local finish line. 'work file' "
                "is the optional internal mark-as-filed step for when the obligation window is open.",
            )
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.COMPUTING_DEADLINES,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary=future_summary,
                    details={
                        "modelo": obligation.modelo,
                        "period": str(obligation.period),
                        "opens_on": obligation.opens_on.isoformat(),
                        "closes_on": obligation.closes_on.isoformat(),
                        "filing_window": FilingWindowState.FUTURE,
                        "deadline_role": DeadlineRole.BINDING,
                    },
                ),
            )
            raise WorkflowAbortSignalError(
                reason=WorkflowAbortReason.NO_PENDING_OBLIGATION,
                summary=future_summary,
            )

        if obligation.closes_on < today:
            if target_modelo is not None and target_period is not None:
                # A targeted but closed-window obligation that genuinely
                # existed is filed locally and late (extemporánea, con recargo)
                # rather than refused; `work file` contacts AEAT zero times.
                overdue_summary = _summary_text(
                    f"Obligation modelo={obligation.modelo} "
                    f"period={obligation.period} closed on {obligation.closes_on.isoformat()}; "
                    "recording a late local filing (extemporánea, con recargo).",
                )
                steps.append(
                    WorkflowStep(
                        stage=WorkflowStage.COMPUTING_DEADLINES,
                        started_at=started,
                        ended_at=_utcnow(),
                        success=True,
                        summary=overdue_summary,
                        details={
                            "modelo": obligation.modelo,
                            "period": str(obligation.period),
                            "closes_on": obligation.closes_on.isoformat(),
                            "overdue": "true",
                            "extemporanea": "true",
                        },
                    ),
                )
                return obligation
            closed_summary = _summary_text(
                f"Deadline for modelo={obligation.modelo} "
                f"period={obligation.period} closed on {obligation.closes_on.isoformat()}",
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
                        "period": str(obligation.period),
                        "closes_on": obligation.closes_on.isoformat(),
                    },
                ),
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
                    f"period={obligation.period} closes_on={obligation.closes_on.isoformat()}",
                ),
                details={
                    "modelo": obligation.modelo,
                    "period": str(obligation.period),
                    "opens_on": obligation.opens_on.isoformat(),
                    "closes_on": obligation.closes_on.isoformat(),
                },
            ),
        )
        return obligation

    def _record_verify_deadline_context(
        self,
        *,
        obligation: ModeloDeadline | None,
        target_modelo: str | None,
        target_period: Period | None,
        today: date,
        started: datetime,
        steps: list[WorkflowStep],
    ) -> ModeloDeadline:
        """Record the filing-window state for a verify run without aborting.

        Verification of a calculation is independent of the AEAT filing
        calendar (see the work-verify deadline-independence ADR). This
        helper turns the ``COMPUTING_DEADLINES`` stage into a purely
        informational step for :attr:`WorkflowPurpose.VERIFY`: it never
        raises ``NO_PENDING_OBLIGATION`` or ``DEADLINE_PASSED``.

        When a scheduled obligation matches the verify target, its real
        filing window is surfaced as informational ``details``. When
        none matches, a context-only :class:`ModeloDeadline` is
        synthesised so the downstream draft/validation stages still
        have a ``(modelo, period)`` carrier; the synthetic record is
        explicitly marked ``NOT_APPLICABLE`` and never reaches a
        filing path.
        """
        if obligation is not None:
            if obligation.opens_on > today:
                window_state = FilingWindowState.FUTURE
            elif obligation.closes_on >= today:
                window_state = FilingWindowState.OPEN
            else:
                window_state = FilingWindowState.CLOSED
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.COMPUTING_DEADLINES,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=True,
                    summary=_summary_text(
                        f"Filing window for modelo={obligation.modelo} "
                        f"period={obligation.period} {window_state} "
                        f"(closes_on={obligation.closes_on.isoformat()}); "
                        "informational only — verification does not depend on it",
                    ),
                    details={
                        "modelo": obligation.modelo,
                        "period": str(obligation.period),
                        "opens_on": obligation.opens_on.isoformat(),
                        "closes_on": obligation.closes_on.isoformat(),
                        "filing_window": window_state,
                        "deadline_role": DeadlineRole.INFORMATIONAL,
                    },
                ),
            )
            return obligation

        if target_modelo is None or target_period is None:
            raise WorkflowError(
                "verify workflow requires an explicit (modelo, period) target",
            )
        synthetic = ModeloDeadline(
            modelo=target_modelo,
            period=target_period,
            opens_on=today,
            closes_on=today,
            status=ObligationStatus.NOT_APPLICABLE,
            applies_because=(
                "Verification context only: no AEAT filing window is "
                "open for this period. Verifying a calculation does not "
                "depend on the filing calendar."
            ),
        )
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary=_summary_text(
                    f"No open filing window for modelo={target_modelo} "
                    f"period={target_period}; informational only — "
                    "verification does not depend on it",
                ),
                details={
                    "modelo": target_modelo,
                    "period": str(target_period),
                    "filing_window": FilingWindowState.ABSENT,
                    "deadline_role": "informational",
                },
            ),
        )
        return synthetic

    async def _stage_checking_inbox(
        self,
        *,
        profile: TaxpayerProfile,
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
        if self._session is None or self._notifications_source is None:
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.CHECKING_INBOX,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=True,
                    summary=_summary_text("Inbox skipped (not wired)"),
                    details={"skipped": "not_wired"},
                ),
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
                f"Inbox has {len(blockers)} blocking requerimiento(s) for modelo={obligation.modelo}",
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
                ),
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
            ),
        )

    async def _stage_building_draft(
        self,
        *,
        profile: TaxpayerProfile,
        obligation: ModeloDeadline,
        fail_on_warning: bool,
        steps: list[WorkflowStep],
    ) -> RegistryModeloDraftProtocol:
        """Stage 5 — consult the status reader, load inputs, build the draft.

        Aborts with ``ALREADY_FILED`` if the (optional) status reader
        reports an existing expediente for the same
        ``(modelo, period)``. Aborts with ``DRAFT_HAS_ERRORS`` if the
        builder refuses to promote the draft to ``READY_TO_SUBMIT``.
        Any unexpected exception lands as ``UNHANDLED_EXCEPTION``.
        """
        started = _utcnow()

        if self._session is not None and self._expedientes_source is not None:
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
            target_year = _registry_filing_year(obligation.period)
            already = tuple(e for e in expedientes if e.modelo == obligation.modelo and e.ejercicio == target_year)
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
                            "period": str(obligation.period),
                            "expediente_count": str(len(already)),
                        },
                    ),
                )
                raise WorkflowAbortSignalError(
                    reason=WorkflowAbortReason.ALREADY_FILED,
                    summary=already_summary,
                )

        try:
            inputs: ModeloInputs = self._inputs_provider.load_inputs(
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
            blocking_findings = _draft_blocking_finding_descriptions(draft)
            findings_clause = f"; blocking findings: {'; '.join(blocking_findings)}" if blocking_findings else ""
            status_summary = _summary_text(
                f"Draft {draft.draft_id} not ready: status={status_value}{findings_clause}",
            )
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.BUILDING_DRAFT,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary=status_summary,
                    details={
                        "draft_id": draft.draft_id,
                        "status": status_value,
                        "blocking_findings": "; ".join(blocking_findings) if blocking_findings else "",
                        "next_action": (
                            "Run: aeat app modelo verification-report list"
                            " --calculation-revision-id <calculation_revision_id>"
                        ),
                    },
                ),
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
            ),
        )
        return draft

    def _require_registry_draft_for_obligation(
        self,
        *,
        draft: RegistryModeloDraftProtocol,
        obligation: ModeloDeadline,
        profile: TaxpayerProfile,
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
            ),
        )
        raise WorkflowAbortSignalError(
            reason=WorkflowAbortReason.DRAFT_HAS_ERRORS,
            summary=summary,
        )

    def _active_registry_schema_version(self, obligation: ModeloDeadline) -> str:
        provider = build_runtime_schema_provider(
            filing_year=obligation.period.filing_year,
            period=obligation.period,
            modelos=(obligation.modelo,),
        )
        return provider.get_subview(obligation.modelo).schema_version

    def _stage_validating_draft(
        self,
        *,
        draft: RegistryModeloDraftProtocol,
        steps: list[WorkflowStep],
    ) -> None:
        """Stage 6 — re-scan the built draft for ERROR-severity findings."""
        started = _utcnow()
        error_findings = tuple(
            f for f in draft.findings if _enum_value(getattr(f, "severity", None)) == BaseSeverity.ERROR
        )
        if error_findings:
            descriptions = _draft_blocking_finding_descriptions(draft)
            errors_summary = _summary_text(
                f"Draft {draft.draft_id} has {len(error_findings)} ERROR finding(s): "
                + ("; ".join(descriptions) if descriptions else "see verification report")
            )
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.VALIDATING_DRAFT,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary=errors_summary,
                    details={
                        "error_count": str(len(error_findings)),
                        "next_action": (
                            "Run: aeat app modelo verification-report list"
                            " --calculation-revision-id <calculation_revision_id>"
                        ),
                    },
                ),
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
            ),
        )

    def _stage_running_preflight(
        self,
        *,
        draft: RegistryModeloDraftProtocol,
        today: date,
        steps: list[WorkflowStep],
        purpose: WorkflowPurpose = WorkflowPurpose.FILE,
    ) -> None:
        """Stage 7 — run preflight gates and verify the auth provider.

        Aborts with ``CERT_INVALID`` if the auth-provider Protocol
        raises, and with ``PREFLIGHT_FAILED`` on any
        :class:`~aeat.domain.submission.SubmissionPreflightError`.

        For local :attr:`WorkflowPurpose.VERIFY` and
        :attr:`WorkflowPurpose.FILE`, the AEAT filing-window preflight
        gate is skipped. VERIFY is calendar-independent; FILE is a local
        mark-as-filed path whose obligation existence has already been
        enforced by the deadline stage. The draft-soundness and
        auth-provider gates still run, so an unsound calculation is still
        refused.
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
                    ),
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
                    f"{describe_provider_operator_impact(certificate)}",
                )
                steps.append(
                    WorkflowStep(
                        stage=WorkflowStage.RUNNING_PREFLIGHT,
                        started_at=started,
                        ended_at=_utcnow(),
                        success=False,
                        summary=provider_summary,
                        details=cert_details,
                    ),
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
                cert_details["cert_severity"] = cert_severity
                cert_details["cert_days_until_expiry"] = str(days_until_expiry)
            else:
                cert_severity = None
                days_until_expiry = None
            if (
                cert_severity
                in (
                    "EXPIRED",
                    "CRITICAL",
                )
                and cert_severity is not None
            ):
                expiry_summary = _summary_text(
                    f"Certificate pre-expiry gate: severity={cert_severity} "
                    f"days_until_expiry={days_until_expiry} "
                    f"kind={certificate.kind.value}",
                )
                steps.append(
                    WorkflowStep(
                        stage=WorkflowStage.RUNNING_PREFLIGHT,
                        started_at=started,
                        ended_at=_utcnow(),
                        success=False,
                        summary=expiry_summary,
                        details=cert_details,
                    ),
                )
                raise WorkflowAbortSignalError(
                    reason=WorkflowAbortReason.CERT_INVALID,
                    summary=expiry_summary,
                )
            if cert_severity == "WARN":
                _logger.warning(
                    "workflow: certificate nearing expiry kind=%s days=%d",
                    certificate.kind.value,
                    days_until_expiry,
                )
        else:
            cert_details = {"cert_skipped": "not_wired"}

        try:
            # The AEAT filing-window preflight gate is skipped for BOTH local
            # purposes. VERIFY is calendar-independent (work-verify
            # deadline-independence ADR). FILE is a LOCAL mark-as-filed that
            # contacts AEAT zero times (cross-period filing deadlock ADR,
            # Decision A): its obligation existence is already enforced at the
            # deadline stage (NO_PENDING_OBLIGATION still refuses a never-existing
            # obligation; an existing-but-overdue one is admitted late, con
            # recargo). Re-applying the submission filing-window gate here would
            # contradict that and re-block the legitimate late local filing that
            # seeds the next period's cross-period carry. The window gate binds
            # only an actual AEAT submission, which this app never performs.
            skip_window = purpose in (WorkflowPurpose.VERIFY, WorkflowPurpose.FILE)
            self._submission_engine.preflight(
                draft,
                today=today,
                skip_deadline_window=skip_window,
            )
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
                ),
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
            ),
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
        period: Period | None = self._run_target_period or (obligation.period if obligation is not None else None)
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
        record_unhandled(stage=stage, started=started, exc=exc, steps=steps)

    def _record_site_unavailable(
        self,
        *,
        stage: WorkflowStage,
        started: datetime,
        exc: SiteHealthError,
        steps: list[WorkflowStep],
    ) -> NoReturn:
        record_site_unavailable(
            stage=stage,
            started=started,
            exc=exc,
            steps=steps,
            current_run_id=self._compute_current_run_id,
        )


__all__ = [
    "ExpedientesSource",
    "NotificationsSource",
    "WorkflowEngine",
    "declaration_key",
]
