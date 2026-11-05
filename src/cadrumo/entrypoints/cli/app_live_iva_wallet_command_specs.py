from __future__ import annotations

from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.shared_contracts import (
    DeferredTarget,
    LazyBinding,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
    translation_key,
)
from cadrumo_client.commands.spec import CommandSpec, ExecutionPolicySpec
from cadrumo_client.contracts.command_ports import (
    CommandNodeKind,
    CommandWriteRoute,
)

from ...core.filing_year import FOUR_DIGIT_YEAR_FIRST, FOUR_DIGIT_YEAR_LAST
from .app_live_command_spec_support import (
    ENCRYPTED_LOCAL_READ_POLICY,
    LEAF_INVOCATION,
    METADATA_GROUP_INVOCATION,
    METADATA_POLICY,
    NO_RESULT_SCHEMA,
    OPTIONAL_TAXPAYER_NIF_OPTION,
    OUTPUT_ROOT_OPTION,
    PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
    REQUIRED_PERIOD_OPTION,
    REQUIRED_YEAR_FROM_OPTION,
    REQUIRED_YEAR_OPTION,
    REQUIRED_YEAR_TO_OPTION,
)

LIVE_IVA_WALLET_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_live_iva_wallet",
        "app_live",
        "iva-wallet",
        kind=CommandNodeKind.GROUP,
        help_key=translation_key("cli.app.live.iva_wallet.app_help"),
        short_help_key=None,
        invocation=METADATA_GROUP_INVOCATION,
        parameters=(),
        policy=METADATA_POLICY,
        handler=None,
        result_schema=NO_RESULT_SCHEMA,
    ),
    CommandSpec(
        "app_live_iva_wallet_pull",
        "app_live_iva_wallet",
        "pull",
        kind=CommandNodeKind.LEAF,
        help_key=translation_key("cli.app.live.iva_wallet.pull_help"),
        short_help_key=None,
        invocation=LEAF_INVOCATION,
        parameters=(
            REQUIRED_YEAR_OPTION,
            REQUIRED_PERIOD_OPTION,
            OPTIONAL_TAXPAYER_NIF_OPTION,
        ),
        policy=PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
        handler=LazyBinding.available(DeferredTarget(".app_live_iva_commands", "iva_wallet_pull_cmd", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".app_live_iva_wallet_results", "IvaWalletPullResult", __package__),
            identity="app.live.iva_wallet.pull",
        ),
    ),
    CommandSpec(
        "app_live_iva_wallet_history",
        "app_live_iva_wallet",
        "history",
        kind=CommandNodeKind.LEAF,
        help_key=translation_key("cli.app.live.iva_wallet.history_help"),
        short_help_key=None,
        invocation=LEAF_INVOCATION,
        parameters=(
            OptionSpec(
                name="as_of_year",
                declarations=("--as-of-year",),
                value=ValueContract(DeferredTarget("builtins", "int")),
                default=ParameterDefault.value(None),
                help_key=translation_key("cli.app.live.iva_wallet.as_of_year_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=FOUR_DIGIT_YEAR_FIRST, maximum=FOUR_DIGIT_YEAR_LAST),
            ),
        ),
        policy=ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(DeferredTarget(".app_live_iva_commands", "iva_wallet_history_cmd", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".app_live_iva_wallet_results", "IvaWalletHistoryResult", __package__),
            identity="app.live.iva_wallet.history",
        ),
    ),
    CommandSpec(
        "app_live_iva_wallet_pull_history",
        "app_live_iva_wallet",
        "pull-history",
        kind=CommandNodeKind.LEAF,
        help_key=translation_key("cli.app.live.iva_wallet.pull_history_help"),
        short_help_key=None,
        invocation=LEAF_INVOCATION,
        parameters=(
            REQUIRED_YEAR_FROM_OPTION,
            REQUIRED_YEAR_TO_OPTION,
            OUTPUT_ROOT_OPTION,
        ),
        policy=PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
        handler=LazyBinding.available(
            DeferredTarget(".app_live_iva_commands", "iva_wallet_pull_history_cmd", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".app_live_iva_wallet_results", "IvaWalletCaptureHistoryResult", __package__),
            identity="app.live.iva_wallet.pull_history",
        ),
    ),
    CommandSpec(
        "app_live_iva_wallet_pull_evidence",
        "app_live_iva_wallet",
        "pull-evidence",
        kind=CommandNodeKind.LEAF,
        help_key=translation_key("cli.app.live.iva_wallet.pull_evidence_help"),
        short_help_key=None,
        invocation=LEAF_INVOCATION,
        parameters=(
            REQUIRED_YEAR_FROM_OPTION,
            REQUIRED_YEAR_TO_OPTION,
            OptionSpec(
                name="target_year",
                declarations=("--target-year",),
                value=ValueContract(DeferredTarget("builtins", "int")),
                default=ParameterDefault.required(),
                help_key=translation_key("cli.app.live.year_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=FOUR_DIGIT_YEAR_FIRST, maximum=FOUR_DIGIT_YEAR_LAST),
            ),
            OptionSpec(
                name="target_period",
                declarations=("--target-period",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=translation_key("cli.app.live.period_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
            OPTIONAL_TAXPAYER_NIF_OPTION,
            OUTPUT_ROOT_OPTION,
        ),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["aeat", "browser", "encrypted-facts", "subprocess"]),
            side_effects=frozenset(["browser", "local-state", "network"]),
            performance="external-io",
            write_route=CommandWriteRoute.PROFILE_BOUND,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=LazyBinding.available(
            DeferredTarget(".app_live_iva_commands", "iva_wallet_pull_evidence_cmd", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".app_live_iva_wallet_results", "IvaWalletPullEvidenceResult", __package__),
            identity="app.live.iva_wallet.pull_evidence",
        ),
    ),
)

__all__ = ["LIVE_IVA_WALLET_COMMAND_SPECS"]
"""Authored CommandSpec declarations for the live iva wallet service."""
"""Authored CommandSpec declarations for the live iva wallet service."""
