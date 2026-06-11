"""Strict pydantic v2 records for the composite workflow engine.

Every boundary-crossing type in :mod:`aeat.application.workflow` is
defined here as a frozen, strict, ``extra="forbid"``
:class:`pydantic.BaseModel` or as an :class:`enum.StrEnum` for closed
enumerations. :attr:`WorkflowStep.details` is reserved for string-valued
diagnostics emitted by workflow diagnostics. Some helpers accept an
optional :class:`SecureObjectRepository` so callers can supply a custom
storage backend without going through the runtime default. The
:class:`WorkflowState` record carries a reference to the active-bucket
:class:`TransactionCatalogueRepository` when one is needed downstream.

This module uses :class:`WorkflowResult`, :class:`WorkflowEngine`,
and :class:`UserProfileRecord` for workflow persistence and state management.

Import ordering note
--------------------
The ``SiteHealthStatus`` and ``ModeloDeadline`` imports are placed
*after* :class:`WorkflowState` and related state models so that
:mod:`aeat.application.auth._actions` (which imports :class:`WorkflowState`
from this partially-initialised module during the browser-adapter import
chain) finds those names already present.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from ...adapters.persistence.storage.bucket import BucketLifecycleStatus
from ...core import (
    STRICT_FROZEN_CONFIG as _STRICT_FROZEN,
)
from ...core import (
    Period,
    require_active_bucket_id,
    resolve_active_bucket_id,
)
from ...core.identity import BucketId
from ...core.logging import get_logger
from ..auth._models import AuthState
from ._utils import utc_now

if TYPE_CHECKING:
    from ...adapters.persistence.storage.sql import SecureObjectRepository
    from ...domain.transactions import TransactionCatalogueRepository
    from ...domain.user_profile import UserProfileRecord
    from ..review._models import InvoiceReviewRecord, LedgerReviewRecord

_log = get_logger(__name__)


class WorkflowEvent(BaseModel):
    """One operator-visible event emitted by a mutating workflow verb.

    Events are appended to :attr:`WorkflowState.bucket_events` so the
    operator can audit which actions ran, when, and against which object.
    ``action`` names the verb (e.g. ``"profile.created"``); ``reason``
    carries a free-form human-readable annotation; ``bucket_id`` and
    ``object_id`` are optional pointers to the affected resource.
    """

    model_config = _STRICT_FROZEN

    action: str = Field(min_length=1)
    reason: str = ""
    bucket_id: BucketId | None = None
    object_id: str | None = None
    at: datetime = Field(default_factory=utc_now)

    @field_validator("action", "reason")
    @classmethod
    def _trim_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("bucket_id", "object_id")
    @classmethod
    def _trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


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


class WorkflowAbortReason(StrEnum):
    """Closed set of reasons the :class:`WorkflowEngine` may abort a run.

    Each member maps to a distinct failure path in the engine's stage
    sequence. CLI surfaces and audit logs carry the string value so
    operators and tools can key on it without importing this module.
    """

    NO_PENDING_OBLIGATION = "NO_PENDING_OBLIGATION"
    INBOX_BLOCKING_REQUERIMIENTO = "INBOX_BLOCKING_REQUERIMIENTO"
    DEADLINE_PASSED = "DEADLINE_PASSED"
    ALREADY_FILED = "ALREADY_FILED"
    DRAFT_HAS_ERRORS = "DRAFT_HAS_ERRORS"
    PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
    CERT_INVALID = "CERT_INVALID"
    USER_CANCELLED = "USER_CANCELLED"
    SITE_UNAVAILABLE = "SITE_UNAVAILABLE"
    UNHANDLED_EXCEPTION = "UNHANDLED_EXCEPTION"


class DeclaracionPointer(BaseModel):
    """Lightweight pointer to a persisted filing draft stored in :class:`WorkflowState`.

    Keyed in :attr:`WorkflowState.declarations` by the value returned from
    :func:`declaration_key`. ``draft_id`` and ``status`` are written by the
    workflow engine after each filing stage; ``exported_path`` records the
    on-disk fichero-BOE path when the draft was exported; ``verified`` records
    the last verification verdict for the ``work verify`` command.
    """

    model_config = _STRICT_FROZEN

    modelo: str
    period: Period
    draft_id: str | None = None
    status: str | None = None
    exported_path: str | None = None
    verified: bool | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class ProfileBucketPointer(BaseModel):
    """Pointer to a secure profile bucket.

    ``bucket_id`` is the immutable UUIDv4 profile identity and the
    name of the bucket directory on disk. ``label`` is the decoupled
    mutable operator-chosen display name read from the bucket manifest.
    ``status`` is the plaintext lifecycle marker carried on the
    manifest; the live-surface scanners filter on it so a tombstoned
    profile never leaks into ``list`` / ``switch`` / name-uniqueness.
    """

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    label: str = Field(min_length=1, max_length=160)
    status: BucketLifecycleStatus = BucketLifecycleStatus.ACTIVE

    @field_validator("bucket_id", "label")
    @classmethod
    def _trim_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value must not be blank")
        return trimmed


def _period_identity_segment(period: Period) -> str:
    """Return the stable non-combined identity segment for ``period``."""
    if not isinstance(period, Period):
        raise TypeError(f"period must be aeat.core.Period, got {type(period).__name__}")
    return f"{period.filing_year}:{period.registry_token}"


def declaration_key(modelo: str, period: Period) -> str:
    """Return the canonical state-store key for a ``(modelo, period)`` pair.

    The period segment is stored as ``filing_year:registry_token`` so
    declaration state never keys by a combined token such as ``2025Q1``.
    """
    return f"{modelo.strip()}:{_period_identity_segment(period)}"


class WorkflowState(BaseModel):
    """Encrypted operator state for the AEAT user CLI.

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
    :func:`aeat.application.workflow._profile_bucket_scan.list_profile_buckets`
    or :func:`read_profile_bucket` directly; both scan
    ``<aeat_local_storage_root>/buckets/*/manifest.toml`` and never
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

    def active_profile_record(self) -> UserProfileRecord | None:
        """Return the active :class:`UserProfileRecord` from its secure bucket.

        The active bucket id resolves via the precedence chain in
        :func:`resolve_active_bucket_id` (env var > pointer file > state
        fallback). The bucket id and profile name are 1:1 by orchestration
        convention, so the resolved id is the lifecycle-service read key.
        """
        bucket_id = resolve_active_bucket_id()
        if bucket_id is None:
            return None
        from ...domain.user_profile import ProfileNotFoundError
        from ..user_profile._orchestration import build_lifecycle_service

        service = build_lifecycle_service(bucket_id=bucket_id)
        try:
            return service.read(bucket_id)
        except ProfileNotFoundError as exc:
            _log.debug("active profile record resolution returned no profile record: %s", type(exc).__name__)
            return None

    def active_profile_bucket_id(self) -> str | None:
        """Return the active profile's secure bucket id via the precedence chain."""
        return resolve_active_bucket_id()


def active_transaction_catalogue_repository(
    state: WorkflowState,
    *,
    objects: SecureObjectRepository | None = None,
) -> TransactionCatalogueRepository:
    """Return the :class:`TransactionCatalogueRepository` for the active profile bucket.

    Args:
        state: The current workflow state used to resolve the active bucket.
        objects: Optional :class:`SecureObjectRepository` override passed through
            to the returned repository.
    """
    from ...core.errors import NoActiveProfileError
    from ...domain.transactions import LedgerNoActiveBucketError, TransactionCatalogueRepository

    try:
        bucket_id = require_active_bucket_id()
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
# already present in sys.modules['aeat.application.workflow._models'].
# ---------------------------------------------------------------------------

from ...adapters.outbound.aeat.browser._site_health import SiteHealthStatus
from ...domain.deadlines import ModeloDeadline
from ..review._models import (
    InvoiceReviewRecord,
    LedgerReviewRecord,
)

WorkflowState.model_rebuild()


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
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
