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
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ...compiler.loader import load_modelo_directory
from ...tests.edition_staging_tree_support import (
    edition_casilla,
    migrated_chain,
    staged_modelo,
    write_edition,
)
from ..edition_candidate_staging import stage_continuity_metadata
from ..tree_validation import load_continuity_metadata_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _editions(source: Path) -> tuple[str, str, str]:
    """The three editions of a staged chain, oldest first, as the loader resolves them."""
    first, second, third = tuple(load_modelo_directory(source).revisions)
    return first, second, third


def _full_copy_modelo(root: Path) -> Path:
    modelo_dir = staged_modelo(root)
    horizon = filing_year_envelope().horizon
    years = (horizon - 2, horizon - 1, horizon)
    for year in years:
        revision_id = str(year)
        write_edition(
            modelo_dir,
            revision_id,
            year=year,
            casillas=(
                edition_casilla(revision_id, "0001", number="1", lineage="base-imponible")
                + edition_casilla(revision_id, "0002", number="2", lineage="cuota-integra")
            ),
            retire=("deduccion-retirada", str(years[0])) if year == years[-1] else None,
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
    source = migrated_chain(tmp_path)
    live = load_modelo_directory(source)
    first, second, third = _editions(source)

    metadata_root = stage_continuity_metadata(source, tmp_path / "stage", revision=third)

    assert metadata_root is not None
    assert sorted(path.name for path in (metadata_root / "revisions").iterdir()) == [first, second]
    witness = load_continuity_metadata_modelo(metadata_root, modelo_id="999", revision_id=third)
    staged = witness.revisions[second]
    assert staged.predecessor is None
    assert _rows(staged) == [
        ("0001", "1", "base-imponible"),
        ("0002", "22", "cuota-integra"),
        ("0003", "3", "deduccion-retirada"),
    ]
    assert _comparable(staged) == _comparable(live.revisions[second])
    assert _comparable(witness.revisions[first]) == _comparable(live.revisions[first])


def test_successors_inheriting_through_the_excluded_target_still_stage_complete(tmp_path: Path) -> None:
    """Staging the first edition leaves out the edition both successors inherit through."""
    source = migrated_chain(tmp_path)
    live = load_modelo_directory(source)
    first, second, third = _editions(source)

    metadata_root = stage_continuity_metadata(source, tmp_path / "stage", revision=first)

    assert metadata_root is not None
    witness = load_continuity_metadata_modelo(metadata_root, modelo_id="999", revision_id=first)
    assert tuple(witness.revisions) == (second, third)
    assert _rows(witness.revisions[third]) == [
        ("0001", "1", "base-imponible"),
        ("0002", "22", "cuota-integra"),
        ("0004", "4", "recargo-nuevo"),
    ]
    for sibling in (second, third):
        assert _comparable(witness.revisions[sibling]) == _comparable(live.revisions[sibling])


def test_copying_an_inheriting_sibling_raw_leaves_a_witness_that_cannot_load(tmp_path: Path) -> None:
    """The defect complete staging prevents: the raw rows of a delta name a predecessor the witness lacks."""
    source = migrated_chain(tmp_path)
    raw_witness = tmp_path / "raw" / "999"
    shutil.copytree(source, raw_witness)
    first = _editions(source)[0]
    shutil.rmtree(raw_witness / "revisions" / first)

    with pytest.raises(RegistryLoadError, match=first):
        load_modelo_directory(raw_witness)


def test_the_declared_predecessor_chain_is_followed_not_the_evolution_chain(tmp_path: Path) -> None:
    """The last edition's only evolution record points at a year no edition carries.

    Its declared chain is the middle edition, then the first.

    The loader accepts the tree, because an evolution's origin names no
    inheritance edge. Staging must follow the same declared edges the loader
    does: a sibling's inherited rows come from the middle and first editions, and the record
    pointing elsewhere decides nothing.
    """
    non_edition = str(int(_editions(migrated_chain(tmp_path / "probe"))[0]) - 1)
    source = migrated_chain(tmp_path, retire_from=non_edition)
    live = load_modelo_directory(source)
    first, _second, third = _editions(source)
    assert [str(item.from_revision) for item in live.revisions[third].casilla_continuidad_evolutions] == [non_edition]

    target_last = stage_continuity_metadata(source, tmp_path / "stage-last", revision=third)
    target_first = stage_continuity_metadata(source, tmp_path / "stage-first", revision=first)

    assert target_last is not None
    assert target_first is not None
    witness = load_continuity_metadata_modelo(target_first, modelo_id="999", revision_id=first)
    assert _rows(witness.revisions[third]) == [
        ("0001", "1", "base-imponible"),
        ("0002", "22", "cuota-integra"),
        ("0004", "4", "recargo-nuevo"),
    ]
    assert _comparable(witness.revisions[third]) == _comparable(live.revisions[third])


def test_a_modelo_whose_editions_state_every_row_stages_byte_for_byte(tmp_path: Path) -> None:
    source = _full_copy_modelo(tmp_path)
    first, second, third = _editions(source)

    metadata_root = stage_continuity_metadata(source, tmp_path / "stage", revision=third)

    assert metadata_root is not None
    assert sorted(path.name for path in (metadata_root / "revisions").iterdir()) == [first, second]
    assert (metadata_root / "manifest.toml").read_bytes() == (source / "manifest.toml").read_bytes()
    for sibling in (first, second):
        assert _tree_bytes(metadata_root / "revisions" / sibling) == _tree_bytes(source / "revisions" / sibling)
