"""The continuity witness staged beside an isolated generated-export candidate.

The witness holds every sibling of the target edition and never the target
itself. Once a modelo's editions name predecessors, a sibling's own files can be
only the rows it changed, and the edition it inherits through may be the very
target the witness must leave out. These tests drive the real staging function
and the real directory loader over on-disk trees: an inheriting sibling must
stage as the complete edition it stands for, the chain resolved must be the
declared predecessor chain rather than the continuity evolution records, and a
modelo whose editions each state every row must stage byte-for-byte as before.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.loader import load_modelo_directory
from ..pipeline._tree_validation import _load_continuity_metadata_modelo
from ..pipeline.candidate_staging import stage_continuity_metadata

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


def _migrated_chain(root: Path, *, retire_from: str = "2024") -> Path:
    """2023 states everything; 2024 names 2023, and 2025 names 2024, each stating only what changed.

    ``retire_from`` is the ``from_revision`` of 2025's one retirement record,
    which is the only link the continuity evolution chain offers out of 2025.
    """
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
        retire=("deduccion-retirada", retire_from),
    )
    return modelo_dir


def _full_copy_modelo(root: Path) -> Path:
    modelo_dir = _modelo(root)
    for revision_id, year in (("2023", 2023), ("2024", 2024), ("2025", 2025)):
        _write_edition(
            modelo_dir,
            revision_id,
            year=year,
            casillas=(
                _casilla(revision_id, "0001", number="1", lineage="base-imponible")
                + _casilla(revision_id, "0002", number="2", lineage="cuota-integra")
            ),
            retire=("deduccion-retirada", "2023") if revision_id == "2025" else None,
        )
    return modelo_dir


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _rows(revision: ModeloRevision) -> list[tuple[str, str, str | None]]:
    return [(str(row.id), row.number, row.continuidad_id) for row in revision.casillas]


def _comparable(revision: ModeloRevision) -> dict[str, object]:
    """The typed dump with the two things a standalone copy cannot carry removed.

    A staged complete edition names no predecessor, and the live load adds one
    locale fallback key to each row it inherited, keyed on the edition that
    states the row, which no single-edition source can author.
    """
    return STR_KEYED_MAPPING_ADAPTER.validate_python(
        revision.model_dump(
            mode="json",
            exclude={"predecessor": True, "casillas": {"__all__": {"localization_keys"}}},
        ),
    )


def test_an_inheriting_predecessor_stages_as_the_complete_edition_it_stands_for(tmp_path: Path) -> None:
    source = _migrated_chain(tmp_path)
    live = load_modelo_directory(source)

    metadata_root = stage_continuity_metadata(source, tmp_path / "stage", revision="2025")

    assert metadata_root is not None
    assert sorted(path.name for path in (metadata_root / "revisions").iterdir()) == ["2023.toml", "2024.toml"]
    witness = _load_continuity_metadata_modelo(metadata_root, modelo_id="999", revision_id="2025")
    staged = witness.revisions["2024"]
    assert staged.predecessor is None
    assert _rows(staged) == [
        ("0001", "1", "base-imponible"),
        ("0002", "22", "cuota-integra"),
        ("0003", "3", "deduccion-retirada"),
    ]
    assert _comparable(staged) == _comparable(live.revisions["2024"])
    assert _comparable(witness.revisions["2023"]) == _comparable(live.revisions["2023"])


def test_successors_inheriting_through_the_excluded_target_still_stage_complete(tmp_path: Path) -> None:
    """Staging the first edition leaves out the edition both successors inherit through."""
    source = _migrated_chain(tmp_path)
    live = load_modelo_directory(source)

    metadata_root = stage_continuity_metadata(source, tmp_path / "stage", revision="2023")

    assert metadata_root is not None
    witness = _load_continuity_metadata_modelo(metadata_root, modelo_id="999", revision_id="2023")
    assert tuple(witness.revisions) == ("2024", "2025")
    assert _rows(witness.revisions["2025"]) == [
        ("0001", "1", "base-imponible"),
        ("0002", "22", "cuota-integra"),
        ("0004", "4", "recargo-nuevo"),
    ]
    for sibling in ("2024", "2025"):
        assert _comparable(witness.revisions[sibling]) == _comparable(live.revisions[sibling])


def test_copying_an_inheriting_sibling_raw_leaves_a_witness_that_cannot_load(tmp_path: Path) -> None:
    """The defect complete staging prevents: the raw rows of a delta name a predecessor the witness lacks."""
    source = _migrated_chain(tmp_path)
    raw_witness = tmp_path / "raw" / "999"
    shutil.copytree(source, raw_witness)
    shutil.rmtree(raw_witness / "revisions" / "2023")

    with pytest.raises(RegistryLoadError, match="2023"):
        load_modelo_directory(raw_witness)


def test_the_declared_predecessor_chain_is_followed_not_the_evolution_chain(tmp_path: Path) -> None:
    """2025's only evolution record points at 2022, which is no edition; its declared chain is 2024 then 2023.

    The loader accepts the tree, because an evolution's origin names no
    inheritance edge. Staging must follow the same declared edges the loader
    does: a sibling's inherited rows come from 2024 and 2023, and the record
    pointing elsewhere decides nothing.
    """
    source = _migrated_chain(tmp_path, retire_from="2022")
    live = load_modelo_directory(source)
    assert [str(item.from_revision) for item in live.revisions["2025"].casilla_continuidad_evolutions] == ["2022"]

    target_2025 = stage_continuity_metadata(source, tmp_path / "stage-2025", revision="2025")
    target_2023 = stage_continuity_metadata(source, tmp_path / "stage-2023", revision="2023")

    assert target_2025 is not None
    assert target_2023 is not None
    witness = _load_continuity_metadata_modelo(target_2023, modelo_id="999", revision_id="2023")
    assert _rows(witness.revisions["2025"]) == [
        ("0001", "1", "base-imponible"),
        ("0002", "22", "cuota-integra"),
        ("0004", "4", "recargo-nuevo"),
    ]
    assert _comparable(witness.revisions["2025"]) == _comparable(live.revisions["2025"])


def test_a_modelo_whose_editions_state_every_row_stages_byte_for_byte(tmp_path: Path) -> None:
    source = _full_copy_modelo(tmp_path)

    metadata_root = stage_continuity_metadata(source, tmp_path / "stage", revision="2025")

    assert metadata_root is not None
    assert sorted(path.name for path in (metadata_root / "revisions").iterdir()) == ["2023", "2024"]
    assert (metadata_root / "manifest.toml").read_bytes() == (source / "manifest.toml").read_bytes()
    for sibling in ("2023", "2024"):
        assert _tree_bytes(metadata_root / "revisions" / sibling) == _tree_bytes(source / "revisions" / sibling)
