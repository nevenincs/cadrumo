"""Real-behavior tests for the typed CLI runner helper.

Exercises :func:`invoke_cached_cli` end-to-end, confirming the
:class:`ClickInvokeKwargs` TypedDict surface passes known kwargs to
Click's ``CliRunner.invoke`` correctly.  No mocks.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from .cli_runner import ClickInvokeKwargs, invoke_cached_cli, semantic_cli_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_invoke_cached_cli_returns_result_for_help_flag() -> None:
    """Invoking --help should succeed and emit usage text."""

    result = invoke_cached_cli(["--help"])
    assert result.exit_code == 0
    assert "config" in result.output


def test_invoke_cached_cli_accept_catch_exceptions_false() -> None:
    """catch_exceptions=False is a valid ClickInvokeKwargs member."""

    result = invoke_cached_cli(["--help"], catch_exceptions=False)
    assert result.exit_code == 0


def test_invoke_cached_cli_accepts_color_false() -> None:
    """color=False is a valid ClickInvokeKwargs member."""

    result = invoke_cached_cli(["--help"], color=False)
    assert result.exit_code == 0


def test_invoke_cached_cli_accepts_env_mapping() -> None:
    """env kwarg is accepted and forwarded as Mapping[str, str]."""

    result = invoke_cached_cli(["--help"], env={"AEAT_ENV": "test"})
    assert result.exit_code == 0


def test_semantic_output_preserves_option_tokens_under_github_actions() -> None:
    """GitHub's forced ANSI styling cannot split semantic option names."""
    source = """
from cadrumo.tests.cli_runner import invoke_cached_cli, semantic_cli_output
result = invoke_cached_cli(["app", "modelo", "work", "calculate", "--help"])
assert result.exit_code == 0, result.output
assert "\\x1b[" in result.output
assert "--output-language" in semantic_cli_output(result)
"""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and literal regression probe.
        [sys.executable, "-c", source],
        capture_output=True,
        check=False,
        env={**os.environ, "GITHUB_ACTIONS": "true"},
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_semantic_cli_text_removes_only_terminal_styling() -> None:
    """Split-stream capture removes ANSI while preserving semantic text."""

    styled = "\x1b[31m--provider\x1b[0m [auto|csv]\n"
    assert semantic_cli_text(styled) == "--provider [auto|csv]\n"


def test_click_invoke_kwargs_typed_dict_contains_expected_keys() -> None:
    """The TypedDict must declare the standard Click invoke surface keys.

    This confirms the TypedDict contract at a structural level: building
    a full kwargs dict with all declared keys must not raise a TypeError.
    """
    kwargs: ClickInvokeKwargs = {
        "env": {"K": "V"},
        "color": False,
        "catch_exceptions": True,
        "input": None,
    }
    # All keys are valid — no unknown-key error at runtime.
    result = invoke_cached_cli(["--help"], **kwargs)
    assert result.exit_code == 0
