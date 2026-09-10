"""The public entry point that resolves one edition into its full-copy raw revision table."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..edition_materialisation import materialise_edition
from ..errors import RegistryLoadError
from ._loader_directory_mode_support import _write_standard_manifest

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
