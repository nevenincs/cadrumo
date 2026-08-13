"""Tests for the Claude client session gate's tool-RESULT verification.

The live capture that motivated this gate connected, dispatched
``cadrumo_harness_load``, received the retired-aeat-state refusal as a tool
ERROR — and the session still recorded ``status="passed"`` because the gate
only checked connection + dispatch. That is the concealment shape
``no-silent-under-declaration`` forbids: a release-readiness row would have
baked a hidden failure. These tests drive the real verdict function with the
two synthesized log shapes: dispatched-and-errored refuses naming the tool
error, dispatched-and-succeeded passes and records the decisive excerpt.
"""

from __future__ import annotations

import json

import pytest

from ..smoke_plugin_install import _CLIENT_TOOL_NAME, _tool_result_verdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CONNECT_LINE = 'MCP server "plugin:cadrumo:cadrumo": Successfully connected\n'
_SESSION_OK = json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "connected"})


def _debug_log(result_fragment: str) -> str:
    return (
        _CONNECT_LINE
        + f"[DEBUG] executing tool={_CLIENT_TOOL_NAME} input={{}}\n"
        + result_fragment
        + "\n[DEBUG] session complete\n"
    )


def test_dispatched_and_errored_tool_call_fails_the_session() -> None:
    """The live shape: dispatched, then an MCP tool error — session must refuse."""
    debug_text = _debug_log(
        '[DEBUG] tool result: {"content":[{"type":"text","text":"the configured local storage root '
        'carries retired aeat-era state; refusing to serve"}],"isError": true}',
    )
    with pytest.raises(SystemExit) as excinfo:
        _tool_result_verdict(debug_text, _SESSION_OK)
    message = str(excinfo.value)
    assert "ERRORED" in message
    # The decisive excerpt is named so the refusal is diagnosable from the log.
    assert "retired aeat-era state" in message


def test_dispatched_and_succeeded_tool_call_passes_with_excerpt() -> None:
    """A genuinely successful call passes and the evidence gets the result excerpt."""
    debug_text = _debug_log(
        '[DEBUG] tool result: {"content":[{"type":"text","text":"harness loaded: 12 personas, '
        '34 skills"}],"isError": false}',
    )
    excerpt = _tool_result_verdict(debug_text, _SESSION_OK)
    assert f"tool={_CLIENT_TOOL_NAME}" in excerpt
    assert "harness loaded" in excerpt


def test_session_level_error_verdict_is_refused_even_without_debug_markers() -> None:
    """The -p json document's is_error is the fail-closed second layer."""
    debug_text = _debug_log("[DEBUG] tool result: (shape this parser has never seen)")
    session_stdout = json.dumps(
        {"type": "result", "subtype": "error_during_execution", "is_error": True, "result": "tool execution failed"},
    )
    with pytest.raises(SystemExit) as excinfo:
        _tool_result_verdict(debug_text, session_stdout)
    assert "is_error=true" in str(excinfo.value)


@pytest.mark.parametrize(
    "marker_fragment",
    (
        '"is_error": true',
        '"isError":true',
        "tool_use_error",
        "Error calling tool cadrumo_harness_load",
        "Tool call failed: upstream refusal",
    ),
)
def test_every_known_error_marker_shape_refuses(marker_fragment: str) -> None:
    """Each documented error-marker spelling independently fails the session."""
    with pytest.raises(SystemExit, match="ERRORED"):
        _tool_result_verdict(_debug_log(f"[DEBUG] {marker_fragment}"), _SESSION_OK)
