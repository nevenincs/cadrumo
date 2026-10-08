"""``aeat app ledger participation`` — transaction participation audit surface.

Surfaces the inverse of the forward ``source_transaction_ids`` link: which
finalized modelo revisions, filings, and justificantes consumed a given ledger
transaction. ``participation <transaction-id>`` emits a typed
:class:`LedgerTransactionParticipationPayload`;
``participation rebuild`` calls
:func:`rebuild_participation_index` to regenerate the
derived :class:`TransactionRevisionParticipationIndex`.
Lookup and rebuild execute inside the exact-profile runtime worker.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from .common import emit_envelope, emit_help_text
from .runtime_ledger_participation import read_ledger_participation_for_cli
from .runtime_ledger_participation_rebuild import rebuild_ledger_participation_for_cli

if TYPE_CHECKING:
    from ._ledger_payloads import LedgerTransactionParticipationEntryPayload


def participation_lookup(ctx: typer.Context, transaction_id: str | None = None) -> None:
    """List finalized participations as a typed ledger participation payload."""
    if ctx.invoked_subcommand is not None:
        return
    if transaction_id is None:
        emit_help_text(ctx)
        raise typer.Exit(code=0)
    if transaction_id == "rebuild":
        participation_rebuild(ctx)
        return
    _emit_participation_lookup(ctx, transaction_id=transaction_id)


def _emit_participation_lookup(
    ctx: typer.Context,
    *,
    transaction_id: str,
) -> None:
    """Read and emit one :class:`TransactionRevisionParticipationIndex`."""
    from ._ledger_payloads import (
        LedgerTransactionParticipationEntryPayload,
        LedgerTransactionParticipationPayload,
    )

    projection = read_ledger_participation_for_cli(ctx, transaction_id=transaction_id)
    resolved_id = projection.transaction_id
    entries = [
        LedgerTransactionParticipationEntryPayload.model_validate(
            {
                "calculation_revision_id": participation.calculation_revision_id,
                "work_unit_id": participation.work_unit_id,
                "modelo": participation.modelo,
                "filing_year": participation.filing_year,
                "period": participation.period.to_period(),
                "revision_state": participation.revision_state,
                "filing_record_id": participation.filing_record_id,
                "justificante_reference": participation.justificante_reference,
            },
        )
        for participation in projection.participations
    ]
    emit_envelope(
        ctx,
        command="ledger.participation",
        result=LedgerTransactionParticipationPayload.model_validate(
            {"transaction_id": resolved_id, "participations": entries},
        ),
        lines=_participation_lines(resolved_id, entries),
    )


def _participation_lines(
    transaction_id: str,
    entries: list[LedgerTransactionParticipationEntryPayload],
) -> list[str]:
    lines = [f"transaction_id\t{transaction_id}"]
    for entry in entries:
        lines.append(
            "\t".join(
                (
                    "participation",
                    entry.modelo,
                    str(entry.filing_year),
                    entry.period.registry_token,
                    entry.revision_state,
                    entry.calculation_revision_id,
                    entry.filing_record_id or "-",
                ),
            ),
        )
    return lines


def participation_rebuild(ctx: typer.Context) -> None:
    """Run :func:`rebuild_participation_index` for the active bucket."""
    from ._ledger_payloads import LedgerParticipationRebuildResult

    stats = rebuild_ledger_participation_for_cli(ctx)
    emit_envelope(
        ctx,
        command="ledger.participation.rebuild",
        result=LedgerParticipationRebuildResult.model_validate(
            {
                "transaction_count": stats.transaction_count,
                "participation_count": stats.participation_count,
                "revision_count": stats.revision_count,
                "stale_removed_count": stats.stale_removed_count,
            }
        ),
        lines=[
            f"transaction_count\t{stats.transaction_count}",
            f"participation_count\t{stats.participation_count}",
            f"revision_count\t{stats.revision_count}",
            f"stale_removed_count\t{stats.stale_removed_count}",
        ],
    )


__all__ = ["participation_lookup", "participation_rebuild"]
