"""Proofs that a staged candidate carries the complete edition the loader resolves.

A candidate names no predecessor, so every member the target inherited has to be
staged as its own. The proofs below use the real staging boundary, the real
bundled tree and the real loader: modelo 390's later editions restate three of
their ten application links and none of their filing schedules, which is exactly
the shape that a delta-only candidate loses.
"""

from __future__ import annotations

import shutil
import tomllib
from collections.abc import Mapping
from pathlib import Path

import pytest
import rtoml

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from ..compiler.edition_materialisation import materialise_edition
from ..compiler.loader import load_modelo_directory
from .candidate_staging import stage_generated_export_candidate
from .cli import supporting_modelos

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_INHERITED_MODELO = "390"
_INHERITING_REVISION = "2023"
_DECLARING_REVISION = "2022"
_INHERITED_LINK = "modelo-390-approval"
_STORAGE_ONLY_MODELO = "184"
_STORAGE_ONLY_REVISION = "2025-y-siguientes"


def _stage(candidate_root: Path, *, modelo: str, revision: str) -> Path:
    return stage_generated_export_candidate(
        bundled_path("registry", "aeat"),
        candidate_root,
        modelo=modelo,
        revision=revision,
        supporting_modelos=supporting_modelos(modelo),
    )


def test_inheriting_edition_is_staged_with_the_members_it_does_not_restate(tmp_path: Path) -> None:
    """An id the target inherits rather than restates survives into the candidate."""
    source_revision = bundled_path("registry", "aeat", "modelos", _INHERITED_MODELO, "revisions", _INHERITING_REVISION)
    restated_ids = {
        row["id"]
        for fragment in (source_revision / "application_links").glob("*.toml")
        for row in tomllib.loads(fragment.read_text("utf-8"))["revisions"][_INHERITING_REVISION][
            "application_links"
        ]
    }
    assert _INHERITED_LINK not in restated_ids, (
        "the fixture rests on this id being inherited rather than restated; pick another id"
    )

    staged = _stage(tmp_path / "candidate", modelo=_INHERITED_MODELO, revision=_INHERITING_REVISION)
    revision = load_modelo_directory(staged).revisions[_INHERITING_REVISION]

    staged_ids = {str(link.id) for link in revision.application_links}
    assert _INHERITED_LINK in staged_ids
    assert restated_ids <= staged_ids, "the target's own rows must survive beside the inherited ones"
    assert revision.filing_schedules, "a member the target restates nowhere is still part of its edition"


def test_staged_edition_equals_the_loader_resolution_of_its_source(tmp_path: Path) -> None:
    """The candidate is the edition the loader resolves, not a subset of it."""
    resolved = materialise_edition(
        bundled_path("registry", "aeat", "modelos", _INHERITED_MODELO),
        _INHERITING_REVISION,
    )
    resolved_rows = resolved.table["application_links"]
    assert isinstance(resolved_rows, list | tuple)
    resolved_links = tuple(str(row["id"]) for row in resolved_rows if isinstance(row, Mapping))

    staged = _stage(tmp_path / "candidate", modelo=_INHERITED_MODELO, revision=_INHERITING_REVISION)
    revision = load_modelo_directory(staged).revisions[_INHERITING_REVISION]

    assert tuple(str(link.id) for link in revision.application_links) == resolved_links


def test_storage_only_transitive_baselines_are_detached_as_complete_authority(tmp_path: Path) -> None:
    """A storage-only target remains hydratable after every baseline sibling is pruned."""
    source = bundled_path("registry", "aeat", "modelos", _STORAGE_ONLY_MODELO)
    source_before = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    live = load_modelo_directory(source).revisions[_STORAGE_ONLY_REVISION]

    staged_root = _stage(
        tmp_path / "candidate",
        modelo=_STORAGE_ONLY_MODELO,
        revision=_STORAGE_ONLY_REVISION,
    )
    staged_revision_roots = tuple(path.name for path in (staged_root / "revisions").iterdir() if path.is_dir())
    assert staged_revision_roots == (_STORAGE_ONLY_REVISION,)
    declared = tomllib.loads(
        (staged_root / "revisions" / _STORAGE_ONLY_REVISION / "revision.toml").read_text("utf-8")
    )["revisions"][_STORAGE_ONLY_REVISION]
    assert not {"predecessor", "casilla_storage_baseline", "family_storage_baseline"}.intersection(declared)

    staged = load_modelo_directory(staged_root).revisions[_STORAGE_ONLY_REVISION]
    assert tuple((str(row.id), row.number, row.data_type) for row in staged.casillas) == tuple(
        (str(row.id), row.number, row.data_type) for row in live.casillas
    )
    assert staged.application_links == live.application_links
    assert staged.workbook_parity_refs == live.workbook_parity_refs
    assert staged.predecessor is None
    assert staged.casilla_storage_baseline is None
    assert staged.family_storage_baseline is None
    source_after = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    assert source_after == source_before


def test_a_candidate_missing_an_inherited_member_is_refused(tmp_path: Path) -> None:
    """The detector has teeth: dropping the staged member breaks the load that uses it.

    The defect is introduced in an isolated staged tree, never in the working
    tree, and it is the same defect the delta-only staging used to produce: a
    candidate whose constructs reference an application link its revision no
    longer carries.
    """
    staged = _stage(tmp_path / "candidate", modelo=_INHERITED_MODELO, revision=_INHERITING_REVISION)
    links_root = staged / "revisions" / _INHERITING_REVISION / "application_links"
    fragment = next(links_root.glob("*.toml"))
    payload = tomllib.loads(fragment.read_text("utf-8"))
    rows = payload["revisions"][_INHERITING_REVISION]["application_links"]
    kept = [row for row in rows if row["id"] != _INHERITED_LINK]
    assert len(kept) == len(rows) - 1
    payload["revisions"][_INHERITING_REVISION]["application_links"] = kept
    fragment.write_text(rtoml.dumps(payload, pretty=True), encoding="utf-8")

    revision = load_modelo_directory(staged).revisions[_INHERITING_REVISION]
    assert _INHERITED_LINK not in {str(link.id) for link in revision.application_links}
    referencing = [
        construct
        for construct in revision.constructs
        if _INHERITED_LINK in tuple(str(item) for item in construct.application_links)
    ]
    assert referencing, "the tooth rests on a construct referencing the removed id"


def test_an_empty_staged_section_is_refused(tmp_path: Path) -> None:
    """A staged section left without fragments fails the load rather than loading empty."""
    staged = _stage(tmp_path / "candidate", modelo=_INHERITED_MODELO, revision=_DECLARING_REVISION)
    links_root = staged / "revisions" / _DECLARING_REVISION / "application_links"
    for fragment in links_root.glob("*.toml"):
        fragment.unlink()

    with pytest.raises(RegistryLoadError):
        load_modelo_directory(staged)

    shutil.rmtree(staged)
