"""Application services for the user-facing AEAT CLI.

The command-line interface needs a small amount of workflow state that is
not owned by a single domain catalogue: the active setup profile, selected
auth method, ledger review annotations, invoice review annotations, and the
last declaration draft chosen for a modelo/period. This module keeps that
state behind the encrypted SQL byte-object backend so command handlers
remain a thin transport layer.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..adapters.persistence.storage.envelope._envelope import Envelope
from ..adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ..adapters.persistence.storage.sql import SecureObjectRepository
from ..core.classification import SensitivityClass
from ..core.config import Settings
from ..core.logging import get_logger

_logger = get_logger(__name__)

_STATE_VERSION = 1
_STATE_NAMESPACE = "aeat.application.user_cli"
_STATE_OBJECT_KEY = "state"


def utc_now() -> datetime:
    """Return an aware UTC timestamp for user-CLI workflow events."""

    return datetime.now(tz=UTC)


def _normalise_key(value: str) -> str:
    """Return the canonical key form used by setup/edit commands.

    Strips surrounding whitespace, lowercases, and folds dashes into
    dots. Underscores are preserved verbatim so registry-canonical
    keys (e.g. ``does_intracomunitario`` and ``iva.roi_enrolled``)
    survive the round-trip through the user-cli store and reach the
    deadline engine, which looks values up by exact key.
    """

    return value.strip().lower().replace("-", ".")


class WorkflowEvent(BaseModel):
    """One operator-visible workflow event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: str = Field(min_length=1)
    reason: str = ""
    at: datetime = Field(default_factory=utc_now)

    @field_validator("action", "reason")
    @classmethod
    def _trim_text(cls, value: str) -> str:
        return value.strip()


class AuthState(BaseModel):
    """Local AEAT access readiness state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str | None = None
    certificate_path: str | None = None
    configured_at: datetime | None = None
    authenticated_at: datetime | None = None
    subject: str | None = None


class ProfileRecord(BaseModel):
    """Setup profile values entered by the user."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    values: dict[str, str] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("name")
    @classmethod
    def _trim_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("profile name must not be blank")
        return trimmed

    @field_validator("values")
    @classmethod
    def _normalise_values(cls, value: dict[str, str]) -> dict[str, str]:
        return {_normalise_key(str(key)): str(raw).strip() for key, raw in value.items()}


class LedgerSplit(BaseModel):
    """Review metadata for a mixed-use ledger row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    business_share: Decimal
    personal_share: Decimal
    reason: str = ""
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("business_share", "personal_share")
    @classmethod
    def _share_in_unit_interval(cls, value: Decimal) -> Decimal:
        if value < Decimal("0") or value > Decimal("1"):
            raise ValueError("split shares must be within 0..1")
        return value

    @field_validator("reason")
    @classmethod
    def _trim_reason(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _shares_sum_to_one(self) -> Self:
        if self.business_share + self.personal_share != Decimal("1"):
            raise ValueError("split shares must sum to 1")
        return self


class LedgerReviewRecord(BaseModel):
    """Workflow annotations for one persisted transaction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: str = Field(min_length=1)
    skipped: bool = False
    split: LedgerSplit | None = None
    fields: dict[str, str] = Field(default_factory=dict)
    history: tuple[WorkflowEvent, ...] = ()
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("fields")
    @classmethod
    def _normalise_fields(cls, value: dict[str, str]) -> dict[str, str]:
        return {_normalise_key(str(key)): str(raw).strip() for key, raw in value.items()}


class InvoiceReviewRecord(BaseModel):
    """Workflow annotations for one persisted invoice."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    invoice_id: str = Field(min_length=1)
    fields: dict[str, str] = Field(default_factory=dict)
    history: tuple[WorkflowEvent, ...] = ()
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("fields")
    @classmethod
    def _normalise_fields(cls, value: dict[str, str]) -> dict[str, str]:
        return {_normalise_key(str(key)): str(raw).strip() for key, raw in value.items()}


class DeclarationPointer(BaseModel):
    """The last declaration draft selected for a modelo/period."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1)
    modelo: str = Field(min_length=1)
    period: str = Field(min_length=1)
    draft_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    exported_path: str | None = None
    verified_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class UserCliState(BaseModel):
    """Encrypted state payload for the user-facing CLI workflow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    active_profile: str | None = None
    profiles: dict[str, ProfileRecord] = Field(default_factory=dict)
    auth: AuthState = Field(default_factory=AuthState)
    ledger_reviews: dict[str, LedgerReviewRecord] = Field(default_factory=dict)
    invoice_reviews: dict[str, InvoiceReviewRecord] = Field(default_factory=dict)
    declarations: dict[str, DeclarationPointer] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utc_now)

    def active_profile_record(self) -> ProfileRecord | None:
        """Return the active profile record if one is selected."""

        if self.active_profile is None:
            return None
        return self.profiles.get(self.active_profile)


class UserCliStateRepository:
    """Encrypted SQL object repository for :class:`UserCliState`."""

    def __init__(self) -> None:
        self._objects = SecureObjectRepository()

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> Self:
        del settings
        return cls()

    def load(self) -> UserCliState:
        """Load state or return an empty payload when absent."""

        record = self._objects.load(
            _STATE_NAMESPACE,
            _STATE_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_STATE_VERSION,
        )
        if record is None:
            return UserCliState()
        envelope = Envelope[UserCliState].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.FINANCIAL:
            raise ClassificationError(
                f"user CLI state has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.FINANCIAL}",
            )
        if envelope.schema_version > _STATE_VERSION:
            raise EnvelopeVersionError(
                f"user CLI state is at version {envelope.schema_version}; consumer supports up to {_STATE_VERSION}",
            )
        return envelope.payload

    def save(self, state: UserCliState) -> None:
        """Persist state in the encrypted database object store."""

        envelope = Envelope[UserCliState](
            schema_version=_STATE_VERSION,
            written_at=utc_now(),
            classification=SensitivityClass.FINANCIAL,
            payload=state.model_copy(update={"updated_at": utc_now()}),
        )
        self._objects.save(
            namespace=_STATE_NAMESPACE,
            object_key=_STATE_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_STATE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _logger.debug("persisted user-cli state to secure backend")

    def update(self, fn: Callable[[UserCliState], UserCliState]) -> UserCliState:
        """Load, transform, save, and return the updated state."""

        state = self.load()
        updated = fn(state)
        self.save(updated)
        return updated


def state_repository(settings: Settings | None = None) -> UserCliStateRepository:
    """Return the repository bound to the configured run-state directory."""

    return UserCliStateRepository.from_settings(settings)


def set_active_profile(state: UserCliState, name: str) -> UserCliState:
    """Select or create an active profile."""

    profile_name = name.strip()
    if not profile_name:
        raise ValueError("profile name must not be blank")
    profiles = dict(state.profiles)
    if profile_name not in profiles:
        profiles[profile_name] = ProfileRecord(name=profile_name)
    return state.model_copy(update={"active_profile": profile_name, "profiles": profiles, "updated_at": utc_now()})


def set_profile_values(state: UserCliState, profile_name: str, values: dict[str, str]) -> UserCliState:
    """Merge values into one profile and select it."""

    profiles = dict(state.profiles)
    current = profiles.get(profile_name, ProfileRecord(name=profile_name))
    merged = {**current.values, **{_normalise_key(key): raw.strip() for key, raw in values.items()}}
    profiles[profile_name] = current.model_copy(update={"values": merged, "updated_at": utc_now()})
    return state.model_copy(update={"active_profile": profile_name, "profiles": profiles, "updated_at": utc_now()})


def clear_profile_values(state: UserCliState, profile_name: str, keys: tuple[str, ...]) -> UserCliState:
    """Clear values from one profile and select it."""

    profiles = dict(state.profiles)
    current = profiles.get(profile_name, ProfileRecord(name=profile_name))
    values = dict(current.values)
    for key in keys:
        values.pop(_normalise_key(key), None)
    profiles[profile_name] = current.model_copy(update={"values": values, "updated_at": utc_now()})
    return state.model_copy(update={"active_profile": profile_name, "profiles": profiles, "updated_at": utc_now()})


def update_auth(
    state: UserCliState,
    *,
    provider: str | None = None,
    certificate_path: str | None = None,
    authenticated: bool | None = None,
    subject: str | None = None,
) -> UserCliState:
    """Update local auth readiness state."""

    auth = state.auth
    update: dict[str, Any] = {}
    if provider is not None:
        update["provider"] = provider.strip().lower()
        update["configured_at"] = utc_now()
    if certificate_path is not None:
        update["certificate_path"] = certificate_path.strip() or None
        update["configured_at"] = utc_now()
    if authenticated is not None:
        update["authenticated_at"] = utc_now() if authenticated else None
    if subject is not None:
        update["subject"] = subject.strip() or None
    return state.model_copy(update={"auth": auth.model_copy(update=update), "updated_at": utc_now()})


def update_ledger_review(
    state: UserCliState,
    transaction_id: str,
    *,
    fields: dict[str, str] | None = None,
    skipped: bool | None = None,
    split: LedgerSplit | None | object = None,
    clear_split: bool = False,
    action: str,
    reason: str = "",
) -> UserCliState:
    """Return state with review metadata updated for one transaction."""

    reviews = dict(state.ledger_reviews)
    current = reviews.get(transaction_id, LedgerReviewRecord(transaction_id=transaction_id))
    update: dict[str, Any] = {"updated_at": utc_now()}
    if fields:
        update["fields"] = {**current.fields, **{_normalise_key(key): raw for key, raw in fields.items()}}
    if skipped is not None:
        update["skipped"] = skipped
    if clear_split:
        update["split"] = None
    elif isinstance(split, LedgerSplit):
        update["split"] = split
    event = WorkflowEvent(action=action, reason=reason)
    update["history"] = (*current.history, event)
    reviews[transaction_id] = current.model_copy(update=update)
    return state.model_copy(update={"ledger_reviews": reviews, "updated_at": utc_now()})


def update_invoice_review(
    state: UserCliState,
    invoice_id: str,
    *,
    fields: dict[str, str],
    action: str,
    reason: str = "",
) -> UserCliState:
    """Return state with review metadata updated for one invoice."""

    reviews = dict(state.invoice_reviews)
    current = reviews.get(invoice_id, InvoiceReviewRecord(invoice_id=invoice_id))
    event = WorkflowEvent(action=action, reason=reason)
    reviews[invoice_id] = current.model_copy(
        update={
            "fields": {**current.fields, **{_normalise_key(key): raw for key, raw in fields.items()}},
            "history": (*current.history, event),
            "updated_at": utc_now(),
        }
    )
    return state.model_copy(update={"invoice_reviews": reviews, "updated_at": utc_now()})


def declaration_key(modelo: str, period: str) -> str:
    """Return the stable state key for a declaration slot."""

    return f"{modelo.strip()}:{period.strip()}"


def update_declaration_pointer(
    state: UserCliState,
    *,
    modelo: str,
    period: str,
    draft_id: str,
    status: str,
    exported_path: str | None = None,
    verified: bool = False,
) -> UserCliState:
    """Persist the last draft/export state for one declaration slot."""

    key = declaration_key(modelo, period)
    current = state.declarations.get(key)
    pointer = DeclarationPointer(
        key=key,
        modelo=modelo,
        period=period,
        draft_id=draft_id,
        status=status,
        exported_path=exported_path if exported_path is not None else (current.exported_path if current else None),
        verified_at=utc_now() if verified else (current.verified_at if current else None),
    )
    declarations = dict(state.declarations)
    declarations[key] = pointer
    return state.model_copy(update={"declarations": declarations, "updated_at": utc_now()})


__all__ = [
    "AuthState",
    "DeclarationPointer",
    "InvoiceReviewRecord",
    "LedgerReviewRecord",
    "LedgerSplit",
    "ProfileRecord",
    "UserCliState",
    "UserCliStateRepository",
    "WorkflowEvent",
    "clear_profile_values",
    "declaration_key",
    "set_active_profile",
    "set_profile_values",
    "state_repository",
    "update_auth",
    "update_declaration_pointer",
    "update_invoice_review",
    "update_ledger_review",
    "utc_now",
]
