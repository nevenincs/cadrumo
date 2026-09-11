"""Authored CommandSpec declarations for the ledger ratios surface."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ._app_ledger_command_spec_policies import (
    _POLICY_4,
    _POLICY_5,
    _POLICY_6,
)
from ._app_ledger_rule_ratio_command_spec_support import (
    _LEDGER_RULE_RATIO_LEAF_INVOCATION,
    _RATIOS_OUTPUT_LANGUAGE_OPTION,
    _RATIOS_YEAR_OPTION,
)
from .command_spec import (
    ArgumentSpec,
    CommandNodeKind,
    CommandSpec,
    DeferredTarget,
    LazyBinding,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

LEDGER_RATIOS_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_ledger_ratios_eligible",
        parent_key="app_ledger_ratios",
        token="eligible",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.ratios.eligible_help"),
        short_help_key=None,
        invocation=_LEDGER_RULE_RATIO_LEAF_INVOCATION,
        parameters=(
            _RATIOS_YEAR_OPTION,
            _RATIOS_OUTPUT_LANGUAGE_OPTION,
        ),
        policy=_POLICY_6,
        handler=LazyBinding.available(DeferredTarget("._ledger_ratios_cli", "ratios_eligible", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("._ledger_ratios_payloads", "RatiosEligibleResult", __package__),
            identity="ledger.ratios.eligible",
        ),
    ),
    CommandSpec(
        key="app_ledger_ratios_list",
        parent_key="app_ledger_ratios",
        token="list",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.ratios.list_help"),
        short_help_key=None,
        invocation=_LEDGER_RULE_RATIO_LEAF_INVOCATION,
        parameters=(
            _RATIOS_YEAR_OPTION,
            _RATIOS_OUTPUT_LANGUAGE_OPTION,
        ),
        policy=_POLICY_5,
        handler=LazyBinding.available(DeferredTarget("._ledger_ratios_cli", "ratios_list", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("._ledger_ratios_payloads", "RatiosListResult", __package__),
            identity="ledger.ratios.list",
        ),
    ),
    CommandSpec(
        key="app_ledger_ratios_set",
        parent_key="app_ledger_ratios",
        token="set",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.ratios.set_help"),
        short_help_key=None,
        invocation=_LEDGER_RULE_RATIO_LEAF_INVOCATION,
        parameters=(
            _RATIOS_YEAR_OPTION,
            ArgumentSpec(
                name="category",
                value=ValueContract(
                    DeferredTarget("...domain.categories.spending_category", "SpendingCategory", __package__)
                ),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.ledger.ratios.category_help"),
                metavar=None,
                constraint=ParameterConstraint(),
                show_default=True,
                hidden=False,
            ),
            ArgumentSpec(
                name="ratio",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.ledger.ratios.ratio_help"),
                metavar=None,
                constraint=ParameterConstraint(),
                show_default=True,
                hidden=False,
            ),
            _RATIOS_OUTPUT_LANGUAGE_OPTION,
        ),
        policy=_POLICY_4,
        handler=LazyBinding.available(DeferredTarget("._ledger_ratios_cli", "ratios_set", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("._ledger_ratios_payloads", "RatiosSetResult", __package__),
            identity="ledger.ratios.set",
        ),
    ),
    CommandSpec(
        key="app_ledger_ratios_unset",
        parent_key="app_ledger_ratios",
        token="unset",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.ratios.unset_help"),
        short_help_key=None,
        invocation=_LEDGER_RULE_RATIO_LEAF_INVOCATION,
        parameters=(
            ArgumentSpec(
                name="category",
                value=ValueContract(
                    DeferredTarget("...domain.categories.spending_category", "SpendingCategory", __package__)
                ),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.ledger.ratios.unset_category_help"),
                metavar=None,
                constraint=ParameterConstraint(),
                show_default=True,
                hidden=False,
            ),
            _RATIOS_OUTPUT_LANGUAGE_OPTION,
        ),
        policy=_POLICY_4,
        handler=LazyBinding.available(DeferredTarget("._ledger_ratios_cli", "ratios_unset", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("._ledger_ratios_payloads", "RatiosUnsetResult", __package__),
            identity="ledger.ratios.unset",
        ),
    ),
    CommandSpec(
        key="app_ledger_ratios_validate",
        parent_key="app_ledger_ratios",
        token="validate",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.ratios.validate_help"),
        short_help_key=None,
        invocation=_LEDGER_RULE_RATIO_LEAF_INVOCATION,
        parameters=(_RATIOS_OUTPUT_LANGUAGE_OPTION,),
        policy=_POLICY_6,
        handler=LazyBinding.available(DeferredTarget("._ledger_ratios_cli", "ratios_validate", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("._ledger_ratios_payloads", "RatiosValidateResult", __package__),
            identity="ledger.ratios.validate",
        ),
    ),
)

__all__ = ["LEDGER_RATIOS_COMMAND_SPECS"]
