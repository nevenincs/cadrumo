"""Shared catalogue loader helpers for ``aeat financial`` and ``aeat review``.

These helpers are extracted here so both the transaction CLI and the
pipeline-review CLI can load from the same configured store without
duplicating the settings lookup or the error translation. Every read
and write routes through
:class:`aeat.domain.transactions.TransactionCatalogueRepository`, so
plaintext transaction rows never land on disk.
"""

from __future__ import annotations

import typer

from ....core.logging import get_logger
from ....domain.transactions import (
    TransactionCatalogue,
    TransactionError,
)
from .._i18n import tr

_logger = get_logger(__name__)


def catalogue_repository():
    """Return the transaction catalogue repository bound to the secure backend."""
    from ....domain.transactions import TransactionCatalogueRepository

    return TransactionCatalogueRepository()


def load_catalogue_or_empty() -> TransactionCatalogue:
    """Load the configured catalogue, returning an empty one when absent.

    Returns:
        The loaded :class:`aeat.domain.transactions.TransactionCatalogue`,
        which may be empty if no catalogue has been written yet.

    Raises:
        typer.Exit: Exit code ``2`` when the secure object cannot be parsed.
    """
    repo = catalogue_repository()
    try:
        return repo.load()
    except TransactionError as exc:
        _logger.warning("load_catalogue_or_empty: catalogue load failed", exc_info=True)
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
        _logger.warning("load_catalogue_required: catalogue load failed", exc_info=True)
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    if len(catalogue) == 0 and not repo.exists():
        typer.echo(
            tr("cli.financial.catalogue.errors.not_found"),
            err=True,
        )
        raise typer.Exit(code=2)
    return catalogue
