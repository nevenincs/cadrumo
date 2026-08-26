"""CLI argument parsing helpers for Modelo 145 communication commands.

The helpers keep raw Typer values out of the application layer by converting
``--casilla`` assignments, period tokens, notes, and actor labels into the
strict backend create-command DTO.

See Also:
    :mod:`~entrypoints.cli._modelo_m145_cli`
        Typer command group that calls these parsing helpers.
    :class:`~application.modelo.M145CommunicationCreateCommand`
        Backend DTO produced by :func:`m145_create_command_from_cli`.
    :class:`~application.modelo.M145CommunicationPeriod`
        Closed period-token type accepted by the CLI option and backend DTO.
    :mod:`~entrypoints.cli._modelo_m145_rendering`
        Sibling output boundary that emits results after parsed commands run.
"""

from __future__ import annotations

from collections.abc import Callable

import typer

from ...application.modelo._m145_communication_records import (
    M145CommunicationCreateCommand,
)
from ...application.modelo.m145_communication_period import M145CommunicationPeriod
from ...core import CasillaId
from ...core.i18n import tr

type ParseCasillaOverride = Callable[[str], tuple[CasillaId, str]]


def m145_actor_from_cli(
    raw_actor: str | None,
    *,
    resolve_default_actor: Callable[[], str],
) -> str:
    """Return the operator label supplied at the CLI boundary."""
    if raw_actor is not None and raw_actor.strip():
        return raw_actor.strip()
    return resolve_default_actor()


def m145_field_values_from_cli(
    casilla_specs: list[str] | None,
    *,
    parse_casilla_override: ParseCasillaOverride,
) -> dict[CasillaId, str]:
    """Parse repeated ``--casilla ID=VALUE`` tokens for the backend service."""
    if not casilla_specs:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.m145.errors.casilla_required",
                default="Provide at least one --casilla ID=VALUE entry.",
            ),
        )
    values: dict[CasillaId, str] = {}
    for spec in casilla_specs:
        casilla_id, value = parse_casilla_override(spec)
        values[casilla_id] = value
    return values


def m145_create_command_from_cli(
    *,
    year: int,
    period: M145CommunicationPeriod,
    casilla_specs: list[str] | None,
    note: str | None,
    parse_casilla_override: ParseCasillaOverride,
) -> M145CommunicationCreateCommand:
    """Build the backend create-command DTO from raw Typer option values."""
    return M145CommunicationCreateCommand(
        communication_year=year,
        period_token=period,
        field_values=m145_field_values_from_cli(casilla_specs, parse_casilla_override=parse_casilla_override),
        note=note,
    )


__all__ = [
    "ParseCasillaOverride",
    "m145_actor_from_cli",
    "m145_create_command_from_cli",
    "m145_field_values_from_cli",
]
