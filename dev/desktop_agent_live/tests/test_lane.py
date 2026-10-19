"""The lane writes the attach button's synthetic files."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..lane import LANE_ATTACHMENTS, write_lane_attachments

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_the_attach_buttons_files_are_synthetic_and_cover_every_outcome(tmp_path: Path) -> None:
    directory = write_lane_attachments(tmp_path / "attach")
    names = sorted(entry.name for entry in directory.iterdir())
    assert names == sorted(LANE_ATTACHMENTS)
    for name, content in LANE_ATTACHMENTS.items():
        assert (directory / name).read_bytes() == content
    # Stored, refused by format, refused by name and refused by content.
    assert {".txt", ".csv", ".zip", ".pdf"} <= {Path(name).suffix for name in names}
    assert any(name.startswith(".") for name in names)
    assert not (directory / "lane-mismatch.pdf").read_bytes().startswith(b"%PDF")
