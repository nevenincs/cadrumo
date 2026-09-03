"""Immutable construction contracts shared by ledger command-spec fragments."""

from __future__ import annotations

from typing import Final

from .command_spec import (
    ArgumentSpec,
    DeferredTarget,
    InvocationSpec,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

_GROUP_INVOCATION: Final[InvocationSpec] = InvocationSpec(
    invoke_without_command=False,
    no_args_is_help=True,
    context_parameter=None,
)
_LEAF_INVOCATION: Final[InvocationSpec] = InvocationSpec(
    invoke_without_command=False,
    no_args_is_help=False,
    context_parameter="ctx",
)
_NO_RESULT_SCHEMA: Final[ResultSchemaSpec] = ResultSchemaSpec(SchemaState.NOT_SUPPORTED)

_EVIDENCE_TRANSACTION_ID_ARGUMENT: Final[ArgumentSpec] = ArgumentSpec(
    name="transaction_id",
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.app.ledger.evidence.pull_id_help"),
    metavar=None,
    constraint=ParameterConstraint(),
    show_default=True,
    hidden=False,
)
_EVIDENCE_ACTOR_OPTION: Final[OptionSpec] = OptionSpec(
    name="actor",
    declarations=("--actor",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.ledger.evidence.pull_actor_help"),
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
_LEDGER_ACTOR_OPTION: Final[OptionSpec] = OptionSpec(
    name="actor",
    declarations=("--actor",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.ledger.add.actor_help"),
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
_LEDGER_ADD_CATEGORY_ID_OPTION: Final[OptionSpec] = OptionSpec(
    name="category_id",
    declarations=("--category-id",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.ledger.add.category_help"),
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
"""The exact optional category parameter shared by transaction add and allocation."""

_LEDGER_USAGE_RATIO_ID_OPTION: Final[OptionSpec] = OptionSpec(
    name="usage_ratio_id",
    declarations=("--usage-ratio-id",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.ledger.add.usage_ratio_help"),
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
"""The exact optional usage-ratio parameter shared by transaction add and allocation."""

_ARCHIVE_REASON_OPTION: Final[OptionSpec] = OptionSpec(
    name="reason",
    declarations=("--reason",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(""),
    help_key=TranslationKey("cli.ledger.archive.reason_help"),
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
"""The exact optional reason accepted by archive, restore, and stash."""

_MERGE_REASON_OPTION: Final[OptionSpec] = OptionSpec(
    name="reason",
    declarations=("--reason",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(""),
    help_key=TranslationKey("cli.ledger.merge.reason_help"),
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
_OPTIONAL_PERIOD_OPTION: Final[OptionSpec] = OptionSpec(
    name="period",
    declarations=("--period",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.ledger.export.period_help"),
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
_OPTIONAL_YEAR_OPTION: Final[OptionSpec] = OptionSpec(
    name="year",
    declarations=("--year",),
    value=ValueContract(DeferredTarget("builtins", "int")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.ledger.check.year_help"),
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
    "_ARCHIVE_REASON_OPTION",
    "_EVIDENCE_ACTOR_OPTION",
    "_EVIDENCE_TRANSACTION_ID_ARGUMENT",
    "_GROUP_INVOCATION",
    "_LEAF_INVOCATION",
    "_LEDGER_ACTOR_OPTION",
    "_LEDGER_ADD_CATEGORY_ID_OPTION",
    "_LEDGER_USAGE_RATIO_ID_OPTION",
    "_MERGE_REASON_OPTION",
    "_NO_RESULT_SCHEMA",
    "_OPTIONAL_PERIOD_OPTION",
    "_OPTIONAL_YEAR_OPTION",
]
