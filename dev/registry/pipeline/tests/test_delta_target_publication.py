"""Staging and publishing a generated export tree whose target edition inherits.

Modelo 210 is authored as a delta chain: its root edition states every casilla
row and each later edition names its predecessor and inherits the rows it does
not restate. These tests drive the real candidate staging, generator, validator
and publication entry points over a temporary registry copy of that chain, with
no substituted component.

The candidate must be the complete edition the loader resolves, naming no
predecessor, and a delta whose predecessor is gone must be refused rather than
staged thin. Publication swaps in the export tree and nothing else: the loader
derives every addressed casilla's ``export_refs`` from that tree, inherited
rows included, so a published delta resolves to exactly the references its
full-copy form carries.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.revision_contracts import DeclaredPredecessor

from ...compiler.authority import compiled_bundled_authority
from ...compiler.edition_materialisation import MaterialisedEdition, materialise_edition
from ...compiler.loader import load_modelo_directory
from .._tree_validation import GeneratedExportTreeValidationContext
from ..candidate_staging import (
    ignore_export_authority_directories,
    stage_continuity_metadata,
    stage_generated_export_candidate,
)
from ..cli import (
    GeneratedTreeInvocation,
    PreparedGeneratedTreeInvocation,
    check_prepared_invocation,
    publish_prepared_invocation,
    stage_published_modelo,
    supporting_modelos,
)
from ..export_fragment_provenance import ExportFragmentTarget
from ..render_check import revision_render_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MODELO = "210"
_REVISION = "2026-y-siguientes"
_SOURCE_REF = "aeat-dr-210-2026"
_FILING_YEAR = 2026
_PERIOD = "EVENT-1"


def _registry_copy(root: Path) -> Path:
    """Copy the authority a candidate is staged from: every top-level tree plus the target modelo."""
    source = bundled_path("registry", "aeat")
    target = root / "registry" / "aeat"
    target.mkdir(parents=True)
    for entry in source.iterdir():
        if entry.is_dir() and entry.name != "modelos":
            shutil.copytree(entry, target / entry.name)
    shutil.copytree(source / "modelos" / _MODELO, target / "modelos" / _MODELO)
    return target


def _declared_predecessor(modelo_root: Path, revision: str) -> str:
    """Return the predecessor the edition's own manifest names, refusing an edition that names none."""
    predecessor = materialise_edition(modelo_root, revision).inherits_from
    assert predecessor is not None, f"edition {_MODELO}/{revision} must inherit, or it is not a delta target"
    return predecessor


def _root_edition(modelo_root: Path) -> str:
    """Walk the live predecessor chain back to the edition that states every row."""
    revision = _REVISION
    while (predecessor := materialise_edition(modelo_root, revision).inherits_from) is not None:
        revision = predecessor
    return revision


def _inherited_row_ids(edition: MaterialisedEdition) -> frozenset[str]:
    """Return the casilla ids the edition resolves from an earlier edition rather than stating."""
    rows = edition.table["casillas"]
    origins = edition.label_origins
    assert isinstance(rows, tuple | list)
    assert origins is not None and len(origins) == len(rows)
    return frozenset(
        str(row["id"]) for row, origin in zip(rows, origins, strict=True) if origin not in (None, edition.revision_id)
    )


def _cite_successor_design_on_inherited_rows(registry_root: Path, *, inherited_source_ref: str) -> None:
    """Make the rows the successor inherits cite the successor's record design.

    An inherited row otherwise carries the record design of the edition that
    states it, which falls outside the successor's validity window and is
    refused by validation before publication is reached. Rewriting it isolates
    the publication boundary these tests are about.
    """
    for path in (registry_root / "modelos" / _MODELO / "revisions").glob("*/casillas/*.toml"):
        text = path.read_text("utf-8")
        path.write_text(
            text.replace(f'"{inherited_source_ref}"', f'"{_SOURCE_REF}"'),
            encoding="utf-8",
            newline="",
        )


def _withdraw_export_layouts(modelo_root: Path, *, revision: str) -> None:
    """Put the edition into the state a first render is published from.

    ``export_layouts`` is a scoped family carried in the generated ``export``
    tree, so an edition awaiting its first render holds none. On a delta that is
    not silence the loader can resolve: the predecessor declares layouts, and an
    edition that states none while saying nothing would empty the family through
    an absent word. The edition therefore declares the withdrawal, which is what
    an author staging a first render writes.

    The clearance is left standing after publication. Once the tree is on disk
    the edition states the family itself and the merge never consults the
    declaration, so it decides nothing; retiring it would mean the publication
    path writing outside ``revisions/<id>/export/``, which is not its boundary.
    """
    revision_dir = modelo_root / "revisions" / revision
    shutil.rmtree(revision_dir / "export")
    manifest = revision_dir / "revision.toml"
    lines = manifest.read_text("utf-8").splitlines(keepends=True)
    header = next(index for index, line in enumerate(lines) if line.startswith(f'[revisions."{revision}"]'))
    clearance = (
        'cleared_families = [{ family = "export_layouts", cause = "not_authored_for_this_edition", '
        'reason = "No export tree has been rendered for this edition yet, and it adopts none from '
        'its predecessor." }]\n'
    )
    # Inserted directly under the revision header: appended at the end of the
    # file the key would land in whichever sub-table happens to be last.
    manifest.write_text("".join([*lines[: header + 1], clearance, *lines[header + 1 :]]), encoding="utf-8", newline="")


def _prepared(work: Path, target_root: Path) -> PreparedGeneratedTreeInvocation:
    modelo_root = target_root / "modelos" / _MODELO
    inputs = revision_render_inputs(
        compiled_bundled_authority(),
        modelo=_MODELO,
        revision=_REVISION,
        source_ref=_SOURCE_REF,
        bootstrap_transport=None,
    )
    candidate_root = work / "candidate" / "registry" / "aeat"
    supporting = supporting_modelos(_MODELO)
    stage_generated_export_candidate(
        target_root,
        candidate_root,
        modelo=_MODELO,
        revision=_REVISION,
        supporting_modelos=supporting,
    )
    return PreparedGeneratedTreeInvocation(
        invocation=GeneratedTreeInvocation(_MODELO, _REVISION, _SOURCE_REF, _FILING_YEAR, _PERIOD),
        inputs=inputs,
        validation=GeneratedExportTreeValidationContext(
            registry_root=candidate_root,
            source_root=bundled_path(),
            target=ExportFragmentTarget(
                modelo=_MODELO,
                revision_id=_REVISION,
                design_epoch=inputs.transport_profile.design_epoch,
            ),
            filing_year=_FILING_YEAR,
            period=_PERIOD,
            supporting_modelos=supporting,
            continuity_metadata_modelo_root=stage_continuity_metadata(modelo_root, work, revision=_REVISION),
        ),
        candidate_root=candidate_root,
        target_root=target_root,
        target_export_root=modelo_root / "revisions" / _REVISION / "export",
        published_modelo_root=stage_published_modelo(work, modelo=_MODELO, revision=_REVISION),
    )


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_a_delta_target_stages_as_the_complete_edition_it_resolves_to(tmp_path: Path) -> None:
    registry_root = _registry_copy(tmp_path / "source")
    modelo_root = registry_root / "modelos" / _MODELO
    resolved = materialise_edition(modelo_root, _REVISION)
    assert resolved.inherits_from is not None, "the target must name a predecessor, or staging it proves nothing"
    assert _inherited_row_ids(resolved), "the target must inherit rows, or staging it proves nothing"

    staged_modelo = stage_generated_export_candidate(
        registry_root,
        tmp_path / "candidate" / "registry" / "aeat",
        modelo=_MODELO,
        revision=_REVISION,
        supporting_modelos=(),
    )

    assert sorted(entry.name for entry in (staged_modelo / "revisions").iterdir()) == [_REVISION]
    staged_revision = staged_modelo / "revisions" / _REVISION
    assert not (staged_revision / "export").exists()
    staged = load_modelo_directory(staged_modelo).revisions[_REVISION]
    assert not isinstance(staged.predecessor, DeclaredPredecessor)
    resolved_rows = resolved.table["casillas"]
    assert isinstance(resolved_rows, tuple | list)
    assert [str(casilla.id) for casilla in staged.casillas] == [row["id"] for row in resolved_rows]
    # The candidate holds no export tree yet, so no row, stated or inherited, carries a back-reference:
    # the loader derives them from the layout the candidate is later rendered with.
    assert all(casilla.export_refs == () for casilla in staged.casillas)


def test_a_delta_target_whose_predecessor_is_absent_is_refused(tmp_path: Path) -> None:
    registry_root = _registry_copy(tmp_path / "source")
    modelo_root = registry_root / "modelos" / _MODELO
    predecessor = _declared_predecessor(modelo_root, _REVISION)
    shutil.rmtree(modelo_root / "revisions" / predecessor)
    candidate_root = tmp_path / "candidate" / "registry" / "aeat"

    with pytest.raises(RegistryLoadError, match=predecessor):
        stage_generated_export_candidate(
            registry_root,
            candidate_root,
            modelo=_MODELO,
            revision=_REVISION,
            supporting_modelos=(),
        )

    assert not (candidate_root / "modelos").exists()


def test_a_target_stating_every_row_stages_as_the_plain_copy_it_always_was(tmp_path: Path) -> None:
    registry_root = _registry_copy(tmp_path / "source")
    modelo_root = registry_root / "modelos" / _MODELO
    root_revision = _root_edition(modelo_root)
    assert root_revision != _REVISION, "the plain-copy case needs an edition other than the delta target"

    staged_modelo = stage_generated_export_candidate(
        registry_root,
        tmp_path / "candidate" / "registry" / "aeat",
        modelo=_MODELO,
        revision=root_revision,
        supporting_modelos=(),
    )
    expected = tmp_path / "expected"
    shutil.copytree(
        modelo_root / "revisions" / root_revision,
        expected,
        ignore=ignore_export_authority_directories,
    )

    assert _tree_bytes(staged_modelo / "revisions" / root_revision) == _tree_bytes(expected)


def test_a_delta_target_with_its_existing_tree_is_checked_at_filing_grade_without_writing(
    tmp_path: Path,
) -> None:
    """Staging is a representation change, so the delta's review carries into the filing-grade check."""
    target_root = _registry_copy(tmp_path / "target")
    prepared = _prepared(tmp_path / "work", target_root)
    before = _tree_bytes(target_root / "modelos" / _MODELO)

    outcome, _rendered, _state = check_prepared_invocation(prepared)

    assert outcome == "matched"
    assert prepared.validation.required_grade is RegistryAuthorityGrade.FILING
    assert _tree_bytes(target_root / "modelos" / _MODELO) == before


def test_an_absent_tree_on_a_delta_target_publishes_and_derives_the_full_copys_references(tmp_path: Path) -> None:
    target_root = _registry_copy(tmp_path / "target")
    modelo_root = target_root / "modelos" / _MODELO
    inherited = _inherited_row_ids(materialise_edition(modelo_root, _REVISION))
    root_revision = _root_edition(modelo_root)
    root_design = load_modelo_directory(modelo_root).revisions[root_revision].casillas[0].source_refs[0]
    _cite_successor_design_on_inherited_rows(target_root, inherited_source_ref=str(root_design))
    _withdraw_export_layouts(modelo_root, revision=_REVISION)
    declarations_before = _tree_bytes(modelo_root)

    checked = _prepared(tmp_path / "check", target_root)
    result, _rendered, _target_state = check_prepared_invocation(checked)
    assert result == "publishable_absence"
    assert not checked.target_export_root.exists()

    publication = _prepared(tmp_path / "publish", target_root)
    _result, rendered, target_state = check_prepared_invocation(publication)
    publish_prepared_invocation(publication, rendered, target_state)

    assert publication.target_export_root.is_dir()
    after = _tree_bytes(modelo_root)
    export_prefix = f"revisions/{_REVISION}/export/"
    assert {path: data for path, data in after.items() if not path.startswith(export_prefix)} == declarations_before
    published = load_modelo_directory(modelo_root).revisions[_REVISION]
    full_copy = compiled_bundled_authority().modelo(_MODELO).revisions[_REVISION]
    assert {str(c.id): c.export_refs for c in published.casillas} == {
        str(c.id): c.export_refs for c in full_copy.casillas
    }
    assert any(casilla.export_refs for casilla in published.casillas if str(casilla.id) in inherited)
