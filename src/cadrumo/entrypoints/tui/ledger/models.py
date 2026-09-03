"""Immutable presentation records for the host-neutral Ledger workspace."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator

from ....application.ledger.workspace import (
    LedgerWorkspaceArea,
    LedgerWorkspaceAvailability,
    LedgerWorkspaceEntryRefV1,
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


__all__ = [
    "LedgerDestinationIdV1",
    "LedgerEntryRowV1",
    "LedgerReviewRowV1",
    "LedgerRouteRefusalV1",
    "LedgerRouteTargetV1",
]
