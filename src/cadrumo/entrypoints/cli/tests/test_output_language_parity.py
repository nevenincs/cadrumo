"""Regression test for ``--output-language`` parity across the CLI surface.

contract closes the parity gap identified in personas R7-C, Ines D3+D6, and
Joan R7-002: ``auth logout``, ``auth reset``, ``auth providers``, ``auth configure``,
``config profile view``, ``modelo work calculate``, ``modelo work verify``,
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

from collections.abc import Sequence

import pytest

from ....core.i18n.render import SUPPORTED_OUTPUT_LANGUAGES
from ....tests.cli_runner import invoke_cached_cli, semantic_cli_output
from ._isolated_profile_storage_fixtures import _isolated_state

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_isolated_state"]

# The option string we assert must appear in every target command's help.
_OPTION_FLAG = "--output-language"
# The pipe-joined accepted-value set the enum metavar surfaces. Asserting the
# choice enumeration itself (not the surrounding bracket glyph, which Click owns
# and rendered as ``[...]`` on older releases and ``<...>`` from click 8.4.x)
# keeps the gate pinned to the real capability: the accepted values are surfaced.
_CHOICE_LIST = "|".join(SUPPORTED_OUTPUT_LANGUAGES)
_AUTH_COMMANDS = (
    ("config", "auth", "logout"),
    ("config", "auth", "reset"),
    ("config", "auth", "providers"),
    ("config", "auth", "configure"),
    ("config", "auth", "status"),
    ("config", "auth", "login"),
    ("config", "auth", "test"),
)
_CONFIG_PROFILE_COMMANDS = (
    ("config", "profile", "view"),
    ("config", "profile", "validate"),
    ("config", "profile", "list"),
    ("config", "profile", "delete"),
    ("config", "profile", "duplicate"),
    ("config", "profile", "rename"),
    ("config", "profile", "export"),
    ("config", "profile", "import"),
    ("config", "logout"),
    ("config", "profile", "status"),
    ("config", "login"),
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
    ("config", "auth", "diagnostics", "view"),
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


def _assert_output_language_registered(args: Sequence[str]) -> None:
    """Invoke ``--help`` for *args* and assert ``--output-language`` is present."""
    help_args = [*args, "--help"]
    result = invoke_cached_cli(help_args)
    assert result.exit_code == 0, f"`{' '.join(help_args)}` exited {result.exit_code}:\n{result.output}"
    help_output = semantic_cli_output(result)
    assert _OPTION_FLAG in help_output, (
        f"`{' '.join(args)}` help does not include `{_OPTION_FLAG}`.\nHelp output:\n{help_output}"
    )
    assert _CHOICE_LIST in help_output, (
        f"`{' '.join(args)}` help does not constrain `{_OPTION_FLAG}` to {_CHOICE_LIST}.\nHelp output:\n{help_output}"
    )


def _assert_output_language_effective(args: Sequence[str]) -> None:
    """Assert *args* actually localises its output, not just accepts the flag.

    Runs the command twice — once in English and once in Hungarian — through both
    the leaf ``--output-language`` option and the root ``--language`` flag, and
    asserts the stdout differs. This closes the *ineffective-flag* gap: a command
    that registers ``--output-language`` (so
    :func:`_assert_output_language_registered` passes) but never routes its output
    through ``tr(...)`` produces byte-identical output in both locales, which this
    assertion catches. The surfaces enrolled here render a localised operator
    verdict line, so the two locales must diverge.
    """
    leaf_en = invoke_cached_cli([*args, "--output-language", "en"])
    leaf_hu = invoke_cached_cli([*args, "--output-language", "hu"])
    assert leaf_en.exit_code == 0, (
        f"`{' '.join(args)} --output-language en` exited {leaf_en.exit_code}:\n{leaf_en.output}"
    )
    assert leaf_hu.exit_code == 0, (
        f"`{' '.join(args)} --output-language hu` exited {leaf_hu.exit_code}:\n{leaf_hu.output}"
    )
    assert leaf_en.output != leaf_hu.output, (
        f"`{' '.join(args)}` output is identical under `--output-language en` and `hu`; "
        f"the flag is accepted but INEFFECTIVE (output not routed through tr()).\n"
        f"Output:\n{leaf_en.output}"
    )
    root_en = invoke_cached_cli(["--language", "en", *args])
    root_hu = invoke_cached_cli(["--language", "hu", *args])
    assert root_en.output != root_hu.output, (
        f"`--language ... {' '.join(args)}` output is identical under `en` and `hu`; "
        f"the root flag is accepted but INEFFECTIVE.\nOutput:\n{root_en.output}"
    )


# Surfaces that render a localised operator verdict line, so ``--language`` /
# ``--output-language`` must produce different output per locale. These are the
# anchors for the ineffective-flag regression gate; ``config auth status`` runs
# without an active profile so it is driveable in the sessionless test harness.
_OUTPUT_LANGUAGE_EFFECTIVE_COMMANDS = (("config", "auth", "status"),)


def test_output_language_is_effective_not_just_accepted() -> None:
    """Enrolled surfaces must localise output, not merely accept ``--output-language``.

    Regression companion to the presence checks: it fails when a command accepts
    the flag but ignores it (the ZSOFIA R9-B ineffective-flag class), which the
    presence-only assertions cannot detect.
    """
    for argv in _OUTPUT_LANGUAGE_EFFECTIVE_COMMANDS:
        _assert_output_language_effective(argv)


def test_auth_commands_accept_output_language() -> None:
    """Config auth commands must accept ``--output-language``."""
    for argv in _AUTH_COMMANDS:
        _assert_output_language_registered(argv)


def test_config_profile_commands_accept_output_language() -> None:
    """Every config-profile verb and ``config login`` accept ``--output-language``."""
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
