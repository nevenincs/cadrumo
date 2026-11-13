"""Import-light authority for the property and lease doors under ``config profile``."""

from __future__ import annotations

from cadrumo_client.commands.execution_policies import ENCRYPTED_WRITE
from cadrumo_client.commands.parameters import ArgumentSpec
from cadrumo_client.commands.shared_contracts import TEXT_VALUE, ParameterDefault, translation_key
from cadrumo_client.commands.spec import CommandSpec

from .record_family_command_specs import record_family_specs, record_leaf, record_row_argument

_PAYLOADS = "..config_rental_payloads"

_END = record_leaf(
    "arrendamiento",
    "end",
    payloads=_PAYLOADS,
    result="ConfigProfileArrendamientoEndResult",
    policy=ENCRYPTED_WRITE,
    parameters=(
        record_row_argument("arrendamiento"),
        ArgumentSpec(
            "fecha",
            TEXT_VALUE,
            ParameterDefault.required(),
            translation_key("cli.config.profile.arrendamiento.end_fecha_help"),
        ),
    ),
)

RENTAL_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    *record_family_specs("arrendamiento", "Arrendamiento", payloads=_PAYLOADS, extra=(_END,)),
    *record_family_specs("inmueble", "Inmueble", payloads=_PAYLOADS),
)

__all__ = ["RENTAL_COMMAND_SPECS"]
