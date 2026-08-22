"""``aeat app ledger participation`` — transaction participation audit surface.

Surfaces the inverse of the forward ``source_transaction_ids`` link: which
finalized modelo revisions, filings, and justificantes consumed a given ledger
transaction. ``participation <transaction-id>`` emits a typed
:class:`LedgerTransactionParticipationPayload`;
``participation rebuild`` calls
:func:`rebuild_participation_index` to regenerate the
derived :class:`TransactionRevisionParticipationIndex`.
Lookup ids are resolved against a :class:`TransactionCatalogueRepository`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import typer
from typer.core import TyperGroup

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...application.ledger import get_transaction_participation
from ...core.i18n import tr
from ._command_policy import command_execution_policy
from ._common import _active_bucket_id_or_bad, _emit_envelope, _state, _tx_repo, emit_help_text
from ._ledger_execution_policies import LEDGER_COMPUTE_WRITE, LEDGER_READ

if TYPE_CHECKING:
    from ._ledger_payloads import LedgerTransactionParticipationEntryPayload

ResolveTransactionId = Callable[[TransactionCatalogueRepository, str], str]


def register_participation_commands(
    app: typer.Typer,
    *,
    resolve_transaction_id: ResolveTransactionId,
) -> None:
    """Register the ``participation`` subgroup under ``aeat app ledger``.

    The group callback handles ``participation <transaction-id>`` (the inverse
    audit lookup); the ``rebuild`` subcommand calls
    :func:`rebuild_participation_index`.
    ``resolve_transaction_id`` canonicalises a possibly-abbreviated id for the
    lookup verb.
    """
    participation = typer.Typer(
        name="participation",
        help=tr("Audit which finalized modelo revisions and filings consumed a ledger transaction."),
        invoke_without_command=True,
    )

    @participation.callback(invoke_without_command=True)
    @command_execution_policy(LEDGER_READ)
    def participation_lookup(
        ctx: typer.Context,
        transaction_id: str | None = typer.Argument(
            None,
            help=tr("Ledger transaction id whose finalized-revision participations to list."),
        ),
    ) -> None:
        """List finalized participations as a typed ledger participation payload."""
        if ctx.invoked_subcommand is not None:
            return
        if transaction_id is None:
            emit_help_text(ctx)
            raise typer.Exit(code=0)
        # ``invoke_without_command=True`` plus an optional positional makes Click
        # bind a bare subcommand token (e.g. ``rebuild``) to ``transaction_id``
        # instead of dispatching the subcommand. Detect a reserved subcommand
        # name and forward to it so ``participation rebuild`` works while
        # ``participation <id>`` keeps its documented lookup UX.
        if transaction_id in _reserved_subcommand_names(participation):
            command = typer.main.get_command(participation)
            if not isinstance(command, TyperGroup):
                raise typer.Exit(code=2)
            subcommand = command.get_command(typer.Context(command), transaction_id)
            if subcommand is None or subcommand.callback is None:
                raise typer.Exit(code=2)
            ctx.invoke(subcommand.callback)
            return
        _emit_participation_lookup(
            ctx,
            transaction_id=transaction_id,
            resolve_transaction_id=resolve_transaction_id,
        )

    _register_rebuild_command(participation)
    app.add_typer(participation, name="participation")


def _reserved_subcommand_names(participation: typer.Typer) -> frozenset[str]:
    """Return the names of subcommands registered under the ``participation`` group.

    The group callback's optional positional ``transaction_id`` would otherwise
    swallow a bare subcommand token (e.g. ``rebuild``); these names are reserved
    so the callback can forward them to their command instead of treating them
    as a transaction id.
    """
    names: set[str] = set()
    for info in participation.registered_commands:
        if info.name:
            names.add(info.name)
            continue
        callback_name = getattr(info.callback, "__name__", "") if info.callback is not None else ""
        if callback_name:
            names.add(callback_name)
    return frozenset(names)


def _emit_participation_lookup(
    ctx: typer.Context,
    *,
    transaction_id: str,
    resolve_transaction_id: ResolveTransactionId,
) -> None:
    """Read and emit one :class:`TransactionRevisionParticipationIndex`."""
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


def _register_rebuild_command(participation: typer.Typer) -> None:
    @participation.command("rebuild")
    @command_execution_policy(LEDGER_COMPUTE_WRITE)
    def participation_rebuild(ctx: typer.Context) -> None:
        """Run :func:`rebuild_participation_index` for the active bucket."""
        from ...application.modelo import rebuild_participation_index
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
                    "stale_removed_count": stats.stale_removed_count,
                },
            ),
            lines=[
                f"transaction_count\t{stats.transaction_count}",
                f"participation_count\t{stats.participation_count}",
                f"revision_count\t{stats.revision_count}",
                f"stale_removed_count\t{stats.stale_removed_count}",
            ],
        )


__all__ = ["register_participation_commands"]
