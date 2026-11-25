"""Real-filesystem proofs for the reviewed set transaction: every member's export and form, or none."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.tests.authored_editions import revision_covering

from ...compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ...form_layout.serialization import form_layout_fragment_path
from ..edition_candidate_staging import stage_continuity_metadata
from ..export_fragment_provenance import ExportFragmentTarget
from ..export_tree import render_complete_export_tree
from ..generated_tree_inventory import GeneratedExportTree
from ..tree_publication import (
    GeneratedExportSetMember,
    publish_validated_generated_export_tree,
    publish_validated_generated_export_tree_set,
)
from ..tree_publication_contracts import GeneratedExportTransactionPaths, GeneratedExportTreePublicationContext
from ..tree_validation import GeneratedExportTreeValidationContext
from .generated_tree_test_support import ISOLATED_TREE, isolated_authorities, isolated_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: A second authored edition of the isolated tree's modelo, so a set holds two real targets.
_SECOND_EDITION = revision_covering(ISOLATED_TREE.modelo, ISOLATED_TREE.filing_year - 1)
_SECOND_TREE = GeneratedExportTree(
    ISOLATED_TREE.modelo,
    str(_SECOND_EDITION.id),
    f"aeat-dr-{ISOLATED_TREE.modelo}-{_SECOND_EDITION.id}",
    str(_SECOND_EDITION.valid_from.year),
    _SECOND_EDITION.valid_from.year,
    ISOLATED_TREE.period,
)
_TREES = (ISOLATED_TREE, _SECOND_TREE)
_PRIOR_FORM_SUFFIX = b"# prior generated form\n"
_STALE_RECORD_SUFFIX = b"# stale record edit\n"


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES)
    }


@dataclass(frozen=True, slots=True)
class _Live:
    target_root: Path

    def revision_root(self, tree: GeneratedExportTree) -> Path:
        return self.target_root / "modelos" / tree.modelo / "revisions" / tree.revision

    def export_root(self, tree: GeneratedExportTree) -> Path:
        return self.revision_root(tree) / "export"

    def form(self, tree: GeneratedExportTree) -> Path:
        return form_layout_fragment_path(self.revision_root(tree))

    def snapshot(self) -> dict[str, bytes]:
        return _tree_bytes(self.target_root)

    def transaction_siblings(self) -> tuple[Path, ...]:
        return scan_directory(self.target_root, pattern=".generated-export-*")


def _stage_live(tmp_path: Path) -> _Live:
    """Copy the committed modelo, then make each export stale and each form a prior version."""
    target_root = tmp_path / "publication-root" / "registry" / "aeat"
    source_modelo = bundled_path("registry", "aeat", "modelos", ISOLATED_TREE.modelo)
    live = _Live(target_root)
    shutil.copytree(source_modelo, target_root / "modelos" / ISOLATED_TREE.modelo)
    for tree in _TREES:
        record = sorted(live.export_root(tree).glob("*-record-*.toml"))[0]
        record.write_bytes(record.read_bytes() + _STALE_RECORD_SUFFIX)
        live.form(tree).write_bytes(live.form(tree).read_bytes() + _PRIOR_FORM_SUFFIX)
    return live


def _member(
    tree: GeneratedExportTree,
    root: Path,
    live: _Live,
    *,
    replace_export_directory: Callable[[Path, Path], None] = os.replace,
) -> tuple[GeneratedExportSetMember, Path]:
    """Render one real candidate through the export-tree renderer and pair it with its generated form."""
    validation = GeneratedExportTreeValidationContext(
        registry_root=isolated_authority(tree, root / "candidate"),
        source_root=bundled_path(),
        target=ExportFragmentTarget(modelo=tree.modelo, revision_id=tree.revision, design_epoch=tree.epoch),
        filing_year=tree.filing_year,
        period=tree.period,
        continuity_metadata_modelo_root=stage_continuity_metadata(
            bundled_path("registry", "aeat", "modelos", tree.modelo), root, revision=tree.revision
        ),
    )
    joined, semantic_map, transport, render_profile, evidence = isolated_authorities(tree)
    candidate_export = validation.registry_root / "modelos" / tree.modelo / "revisions" / tree.revision / "export"
    rendered = render_complete_export_tree(
        candidate_export,
        revision_id=tree.revision,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=transport,
        render_profile=render_profile,
        render_profile_source_evidence=evidence,
    )
    committed_form = form_layout_fragment_path(
        bundled_path("registry", "aeat", "modelos", tree.modelo, "revisions", tree.revision)
    ).read_bytes()
    member = GeneratedExportSetMember(
        context=GeneratedExportTreePublicationContext(
            validation=validation,
            temporary_root=root,
            target_root=live.target_root,
            target_export_root=live.export_root(tree),
            replace_export_directory=replace_export_directory,
        ),
        joined=joined,
        semantic_map=semantic_map,
        rendered=rendered,
        render_profile=render_profile,
        render_profile_source_evidence=evidence,
        form_fragment=committed_form,
    )
    return member, candidate_export


def _refuse_first_install_into(target_export_root: Path) -> Callable[[Path, Path], None]:
    """Refuse the one swap that installs a candidate into this target; every other swap is real."""
    refused: list[Path] = []

    def replace(source: Path, destination: Path) -> None:
        if destination == target_export_root and not refused:
            refused.append(source)
            raise OSError("planted refusal of the second member's install")
        os.replace(source, destination)

    return replace


def test_a_set_installs_every_export_and_form_before_one_live_validation(tmp_path: Path) -> None:
    live = _stage_live(tmp_path)
    first, first_candidate = _member(ISOLATED_TREE, tmp_path / "m1", live)
    second, second_candidate = _member(_SECOND_TREE, tmp_path / "m2", live)
    observed: list[tuple[dict[str, bytes], dict[str, bytes], bytes, bytes]] = []

    def validate_live() -> None:
        observed.append(
            (
                _tree_bytes(live.export_root(ISOLATED_TREE)),
                _tree_bytes(live.export_root(_SECOND_TREE)),
                live.form(ISOLATED_TREE).read_bytes(),
                live.form(_SECOND_TREE).read_bytes(),
            )
        )

    published = publish_validated_generated_export_tree_set(members=(first, second), final_live_validator=validate_live)

    expected = (
        _tree_bytes(first_candidate),
        _tree_bytes(second_candidate),
        first.form_fragment,
        second.form_fragment,
    )
    assert observed == [expected], "the one live validation must see every member installed"
    assert (
        _tree_bytes(live.export_root(ISOLATED_TREE)),
        _tree_bytes(live.export_root(_SECOND_TREE)),
        live.form(ISOLATED_TREE).read_bytes(),
        live.form(_SECOND_TREE).read_bytes(),
    ) == expected
    assert [item.export_root for item in published] == [live.export_root(tree) for tree in _TREES]
    assert not live.transaction_siblings()
    assert not any(GeneratedExportTransactionPaths.for_context(m.context).journal.exists() for m in (first, second))


def test_a_failed_second_install_restores_both_exports_and_forms_byte_for_byte(tmp_path: Path) -> None:
    live = _stage_live(tmp_path)
    before = live.snapshot()
    first, _first_candidate = _member(ISOLATED_TREE, tmp_path / "m1", live)
    second, _second_candidate = _member(
        _SECOND_TREE,
        tmp_path / "m2",
        live,
        replace_export_directory=_refuse_first_install_into(live.export_root(_SECOND_TREE)),
    )
    validated: list[bool] = []

    with pytest.raises(RegistryValidationError, match="every member's previous tree was restored"):
        publish_validated_generated_export_tree_set(
            members=(first, second), final_live_validator=lambda: validated.append(True)
        )

    assert live.snapshot() == before
    assert validated == []
    assert not live.transaction_siblings()


def test_a_failed_live_validation_restores_every_member_including_its_form(tmp_path: Path) -> None:
    live = _stage_live(tmp_path)
    before = live.snapshot()
    first, _first_candidate = _member(ISOLATED_TREE, tmp_path / "m1", live)
    second, _second_candidate = _member(_SECOND_TREE, tmp_path / "m2", live)
    assert live.form(ISOLATED_TREE).read_bytes() != first.form_fragment

    def refuse_live() -> None:
        assert live.form(ISOLATED_TREE).read_bytes() == first.form_fragment
        raise RegistryValidationError("planted live compile refusal")

    with pytest.raises(RegistryValidationError, match="planted live compile refusal"):
        publish_validated_generated_export_tree_set(members=(first, second), final_live_validator=refuse_live)

    assert live.snapshot() == before
    assert live.form(ISOLATED_TREE).read_bytes().endswith(_PRIOR_FORM_SUFFIX)
    assert not live.transaction_siblings()


def test_a_set_of_one_installs_the_export_the_single_target_publisher_installs(tmp_path: Path) -> None:
    set_live = _stage_live(tmp_path / "set")
    single_live = _stage_live(tmp_path / "single")
    member, _candidate = _member(ISOLATED_TREE, tmp_path / "m-set", set_live)
    single, _single_candidate = _member(ISOLATED_TREE, tmp_path / "m-single", single_live)

    publish_validated_generated_export_tree_set(members=(member,), final_live_validator=lambda: None)
    publish_validated_generated_export_tree(
        context=single.context,
        joined=single.joined,
        semantic_map=single.semantic_map,
        rendered=single.rendered,
        render_profile=single.render_profile,
        render_profile_source_evidence=single.render_profile_source_evidence,
    )

    assert _tree_bytes(set_live.export_root(ISOLATED_TREE)) == _tree_bytes(single_live.export_root(ISOLATED_TREE))
    assert set_live.form(ISOLATED_TREE).read_bytes() == member.form_fragment
    # The single-target publisher keeps its export-only boundary: the form stays with its owner.
    assert single_live.form(ISOLATED_TREE).read_bytes().endswith(_PRIOR_FORM_SUFFIX)
    assert (set_live.export_root(ISOLATED_TREE) / EXPORT_FRAGMENT_PROVENANCE_FILENAME).is_file()


def test_a_set_refuses_a_repeated_revision_before_any_write(tmp_path: Path) -> None:
    live = _stage_live(tmp_path)
    before = live.snapshot()
    first, _first_candidate = _member(ISOLATED_TREE, tmp_path / "m1", live)
    again, _again_candidate = _member(ISOLATED_TREE, tmp_path / "m2", live)

    with pytest.raises(RegistryValidationError, match="distinct revisions of one modelo"):
        publish_validated_generated_export_tree_set(members=(first, again), final_live_validator=lambda: None)

    assert live.snapshot() == before
