"""Shared catalogue loader helpers for ``aeat financial`` and ``aeat review``.

These helpers are extracted here so both the transaction CLI and the
pipeline-review CLI can load from the same configured path without
duplicating the settings lookup or the error translation.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ...config import load_settings
from ...financial.transactions import (
    TransactionCatalogue,
    TransactionError,
    load_transactions,
)

DEFAULT_CATALOGUE_FILENAME = "transactions.json"


def catalogue_path() -> Path:
    """Return the default on-disk catalogue path from settings."""
    return load_settings().aeat_financial_txs_dir.resolve() / DEFAULT_CATALOGUE_FILENAME


def load_catalogue_or_empty() -> TransactionCatalogue:
    """Load the configured catalogue, returning an empty one when absent."""
    path = catalogue_path()
    if path.exists():
        return load_catalogue_required()
    return TransactionCatalogue()


def load_catalogue_required() -> TransactionCatalogue:
    """Load the configured catalogue or exit cleanly on failure."""
    path = catalogue_path()
    try:
        return load_transactions(path)
    except TransactionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
