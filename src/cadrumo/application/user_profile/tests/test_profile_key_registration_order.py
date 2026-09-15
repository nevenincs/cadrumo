"""Real-behavior tests for cold application profile-key readers.

Each probe runs in a genuinely fresh interpreter that imports only the
application reader under test. The reader must compile the wizard-owned
catalogue on demand rather than relying on another module's import order.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import run_audited_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SRC_ROOT = Path(__file__).resolve().parents[4]

_READER_PROBES: tuple[tuple[str, str], ...] = (
    (
        "validate_profile_values",
        "print(validate_profile_values({}).total_keys)",
    ),
    (
        "profile_keys",
        "print(len(profile_keys()))",
    ),
)


def _run_cold(body: str) -> subprocess.CompletedProcess[str]:
    """Execute ``body`` in a fresh interpreter with no prior wizard import."""
    source = (
        "from cadrumo.application.user_profile.keys_validation import ("
        "profile_keys, validate_profile_values)\n" + body + "\n"
    )
    return run_audited_process(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        cwd=str(_SRC_ROOT),
        check=False,
    )


@pytest.mark.parametrize(("reader", "body"), _READER_PROBES, ids=[name for name, _ in _READER_PROBES])
def test_reader_succeeds_in_a_cold_interpreter(reader: str, body: str) -> None:
    result = _run_cold(body)

    assert result.returncode == 0, result.stderr


def test_cold_readers_agree_on_the_registered_key_count() -> None:
    result = _run_cold(
        "print(validate_profile_values({}).total_keys, len(profile_keys()))",
    )

    assert result.returncode == 0, result.stderr
    counts = [int(token) for token in result.stdout.split()]
    assert len(counts) == 2
    assert counts[0] > 0
    assert len(set(counts)) == 1


def test_application_catalogue_resolves_directly_in_a_cold_interpreter() -> None:
    """The canonical application resolver has no registration/bootstrap precondition."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from cadrumo.application.user_profile.profile_keys import profile_key, profile_keys\n"
                "print(len(profile_keys()), profile_key('IDENTITY.TAX_ID').key)\n"
            ),
        ],
        capture_output=True,
        text=True,
        cwd=str(_SRC_ROOT),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    count, key = result.stdout.split()
    assert int(count) > 0
    assert key == "identity.tax_id"
