"""Operator-facing door for the ``renta_arrendamiento`` lease records.

Five verbs are mounted under ``config profile arrendamiento``: ``add``, ``edit``,
``list``, ``end`` and ``remove``. A lease names one property by its row key and
states the facts fixed when the contract was signed, which decide the tier of the
art. 23.2 LIRPF reduction. The tier itself is never entered: it is derived.

``end`` states the last day of a lease; the lease and its facts stay in the profile.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from cadrumo_client.commands.output import activate_subcommand_output_language

from ....core.external_constants import OutputLanguage
from ....domain.contribuyente.inmueble_facts import ARRENDAMIENTO_SECTION
from ..common import emit_envelope
from ..config_rental_payloads import (
    ConfigProfileArrendamientoAddResult,
    ConfigProfileArrendamientoEditResult,
    ConfigProfileArrendamientoEndResult,
    ConfigProfileArrendamientoListResult,
    ConfigProfileArrendamientoRemoveResult,
    ProfileRentalRowPayload,
)
from .rental_row_doors import (
    RentalDoorState,
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
            f"arrendamiento[{row}]",
            f"inmueble={facts.get('inmueble', '-')}",
            f"contrato={facts.get('fecha_contrato', '-')}",
            f"inicio={facts.get('fecha_inicio', '-')}",
            f"fin={facts.get('fecha_fin', '-')}",
        )
    )


def _edit(
    ctx: typer.Context, row: int, values: list[str] | None, clear: list[str] | None
) -> tuple[RentalDoorState, bool, dict[str, str]]:
    clears = distinct_clears(clear)
    state = open_rental_door(ctx)
    changes = checked_values(state, ARRENDAMIENTO_SECTION, values, clears)
    before = require_row(ARRENDAMIENTO_SECTION, row, stored_rows(state, ARRENDAMIENTO_SECTION))
    after = merged_row(before, changes, clears)
    changed, current = submit_edit(state, ARRENDAMIENTO_SECTION, row, before, after)
    after = settled_row(ARRENDAMIENTO_SECTION, row, current)
    return state, changed, after


def arrendamiento_add(
    ctx: typer.Context,
    value: list[str] | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Add one lease from ``--value LEAF=VALUE`` facts; the property it names must exist."""
    activate_subcommand_output_language(ctx, output_language)
    state = open_rental_door(ctx)
    row, current = submit_add(state, ARRENDAMIENTO_SECTION, checked_values(state, ARRENDAMIENTO_SECTION, value))
    stored = settled_row(ARRENDAMIENTO_SECTION, row, current)
    emit_envelope(
        ctx,
        command="config.profile.arrendamiento.add",
        result=ConfigProfileArrendamientoAddResult(
            profile=state.pointer.label, row=row, total=count_after(ARRENDAMIENTO_SECTION, current)
        ),
        lines=(f"profile\t{state.pointer.label}", f"row\t{row}", _row_line(row, stored)),
    )


def arrendamiento_edit(
    ctx: typer.Context,
    row: int,
    value: list[str] | None = None,
    clear: list[str] | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Replace the named facts of lease ``row`` and clear the named leaves; the rest stand."""
    activate_subcommand_output_language(ctx, output_language)
    state, changed, after = _edit(ctx, row, value, clear)
    emit_envelope(
        ctx,
        command="config.profile.arrendamiento.edit",
        result=ConfigProfileArrendamientoEditResult(profile=state.pointer.label, row=row, changed=changed),
        lines=(f"profile\t{state.pointer.label}", f"changed\t{str(changed).lower()}", _row_line(row, after)),
    )


def arrendamiento_end(
    ctx: typer.Context,
    row: int,
    fecha: str,
    output_language: OutputLanguage | None = None,
) -> None:
    """State that lease ``row`` ends on ``fecha`` (YYYY-MM-DD, not before it started)."""
    activate_subcommand_output_language(ctx, output_language)
    state, changed, after = _edit(ctx, row, [f"fecha_fin={fecha}"], None)
    emit_envelope(
        ctx,
        command="config.profile.arrendamiento.end",
        result=ConfigProfileArrendamientoEndResult(
            profile=state.pointer.label, row=row, fecha_fin=after["fecha_fin"], changed=changed
        ),
        lines=(f"profile\t{state.pointer.label}", f"changed\t{str(changed).lower()}", _row_line(row, after)),
    )


def arrendamiento_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """List the stored leases by row key, each with the facts it states as stored."""
    activate_subcommand_output_language(ctx, output_language)
    state = open_rental_door(ctx)
    rows = stored_rows(state, ARRENDAMIENTO_SECTION)
    emit_envelope(
        ctx,
        command="config.profile.arrendamiento.list",
        result=ConfigProfileArrendamientoListResult(
            profile=state.pointer.label,
            total=len(rows),
            arrendamientos=[ProfileRentalRowPayload(row=row, facts=facts) for row, facts in rows.items()],
        ),
        lines=(f"profile\t{state.pointer.label}", f"total\t{len(rows)}", *(_row_line(r, f) for r, f in rows.items())),
    )


def arrendamiento_remove(
    ctx: typer.Context,
    row: int,
    output_language: OutputLanguage | None = None,
) -> None:
    """Remove lease ``row``. The row key is never reused."""
    activate_subcommand_output_language(ctx, output_language)
    state = open_rental_door(ctx)
    require_row(ARRENDAMIENTO_SECTION, row, stored_rows(state, ARRENDAMIENTO_SECTION))
    current = submit_remove(state, ARRENDAMIENTO_SECTION, row)
    total = count_after(ARRENDAMIENTO_SECTION, current)
    emit_envelope(
        ctx,
        command="config.profile.arrendamiento.remove",
        result=ConfigProfileArrendamientoRemoveResult(profile=state.pointer.label, removed_row=row, total=total),
        lines=(f"profile\t{state.pointer.label}", f"removed_row\t{row}", f"total\t{total}"),
    )


__all__ = [
    "arrendamiento_add",
    "arrendamiento_edit",
    "arrendamiento_end",
    "arrendamiento_list",
    "arrendamiento_remove",
]
