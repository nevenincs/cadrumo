"""Frozen parameter tuples shared by the non-work Modelo command specs."""

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

_TEXT_VALUE: Final[ValueContract] = ValueContract(DeferredTarget("builtins", "str"))
_WHOLE_NUMBER_VALUE: Final[ValueContract] = ValueContract(DeferredTarget("builtins", "int"))
_FLAG_VALUE: Final[ValueContract] = ValueContract(DeferredTarget("builtins", "bool"))


def _optional_text_option(name: str, declarations: tuple[str, ...], help_key: str) -> OptionSpec:
    """Declare an optional free-text option defaulting to absent.

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
        multiple=False,
        is_flag=False,
        flag_value=None,
        constraint=ParameterConstraint(),
    )


def _required_text_option(name: str, declarations: tuple[str, ...], help_key: str) -> OptionSpec:
    """Declare a mandatory free-text option.

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
        multiple=False,
        is_flag=False,
        flag_value=None,
        constraint=ParameterConstraint(),
    )


def _optional_whole_number_option(name: str, declarations: tuple[str, ...], help_key: str) -> OptionSpec:
    """Declare an optional whole-number option defaulting to absent.

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
        value=_WHOLE_NUMBER_VALUE,
        default=ParameterDefault.value(None),
        help_key=TranslationKey(help_key),
        multiple=False,
        is_flag=False,
        flag_value=None,
        constraint=ParameterConstraint(),
    )


def _required_whole_number_option(name: str, declarations: tuple[str, ...], help_key: str) -> OptionSpec:
    """Declare a mandatory whole-number option.

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
        value=_WHOLE_NUMBER_VALUE,
        default=ParameterDefault.required(),
        help_key=TranslationKey(help_key),
        multiple=False,
        is_flag=False,
        flag_value=None,
        constraint=ParameterConstraint(),
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
        multiple=True,
        is_flag=False,
        flag_value=None,
        constraint=ParameterConstraint(),
    )


def _boolean_flag_option(name: str, declarations: tuple[str, ...], help_key: str) -> OptionSpec:
    """Declare a boolean option that is false unless supplied.

    Note this family declares ``is_flag=False``: the token takes an explicit
    boolean value rather than being a bare presence switch, which is the
    non-work Modelo surface's own convention and differs from the ledger's.

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
        multiple=False,
        is_flag=False,
        flag_value=None,
        constraint=ParameterConstraint(),
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
    )


def _optional_text_argument(name: str, help_key: str) -> ArgumentSpec:
    """Declare an optional positional free-text argument defaulting to absent.

    Args:
        name: The parameter's identifier.
        help_key: The translation key for its help text.

    Returns:
        The immutable argument declaration.
    """
    return ArgumentSpec(
        name=name,
        value=_TEXT_VALUE,
        default=ParameterDefault.value(None),
        help_key=TranslationKey(help_key),
    )


_MODELO_OPTION: Final[OptionSpec] = OptionSpec(
    name="modelo",
    declarations=("--modelo",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.modelo.work.modelo_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(),
)

_YEAR_OPTION: Final[OptionSpec] = OptionSpec(
    name="year",
    declarations=("--year",),
    value=ValueContract(DeferredTarget("builtins", "int")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.modelo.work.year_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(),
)

_PERIOD_OPTION: Final[OptionSpec] = OptionSpec(
    name="period",
    declarations=("--period",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.modelo.work.period_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(),
)

_REGISTRY_REVISION_OPTION: Final[OptionSpec] = OptionSpec(
    name="registry_revision",
    declarations=("--registry-revision",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.modelo.work.revision_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(),
)

_BUCKET_ID_OPTION: Final[OptionSpec] = OptionSpec(
    name="bucket_id",
    declarations=("--bucket-id",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.modelo.work.bucket_id_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(),
)

_SELECT_OPTION: Final[OptionSpec] = OptionSpec(
    name="select",
    declarations=("--select",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value("current"),
    help_key=TranslationKey("cli.app.modelo.work.revision_selector_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(),
)

CALCULATION_REVISION_SELECTOR_OPTIONS: Final[tuple[OptionSpec, ...]] = (
    _MODELO_OPTION,
    _YEAR_OPTION,
    _PERIOD_OPTION,
    _REGISTRY_REVISION_OPTION,
    _BUCKET_ID_OPTION,
    _SELECT_OPTION,
)

_REFUND_ELECTION_OPTION: Final[OptionSpec] = OptionSpec(
    name="refund_election",
    declarations=("--refund-election",),
    value=ValueContract(DeferredTarget("cadrumo.core.refund_election", "RefundElection")),
    default=ParameterDefault.value("compensar"),
    help_key=TranslationKey("cli.app.modelo.work.refund_election_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(),
)

_PAYMENT_ELECTION_OPTION: Final[OptionSpec] = OptionSpec(
    name="payment_election",
    declarations=("--payment-election",),
    value=ValueContract(DeferredTarget("cadrumo.core.payment_election", "PaymentElection")),
    default=ParameterDefault.value("ingreso"),
    help_key=TranslationKey("cli.app.modelo.work.payment_election_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(),
)

_PRIOR_DOMICILIATION_ELECTION_OPTION: Final[OptionSpec] = OptionSpec(
    name="prior_domiciliation_election",
    declarations=("--prior-domiciliation-election",),
    value=ValueContract(DeferredTarget("cadrumo.core.prior_domiciliation_election", "PriorDomiciliationElection")),
    default=ParameterDefault.value("keep"),
    help_key=TranslationKey("cli.app.modelo.work.prior_domiciliation_election_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(),
)

FILING_ELECTION_OPTIONS: Final[tuple[OptionSpec, ...]] = (
    _REFUND_ELECTION_OPTION,
    _PAYMENT_ELECTION_OPTION,
    _PRIOR_DOMICILIATION_ELECTION_OPTION,
)

__all__ = ["CALCULATION_REVISION_SELECTOR_OPTIONS", "FILING_ELECTION_OPTIONS"]
