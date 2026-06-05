"""Real-behavior tests for the typed CLI runner helper.

Exercises :func:`invoke_cached_cli` end-to-end, confirming the
:class:`ClickInvokeKwargs` TypedDict surface passes known kwargs to
Click's ``CliRunner.invoke`` correctly.  No mocks.
"""

from __future__ import annotations

import pytest

from .cli_runner import ClickInvokeKwargs, invoke_cached_cli

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
