"""Strict run contracts for the composite workflow engine.

This module owns stages, purposes, deadline observations, step details, and terminal
run results. Records are frozen strict Pydantic models or closed enumerations, and
persisted presentation carries locale keys rather than rendered prose. Encrypted
workflow state, declaration pointers, and active-profile helpers live in the separate
``_state_models`` owner.

See Also:
    :class:`~cadrumo.application.workflow.WorkflowEngine`
        Produces :class:`WorkflowResult` records and advances
        :class:`WorkflowStage` values.
    :class:`~cadrumo.application.workflow.WorkflowPurpose`
        Selects the local FILE or VERIFY policy that controls deadline and
        preflight treatment.
    :class:`~cadrumo.application.workflow.WorkflowRunRepository`
        Persists terminal :class:`WorkflowResult` records in secure storage.
    :class:`~cadrumo.application.workflow.WorkflowStateRepository`
        Persists the encrypted :class:`WorkflowState` envelope.
    :mod:`cadrumo.application.modelo._workflow_gate`
        Drives calculation revisions through the workflow and persists the
        resulting run record before verification or local filing state changes.

"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, BeforeValidator, Field, NonNegativeInt, field_validator, model_validator

from ...core.auth_provider import AuthProviderKind
from ...core.errors.hierarchy import SiteHealthState, SiteHealthStatusLike
from ...core.hashing import sha256_hex
from ...core.identifier_grammar import NamespacedId
from ...core.logging import get_logger
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period
from ...core.text_bounds import PositiveCount
from ...domain.deadlines.models import ModeloDeadline, ObligationStatus
from ...domain.submission.models import ModeloDraftStatus
from ..operator_actions.models import ConditionEvidence, PreconditionVerdict
from ._identity import period_identity_segment
from .abort import WorkflowAbortReason
from .engine_helpers import CertificateSeverityValue, DeadlineRole, FilingWindowState

_log = get_logger(__name__)

_WORKFLOW_PROSE_EVIDENCE_KEY_TOKENS = frozenset(
    {
        "description",
        "detail",
        "exception",
        "message",
        "prose",
        "reason",
        "summary",
        "text",
        "traceback",
    },
)
_WORKFLOW_EXCEPTION_TEXT_PATTERN = re.compile(
    r"^[a-z_][a-z0-9_.]*(?:error|exception):",
    flags=re.IGNORECASE,
)
_WORKFLOW_STABLE_FACT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.:-]*$")


class WorkflowStage(StrEnum):
    """The read-only stages of the composite workflow, in strict order."""

    LOADING_PROFILE = "LOADING_PROFILE"
    COMPUTING_DEADLINES = "COMPUTING_DEADLINES"
    CHECKING_INBOX = "CHECKING_INBOX"
    BUILDING_DRAFT = "BUILDING_DRAFT"
    VALIDATING_DRAFT = "VALIDATING_DRAFT"
    RUNNING_PREFLIGHT = "RUNNING_PREFLIGHT"
    DONE = "DONE"
    ABORTED = "ABORTED"


class WorkflowPurpose(StrEnum):
    """Why the workflow engine is being driven.

    The purpose decides whether the filing-window deadline is an abort
    gate or merely informational context:

    * ``FILE`` — the end-to-end filing pipeline (``work file`` and the
      end-to-end ``WorkflowEngine`` run). Filing without a pending
      obligation is refused: the ``COMPUTING_DEADLINES`` stage aborts
      with :attr:`WorkflowAbortReason.NO_PENDING_OBLIGATION` when the
      schedule carries no matching obligation and with
      :attr:`WorkflowAbortReason.DEADLINE_PASSED` when the obligation
      window has already closed.
    * ``VERIFY`` — the ``work verify`` calculation check. Verification
      asserts a calculation is internally sound against the registry's
      verification expectations; it has no honest dependency on the
      AEAT filing calendar. The ``COMPUTING_DEADLINES`` stage records
      the filing-window state as informational context and never
      aborts on it, so a correct calculation can be confirmed early,
      offline, or for a past period.
    """

    FILE = "FILE"
    VERIFY = "VERIFY"


class WorkflowSiteHealthFacts(BaseModel):
    """Locale-neutral persisted projection of one site-health observation.

    Adapter evidence may include a probe URL, source-language marker text, and
    a redacted HTML fragment.  Those transient diagnostics never cross the
    workflow-run persistence boundary.  The projection retains only closed
    state, stable identity, timestamp, numeric status, retry timing, and count
    facts needed by renderers and operators.
    """

    model_config = _STRICT_FROZEN

    alert_code: str = Field(
        pattern=r"^workflow\.site\.[a-z][a-z0-9_]*$",
        min_length=3,
        max_length=96,
    )
    state: SiteHealthState
    observed_at: AwareDatetime
    http_status: int = Field(ge=100, le=599)
    retry_after_seconds: int | None = Field(default=None, ge=1)
    detected_marker_count: NonNegativeInt

    @model_validator(mode="after")
    def _validate_alert_identity(self) -> WorkflowSiteHealthFacts:
        """Bind the persisted alert code to the canonical closed state."""
        expected = f"workflow.site.{self.state.value}"
        if self.alert_code != expected:
            raise ValueError("workflow site-health alert code must match its canonical state")
        return self

    @classmethod
    def from_status(cls, status: SiteHealthStatusLike) -> WorkflowSiteHealthFacts:
        """Project adapter status without URL, marker text, or HTML evidence."""
        return cls(
            alert_code=f"workflow.site.{status.state.value}",
            state=status.state,
            observed_at=status.observed_at,
            http_status=status.evidence.http_status,
            retry_after_seconds=status.retry_after_seconds,
            detected_marker_count=len(status.evidence.detected_markers),
        )


class SiteHealthAlert(BaseModel):
    """Workflow-side alert carrying only stable site-health facts.

    Attached to a :class:`WorkflowStep` when the AEAT browser health-check
    adapter reports a non-nominal site status during a workflow run. ``stage``
    identifies the workflow stage that observed the alert; ``run_id`` ties it
    to the enclosing :class:`WorkflowResult`.
    """

    model_config = _STRICT_FROZEN

    stage: WorkflowStage
    status: WorkflowSiteHealthFacts
    run_id: str = Field(min_length=1, max_length=128)


class WorkflowDeadlineRecoveryFacts(BaseModel):
    """Locale-neutral legal and amount facts for an overdue obligation.

    The domain recovery record also carries an operator command.  Workflow-run
    persistence deliberately excludes that presentation-owned string and keeps
    only registry identities and evaluated recargo facts.
    """

    model_config = _STRICT_FROZEN

    still_filable: bool
    recargo_band_id: str = Field(min_length=1, max_length=64)
    min_completed_months: NonNegativeInt
    max_completed_months: int | None = Field(default=None, ge=0)
    surcharge_pct: Decimal = Field(ge=Decimal("0"))
    interest_applies: bool
    legal_ref: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _validate_stable_facts(self) -> WorkflowDeadlineRecoveryFacts:
        """Reject prose-shaped identifiers and an inverted month range."""
        if _WORKFLOW_STABLE_FACT_ID_PATTERN.fullmatch(self.recargo_band_id) is None:
            raise ValueError("recargo band id must be a stable locale-neutral identity")
        if _WORKFLOW_STABLE_FACT_ID_PATTERN.fullmatch(self.legal_ref) is None:
            raise ValueError("recargo legal reference must be a stable locale-neutral identity")
        if self.max_completed_months is not None and self.max_completed_months < self.min_completed_months:
            raise ValueError("recargo maximum completed months cannot precede the minimum")
        return self


class WorkflowObligationFacts(BaseModel):
    """Strict persisted projection of one domain filing obligation.

    ``ModeloDeadline`` contains source-language applicability prose and a raw
    recovery command.  Neither belongs in a durable workflow record.  This
    projection retains the canonical address, dates, status, legal identities,
    and typed overdue facts needed by resume and rendering consumers.
    """

    model_config = _STRICT_FROZEN

    modelo: Modelo
    period: Period
    opens_on: date
    closes_on: date
    payment_cutoff_on: date | None = None
    status: ObligationStatus
    boe_references: tuple[str, ...] = ()
    recovery: WorkflowDeadlineRecoveryFacts | None = None

    @field_validator("boe_references")
    @classmethod
    def _legal_references_are_stable(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Keep only unique registry identities, never rendered citations."""
        if len(set(value)) != len(value):
            raise ValueError("workflow obligation legal references must be unique")
        if any(_WORKFLOW_STABLE_FACT_ID_PATTERN.fullmatch(item) is None for item in value):
            raise ValueError("workflow obligation legal references must be stable locale-neutral identities")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def _validate_window(self) -> WorkflowObligationFacts:
        """Retain the domain window and overdue-recovery coherence."""
        if self.opens_on > self.closes_on:
            raise ValueError("workflow obligation opens_on cannot follow closes_on")
        if self.payment_cutoff_on is not None and self.payment_cutoff_on > self.closes_on:
            raise ValueError("workflow obligation payment cutoff cannot follow closes_on")
        if self.recovery is not None and self.status is not ObligationStatus.OVERDUE:
            raise ValueError("workflow obligation recovery facts require overdue status")
        return self

    @classmethod
    def from_deadline(cls, obligation: ModeloDeadline) -> WorkflowObligationFacts:
        """Project one domain deadline without its prose or raw command fields."""
        recovery = obligation.recovery
        recovery_facts = None
        if recovery is not None:
            band = recovery.recargo_band
            recovery_facts = WorkflowDeadlineRecoveryFacts(
                still_filable=recovery.still_filable,
                recargo_band_id=band.id,
                min_completed_months=band.min_completed_months,
                max_completed_months=band.max_completed_months,
                surcharge_pct=band.surcharge_pct,
                interest_applies=band.interest_applies,
                legal_ref=band.legal_ref,
            )
        return cls(
            modelo=obligation.modelo,
            period=obligation.period,
            opens_on=obligation.opens_on,
            closes_on=obligation.closes_on,
            payment_cutoff_on=obligation.payment_cutoff_on,
            status=obligation.status,
            boe_references=obligation.boe_references,
            recovery=recovery_facts,
        )


class WorkflowDiagnosticSkipReason(StrEnum):
    """Closed reasons a non-applicable workflow diagnostic was skipped."""

    NOT_WIRED = "not_wired"


class _WorkflowStepDetail(BaseModel):
    """Frozen base for one closed, locale-neutral workflow detail shape."""

    model_config = _STRICT_FROZEN


class WorkflowDeadlineContextDetails(_WorkflowStepDetail):
    """The one of the closed deadline contexts a workflow step can carry."""

    kind: Literal["deadline_context"]
    modelo: Modelo
    period: Period
    opens_on: date | None = None
    closes_on: date | None = None
    filing_window: FilingWindowState | None = None
    deadline_role: DeadlineRole | None = None
    overdue: bool | None = None
    extemporanea: bool | None = None

    @model_validator(mode="after")
    def _validate_context(self) -> WorkflowDeadlineContextDetails:
        """Keep deadline metadata internally coherent rather than loosely optional.

        A context carries exactly one of three mutually exclusive shapes — an
        overdue observation, a binding filing window, or an informational one —
        each with its own coherence rule below.
        """
        if self.overdue is not None or self.extemporanea is not None:
            self._validate_overdue_shape()
            return self

        if (self.filing_window is None) != (self.deadline_role is None):
            raise ValueError("deadline_role and filing_window must be declared together")
        if self.deadline_role is None:
            if self.opens_on is None and self.closes_on is None:
                raise ValueError("deadline context requires at least one boundary date")
            return self

        if self.deadline_role is DeadlineRole.BINDING:
            self._validate_binding_shape()
            return self

        self._validate_informational_shape()
        return self

    def _both_boundary_dates_declared(self) -> bool:
        """Return whether the context carries both filing-window boundary dates."""
        return self.opens_on is not None and self.closes_on is not None

    def _validate_overdue_shape(self) -> None:
        """Require an overdue observation to carry only its closing date."""
        if self.overdue is not True or self.extemporanea is not True:
            raise ValueError("overdue deadline context requires overdue and extemporanea to be true")
        if self.closes_on is None or self.opens_on is not None:
            raise ValueError("overdue deadline context requires only closes_on")
        if self.filing_window is not None or self.deadline_role is not None:
            raise ValueError("overdue deadline context cannot carry filing-window metadata")

    def _validate_binding_shape(self) -> None:
        """Require a binding role to name a future window bounded on both sides."""
        if self.filing_window is not FilingWindowState.FUTURE:
            raise ValueError("binding deadline context requires a future filing window")
        if not self._both_boundary_dates_declared():
            raise ValueError("binding deadline context requires opens_on and closes_on")

    def _validate_informational_shape(self) -> None:
        """Require an informational window to be either absent or fully dated."""
        if self.filing_window is FilingWindowState.ABSENT:
            if self.opens_on is not None or self.closes_on is not None:
                raise ValueError("absent informational windows cannot carry boundary dates")
            return
        if not self._both_boundary_dates_declared():
            raise ValueError("dated informational windows require opens_on and closes_on")


class WorkflowInboxSkippedDetails(_WorkflowStepDetail):
    """An inbox step intentionally skipped because its adapter is not wired."""

    kind: Literal["inbox_skipped"]
    skip_reason: Literal[WorkflowDiagnosticSkipReason.NOT_WIRED]


class WorkflowInboxBlockedDetails(_WorkflowStepDetail):
    """A workflow inbox failure with a bounded, machine-readable first item."""

    kind: Literal["inbox_blocked"]
    blocker_count: PositiveCount
    first_notificacion_id: str = Field(min_length=1, max_length=256)


class WorkflowDraftBuiltDetails(_WorkflowStepDetail):
    """The durable identity of a successfully built draft."""

    kind: Literal["draft_built"]
    draft_id: str = Field(min_length=1, max_length=256)


class WorkflowAlreadyFiledDetails(_WorkflowStepDetail):
    """The model and period already evidenced as filed."""

    kind: Literal["already_filed"]
    modelo: Modelo
    period: Period
    expediente_count: PositiveCount


class WorkflowDraftNotReadyDetails(_WorkflowStepDetail):
    """A built draft whose lifecycle status does not permit filing."""

    kind: Literal["draft_not_ready"]
    draft_id: str = Field(min_length=1, max_length=256)
    draft_status: ModeloDraftStatus
    blocking_finding_codes: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("blocking_finding_codes")
    @classmethod
    def _finding_codes_are_stable(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require deterministic non-prose finding identities."""
        if len(set(value)) != len(value):
            raise ValueError("blocking finding codes must be unique")
        if any(not code or code != code.strip() or any(character.isspace() for character in code) for code in value):
            raise ValueError("blocking finding codes must be stable non-prose identities")
        return tuple(sorted(value))


class WorkflowDraftMismatchDetails(_WorkflowStepDetail):
    """A draft that cannot be used for the target obligation.

    The mismatching facts themselves are condition evidence on the paired
    :class:`PreconditionVerdict`, not a second free-form detail map.
    """

    kind: Literal["draft_mismatch"]
    draft_id: str = Field(min_length=1, max_length=256)


class WorkflowValidationFailedDetails(_WorkflowStepDetail):
    """The number of blocking validation findings on one draft."""

    kind: Literal["validation_failed"]
    error_count: PositiveCount


class WorkflowAuthCheckDetails(_WorkflowStepDetail):
    """Closed certificate/provider readiness facts for preflight."""

    kind: Literal["auth_check"]
    provider_kind: AuthProviderKind | None = None
    provider_check_skipped: bool = False
    skip_reason: Literal[WorkflowDiagnosticSkipReason.NOT_WIRED] | None = None
    cert_not_after: date | None = None
    cert_severity: CertificateSeverityValue | None = None
    cert_days_until_expiry: int | None = None

    @model_validator(mode="after")
    def _validate_provider_shape(self) -> WorkflowAuthCheckDetails:
        """Make configured and skipped provider observations disjoint shapes."""
        if self.provider_check_skipped:
            self._validate_skipped_shape()
            return self

        if self.provider_kind is None or self.skip_reason is not None:
            raise ValueError("configured provider checks require provider_kind and no skip reason")
        certificate_values = (self.cert_not_after, self.cert_severity, self.cert_days_until_expiry)
        declared = tuple(value for value in certificate_values if value is not None)
        if declared and len(declared) != len(certificate_values):
            raise ValueError("certificate expiry facts must be provided together")
        return self

    def _validate_skipped_shape(self) -> None:
        """Require a skipped provider check to carry no provider or certificate facts."""
        if self.skip_reason is not WorkflowDiagnosticSkipReason.NOT_WIRED:
            raise ValueError("skipped provider checks require the not_wired reason")
        if any(
            value is not None
            for value in (
                self.provider_kind,
                self.cert_not_after,
                self.cert_severity,
                self.cert_days_until_expiry,
            )
        ):
            raise ValueError("skipped provider checks cannot carry certificate facts")


class WorkflowPreflightFailedDetails(_WorkflowStepDetail):
    """A preflight failure identified by a stable application error code."""

    kind: Literal["preflight_failed"]
    error_code: NamespacedId
    auth_check: WorkflowAuthCheckDetails | None = None


class WorkflowFailureDetails(_WorkflowStepDetail):
    """A non-precondition workflow failure represented without exception prose."""

    kind: Literal["workflow_failure"]
    error_code: NamespacedId


type WorkflowStepDetails = Annotated[
    WorkflowDeadlineContextDetails
    | WorkflowInboxSkippedDetails
    | WorkflowInboxBlockedDetails
    | WorkflowDraftBuiltDetails
    | WorkflowAlreadyFiledDetails
    | WorkflowDraftNotReadyDetails
    | WorkflowDraftMismatchDetails
    | WorkflowValidationFailedDetails
    | WorkflowAuthCheckDetails
    | WorkflowPreflightFailedDetails
    | WorkflowFailureDetails,
    Field(discriminator="kind"),
]

_PRECONDITION_DETAIL_TYPES = (
    WorkflowInboxBlockedDetails,
    WorkflowAlreadyFiledDetails,
    WorkflowDraftNotReadyDetails,
    WorkflowDraftMismatchDetails,
    WorkflowValidationFailedDetails,
)


WORKFLOW_SUMMARY_LOCALE_KEYS: tuple[str, ...] = (
    "application.workflow.results.aborted",
    "application.workflow.results.completed",
    "application.workflow.steps.already_filed",
    "application.workflow.steps.auth_certificate_invalid",
    "application.workflow.steps.auth_certificate_load_failed",
    "application.workflow.steps.auth_provider_unavailable",
    "application.workflow.steps.deadline_absent",
    "application.workflow.steps.deadline_closed",
    "application.workflow.steps.deadline_future",
    "application.workflow.steps.deadline_informational",
    "application.workflow.steps.deadline_missing",
    "application.workflow.steps.deadline_open",
    "application.workflow.steps.deadline_overdue",
    "application.workflow.steps.draft_build_failed",
    "application.workflow.steps.draft_built",
    "application.workflow.steps.draft_identity_mismatch",
    "application.workflow.steps.draft_not_ready",
    "application.workflow.steps.inbox_blocked",
    "application.workflow.steps.inbox_clear",
    "application.workflow.steps.inbox_skipped",
    "application.workflow.steps.preflight_completed",
    "application.workflow.steps.preflight_failed",
    "application.workflow.steps.profile_loaded",
    "application.workflow.steps.site_unavailable",
    "application.workflow.steps.validation_clean",
    "application.workflow.steps.validation_failed",
    "application.workflow.steps.workflow_failure",
)
"""Every persisted workflow summary locale identity emitted by engine producers.

The ``_LOCALE_KEYS`` suffix makes this closed producer set visible to the
static locale scanner even though a persisted result selects one key at
runtime. Keep it synchronized with the workflow engine, deadline stage, and
recording failure producers.
"""


def _parse_workflow_locale_key(value: object) -> str:
    """Return one stable abstract locale identity, never rendered prose."""
    if not isinstance(value, str):
        raise ValueError("workflow summary locale key must be a string")
    if not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", value):
        raise ValueError("workflow summary must carry a stable dotted locale key")
    if value not in WORKFLOW_SUMMARY_LOCALE_KEYS:
        raise ValueError("workflow summary locale key must be one of the closed workflow producer keys")
    return value


type WorkflowLocaleKey = Annotated[str, BeforeValidator(_parse_workflow_locale_key)]


def _evidence_carries_prose(evidence: ConditionEvidence) -> bool:
    """Return whether one evidence record holds rendered or exception prose.

    Workflow refusal evidence is a locale-neutral fact map. A prose-shaped key
    token, a value carrying whitespace, or a value shaped like a rendered
    ``SomeError: ...`` line all mark presentation text that must not reach a
    durable record.
    """
    key_tokens = {token for key in evidence.values for token in re.split(r"[._]", key)}
    if key_tokens & _WORKFLOW_PROSE_EVIDENCE_KEY_TOKENS:
        return True
    string_values = tuple(value for value in evidence.values.values() if isinstance(value, str))
    return any(
        any(character.isspace() for character in value) or _WORKFLOW_EXCEPTION_TEXT_PATTERN.match(value) is not None
        for value in string_values
    )


def _reject_prose_precondition_evidence(verdict: PreconditionVerdict) -> None:
    """Refuse a verdict whose evidence would persist rendered or exception prose."""
    for evidence in verdict.evidence:
        if _evidence_carries_prose(evidence):
            raise ValueError("workflow precondition evidence cannot persist rendered or exception prose")


class WorkflowStep(BaseModel):
    """A single step in a :class:`WorkflowResult`."""

    model_config = _STRICT_FROZEN

    stage: WorkflowStage
    started_at: datetime
    ended_at: datetime | None = None
    success: bool | None = None
    summary_locale_key: WorkflowLocaleKey
    details: WorkflowStepDetails | None = None
    precondition_verdict: PreconditionVerdict | None = None
    site_health_alert: SiteHealthAlert | None = None

    @model_validator(mode="after")
    def _check_timestamps(self) -> WorkflowStep:
        if self.ended_at is not None:
            if self.ended_at < self.started_at:
                raise ValueError(f"ended_at ({self.ended_at}) precedes started_at ({self.started_at})")
            if self.success is None:
                raise ValueError("completed steps must set success explicitly")
        if self.precondition_verdict is not None and self.success is not False:
            raise ValueError("precondition verdicts belong only to explicitly failed workflow steps")
        if isinstance(self.details, _PRECONDITION_DETAIL_TYPES) and self.precondition_verdict is None:
            raise ValueError("refusal detail records require a typed precondition verdict")
        if self.precondition_verdict is not None:
            _reject_prose_precondition_evidence(self.precondition_verdict)
        return self


class WorkflowResult(BaseModel):
    """The full result of one :meth:`WorkflowEngine.run_next` invocation."""

    model_config = _STRICT_FROZEN

    run_id: str = Field(min_length=16, max_length=16)
    started_at: datetime
    ended_at: datetime
    final_stage: WorkflowStage
    aborted_reason: WorkflowAbortReason | None = None
    obligation: WorkflowObligationFacts | None = None
    draft_id: str | None = None
    submission_id: str | None = None
    steps: tuple[WorkflowStep, ...]
    summary_locale_key: WorkflowLocaleKey
    summary_details: WorkflowStepDetails | None = None
    resumed_from: str | None = None

    @model_validator(mode="after")
    def _check_terminal_consistency(self) -> WorkflowResult:
        if self.ended_at < self.started_at:
            raise ValueError("ended_at precedes started_at")
        if self.final_stage not in {WorkflowStage.DONE, WorkflowStage.ABORTED}:
            raise ValueError(f"final_stage must be DONE or ABORTED; got {self.final_stage.value}")
        if self.final_stage is WorkflowStage.DONE:
            if self.aborted_reason is not None:
                raise ValueError("DONE results must not carry an aborted_reason")
            return self
        if self.aborted_reason is None:
            raise ValueError("ABORTED results must carry an aborted_reason")
        if not self.steps or self.steps[-1].success is not False:
            raise ValueError("ABORTED results must end with an explicitly failed workflow step")
        if self.steps[-1].precondition_verdict is None:
            raise ValueError("ABORTED results must end with a typed precondition verdict")
        return self


def compute_run_id(
    *,
    tax_id: str,
    modelo: str,
    period: Period | None,
    started_at: datetime,
) -> str:
    """Return a stable 16-char hex hash for a workflow run."""
    period_segment = period_identity_segment(period) if period is not None else "-"
    payload = "|".join([tax_id, modelo, period_segment, started_at.isoformat()])
    return sha256_hex(payload.encode("utf-8"))[:16]


__all__ = [
    "WORKFLOW_SUMMARY_LOCALE_KEYS",
    "SiteHealthAlert",
    "WorkflowAlreadyFiledDetails",
    "WorkflowAuthCheckDetails",
    "WorkflowDeadlineContextDetails",
    "WorkflowDeadlineRecoveryFacts",
    "WorkflowDiagnosticSkipReason",
    "WorkflowDraftBuiltDetails",
    "WorkflowDraftMismatchDetails",
    "WorkflowDraftNotReadyDetails",
    "WorkflowFailureDetails",
    "WorkflowInboxBlockedDetails",
    "WorkflowInboxSkippedDetails",
    "WorkflowLocaleKey",
    "WorkflowObligationFacts",
    "WorkflowPreflightFailedDetails",
    "WorkflowPurpose",
    "WorkflowResult",
    "WorkflowSiteHealthFacts",
    "WorkflowStage",
    "WorkflowStep",
    "WorkflowStepDetails",
    "WorkflowValidationFailedDetails",
    "compute_run_id",
]
