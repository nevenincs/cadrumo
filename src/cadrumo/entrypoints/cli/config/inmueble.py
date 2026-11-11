"""Operator-facing door for the ``renta_inmueble`` property records.

Four verbs are mounted under ``config profile inmueble``: ``add``, ``edit``,
``list`` and ``remove``. Each reads the complete profile facts once and submits a
registered row operation bound to the exact revision and content digest it read.

A row states identification and structural facts only: where the property is, who
holds it and in what right, how it was acquired, its dated cadastral values, the
uses other than letting and one optional accessory property. It never states an
annual total; amounts come from the ledger. A property that a lease still names
cannot be removed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from cadrumo_client.commands.output import activate_subcommand_output_language

from ....application.user_profile.rental_records import canonical_inmueble_values, require_inmueble_removable
from ....core.external_constants import OutputLanguage
from ....domain.contribuyente.inmueble_facts import INMUEBLE_SECTION, arrendamientos_from_facts
from ..common import emit_envelope
from ..config_rental_payloads import (
    ConfigProfileInmuebleAddResult,
    ConfigProfileInmuebleEditResult,
    ConfigProfileInmuebleListResult,
    ConfigProfileInmuebleRemoveResult,
    ProfileRentalRowPayload,
)
from .rental_row_doors import (
    checked_values,
    count_after,
    distinct_clears,
    merged_row,
    open_rental_door,
    require_row,
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
            f"inmueble[{row}]",
            f"situacion={facts.get('situacion', '-')}",
            f"referencia_catastral={facts.get('referencia_catastral', '-')}",
            f"titularidad={facts.get('titularidad_regimen', '-')}",
            f"direccion={facts.get('direccion', '-')}",
        )
    )


def inmueble_add(
    ctx: typer.Context,
    value: list[str] | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Add one property from ``--value LEAF=VALUE`` facts; it is stored only if it coheres as a record."""
    activate_subcommand_output_language(ctx, output_language)
    state = open_rental_door(ctx)
    stored = canonical_inmueble_values(checked_values(state, INMUEBLE_SECTION, value))
    row, current = submit_add(state, INMUEBLE_SECTION, stored)
    emit_envelope(
        ctx,
        command="config.profile.inmueble.add",
        result=ConfigProfileInmuebleAddResult(
            profile=state.pointer.label, row=row, total=count_after(INMUEBLE_SECTION, current)
        ),
        lines=(f"profile\t{state.pointer.label}", f"row\t{row}", _row_line(row, stored)),
    )


def inmueble_edit(
    ctx: typer.Context,
    row: int,
    value: list[str] | None = None,
    clear: list[str] | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Replace the named facts of property ``row`` and clear the named leaves; the rest stand."""
    activate_subcommand_output_language(ctx, output_language)
    clears = distinct_clears(clear)
    state = open_rental_door(ctx)
    values = checked_values(state, INMUEBLE_SECTION, value, clears)
    before = require_row(INMUEBLE_SECTION, row, stored_rows(state, INMUEBLE_SECTION))
    after = canonical_inmueble_values(merged_row(before, values, clears), clave=row)
    changed, _current = submit_edit(state, INMUEBLE_SECTION, row, before, after)
    emit_envelope(
        ctx,
        command="config.profile.inmueble.edit",
        result=ConfigProfileInmuebleEditResult(profile=state.pointer.label, row=row, changed=changed),
        lines=(f"profile\t{state.pointer.label}", f"changed\t{str(changed).lower()}", _row_line(row, after)),
    )


def inmueble_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """List the stored properties by row key, each with the facts it states as stored."""
    activate_subcommand_output_language(ctx, output_language)
    state = open_rental_door(ctx)
    rows = stored_rows(state, INMUEBLE_SECTION)
    emit_envelope(
        ctx,
        command="config.profile.inmueble.list",
        result=ConfigProfileInmuebleListResult(
            profile=state.pointer.label,
            total=len(rows),
            inmuebles=[ProfileRentalRowPayload(row=row, facts=facts) for row, facts in rows.items()],
        ),
        lines=(f"profile\t{state.pointer.label}", f"total\t{len(rows)}", *(_row_line(r, f) for r, f in rows.items())),
    )


def inmueble_remove(
    ctx: typer.Context,
    row: int,
    output_language: OutputLanguage | None = None,
) -> None:
    """Remove property ``row``; refused while a lease names it. The row key is never reused."""
    activate_subcommand_output_language(ctx, output_language)
    state = open_rental_door(ctx)
    require_row(INMUEBLE_SECTION, row, stored_rows(state, INMUEBLE_SECTION))
    require_inmueble_removable(row, arrendamientos_from_facts(state.path_values))
    current = submit_remove(state, INMUEBLE_SECTION, row)
    total = count_after(INMUEBLE_SECTION, current)
    emit_envelope(
        ctx,
        command="config.profile.inmueble.remove",
        result=ConfigProfileInmuebleRemoveResult(profile=state.pointer.label, removed_row=row, total=total),
        lines=(f"profile\t{state.pointer.label}", f"removed_row\t{row}", f"total\t{total}"),
    )


__all__ = ["inmueble_add", "inmueble_edit", "inmueble_list", "inmueble_remove"]
