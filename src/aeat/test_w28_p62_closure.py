"""Closure verification for W28.P62 (S679, S680).

S679
----
Every ``raise RuntimeError(`` in ``entrypoints/cli/_doc_reference.py``
must be immediately preceded (within 3 lines) by a
``BROAD-EXCEPT-RATIONALE-SUBPROCESS-GUARD`` marker comment.

S680
----
This module itself verifies S679 and re-runs all 7 standing inventory
ratchets to confirm they remain green.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = pathlib.Path(__file__).parent
_DOC_REFERENCE = (
    _SRC_ROOT / "entrypoints" / "cli" / "_doc_reference.py"
)
_MARKER_TOKEN = "BROAD-EXCEPT-RATIONALE-SUBPROCESS-GUARD"
_RAISE_PATTERN = "raise RuntimeError("


# ---------------------------------------------------------------------------
# S679 — marker precedes every RuntimeError raise in _doc_reference.py
# ---------------------------------------------------------------------------


def test_s679_subprocess_guard_markers_precede_all_runtime_errors() -> None:
    """BROAD-EXCEPT-RATIONALE-SUBPROCESS-GUARD must appear within 3 lines
    preceding each ``raise RuntimeError(`` in _doc_reference.py."""
    assert _DOC_REFERENCE.exists(), f"_doc_reference.py not found at {_DOC_REFERENCE}"

    lines = _DOC_REFERENCE.read_text(encoding="utf-8").splitlines()

    raise_sites: list[int] = [
        idx for idx, ln in enumerate(lines) if _RAISE_PATTERN in ln
    ]
    assert raise_sites, f"No '{_RAISE_PATTERN}' found in {_DOC_REFERENCE} — file changed?"

    failures: list[str] = []
    for idx in raise_sites:
        window_start = max(0, idx - 3)
        window = lines[window_start:idx]
        if not any(_MARKER_TOKEN in ln for ln in window):
            failures.append(
                f"Line {idx + 1}: marker absent in preceding 3 lines.\n"
                f"  Window: {window!r}"
            )

    assert not failures, (
        f"{len(failures)} RuntimeError site(s) lack the rationale marker:\n"
        + "\n".join(failures)
    )


# ---------------------------------------------------------------------------
# Standing inventory ratchets — all 7 must remain green
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
