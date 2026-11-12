"""Import-light authority for the savings position door under ``config profile``."""

from __future__ import annotations

from cadrumo_client.commands.spec import CommandSpec

from .record_family_command_specs import record_family_specs

POSICION_COMMAND_SPECS: tuple[CommandSpec, ...] = record_family_specs(
    "posicion", "Posicion", payloads="..config_posicion_payloads"
)

__all__ = ["POSICION_COMMAND_SPECS"]
