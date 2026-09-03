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

_TEXT_VALUE: Final[ValueContract] = ValueContract(DeferredTarget("builtins", "str"))
_FLAG_VALUE: Final[ValueContract] = ValueContract(DeferredTarget("builtins", "bool"))


def _optional_text_option(name: str, declarations: tuple[str, ...], help_key: str) -> OptionSpec:
    """Declare an optional free-text option defaulting to absent.

    The most repeated parameter contract in the ledger command surface. Only the
    identity fields vary between uses; every other field is fixed by this
    contract, which is why they are supplied here rather than at each call.

    Args:
        name: The parameter's identifier.
        declarations: The CLI tokens that introduce it, aliases included.
        help_key: The translation key for its help text.

    Returns:
        The immutable option declaration.
    """
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=_TEXT_VALUE,
        default=ParameterDefault.value(None),
        help_key=TranslationKey(help_key),
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


def _required_text_option(name: str, declarations: tuple[str, ...], help_key: str) -> OptionSpec:
    """Declare a mandatory free-text option.

    Distinct from :func:`_optional_text_option` in exactly one field, and the
    distinction is a contract rather than a detail: a required parameter has no
    absent state, so its handler never sees ``None``.

    Args:
        name: The parameter's identifier.
        declarations: The CLI tokens that introduce it, aliases included.
        help_key: The translation key for its help text.

    Returns:
        The immutable option declaration.
    """
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=_TEXT_VALUE,
        default=ParameterDefault.required(),
        help_key=TranslationKey(help_key),
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


def _blank_default_text_option(name: str, declarations: tuple[str, ...], help_key: str) -> OptionSpec:
    """Declare a free-text option defaulting to the empty string.

    The empty default is not the same state as :func:`_optional_text_option`'s
    absent default: this parameter always carries a string, so a handler cannot
    distinguish "not supplied" from "supplied empty". Kept separate for that
    reason rather than folded in behind a default argument.

    Args:
        name: The parameter's identifier.
        declarations: The CLI tokens that introduce it, aliases included.
        help_key: The translation key for its help text.

    Returns:
        The immutable option declaration.
    """
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=_TEXT_VALUE,
        default=ParameterDefault.value(""),
        help_key=TranslationKey(help_key),
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


def _repeatable_text_option(name: str, declarations: tuple[str, ...], help_key: str) -> OptionSpec:
    """Declare a repeatable free-text option collecting into a tuple.

    Args:
        name: The parameter's identifier.
        declarations: The CLI tokens that introduce it, aliases included.
        help_key: The translation key for its help text.

    Returns:
        The immutable option declaration.
    """
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=_TEXT_VALUE,
        default=ParameterDefault.value(()),
        help_key=TranslationKey(help_key),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=True,
        count=False,
        eager=False,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


def _boolean_flag_option(name: str, declarations: tuple[str, ...], help_key: str) -> OptionSpec:
    """Declare a boolean flag that is false unless the token is present.

    Args:
        name: The parameter's identifier.
        declarations: The CLI tokens that introduce it, aliases included.
        help_key: The translation key for its help text.

    Returns:
        The immutable option declaration.
    """
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=_FLAG_VALUE,
        default=ParameterDefault.value(False),
        help_key=TranslationKey(help_key),
        metavar=None,
        is_flag=True,
        flag_value=True,
        multiple=False,
        count=False,
        eager=False,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


def _required_text_argument(name: str, help_key: str) -> ArgumentSpec:
    """Declare a mandatory positional free-text argument.

    Args:
        name: The parameter's identifier.
        help_key: The translation key for its help text.

    Returns:
        The immutable argument declaration.
    """
    return ArgumentSpec(
        name=name,
        value=_TEXT_VALUE,
        default=ParameterDefault.required(),
        help_key=TranslationKey(help_key),
        metavar=None,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


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
    "_blank_default_text_option",
    "_boolean_flag_option",
    "_optional_text_option",
    "_repeatable_text_option",
    "_required_text_argument",
    "_required_text_option",
]
