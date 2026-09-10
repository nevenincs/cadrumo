"""Staging and publishing a generated export tree whose target edition inherits.

A migrated edition names a predecessor and states only the casilla rows it
changed. These tests migrate a real edition in a temporary registry copy -- the
successor of modelo 210 keeps the rows that differ from its predecessor and
inherits the rest -- and drive the real candidate staging, generator, validator
and publication entry points over it, with no substituted component.

The candidate must be the complete edition the loader resolves, naming no
predecessor, and a delta whose predecessor is gone must be refused rather than
staged thin. Publication writes each addressed casilla's ``export_refs`` onto the
target edition's own declarations after the export tree is swapped in; a layout
addressing an inherited casilla must therefore be refused before anything in the
target is written, never after the cutover.
"""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.edition_materialisation import materialise_edition
from cadrumo.domain.calculations.registry.errors import RegistryLoadError, RegistryValidationError
from cadrumo.domain.calculations.registry.loader import load_modelo_directory
from cadrumo.domain.calculations.registry.schema import DeclaredPredecessor

from ..analysis.delta_minimality import MinimalityVerdict, judge_definition
from ..pipeline._export_tree import _render_toml_bytes
from ..pipeline._tree_publication import GeneratedExportTreeTargetStateReceipt
from ..pipeline._tree_validation import GeneratedExportTreeValidationContext
from ..pipeline.candidate_staging import (
    ignore_export_authority_directories,
    stage_continuity_metadata,
    stage_generated_export_candidate,
)
from ..pipeline.cli import (
    _check,
    _Invocation,
    _PreparedInvocation,
    _publish,
    _render_candidate,
    _stage_isolated_edition,
    _supporting_modelos,
)
from ..pipeline.export_fragment_provenance import ExportFragmentTarget
from ..pipeline.render_check import revision_render_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MODELO = "210"
_PREDECESSOR = "2025"
_REVISION = "2026-y-siguientes"
_SOURCE_REF = "aeat-dr-210-2026"
_PREDECESSOR_SOURCE_REF = "aeat-dr-210-2022"
_FILING_YEAR = 2026
_PERIOD = "EVENT-N"


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


def _migrate(registry_root: Path) -> frozenset[str]:
    """Make the successor a delta: name its predecessor and drop every row it restates unchanged.

    Returns the ids of the dropped rows, which the edition now inherits.
    """
    modelo_root = registry_root / "modelos" / _MODELO
    revision_root = modelo_root / "revisions" / _REVISION
    dropped = frozenset(
        judgement.casilla
        for judgement in judge_definition(load_modelo_directory(modelo_root), modelo_id=_MODELO)
        if judgement.revision == _REVISION and judgement.kind == MinimalityVerdict.RESTATED_UNCHANGED
    )
    for path in sorted((revision_root / "casillas").glob("*.toml")):
        rows = tomllib.loads(path.read_text("utf-8"))["revisions"][_REVISION]["casillas"]
        kept = [row for row in rows if row["id"] not in dropped]
        if kept:
            path.write_bytes(_render_toml_bytes(path.name, {"revisions": {_REVISION: {"casillas": kept}}}))
        else:
            path.unlink()
    manifest_path = revision_root / "revision.toml"
    manifest = manifest_path.read_text("utf-8")
    header = f'[revisions."{_REVISION}"]\n'
    assert manifest.count(header) == 1, "the successor manifest must open with its own revision table"
    manifest_path.write_text(
        manifest.replace(header, f'{header}predecessor = "{_PREDECESSOR}"\nreviewed_against = "{_PREDECESSOR}"\n'),
        encoding="utf-8",
        newline="",
    )
    return dropped


def _cite_successor_design_on_inherited_rows(registry_root: Path) -> None:
    """Make the predecessor's rows cite the successor's record design.

    An inherited row otherwise carries the predecessor's own design reference,
    which falls outside the successor's validity window and is refused by
    validation before publication is reached. Rewriting it isolates the
    publication boundary these tests are about.
    """
    for path in (registry_root / "modelos" / _MODELO / "revisions" / _PREDECESSOR / "casillas").glob("*.toml"):
        text = path.read_text("utf-8")
        path.write_text(
            text.replace(f'"{_PREDECESSOR_SOURCE_REF}"', f'"{_SOURCE_REF}"'),
            encoding="utf-8",
            newline="",
        )


def _prepared(work: Path, target_root: Path) -> _PreparedInvocation:
    modelo_root = target_root / "modelos" / _MODELO
    inputs = revision_render_inputs(
        bundled_authority(),
        modelo=_MODELO,
        revision=_REVISION,
        source_ref=_SOURCE_REF,
        bootstrap_transport=None,
    )
    candidate_root = work / "candidate" / "registry" / "aeat"
    supporting = _supporting_modelos(_MODELO)
    stage_generated_export_candidate(
        target_root,
        candidate_root,
        modelo=_MODELO,
        revision=_REVISION,
        supporting_modelos=supporting,
    )
    return _PreparedInvocation(
        invocation=_Invocation(_MODELO, _REVISION, _SOURCE_REF, _FILING_YEAR, _PERIOD),
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
        published_modelo_root=_stage_isolated_edition(
            modelo_root, work / "published-modelo" / _MODELO, revision=_REVISION
        ),
    )


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_a_delta_target_stages_as_the_complete_edition_it_resolves_to(tmp_path: Path) -> None:
    registry_root = _registry_copy(tmp_path / "source")
    inherited = _migrate(registry_root)
    assert inherited, "the migration must leave the successor inheriting rows, or it proves nothing"
    modelo_root = registry_root / "modelos" / _MODELO
    resolved = materialise_edition(modelo_root, _REVISION)
    assert resolved.inherits_from == _PREDECESSOR

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
    # A stated row keeps the back-reference it declares; an inherited row carries none of its origin's.
    by_id = {str(casilla.id): casilla for casilla in staged.casillas}
    assert all(by_id[casilla_id].export_refs == () for casilla_id in inherited)
    stated = [casilla for casilla_id, casilla in by_id.items() if casilla_id not in inherited]
    assert any(casilla.export_refs for casilla in stated)


def test_a_delta_target_whose_predecessor_is_absent_is_refused(tmp_path: Path) -> None:
    registry_root = _registry_copy(tmp_path / "source")
    _migrate(registry_root)
    shutil.rmtree(registry_root / "modelos" / _MODELO / "revisions" / _PREDECESSOR)
    candidate_root = tmp_path / "candidate" / "registry" / "aeat"

    with pytest.raises(RegistryLoadError, match=_PREDECESSOR):
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
    staged_modelo = stage_generated_export_candidate(
        registry_root,
        tmp_path / "candidate" / "registry" / "aeat",
        modelo=_MODELO,
        revision=_REVISION,
        supporting_modelos=(),
    )
    expected = tmp_path / "expected"
    shutil.copytree(
        registry_root / "modelos" / _MODELO / "revisions" / _REVISION,
        expected,
        ignore=ignore_export_authority_directories,
    )

    assert _tree_bytes(staged_modelo / "revisions" / _REVISION) == _tree_bytes(expected)


def test_a_published_delta_target_is_refused_by_validation_before_anything_is_written(tmp_path: Path) -> None:
    target_root = _registry_copy(tmp_path / "target")
    _migrate(target_root)
    prepared = _prepared(tmp_path / "work", target_root)
    before = _tree_bytes(target_root / "modelos" / _MODELO)

    with pytest.raises(RegistryValidationError, match="is not declared by casilla"):
        _check(prepared)

    assert _tree_bytes(target_root / "modelos" / _MODELO) == before


def test_an_absent_tree_on_a_delta_addressing_inherited_casillas_is_refused_before_cutover(tmp_path: Path) -> None:
    target_root = _registry_copy(tmp_path / "target")
    inherited = _migrate(target_root)
    _cite_successor_design_on_inherited_rows(target_root)
    modelo_root = target_root / "modelos" / _MODELO
    shutil.rmtree(modelo_root / "revisions" / _REVISION / "export")
    prepared = _prepared(tmp_path / "work", target_root)
    before = _tree_bytes(modelo_root)

    with pytest.raises(ValueError, match="which the edition inherits from '2025'") as refusal:
        _check(prepared)
    named = str(refusal.value)
    assert all(f"'{casilla_id}'" not in named for casilla_id in _stated_ids(modelo_root))
    assert any(f"'{casilla_id}'" in named for casilla_id in inherited)

    # Publication refuses on its own, not only because check did: republication reaches it without a check.
    publication = _prepared(tmp_path / "publish", target_root)
    rendered = _render_candidate(publication)
    with pytest.raises(ValueError, match="which the edition inherits from '2025'"):
        _publish(publication, rendered, GeneratedExportTreeTargetStateReceipt.observe(publication.target_export_root))

    assert not prepared.target_export_root.exists()
    assert _tree_bytes(modelo_root) == before


def _stated_ids(modelo_root: Path) -> frozenset[str]:
    return frozenset(
        str(row["id"])
        for path in (modelo_root / "revisions" / _REVISION / "casillas").glob("*.toml")
        for row in tomllib.loads(path.read_text("utf-8"))["revisions"][_REVISION]["casillas"]
    )
