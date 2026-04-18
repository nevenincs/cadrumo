"""`aeat review history` command (#237)."""

from __future__ import annotations

import json
from typing import Any

import typer

from ...financial.transactions import (
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
    appended as the final synthesised entry so Kent can see every
    decision applied to this transaction, including the head.
    """
    catalogue = load_catalogue_required()
    transaction = find_transaction(catalogue, transaction_id)
    if transaction is None:
        typer.echo(f"transaction not found: {transaction_id}", err=True)
        raise typer.Exit(code=2)
    head = snapshot_classification_state(transaction)
    entries = (*transaction.classification_history, head)
    typer.echo(json.dumps([_entry_payload(entry) for entry in entries], indent=2, default=str))


def _entry_payload(entry: ClassificationHistoryEntry) -> dict[str, Any]:
    """Return a JSON-serialisable payload for one history entry."""
    return entry.model_dump(mode="json")
