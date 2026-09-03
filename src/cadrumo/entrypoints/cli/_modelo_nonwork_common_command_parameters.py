"""Frozen parameter tuples shared by the non-work Modelo command specs."""

from __future__ import annotations

from typing import Final

from .command_spec import (
    DeferredTarget,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    TranslationKey,
    ValueContract,
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
