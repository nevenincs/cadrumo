"""Shared immutable CommandSpec facts for ledger rule and ratios leaves."""

from __future__ import annotations

from typing import Final

from .command_spec import (
    DeferredTarget,
    InvocationSpec,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    TranslationKey,
    ValueContract,
)

_LEDGER_RULE_RATIO_LEAF_INVOCATION: Final[InvocationSpec] = InvocationSpec(
    invoke_without_command=False,
    no_args_is_help=False,
    context_parameter="ctx",
)
"""The common dispatch shape for every ledger rule and ratios leaf."""

_RULE_ACTOR_OPTION: Final[OptionSpec] = OptionSpec(
    name="actor",
    declarations=("--actor",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.ledger.rule.actor_help"),
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
"""The exact optional actor parameter shared by rule mutation leaves."""

_RATIOS_YEAR_OPTION: Final[OptionSpec] = OptionSpec(
    name="year",
    declarations=("--year",),
    value=ValueContract(DeferredTarget("builtins", "int")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.ledger.ratios.year_help"),
    metavar="YEAR",
    is_flag=False,
    flag_value=None,
    multiple=False,
    count=False,
    eager=False,
    constraint=ParameterConstraint(),
    show_default=True,
    hidden=False,
)
"""The exact optional year filter used by eligible, list, and set."""

_RATIOS_OUTPUT_LANGUAGE_OPTION: Final[OptionSpec] = OptionSpec(
    name="output_language",
    declarations=("--output-language", "--language"),
    value=ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.auth.output_language_help"),
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
"""The exact optional output-language parameter on every ratios leaf."""

__all__ = [
    "_LEDGER_RULE_RATIO_LEAF_INVOCATION",
    "_RATIOS_OUTPUT_LANGUAGE_OPTION",
    "_RATIOS_YEAR_OPTION",
    "_RULE_ACTOR_OPTION",
]
