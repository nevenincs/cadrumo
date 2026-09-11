"""Cache identity of a delta edition follows the physical files, never the expansion.

An edition that names a predecessor is expanded at load time: the loader
inherits the predecessor's casilla rows into it, so the compiled successor
holds rows its own files never state. Every compiled cache is keyed on the
registry fingerprint, and that fingerprint must describe what was READ, not
what was expanded. Two consequences follow, each proven against an on-disk
tree driven through the real modelo-directory loader and the real registry-tree
loader whose fingerprint keys the compiled registry:

- editing any physical file the expansion reads -- the delta edition's own
  fragment, or the predecessor fragment the successor inherits from -- moves
  the fingerprint and yields the new content;
- the expansion itself contributes nothing: the fingerprint is equal before
  and after materialisation, equal across repeated loads of identical files,
  and equal row for row to an independent reconstruction built from the files
  on disk alone.

Each invalidation proof carries its teeth: the compiled cache still holds the
superseded expansion under the pre-edit key, so only the fingerprint moving
stands between the caller and stale output.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cadrumo.core.hashing import blake2b_hex
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..compiler._loader_internals import (
    _collect_modelo_directory_fingerprints,
    _collect_registry_tree_fingerprints_uncached,
    _load_modelo_directory_cached,
)
from ..compiler.loader import _load_registry_tree_cached, load_modelo_directory, load_registry_tree
from ..compiler.loader_fingerprints import clear_fingerprint_cache
from ..conformance.tests._loader_directory_mode_support import (
    write_fragmented_revision,
    write_minimal_shared_catalogues,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

type _Fingerprint = tuple[str, int, int, str]
type _Rows = list[tuple[str, str, str | None]]

_MODELO_ID = "999"
_LEGAL_REF = "ley-58-2003:art-29"

_MANIFEST_TOML = f"""\
[modelo]
id = "{_MODELO_ID}"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["{_LEGAL_REF}"]
source_refs = ["aeat-manual"]
"""


def _revision(revision_id: str, *, predecessor: str | None) -> str:
    predecessor_line = f'predecessor = "{predecessor}"\n' if predecessor is not None else ""
    return (
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {revision_id}-01-01\n"
        f"valid_to = {revision_id}-12-31\n"
        f'period_selector = {{ years = [{revision_id}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        'source_refs = ["aeat-manual"]\n'
        f"{predecessor_line}\n"
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


def _write_tree(tmp_path: Path) -> Path:
    """A 2024 edition with two rows and a 2025 delta edition restating one of them."""
    registry_root = tmp_path / "registry" / "aeat"
    write_minimal_shared_catalogues(registry_root / "legal", years=(2024, 2025))
    modelo_dir = registry_root / "modelos" / _MODELO_ID
    modelo_dir.mkdir(parents=True)
    (modelo_dir / "manifest.toml").write_text(_MANIFEST_TOML, encoding="utf-8", newline="\n")
    write_fragmented_revision(
        modelo_dir / "revisions" / "2024",
        _revision("2024", predecessor=None)
        + _casilla("2024", "01", number="01", lineage="base")
        + _casilla("2024", "02", number="02", lineage="cuota"),
    )
    write_fragmented_revision(
        modelo_dir / "revisions" / "2025",
        _revision("2025", predecessor="2024") + _casilla("2025", "02", number="22", lineage="cuota"),
    )
    return registry_root.resolve()


def _modelo_dir(registry_root: Path) -> Path:
    return registry_root / "modelos" / _MODELO_ID


def _casilla_fragment(registry_root: Path, revision_id: str) -> Path:
    return _modelo_dir(registry_root) / "revisions" / revision_id / "casillas" / "0001-casillas.toml"


def _rewrite(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"sanity: {old!r} must be present in {path.name} for the edit to mean anything"
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def _rows(definition: ModeloDefinition, revision_id: str) -> _Rows:
    return [
        (casilla.id, casilla.number, casilla.continuidad_id) for casilla in definition.revisions[revision_id].casillas
    ]


def _tree_rows(registry_root: Path, revision_id: str) -> _Rows:
    modelos, _catalogues = load_registry_tree(registry_root)
    return _rows(next(modelo for modelo in modelos if modelo.id == _MODELO_ID), revision_id)


def _cached_tree_rows(registry_root: Path, fingerprints: tuple[_Fingerprint, ...], revision_id: str) -> _Rows:
    modelos, _catalogues = _load_registry_tree_cached(str(registry_root), fingerprints)
    return _rows(next(modelo for modelo in modelos if modelo.id == _MODELO_ID), revision_id)


def _changed_paths(before: tuple[_Fingerprint, ...], after: tuple[_Fingerprint, ...]) -> set[str]:
    return {row[0] for row in set(before) ^ set(after)}


#: The successor as expanded from the unedited tree: the inherited ``base`` row
#: first, then the stated ``cuota`` row in the slot of the row it supersedes.
_EXPANDED_2025: _Rows = [("01", "01", "base"), ("02", "22", "cuota")]


@pytest.fixture(autouse=True)
def _cold_fingerprint_cache() -> None:
    clear_fingerprint_cache()


def test_editing_the_delta_edition_invalidates_and_serves_its_new_content(tmp_path: Path) -> None:
    registry_root = _write_tree(tmp_path)
    modelo_dir = _modelo_dir(registry_root)
    delta = _casilla_fragment(registry_root, "2025")

    assert _tree_rows(registry_root, "2025") == _EXPANDED_2025
    assert _rows(load_modelo_directory(modelo_dir), "2025") == _EXPANDED_2025
    tree_before = _collect_registry_tree_fingerprints_uncached(registry_root)
    modelo_before = _collect_modelo_directory_fingerprints(modelo_dir)

    _rewrite(delta, 'number = "22"', 'number = "23"')

    assert _changed_paths(tree_before, _collect_registry_tree_fingerprints_uncached(registry_root)) == {str(delta)}
    assert _changed_paths(modelo_before, _collect_modelo_directory_fingerprints(modelo_dir)) == {str(delta)}
    edited: _Rows = [("01", "01", "base"), ("02", "23", "cuota")]
    assert _tree_rows(registry_root, "2025") == edited
    assert _rows(load_modelo_directory(modelo_dir), "2025") == edited

    assert _cached_tree_rows(registry_root, tree_before, "2025") == _EXPANDED_2025, (
        "the compiled registry must still hold the pre-edit expansion under the pre-edit key, "
        "or the invalidation above proves nothing about the fingerprint"
    )
    assert _rows(_load_modelo_directory_cached(str(modelo_dir), modelo_before), "2025") == _EXPANDED_2025


def test_editing_the_predecessor_invalidates_the_successor_that_inherits_from_it(tmp_path: Path) -> None:
    """The successor's own files are untouched; only the inherited source changes.

    A fingerprint keyed on the successor's files alone would hand back the
    successor expanded from the superseded predecessor.
    """
    registry_root = _write_tree(tmp_path)
    modelo_dir = _modelo_dir(registry_root)
    predecessor = _casilla_fragment(registry_root, "2024")
    successor_files = sorted((modelo_dir / "revisions" / "2025").rglob("*.toml"))
    successor_bytes = [path.read_bytes() for path in successor_files]

    assert _tree_rows(registry_root, "2025") == _EXPANDED_2025
    assert _rows(load_modelo_directory(modelo_dir), "2025") == _EXPANDED_2025
    tree_before = _collect_registry_tree_fingerprints_uncached(registry_root)
    modelo_before = _collect_modelo_directory_fingerprints(modelo_dir)

    _rewrite(predecessor, 'number = "01"', 'number = "11"')

    assert [path.read_bytes() for path in successor_files] == successor_bytes
    assert _changed_paths(tree_before, _collect_registry_tree_fingerprints_uncached(registry_root)) == {
        str(predecessor)
    }
    assert _changed_paths(modelo_before, _collect_modelo_directory_fingerprints(modelo_dir)) == {str(predecessor)}
    reinherited: _Rows = [("01", "11", "base"), ("02", "22", "cuota")]
    assert _tree_rows(registry_root, "2025") == reinherited
    assert _rows(load_modelo_directory(modelo_dir), "2025") == reinherited

    assert _cached_tree_rows(registry_root, tree_before, "2025") == _EXPANDED_2025, (
        "the compiled registry must still hold the successor expanded from the old predecessor under the "
        "pre-edit key, or the invalidation above proves nothing about the fingerprint"
    )
    assert _rows(_load_modelo_directory_cached(str(modelo_dir), modelo_before), "2025") == _EXPANDED_2025


def _physical_modelo_fingerprints(modelo_dir: Path) -> set[_Fingerprint]:
    """Reconstruct the modelo fingerprint from the files on disk, knowing nothing of the loader."""
    rows: set[_Fingerprint] = set()
    for directory, _subdirectories, filenames in os.walk(modelo_dir):
        directory_path = Path(directory)
        stat = directory_path.stat()
        rows.add((str(directory_path), stat.st_size, stat.st_mtime_ns, ""))
        for filename in filenames:
            if filename.endswith(".toml"):
                path = directory_path / filename
                stat = path.stat()
                rows.add((str(path), stat.st_size, stat.st_mtime_ns, blake2b_hex(path.read_bytes())))
    return rows


def test_the_fingerprint_is_a_function_of_the_physical_files_alone(tmp_path: Path) -> None:
    """Materialisation changes what the successor holds and nothing about its cache key.

    The successor's single stated row expands to two, yet the key before any
    expansion exists, the key after it, and the key rebuilt from the files by
    a reconstruction that never loads anything are one and the same. The
    successor's casilla row in the key digests the one row it states, so no
    expanded content reaches the key.
    """
    registry_root = _write_tree(tmp_path)
    modelo_dir = _modelo_dir(registry_root)
    delta = _casilla_fragment(registry_root, "2025")

    modelo_before = _collect_modelo_directory_fingerprints(modelo_dir)
    tree_before = _collect_registry_tree_fingerprints_uncached(registry_root)

    assert _tree_rows(registry_root, "2025") == _EXPANDED_2025
    expanded = load_modelo_directory(modelo_dir)
    assert _rows(expanded, "2025") == _EXPANDED_2025
    assert delta.read_text(encoding="utf-8").count("[[revisions.") == 1, (
        "sanity: the successor must state fewer rows than it expands to, or nothing was materialised"
    )

    modelo_after = _collect_modelo_directory_fingerprints(modelo_dir)
    assert modelo_after == modelo_before
    assert _collect_registry_tree_fingerprints_uncached(registry_root) == tree_before

    physical = _physical_modelo_fingerprints(modelo_dir)
    assert set(modelo_after) == physical
    assert {row for row in tree_before if Path(row[0]).is_relative_to(modelo_dir)} == physical

    delta_stat = delta.stat()
    assert [row for row in modelo_after if row[0] == str(delta)] == [
        (str(delta), delta_stat.st_size, delta_stat.st_mtime_ns, blake2b_hex(delta.read_bytes()))
    ]

    assert load_modelo_directory(modelo_dir) is expanded, (
        "a second load of identical files must resolve to the same cache entry, never a second expansion"
    )
