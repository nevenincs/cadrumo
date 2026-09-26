"""Dispatch refuses every command whose policy declares a live AEAT write.

Live AEAT submission is permanently forbidden. A ``live_write`` declaration is
therefore a description the MCP surface can classify, never a permission: the
runtime compiler's dispatch seam raises the access gate's typed refusal before
preflight or the handler runs, and the process boundary renders it as that
registered error.

The synthetic graph runs through the real runtime compiler and the real
terminal error contract. Preflight does not stop the planted leaf on its own:
without the dispatch refusal its handler runs and exits 0.
"""

from __future__ import annotations

from typing import Final

import pytest
from typer.testing import CliRunner

from cadrumo.application.operator_surface.command_ports import CommandNodeKind, CommandWriteRoute

from ....core.access_gate.errors import LiveSubmitForbiddenError
from ....core.errors.error_codes import get_error_exit_code, get_registered_error_code, resolve_error_message
from .._command_runtime import build_command_app
from ..command_spec import (
    CommandSpec,
    CommandSpecGraph,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RAN: list[str] = []
_HELP: Final = TranslationKey("cli.root.version_help")
_NO_SCHEMA: Final = ResultSchemaSpec(SchemaState.NOT_SUPPORTED)
_STATE_FREE: Final = ExecutionPolicySpec(
    capabilities=frozenset({"state-free"}),
    side_effects=frozenset({"none"}),
    performance="metadata",
    write_route=CommandWriteRoute.NONE,
)
_LIVE_WRITE: Final = ExecutionPolicySpec(
    capabilities=frozenset({"browser"}),
    side_effects=frozenset({"browser"}),
    performance="external-io",
    write_route=CommandWriteRoute.NONE,
    live_write=True,
)


def record_live_submit(ctx: object) -> None:
    """Record that the planted live-write handler ran."""
    del ctx
    _RAN.append("live-submit")


def record_local_read(ctx: object) -> None:
    """Record that the ordinary sibling handler ran."""
    del ctx
    _RAN.append("local-read")


def _leaf(token: str, handler: str, policy: ExecutionPolicySpec) -> CommandSpec:
    return CommandSpec(
        token.replace("-", "_"),
        "root",
        token,
        kind=CommandNodeKind.LEAF,
        help_key=_HELP,
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=policy,
        handler=LazyBinding.available(
            DeferredTarget(".test_command_runtime_live_write_refusal", handler, __package__),
        ),
        result_schema=_NO_SCHEMA,
    )


def _graph() -> CommandSpecGraph:
    root = CommandSpec(
        "root",
        None,
        "aeat",
        kind=CommandNodeKind.ROOT,
        help_key=TranslationKey("cli.root.app_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=_STATE_FREE,
        handler=None,
        result_schema=_NO_SCHEMA,
    )
    return CommandSpecGraph(
        (
            root,
            _leaf("live-submit", "record_live_submit", _LIVE_WRITE),
            _leaf("local-read", "record_local_read", _STATE_FREE),
        ),
    )


def test_a_declared_live_write_command_is_refused_and_its_handler_never_runs() -> None:
    _RAN.clear()

    result = CliRunner().invoke(build_command_app(_graph()), ["live-submit"])

    refusal = LiveSubmitForbiddenError()
    code = get_registered_error_code(refusal)
    assert code.code == "LOCKED_ACCESS_GATE_LIVE_SUBMIT_FORBIDDEN"
    assert result.exit_code == get_error_exit_code(code.category), result.output
    assert resolve_error_message(refusal) in result.stderr
    assert _RAN == []


def test_a_sibling_without_live_write_still_runs() -> None:
    _RAN.clear()

    result = CliRunner().invoke(build_command_app(_graph()), ["local-read"])

    assert result.exit_code == 0, result.output
    assert _RAN == ["local-read"]
