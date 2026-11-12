"""Operator-facing entry surface for the ``renta_family.ascendiente.*`` household facts.

Four flag verbs are mounted under ``config profile ascendiente``: ``add`` (append
one or more ascendants, or state that there are none), ``edit`` (replace or clear
named facts of one ascendant by 0-based index, keeping the rest), ``list`` (show the
stored ascendants and what the profile says about the group) and ``remove`` (drop one
ascendant by 0-based index).

Every verb submits the ``user-profile.ascendants`` operation the window uses. It
replaces the whole set against the exact revision and content digest the verb read,
so a profile that moved in between refuses the write instead of overwriting it.
Stating that there are none is the same replacement with no rows: the stored count of
zero is an answer, and a profile never asked stays ``unknown``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.output import activate_subcommand_output_language

from ....core.external_constants import OutputLanguage
from ..common import emit_envelope
from .profile_support import require_active_profile_pointer

if TYPE_CHECKING:
    from ....application.user_profile.ascendant_rows import ProfileAscendantRow
    from ..config_ascendiente_payloads import ProfileAscendientePayload


def _row_values(row: ProfileAscendantRow) -> dict[str, str]:
    return {fact.field_key: fact.value for fact in row.facts}


def _answer(values: dict[str, str], leaf: str) -> bool | None:
    """A stored yes-or-no leaf, ``None`` while the row does not state it."""
    stored = values.get(leaf)
    return None if stored is None else stored == "true"


def _row_lines(rows: tuple[ProfileAscendantRow, ...]) -> list[str]:
    lines: list[str] = []
    for index, row in enumerate(rows):
        values = _row_values(row)
        lines.append(
            "\t".join(
                (
                    f"ascendiente[{index}]",
                    f"nacimiento={values.get('birth_date', '-')}",
                    f"fallecimiento={values.get('fallecimiento', '-')}",
                    f"convivientes={values.get('convivientes', '-')}",
                    f"rentas={values.get('rentas_anuales', '-')}",
                    f"declaracion_propia={values.get('declaracion_propia', '-')}",
                    f"discapacidad={values.get('discapacidad', '-')}",
                    f"convivencia_mitad_periodo={values.get('convivencia_mitad_periodo', '-')}",
                    f"discapacidad_asistencia={values.get('discapacidad_asistencia', '-')}",
                    f"incapacidad_judicial={values.get('incapacidad_judicial', '-')}",
                    f"nif={values.get('nif', '-')}",
                    f"apellidos_nombre={values.get('apellidos_nombre', '-')}",
                )
            )
        )
    return lines


def _row_payloads(rows: tuple[ProfileAscendantRow, ...]) -> list[ProfileAscendientePayload]:
    from datetime import date
    from decimal import Decimal

    from ..config_ascendiente_payloads import ProfileAscendientePayload

    payloads: list[ProfileAscendientePayload] = []
    for index, row in enumerate(rows):
        values = _row_values(row)
        death = values.get("fallecimiento")
        cohabiting = values.get("convivientes")
        rentas = values.get("rentas_anuales")
        disability = values.get("discapacidad")
        payloads.append(
            ProfileAscendientePayload(
                index=index,
                nif=values.get("nif"),
                apellidos_nombre=values.get("apellidos_nombre"),
                birth_date=date.fromisoformat(values["birth_date"]),
                death_date=date.fromisoformat(death) if death is not None else None,
                convivientes=int(cohabiting) if cohabiting is not None else None,
                rentas_anuales=Decimal(rentas) if rentas is not None else None,
                declaracion_propia=_answer(values, "declaracion_propia"),
                discapacidad=int(disability) if disability is not None else None,
                convivencia_mitad_periodo=_answer(values, "convivencia_mitad_periodo"),
                discapacidad_asistencia=_answer(values, "discapacidad_asistencia"),
                incapacidad_judicial=_answer(values, "incapacidad_judicial"),
            )
        )
    return payloads


def ascendiente_add(
    ctx: typer.Context,
    ascendiente: list[str] | None = None,
    none: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """Append ``--ascendiente`` rows to the active profile, or state with ``--none`` that there are none.

    Each ``--ascendiente`` value is read into one row before anything is written; the
    operation then validates every leaf against the pinned authority. ``--none`` is
    refused next to a row and while the profile stores ascendants or states a count.
    """
    from uuid import UUID

    from cadrumo_client.commands.profile_binding import require_profile_client

    from ....application.user_profile.ascendant_rows import ASCENDANT_OBJECT_PATH
    from ..config_ascendiente_payloads import ConfigProfileAscendienteAddResult
    from .ascendiente_flag import parse_ascendiente_flag
    from .operation_ascendants import decode_ascendants, replace_ascendants
    from .operation_household import (
        household_group,
        read_household_baseline,
        require_group_open_to_none,
        require_rows_or_none,
    )
    from .profile_mutation import mutation_deadline

    activate_subcommand_output_language(ctx, output_language)
    new_rows = tuple(parse_ascendiente_flag(raw) for raw in ascendiente or ())
    require_rows_or_none(flag="--ascendiente", supplied=len(new_rows), none=none)
    pointer = require_active_profile_pointer()
    client = require_profile_client(ctx, expected_profile_id=UUID(str(pointer.bucket_id)))
    deadline = mutation_deadline()
    baseline = read_household_baseline(client, deadline=deadline)
    if none:
        require_group_open_to_none(household_group(baseline, group_key=ASCENDANT_OBJECT_PATH))
    existing = decode_ascendants(client, baseline)
    committed = replace_ascendants(client, baseline=baseline, ascendants=(*existing, *new_rows), deadline=deadline)
    result = ConfigProfileAscendienteAddResult(
        profile=pointer.label, added=len(new_rows), total=len(committed), none_declared=none
    )
    emit_envelope(
        ctx,
        command="config.profile.ascendiente.add",
        result=result,
        lines=(
            f"profile	{pointer.label}",
            f"added	{len(new_rows)}",
            f"total	{len(committed)}",
            *(("none_declared	true",) if none else ()),
            *_row_lines(committed),
        ),
    )


def ascendiente_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """List the stored ascendants and whether the profile states none, is incomplete or was never asked."""
    from time import monotonic
    from uuid import UUID

    from cadrumo_client.commands.profile_binding import require_profile_client

    from ....application.user_profile.ascendant_rows import ASCENDANT_OBJECT_PATH
    from ..config_ascendiente_payloads import ConfigProfileAscendienteListResult
    from .operation_ascendants import decode_ascendants
    from .operation_household import household_group, read_household_baseline

    activate_subcommand_output_language(ctx, output_language)
    pointer = require_active_profile_pointer()
    client = require_profile_client(ctx, expected_profile_id=UUID(str(pointer.bucket_id)))
    baseline = read_household_baseline(client, deadline=monotonic() + 60)
    rows = decode_ascendants(client, baseline)
    group = household_group(baseline, group_key=ASCENDANT_OBJECT_PATH)
    result = ConfigProfileAscendienteListResult(
        profile=pointer.label,
        total=len(rows),
        state=group.state,
        stated_count=group.stated_count,
        ascendientes=_row_payloads(rows),
    )
    emit_envelope(
        ctx,
        command="config.profile.ascendiente.list",
        result=result,
        lines=(
            f"profile	{pointer.label}",
            f"total	{len(rows)}",
            f"state	{group.state.value}",
            *_row_lines(rows),
        ),
    )


def ascendiente_edit(
    ctx: typer.Context,
    index: int,
    ascendiente: list[str] | None = None,
    clear: list[str] | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Replace the named facts of the ascendant at ``index`` and drop the ``--clear`` keys; the rest stand.

    The whole set is written back against the exact revision and content digest the verb
    read, with every other ascendant unchanged, so the operation judges the edited row as
    it judges an added one. An edit that changes nothing writes nothing.
    """
    from uuid import UUID

    from cadrumo_client.commands.profile_binding import require_profile_client

    from ....application.user_profile.ascendant_rows import ProfileAscendantFact, ProfileAscendantRow
    from ..config_ascendiente_payloads import ConfigProfileAscendienteEditResult
    from .ascendiente_flag import parse_ascendiente_edit
    from .operation_ascendants import decode_ascendants, replace_ascendants
    from .operation_household import read_household_baseline
    from .profile_mutation import mutation_deadline

    activate_subcommand_output_language(ctx, output_language)
    replaced, cleared = parse_ascendiente_edit(ascendiente, clear)
    pointer = require_active_profile_pointer()
    client = require_profile_client(ctx, expected_profile_id=UUID(str(pointer.bucket_id)))
    deadline = mutation_deadline()
    baseline = read_household_baseline(client, deadline=deadline)
    existing = decode_ascendants(client, baseline)
    if index < 0 or index >= len(existing):
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.ascendiente.index_out_of_range",
            context={"index": str(index), "total": str(len(existing))},
        )
    before = _row_values(existing[index])
    after = {**before, **replaced}
    for leaf in cleared:
        after.pop(leaf, None)
    changed = after != before
    committed = existing
    if changed:
        edited = ProfileAscendantRow(
            facts=tuple(ProfileAscendantFact(field_key=leaf, value=value) for leaf, value in after.items())
        )
        rows = tuple(edited if position == index else row for position, row in enumerate(existing))
        committed = replace_ascendants(client, baseline=baseline, ascendants=rows, deadline=deadline)
    result = ConfigProfileAscendienteEditResult(
        profile=pointer.label, index=index, changed=changed, total=len(committed)
    )
    emit_envelope(
        ctx,
        command="config.profile.ascendiente.edit",
        result=result,
        lines=(
            f"profile	{pointer.label}",
            f"changed	{str(changed).lower()}",
            *_row_lines(committed)[index : index + 1],
        ),
    )


def ascendiente_remove(
    ctx: typer.Context,
    index: int,
    output_language: OutputLanguage | None = None,
) -> None:
    """Remove the ascendant at ``index`` and re-index the remaining rows."""
    from uuid import UUID

    from cadrumo_client.commands.profile_binding import require_profile_client

    from ..config_ascendiente_payloads import ConfigProfileAscendienteRemoveResult
    from .operation_ascendants import decode_ascendants, replace_ascendants
    from .operation_household import read_household_baseline
    from .profile_mutation import mutation_deadline

    activate_subcommand_output_language(ctx, output_language)
    pointer = require_active_profile_pointer()
    client = require_profile_client(ctx, expected_profile_id=UUID(str(pointer.bucket_id)))
    deadline = mutation_deadline()
    baseline = read_household_baseline(client, deadline=deadline)
    existing = decode_ascendants(client, baseline)
    if index < 0 or index >= len(existing):
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.ascendiente.index_out_of_range",
            context={"index": str(index), "total": str(len(existing))},
        )
    remaining = tuple(row for position, row in enumerate(existing) if position != index)
    committed = replace_ascendants(client, baseline=baseline, ascendants=remaining, deadline=deadline)
    result = ConfigProfileAscendienteRemoveResult(profile=pointer.label, removed_index=index, total=len(committed))
    emit_envelope(
        ctx,
        command="config.profile.ascendiente.remove",
        result=result,
        lines=(
            f"profile	{pointer.label}",
            f"removed_index	{index}",
            f"total	{len(committed)}",
        ),
    )


__all__ = ["ascendiente_add", "ascendiente_edit", "ascendiente_list", "ascendiente_remove"]
