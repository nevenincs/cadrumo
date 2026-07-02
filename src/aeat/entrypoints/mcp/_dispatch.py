"""Map MCP tool calls to ``aeat`` CLI invocations.

Pure name and argv mapping: an MCP tool name round-trips to its registry command
key, and a command key plus operator-supplied arguments project onto the CLI argv
the server runs. The actual invocation lives in the server shell; this module is
deterministic and unit-tested.

The live serving path builds its argv from the command's per-verb input schema
via :func:`~entrypoints.mcp._input_schema.cli_argv_for` (named arguments in,
resolved CLI path out); :func:`tool_request_argv` remains the pure
``(command_key, cli_tokens) -> argv`` mapper the determinism-replay eval uses to
reconstruct a recorded raw-token call.
"""

from __future__ import annotations

from collections.abc import Iterable

_TOOL_PREFIX = "aeat_"
# Command keys that are group-callback / help emit surfaces, not operator-callable
# tools. They are excluded from the exposed tool set.
_NON_TOOL_KEYS: frozenset[str] = frozenset({"root.status", "root.app"})


def is_exposable_command(command_key: str) -> bool:
    """Return True when a registry command key should surface as an MCP tool."""
    return command_key not in _NON_TOOL_KEYS


def tool_name_for_command(command_key: str) -> str:
    """Render a registry command key as a namespaced MCP tool name.

    ``modelo.work.calculate`` becomes ``aeat_modelo_work_calculate``.
    """
    return _TOOL_PREFIX + command_key.replace(".", "_")


def command_key_for_tool(tool_name: str, *, command_keys: Iterable[str]) -> str | None:
    """Reverse a tool name to its registry command key.

    Segment-internal underscores (``iva_wallet``) make a naive ``_`` -> ``.``
    inverse ambiguous, so the reverse is resolved against the known command-key
    set: the unique key whose forward mapping equals ``tool_name``.
    """
    return next((key for key in command_keys if tool_name_for_command(key) == tool_name), None)


def _cli_path_tokens(command_key: str) -> list[str]:
    """Project a registry command key onto its CLI path tokens.

    ``config.*`` and ``app.live.*`` keys carry their own leading root segment;
    every other key is a child of ``app``.
    """
    tokens = command_key.split(".")
    if tokens[0] in {"config", "app"}:
        return tokens
    return ["app", *tokens]


def tool_request_argv(command_key: str, args: Iterable[str]) -> list[str]:
    """Build the CLI argv for a recorded raw-token tool call.

    ``--format json`` is a root option (it precedes the command path), so the
    machine envelope is always requested. The pre-resolved ``args`` tokens are
    appended after the command path. The live serving path instead builds its
    argv from the per-verb schema via
    :func:`~entrypoints.mcp._input_schema.cli_argv_for`; this mapper serves
    the determinism-replay eval, which records raw CLI-token calls.
    """
    return ["--format", "json", *_cli_path_tokens(command_key), *args]
