"""Immutable construction contracts shared by ledger command-spec fragments."""

from __future__ import annotations

from typing import Final

from cadrumo_client.commands.parameters import ArgumentSpec, OptionSpec
from cadrumo_client.commands.shared_contracts import (
    FLAG_VALUE,
    NON_BLANK_CONSTRAINT,
    TEXT_VALUE,
    DeferredTarget,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from cadrumo_client.commands.spec import InvocationSpec

from ...application.ledger.operator_input_contracts import OperatorInputContract

GROUP_INVOCATION: Final[InvocationSpec] = InvocationSpec(
    invoke_without_command=False,
    no_args_is_help=True,
    context_parameter=None,
)
LEAF_INVOCATION: Final[InvocationSpec] = InvocationSpec(
    invoke_without_command=False,
    no_args_is_help=False,
    context_parameter="ctx",
)
NO_RESULT_SCHEMA: Final[ResultSchemaSpec] = ResultSchemaSpec(SchemaState.NOT_SUPPORTED)


def irpf_category_option(help_key: str) -> OptionSpec:
    """Declare the optional ``--irpf-category`` token, resolved against the published taxonomy."""
    return OptionSpec(
        name="irpf_category",
        declarations=("--irpf-category",),
        value=ValueContract(
            DeferredTarget("builtins", "str"),
            click_type=DeferredTarget(".common", "IRPF_CATEGORY_CHOICE", __package__),
        ),
        default=ParameterDefault.value(None),
        help_key=TranslationKey(help_key),
    )


def optional_text_option(
    name: str, declarations: tuple[str, ...], help_key: str, *, non_blank: bool = False
) -> OptionSpec:
    """Declare an optional free-text option defaulting to absent.

    The most repeated parameter contract in the ledger command surface. Only the
    identity fields vary between uses; every other field is fixed by this
    contract, which is why they are supplied here rather than at each call.

    Args:
        name: The parameter's identifier.
        declarations: The CLI tokens that introduce it, aliases included.
        help_key: The translation key for its help text.
        non_blank: Refuse an empty or blank value at the parse boundary, for an identifier.

    Returns:
        The immutable option declaration.
    """
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=TEXT_VALUE,
        default=ParameterDefault.value(None),
        help_key=TranslationKey(help_key),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=False,
        count=False,
        eager=False,
        constraint=NON_BLANK_CONSTRAINT if non_blank else ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


def required_text_option(
    name: str, declarations: tuple[str, ...], help_key: str, *, non_blank: bool = False
) -> OptionSpec:
    """Declare a mandatory free-text option.

    Distinct from :func:`optional_text_option` in exactly one field, and the
    distinction is a contract rather than a detail: a required parameter has no
    absent state, so its handler never sees ``None``.

    Args:
        name: The parameter's identifier.
        declarations: The CLI tokens that introduce it, aliases included.
        help_key: The translation key for its help text.
        non_blank: Refuse an empty or blank value at the parse boundary, for an identifier.

    Returns:
        The immutable option declaration.
    """
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=TEXT_VALUE,
        default=ParameterDefault.required(),
        help_key=TranslationKey(help_key),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=False,
        count=False,
        eager=False,
        constraint=NON_BLANK_CONSTRAINT if non_blank else ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


def blank_default_text_option(name: str, declarations: tuple[str, ...], help_key: str) -> OptionSpec:
    """Declare a free-text option defaulting to the empty string.

    The empty default is not the same state as :func:`optional_text_option`'s
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
        value=TEXT_VALUE,
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


def repeatable_text_option(
    name: str, declarations: tuple[str, ...], help_key: str, *, non_blank: bool = False
) -> OptionSpec:
    """Declare a repeatable free-text option collecting into a tuple.

    Args:
        name: The parameter's identifier.
        declarations: The CLI tokens that introduce it, aliases included.
        help_key: The translation key for its help text.
        non_blank: Refuse an empty or blank value at the parse boundary, for an identifier.

    Returns:
        The immutable option declaration.
    """
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=TEXT_VALUE,
        default=ParameterDefault.value(()),
        help_key=TranslationKey(help_key),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=True,
        count=False,
        eager=False,
        constraint=NON_BLANK_CONSTRAINT if non_blank else ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


def boolean_flag_option(name: str, declarations: tuple[str, ...], help_key: str) -> OptionSpec:
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
        value=FLAG_VALUE,
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


def required_text_argument(name: str, help_key: str, *, non_blank: bool = False) -> ArgumentSpec:
    """Declare a mandatory positional free-text argument.

    Args:
        name: The parameter's identifier.
        help_key: The translation key for its help text.
        non_blank: Refuse an empty or blank value at the parse boundary, for an identifier.

    Returns:
        The immutable argument declaration.
    """
    return ArgumentSpec(
        name=name,
        value=TEXT_VALUE,
        default=ParameterDefault.required(),
        help_key=TranslationKey(help_key),
        metavar=None,
        constraint=NON_BLANK_CONSTRAINT if non_blank else ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


def optional_text_argument(name: str, help_key: str, *, non_blank: bool = False) -> ArgumentSpec:
    """Declare an optional positional free-text argument defaulting to absent."""
    return ArgumentSpec(
        name=name,
        value=TEXT_VALUE,
        default=ParameterDefault.value(None),
        help_key=TranslationKey(help_key),
        metavar=None,
        constraint=NON_BLANK_CONSTRAINT if non_blank else ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


def option_from_application_contract(contract: OperatorInputContract, help_key: str | None) -> OptionSpec:
    """Project an application-owned operator input into CLI presentation metadata."""
    return OptionSpec(
        name=contract.name,
        declarations=contract.tokens,
        value=ValueContract(DeferredTarget(contract.value_module, contract.value_name, __package__)),
        default=ParameterDefault.required() if contract.required else ParameterDefault.value(None),
        help_key=TranslationKey(help_key) if help_key is not None else None,
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


EVIDENCE_TRANSACTION_ID_ARGUMENT: Final[ArgumentSpec] = ArgumentSpec(
    name="transaction_id",
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.app.ledger.evidence.pull_id_help"),
    metavar=None,
    constraint=NON_BLANK_CONSTRAINT,
    show_default=True,
    hidden=False,
)
EVIDENCE_ACTOR_OPTION: Final[OptionSpec] = OptionSpec(
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
LEDGER_ACTOR_OPTION: Final[OptionSpec] = OptionSpec(
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
LEDGER_ADD_CATEGORY_ID_OPTION: Final[OptionSpec] = OptionSpec(
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

LEDGER_USAGE_RATIO_ID_OPTION: Final[OptionSpec] = OptionSpec(
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

ARCHIVE_REASON_OPTION: Final[OptionSpec] = OptionSpec(
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

MERGE_REASON_OPTION: Final[OptionSpec] = OptionSpec(
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
OPTIONAL_PERIOD_OPTION: Final[OptionSpec] = OptionSpec(
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
OPTIONAL_YEAR_OPTION: Final[OptionSpec] = OptionSpec(
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
    "ARCHIVE_REASON_OPTION",
    "EVIDENCE_ACTOR_OPTION",
    "EVIDENCE_TRANSACTION_ID_ARGUMENT",
    "GROUP_INVOCATION",
    "LEAF_INVOCATION",
    "LEDGER_ACTOR_OPTION",
    "LEDGER_ADD_CATEGORY_ID_OPTION",
    "LEDGER_USAGE_RATIO_ID_OPTION",
    "MERGE_REASON_OPTION",
    "NO_RESULT_SCHEMA",
    "OPTIONAL_PERIOD_OPTION",
    "OPTIONAL_YEAR_OPTION",
    "blank_default_text_option",
    "boolean_flag_option",
    "option_from_application_contract",
    "optional_text_argument",
    "optional_text_option",
    "repeatable_text_option",
    "required_text_argument",
    "required_text_option",
]
