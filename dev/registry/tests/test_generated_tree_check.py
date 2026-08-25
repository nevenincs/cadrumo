"""Real-filesystem regression proof for generated export check mode."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from shutil import rmtree

import pytest

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.hashing import hash_file
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..pipeline import _tree_check
from ..pipeline._export_tree import ExportTreeTransportProfile
from ..pipeline._provenance_manifest import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    export_fragment_provenance_manifest_json_bytes,
    load_export_fragment_provenance_manifest,
    normalised_loader_semantics,
)
from ..pipeline._tree_check import (
    GeneratedExportTreeCheckContext,
    check_generated_export_tree,
)
from .test_export_tree import (
    _ISOLATED_TREE,
    _isolated_render_profile,
    _real_authorities,
    _wire_profile,
    _write_isolated_generated_authority_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# Modelo 130 throughout: `_write_isolated_generated_authority_tree` in
# `test_export_tree` builds its isolated tree for modelo 130, because the
# modelo 200 revision it used to target now declares 578 projection endpoints
# that semantic-map validation checks as a bijection, which a synthetic map
# cannot satisfy. These modules consume that helper, so their own paths and
# snapshot must name the same modelo or the tree and the paths disagree.
def _tree_hashes(root: Path) -> dict[str, str]:
    """Observe existing target bytes using the production hashing utility."""
    return {
        path.relative_to(root).as_posix(): hash_file(path)[0]
        for path in scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES)
    }


def _check_inputs(tmp_path: Path, snapshot):
    """Build separate current target and empty candidate authorities on disk."""
    target_validation, joined, semantic_map, _rendered, target_export_root = _write_isolated_generated_authority_tree(
        tmp_path / "published",
        snapshot,
    )
    candidate_validation, _candidate_joined, _candidate_map, _candidate_rendered, candidate_export_root = (
        _write_isolated_generated_authority_tree(tmp_path / "candidate", snapshot)
    )
    rmtree(candidate_export_root)
    context = GeneratedExportTreeCheckContext(
        validation=candidate_validation,
        temporary_root=tmp_path / "candidate",
        target_registry_root=target_validation.registry_root,
        target_export_root=target_export_root,
    )
    return context, joined, semantic_map, target_export_root


#: Substring of the registry's filing-grade review refusal. ``check_generated_export_tree``
#: selects a filing-grade snapshot partway through, so an unreviewed target revision raises
#: the same exception type these cases expect, before the comparison under test ever runs.
_REVIEW_GATE_REFUSAL = "filing-grade snapshot requires operator_reviewed"


def _require_the_defect_was_reached(refusal: BaseException, defect: str) -> None:
    """Refuse a pass earned by the review gate rather than by the injected defect."""
    assert _REVIEW_GATE_REFUSAL not in str(refusal), (
        f"defect {defect!r} was not detected on its own terms: the check refused on the "
        f"registry's filing-grade review gate before reaching the comparison this case "
        f"exercises, so a green result here would prove nothing about the injected drift"
    )


def _rendered_record_fragments(export_root):
    """The record fragments the renderer actually wrote, in file order.

    These filenames were transcribed from the old synthetic tree
    (`0001-record-generated-registro-tipo-1.toml`). The fixture now renders a
    REAL tree, whose fragments are named after that modelo's own records, so a
    transcribed name is a file that does not exist and the case dies on the
    tamper rather than on the drift it is testing.
    """
    return sorted(
        path
        for path in export_root.iterdir()
        if path.suffix == ".toml" and path.name != EXPORT_FRAGMENT_PROVENANCE_FILENAME
    )


def _profile() -> ExportTreeTransportProfile:
    """The isolated tree's own transport profile, derived rather than transcribed.

    Every axis here -- modelo, design epoch, source ref, source digest, layout id
    -- has to agree with the joined design the fixture actually builds. They were
    transcribed by hand and went stale each time the fixture's target moved, so
    they are read off `_ISOLATED_TREE` and the real intermediate instead.
    """
    _joined, _map, transport, _profile_obj, _evidence = _real_authorities(_ISOLATED_TREE)
    return transport


def test_check_regenerates_in_isolation_and_preserves_published_hashes(m130_inspection_snapshot, tmp_path) -> None:
    """A real candidate must match every current target member without target mutation."""
    context, joined, semantic_map, target_export_root = _check_inputs(tmp_path, m130_inspection_snapshot)
    before = _tree_hashes(target_export_root)

    checked = check_generated_export_tree(
        context=context,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=_profile(),
        render_profile=_isolated_render_profile()[0],
        render_profile_source_evidence=_isolated_render_profile()[1],
    )

    assert _tree_hashes(target_export_root) == before
    assert checked.candidate.snapshot.revision.export_layouts == (checked.candidate.layout,)
    assert checked.published_manifest == checked.candidate.provenance_manifest
    assert normalised_loader_semantics(checked.published_layout) == normalised_loader_semantics(
        checked.candidate.layout,
    )
    candidate_export_root = (
        context.validation.registry_root
        / "modelos"
        / _ISOLATED_TREE.modelo
        / "revisions"
        / _ISOLATED_TREE.revision
        / "export"
    )
    assert _tree_hashes(candidate_export_root) == before


@pytest.mark.parametrize(
    "defect",
    (
        "semantic-map",
        "source",
        "transport-profile",
        "render-profile",
        "output-byte",
        "manifest-authority",
        "manifest-schema",
        "missing-output",
        "extra-output",
        "obsolete-sibling",
        "obsolete-direct-modelo",
    ),
)
def test_check_refuses_drift_without_changing_published_hashes(m130_inspection_snapshot, tmp_path, defect: str) -> None:
    """Every authority or membership defect fails while target bytes remain exactly as supplied."""
    context, joined, semantic_map, target_export_root = _check_inputs(tmp_path, m130_inspection_snapshot)
    profile = _profile()
    render_profile = _wire_profile()
    if defect == "semantic-map":
        semantic_map = semantic_map.model_copy(
            update={
                "entries": (
                    semantic_map.entries[0].model_copy(update={"literal": "XX"}),
                    *semantic_map.entries[1:],
                ),
            },
        )
    elif defect == "source":
        joined = joined.model_copy(
            update={"source": joined.source.model_copy(update={"source_sha256": "b" * 64})},
        )
    elif defect == "transport-profile":
        profile = profile.model_copy(update={"source_sha256": "b" * 64})
    elif defect == "render-profile":
        render_profile = render_profile.model_copy(update={"fragment_ids": ("digest-drift",)})
    elif defect == "output-byte":
        output = _rendered_record_fragments(target_export_root)[0]
        output.write_bytes(output.read_bytes() + b"# drift\n")
    elif defect == "manifest-authority":
        manifest_path = target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME
        manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
        manifest_path.write_bytes(
            export_fragment_provenance_manifest_json_bytes(
                manifest.model_copy(update={"source_sha256": "b" * 64}),
            ),
        )
    elif defect == "manifest-schema":
        manifest_path = target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME
        manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
        manifest_path.write_bytes(
            export_fragment_provenance_manifest_json_bytes(
                manifest.model_copy(update={"generator_schema_version": 1}),
            ),
        )
    elif defect == "missing-output":
        _rendered_record_fragments(target_export_root)[-1].unlink()
    elif defect == "extra-output":
        (target_export_root / "0003-unreviewed.toml").write_text("unreviewed = true\n", encoding="utf-8")
    elif defect == "obsolete-sibling":
        (target_export_root.parent / "export.provenance.json").write_text("{}\n", encoding="utf-8")
    elif defect == "obsolete-direct-modelo":
        (context.target_registry_root / "modelos" / "200.toml").write_text(
            '[modelo]\nid = "130"\n',
            encoding="utf-8",
        )
    else:
        raise AssertionError(f"unknown test defect: {defect}")
    before = _tree_hashes(target_export_root)

    with pytest.raises(RegistryValidationError) as refusal:
        check_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            transport_profile=profile,
            render_profile=render_profile,
            render_profile_source_evidence=_isolated_render_profile()[1],
        )

    _require_the_defect_was_reached(refusal.value, defect)
    assert _tree_hashes(target_export_root) == before


def test_check_refuses_candidate_reuse_without_changing_published_hashes(m130_inspection_snapshot, tmp_path) -> None:
    """A prior candidate output cannot become a check input or a silent green path."""
    context, joined, semantic_map, target_export_root = _check_inputs(tmp_path, m130_inspection_snapshot)
    candidate_export_root = (
        context.validation.registry_root
        / "modelos"
        / _ISOLATED_TREE.modelo
        / "revisions"
        / _ISOLATED_TREE.revision
        / "export"
    )
    candidate_export_root.mkdir()
    before = _tree_hashes(target_export_root)

    with pytest.raises(RegistryValidationError, match="must be absent before fresh rendering"):
        check_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            transport_profile=_profile(),
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )

    assert _tree_hashes(target_export_root) == before


def test_check_refuses_linked_candidate_ancestor_before_rendering(m130_inspection_snapshot, tmp_path) -> None:
    """A directory link cannot redirect candidate rendering before the validation boundary."""
    context, joined, semantic_map, target_export_root = _check_inputs(tmp_path, m130_inspection_snapshot)
    candidate_modelos_root = context.validation.registry_root / "modelos"
    redirected_modelos_root = tmp_path / "redirected-modelos"
    candidate_modelos_root.rename(redirected_modelos_root)
    candidate_modelos_root.symlink_to(redirected_modelos_root, target_is_directory=True)
    before = _tree_hashes(target_export_root)
    redirected_export_root = redirected_modelos_root / "130" / "revisions" / _ISOLATED_TREE.revision / "export"

    with pytest.raises(RegistryValidationError, match="candidate revision root must not be a link"):
        check_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            transport_profile=_profile(),
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )

    assert not redirected_export_root.exists()
    assert _tree_hashes(target_export_root) == before


def test_check_module_has_no_migration_reader_or_publisher_surface() -> None:
    """The permanent check API must not regain an obsolete migration or publish route."""
    module = ast.parse(inspect.getsource(_tree_check))
    referenced_names = {node.id for node in ast.walk(module) if isinstance(node, ast.Name)}
    attribute_names = {node.attr for node in ast.walk(module) if isinstance(node, ast.Attribute)}
    imported_modules = {
        node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name for node in ast.walk(module) if isinstance(node, ast.Import) for alias in node.names
    )

    forbidden = {
        "bundled_authority",
        "copytree",
        "copy2",
        "load_modelo_file",
        "load_modelo_path",
        "publish_validated_generated_export_tree",
        "resolve_export_layout",
    }
    assert not forbidden.intersection(referenced_names)
    assert not forbidden.intersection(attribute_names)
    assert "dev.registry._generated_tree_publication" not in imported_modules
    assert "legacy" not in inspect.getsource(_tree_check).casefold()
