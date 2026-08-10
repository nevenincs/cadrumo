"""Real-filesystem proofs for generated revision publication."""

from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry import RegistryValidationError

from .. import _generated_tree_publication
from .._generated_tree_publication import (
    GeneratedExportTreePublicationContext,
    publish_validated_generated_export_tree,
)
from .test_export_tree import _write_isolated_generated_authority_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _tree_bytes(root: Path) -> dict[str, bytes]:
    """Capture a real regular tree for byte-identical target assertions."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file()
    }


def _publication_inputs(tmp_path: Path, snapshot, *, existing_target: bool):
    """Build independent S10 candidates, never by copying an old fragment tree."""
    candidate_base = tmp_path / "temporary-root"
    validation, joined, semantic_map, rendered, _export_root = _write_isolated_generated_authority_tree(
        candidate_base,
        snapshot,
    )
    target_root = tmp_path / "publication-root" / "registry" / "aeat"
    target_revision_root = target_root / "modelos" / "200" / "revisions" / "2025"
    target_revision_root.parent.mkdir(parents=True)
    if existing_target:
        prior_base = tmp_path / "prior-root"
        prior = _write_isolated_generated_authority_tree(prior_base, snapshot)
        prior_context = prior[0]
        prior_revision_root = prior_context.registry_root / "modelos" / "200" / "revisions" / "2025"
        os.replace(prior_revision_root, target_revision_root)
        (target_revision_root / "revision.toml").write_text("# prior generated revision\n", encoding="utf-8")
    context = GeneratedExportTreePublicationContext(
        validation=validation,
        temporary_root=candidate_base,
        target_root=target_root,
        target_revision_root=target_revision_root,
    )
    candidate_revision_root = validation.registry_root / "modelos" / "200" / "revisions" / "2025"
    return context, joined, semantic_map, rendered, candidate_revision_root


def _rollback_siblings(target_revision_root: Path) -> tuple[Path, ...]:
    return tuple(target_revision_root.parent.glob(f".{target_revision_root.name}.generator-rollback-*"))


def test_publication_replaces_an_existing_revision_and_removes_rollback(_m200_snapshot, tmp_path) -> None:
    """The validated candidate replaces the entire revision with no old-tree residue."""
    context, joined, semantic_map, rendered, candidate_revision_root = _publication_inputs(
        tmp_path,
        _m200_snapshot,
        existing_target=True,
    )
    expected = _tree_bytes(candidate_revision_root)

    published = publish_validated_generated_export_tree(
        context=context,
        joined=joined,
        semantic_map=semantic_map,
        rendered=rendered,
    )

    assert published.revision_root == context.target_revision_root
    assert published.export_root == context.target_revision_root / "export"
    assert published.provenance_manifest_path.is_file()
    assert _tree_bytes(context.target_revision_root) == expected
    assert not candidate_revision_root.exists()
    assert not _rollback_siblings(context.target_revision_root)


def test_publication_creates_a_missing_revision_without_rollback_residue(_m200_snapshot, tmp_path) -> None:
    """No pre-existing target is required for the same complete cutover."""
    context, joined, semantic_map, rendered, candidate_revision_root = _publication_inputs(
        tmp_path,
        _m200_snapshot,
        existing_target=False,
    )
    expected = _tree_bytes(candidate_revision_root)

    publish_validated_generated_export_tree(
        context=context,
        joined=joined,
        semantic_map=semantic_map,
        rendered=rendered,
    )

    assert _tree_bytes(context.target_revision_root) == expected
    assert not _rollback_siblings(context.target_revision_root)


@pytest.mark.parametrize("defect", ("missing", "extra"))
def test_publication_refuses_invalid_candidate_without_changing_existing_target(
    _m200_snapshot,
    tmp_path,
    defect: str,
) -> None:
    """S10 refusal is the last pre-mutation gate, preserving target bytes exactly."""
    context, joined, semantic_map, rendered, candidate_revision_root = _publication_inputs(
        tmp_path,
        _m200_snapshot,
        existing_target=True,
    )
    before = _tree_bytes(context.target_revision_root)
    export_root = candidate_revision_root / "export"
    if defect == "missing":
        (export_root / rendered.output_files[-1]).unlink()
    else:
        (export_root / "0003-unreviewed-layout.toml").write_text("unreviewed = true\n", encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="exactly the current rendered outputs"):
        publish_validated_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
        )

    assert _tree_bytes(context.target_revision_root) == before
    assert candidate_revision_root.exists()
    assert not _rollback_siblings(context.target_revision_root)


def test_publication_restores_old_target_after_real_windows_locked_candidate_failure(_m200_snapshot, tmp_path) -> None:
    """A real Windows file handle forces the second rename to fail after rollback staging."""
    context, joined, semantic_map, rendered, candidate_revision_root = _publication_inputs(
        tmp_path,
        _m200_snapshot,
        existing_target=True,
    )
    before = _tree_bytes(context.target_revision_root)
    held_output = candidate_revision_root / "export" / rendered.output_files[0]

    with held_output.open("rb"), pytest.raises(RegistryValidationError, match="previous target was restored"):
        publish_validated_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
        )

    assert _tree_bytes(context.target_revision_root) == before
    assert candidate_revision_root.exists()
    assert not _rollback_siblings(context.target_revision_root)


def test_publication_module_has_no_old_tree_read_merge_or_copy_surface() -> None:
    """The publisher must stay a hard cutover instead of reviving compatibility behavior."""
    module = ast.parse(inspect.getsource(_generated_tree_publication))
    referenced_names = {node.id for node in ast.walk(module) if isinstance(node, ast.Name)}
    attribute_names = {node.attr for node in ast.walk(module) if isinstance(node, ast.Attribute)}
    source = inspect.getsource(_generated_tree_publication).casefold()

    assert not {
        "copytree",
        "copy2",
        "read_text",
        "read_bytes",
        "load_modelo_directory",
        "bundled_authority",
    }.intersection(referenced_names)
    assert not {"copytree", "copy2", "read_text", "read_bytes"}.intersection(attribute_names)
    assert "fallback" not in source
