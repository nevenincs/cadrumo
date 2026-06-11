"""``aeat app ledger participation`` — transaction participation audit surface.

Surfaces the inverse of the forward ``source_transaction_ids`` link: which
finalized modelo revisions, filings, and justificantes consumed a given ledger
transaction. ``participation <transaction-id>`` emits a typed
:class:`LedgerTransactionParticipationPayload`; ``participation rebuild``
regenerates the derived index from the authoritative revision catalogue.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import typer

from ...application.ledger import get_transaction_participation
from ...application.modelo import rebuild_participation_index
from ._common import _active_bucket_id_or_bad, _emit_envelope, _state, _tx_repo

ResolveTransactionId = Callable[[Any, str], str]


def register_participation_commands(
    app: typer.Typer,
    *,
    resolve_transaction_id: ResolveTransactionId,
) -> None:
    """Register the ``participation`` subgroup under ``aeat app ledger``.

    The group callback handles ``participation <transaction-id>`` (the inverse
    audit lookup); the ``rebuild`` subcommand regenerates the index.
    ``resolve_transaction_id`` canonicalises a possibly-abbreviated id for the
    lookup verb.
    """
    participation = typer.Typer(
        name="participation",
        help="Audit which finalized modelo revisions and filings consumed a ledger transaction.",
        invoke_without_command=True,
    )

    @participation.callback(invoke_without_command=True)
    def participation_lookup(
        ctx: typer.Context,
        transaction_id: str | None = typer.Argument(
            None,
            help="Ledger transaction id whose finalized-revision participations to list.",
        ),
        include_borradores: bool = typer.Option(
            False,
            "--include-borradores",
            help="Reserved: include pending-draft (borrador) participations (deferred; no effect yet).",
        ),
    ) -> None:
        """List the finalized modelo revisions and filings that consumed a transaction."""
        if ctx.invoked_subcommand is not None:
            return
        if transaction_id is None:
            typer.echo(ctx.get_help())
            raise typer.Exit(code=0)
        _emit_participation_lookup(
            ctx,
            transaction_id=transaction_id,
            resolve_transaction_id=resolve_transaction_id,
        )

    _register_rebuild_command(participation)
    app.add_typer(participation, name="participation")


def _emit_participation_lookup(
    ctx: typer.Context,
    *,
    transaction_id: str,
    resolve_transaction_id: ResolveTransactionId,
) -> None:
    from ._ledger_payloads import (
        LedgerTransactionParticipationEntryPayload,
        LedgerTransactionParticipationPayload,
    )

    transaction_repository = _tx_repo(_state())
    resolved_id = resolve_transaction_id(transaction_repository, transaction_id)
    index = get_transaction_participation(
        transaction_id=resolved_id,
        bucket_id=transaction_repository.bucket_id,
    )
    entries = [
        LedgerTransactionParticipationEntryPayload.model_validate(
            {
                "calculation_revision_id": participation.calculation_revision_id,
                "work_unit_id": participation.work_unit_id,
                "modelo": str(participation.modelo),
                "filing_year": participation.filing_year,
                "period": participation.period,
                "revision_state": participation.revision_state,
                "filing_record_id": participation.filing_record_id,
                "justificante_reference": participation.justificante_reference,
            },
        )
        for participation in index.participations
    ]
    _emit_envelope(
        ctx,
        command="ledger.participation",
        result=LedgerTransactionParticipationPayload.model_validate(
            {"transaction_id": resolved_id, "participations": entries},
        ),
        lines=_participation_lines(resolved_id, entries),
    )


def _participation_lines(
    transaction_id: str,
    entries: list[Any],
) -> list[str]:
    lines = [f"transaction_id\t{transaction_id}"]
    for entry in entries:
        lines.append(
            "\t".join(
                (
                    "participation",
                    entry.modelo,
                    str(entry.filing_year),
                    entry.period,
                    entry.revision_state,
                    entry.calculation_revision_id,
                    entry.filing_record_id or "-",
                ),
            ),
        )
    return lines


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
