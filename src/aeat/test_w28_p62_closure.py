"""Closure verification for W28.P62 standing inventory ratchets."""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_INVENTORY_MODULES = [
    "aeat.test_utf8_enrollment_inventory",
    "aeat.test_cast_rationale_inventory",
    "aeat.test_latin1_encoding_constant_enrollment",
    "aeat.test_enum_constant_extraction_inventory",
    "aeat.test_any_param_rationale_inventory",
    "aeat.test_mock_inventory",
    "aeat.test_type_ignore_rationale_inventory",
]


@pytest.mark.parametrize("module_name", _INVENTORY_MODULES)
def test_standing_inventory_ratchet_green(module_name: str) -> None:
    """Each standing inventory ratchet module must contain only passing tests."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--pyargs",
            module_name,
            "-q",
            "--tb=short",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Inventory ratchet {module_name!r} failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
