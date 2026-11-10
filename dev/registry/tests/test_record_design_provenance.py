"""Official-design citations remain checked after the rename campaign is retired."""

from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions, filing_year_envelope
from dev.registry.record_design_labels import RecordDesignUnavailableError, record_design_source_ref

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_an_evolution_cites_the_design_source_the_edition_declares() -> None:
    # Modelos 714 and 131 name their one-year designs after the edition, which is the
    # spelling expected here independently of how the registry is read.
    editions_714 = tuple(str(revision.id) for revision in authored_revisions("714"))
    one_year_131 = tuple(
        str(revision.id)
        for revision in authored_revisions("131")
        if revision.valid_to is not None and str(revision.id) == str(revision.valid_from.year)
    )
    assert editions_714 and one_year_131
    for edition in editions_714:
        assert record_design_source_ref("714", edition) == f"aeat-dr-714-{edition}"
    for edition in one_year_131:
        assert record_design_source_ref("131", edition) == f"aeat-dr-131-{edition}"
    root = Path(bundled_path("registry", "aeat", "modelos"))
    for edition in editions_714:
        manifest = root / "714" / "revisions" / edition / "revision.toml"
        table = parse_toml(manifest.read_text(encoding="utf-8"))["revisions"][edition]
        assert record_design_source_ref("714", edition) in table.get("source_refs", ())


def test_an_edition_citing_no_record_design_refuses_rather_than_naming_one(tmp_path: Path) -> None:
    edition = str(filing_year_envelope().horizon)
    revision_dir = tmp_path / "999" / "revisions" / edition
    revision_dir.mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{edition}"]\nvalid_from = {edition}-01-01\nsource_refs = ["aeat-modelo-999-instructions"]\n',
        encoding="utf-8",
    )
    with pytest.raises(RecordDesignUnavailableError, match="cites no record_design source"):
        record_design_source_ref("999", edition, modelos_root=tmp_path)
