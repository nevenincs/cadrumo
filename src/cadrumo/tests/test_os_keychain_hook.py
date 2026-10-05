"""A refusing credential store skips the case under a warning; a working one lets it run.

Each case runs in a fresh interpreter, because ``keyring`` settles its backend
once per process and the probe caches its verdict for the same lifetime. The
backend is the real selection mechanism, ``PYTHON_KEYRING_BACKEND``, naming
either keyring's own failing backend or one of the shapes this suite already
keeps for the purpose.
"""

from __future__ import annotations

import os
import sys

import pytest
from pydantic import BaseModel

from .audited_process import run_audited_process
from .call_time_refusing_keyring import CALL_TIME_REFUSING_KEYRING
from .in_memory_keyring import IN_MEMORY_KEYRING

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_NO_USABLE_BACKEND = "keyring.backends.fail.Keyring"

# Two cases, not one: the verdict is cached per process, and the second case
# must be told what the first was rather than run on a remembered refusal.
_TWO_CASES = """
import json
import warnings

import pytest

from cadrumo.tests.os_keychain_hook import require_os_credential_store


def case():
    require_os_credential_store()
    return "ran"


outcomes = []
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    for _ in range(2):
        try:
            outcomes.append({"outcome": case()})
        except pytest.skip.Exception as skipped:
            outcomes.append({"outcome": "skipped", "reason": skipped.msg})
print(
    json.dumps(
        {
            "cases": outcomes,
            "warnings": [
                {"category": type(item.message).__name__, "message": str(item.message), "filename": item.filename}
                for item in caught
            ],
        }
    )
)
"""


class _Report(BaseModel):
    """What the child interpreter observed across its two cases."""

    cases: list[dict[str, str]]
    warnings: list[dict[str, str]]


def _two_cases_under(backend: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    env = {**os.environ, "PYTHON_KEYRING_BACKEND": backend}
    completed = run_audited_process([sys.executable, "-c", _TWO_CASES], env=env, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    report = _Report.model_validate_json(str(completed.stdout))
    return report.cases, report.warnings


@pytest.mark.parametrize(
    ("backend", "measured_refusal"),
    [
        pytest.param(_NO_USABLE_BACKEND, "no usable OS credential store is configured", id="no-usable-backend"),
        pytest.param(
            CALL_TIME_REFUSING_KEYRING,
            "refused a synthetic probe write: (1312, 'CredWrite'",
            id="call-time-logon-session-refusal",
        ),
    ],
)
def test_a_refusing_store_skips_every_case_under_a_warning_naming_the_refusal(
    backend: str, measured_refusal: str
) -> None:
    """Neither way a host refuses custody reaches the case body, and neither is silent."""
    cases, warned = _two_cases_under(backend)

    assert [case["outcome"] for case in cases] == ["skipped", "skipped"]
    for case in cases:
        assert measured_refusal in case["reason"]
        assert "NOT verified" in case["reason"]
    assert [item["category"] for item in warned] == ["OsCredentialStoreRefusedWarning"] * 2
    assert [item["message"] for item in warned] == [case["reason"] for case in cases]
    # Attributed to the case that was skipped, not to the hook that skipped it.
    assert {item["filename"] for item in warned} == {"<string>"}


def test_a_working_store_lets_every_case_run_without_a_warning() -> None:
    """ANTI-VACUITY: the skip is the store's verdict, not something the hook always does."""
    cases, warned = _two_cases_under(IN_MEMORY_KEYRING)

    assert cases == [{"outcome": "ran"}, {"outcome": "ran"}]
    assert warned == []
