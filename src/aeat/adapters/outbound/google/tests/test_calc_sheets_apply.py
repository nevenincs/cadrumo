"""Real-behavior tests asserting Google Sheets / Drive boundary rationale
comments remain present in ``_calc_sheets_apply.py``.

The ``dict[str, Any]`` return signatures in the apply adapter document why
the Google Drive / Sheets APIs cannot use narrower types at their
third-party boundary.  These tests read the source file directly and
assert that the ``"irreducible"`` rationale marker survives refactors.
Removal of the marker without a matching narrowing means the boundary
is no longer annotated and the absence is deliberately surfaced here.
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_APPLY_PY = pathlib.Path(__file__).parent.parent / "_calc_sheets_apply.py"

_BOUNDARY_RATIONALE_MARKER = "irreducible"
"""Shared substring embedded in every documented ``dict[str, Any]`` rationale."""

_REQUIRED_ANCHORS: list[str] = [
    # ``_find_folder`` is the first documented boundary return in the file.
    "``_find_folder``",
]


def test_calc_sheets_apply_source_exists() -> None:
    # Guard: the source file this module asserts against must be on disk.
    assert _APPLY_PY.exists(), f"Source adapter not found: {_APPLY_PY}"


def test_calc_sheets_apply_boundary_rationale_comment_present() -> None:
    # The ``dict[str, Any]`` boundary annotation for the Google Drive API
    # response shape must be documented with the ``"irreducible"`` marker.
    # If the annotation disappears, the boundary is unannotated and
    # callers that rely on heterogeneous dict fields lose their contract.
    source = _APPLY_PY.read_text(encoding="utf-8")
    assert _BOUNDARY_RATIONALE_MARKER in source, (
        f"Boundary rationale comment containing {_BOUNDARY_RATIONALE_MARKER!r} "
        f"is missing from _calc_sheets_apply.py. "
        f"Re-add the ``dict[str, Any]`` annotation near the Drive API boundary functions."
    )


@pytest.mark.parametrize("anchor", _REQUIRED_ANCHORS)
def test_calc_sheets_apply_boundary_anchor_present(anchor: str) -> None:
    # The rationale comment must reference the specific function it guards.
    # This detects copy-paste errors where the comment is moved to a
    # different location without updating the function reference.
    source = _APPLY_PY.read_text(encoding="utf-8")
    assert anchor in source, (
        f"Boundary rationale anchor {anchor!r} is missing from _calc_sheets_apply.py. "
        f"The comment must document the specific function whose return type uses Any."
    )
