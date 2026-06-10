"""Regression test for ``--output-language`` parity across the CLI surface.

contract closes the parity gap identified in personas R7-C, Ines D3+D6, and
Joan R7-002: ``auth clear``, ``auth providers``, ``auth configure``,
``config profile show``, ``modelo work calculate``, ``modelo work verify``,
and ``modelo work file`` must each accept ``--output-language`` so the
operator can request a specific output language on any user-facing verb.

Test strategy:
- Invoke ``--help`` for each target command via the real CLI runner.
- Assert the help text includes ``--output-language`` and the language
  choice list, confirming the option is registered.
- A failing assertion on first landing surfaces any still-missed surface
  and keeps that command enrolled in parity coverage.

No active profile is required: ``--help`` is intercepted by Click/Typer
before any state access.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_sessionless_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# The option string we assert must appear in every target command's help.
_OPTION_FLAG = "--output-language"
_CHOICE_LIST = f"[{'|'.join(SUPPORTED_OUTPUT_LANGUAGES)}]"


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path) -> Iterator[None]:
    with isolated_sessionless_storage_root(tmp_path=tmp_path):
        yield


def _assert_output_language_registered(args: list[str]) -> None:
    """Invoke ``--help`` for *args* and assert ``--output-language`` is present."""
    help_args = [*args, "--help"]
    result = invoke_cached_cli(help_args)
    assert result.exit_code == 0, f"`{' '.join(help_args)}` exited {result.exit_code}:\n{result.output}"
    assert _OPTION_FLAG in result.output, (
        f"`{' '.join(args)}` help does not include `{_OPTION_FLAG}`.\nHelp output:\n{result.output}"
    )
    assert _CHOICE_LIST in result.output, (
        f"`{' '.join(args)}` help does not constrain `{_OPTION_FLAG}` to {_CHOICE_LIST}.\nHelp output:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# contract — auth subcommands
# ---------------------------------------------------------------------------


def test_auth_clear_accepts_output_language() -> None:
    """``aeat config auth clear`` must accept ``--output-language`` (contract)."""
    _assert_output_language_registered(["config", "auth", "clear"])


def test_auth_providers_accepts_output_language() -> None:
    """``aeat config auth providers`` must accept ``--output-language`` (contract)."""
    _assert_output_language_registered(["config", "auth", "providers"])


def test_auth_configure_accepts_output_language() -> None:
    """``aeat config auth configure`` must accept ``--output-language`` (contract)."""
    _assert_output_language_registered(["config", "auth", "configure"])


# ---------------------------------------------------------------------------
# contract — config profile subcommands
# ---------------------------------------------------------------------------


def test_config_profile_show_accepts_output_language() -> None:
    """``aeat config profile show`` must accept ``--output-language`` (contract)."""
    _assert_output_language_registered(["config", "profile", "show"])


# ---------------------------------------------------------------------------
# contract — modelo work subcommands
# ---------------------------------------------------------------------------


def test_work_calculate_accepts_output_language() -> None:
    """``aeat app modelo work calculate`` must accept ``--output-language`` (contract)."""
    _assert_output_language_registered(["app", "modelo", "work", "calculate"])


def test_work_verify_accepts_output_language() -> None:
    """``aeat app modelo work verify`` must accept ``--output-language`` (contract)."""
    _assert_output_language_registered(["app", "modelo", "work", "verify"])


def test_work_file_accepts_output_language() -> None:
    """``aeat app modelo work file`` must accept ``--output-language`` (contract)."""
    _assert_output_language_registered(["app", "modelo", "work", "file"])


# ---------------------------------------------------------------------------
# Commands confirmed to already have the flag (anti-regression guard)
# ---------------------------------------------------------------------------


def test_auth_status_retains_output_language() -> None:
    """``aeat config auth status`` had ``--output-language`` before contract; must keep it."""
    _assert_output_language_registered(["config", "auth", "status"])


def test_auth_login_retains_output_language() -> None:
    """``aeat config auth login`` had ``--output-language`` before contract; must keep it."""
    _assert_output_language_registered(["config", "auth", "login"])


def test_auth_test_retains_output_language() -> None:
    """``aeat config auth test`` had ``--output-language`` before contract; must keep it."""
    _assert_output_language_registered(["config", "auth", "test"])


# ---------------------------------------------------------------------------
# Modelo work read-only verbs.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "verb",
    ["list", "status", "history", "revisions", "revision", "runs"],
)
def test_work_read_only_verb_accepts_output_language(verb: str) -> None:
    """Every read-only `aeat app modelo work` verb must accept ``--output-language``.

    Closes the discovery3 #121 CLI completeness audit gap for the six
    work_ verbs that previously had no language flag (contract), pinning
    them under the parity regression gate (contract/contract broader sweep)."""
    _assert_output_language_registered(["app", "modelo", "work", verb])


# ---------------------------------------------------------------------------
# Config profile validate verb.
# ---------------------------------------------------------------------------


def test_config_profile_validate_accepts_output_language() -> None:
    """``aeat config profile validate`` accepts ``--output-language``."""
    _assert_output_language_registered(["config", "profile", "validate"])


# ---------------------------------------------------------------------------
# Full config profile verb tree parity sweep.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "verb",
    ["list", "delete", "duplicate", "rename", "export", "import", "logout", "status"],
)
def test_config_profile_verb_accepts_output_language(verb: str) -> None:
    """Every config-profile verb that previously
    lacked ``--output-language`` now accepts it for parity with the rest
    of the config noun-group."""
    _assert_output_language_registered(["config", "profile", verb])


def test_config_switch_accepts_output_language() -> None:
    """``aeat config switch`` (the profile-switch verb that replaced
    ``config unlock`` per the cli-operator-surface rename decision) accepts
    ``--output-language`` for parity with the rest of the config surface."""
    _assert_output_language_registered(["config", "switch"])


# ---------------------------------------------------------------------------
# Sub-noun-group parity sweep.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["config", "auth", "diagnostics", "list"],
        ["config", "auth", "diagnostics", "show"],
        ["config", "auth", "diagnostics", "report"],
        ["config", "auth", "apoderado", "scopes", "list"],
        ["config", "auth", "apoderado", "status"],
        ["config", "auth", "apoderado", "configure"],
        ["config", "auth", "apoderado", "clear"],
        ["config", "auth", "apoderado", "check"],
        ["config", "bucket", "history"],
        ["app", "ledger", "ratios", "list"],
        ["app", "ledger", "ratios", "set"],
        ["app", "ledger", "ratios", "unset"],
        ["app", "ledger", "ratios", "eligible"],
        ["app", "ledger", "ratios", "validate"],
    ],
)
def test_sub_noun_group_verb_accepts_output_language(argv: list[str]) -> None:
    """Every CLI sub-noun-group verb under
    auth_diagnostics, apoderado, bucket, and ledger ratios accepts
    ``--output-language`` for parity with the top-level config verbs."""
    _assert_output_language_registered(argv)
