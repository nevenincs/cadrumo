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

from collections.abc import Mapping
from datetime import date, datetime
from typing import NoReturn

from ...core import (
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    Modelo,
    NoRecoveryOutcome,
)
from ...core.period import Period
from ...core.config import Settings
from ...core.errors.hierarchy import SiteHealthError
from ...core.errors.severity import BaseSeverity
from ...core.logging import get_logger
from ...core.parsing import enum_value as _enum_value
from ...core.time import now as _utcnow
from ...core.time import today_madrid
from ...domain.deadlines.models import ModeloDeadline, ObligationStatus, TaxpayerProfile
from ...domain.filing.errors import ModeloBuilderError
from ...domain.submission import ModeloDraftStatus, SubmissionPreflightError
from ..filing.runtime import build_runtime_schema_provider
from ..operator_actions import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
    no_action_precondition_verdict,
)
from ._deadline_stage import abort_missing_deadline_obligation, resolve_deadline_stage_obligation
from .engine_helpers import (
    DeadlineRole,
    FilingWindowState,
)
from .engine_helpers import (
    classify_cert_expiry as _classify_cert_expiry,
)
from .engine_helpers import (
    registry_filing_year as _registry_filing_year,
)
from .engine_recording import record_site_unavailable, record_unhandled
from .errors import WorkflowAbortSignalError, WorkflowError, WorkflowInputMismatchError
from .protocols import (
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
from .run_models import (
    WorkflowAbortReason,
    WorkflowAlreadyFiledDetails,
    WorkflowAuthCheckDetails,
    WorkflowDeadlineContextDetails,
    WorkflowDiagnosticSkipReason,
    WorkflowDraftBuiltDetails,
    WorkflowDraftMismatchDetails,
    WorkflowDraftNotReadyDetails,
    WorkflowFailureDetails,
    WorkflowInboxBlockedDetails,
    WorkflowInboxSkippedDetails,
    WorkflowObligationFacts,
    WorkflowPreflightFailedDetails,
    WorkflowPurpose,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
    WorkflowValidationFailedDetails,
    compute_run_id,
)

_logger = get_logger(__name__)

type WorkflowDeadlineTarget = ModeloDeadline | WorkflowObligationFacts


def _no_recovery_verdict(
    *,
    condition_id: str,
    evidence_id: str,
    provenance: ActionEvidenceProvenance,
    values: Mapping[str, str | int | bool],
    outcome: NoRecoveryOutcome,
) -> PreconditionVerdict:
    """Build one closed non-actionable workflow precondition outcome."""
    return no_action_precondition_verdict(
        condition_id=condition_id,
        evidence_id=evidence_id,
        facts=values,
        provenance=provenance,
        outcome=outcome,
    )


def _conditional_action_verdict(
    *,
    condition_id: str,
    evidence_id: str,
    provenance: ActionEvidenceProvenance,
    values: Mapping[str, str | int | bool],
    action_id: str,
    missing_argument_names: tuple[str, ...],
) -> PreconditionVerdict:
    """Build one typed next action whose missing address is explicit."""
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            ConditionEvidence(
                condition_id=condition_id,
                evidence_id=evidence_id,
                provenance=provenance,
                values=values,
            ),
        ),
        action=ActionReference(action_id=action_id),
        argument_bindings=tuple(
            ActionArgumentBinding(argument_name=name, status=ActionArgumentStatus.MISSING)
            for name in missing_argument_names
        ),
        missing_argument_names=missing_argument_names,
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )


def _draft_blocking_finding_codes(draft: RegistryModeloDraftProtocol) -> tuple[str, ...]:
    """Return stable finding identifiers without retaining rendered descriptions.

    ``severity`` and ``code`` are read as typed attributes, never through
    ``getattr(..., None)``: :attr:`RegistryModeloDraftProtocol.findings` is
    typed ``tuple[WorkflowFindingLike, ...]``, and that Protocol declares both
    fields required, so a rename fails loud here. Read defensively, a renamed
    field would silently drop every finding from this diagnostic detail --
    the same fail-open shape ``_stage_validating_draft`` and
    ``domain/submission/_preflight.py`` carried, just feeding a reported
    detail on an already-decided abort rather than the abort decision itself.
    """
    codes: set[str] = set()
    for finding in draft.findings:
        code = finding.code
        if (
            finding.severity in {BaseSeverity.ERROR, BaseSeverity.WARNING}
            and code
            and not any(character.isspace() for character in code)
        ):
            codes.add(code)
    return tuple(sorted(codes))


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
            deadline_engine: Protocol over :class:`domain.deadlines.DeadlineEngine`.
            filing_draft_builder: Protocol over :func:`application.filing.build_draft`.
            submission_engine: Protocol over :class:`~domain.submission.SubmissionEngine`.
            session: Optional authenticated :class:`adapters.outbound.aeat.auth.AeatSession`
                used to drive the live :mod:`adapters.outbound.aeat.sede` reader. ``None``
                skips both the inbox probe and the already-filed probe.
            certificate_bundle: Optional Protocol over the certificate
                backend. ``None`` skips the cert load probe.
            inputs_provider: Protocol that supplies casilla inputs for
                the draft stage.
            settings: Application :class:`Settings` instance.
            expedientes_source: Test seam over
                :func:`adapters.outbound.aeat.sede.walk_expedientes_tree`. Defaults to the
                live walker.
            notifications_source: Test seam over
                a bucket-scoped application capture. ``None`` leaves the
                inbox stage not wired; it must never default to a direct
                outbound-adapter fetch.
        """
        self._deadline_engine = deadline_engine
        self._filing_draft_builder = filing_draft_builder
        self._submission_engine = submission_engine
        self.session = session
        self._certificate_bundle = certificate_bundle
        self._inputs_provider = inputs_provider
        self._settings = settings
        self.expedientes_source = expedientes_source
        self.notifications_source = notifications_source
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
        self._run_obligation: WorkflowDeadlineTarget | None = None

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
                    translated_message="application.modelo.errors.workflow_input_mismatch",
                    context={"field": "resumed_from", "value": str(resumed_from), "run_id_shape_valid": False},
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
        reference_today = today or today_madrid()

        # Record run context so ``_record_site_unavailable`` can lazily
        # recompute the run_id from whichever information is latest
        # (preferring a resolved obligation over caller targets).
        self._run_tax_id = profile.tax_id
        self._run_started_at = started_at
        self._run_target_modelo = target_modelo
        self._run_target_period = target_period
        self._run_obligation = None

        steps: list[WorkflowStep] = []
        obligation: WorkflowDeadlineTarget | None = None
        draft: RegistryModeloDraftProtocol | None = None
        final_stage: WorkflowStage = WorkflowStage.ABORTED
        aborted_reason: WorkflowAbortReason | None = None

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
        run_id = compute_run_id(
            tax_id=profile.tax_id,
            modelo=modelo_for_hash,
            period=period_for_hash,
            started_at=started_at,
        )

        summary_locale_key: str
        summary_details = steps[-1].details if steps else None
        if final_stage is WorkflowStage.DONE:
            summary_locale_key = "application.workflow.results.completed"
        else:
            summary_locale_key = "application.workflow.results.aborted"

        return WorkflowResult(
            run_id=run_id,
            started_at=started_at,
            ended_at=ended_at,
            final_stage=final_stage,
            aborted_reason=aborted_reason,
            obligation=_persisted_obligation(obligation),
            draft_id=draft.draft_id if draft is not None else None,
            submission_id=None,
            steps=tuple(steps),
            summary_locale_key=summary_locale_key,
            summary_details=summary_details,
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
                summary_locale_key="application.workflow.steps.profile_loaded",
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
    ) -> WorkflowDeadlineTarget:
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
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.COMPUTING_DEADLINES,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary_locale_key="application.workflow.steps.deadline_future",
                    details=WorkflowDeadlineContextDetails(
                        kind="deadline_context",
                        modelo=obligation.modelo,
                        period=obligation.period,
                        opens_on=obligation.opens_on,
                        closes_on=obligation.closes_on,
                        filing_window=FilingWindowState.FUTURE,
                        deadline_role=DeadlineRole.BINDING,
                    ),
                    precondition_verdict=_no_recovery_verdict(
                        condition_id="workflow.deadline.filing_window_open",
                        evidence_id="workflow.deadline.window",
                        provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
                        values={
                            "filing_window": FilingWindowState.FUTURE.value,
                            "modelo": obligation.modelo.value,
                            "filing_year": obligation.period.filing_year,
                            "period_code": obligation.period.registry_token,
                        },
                        outcome=NoRecoveryOutcome.TERMINAL,
                    ),
                ),
            )
            raise WorkflowAbortSignalError(reason=WorkflowAbortReason.NO_PENDING_OBLIGATION)

        if obligation.closes_on < today:
            if target_modelo is not None and target_period is not None:
                # A targeted but closed-window obligation that genuinely
                # existed is filed locally and late (extemporánea, con recargo)
                # rather than refused; `work file` contacts AEAT zero times.
                steps.append(
                    WorkflowStep(
                        stage=WorkflowStage.COMPUTING_DEADLINES,
                        started_at=started,
                        ended_at=_utcnow(),
                        success=True,
                        summary_locale_key="application.workflow.steps.deadline_overdue",
                        details=WorkflowDeadlineContextDetails(
                            kind="deadline_context",
                            modelo=obligation.modelo,
                            period=obligation.period,
                            closes_on=obligation.closes_on,
                            overdue=True,
                            extemporanea=True,
                        ),
                    ),
                )
                return obligation
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.COMPUTING_DEADLINES,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary_locale_key="application.workflow.steps.deadline_closed",
                    details=WorkflowDeadlineContextDetails(
                        kind="deadline_context",
                        modelo=obligation.modelo,
                        period=obligation.period,
                        closes_on=obligation.closes_on,
                    ),
                    precondition_verdict=_no_recovery_verdict(
                        condition_id="workflow.deadline.filing_window_open",
                        evidence_id="workflow.deadline.window",
                        provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
                        values={
                            "filing_window": FilingWindowState.CLOSED.value,
                            "modelo": obligation.modelo.value,
                            "filing_year": obligation.period.filing_year,
                            "period_code": obligation.period.registry_token,
                        },
                        outcome=NoRecoveryOutcome.TERMINAL,
                    ),
                ),
            )
            raise WorkflowAbortSignalError(reason=WorkflowAbortReason.DEADLINE_PASSED)

        steps.append(
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary_locale_key="application.workflow.steps.deadline_open",
                details=WorkflowDeadlineContextDetails(
                    kind="deadline_context",
                    modelo=obligation.modelo,
                    period=obligation.period,
                    opens_on=obligation.opens_on,
                    closes_on=obligation.closes_on,
                ),
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
    ) -> WorkflowDeadlineTarget:
        """Record the filing-window state for a verify run without aborting.

        Verification of a calculation is independent of the AEAT filing
        calendar. This
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
                    summary_locale_key="application.workflow.steps.deadline_informational",
                    details=WorkflowDeadlineContextDetails(
                        kind="deadline_context",
                        modelo=obligation.modelo,
                        period=obligation.period,
                        opens_on=obligation.opens_on,
                        closes_on=obligation.closes_on,
                        filing_window=window_state,
                        deadline_role=DeadlineRole.INFORMATIONAL,
                    ),
                ),
            )
            return obligation

        if target_modelo is None or target_period is None:
            raise WorkflowError(
                translated_message="errors.error.error_workflow",
                context={"workflow": "verify", "explicit_target_supplied": False},
            )
        synthetic = WorkflowObligationFacts(
            modelo=Modelo(target_modelo),
            period=target_period,
            opens_on=today,
            closes_on=today,
            status=ObligationStatus.NOT_APPLICABLE,
        )
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary_locale_key="application.workflow.steps.deadline_absent",
                details=WorkflowDeadlineContextDetails(
                    kind="deadline_context",
                    modelo=Modelo(target_modelo),
                    period=target_period,
                    filing_window=FilingWindowState.ABSENT,
                    deadline_role=DeadlineRole.INFORMATIONAL,
                ),
            ),
        )
        return synthetic

    async def _stage_checking_inbox(
        self,
        *,
        profile: TaxpayerProfile,
        obligation: WorkflowDeadlineTarget,
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
        if self.session is None or self.notifications_source is None:
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.CHECKING_INBOX,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=True,
                    summary_locale_key="application.workflow.steps.inbox_skipped",
                    details=WorkflowInboxSkippedDetails(
                        kind="inbox_skipped",
                        skip_reason=WorkflowDiagnosticSkipReason.NOT_WIRED,
                    ),
                ),
            )
            return
        try:
            snapshot = await self.notifications_source(self.session)
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
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.CHECKING_INBOX,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary_locale_key="application.workflow.steps.inbox_blocked",
                    details=WorkflowInboxBlockedDetails(
                        kind="inbox_blocked",
                        blocker_count=len(blockers),
                        first_notificacion_id=blockers[0].certificado_id,
                    ),
                    precondition_verdict=_no_recovery_verdict(
                        condition_id="workflow.inbox.clear",
                        evidence_id="workflow.inbox.blockers",
                        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                        values={"blocker_count": len(blockers), "inbox_clear": False},
                        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                    ),
                ),
            )
            raise WorkflowAbortSignalError(reason=WorkflowAbortReason.INBOX_BLOCKING_REQUERIMIENTO)
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.CHECKING_INBOX,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary_locale_key="application.workflow.steps.inbox_clear",
            ),
        )

    async def _stage_building_draft(
        self,
        *,
        profile: TaxpayerProfile,
        obligation: WorkflowDeadlineTarget,
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
        await self._abort_if_already_filed(obligation=obligation, started=started, steps=steps)
        draft = self._load_and_build_draft(
            profile=profile,
            obligation=obligation,
            fail_on_warning=fail_on_warning,
            started=started,
            steps=steps,
        )
        self._require_registry_draft_for_obligation(
            draft=draft,
            obligation=obligation,
            profile=profile,
            started=started,
            steps=steps,
        )
        self._abort_if_draft_not_ready(draft=draft, started=started, steps=steps)

        steps.append(
            WorkflowStep(
                stage=WorkflowStage.BUILDING_DRAFT,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary_locale_key="application.workflow.steps.draft_built",
                details=WorkflowDraftBuiltDetails(kind="draft_built", draft_id=draft.draft_id),
            ),
        )
        return draft

    async def _abort_if_already_filed(
        self,
        *,
        obligation: WorkflowDeadlineTarget,
        started: datetime,
        steps: list[WorkflowStep],
    ) -> None:
        """Abort with ``ALREADY_FILED`` when the status reader reports an existing expediente."""
        if self.session is not None and self.expedientes_source is not None:
            try:
                expedientes = await self.expedientes_source(self.session, obligation.modelo)
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
                steps.append(
                    WorkflowStep(
                        stage=WorkflowStage.BUILDING_DRAFT,
                        started_at=started,
                        ended_at=_utcnow(),
                        success=False,
                        summary_locale_key="application.workflow.steps.already_filed",
                        details=WorkflowAlreadyFiledDetails(
                            kind="already_filed",
                            modelo=obligation.modelo,
                            period=obligation.period,
                            expediente_count=len(already),
                        ),
                        precondition_verdict=_no_recovery_verdict(
                            condition_id="workflow.obligation.unfiled",
                            evidence_id="workflow.obligation.filing_state",
                            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                            values={
                                "expediente_count": len(already),
                                "modelo": obligation.modelo.value,
                                "filing_year": obligation.period.filing_year,
                                "period_code": obligation.period.registry_token,
                                "unfiled": False,
                            },
                            outcome=NoRecoveryOutcome.TERMINAL,
                        ),
                    ),
                )
                raise WorkflowAbortSignalError(reason=WorkflowAbortReason.ALREADY_FILED)

    def _load_and_build_draft(
        self,
        *,
        profile: TaxpayerProfile,
        obligation: WorkflowDeadlineTarget,
        fail_on_warning: bool,
        started: datetime,
        steps: list[WorkflowStep],
    ) -> RegistryModeloDraftProtocol:
        """Load modelo inputs and build the draft, recording site/build failures.

        Aborts with ``DRAFT_HAS_ERRORS`` when the builder refuses; a
        :class:`SiteHealthError` or any other unexpected exception is recorded and
        re-raised through :meth:`_record_site_unavailable` / :meth:`_record_unhandled`.
        """
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
        except ModeloBuilderError as exc:
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.BUILDING_DRAFT,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary_locale_key="application.workflow.steps.draft_build_failed",
                    details=WorkflowFailureDetails(
                        kind="workflow_failure",
                        error_code="workflow.draft.build_failure",
                    ),
                    precondition_verdict=_conditional_action_verdict(
                        condition_id="workflow.draft.buildable",
                        evidence_id="workflow.draft.build_failure",
                        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                        values={"buildable": False},
                        action_id="operator.modelo.work.calculate",
                        missing_argument_names=("work_unit_id",),
                    ),
                ),
            )
            raise WorkflowAbortSignalError(reason=WorkflowAbortReason.DRAFT_HAS_ERRORS) from exc
        except Exception as exc:
            self._record_unhandled(
                stage=WorkflowStage.BUILDING_DRAFT,
                started=started,
                exc=exc,
                steps=steps,
            )
        return draft

    def _abort_if_draft_not_ready(
        self,
        *,
        draft: RegistryModeloDraftProtocol,
        started: datetime,
        steps: list[WorkflowStep],
    ) -> None:
        """Abort with ``DRAFT_HAS_ERRORS`` unless the draft promoted to a ready status."""
        ready_statuses = {
            ModeloDraftStatus.LISTO_PARA_PRESENTAR.value,
            ModeloDraftStatus.APROBADO.value,
        }
        if _enum_value(draft.status) not in ready_statuses:
            status_value = _enum_value(draft.status)
            blocking_finding_codes = _draft_blocking_finding_codes(draft)
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.BUILDING_DRAFT,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary_locale_key="application.workflow.steps.draft_not_ready",
                    details=WorkflowDraftNotReadyDetails(
                        kind="draft_not_ready",
                        draft_id=draft.draft_id,
                        draft_status=ModeloDraftStatus(status_value),
                        blocking_finding_codes=blocking_finding_codes,
                    ),
                    precondition_verdict=_conditional_action_verdict(
                        condition_id="workflow.draft.ready",
                        evidence_id="workflow.draft.status",
                        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
                        values={"draft_id": draft.draft_id, "draft_status": status_value, "ready": False},
                        action_id="operator.modelo.verification_report.list",
                        missing_argument_names=("calculation_revision_id",),
                    ),
                ),
            )
            raise WorkflowAbortSignalError(reason=WorkflowAbortReason.DRAFT_HAS_ERRORS)

    def _require_registry_draft_for_obligation(
        self,
        *,
        draft: RegistryModeloDraftProtocol,
        obligation: WorkflowDeadlineTarget,
        profile: TaxpayerProfile,
        started: datetime,
        steps: list[WorkflowStep],
    ) -> None:
        identity_evidence: dict[str, str | bool] = {
            "draft_id": draft.draft_id,
            "modelo_matches": draft.modelo == obligation.modelo,
            "period_matches": draft.period == obligation.period,
            "profile_tax_id_matches": draft.profile_tax_id == profile.tax_id,
        }
        try:
            expected_schema_version = self._active_registry_schema_version(obligation)
        except (ModeloBuilderError, ValueError) as exc:
            del exc
            identity_evidence["registry_schema_resolved"] = False
        else:
            identity_evidence["registry_schema_resolved"] = True
            identity_evidence["schema_version_matches"] = draft.schema_version == expected_schema_version
        if all(value is not False for value in identity_evidence.values()):
            return

        steps.append(
            WorkflowStep(
                stage=WorkflowStage.BUILDING_DRAFT,
                started_at=started,
                ended_at=_utcnow(),
                success=False,
                summary_locale_key="application.workflow.steps.draft_identity_mismatch",
                details=WorkflowDraftMismatchDetails(kind="draft_mismatch", draft_id=draft.draft_id),
                precondition_verdict=_no_recovery_verdict(
                    condition_id="workflow.draft.identity_matches",
                    evidence_id="workflow.draft.identity",
                    provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
                    values=identity_evidence,
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                ),
            ),
        )
        raise WorkflowAbortSignalError(reason=WorkflowAbortReason.DRAFT_HAS_ERRORS)

    def _active_registry_schema_version(self, obligation: WorkflowDeadlineTarget) -> str:
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
        """Stage 6 — re-scan the built draft for ERROR-severity findings.

        ``severity`` is read as a typed attribute, never through
        ``getattr(..., None)``. :attr:`ModeloDraftLike.findings` is typed
        ``tuple[ModeloFindingLike, ...]``, and that Protocol declares
        ``severity`` required, so a rename fails loud here. Read defensively,
        a renamed field would yield ``None`` for EVERY finding, this stage
        would find no errors on a draft that has them, and it would report
        success — the same fail-open this file's sibling gate carried in
        ``domain/submission/_preflight.py``.
        """
        started = _utcnow()
        error_findings = tuple(f for f in draft.findings if f.severity == BaseSeverity.ERROR)
        if error_findings:
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.VALIDATING_DRAFT,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary_locale_key="application.workflow.steps.validation_failed",
                    details=WorkflowValidationFailedDetails(
                        kind="validation_failed",
                        error_count=len(error_findings),
                    ),
                    precondition_verdict=_conditional_action_verdict(
                        condition_id="workflow.draft.validation_clean",
                        evidence_id="workflow.draft.validation",
                        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
                        values={"error_count": len(error_findings), "validation_clean": False},
                        action_id="operator.modelo.verification_report.list",
                        missing_argument_names=("calculation_revision_id",),
                    ),
                ),
            )
            raise WorkflowAbortSignalError(reason=WorkflowAbortReason.DRAFT_HAS_ERRORS)
        steps.append(
            WorkflowStep(
                stage=WorkflowStage.VALIDATING_DRAFT,
                started_at=started,
                ended_at=_utcnow(),
                success=True,
                summary_locale_key="application.workflow.steps.validation_clean",
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
        :class:`~domain.submission.SubmissionPreflightError`.

        For local :attr:`WorkflowPurpose.VERIFY` and
        :attr:`WorkflowPurpose.FILE`, the AEAT filing-window preflight
        gate is skipped. VERIFY is calendar-independent; FILE is a local
        mark-as-filed path whose obligation existence has already been
        enforced by the deadline stage. The draft-soundness and
        auth-provider gates still run, so an unsound calculation is still
        refused.
        """
        started = _utcnow()
        cert_details: WorkflowAuthCheckDetails
        if self._certificate_bundle is not None:
            try:
                certificate = self._certificate_bundle.describe()
            except Exception as exc:
                steps.append(
                    WorkflowStep(
                        stage=WorkflowStage.RUNNING_PREFLIGHT,
                        started_at=started,
                        ended_at=_utcnow(),
                        success=False,
                        summary_locale_key="application.workflow.steps.auth_certificate_load_failed",
                        details=WorkflowFailureDetails(
                            kind="workflow_failure",
                            error_code="workflow.auth.certificate_load_failed",
                        ),
                        precondition_verdict=_no_recovery_verdict(
                            condition_id="workflow.execution.completed",
                            evidence_id="workflow.execution.error_code",
                            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                            values={
                                "completed": False,
                                "error_code": "workflow.auth.certificate_load_failed",
                            },
                            outcome=NoRecoveryOutcome.TERMINAL,
                        ),
                    ),
                )
                raise WorkflowAbortSignalError(reason=WorkflowAbortReason.CERT_INVALID) from exc
            cert_details = WorkflowAuthCheckDetails(
                kind="auth_check",
                provider_kind=certificate.kind,
            )
            if not certificate.configured or not certificate.available:
                steps.append(
                    WorkflowStep(
                        stage=WorkflowStage.RUNNING_PREFLIGHT,
                        started_at=started,
                        ended_at=_utcnow(),
                        success=False,
                        summary_locale_key="application.workflow.steps.auth_provider_unavailable",
                        details=cert_details,
                        precondition_verdict=_no_recovery_verdict(
                            condition_id="workflow.auth.provider_available",
                            evidence_id="workflow.auth.provider_state",
                            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                            values={
                                "available": certificate.available,
                                "configured": certificate.configured,
                                "provider_kind": certificate.kind.value,
                            },
                            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                        ),
                    ),
                )
                raise WorkflowAbortSignalError(reason=WorkflowAbortReason.CERT_INVALID)
            if certificate.expires_on is not None:
                cert_severity, days_until_expiry = _classify_cert_expiry(
                    not_after=certificate.expires_on,
                    today=today,
                    warn_days=self._settings.cadrumo_cert_warn_days,
                    critical_days=self._settings.cadrumo_cert_critical_days,
                )
                cert_details = WorkflowAuthCheckDetails(
                    kind="auth_check",
                    provider_kind=certificate.kind,
                    cert_not_after=certificate.expires_on,
                    cert_severity=cert_severity,
                    cert_days_until_expiry=days_until_expiry,
                )
            else:
                cert_severity = None
                days_until_expiry = None
            if cert_severity in (
                "EXPIRED",
                "CRITICAL",
            ):
                steps.append(
                    WorkflowStep(
                        stage=WorkflowStage.RUNNING_PREFLIGHT,
                        started_at=started,
                        ended_at=_utcnow(),
                        success=False,
                        summary_locale_key="application.workflow.steps.auth_certificate_invalid",
                        details=cert_details,
                        precondition_verdict=_no_recovery_verdict(
                            condition_id="workflow.auth.certificate_valid",
                            evidence_id="workflow.auth.certificate_state",
                            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                            values={
                                "certificate_valid": False,
                                "cert_severity": cert_severity,
                                "provider_kind": certificate.kind.value,
                            },
                            outcome=NoRecoveryOutcome.SAFETY,
                        ),
                    ),
                )
                raise WorkflowAbortSignalError(reason=WorkflowAbortReason.CERT_INVALID)
            if cert_severity == "WARN":
                _logger.warning(
                    "workflow: certificate nearing expiry kind=%s days=%d",
                    certificate.kind.value,
                    days_until_expiry,
                )
        else:
            cert_details = WorkflowAuthCheckDetails(
                kind="auth_check",
                provider_check_skipped=True,
                skip_reason=WorkflowDiagnosticSkipReason.NOT_WIRED,
            )

        try:
            # The AEAT filing-window preflight gate is skipped for BOTH local
            # purposes. VERIFY is calendar-independent. FILE is a LOCAL
            # mark-as-filed that contacts AEAT zero times: its obligation
            # existence is already enforced at the
            # deadline stage (NO_PENDING_OBLIGATION still refuses a never-existing
            # obligation; an existing-but-overdue one is admitted late, con
            # recargo). Re-applying the submission filing-window gate here would
            # contradict that and re-block the legitimate late local filing that
            # seeds the next period's cross-period carry. The window gate binds
            # only an actual AEAT submission, which this app never performs.
            skip_window = purpose in (WorkflowPurpose.VERIFY, WorkflowPurpose.FILE)
            # Auth-provider readiness (gate 4) binds only live/AEAT-touching
            # purposes. Both workflow purposes are local (the app performs no
            # actual AEAT submission), so auth is not required to complete the
            # local build/verify/file/export flow; a taxpayer with no provider
            # configured uploads at the AEAT portal themselves (operator ruling).
            skip_auth = purpose in (WorkflowPurpose.VERIFY, WorkflowPurpose.FILE)
            self._submission_engine.preflight(
                draft,
                today=today,
                skip_deadline_window=skip_window,
                skip_auth_readiness=skip_auth,
            )
        except SiteHealthError as exc:
            self._record_site_unavailable(
                stage=WorkflowStage.RUNNING_PREFLIGHT,
                started=started,
                exc=exc,
                steps=steps,
            )
        except SubmissionPreflightError as exc:
            steps.append(
                WorkflowStep(
                    stage=WorkflowStage.RUNNING_PREFLIGHT,
                    started_at=started,
                    ended_at=_utcnow(),
                    success=False,
                    summary_locale_key="application.workflow.steps.preflight_failed",
                    details=WorkflowPreflightFailedDetails(
                        kind="preflight_failed",
                        error_code="workflow.submission.preflight_refused",
                        auth_check=cert_details,
                    ),
                    precondition_verdict=_no_recovery_verdict(
                        condition_id="workflow.submission.safe",
                        evidence_id="workflow.submission.safety_state",
                        provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
                        values={"submission_safe": False},
                        outcome=NoRecoveryOutcome.SAFETY,
                    ),
                ),
            )
            raise WorkflowAbortSignalError(reason=WorkflowAbortReason.PREFLIGHT_FAILED) from exc
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
                summary_locale_key="application.workflow.steps.preflight_completed",
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


def _persisted_obligation(obligation: WorkflowDeadlineTarget | None) -> WorkflowObligationFacts | None:
    """Return the locale-neutral durable projection for an in-flight deadline."""
    if obligation is None or isinstance(obligation, WorkflowObligationFacts):
        return obligation
    return WorkflowObligationFacts.from_deadline(obligation)


__all__ = [
    "WorkflowDeadlineTarget",
    "WorkflowEngine",
]
