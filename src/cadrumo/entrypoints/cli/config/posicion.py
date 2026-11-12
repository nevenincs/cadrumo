"""Operator-facing door for the ``inversiones_posicion`` savings position records.

Four verbs are mounted under ``config profile posicion``: ``add``, ``edit``,
``list`` and ``remove``. Each reads the complete profile facts once, parses the leaves
typed and submits a registered row operation bound to the exact revision and content
digest it read. The operation judges the row; the door only parses.

A row states what identifies an account, a term deposit or a securities account:
its kind, its payer, the state its income comes from, the share the taxpayer holds
and since when, and the operator's own identifier for it. It never states an
amount; income comes from the ledger and the withholding from the payer's record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from cadrumo_client.commands.output import activate_subcommand_output_language

from ....core.external_constants import OutputLanguage
from ....domain.contribuyente.posicion_facts import POSICION_SECTION
from ..common import emit_envelope
from ..config_posicion_payloads import (
    ConfigProfilePosicionAddResult,
    ConfigProfilePosicionEditResult,
    ConfigProfilePosicionListResult,
    ConfigProfilePosicionRemoveResult,
    ProfilePosicionRowPayload,
)
from .rental_row_doors import (
    checked_values,
    count_after,
    distinct_clears,
    merged_row,
    open_rental_door,
    require_row,
    settled_row,
    stored_rows,
    submit_add,
    submit_edit,
    submit_remove,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


def _row_line(row: int, facts: Mapping[str, str]) -> str:
    return "\t".join(
        (
            f"posicion[{row}]",
            f"tipo={facts.get('tipo', '-')}",
            f"pagador_nombre={facts.get('pagador_nombre', '-')}",
            f"pais_origen={facts.get('pais_origen', '-')}",
            f"porcentaje_titularidad={facts.get('porcentaje_titularidad', '-')}",
            f"identificador={facts.get('identificador', '-')}",
        )
    )


def posicion_add(
    ctx: typer.Context,
    value: list[str] | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Add one position from ``--value LEAF=VALUE`` facts; it is stored only if it coheres as a record."""
    activate_subcommand_output_language(ctx, output_language)
    state = open_rental_door(ctx)
    row, current = submit_add(state, POSICION_SECTION, checked_values(state, POSICION_SECTION, value))
    stored = settled_row(POSICION_SECTION, row, current)
    emit_envelope(
        ctx,
        command="config.profile.posicion.add",
        result=ConfigProfilePosicionAddResult(
            profile=state.pointer.label, row=row, total=count_after(POSICION_SECTION, current)
        ),
        lines=(f"profile\t{state.pointer.label}", f"row\t{row}", _row_line(row, stored)),
    )


def posicion_edit(
    ctx: typer.Context,
    row: int,
    value: list[str] | None = None,
    clear: list[str] | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Replace the named facts of position ``row`` and clear the named leaves; the rest stand."""
    activate_subcommand_output_language(ctx, output_language)
    clears = distinct_clears(clear)
    state = open_rental_door(ctx)
    values = checked_values(state, POSICION_SECTION, value, clears)
    before = require_row(POSICION_SECTION, row, stored_rows(state, POSICION_SECTION))
    after = merged_row(before, values, clears)
    changed, current = submit_edit(state, POSICION_SECTION, row, before, after)
    after = settled_row(POSICION_SECTION, row, current)
    emit_envelope(
        ctx,
        command="config.profile.posicion.edit",
        result=ConfigProfilePosicionEditResult(profile=state.pointer.label, row=row, changed=changed),
        lines=(f"profile\t{state.pointer.label}", f"changed\t{str(changed).lower()}", _row_line(row, after)),
    )


def posicion_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """List the stored positions by row key, each with the facts it states as stored."""
    activate_subcommand_output_language(ctx, output_language)
    state = open_rental_door(ctx)
    rows = stored_rows(state, POSICION_SECTION)
    emit_envelope(
        ctx,
        command="config.profile.posicion.list",
        result=ConfigProfilePosicionListResult(
            profile=state.pointer.label,
            total=len(rows),
            posiciones=[ProfilePosicionRowPayload(row=row, facts=facts) for row, facts in rows.items()],
        ),
        lines=(f"profile\t{state.pointer.label}", f"total\t{len(rows)}", *(_row_line(r, f) for r, f in rows.items())),
    )


def posicion_remove(
    ctx: typer.Context,
    row: int,
    output_language: OutputLanguage | None = None,
) -> None:
    """Remove position ``row``. The row key is never reused."""
    activate_subcommand_output_language(ctx, output_language)
    state = open_rental_door(ctx)
    require_row(POSICION_SECTION, row, stored_rows(state, POSICION_SECTION))
    current = submit_remove(state, POSICION_SECTION, row)
    total = count_after(POSICION_SECTION, current)
    emit_envelope(
        ctx,
        command="config.profile.posicion.remove",
        result=ConfigProfilePosicionRemoveResult(profile=state.pointer.label, removed_row=row, total=total),
        lines=(f"profile\t{state.pointer.label}", f"removed_row\t{row}", f"total\t{total}"),
    )


__all__ = ["posicion_add", "posicion_edit", "posicion_list", "posicion_remove"]
