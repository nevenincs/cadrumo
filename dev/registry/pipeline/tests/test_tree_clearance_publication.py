"""A revision clears its export layouts only where its own metadata says so."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    open_ended_revision,
)

from ..tree_clearance_publication import has_export_clearance

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELOS = Path("src/cadrumo/_data/registry/aeat/modelos")
#: Synthetic revision ids for the isolated metadata cases, newest first.
_LATEST = str(filing_year_envelope().horizon)
_PREVIOUS = str(filing_year_envelope().horizon - 1)
_EARLIER = str(filing_year_envelope().horizon - 2)


def test_a_revision_that_clears_its_export_layouts_is_recognised() -> None:
    revision = str(open_ended_revision("296").id)
    assert has_export_clearance(_MODELOS / "296" / "revisions" / revision, revision)


def test_a_revision_with_a_generated_export_declares_no_clearance() -> None:
    revision_id = str(open_ended_revision("194").id)
    revision = _MODELOS / "194" / "revisions" / revision_id
    assert (revision / "export").is_dir(), "the control revision no longer carries a generated export"

    assert not has_export_clearance(revision, revision_id)


def test_a_clearance_is_read_for_the_named_revision_only(tmp_path: Path) -> None:
    (tmp_path / "revision.toml").write_text(
        f'[[revisions."{_LATEST}".cleared_families]]\nfamily = "export_layouts"\n'
        'cause = "not_authored_for_this_edition"\n'
        f'\n[[revisions."{_PREVIOUS}".cleared_families]]\nfamily = "projection_endpoints"\n'
        'cause = "not_authored_for_this_edition"\n',
        encoding="utf-8",
    )

    assert has_export_clearance(tmp_path, _LATEST)
    assert not has_export_clearance(tmp_path, _PREVIOUS)
    assert not has_export_clearance(tmp_path, _EARLIER)


def test_a_revision_without_metadata_clears_nothing(tmp_path: Path) -> None:
    assert not has_export_clearance(tmp_path, _LATEST)
