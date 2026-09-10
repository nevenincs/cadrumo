"""Isolated staging of one edition for the published-layout witness.

The witness is a copy of the modelo holding only the target edition. Pruning
the sibling editions is what isolates it, and it deletes precisely the chain an
edition naming a predecessor inherits from. These tests drive the real staging
function and the real directory loader over on-disk trees: a delta edition must
stage as the complete edition it stands for, a delta whose predecessor is gone
must be refused, and an edition stating every row must stage byte-for-byte as
the copy it always was.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.edition_materialisation import materialise_edition
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.loader import load_modelo_directory
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..pipeline.cli import _stage_isolated_edition

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LEGAL_REF = "ley-58-2003:art-29"
_MANIFEST = (
    "[modelo]\n"
    'id = "999"\n'
    'tax_domain = "iva"\n'
    'cadence = "annual"\n'
    'jurisdiction = "ES-AEAT"\n'
    f'legal_refs = ["{_LEGAL_REF}"]\n'
    'source_refs = ["aeat-manual"]\n'
)


def _casilla(revision_id: str, casilla_id: str, *, number: str, lineage: str) -> str:
    return (
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{number}"\n'
        'section = ["liquidacion"]\n'
        f'continuidad_id = "{lineage}"\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        'source_refs = ["aeat-manual"]\n\n'
    )


def _write_edition(
    modelo_dir: Path,
    revision_id: str,
    *,
    year: int,
    casillas: str,
    predecessor: str | None = None,
    retire: tuple[str, str] | None = None,
) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    (revision_dir / "casillas").mkdir(parents=True)
    predecessor_line = f'predecessor = "{predecessor}"\n' if predecessor is not None else ""
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        'source_refs = ["aeat-manual"]\n'
        f"{predecessor_line}",
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(casillas, encoding="utf-8", newline="\n")
    if retire is not None:
        lineage, from_revision = retire
        (revision_dir / "casilla_continuidad_evolutions").mkdir()
        (revision_dir / "casilla_continuidad_evolutions" / "0001-evolutions.toml").write_text(
            f'[[revisions."{revision_id}".casilla_continuidad_evolutions]]\n'
            f'id = "retire-{lineage}"\n'
            f'continuidad_id = "{lineage}"\n'
            f'from_revision = "{from_revision}"\n'
            f'to_revision = "{revision_id}"\n'
            'evolution_kind = "retired"\n'
            f'legal_refs = ["{_LEGAL_REF}"]\n'
            'source_refs = ["aeat-manual"]\n',
            encoding="utf-8",
            newline="\n",
        )


def _modelo(root: Path) -> Path:
    modelo_dir = root / "source" / "999"
    modelo_dir.mkdir(parents=True)
    (modelo_dir / "manifest.toml").write_text(_MANIFEST, encoding="utf-8", newline="\n")
    return modelo_dir


def _migrated_chain(root: Path) -> Path:
    """2023 states everything; 2024 and 2025 each state only what changed against their predecessor."""
    modelo_dir = _modelo(root)
    _write_edition(
        modelo_dir,
        "2023",
        year=2023,
        casillas=(
            _casilla("2023", "0001", number="1", lineage="base-imponible")
            + _casilla("2023", "0002", number="2", lineage="cuota-integra")
            + _casilla("2023", "0003", number="3", lineage="deduccion-retirada")
        ),
    )
    _write_edition(
        modelo_dir,
        "2024",
        year=2024,
        predecessor="2023",
        casillas=_casilla("2024", "0002", number="22", lineage="cuota-integra"),
    )
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        predecessor="2024",
        casillas=_casilla("2025", "0004", number="4", lineage="recargo-nuevo"),
        retire=("deduccion-retirada", "2024"),
    )
    return modelo_dir


def _full_copy_modelo(root: Path) -> Path:
    modelo_dir = _modelo(root)
    for revision_id, year in (("2024", 2024), ("2025", 2025)):
        _write_edition(
            modelo_dir,
            revision_id,
            year=year,
            casillas=(
                _casilla(revision_id, "0001", number="1", lineage="base-imponible")
                + _casilla(revision_id, "0002", number="2", lineage="cuota-integra")
            ),
        )
    return modelo_dir


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _without_label_origin_fallback(revision: ModeloRevision) -> ModeloRevision:
    """Drop the one locale key the live load adds to rows it inherited, which no staged tree can author."""
    return revision.model_copy(
        update={
            "casillas": tuple(
                casilla.model_copy(
                    update={"localization_keys": casilla.localization_keys[:1] + casilla.localization_keys[2:]}
                )
                if casilla.id != "0004"
                else casilla
                for casilla in revision.casillas
            ),
        },
    )


def test_a_migrated_successor_stages_as_the_complete_edition_it_stands_for(tmp_path: Path) -> None:
    source = _migrated_chain(tmp_path)
    live = load_modelo_directory(source).revisions["2025"]

    staged_root = _stage_isolated_edition(source, tmp_path / "staged" / "999", revision="2025")

    assert sorted(path.name for path in (staged_root / "revisions").iterdir()) == ["2025.toml"]
    assert "predecessor" not in (staged_root / "revisions" / "2025.toml").read_text(encoding="utf-8")
    staged_definition = load_modelo_directory(staged_root)
    assert tuple(staged_definition.revisions) == ("2025",)
    staged = staged_definition.revisions["2025"]
    assert staged.predecessor is None
    assert [(row.id, row.number, row.continuidad_id) for row in staged.casillas] == [
        ("0001", "1", "base-imponible"),
        ("0002", "22", "cuota-integra"),
        ("0004", "4", "recargo-nuevo"),
    ]
    assert staged.model_copy(update={"predecessor": live.predecessor}) == _without_label_origin_fallback(live)


def test_a_staged_successor_equals_what_the_entry_point_materialises(tmp_path: Path) -> None:
    source = _migrated_chain(tmp_path)
    edition = materialise_edition(source, "2025")

    staged_root = _stage_isolated_edition(source, tmp_path / "staged" / "999", revision="2025")

    assert edition.inherits_from == "2024"
    assert materialise_edition(staged_root, "2025").table == edition.table
    assert materialise_edition(staged_root, "2025").inherits_from is None


def test_a_staged_delta_whose_predecessor_was_removed_is_refused(tmp_path: Path) -> None:
    source = _migrated_chain(tmp_path)
    shutil.rmtree(source / "revisions" / "2024")
    staged_root = tmp_path / "staged" / "999"

    with pytest.raises(RegistryLoadError, match="2024"):
        _stage_isolated_edition(source, staged_root, revision="2025")

    assert not staged_root.exists()


def test_pruning_without_materialising_leaves_a_successor_naming_a_deleted_predecessor(tmp_path: Path) -> None:
    """The defect materialising prevents: the pruned copy no longer loads as an edition at all."""
    source = _migrated_chain(tmp_path)
    pruned = tmp_path / "pruned" / "999"
    shutil.copytree(source, pruned)
    for entry in (pruned / "revisions").iterdir():
        if entry.name != "2025":
            shutil.rmtree(entry)

    with pytest.raises(RegistryLoadError, match="2024"):
        load_modelo_directory(pruned)


def test_an_edition_stating_every_row_stages_as_an_unchanged_copy(tmp_path: Path) -> None:
    source = _full_copy_modelo(tmp_path)

    staged_root = _stage_isolated_edition(source, tmp_path / "staged" / "999", revision="2025")

    assert sorted(path.name for path in (staged_root / "revisions").iterdir()) == ["2025"]
    assert _tree_bytes(staged_root / "revisions" / "2025") == _tree_bytes(source / "revisions" / "2025")
    assert (staged_root / "manifest.toml").read_bytes() == (source / "manifest.toml").read_bytes()
    assert load_modelo_directory(staged_root).revisions["2025"] == load_modelo_directory(source).revisions["2025"]
