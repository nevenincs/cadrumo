"""Immutable presentation records for the host-neutral Ledger workspace."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, model_validator

from ....application.ledger.workspace import (
    LedgerWorkspaceArea,
    LedgerWorkspaceAvailability,
    LedgerWorkspaceEntryRefV1,
)
from ....application.ledger.models import (
    LedgerSourceImportCommand,
    LedgerSourceImportResult,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)
from ....application.operator_actions.models import ActionReference
from ....core.identity import TransactionId
from ....core.models import STRICT_FROZEN_CONFIG

type LedgerDestinationIdV1 = Literal[
    "ledger.overview",
    "ledger.entries",
    "ledger.review",
    "ledger.import",
    "ledger.classification",
    "ledger.evidence",
    "ledger.reconciliation",
]


class LedgerRouteTargetV1(BaseModel):
    """One internal destination selected by its stable area identity."""

    model_config = STRICT_FROZEN_CONFIG

    destination: LedgerDestinationIdV1
    area: LedgerWorkspaceArea


class LedgerRouteRefusalV1(BaseModel):
    """A route that cannot be opened, preserving the authority that refused it."""

    model_config = STRICT_FROZEN_CONFIG

    target: LedgerRouteTargetV1
    availability: LedgerWorkspaceAvailability
    reason_key: str


class LedgerEntryRowV1(BaseModel):
    """Safe entry row containing no description, amount, counterparty, or evidence."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
    review_status: str
    source: LedgerWorkspaceEntryRefV1

    @model_validator(mode="after")
    def _mirror_source(self) -> LedgerEntryRowV1:
        if self.transaction_id != self.source.transaction_id or self.review_status != self.source.review_status:
            raise ValueError("Ledger entry row must mirror its application projection source")
        return self


class LedgerReviewRowV1(BaseModel):
    """A reviewable transaction plus the canonical read action naming its door."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
    review_status: str
    action: ActionReference
    source: LedgerWorkspaceEntryRefV1

    @model_validator(mode="after")
    def _mirror_source(self) -> LedgerReviewRowV1:
        if self.transaction_id != self.source.transaction_id or self.review_status != self.source.review_status:
            raise ValueError("Ledger review row must mirror its application projection source")
        return self


class LedgerFlowState(StrEnum):
    """Explicit state of a command-backed Ledger interaction."""

    EDITING = "editing"
    CONFIRMING = "confirming"
    SUBMITTING = "submitting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LedgerClassificationSubmissionV1(BaseModel):
    """Catalogue-authorized canonical classification patch submission."""

    model_config = STRICT_FROZEN_CONFIG

    action: ActionReference
    transaction_id: TransactionId
    patch: ManualLedgerTransactionPatch


class LedgerClassificationSubmitterV1(Protocol):
    """Injected application door for a classification mutation."""

    async def __call__(self, submission: LedgerClassificationSubmissionV1) -> ManualLedgerTransactionResult: ...


class LedgerPreparedImportV1:
    """Opaque pre-resolved import command plus safe catalogue display keys.

    The command deliberately has no public attribute, representation, or model
    serialization surface: paths and provider transport values remain inside
    the injected command boundary.
    """

    __slots__ = ("_command", "choice_id", "provider_label_key", "source_label_key")

    def __init__(
        self,
        *,
        choice_id: str,
        provider_label_key: str,
        source_label_key: str,
        command: LedgerSourceImportCommand,
    ) -> None:
        if not choice_id or not provider_label_key.startswith("tui.ledger.") or not source_label_key.startswith("tui.ledger."):
            raise ValueError("prepared imports require safe Ledger catalogue identities")
        self.choice_id = choice_id
        self.provider_label_key = provider_label_key
        self.source_label_key = source_label_key
        self._command = command

    def __repr__(self) -> str:
        return f"LedgerPreparedImportV1(choice_id={self.choice_id!r})"


class LedgerImportSubmitterV1(Protocol):
    """Injected application door for an already-resolved import command."""

    async def __call__(self, command: LedgerSourceImportCommand) -> LedgerSourceImportResult: ...


__all__ = [
    "LedgerDestinationIdV1",
    "LedgerClassificationSubmissionV1",
    "LedgerClassificationSubmitterV1",
    "LedgerEntryRowV1",
    "LedgerFlowState",
    "LedgerImportSubmitterV1",
    "LedgerPreparedImportV1",
    "LedgerReviewRowV1",
    "LedgerRouteRefusalV1",
    "LedgerRouteTargetV1",
]
