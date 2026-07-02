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

from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_sessionless_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# The option string we assert must appear in every target command's help.
_OPTION_FLAG = "--output-language"
_CHOICE_LIST = f"[{'|'.join(SUPPORTED_OUTPUT_LANGUAGES)}]"
_AUTH_COMMANDS = (
    ("config", "auth", "clear"),
    ("config", "auth", "providers"),
    ("config", "auth", "configure"),
    ("config", "auth", "status"),
    ("config", "auth", "login"),
    ("config", "auth", "test"),
)
_CONFIG_PROFILE_COMMANDS = (
    ("config", "profile", "show"),
    ("config", "profile", "validate"),
    ("config", "profile", "list"),
    ("config", "profile", "delete"),
    ("config", "profile", "duplicate"),
    ("config", "profile", "rename"),
    ("config", "profile", "export"),
    ("config", "profile", "import"),
    ("config", "profile", "logout"),
    ("config", "profile", "status"),
    ("config", "switch"),
)
_MODELO_WORK_COMMANDS = (
    ("app", "modelo", "work", "calculate"),
    ("app", "modelo", "work", "verify"),
    ("app", "modelo", "work", "file"),
    ("app", "modelo", "work", "list"),
    ("app", "modelo", "work", "status"),
    ("app", "modelo", "work", "history"),
    ("app", "modelo", "work", "revisions"),
    ("app", "modelo", "work", "revision"),
    ("app", "modelo", "work", "runs"),
    ("app", "modelo", "work", "create"),
)
_REVIEW_COMMANDS = (
    ("app", "review", "queue"),
    ("app", "review", "view"),
)
_SUB_NOUN_GROUP_COMMANDS = (
    ("config", "auth", "diagnostics", "list"),
    ("config", "auth", "diagnostics", "show"),
    ("config", "auth", "diagnostics", "report"),
    ("config", "auth", "apoderado", "scopes", "list"),
    ("config", "auth", "apoderado", "status"),
    ("config", "auth", "apoderado", "configure"),
    ("config", "auth", "apoderado", "clear"),
    ("config", "auth", "apoderado", "check"),
    ("config", "profile", "history"),
    ("app", "ledger", "ratios", "list"),
    ("app", "ledger", "ratios", "set"),
    ("app", "ledger", "ratios", "unset"),
    ("app", "ledger", "ratios", "eligible"),
    ("app", "ledger", "ratios", "validate"),
)


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path) -> Iterator[None]:
    with isolated_sessionless_storage_root(tmp_path=tmp_path):
        yield


def _assert_output_language_registered(args: Sequence[str]) -> None:
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


def test_auth_commands_accept_output_language() -> None:
    """Config auth commands must accept ``--output-language``."""
    for argv in _AUTH_COMMANDS:
        _assert_output_language_registered(argv)


def test_config_profile_commands_accept_output_language() -> None:
    """Every config-profile verb and ``config switch`` accept ``--output-language``."""
    for argv in _CONFIG_PROFILE_COMMANDS:
        _assert_output_language_registered(argv)


def test_modelo_work_commands_accept_output_language() -> None:
    """Every ``aeat app modelo work`` command accepts ``--output-language``."""
    for argv in _MODELO_WORK_COMMANDS:
        _assert_output_language_registered(argv)


def test_review_commands_accept_output_language() -> None:
    """Every ``aeat app review`` read verb accepts ``--output-language``."""
    for argv in _REVIEW_COMMANDS:
        _assert_output_language_registered(argv)


def test_sub_noun_group_commands_accept_output_language() -> None:
    """Every enrolled sub-noun-group verb accepts ``--output-language``."""
    for argv in _SUB_NOUN_GROUP_COMMANDS:
        _assert_output_language_registered(argv)
