"""Real-behavior tests pinning the ``--language`` help-text honesty contract.

The operator-surface decision requires the root ``--language`` / ``--lang`` flag
to be honest about help text: it must not silently fail to do what it advertises.
Per the accepted ordering (work, then remove, then warn), the feasibility spike
found the highest outcome —
*make it work* — was cheaply achievable by promoting an explicit ``--language``
flag to ``AEAT_OUTPUT_LANGUAGE`` in the console entry point, before the lazily
imported subcommand modules render their ``tr(...)``-bound help. These tests pin
that contract against the real installed ``aeat`` console.

The help-text localisation only occurs through the real ``main()`` entry point
(the pre-parse runs there, before the lazy command tree imports), so the
subprocess tests invoke the installed console script rather than an in-process
``CliRunner`` (which bypasses ``main()``). The pure-parser unit tests isolate the
argv-scan logic, which carries no external dependency.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ....core.config import SecretStoreBackend
from ....tests.secure_sql import dev_test_database_password
from .._language_argv import _language_from_argv

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _console_env(tmp_path: Path, *, language: str | None) -> dict[str, str]:
    """Build a clean subprocess env with no ambient ``AEAT_OUTPUT_LANGUAGE``.

    Strips every ``AEAT_*`` variable so the only language signal reaching the
    console is the ``--language`` flag under test (or, when ``language`` is set,
    an explicit ambient override used to prove the flag wins over it).
    """
    env = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    env.update(
        {
            "AEAT_SECRET_STORE_BACKEND": SecretStoreBackend.FILE.value,
            "AEAT_SECRET_PASSPHRASE": dev_test_database_password(),
            "AEAT_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
            "AEAT_TOKEN_DIR": str(tmp_path / "tokens"),
            "AEAT_RUNS_DIR": str(tmp_path / "runs"),
            "AEAT_FINANCIAL_TXS_DIR": str(tmp_path / "txs"),
            "AEAT_INVOICES_DIR": str(tmp_path / "invoices"),
            "AEAT_DRAFTS_DIR": str(tmp_path / "drafts"),
        }
    )
    if language is not None:
        env["AEAT_OUTPUT_LANGUAGE"] = language
    return env


def _run_console(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    aeat_exe = shutil.which("aeat")
    assert aeat_exe is not None, "the aeat console script must be installed for this test"
    return subprocess.run(
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
    """An explicit ``--language en`` wins over an ambient ``AEAT_OUTPUT_LANGUAGE=es``.

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
    """The ``AEAT_OUTPUT_LANGUAGE`` override path is unchanged when no flag is given.

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


def test_invalid_language_value_is_refused_with_accepted_set(tmp_path: Path) -> None:
    """An unsupported ``--language`` value is refused with the accepted-set hint.

    The pre-parse forwards only supported values; the canonical Typer ``Choice``
    on the root callback remains the single refusal authority and must name the
    accepted set rather than silently ignoring the value.
    """
    result = _run_console(
        ["--language", "xx", "config", "profile", "create", "--help"],
        _console_env(tmp_path, language=None),
    )
    combined = f"{result.stdout}\n{result.stderr}"
    assert "Invalid value" in combined, combined
    assert "'xx' is not one of" in combined, combined
    for code in ("es", "en", "ca", "hu"):
        assert f"'{code}'" in combined, combined
    # The invalid value must not localise help instead of refusing.
    assert _CREATE_HELP_EN not in result.stdout, combined


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--language", "en", "config", "profile", "create", "--help"], "en"),
        (["--lang", "ca", "app", "ledger", "import"], "ca"),
        (["--language=hu", "config", "profile", "list"], "hu"),
        (["--lang=es"], "es"),
        (["config", "profile", "create"], None),
        (["--language", "xx", "config"], None),
        (["--language"], None),
        (["--profile", "alice", "config", "profile", "list"], None),
        (["--language", "EN", "config"], "en"),
    ],
)
def test_language_from_argv_extracts_supported_value(argv: list[str], expected: str | None) -> None:
    """The pure argv parser extracts the supported language or ``None``.

    Unit-isolated pure logic: no external dependency, so a direct assertion on
    the parser is appropriate. Unsupported values (``xx``), missing values, and
    unrelated flags (``--profile``) all yield ``None`` so the canonical Typer
    validation stays the single refusal authority.
    """
    assert _language_from_argv(argv) == expected
