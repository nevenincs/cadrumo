"""Prepare and commit manual transactions through the live ledger services in tests."""

from __future__ import annotations

from datetime import datetime

from ....domain.currency.service import CurrencyNormalizationService
from ..action_ports import LedgerActionPorts
from ..actions_manual import commit_manual_transaction, prepare_manual_transaction
from ..models import ManualLedgerTransactionCommand, ManualLedgerTransactionResult


def create_manual_transaction(
    command: ManualLedgerTransactionCommand,
    *,
    ports: LedgerActionPorts,
    occurred_at: datetime | None = None,
    currency_normalizer: CurrencyNormalizationService | None = None,
    require_revision_guard: bool = False,
) -> ManualLedgerTransactionResult:
    """Persist one manual ledger transaction in the command's bucket.

    Returns a :class:`~cadrumo.application.ledger.models.ManualLedgerTransactionResult`
    with the created transaction and associated bucket event.
    """
    prepared = prepare_manual_transaction(
        command,
        ports=ports,
        occurred_at=occurred_at,
        currency_normalizer=currency_normalizer,
        require_revision_guard=require_revision_guard,
    )
    if isinstance(prepared, ManualLedgerTransactionResult):
        return prepared
    return commit_manual_transaction(prepared, ports=ports)
