from __future__ import annotations

import pytest
from typer.testing import CliRunner

from .._command_runtime import build_command_app, command_schema_targets, resolve_deferred_target
from .._command_spec import (
    CommandSpec,
    CommandSpecGraph,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SEEN: list[tuple[object, str]] = []
_POLICY = ExecutionPolicySpec(
    capabilities=frozenset({"state-free"}),
    side_effects=frozenset({"none"}),
    performance="metadata",
    write_route="none",
)
_NO_SCHEMA = ResultSchemaSpec(SchemaState.NOT_SUPPORTED)


def public_behavior(ctx: object, *, name: str) -> None:
    _SEEN.append((ctx, name))


def _graph() -> CommandSpecGraph:
    root = CommandSpec(
        key="root",
        parent_key=None,
        token="aeat",  # noqa: S106 - CLI operator token, not a credential
        kind="root",
        help_key=TranslationKey("cli.root.app_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=_POLICY,
        handler=None,
        result_schema=_NO_SCHEMA,
    )
    leaf = CommandSpec(
        key="greet",
        parent_key="root",
        token="greet",  # noqa: S106 - CLI operator token, not a credential
        kind="leaf",
        help_key=TranslationKey("cli.root.version_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="name",
                declarations=("--name",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.root.language_help"),
            ),
        ),
        policy=_POLICY,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli.tests.test_command_runtime", "public_behavior")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("builtins", "dict"),
            identity="root.greet",
        ),
    )
    return CommandSpecGraph((root, leaf))


def test_runtime_compiles_help_and_invokes_public_behavior_from_specs() -> None:
    _SEEN.clear()
    result = CliRunner().invoke(build_command_app(_graph()), ["greet", "--name", "Ada"])

    assert result.exit_code == 0, result.output
    assert len(_SEEN) == 1
    assert _SEEN[0][1] == "Ada"


def test_runtime_schema_projection_and_public_target_boundary() -> None:
    assert command_schema_targets(_graph()) == (("root.greet", DeferredTarget("builtins", "dict")),)
    assert resolve_deferred_target(DeferredTarget("builtins", "str")) is str
