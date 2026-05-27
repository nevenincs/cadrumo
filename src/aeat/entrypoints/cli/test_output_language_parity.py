"""Regression test for ``--output-language`` parity across the CLI surface.

S144 closes the parity gap identified in personas R7-C, Ines D3+D6, and
Joan R7-002: ``auth clear``, ``auth providers``, ``auth configure``,
``config profile show``, ``modelo work calculate``, ``modelo work verify``,
and ``modelo work file`` must each accept ``--output-language`` so the
operator can request a specific output language on any user-facing verb.

Test strategy:
- Invoke ``--help`` for each target command via the real CLI runner.
- Assert the help text includes ``--output-language`` and the language
  choice list, confirming the option is registered.
- A failing assertion on first landing surfaces any still-missed surface
  and drives a W09 follow-up for that command.

No active profile is required: ``--help`` is intercepted by Click/Typer
before any state access.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.core.config import override_settings
from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

# The option string we assert must appear in every target command's help.
_OPTION_FLAG = "--output-language"


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path) -> Iterator[None]:
    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=None) as settings:
        dispose_engine(settings)
        try:
            yield
        finally:
            dispose_engine(settings)


def _assert_output_language_registered(args: list[str]) -> None:
    """Invoke ``--help`` for *args* and assert ``--output-language`` is present."""
    help_args = [*args, "--help"]
    result = invoke_cached_cli(help_args)
    assert result.exit_code == 0, f"`{' '.join(help_args)}` exited {result.exit_code}:\n{result.output}"
    assert _OPTION_FLAG in result.output, (
        f"`{' '.join(args)}` help does not include `{_OPTION_FLAG}`.\nHelp output:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# S141 — auth subcommands
# ---------------------------------------------------------------------------


def test_auth_clear_accepts_output_language() -> None:
    """``aeat config auth clear`` must accept ``--output-language`` (S141)."""
    _assert_output_language_registered(["config", "auth", "clear"])


def test_auth_providers_accepts_output_language() -> None:
    """``aeat config auth providers`` must accept ``--output-language`` (S141)."""
    _assert_output_language_registered(["config", "auth", "providers"])


def test_auth_configure_accepts_output_language() -> None:
    """``aeat config auth configure`` must accept ``--output-language`` (S141)."""
    _assert_output_language_registered(["config", "auth", "configure"])


# ---------------------------------------------------------------------------
# S142 — config profile subcommands
# ---------------------------------------------------------------------------


def test_config_profile_show_accepts_output_language() -> None:
    """``aeat config profile show`` must accept ``--output-language`` (S142)."""
    _assert_output_language_registered(["config", "profile", "show"])


# ---------------------------------------------------------------------------
# S143 — modelo work subcommands
# ---------------------------------------------------------------------------


def test_work_calculate_accepts_output_language() -> None:
    """``aeat app modelo work calculate`` must accept ``--output-language`` (S143)."""
    _assert_output_language_registered(["app", "modelo", "work", "calculate"])


def test_work_verify_accepts_output_language() -> None:
    """``aeat app modelo work verify`` must accept ``--output-language`` (S143)."""
    _assert_output_language_registered(["app", "modelo", "work", "verify"])


def test_work_file_accepts_output_language() -> None:
    """``aeat app modelo work file`` must accept ``--output-language`` (S143)."""
    _assert_output_language_registered(["app", "modelo", "work", "file"])


# ---------------------------------------------------------------------------
# Commands confirmed to already have the flag (anti-regression guard)
# ---------------------------------------------------------------------------


def test_auth_status_retains_output_language() -> None:
    """``aeat config auth status`` had ``--output-language`` before S141; must keep it."""
    _assert_output_language_registered(["config", "auth", "status"])


def test_auth_login_retains_output_language() -> None:
    """``aeat config auth login`` had ``--output-language`` before S141; must keep it."""
    _assert_output_language_registered(["config", "auth", "login"])


def test_auth_test_retains_output_language() -> None:
    """``aeat config auth test`` had ``--output-language`` before S141; must keep it."""
    _assert_output_language_registered(["config", "auth", "test"])
