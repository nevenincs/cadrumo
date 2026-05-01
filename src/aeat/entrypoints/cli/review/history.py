"""``aeat review history`` command implementation.

Emits the classification history chain for one transaction as JSON,
oldest first with the current head appended last so the operator sees
every decision applied to the transaction.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from ....domain.transactions import (
    ClassificationHistoryEntry,
    find_transaction,
    snapshot_classification_state,
)
from ..financial._catalogue import load_catalogue_required


def history_cmd(
    transaction_id: str = typer.Argument(..., help="Stable transaction identifier."),
) -> None:
    """Print a transaction's classification history chain as JSON.

    Entries are emitted oldest first; the current classification is
    appended as the final synthesised entry so Kent sees every decision
    applied to this transaction, including the head.

    Args:
        transaction_id: Stable transaction identifier to resolve in the
            persisted catalogue.

    Raises:
        typer.Exit: Code ``2`` when ``transaction_id`` does not match
            any persisted transaction.
    """
    catalogue = load_catalogue_required()
    transaction = find_transaction(catalogue, transaction_id)
    if transaction is None:
        typer.echo(f"transaction not found: {transaction_id}", err=True)
        raise typer.Exit(code=2)
    head = snapshot_classification_state(transaction)
    entries = (*transaction.classification_history, head)
    typer.echo(json.dumps([_entry_payload(entry) for entry in entries], indent=2))


def _entry_payload(entry: ClassificationHistoryEntry) -> dict[str, Any]:
    """Return a JSON-serialisable payload for one history entry."""
    return entry.model_dump(mode="json")
