"""Authored CommandSpec declarations for the live verify service."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from typing import Final

from ._app_live_command_spec_support import (
    _ENCRYPTED_LOCAL_READ_POLICY,
    _LEAF_INVOCATION,
    _METADATA_GROUP_INVOCATION,
    _METADATA_POLICY,
    _PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
    NO_RESULT_SCHEMA,
    _key,
)
from .command_spec import (
    ArgumentSpec,
    CommandNodeKind,
    CommandSpec,
    DeferredTarget,
    LazyBinding,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
)

_VERIFY_EXPECTED_OPTION: Final[OptionSpec] = OptionSpec(
    name="expected",
    declarations=("--expected",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=_key("cli.app.live.verify.expected_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(minimum=None, maximum=None),
)

LIVE_VERIFY_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_live_verify",
        parent_key="app_live",
        token="verify",
        kind=CommandNodeKind.GROUP,
        help_key=_key("cli.app.live.verify.app_help"),
        short_help_key=None,
        invocation=_METADATA_GROUP_INVOCATION,
        parameters=(),
        policy=_METADATA_POLICY,
        handler=None,
        result_schema=NO_RESULT_SCHEMA,
    ),
    CommandSpec(
        key="app_live_verify_list",
        parent_key="app_live_verify",
        token="list",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.verify.list_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            OptionSpec(
                name="surface",
                declarations=("--surface",),
                value=ValueContract(DeferredTarget("cadrumo.application.live.verify", "VerifySurface")),
                default=ParameterDefault.value(None),
                help_key=_key("cli.app.live.verify.surface_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
            OptionSpec(
                name="nif",
                declarations=("--nif",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=_key("cli.app.live.verify.nif_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live_verify_cli", "verify_list")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_verify_payloads", "VerifyListResult"),
            identity="app.live.verify.list",
        ),
    ),
    CommandSpec(
        key="app_live_verify_view",
        parent_key="app_live_verify",
        token="view",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.verify.view_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            ArgumentSpec(
                name="observation_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.verify.observation_id_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live_verify_cli", "verify_show")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_verify_payloads", "VerifyViewResult"),
            identity="app.live.verify.view",
        ),
    ),
    CommandSpec(
        key="app_live_verify_latest",
        parent_key="app_live_verify",
        token="latest",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.verify.latest_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            OptionSpec(
                name="surface",
                declarations=("--surface",),
                value=ValueContract(DeferredTarget("cadrumo.application.live.verify", "VerifySurface")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.verify.latest_surface_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
            OptionSpec(
                name="nif",
                declarations=("--nif",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.verify.latest_nif_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live_verify_cli", "verify_latest")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_verify_payloads", "VerifyLatestResult"),
            identity="app.live.verify.latest",
        ),
    ),
    CommandSpec(
        key="app_live_verify_nif_iva",
        parent_key="app_live_verify",
        token="nif-iva",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.verify.nif_iva_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            ArgumentSpec(
                name="nif",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.verify.nif_iva_arg_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
            _VERIFY_EXPECTED_OPTION,
        ),
        policy=_PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live_verify_cli", "verify_nif_iva")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_verify_payloads", "VerifyNifIvaResult"),
            identity="app.live.verify.nif_iva",
        ),
    ),
    CommandSpec(
        key="app_live_verify_tgvi",
        parent_key="app_live_verify",
        token="tgvi",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.verify.tgvi_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            ArgumentSpec(
                name="nif",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.verify.tgvi_arg_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
            _VERIFY_EXPECTED_OPTION,
        ),
        policy=_PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live_verify_cli", "verify_tgvi")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_verify_payloads", "VerifyTgviResult"),
            identity="app.live.verify.tgvi",
        ),
    ),
)

__all__ = ["LIVE_VERIFY_COMMAND_SPECS"]
