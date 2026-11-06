"""A revision clears its export layouts only where its own metadata says so."""

from pathlib import Path

import pytest

from ..tree_clearance_publication import has_export_clearance

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELOS = Path("src/cadrumo/_data/registry/aeat/modelos")


def test_a_revision_that_clears_its_export_layouts_is_recognised() -> None:
    assert has_export_clearance(_MODELOS / "296/revisions/2026-y-siguientes", "2026-y-siguientes")


def test_a_revision_with_a_generated_export_declares_no_clearance() -> None:
    revision = _MODELOS / "194/revisions/2024"
    assert (revision / "export").is_dir(), "the control revision no longer carries a generated export"

    assert not has_export_clearance(revision, "2024")


def test_a_clearance_is_read_for_the_named_revision_only(tmp_path: Path) -> None:
    (tmp_path / "revision.toml").write_text(
        '[[revisions."2026".cleared_families]]\nfamily = "export_layouts"\ncause = "not_authored_for_this_edition"\n'
        '\n[[revisions."2025".cleared_families]]\nfamily = "projection_endpoints"\n'
        'cause = "not_authored_for_this_edition"\n',
        encoding="utf-8",
    )

    assert has_export_clearance(tmp_path, "2026")
    assert not has_export_clearance(tmp_path, "2025")
    assert not has_export_clearance(tmp_path, "2024")


def test_a_revision_without_metadata_clears_nothing(tmp_path: Path) -> None:
    assert not has_export_clearance(tmp_path, "2026")
