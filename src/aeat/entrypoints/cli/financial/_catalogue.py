"""Shared catalogue loader helpers for ``aeat financial`` and ``aeat review``.

These helpers are extracted here so both the transaction CLI and the
pipeline-review CLI can load from the same configured store without
duplicating the settings lookup or the error translation. Every read
and write routes through
:class:`aeat.domain.transactions.TransactionCatalogueRepository`, so
plaintext transaction rows never land on disk.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ....core.config import load_settings
from ....domain.transactions import (
    TransactionCatalogue,
    TransactionError,
)
from .._i18n import t, tr


def catalogue_dir() -> Path:
    """Return the configured transaction catalogue store directory.

    Returns:
        The resolved value of ``Settings.aeat_financial_txs_dir``.
    """
    return load_settings().aeat_financial_txs_dir.resolve()


def catalogue_repository():
    """Return a :class:`aeat.domain.transactions.TransactionCatalogueRepository` bound to the configured store dir."""
    from ....domain.transactions import TransactionCatalogueRepository

    return TransactionCatalogueRepository(store_dir=catalogue_dir())


def catalogue_envelope_path() -> Path:
    """Return the canonical envelope file path under the configured store dir."""
    return catalogue_repository().envelope_path


def load_catalogue_or_empty() -> TransactionCatalogue:
    """Load the configured catalogue, returning an empty one when absent.

    Returns:
        The loaded :class:`aeat.domain.transactions.TransactionCatalogue`,
        which may be empty if no envelope has been written yet.

    Raises:
        typer.Exit: Exit code ``2`` when the envelope exists but cannot
            be parsed.
    """
    repo = catalogue_repository()
    try:
        return repo.load()
    except TransactionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def load_catalogue_required() -> TransactionCatalogue:
    """Load the configured catalogue or exit cleanly on failure.

    Returns:
        The loaded :class:`aeat.domain.transactions.TransactionCatalogue`.

    Raises:
        typer.Exit: Exit code ``2`` when the catalogue is missing or
            cannot be parsed.
    """
    repo = catalogue_repository()
    try:
        catalogue = repo.load()
    except TransactionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    if len(catalogue) == 0 and not repo.envelope_path.exists():
        typer.echo(
            tr(
                t(
                    f"catálogo de transacciones no encontrado en {repo.envelope_path}",
                    f"transaction catalogue not found at {repo.envelope_path}",
                    f"catàleg de transaccions no trobat a {repo.envelope_path}",
                    f"tranzakciókatalógus nem található itt: {repo.envelope_path}",
                )
            ),
            err=True,
        )
        raise typer.Exit(code=2)
    return catalogue
