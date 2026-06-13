"""Help and usage-error surfaces never demand the secret-store passphrase.

Operator-surface regression for the help-tree black hole: with an active
profile configured but ``AEAT_SECRET_PASSPHRASE`` unset and a
non-interactive stdin, the root callback's bucket-session activation used
to run before any help or usage rendering, so EVERY subgroup help
(``aeat config --help``, ``aeat app --help``, ``aeat app ledger --help``)
and every unknown-command typo died with the master-key refusal (exit 5)
instead of rendering. A newcomer could not browse the command tree before
creating secrets and scripted ``--help`` introspection was dead.

The contract under test: help and usage-error renderings are
introspection surfaces — like ``--version`` and the bare landing card —
and must not open the encrypted session; the master key unlocks only when
a verb actually executes against the store, where the existing refusal
stays intact.

Real-behavior only: each case runs the REAL installed ``aeat`` console
script in a subprocess with a controlled environment (no passphrase, a
configured active profile, isolated storage root) and captured stdio (so
stdin is genuinely non-interactive — the exact operator condition).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FAKE_ACTIVE_PROFILE = "0123456789abcdef0123456789abcdef"


def _passphraseless_env(tmp_path: Path) -> dict[str, str]:
    """Environment with an active profile but NO secret-store passphrase."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    env.update(
        {
            "AEAT_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
            "AEAT_TOKEN_DIR": str(tmp_path / "tokens"),
            "AEAT_RUNS_DIR": str(tmp_path / "runs"),
            "AEAT_ACTIVE_PROFILE": _FAKE_ACTIVE_PROFILE,
        },
    )
    return env


def _run(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    aeat_exe = shutil.which("aeat")
    assert aeat_exe is not None, "aeat console script must be installed for this gate"
    return subprocess.run(
        [aeat_exe, *args],
        cwd=Path.cwd(),
        env=_passphraseless_env(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


@pytest.mark.parametrize(
    ("args", "expected_row"),
    [
        (["config", "--help"], "aeat config profile create"),
        (["app", "--help"], "aeat app ledger import"),
        (["app", "ledger", "--help"], "import"),
        (["app", "modelo", "--help"], "work"),
    ],
)
def test_subgroup_help_renders_without_passphrase(
    tmp_path: Path,
    args: list[str],
    expected_row: str,
) -> None:
    """Every subgroup help renders exit 0 with real content, no master key."""
    result = _run(args, tmp_path)
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    assert expected_row in result.stdout, combined
    assert "AEAT_SECRET_PASSPHRASE" not in combined
    assert "Traceback" not in combined


def test_unknown_command_renders_usage_error_without_passphrase(tmp_path: Path) -> None:
    """A typo'd subcommand yields the exit-2 usage error, not a key refusal."""
    result = _run(["config", "nosuchcmd"], tmp_path)
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 2, combined
    assert "nosuchcmd" in combined
    assert "AEAT_SECRET_PASSPHRASE" not in combined


def test_data_verb_still_refuses_without_passphrase(tmp_path: Path) -> None:
    """Anti-tautology: a verb that touches the store keeps the hard refusal.

    If this ever turns green-by-accident (exit 0), the introspection gate
    has started skipping the session for real verb execution and every
    help assertion above is meaningless.
    """
    result = _run(["app", "ledger", "list"], tmp_path)
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0, combined
    assert "AEAT_SECRET_PASSPHRASE" in combined
