"""Strict pydantic v2 records for the composite workflow engine.

Every boundary-crossing type in :mod:`cadrumo.application.workflow` is
defined here as a frozen, strict, ``extra="forbid"``
:class:`pydantic.BaseModel` or as an :class:`enum.StrEnum` for closed
enumerations. :attr:`WorkflowStep.details` is reserved for string-valued
diagnostics emitted by workflow diagnostics. Some helpers accept an
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

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from ...core import (
    STRICT_FROZEN_CONFIG as _STRICT_FROZEN,
)
from ...core import (
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
from ...core.logging import get_logger
from ...domain.submission import ModeloDraftStatus
from .._workflow_auth_models import AuthState
from .._workflow_review_models import (
    InvoiceReviewRecord,
    LedgerReviewRecord,
    WorkflowEvent,
)
from ._profile_bucket_models import ProfileBucketPointer as ProfileBucketPointer
from ._profile_bucket_scan import resolve_profile_bucket
from ._utils import utc_now
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
    if not isinstance(period, Period):
        raise TypeError(f"period must be cadrumo.core.Period, got {type(period).__name__}")
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
            modelo=modelo,
            period=period,
            draft_id=draft_id,
            status=status,
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


class WorkflowStepDetails(BaseModel):
    """Operator-visible details attached to a workflow step.

    Carries arbitrary string-keyed diagnostic values emitted by the
    workflow engine. The model is intentionally permissive
    (``extra='allow'``) so existing call sites can continue to pass
    free-form dicts; the boundary is now a typed pydantic record
    instead of an opaque ``dict[str, str]``, so a future PR can
    promote specific step kinds into a discriminated union without
    breaking the field type on :class:`WorkflowStep`.

    Per-stage key catalogue (the documented contract external tools
    consuming ``WorkflowResult.steps`` may rely on):

    * Deadline checks: ``{"modelo", "period", "closes_on"}``.
    * Draft / snapshot mismatch: ``{"draft_id", "modelo", "period",
      "profile_tax_id", "schema_version"}``.
    * Calculation validation failure: ``{"error_count"}`` and any
      issue-specific keys.
    * AEAT certificate health: ``{"provider_kind",
      "provider_operator_impact", "cert_not_after", "cert_severity",
      "cert_days_until_expiry"}``.
    * Site-health alerts: ``{"status", "run_id"}``.

    New keys may be added by the engine without bumping the workflow
    schema version. Removal or rename is a breaking change and must
    be paired with a workflow schema-version bump.

    Implements ``__getitem__``, ``__contains__``, and ``get`` so
    existing read-side code that treats ``step.details`` like a
    ``Mapping[str, str]`` keeps working without per-call-site
    migration; the typed model now anchors the storage shape.

    Frozen and strict on the inner values to preserve the
    boundary-strictness guarantee on workflow diagnostics.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="allow")

    def __getitem__(self, key: str) -> object:
        """Return the diagnostic value stored under ``key``."""
        return self.__pydantic_extra__[key] if self.__pydantic_extra__ else self.__dict__[key]

    def __contains__(self, key: object) -> bool:
        """Return ``True`` if ``key`` is present in the step's diagnostic payload."""
        extra = self.__pydantic_extra__ or {}
        return key in extra or key in self.__dict__

    def get(self, key: str, default: object = None) -> object:
        """Return the diagnostic value for ``key``, or ``default`` if absent."""
        if self.__pydantic_extra__ and key in self.__pydantic_extra__:
            return self.__pydantic_extra__[key]
        return self.__dict__.get(key, default)

    def items(self) -> Mapping[str, object]:
        """Return all extra diagnostic key-value pairs as a ``Mapping``."""
        merged: dict[str, object] = dict(self.__pydantic_extra__ or {})
        return merged


def _coerce_workflow_step_details(value: object) -> object:
    """BeforeValidator coercion: ``Mapping`` → ``WorkflowStepDetails``.

    Pydantic calls this before the ``WorkflowStep.details`` field is
    validated. ``None`` and already-typed instances pass through unchanged;
    a ``Mapping`` is coerced into a :class:`WorkflowStepDetails` so the
    stored shape is always the typed record.
    """
    if value is None or isinstance(value, WorkflowStepDetails):
        return value
    if isinstance(value, Mapping):
        return WorkflowStepDetails.model_validate(dict(value))
    return value


class WorkflowStep(BaseModel):
    """A single step in a :class:`WorkflowResult`."""

    model_config = _STRICT_FROZEN

    stage: WorkflowStage
    started_at: datetime
    ended_at: datetime | None = None
    success: bool | None = None
    summary: str
    details: Annotated[
        # The Mapping branch is intentionally typed ``str -> object`` rather
        # than ``str -> str`` because :class:`WorkflowStepDetails` carries
        # ``extra="allow"`` and stores diagnostic values heterogeneously
        # (engine call sites stringify by convention but the storage shape
        # is not constrained). The BeforeValidator coerces a Mapping to a
        # WorkflowStepDetails so downstream readers always see the typed
        # record.
        WorkflowStepDetails | Mapping[str, object] | None,
        BeforeValidator(_coerce_workflow_step_details),
    ] = None
    site_health_alert: SiteHealthAlert | None = None

    @model_validator(mode="after")
    def _check_timestamps(self) -> WorkflowStep:
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError(f"ended_at ({self.ended_at}) precedes started_at ({self.started_at})")
        if self.ended_at is not None and self.success is None:
            raise ValueError("completed steps must set success explicitly")
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
    summary: str
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
