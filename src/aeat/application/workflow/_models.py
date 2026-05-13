"""Strict pydantic v2 records for the composite workflow engine.

Every boundary-crossing type in :mod:`aeat.application.workflow` is
defined here as a frozen, strict, ``extra="forbid"``
:class:`pydantic.BaseModel` or as an :class:`enum.StrEnum` for closed
enumerations. :attr:`WorkflowStep.details` is reserved for string-valued
diagnostics emitted by workflow diagnostics.

Import ordering note
--------------------
The ``SiteHealthStatus`` and ``FilingObligation`` imports are placed
*after* :class:`WorkflowState` and related state models so that
:mod:`aeat.application.auth._actions` (which imports :class:`WorkflowState`
from this partially-initialised module during the browser-adapter import
chain) finds those names already present.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..auth._models import AuthState
from ._utils import utc_now

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class WorkflowEvent(BaseModel):
    """One operator-visible workflow event."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    action: str = Field(min_length=1)
    reason: str = ""
    bucket_id: str | None = None
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


class WorkflowAbortReason(StrEnum):
    """Closed set of reasons the workflow may abort."""

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


class DeclarationPointer(BaseModel):
    """Pointer to a persisted filing draft and its status."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: str
    period: str
    draft_id: str | None = None
    status: str | None = None
    exported_path: str | None = None
    verified: bool | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class ProfileBucketPointer(BaseModel):
    """Pointer from workflow state to a secure profile bucket."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bucket_id: str = Field(min_length=1, max_length=128)

    @field_validator("bucket_id")
    @classmethod
    def _trim_bucket_id(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("bucket_id must not be blank")
        return trimmed


def declaration_key(modelo: str, period: str) -> str:
    """Return the canonical state-store key for a ``(modelo, period)`` pair."""
    return f"{modelo.strip()}:{period.strip()}"


class WorkflowState(BaseModel):
    """Encrypted operator state for the AEAT user CLI.

    The entire state is persisted as a single encrypted envelope via
    :class:`WorkflowStateRepository`. Mutations always return a new
    copy (:meth:`model_copy`) to preserve the frozen-model invariant.

    Attributes:
        auth: Local AEAT access readiness state.
        profiles: Profile-bucket pointers keyed by profile name.
        active_profile: Currently selected profile name, or ``None``.
        declarations: Filing draft pointers keyed by :func:`declaration_key`.
        invoice_reviews: Invoice review annotations keyed by ``invoice_id``.
        ledger_reviews: Ledger transaction review annotations keyed by
            ``transaction_id``.
        updated_at: UTC timestamp of the last write.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    auth: AuthState = Field(default_factory=AuthState)
    profiles: dict[str, ProfileBucketPointer] = Field(default_factory=dict)
    active_profile: str | None = None
    declarations: dict[str, DeclarationPointer] = Field(default_factory=dict)
    invoice_reviews: dict[str, Any] = Field(default_factory=dict)
    ledger_reviews: dict[str, Any] = Field(default_factory=dict)
    bucket_events: tuple[WorkflowEvent, ...] = ()
    updated_at: datetime = Field(default_factory=utc_now)

    def active_profile_record(self) -> Any | None:
        """Return the active profile record from the profile's secure bucket."""
        if self.active_profile is None:
            return None
        pointer = self.profiles.get(self.active_profile)
        if pointer is None:
            return None
        from ..profile._repository import profile_bucket_repository

        return profile_bucket_repository().load(pointer.bucket_id)

    def active_profile_bucket_id(self) -> str | None:
        """Return the active profile's secure bucket id."""
        if self.active_profile is None:
            return None
        pointer = self.profiles.get(self.active_profile)
        if pointer is None:
            return None
        return pointer.bucket_id


def update_declaration_pointer(
    state: WorkflowState,
    *,
    modelo: str,
    period: str,
    draft_id: str,
    status: str,
    exported_path: str | None = None,
    verified: bool | None = None,
) -> WorkflowState:
    """Return ``state`` with the declaration pointer upserted for ``(modelo, period)``."""
    import json as _json

    declarations: dict[str, Any] = dict(state.declarations)
    key = declaration_key(modelo, period)
    current = declarations.get(key)
    if isinstance(current, dict):
        current = DeclarationPointer.model_validate_json(_json.dumps(current, default=str))

    update_fields: dict[str, Any] = {
        "draft_id": draft_id,
        "status": status,
        "updated_at": utc_now(),
    }
    if exported_path is not None:
        update_fields["exported_path"] = exported_path
    if verified is not None:
        update_fields["verified"] = verified

    if isinstance(current, DeclarationPointer):
        declarations[key] = current.model_copy(update=update_fields)
    else:
        declarations[key] = DeclarationPointer(modelo=modelo, period=period, **update_fields)
    return state.model_copy(update={"declarations": declarations, "updated_at": utc_now()})


# ---------------------------------------------------------------------------
# Heavy adapter/domain imports — placed AFTER the state models above so that
# auth._actions (which imports WorkflowState from this partially-loaded
# module during the browser-adapter initialisation chain) finds the names
# already present in sys.modules['aeat.application.workflow._models'].
# ---------------------------------------------------------------------------

from ...adapters.outbound.aeat.browser._site_health import SiteHealthStatus  # noqa: E402
from ...domain.deadlines import FilingObligation  # noqa: E402


class SiteHealthAlert(BaseModel):
    """Workflow-side alert wrapping a browser site-health status."""

    model_config = _STRICT_FROZEN

    stage: WorkflowStage
    status: SiteHealthStatus
    run_id: str = Field(min_length=1, max_length=128)


class WorkflowStep(BaseModel):
    """A single step in a :class:`WorkflowResult`."""

    model_config = _STRICT_FROZEN

    stage: WorkflowStage
    started_at: datetime
    ended_at: datetime | None = None
    success: bool | None = None
    summary: str
    details: dict[str, str] | None = None
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
    obligation: FilingObligation | None = None
    draft_id: str | None = None
    submission_id: str | None = None
    steps: tuple[WorkflowStep, ...]
    summary: str

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
    period: str,
    started_at: datetime,
) -> str:
    """Return a stable 16-char hex hash for a workflow run."""
    payload = "|".join([tax_id, modelo, period, started_at.isoformat()])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
