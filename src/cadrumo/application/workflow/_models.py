"""Strict pydantic v2 records for the composite workflow engine.

Every boundary-crossing type in :mod:`cadrumo.application.workflow` is
defined here as a frozen, strict, ``extra="forbid"``
:class:`pydantic.BaseModel` or as an :class:`enum.StrEnum` for closed
enumerations. Persisted workflow presentation carries abstract locale keys,
never rendered prose. :attr:`WorkflowStep.details` is a closed record of
locale-neutral facts, while :attr:`WorkflowStep.precondition_verdict` carries
the canonical application-owned refusal outcome. Some helpers accept an
optional :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository` so
callers can supply a custom storage backend without going through the runtime
default. The
:class:`WorkflowState` record carries a reference to the active-bucket
:class:`TransactionCatalogueRepository` when one is needed downstream.

This module uses :class:`WorkflowResult`, :class:`WorkflowEngine`,
and :class:`UserProfileRecord` for workflow persistence and state management.
:class:`WorkflowEvent` and the review-annotation field types embedded on
:class:`WorkflowState` (``InvoiceReviewRecord``, ``LedgerReviewRecord``) are
defined in the shared leaf module
:mod:`cadrumo.application._workflow_review_models` rather than here or in
:mod:`cadrumo.application.review`, because :mod:`cadrumo.application.review` embeds
:class:`WorkflowEvent` as a field type in turn — a genuine mutual runtime
dependency that a shared leaf module resolves without either package
importing the other.

Workflow-owned auth field types are similarly defined in
:mod:`cadrumo.application._workflow_auth_models` and exported publicly by
:mod:`cadrumo.application.workflow`. Auth services consume that shared leaf;
they do not own or re-export the persisted records.

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
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator

from ...core import (
    STRICT_FROZEN_CONFIG as _STRICT_FROZEN,
)
from ...core import (
    AuthProviderKind,
    Modelo,
    Period,
)
from ...core import (
    require_active_bucket_id as _require_active_bucket_id,
)
from ...core import (
    resolve_active_bucket_id as _resolve_active_bucket_id,
)
from ...core.config import override_settings
from ...core.hashing import sha256_hex
from ...core.i18n import Translatable
from ...core.logging import get_logger
from ...core.time import now as utc_now
from ...domain.submission import ModeloDraftStatus
from .._workflow_auth_models import AuthState
from .._workflow_review_models import (
    InvoiceReviewRecord,
    LedgerReviewRecord,
    WorkflowEvent,
)
from ..operator_actions import PreconditionVerdict
from ._engine_helpers import CertificateSeverityValue, DeadlineRole, FilingWindowState
from ._profile_bucket_models import ProfileBucketPointer as ProfileBucketPointer
from ._profile_bucket_scan import resolve_profile_bucket
from ._workflow_abort import WorkflowAbortReason as WorkflowAbortReason

if TYPE_CHECKING:
    from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ...adapters.persistence.storage import SecureObjectRepository
    from ...domain.user_profile import ProfileSchemaDefinition, UserProfileRecord

_log = get_logger(__name__)


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


def _parse_declaration_modelo(value: object) -> Modelo:
    """Resolve a persisted declaration pointer through the canonical Modelo enum."""
    if isinstance(value, Modelo):
        return value
    if isinstance(value, str):
        try:
            return Modelo(value)
        except ValueError as exc:
            raise ValueError(f"declaration pointer modelo {value!r} is not a canonical AEAT modelo") from exc
    raise ValueError(f"declaration pointer modelo must be a Modelo or str, got {type(value).__name__}")


def _parse_declaration_status(value: object) -> ModeloDraftStatus:
    """Resolve a persisted declaration pointer through the closed draft-status enum."""
    if isinstance(value, ModeloDraftStatus):
        return value
    if isinstance(value, str):
        try:
            return ModeloDraftStatus(value)
        except ValueError as exc:
            raise ValueError(f"declaration pointer status {value!r} is not a ModeloDraftStatus") from exc
    raise ValueError(f"declaration pointer status must be a ModeloDraftStatus or str, got {type(value).__name__}")


class DeclaracionPointer(BaseModel):
    """Lightweight pointer to a persisted filing draft stored in :class:`WorkflowState`.

    Keyed in :attr:`WorkflowState.declarations` by the value returned from
    :func:`declaration_key`. ``draft_id`` and ``status`` are written by the
    workflow engine after each filing stage; ``exported_path`` records the
    on-disk fichero-BOE path when the draft was exported; ``verified`` records
    the last verification verdict for the ``work verify`` command.
    """

    model_config = _STRICT_FROZEN

    modelo: Annotated[Modelo, BeforeValidator(_parse_declaration_modelo)]
    period: Period
    draft_id: str | None = None
    status: Annotated[ModeloDraftStatus, BeforeValidator(_parse_declaration_status)] | None = None
    exported_path: str | None = None
    verified: bool | None = None
    updated_at: datetime = Field(default_factory=utc_now)


def _period_identity_segment(period: Period) -> str:
    """Return the stable non-combined identity segment for ``period``."""
    # Deliberate runtime guard: annotations are not enforced at call time, and this
    # segment lands in a persisted identity, so a wrong type here would be discovered
    # as a corrupt key rather than a refusal. The check is redundant to the checker
    # and load-bearing at runtime.
    if not isinstance(period, Period):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"period must be a cadrumo.core.Period instance, got {type(period).__name__}")
    return f"{period.filing_year}:{period.registry_token}"


def declaration_key(modelo: str, period: Period) -> str:
    """Return the canonical state-store key for a ``(modelo, period)`` pair.

    The period segment is stored as ``filing_year:registry_token`` so
    declaration state never keys by a combined token such as ``2025Q1``.
    """
    return f"{modelo.strip()}:{_period_identity_segment(period)}"


class WorkflowState(BaseModel):
    """Encrypted operator state for the Cadrumo ``aeat`` CLI.

    The entire state is persisted as a single encrypted envelope via
    :class:`WorkflowStateRepository`. Mutations always return a new
    copy (:meth:`model_copy`) to preserve the frozen-model invariant.

    Attributes:
        auth: Local AEAT access readiness state.
        declarations: Filing draft pointers keyed by :func:`declaration_key`.
        invoice_reviews: Invoice review annotations keyed by ``invoice_id``.
        ledger_reviews: Ledger transaction review annotations keyed by
            ``transaction_id``.
        updated_at: UTC timestamp of the last write.

    The historical ``profiles`` field has retired. Consumers that
    need to enumerate registered profiles call
    :func:`cadrumo.application.workflow._profile_bucket_scan.list_profile_buckets`
    or :func:`read_profile_bucket` directly; both scan
    ``<cadrumo_local_storage_root>/buckets/*/manifest.toml`` and never
    open an encrypted database. The active profile resolves via the
    precedence chain (Settings override > plaintext pointer file).
    """

    model_config = _STRICT_FROZEN

    auth: AuthState = Field(default_factory=AuthState)
    declarations: dict[str, DeclaracionPointer] = Field(default_factory=dict)
    invoice_reviews: dict[str, InvoiceReviewRecord] = Field(default_factory=dict)
    ledger_reviews: dict[str, LedgerReviewRecord] = Field(default_factory=dict)
    bucket_events: tuple[WorkflowEvent, ...] = ()
    updated_at: datetime = Field(default_factory=utc_now)

    def active_profile_record(
        self,
        *,
        secure_objects: SecureObjectRepository | None = None,
        schema: ProfileSchemaDefinition | None = None,
    ) -> UserProfileRecord | None:
        """Return the active :class:`UserProfileRecord` from its secure bucket.

        The active selector resolves via the precedence chain in
        :func:`cadrumo.core.resolve_active_bucket_id` (env var > pointer file
        fallback), then the manifest resolver canonicalizes a display label to
        its immutable bucket UUID before secure storage is addressed.

        ``secure_objects`` (a :class:`SecureObjectRepository` override) and
        ``schema`` are optional overrides forwarded to
        :func:`~cadrumo.application.user_profile.build_lifecycle_service`; a
        per-bucket store and the bundled schema are resolved when ``None``.
        """
        identifier, bucket_id = self._active_profile_selection()
        if bucket_id is None:
            if identifier is not None:
                _log.debug(
                    "active profile record resolution returned no profile record: selected profile has no live bucket",
                )
            return None
        from ...domain.user_profile import ProfileNotFoundError
        from ..user_profile import build_lifecycle_service

        with override_settings(cadrumo_active_profile=bucket_id):
            service = build_lifecycle_service(bucket_id=bucket_id, secure_objects=secure_objects, schema=schema)
            try:
                return service.read(bucket_id)
            except ProfileNotFoundError as exc:
                _log.debug("active profile record resolution returned no profile record: %s", type(exc).__name__)
                return None

    def active_profile_bucket_id(self) -> str | None:
        """Return the selected profile's canonical secure bucket UUID.

        Core owns active-selector precedence. The workflow manifest resolver
        then maps an operator-facing label to the existing immutable bucket
        UUID. A selector without a live manifest has no secure bucket and
        returns ``None``; health diagnostics retain the raw selector separately.
        """
        return self._active_profile_selection()[1]

    @staticmethod
    def _active_profile_selection() -> tuple[str | None, str | None]:
        """Return the raw active selector and its canonical live bucket UUID."""
        identifier = _resolve_active_bucket_id()
        if identifier is None:
            return None, None
        pointer = resolve_profile_bucket(identifier)
        return identifier, pointer.bucket_id if pointer is not None else None


def active_transaction_catalogue_repository(
    state: WorkflowState,
    *,
    objects: SecureObjectRepository | None = None,
) -> TransactionCatalogueRepository:
    """Return the :class:`TransactionCatalogueRepository` for the active profile bucket.

    Args:
        state: The current workflow state used to resolve the active bucket.
        objects: Optional
            :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
            override passed through to the returned repository.
    """
    from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ...core.errors import NoActiveProfileError
    from ...domain.transactions import LedgerNoActiveBucketError

    try:
        bucket_id = _require_active_bucket_id()
    except NoActiveProfileError as exc:
        raise LedgerNoActiveBucketError(
            translated_message="application.workflow.errors.no_active_profile_bucket",
            context={"repository": "transaction_catalogue", "operation": "resolve_active_bucket"},
            suggestion="aeat config profile create NAME",
        ) from exc
    return TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects)


def update_declaration_pointer(
    state: WorkflowState,
    *,
    modelo: str,
    period: Period,
    draft_id: str | None = None,
    status: str | None = None,
    exported_path: str | None = None,
    verified: bool | None = None,
) -> WorkflowState:
    """Return ``state`` with the declaration pointer upserted for ``(modelo, period)``.

    ``draft_id`` and ``status`` are optional: when omitted (``None``) on an update
    they leave the existing pointer's value untouched rather than clobbering it,
    so a partial update (e.g. recording only an ``exported_path``) is safe.

    Returns the updated :class:`WorkflowState` with the pointer recorded.
    """
    import json as _json

    declarations: dict[str, DeclaracionPointer] = dict(state.declarations)
    key = declaration_key(modelo, period)
    current = declarations.get(key)
    if isinstance(current, dict):
        current = DeclaracionPointer.model_validate_json(_json.dumps(current, default=str))

    now = utc_now()
    update_fields: dict[str, object] = {"updated_at": now}
    if draft_id is not None:
        update_fields["draft_id"] = draft_id
    if status is not None:
        update_fields["status"] = status
    if exported_path is not None:
        update_fields["exported_path"] = exported_path
    if verified is not None:
        update_fields["verified"] = verified

    if isinstance(current, DeclaracionPointer):
        declarations[key] = current.model_copy(update=update_fields)
    else:
        declarations[key] = DeclaracionPointer(
            modelo=_parse_declaration_modelo(modelo),
            period=period,
            draft_id=draft_id,
            status=_parse_declaration_status(status) if status is not None else None,
            exported_path=exported_path,
            verified=verified,
            updated_at=now,
        )
    return state.model_copy(update={"declarations": declarations, "updated_at": utc_now()})


# ---------------------------------------------------------------------------
# Heavy adapter/domain imports — placed AFTER the state models above so that
# auth._actions (which imports WorkflowState from this partially-loaded
# module during the browser-adapter initialisation chain) finds the names
# already present in sys.modules['cadrumo.application.workflow._models'].
# ---------------------------------------------------------------------------

from ...adapters.outbound.aeat.browser import SiteHealthStatus
from ...domain.deadlines import ModeloDeadline


class SiteHealthAlert(BaseModel):
    """Workflow-side alert wrapping a ``SiteHealthStatus`` observation.

    Attached to a :class:`WorkflowStep` when the AEAT browser health-check
    adapter reports a non-nominal site status during a workflow run. ``stage``
    identifies the workflow stage that observed the alert; ``run_id`` ties it
    to the enclosing :class:`WorkflowResult`.
    """

    model_config = _STRICT_FROZEN

    stage: WorkflowStage
    status: SiteHealthStatus
    run_id: str = Field(min_length=1, max_length=128)


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
        """Keep deadline metadata internally coherent rather than loosely optional."""
        if self.overdue is not None or self.extemporanea is not None:
            if self.overdue is not True or self.extemporanea is not True:
                raise ValueError("overdue deadline context requires overdue and extemporanea to be true")
            if self.closes_on is None or self.opens_on is not None:
                raise ValueError("overdue deadline context requires only closes_on")
            if self.filing_window is not None or self.deadline_role is not None:
                raise ValueError("overdue deadline context cannot carry filing-window metadata")
            return self

        if (self.filing_window is None) != (self.deadline_role is None):
            raise ValueError("deadline_role and filing_window must be declared together")
        if self.deadline_role is None:
            if self.opens_on is None and self.closes_on is None:
                raise ValueError("deadline context requires at least one boundary date")
            return self

        if self.deadline_role is DeadlineRole.BINDING:
            if self.filing_window is not FilingWindowState.FUTURE:
                raise ValueError("binding deadline context requires a future filing window")
            if self.opens_on is None or self.closes_on is None:
                raise ValueError("binding deadline context requires opens_on and closes_on")
            return self

        if self.filing_window is FilingWindowState.ABSENT:
            if self.opens_on is not None or self.closes_on is not None:
                raise ValueError("absent informational windows cannot carry boundary dates")
            return self
        if self.opens_on is None or self.closes_on is None:
            raise ValueError("dated informational windows require opens_on and closes_on")
        return self


class WorkflowInboxSkippedDetails(_WorkflowStepDetail):
    """An inbox step intentionally skipped because its adapter is not wired."""

    kind: Literal["inbox_skipped"]
    skip_reason: Literal[WorkflowDiagnosticSkipReason.NOT_WIRED]


class WorkflowInboxBlockedDetails(_WorkflowStepDetail):
    """A workflow inbox failure with a bounded, machine-readable first item."""

    kind: Literal["inbox_blocked"]
    blocker_count: int = Field(ge=1)
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
    expediente_count: int = Field(ge=1)


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
    error_count: int = Field(ge=1)


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
            return self

        if self.provider_kind is None or self.skip_reason is not None:
            raise ValueError("configured provider checks require provider_kind and no skip reason")
        certificate_values = (self.cert_not_after, self.cert_severity, self.cert_days_until_expiry)
        if any(value is not None for value in certificate_values) and any(
            value is None for value in certificate_values
        ):
            raise ValueError("certificate expiry facts must be provided together")
        return self


class WorkflowPreflightFailedDetails(_WorkflowStepDetail):
    """A preflight failure identified by a stable application error code."""

    kind: Literal["preflight_failed"]
    error_code: str = Field(
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
        min_length=3,
        max_length=160,
    )
    auth_check: WorkflowAuthCheckDetails | None = None


class WorkflowFailureDetails(_WorkflowStepDetail):
    """A non-precondition workflow failure represented without exception prose."""

    kind: Literal["workflow_failure"]
    error_code: str = Field(
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
        min_length=3,
        max_length=160,
    )


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


def _parse_workflow_locale_key(value: object) -> Translatable:
    """Return one stable abstract locale identity, never rendered prose."""
    if not isinstance(value, str):
        raise ValueError("workflow summary locale key must be a string")
    if not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", value):
        raise ValueError("workflow summary must carry a stable dotted locale key")
    return Translatable(value)


WorkflowLocaleKey = Annotated[Translatable, BeforeValidator(_parse_workflow_locale_key)]


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
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError(f"ended_at ({self.ended_at}) precedes started_at ({self.started_at})")
        if self.ended_at is not None and self.success is None:
            raise ValueError("completed steps must set success explicitly")
        if self.precondition_verdict is not None and self.success is not False:
            raise ValueError("precondition verdicts belong only to explicitly failed workflow steps")
        if isinstance(self.details, _PRECONDITION_DETAIL_TYPES) and self.precondition_verdict is None:
            raise ValueError("refusal detail records require a typed precondition verdict")
        if self.precondition_verdict is not None:
            for evidence in self.precondition_verdict.evidence:
                if any(
                    isinstance(value, str) and any(character.isspace() for character in value)
                    for value in evidence.values.values()
                ):
                    raise ValueError("workflow precondition evidence cannot persist rendered or exception prose")
        return self


class WorkflowResult(BaseModel):
    """The full result of one :meth:`WorkflowEngine.run_next` invocation."""

    model_config = _STRICT_FROZEN

    run_id: str = Field(min_length=16, max_length=16)
    started_at: datetime
    ended_at: datetime
    final_stage: WorkflowStage
    aborted_reason: WorkflowAbortReason | None = None
    obligation: ModeloDeadline | None = None
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
        if self.final_stage is WorkflowStage.ABORTED and self.aborted_reason is None:
            raise ValueError("ABORTED results must carry an aborted_reason")
        if self.final_stage is WorkflowStage.DONE and self.aborted_reason is not None:
            raise ValueError("DONE results must not carry an aborted_reason")
        if self.final_stage is WorkflowStage.ABORTED and (not self.steps or self.steps[-1].success is not False):
            raise ValueError("ABORTED results must end with an explicitly failed workflow step")
        return self


def compute_run_id(
    *,
    tax_id: str,
    modelo: str,
    period: Period | None,
    started_at: datetime,
) -> str:
    """Return a stable 16-char hex hash for a workflow run."""
    period_segment = _period_identity_segment(period) if period is not None else "-"
    payload = "|".join([tax_id, modelo, period_segment, started_at.isoformat()])
    return sha256_hex(payload.encode("utf-8"))[:16]
