"""``aeat app ledger participation`` — transaction participation audit surface.

Surfaces the inverse of the forward ``source_transaction_ids`` link: which
finalized modelo revisions, filings, and justificantes consumed a given ledger
transaction. The read verb takes a transaction id and emits a typed
:class:`LedgerTransactionParticipationPayload`; the ``rebuild`` subcommand
regenerates the derived index from the authoritative revision catalogue.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import typer

from ...application.modelo import rebuild_participation_index
from ._common import _active_bucket_id_or_bad, _emit_envelope, _state

ResolveTransactionId = Callable[[Any, str], str]


def register_participation_commands(
    app: typer.Typer,
    *,
    resolve_transaction_id: ResolveTransactionId,
) -> None:
    """Register the ``participation`` subgroup under ``aeat app ledger``.

    ``resolve_transaction_id`` resolves a possibly-abbreviated transaction id to
    its canonical form for the read verb (wired in a later step); the ``rebuild``
    subcommand does not consume it.
    """
    participation = typer.Typer(
        name="participation",
        help="Audit which finalized modelo revisions and filings consumed a ledger transaction.",
        no_args_is_help=True,
    )
    _register_rebuild_command(participation)
    app.add_typer(participation, name="participation")


def _register_rebuild_command(participation: typer.Typer) -> None:
    @participation.command("rebuild")
    def participation_rebuild(ctx: typer.Context) -> None:
        """Rebuild the transaction participation index from the revision catalogue."""
        from ._ledger_payloads import LedgerParticipationRebuildResult

        bucket_id = _active_bucket_id_or_bad(_state())
        stats = rebuild_participation_index(bucket_id=bucket_id)
        _emit_envelope(
            ctx,
            command="ledger.participation.rebuild",
            result=LedgerParticipationRebuildResult.model_validate(
                {
                    "transaction_count": stats.transaction_count,
                    "participation_count": stats.participation_count,
                    "revision_count": stats.revision_count,
                },
            ),
            lines=[
                f"transaction_count\t{stats.transaction_count}",
                f"participation_count\t{stats.participation_count}",
                f"revision_count\t{stats.revision_count}",
            ],
        )


__all__ = ["register_participation_commands"]
