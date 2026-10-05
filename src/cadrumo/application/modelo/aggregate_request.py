"""Confidential typed aggregate requests and optional ledger payment evidence."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..aggregation.ledger_payment_withholding import (
    LedgerPaymentWithholdingEvidenceRequest,
)
from ..aggregation.service import (
    PerModeloAggregationCommand,
)
from .aggregate_contracts import AGGREGATE_LEDGER_PAYMENT_MODELOS
from .aggregate_public import PublicLedgerPaymentEvidenceRequest, PublicModeloAggregateCommand


class ModeloAggregateOperationRequest(BaseModel):
    """Confidential typed aggregation operands and optional ledger payment evidence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    command: PublicModeloAggregateCommand = Field(repr=False)
    ledger_payment: PublicLedgerPaymentEvidenceRequest | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def _closed_aggregate_scope(self) -> Self:
        model = self.command.modelo
        if self.ledger_payment is not None:
            if model not in AGGREGATE_LEDGER_PAYMENT_MODELOS:
                raise ValueError("ledger-payment withholding capture is supported only for Modelos 111 and 123")
            if self.command.counterpart_observations or self.command.foreign_asset_observations:
                raise ValueError("ledger-payment capture cannot be mixed with another aggregation provider")
        return self

    @classmethod
    def from_inputs(
        cls,
        *,
        profile_id: UUID,
        command: PerModeloAggregationCommand,
        ledger_payment: LedgerPaymentWithholdingEvidenceRequest | None = None,
    ) -> Self:
        """Keep the exact typed CLI/TUI/MCP operands in the encrypted request store."""
        return cls(
            profile_id=profile_id,
            command=PublicModeloAggregateCommand.from_domain(command),
            ledger_payment=(
                None if ledger_payment is None else PublicLedgerPaymentEvidenceRequest.from_domain(ledger_payment)
            ),
        )
