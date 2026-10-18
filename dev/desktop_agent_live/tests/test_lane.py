"""The lane names the developer's key variable from the provider id, and writes the attach button's synthetic files."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..lane import LANE_ATTACHMENTS, key_variable, write_lane_attachments

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("provider_id", "variable"),
    [
        ("alpha", "CADRUMO_LLM_ALPHA_API_KEY"),
        ("beta_two", "CADRUMO_LLM_BETA_TWO_API_KEY"),
        ("Mixed_Case", "CADRUMO_LLM_MIXED_CASE_API_KEY"),
    ],
)
def test_the_key_variable_is_built_from_the_provider_id(provider_id: str, variable: str) -> None:
    assert key_variable(provider_id) == variable


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
