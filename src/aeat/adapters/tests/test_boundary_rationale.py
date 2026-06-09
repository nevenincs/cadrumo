"""Real-behavior tests asserting that Google and Playwright adapter boundary
rationale comments remain present in the source tree.

These tests guard against silent removal of the ``dict[str, Any]`` boundary
annotations that document why the Google Drive / Sheets and Playwright
adapters cannot use narrower types at their third-party API surfaces.  The
pattern is source-file inspection, not a mock: if the comment disappears
during a refactor the test fails loudly.
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SRC = pathlib.Path(__file__).parent.parent

_BOUNDARY_RATIONALE_MARKER = "irreducible"
"""Shared substring present in every documented ``dict[str, Any]`` rationale comment."""

_ANNOTATED_FILES: list[tuple[str, str]] = [
    (
        "outbound/google/_calc_sheets_apply.py",
        "``_find_folder``",
    ),
    (
        "outbound/storage/_google_drive.py",
        "_find_file",
    ),
    (
        "outbound/aeat/browser/session.py",
        "_build_context_kwargs",
    ),
]


@pytest.mark.parametrize("rel_path,anchor_text", _ANNOTATED_FILES)
def test_boundary_rationale_comment_present(rel_path: str, anchor_text: str) -> None:
    """Assert that the boundary rationale marker comment exists in the adapter file.

    The marker substring ``"irreducible"`` is embedded in every legitimate
    ``dict[str, Any]`` boundary annotation added to Google/Playwright adapters
    (e.g., "irreducible Google Drive API boundary shape").  If it disappears
    the boundary is unannotated and the assertion must be re-evaluated.
    """
    path = _SRC / rel_path
    assert path.exists(), f"Adapter file not found: {path}"
    source = path.read_text(encoding="utf-8")
    assert _BOUNDARY_RATIONALE_MARKER in source, (
        f"Boundary rationale comment containing {_BOUNDARY_RATIONALE_MARKER!r} "
        f"is missing from {rel_path!r}.  Re-add the ``dict[str, Any]`` "
        f"annotation near the function containing {anchor_text!r}."
    )
