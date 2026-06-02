"""Closure verification for W27.P61 (S676, S677, S678).

S676
----
The any-param ratchet in ``test_any_param_rationale_inventory`` must pass
with updated line numbers that reflect the +1 shift introduced by W26
comment insertions.

S677
----
The LOGGING-STDLIB-RATIONALE-STDIO-PLATFORM-FALLBACK marker must appear
within 3 lines preceding ``import logging`` in
``entrypoints/cli/_stdio.py``.

Standing ratchets
-----------------
All seven canonical inventory ratchets must remain green simultaneously.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = pathlib.Path(__file__).parent


# ---------------------------------------------------------------------------
# S676 — any-param ratchet passes
# ---------------------------------------------------------------------------


def test_s676_any_param_ratchet_passes() -> None:
    """The any-param inventory ratchet must pass with the corrected line numbers."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(_SRC_ROOT / "test_any_param_rationale_inventory.py"),
            "-x",
            "-q",
            "--tb=short",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "any-param ratchet failed — S676 line-number update is incomplete.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# S677 — LOGGING-STDLIB-RATIONALE-STDIO-PLATFORM-FALLBACK marker present
# ---------------------------------------------------------------------------


def test_s677_logging_rationale_marker_precedes_import() -> None:
    """LOGGING-STDLIB-RATIONALE-STDIO-PLATFORM-FALLBACK must appear within 3 lines
    preceding ``import logging`` in entrypoints/cli/_stdio.py."""
    stdio_path = (
        _SRC_ROOT / "entrypoints" / "cli" / "_stdio.py"
    )
    assert stdio_path.exists(), f"_stdio.py not found at {stdio_path}"

    lines = stdio_path.read_text(encoding="utf-8").splitlines()
    token = "LOGGING-STDLIB-RATIONALE-STDIO-PLATFORM-FALLBACK"

    import_logging_lineno: int | None = None
    for idx, line in enumerate(lines):
        if line.strip() == "import logging":
            import_logging_lineno = idx
            break

    assert import_logging_lineno is not None, (
        "Could not find 'import logging' in _stdio.py"
    )

    window_start = max(0, import_logging_lineno - 3)
    window = lines[window_start:import_logging_lineno]
    found = any(token in ln for ln in window)
    assert found, (
        f"{token!r} not found within 3 lines before 'import logging' "
        f"(line {import_logging_lineno + 1}) in {stdio_path}.\n"
        f"Window checked:\n" + "\n".join(window)
    )


# ---------------------------------------------------------------------------
# Standing inventory ratchets — all must be green
# ---------------------------------------------------------------------------

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
        f"Inventory ratchet {module_name!r} failed.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
