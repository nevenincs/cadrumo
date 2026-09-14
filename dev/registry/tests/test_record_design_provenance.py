"""Official-design citations remain checked after the rename campaign is retired."""

import tomllib
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from dev.registry.record_design_labels import RecordDesignUnavailableError, record_design_source_ref

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_an_evolution_cites_the_design_source_the_edition_declares() -> None:
    assert record_design_source_ref("714", "2021") == "aeat-dr-714-2021"
    assert record_design_source_ref("131", "2025") == "aeat-dr-131-2025"
    root = Path(bundled_path("registry", "aeat", "modelos"))
    for edition in ("2021", "2022"):
        manifest = root / "714" / "revisions" / edition / "revision.toml"
        table = tomllib.loads(manifest.read_text(encoding="utf-8"))["revisions"][edition]
        assert record_design_source_ref("714", edition) in table.get("source_refs", ())


def test_an_edition_citing_no_record_design_refuses_rather_than_naming_one(tmp_path: Path) -> None:
    revision_dir = tmp_path / "999" / "revisions" / "2025"
    revision_dir.mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        '[revisions."2025"]\nvalid_from = 2025-01-01\nsource_refs = ["aeat-modelo-999-instructions"]\n',
        encoding="utf-8",
    )
    with pytest.raises(RecordDesignUnavailableError, match="cites no record_design source"):
        record_design_source_ref("999", "2025", modelos_root=tmp_path)
