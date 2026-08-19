"""Real-behavior tests pinning the ``--language`` help-text honesty contract.

The operator-surface decision requires the root ``--language`` / ``--lang`` flag
to be honest about help text: it must not silently fail to do what it advertises.
Per the accepted ordering (work, then remove, then warn), the feasibility spike
found the highest outcome —
*make it work* — was cheaply achievable by promoting an explicit ``--language``
flag to ``CADRUMO_OUTPUT_LANGUAGE`` in the console entry point, before the lazily
imported subcommand modules render their ``tr(...)``-bound help. These tests pin
that contract against the real installed ``aeat`` console.

The help-text localisation only occurs through the real ``main()`` entry point
(the pre-parse runs there, before the lazy command tree imports), so the
subprocess tests invoke the installed console script rather than an in-process
test runner (which bypasses ``main()``). The pure-parser unit tests isolate the
argv-scan logic, which carries no external dependency.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from cadrumo.core.config import SecretStoreBackend
from cadrumo.entrypoints.cli._language_argv import _language_from_argv
from cadrumo.tests.secure_sql import dev_test_database_password

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _console_env(tmp_path: Path, *, language: str | None) -> dict[str, str]:
    """Build a clean subprocess env with no ambient ``CADRUMO_OUTPUT_LANGUAGE``.

    Strips every ``CADRUMO_*`` and ``AEAT_*`` variable so the only language
    signal reaching the console is the ``--language`` flag under test (or, when
    ``language`` is set, an explicit ambient override used to prove the flag
    wins over it).

    Stripping the product prefix is what makes the flag cases mean anything.
    The test process pins ``CADRUMO_OUTPUT_LANGUAGE=en`` for its own
    readability, so an inherited environment would hand the child the very
    answer a ``--language en`` case exists to prove the flag produces, and that
    case would pass with the flag doing nothing. Mirrors the CLI-reference
    generator's environment builder, which strips both prefixes for the same
    reason.
    """
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith(("CADRUMO_", "AEAT_"))}
    env.update(
        {
            "CADRUMO_SECRET_STORE_BACKEND": SecretStoreBackend.AUTO.value,
            "CADRUMO_SECRET_PASSPHRASE": dev_test_database_password(),
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
            "CADRUMO_TOKEN_DIR": str(tmp_path / "probe-tokens"),
            "CADRUMO_RUNS_DIR": str(tmp_path / "probe-runs"),
            "CADRUMO_FINANCIAL_TXS_DIR": str(tmp_path / "txs"),
            "CADRUMO_INVOICES_DIR": str(tmp_path / "invoices"),
            "CADRUMO_DRAFTS_DIR": str(tmp_path / "probe-drafts"),
        },
    )
    if language is not None:
        env["CADRUMO_OUTPUT_LANGUAGE"] = language
    return env


def _run_console(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    aeat_exe = shutil.which("aeat")
    assert aeat_exe is not None, "the aeat console script must be installed for this test"
    return subprocess.run(  # noqa: S603 - resolved executable, fixed argv, no shell
        [aeat_exe, *args],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


# The English and Spanish help descriptions for ``config profile create`` are
# distinct, locale-authored strings (``cli.config.profile.create_help``). They
# are the observable proof that help text rendered in the chosen language.
_CREATE_HELP_EN = "Initialize a new active profile."
_CREATE_HELP_ES = "Inicializa un nuevo perfil activo."
_CALENDAR_HELP_HU = "A határidő-naptár megjelenítése az aktív profilhoz"
_CALENDAR_FROM_HELP_HU = "A naptárablak kezdő dátuma"
_CALENDAR_TO_HELP_HU = "A naptárablak záró dátuma"
_CALENDAR_ALLOW_INCOMPLETE_HELP_HU = "A naptár megjelenítése akkor is"
_CALENDAR_SHOW_SUPPRESSED_HELP_HU = "Elnyomott bejegyzések megjelenítése"
_CALENDAR_ALL_PROFILES_HELP_HU = "Az összes regisztrált profil naptárát"
_CALENDAR_FROM_HELP_EN = "Inclusive start date for the calendar window"
_CALENDAR_ALL_PROFILES_HELP_EN = "Render the calendar for every registered active profile"


def test_language_flag_renders_english_leaf_help(tmp_path: Path) -> None:
    """``--language en`` localises a leaf subcommand's help text to English."""
    result = _run_console(
        ["--language", "en", "config", "profile", "create", "--help"],
        _console_env(tmp_path, language=None),
    )
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    assert _CREATE_HELP_EN in result.stdout, combined
    assert _CREATE_HELP_ES not in result.stdout, combined


def test_language_flag_renders_spanish_leaf_help(tmp_path: Path) -> None:
    """``--language es`` localises the same leaf help text to Spanish."""
    result = _run_console(
        ["--language", "es", "config", "profile", "create", "--help"],
        _console_env(tmp_path, language=None),
    )
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    assert _CREATE_HELP_ES in result.stdout, combined
    assert _CREATE_HELP_EN not in result.stdout, combined


def test_lang_alias_localises_leaf_help(tmp_path: Path) -> None:
    """The ``--lang`` alias localises help text identically to ``--language``."""
    result = _run_console(
        ["--lang", "en", "config", "profile", "create", "--help"],
        _console_env(tmp_path, language=None),
    )
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    assert _CREATE_HELP_EN in result.stdout, combined


def test_explicit_language_flag_overrides_ambient_env(tmp_path: Path) -> None:
    """An explicit ``--language en`` wins over an ambient ``CADRUMO_OUTPUT_LANGUAGE=es``.

    The flag is the most specific operator intent for the invocation, so it must
    override an ambient environment language for that run's help text.
    """
    result = _run_console(
        ["--language", "en", "config", "profile", "create", "--help"],
        _console_env(tmp_path, language="es"),
    )
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    assert _CREATE_HELP_EN in result.stdout, combined
    assert _CREATE_HELP_ES not in result.stdout, combined


def test_env_var_still_controls_help_without_flag(tmp_path: Path) -> None:
    """The ``CADRUMO_OUTPUT_LANGUAGE`` override path is unchanged when no flag is given.

    The fix corrects only the eager flag's silent-failure-on-help behaviour; the
    profile-owned precedence and the env override must keep working untouched.
    """
    result = _run_console(
        ["config", "profile", "create", "--help"],
        _console_env(tmp_path, language="en"),
    )
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    assert _CREATE_HELP_EN in result.stdout, combined


def test_hungarian_overview_calendar_help_localises_custom_options_together(tmp_path: Path) -> None:
    """``overview calendar --help`` must not mix Hungarian and English custom option help."""
    result = _run_console(
        ["--language", "hu", "app", "overview", "calendar", "--help"],
        _console_env(tmp_path, language=None),
    )
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    for expected in (
        _CALENDAR_HELP_HU,
        _CALENDAR_FROM_HELP_HU,
        _CALENDAR_TO_HELP_HU,
        _CALENDAR_ALLOW_INCOMPLETE_HELP_HU,
        _CALENDAR_SHOW_SUPPRESSED_HELP_HU,
        _CALENDAR_ALL_PROFILES_HELP_HU,
    ):
        assert expected in result.stdout, combined
    assert _CALENDAR_FROM_HELP_EN not in result.stdout, combined
    assert _CALENDAR_ALL_PROFILES_HELP_EN not in result.stdout, combined


def test_invalid_language_value_is_refused_with_accepted_set(tmp_path: Path) -> None:
    """An unsupported ``--language`` value is refused with the accepted-set hint.

    The pre-parse forwards only supported values; the canonical Typer ``Choice``
    on the root callback remains the single refusal authority and must name the
    accepted set rather than silently ignoring the value.

    The ambient language is pinned to English deliberately, and this is the one
    case in the module that wants one. Click localises the ``Invalid value for``
    prefix but not the accepted-set clause, so the English assertion below is
    only honest if the run is English by declaration rather than by whatever the
    machine resolves. It also keeps the last assertion from going vacuous: the
    guard is that an invalid value must refuse rather than render help, and help
    wrongly rendered under a Spanish default would not contain the English
    string being looked for, so the check would pass while the defect shipped.
    """
    result = _run_console(
        ["--language", "xx", "config", "profile", "create", "--help"],
        _console_env(tmp_path, language="en"),
    )
    combined = f"{result.stdout}\n{result.stderr}"
    assert "Invalid value" in combined, combined
    assert "'xx' is not one of" in combined, combined
    for code in ("es", "en", "ca", "hu"):
        assert f"'{code}'" in combined, combined
    # The invalid value must not localise help instead of refusing.
    assert _CREATE_HELP_EN not in result.stdout, combined


_LANGUAGE_ARGV_CASES = (
    (["--language", "en", "config", "profile", "create", "--help"], "en"),
    (["--lang", "ca", "app", "ledger", "import"], "ca"),
    (["--language=hu", "config", "profile", "list"], "hu"),
    (["--lang=es"], "es"),
    (["config", "profile", "create"], None),
    (["--language", "xx", "config"], None),
    (["--language"], None),
    (["--profile", "alice", "config", "profile", "list"], None),
    (["--language", "EN", "config"], "en"),
)


def test_language_from_argv_extracts_supported_value() -> None:
    """The pure argv parser extracts the supported language or ``None``.

    Unit-isolated pure logic: no external dependency, so a direct assertion on
    the parser is appropriate. Unsupported values (``xx``), missing values, and
    unrelated flags (``--profile``) all yield ``None`` so the canonical Typer
    validation stays the single refusal authority.
    """
    failures: list[str] = []
    for argv, expected in _LANGUAGE_ARGV_CASES:
        actual = _language_from_argv(argv)
        if actual != expected:
            failures.append(f"{argv!r}: expected {expected!r}, got {actual!r}")

    assert not failures, "\n".join(failures)


# The ``Options`` plain-text help section heading is localised to the resolved
# output locale by ``_localise_help_section_headers`` in the console entry
# point. The Hungarian rendering is the observable proof the ``--help`` SECTION
# HEADING (not just the option descriptions) localises.
_OPTIONS_PANEL_HU = "Kapcsolók"
_OPTIONS_PANEL_EN = "Options:"


def test_help_section_headers_localise_to_hungarian(tmp_path: Path) -> None:
    """``--language hu`` localises the plain-text ``--help`` section heading, not just descriptions.

    The option *descriptions* already localise via the env promotion; this pins
    the residual framework-owned ``Options`` heading to the resolved locale.
    """
    result = _run_console(
        ["--language", "hu", "config", "auth", "status", "--help"],
        _console_env(tmp_path, language=None),
    )
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    assert _OPTIONS_PANEL_HU in result.stdout, combined
    assert _OPTIONS_PANEL_EN not in result.stdout, combined


def test_help_section_header_locale_does_not_leak_across_processes(tmp_path: Path) -> None:
    """A Hungarian ``--help`` run must not leak its localised heading into a later English run.

    ``_localise_help_section_headers`` rebinds the module-level ``_`` gettext
    name inside :mod:`typer.core`, so this guards the invocation-scoping
    contract: because each real ``aeat`` invocation is its own process, an ``hu``
    run's rebind must not survive into a subsequent ``en`` run. Two separate
    console processes prove the rebind reflects only its own invocation's locale.
    """
    env = _console_env(tmp_path, language=None)
    hu = _run_console(["--language", "hu", "config", "auth", "status", "--help"], env)
    assert _OPTIONS_PANEL_HU in hu.stdout, f"{hu.stdout}\n{hu.stderr}"
    en = _run_console(["--language", "en", "config", "auth", "status", "--help"], env)
    en_combined = f"{en.stdout}\n{en.stderr}"
    assert _OPTIONS_PANEL_EN in en.stdout, en_combined
    assert _OPTIONS_PANEL_HU not in en.stdout, en_combined
