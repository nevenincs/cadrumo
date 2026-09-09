"""Persisted workflow state contracts and their state-scoped helpers.

This module owns the encrypted :class:`WorkflowState` envelope and
transaction-catalogue selection. Active-profile selection and
record resolution live in :mod:`.active_profile`, while run stages, deadline
observations, step details, and terminal results live in :mod:`.run_models`.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time.clock import now as utc_now
from ..auth.models import AuthState
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


class WorkflowState(BaseModel):
    """Encrypted operator state for the Cadrumo ``aeat`` CLI.

    The entire state is persisted as a single encrypted envelope via
    :class:`WorkflowStateRepository`. Mutations always return a new
    copy (:meth:`model_copy`) to preserve the frozen-model invariant.

    Attributes:
        auth: Local AEAT access readiness state.
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


__all__ = ["WorkflowState"]
