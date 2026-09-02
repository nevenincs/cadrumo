"""Real-behavior tests: every profile-key reader registers before it reads.

The profile-key registry is seeded by the wizard catalogue's import side
effect, and the domain accessor raises rather than returning an empty tuple
when nothing has seeded it. Only one of this module's three readers imported
the catalogue; the other two called the domain accessor directly and worked
purely because something earlier in the process had already imported the
wizard.

That masks the defect everywhere it is convenient to look. Importing any
module that touches the catalogue repairs the order for the rest of the
process, so an in-suite assertion proves nothing about a cold entry point.
These tests therefore run each reader in a genuinely fresh interpreter that
imports only the module under test.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SRC_ROOT = Path(__file__).resolve().parents[4]

_READER_PROBES: tuple[tuple[str, str], ...] = (
    (
        "validate_profile_values",
        "print(validate_profile_values({}).total_keys)",
    ),
    (
        "list_profile_key_records",
        "print(len(list_profile_key_records()))",
    ),
)


def _run_cold(body: str) -> subprocess.CompletedProcess[str]:
    """Execute ``body`` in a fresh interpreter with no prior wizard import."""
    source = (
        "from cadrumo.application.user_profile.keys_validation import ("
        "list_profile_key_records, validate_profile_values)\n" + body + "\n"
    )
    return subprocess.run(  # noqa: S603 - fixed argv, no shell, test-local source
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        cwd=str(_SRC_ROOT),
        check=False,
    )


@pytest.mark.parametrize(("reader", "body"), _READER_PROBES, ids=[name for name, _ in _READER_PROBES])
def test_reader_succeeds_in_a_cold_interpreter(reader: str, body: str) -> None:
    result = _run_cold(body)

    assert "ProfileKeysRegistrationError" not in result.stderr, (
        f"{reader} read the profile-key registry before registering it: {result.stderr}"
    )
    assert result.returncode == 0, result.stderr


def test_cold_readers_agree_on_the_registered_key_count() -> None:
    result = _run_cold(
        "print(validate_profile_values({}).total_keys, len(list_profile_key_records()))",
    )

    assert result.returncode == 0, result.stderr
    counts = [int(token) for token in result.stdout.split()]
    assert len(counts) == 2
    assert counts[0] > 0
    assert len(set(counts)) == 1


def test_the_domain_accessor_still_refuses_an_unregistered_registry() -> None:
    """The guard this fix routes around must stay loud, not become lenient."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from cadrumo.domain.contribuyente.keys import profile_keys\nprofile_keys()\n",
        ],
        capture_output=True,
        text=True,
        cwd=str(_SRC_ROOT),
        check=False,
    )

    assert result.returncode != 0
    assert "ProfileKeysRegistrationError" in result.stderr
