"""Authored CommandSpec declarations for the live iva wallet service."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ._app_live_command_spec_support import (
    _ENCRYPTED_LOCAL_READ_POLICY,
    _LEAF_INVOCATION,
    _METADATA_GROUP_INVOCATION,
    _METADATA_POLICY,
    _OPTIONAL_TAXPAYER_NIF_OPTION,
    _OUTPUT_ROOT_OPTION,
    _PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
    _REQUIRED_PERIOD_OPTION,
    _REQUIRED_YEAR_FROM_OPTION,
    _REQUIRED_YEAR_OPTION,
    _REQUIRED_YEAR_TO_OPTION,
    NO_RESULT_SCHEMA,
    _key,
)
from .command_spec import (
    CommandNodeKind,
    CommandSpec,
    CommandWriteRoute,
    DeferredTarget,
    ExecutionPolicySpec,
    LazyBinding,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
)

LIVE_IVA_WALLET_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_live_iva_wallet",
        parent_key="app_live",
        token="iva-wallet",
        kind=CommandNodeKind.GROUP,
        help_key=_key("cli.app.live.iva_wallet.app_help"),
        short_help_key=None,
        invocation=_METADATA_GROUP_INVOCATION,
        parameters=(),
        policy=_METADATA_POLICY,
        handler=None,
        result_schema=NO_RESULT_SCHEMA,
    ),
    CommandSpec(
        key="app_live_iva_wallet_pull",
        parent_key="app_live_iva_wallet",
        token="pull",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.iva_wallet.pull_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            _REQUIRED_YEAR_OPTION,
            _REQUIRED_PERIOD_OPTION,
            _OPTIONAL_TAXPAYER_NIF_OPTION,
        ),
        policy=_PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live", "iva_wallet_pull_cmd")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_iva_wallet_payloads", "IvaWalletPullResult"),
            identity="app.live.iva_wallet.pull",
        ),
    ),
    CommandSpec(
        key="app_live_iva_wallet_history",
        parent_key="app_live_iva_wallet",
        token="history",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.iva_wallet.history_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            OptionSpec(
                name="as_of_year",
                declarations=("--as-of-year",),
                value=ValueContract(DeferredTarget("builtins", "int")),
                default=ParameterDefault.value(None),
                help_key=_key("cli.app.live.iva_wallet.as_of_year_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=2000, maximum=2099),
            ),
        ),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live", "iva_wallet_history_cmd")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_iva_wallet_payloads", "IvaWalletHistoryResult"),
            identity="app.live.iva_wallet.history",
        ),
    ),
    CommandSpec(
        key="app_live_iva_wallet_pull_history",
        parent_key="app_live_iva_wallet",
        token="pull-history",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.iva_wallet.pull_history_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            _REQUIRED_YEAR_FROM_OPTION,
            _REQUIRED_YEAR_TO_OPTION,
            _OUTPUT_ROOT_OPTION,
        ),
        policy=_PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live", "iva_wallet_pull_history_cmd")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._app_live_iva_wallet_payloads", "IvaWalletCaptureHistoryResult"
            ),
            identity="app.live.iva_wallet.pull_history",
        ),
    ),
    CommandSpec(
        key="app_live_iva_wallet_pull_evidence",
        parent_key="app_live_iva_wallet",
        token="pull-evidence",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.iva_wallet.pull_evidence_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            _REQUIRED_YEAR_FROM_OPTION,
            _REQUIRED_YEAR_TO_OPTION,
            OptionSpec(
                name="target_year",
                declarations=("--target-year",),
                value=ValueContract(DeferredTarget("builtins", "int")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.year_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=2000, maximum=2099),
            ),
            OptionSpec(
                name="target_period",
                declarations=("--target-period",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.period_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
            _OPTIONAL_TAXPAYER_NIF_OPTION,
            _OUTPUT_ROOT_OPTION,
        ),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["browser", "encrypted-facts", "subprocess"]),
            side_effects=frozenset(["browser", "local-state", "network"]),
            performance="external-io",
            write_route=CommandWriteRoute.PROFILE_BOUND,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live", "iva_wallet_pull_evidence_cmd")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._app_live_iva_wallet_payloads", "IvaWalletPullEvidenceResult"
            ),
            identity="app.live.iva_wallet.pull_evidence",
        ),
    ),
)

__all__ = ["LIVE_IVA_WALLET_COMMAND_SPECS"]
