"""Canonical reusable parameter records for ledger inventory command specs."""

from __future__ import annotations

from typing import Final

from .command_spec import (
    ArgumentSpec,
    DeferredTarget,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    TranslationKey,
    ValueContract,
)

INVENTORY_ACTIVIDAD_ID_ARGUMENT: Final[ArgumentSpec] = ArgumentSpec(
    name="actividad_id",
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.app.ledger.inventory.actividad_id_help"),
    metavar=None,
    constraint=ParameterConstraint(),
    show_default=True,
    hidden=False,
)

INVENTORY_ACTIVIDAD_ID_OPTION: Final[OptionSpec] = OptionSpec(
    name="actividad_id",
    declarations=("--actividad-id",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.app.ledger.inventory.actividad_id_help"),
    metavar=None,
    is_flag=False,
    flag_value=None,
    multiple=False,
    count=False,
    eager=False,
    constraint=ParameterConstraint(),
    show_default=True,
    hidden=False,
)

INVENTORY_YEAR_OPTION: Final[OptionSpec] = OptionSpec(
    name="year",
    declarations=("--year",),
    value=ValueContract(DeferredTarget("builtins", "int")),
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.app.ledger.inventory.year_help"),
    metavar=None,
    is_flag=False,
    flag_value=None,
    multiple=False,
    count=False,
    eager=False,
    constraint=ParameterConstraint(),
    show_default=True,
    hidden=False,
)

__all__ = [
    "INVENTORY_ACTIVIDAD_ID_ARGUMENT",
    "INVENTORY_ACTIVIDAD_ID_OPTION",
    "INVENTORY_YEAR_OPTION",
]
