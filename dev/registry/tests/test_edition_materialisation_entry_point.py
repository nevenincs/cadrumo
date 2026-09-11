"""The public entry point that resolves one edition into its full-copy raw revision table."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.edition_materialisation import materialise_edition
from ..conformance.tests._loader_directory_mode_support import _write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "ley-58-2003:art-29"


def _write_edition(
    modelo_dir: Path, revision_id: str, *, year: int, rows: tuple[tuple[str, str], ...], extra: str
) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    (revision_dir / "casillas").mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        'source_refs = ["aeat-manual"]\n'
        f"{extra}",
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(
        "".join(
            f'[[revisions."{revision_id}".casillas]]\nid = "{casilla_id}"\nnumber = "{casilla_id}"\n'
            f'section = ["liquidacion"]\ncontinuidad_id = "{lineage}"\n'
            f'legal_refs = ["{_LEGAL_REF}"]\nsource_refs = ["aeat-manual"]\n\n'
            for casilla_id, lineage in rows
        ),
        encoding="utf-8",
        newline="\n",
    )


def _modelo(tmp_path: Path, *, successor_extra: str) -> Path:
    modelo_dir = tmp_path / "999"
    modelo_dir.mkdir()
    _write_standard_manifest(modelo_dir, "Test")
    _write_edition(modelo_dir, "2024", year=2024, rows=(("1", "base"), ("2", "cuota")), extra="")
    _write_edition(modelo_dir, "2025", year=2025, rows=(("3", "recargo"),), extra=successor_extra)
    return modelo_dir


def test_a_delta_edition_resolves_to_every_row_and_names_no_predecessor(tmp_path: Path) -> None:
    edition = materialise_edition(_modelo(tmp_path, successor_extra='predecessor = "2024"\n'), "2025")

    assert edition.inherits_from == "2024"
    assert "predecessor" not in edition.table
    rows = edition.table["casillas"]
    assert isinstance(rows, tuple)
    assert [row["continuidad_id"] for row in rows] == ["base", "cuota", "recargo"]
    assert edition.label_origins == ("2024", "2024", None)


def test_an_edition_stating_every_row_is_returned_as_declared(tmp_path: Path) -> None:
    edition = materialise_edition(_modelo(tmp_path, successor_extra=""), "2025")

    assert edition.inherits_from is None
    assert edition.label_origins is None
    rows = edition.table["casillas"]
    assert isinstance(rows, tuple)
    assert [row["continuidad_id"] for row in rows] == ["recargo"]


def test_an_edition_the_modelo_does_not_declare_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RegistryLoadError, match="no edition '2026'"):
        materialise_edition(_modelo(tmp_path, successor_extra=""), "2026")


def test_a_named_predecessor_absent_from_the_tree_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RegistryLoadError, match="2023"):
        materialise_edition(_modelo(tmp_path, successor_extra='predecessor = "2023"\n'), "2025")


_REVIEWED_DELTA = (
    'predecessor = "2024"\n'
    'engineered_by = "agent:author"\n'
    'review_status = "agent_reviewed"\n'
    'reviewed_by = "agent:reviewer"\n'
    "reviewed_at = 2026-09-10\n"
    'reviewed_against = "2024"\n'
)


def _standalone(table: object) -> ModeloRevision:
    """Validate a materialised table's revision scalars as the edition's only source, with no predecessor present.

    The casilla rows are left out because their locale keys are computed by the
    loader, and the stamp rules read nothing from them.
    """
    assert isinstance(table, dict)
    scalars = {key: value for key, value in table.items() if key != "casillas"}
    return ModeloRevision.model_validate({**scalars, "id": "2025", "localization_key": "standalone"})


def test_a_reviewed_delta_edition_resolves_to_an_unreviewed_full_copy_that_says_what_it_set_aside(
    tmp_path: Path,
) -> None:
    """The delta's review covered only its stated rows, so the full copy claims no review and reports the withdrawal."""
    edition = materialise_edition(_modelo(tmp_path, successor_extra=_REVIEWED_DELTA), "2025")

    assert edition.withdrawn_review_status == "agent_reviewed"
    assert edition.table["review_status"] == "pending_review"
    assert not {"reviewed_by", "reviewed_at", "reviewed_against"} & set(edition.table)
    assert edition.table["engineered_by"] == "agent:author"
    standalone = _standalone(edition.table)
    assert standalone.review_status.value == "pending_review"
    assert standalone.reviewed_against is None


def test_the_delta_review_cannot_stand_on_the_full_copy(tmp_path: Path) -> None:
    """The teeth: carrying the delta's claim onto the full copy is refused by the schema itself."""
    source = _modelo(tmp_path, successor_extra=_REVIEWED_DELTA) / "revisions" / "2025" / "revision.toml"
    declared = tomllib.loads(source.read_text(encoding="utf-8"))["revisions"]["2025"]
    edition = materialise_edition(source.parents[2], "2025")
    carried = {**edition.table, **{key: declared[key] for key in ("review_status", "reviewed_by", "reviewed_at")}}
    carried["reviewed_against"] = declared["reviewed_against"]

    with pytest.raises(ValidationError, match="names no predecessor"):
        _standalone(carried)


def test_an_edition_stating_every_row_keeps_its_review(tmp_path: Path) -> None:
    extra = 'review_status = "agent_reviewed"\nreviewed_by = "agent:reviewer"\nreviewed_at = 2026-09-10\n'
    edition = materialise_edition(_modelo(tmp_path, successor_extra=extra), "2025")

    assert edition.withdrawn_review_status is None
    assert edition.table["review_status"] == "agent_reviewed"
    assert edition.table["reviewed_by"] == "agent:reviewer"


def test_an_unreviewed_delta_edition_withdraws_nothing(tmp_path: Path) -> None:
    edition = materialise_edition(_modelo(tmp_path, successor_extra='predecessor = "2024"\n'), "2025")

    assert edition.withdrawn_review_status is None
    assert edition.table["review_status"] == "pending_review"
