"""The test keyring backends are usable only when a process names them.

Each case runs in a fresh interpreter, because ``keyring`` settles its backend
once per process and the question is what that first choice is.
"""

from __future__ import annotations

import os
import sys

import pytest

from .audited_process import run_audited_process
from .call_time_refusing_keyring import CALL_TIME_REFUSING_KEYRING
from .in_memory_keyring import IN_MEMORY_KEYRING

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROBE = """
import keyring
import cadrumo.tests.call_time_refusing_keyring
import cadrumo.tests.in_memory_keyring
selected = keyring.get_keyring()
print(f"{type(selected).__module__}.{type(selected).__qualname__}")
print(selected.priority)
"""


def _selected_backend(selection: str | None) -> tuple[str, float]:
    env = {key: value for key, value in os.environ.items() if key != "PYTHON_KEYRING_BACKEND"}
    if selection is not None:
        env["PYTHON_KEYRING_BACKEND"] = selection
    completed = run_audited_process([sys.executable, "-c", _PROBE], env=env, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    name, priority = str(completed.stdout).split()
    return name, float(priority)


def test_importing_the_test_backends_leaves_the_detected_default_alone() -> None:
    """DETECTOR TEETH: a pytest worker imports every test module at collection.

    A fixed positive priority made whichever test backend was imported the
    worker's default keyring, so a parent minted into a process-local store its
    own child could never read.
    """
    name, _priority = _selected_backend(None)

    assert name not in {IN_MEMORY_KEYRING, CALL_TIME_REFUSING_KEYRING}


@pytest.mark.parametrize("backend", [IN_MEMORY_KEYRING, CALL_TIME_REFUSING_KEYRING])
def test_a_named_backend_is_selected_as_a_usable_keychain(backend: str) -> None:
    """ANTI-VACUITY: the backends still stand in for a usable keychain where selected."""
    name, priority = _selected_backend(backend)

    assert name == backend
    assert priority > 0
