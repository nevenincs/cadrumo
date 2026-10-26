"""Every compiled revision is read by a type-column instrument, declares no export, or is named unchecked.

The generated-tree gate reads derivation records out of generation manifests; the
hand-authored gate reads an authored ``export_layouts`` tree where one exists and
the layout the revision resolves where none does. A revision in neither input is
read by nobody, so both gates report clean without having looked at it. The
partition asked here comes from the compiled registry, not from a directory glob,
so such a revision surfaces by name instead of vanishing.

Eligibility is a record FIELD rather than a declared layout, because a type
column types wire slots: a revision whose layout carries no record -- Modelo
100's ``xml_dictionary`` editions -- has nothing either instrument could compare,
which is different from having something nobody compared.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from ..analysis.hand_authored_type_column import hand_authored_revisions
from ..analysis.type_column_coverage import (
    TypeColumnCoverage,
    type_column_coverage,
)
from ..compiler.authority import compiled_bundled_authority
from ..compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MODELO = "232"
_BASE = "2016-2017"
_DELTA = "2018-y-siguientes"


@pytest.fixture(scope="module")
def shipped():
    authority = compiled_bundled_authority()
    return authority, type_column_coverage(authority.modelos, modelos_root=bundled_path("registry", "aeat", "modelos"))


def test_no_shipped_revision_declaring_an_export_is_left_unread(shipped) -> None:
    _authority, rows = shipped
    unchecked = [row.render() for row in rows if row.coverage is TypeColumnCoverage.UNCHECKED]
    assert not unchecked, "revisions no type-column instrument reads:\n" + "\n".join(unchecked)


def test_the_partition_covers_every_compiled_revision_once(shipped) -> None:
    authority, rows = shipped
    compiled = {f"{modelo.id}/{revision}" for modelo in authority.modelos for revision in modelo.revisions}
    subjects = [row.subject for row in rows]
    assert len(subjects) == len(set(subjects))
    assert set(subjects) == compiled


def test_the_partition_agrees_with_what_each_gate_actually_reads(shipped) -> None:
    """Coverage is only true if each gate's real input is exactly the revisions credited to it."""
    authority, rows = shipped
    by_state = {state: {row.subject for row in rows if row.coverage is state} for state in TypeColumnCoverage}
    manifests = bundled_path("registry", "aeat", "modelos").glob(
        f"*/revisions/*/export/{EXPORT_FRAGMENT_PROVENANCE_FILENAME}"
    )
    generated_gate_input = {f"{path.parts[-5]}/{path.parts[-3]}" for path in manifests}
    hand_gate_input = {f"{modelo}/{revision}" for modelo, revision, _root in hand_authored_revisions(authority)}

    assert by_state[TypeColumnCoverage.GENERATED_MANIFEST] == generated_gate_input
    assert by_state[TypeColumnCoverage.HAND_AUTHORED_LAYOUTS] == hand_gate_input
    assert by_state[TypeColumnCoverage.NO_EXPORT_SURFACE], "sanity: some revisions declare no export surface"


def _copied_modelo(tmp_path: Path) -> Path:
    modelos_root = tmp_path / "modelos"
    shutil.copytree(bundled_path("registry", "aeat", "modelos", _MODELO), modelos_root / _MODELO)
    return modelos_root


def _coverage(modelos_root: Path) -> dict[str, tuple[TypeColumnCoverage, str | None]]:
    rows = type_column_coverage([load_modelo_directory(modelos_root / _MODELO)], modelos_root=modelos_root)
    return {row.revision: (row.coverage, row.reason) for row in rows}


def test_a_revision_without_its_generation_manifest_moves_to_the_other_instrument(tmp_path: Path) -> None:
    """Removing the manifest moves the revision between instruments, never out of the partition.

    Losing the manifest takes the revision out of the generated gate's input,
    and the hand-authored screen picks it up from the layout it resolves. What
    must never happen is the revision quietly leaving the partition, which is
    the state where both gates read clean without having looked at it.
    """
    modelos_root = _copied_modelo(tmp_path)
    assert _coverage(modelos_root)[_DELTA] == (TypeColumnCoverage.GENERATED_MANIFEST, None)

    (modelos_root / _MODELO / "revisions" / _DELTA / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME).unlink()
    coverage = _coverage(modelos_root)

    assert _DELTA in coverage
    assert coverage[_DELTA] == (TypeColumnCoverage.HAND_AUTHORED_LAYOUTS, None)
    assert coverage[_BASE] == (TypeColumnCoverage.GENERATED_MANIFEST, None)


def test_a_manifest_less_delta_edition_is_read_from_the_layout_it_resolves(tmp_path: Path) -> None:
    """A delta edition with no manifest is read, not reported as unread.

    This is the case the partition used to get wrong. A delta states no layout
    of its own, so keying on the directory listing left it credited to neither
    instrument while the hand-authored screen could resolve and compare it
    perfectly well.
    """
    modelos_root = _copied_modelo(tmp_path)
    revision_dir = modelos_root / _MODELO / "revisions" / _DELTA
    manifest = revision_dir / "revision.toml"
    # The edition states its own predecessor, so the delta this test needs is
    # the authored one. Asserting it rather than injecting a second declaration
    # keeps the test honest if the edition is ever re-rooted: injecting made a
    # duplicate TOML key the moment the edition gained a predecessor of its own.
    assert f'predecessor = "{_BASE}"' in manifest.read_text(encoding="utf-8")
    (revision_dir / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME).unlink()

    state, reason = _coverage(modelos_root)[_DELTA]

    assert state is TypeColumnCoverage.HAND_AUTHORED_LAYOUTS
    assert reason is None


def test_an_authored_tree_beside_a_manifest_is_unchecked_not_credited_to_either_gate(tmp_path: Path) -> None:
    """The hand-authored gate skips a manifest-bearing revision, so authored layouts there go unread."""
    modelos_root = _copied_modelo(tmp_path)
    revision_dir = modelos_root / _MODELO / "revisions" / _DELTA
    fragment = sorted((revision_dir / "export").glob("*.toml"))[-1]
    (revision_dir / "export_layouts").mkdir()
    fragment.rename(revision_dir / "export_layouts" / fragment.name)

    state, reason = _coverage(modelos_root)[_DELTA]

    assert state is TypeColumnCoverage.UNCHECKED
    assert reason is not None
    assert "both" in reason
