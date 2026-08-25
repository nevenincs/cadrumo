"""Persisted workflow state contracts and their state-scoped helpers.

This module owns the encrypted :class:`WorkflowState` envelope, declaration
pointers, and transaction-catalogue selection. Active-profile selection and
record resolution live in :mod:`.active_profile`, while run stages, deadline
observations, step details, and terminal results live in :mod:`.run_models`.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, BeforeValidator, Field

from ...core import (
    STRICT_FROZEN_CONFIG as _STRICT_FROZEN,
)
from ...core import (
    Modelo,
    Period,
)
from ...core.time import now as utc_now
from ...domain.submission import ModeloDraftStatus
from ..auth.models import AuthState
from ._identity import period_identity_segment
from .active_profile import (
    active_profile_selection,
    resolve_active_profile_record,
)
from .review_models import (
    InvoiceReviewRecord,
    LedgerReviewRecord,
    WorkflowEvent,
)

if TYPE_CHECKING:
    from ...domain.user_profile.values import UserProfileRecord


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


def declaration_key(modelo: str, period: Period) -> str:
    """Return the canonical state-store key for a ``(modelo, period)`` pair.

    The period segment is stored as ``filing_year:registry_token`` so
    declaration state never keys by a combined token such as ``2025Q1``.
    """
    return f"{modelo.strip()}:{period_identity_segment(period)}"


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
    :func:`cadrumo.application.workflow.profile_bucket_scan.list_profile_buckets`
    or :func:`read_profile_bucket` directly; both enumerate only committed
    current-format capsules through their anchored descriptors and never
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

        The active selector resolves via the precedence chain in
        :func:`cadrumo.application.workflow.active_profile.active_profile_selection`
        resolves the canonical selector, then the committed-capsule projection resolves a display
        label to its immutable bucket UUID before secure storage is addressed.

        This is the convenience view for callers that legitimately act only on
        a present record and treat every absence alike. A caller that REPORTS
        the absence to an operator must use
        :func:`resolve_active_profile_record` instead: the ``None`` here does
        not distinguish a locked profile from one whose record is genuinely
        gone, and a projection that guesses between them tells the operator
        their financial records are missing when they merely need to log in.
        """
        return resolve_active_profile_record().record

    def active_profile_bucket_id(self) -> str | None:
        """Return the selected profile's canonical secure bucket UUID.

        Core owns active-selector precedence. The committed-capsule projection
        then maps an operator-facing label to the existing immutable bucket
        UUID. A selector without a current capsule has no secure bucket and
        returns ``None``; health diagnostics retain the raw selector separately.
        """
        return active_profile_selection()[1]


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


__all__ = [
    "DeclaracionPointer",
    "WorkflowState",
    "declaration_key",
    "update_declaration_pointer",
]
