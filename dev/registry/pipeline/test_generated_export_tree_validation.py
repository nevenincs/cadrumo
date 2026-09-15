"""Real registry-authority proofs for generated export-tree validation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryError, RegistryValidationError

from ._export_tree import RenderedExportTree
from ._generated_tree_test_support import (
    ISOLATED_TREE,
    isolated_export_root,
    isolated_render_profile,
    write_isolated_generated_authority_tree,
)
from ._tree_validation import (
    GeneratedExportTreeValidationContext,
    ValidatedGeneratedExportTree,
    validate_generated_export_tree,
)
from .export_fragment_provenance import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    export_fragment_provenance_manifest_json_bytes,
    load_export_fragment_provenance_manifest,
)
from .joined_record_design import JoinedRecordDesign
from .semantic_map import SemanticMap

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _validate(
    context: GeneratedExportTreeValidationContext,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
) -> ValidatedGeneratedExportTree:
    """Validate with the isolated tree's real render profile and source evidence."""
    render_profile, render_evidence = isolated_render_profile()
    return validate_generated_export_tree(
        context=context,
        joined=joined,
        semantic_map=semantic_map,
        rendered=rendered,
        render_profile=render_profile,
        render_profile_source_evidence=render_evidence,
    )


def test_generated_tree_validation_requires_real_loader_and_authority_selection(tmp_path: Path) -> None:
    """A fresh target must compile, attest, and select through the production authority."""
    context, joined, semantic_map, rendered, _export_root = write_isolated_generated_authority_tree(tmp_path)

    validated = _validate(context, joined, semantic_map, rendered)

    assert validated.target == context.target
    assert validated.layout == rendered.layout
    assert validated.provenance_manifest == rendered.provenance_manifest
    assert validated.snapshot.modelo.id == ISOLATED_TREE.modelo
    assert validated.snapshot.revision.id == ISOLATED_TREE.revision
    assert validated.snapshot.revision.export_layouts == (rendered.layout,)


def test_generated_tree_validation_selects_from_the_isolated_registry_not_the_published_bundle(
    tmp_path: Path,
) -> None:
    """Authority selection compiles the isolated candidate, which holds only its target revision.

    The published registry carries the target's predecessor editions, so a
    selection that read it would satisfy strict lineage continuation. The
    isolated candidate does not, and without the separately staged continuity
    witness its lineage check must refuse.
    """
    context, joined, semantic_map, rendered, _export_root = write_isolated_generated_authority_tree(tmp_path)

    with pytest.raises(RegistryValidationError, match="has no predecessor edition to continue"):
        _validate(replace(context, continuity_metadata_modelo_root=None), joined, semantic_map, rendered)


def test_generated_tree_validation_refuses_partial_or_non_generated_export_siblings(tmp_path: Path) -> None:
    """Missing output and a non-generated sibling both refuse before any publication path exists."""
    context, joined, semantic_map, rendered, export_root = write_isolated_generated_authority_tree(tmp_path)
    (export_root / rendered.output_files[-1]).unlink()

    with pytest.raises(RegistryValidationError, match="exactly the current rendered outputs"):
        _validate(context, joined, semantic_map, rendered)

    context, joined, semantic_map, rendered, export_root = write_isolated_generated_authority_tree(
        tmp_path / "sibling",
    )
    legal_refs = ", ".join(f'"{ref}"' for ref in rendered.layout.legal_refs)
    (export_root / "0003-unreviewed-layout.toml").write_text(
        f'[[revisions."{ISOLATED_TREE.revision}".export_layouts]]\n'
        'id = "unreviewed-layout"\n'
        'format = "fixed_width"\n'
        f'source_refs = ["{ISOLATED_TREE.source_ref}"]\n'
        f"legal_refs = [{legal_refs}]\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(RegistryValidationError, match="exactly the current rendered outputs"):
        _validate(context, joined, semantic_map, rendered)


def test_generated_tree_validation_refuses_direct_modelo_file_and_malformed_output(tmp_path: Path) -> None:
    """No single-file modelo or malformed output reaches authority selection."""
    context, joined, semantic_map, rendered, _export_root = write_isolated_generated_authority_tree(tmp_path)
    (context.registry_root / "modelos" / "200.toml").write_text("[modelo]\nid = '200'\n", encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="generated registry modelos root must contain exactly"):
        _validate(context, joined, semantic_map, rendered)

    context, joined, semantic_map, rendered, export_root = write_isolated_generated_authority_tree(
        tmp_path / "malformed",
    )
    (export_root / rendered.output_files[0]).write_text("[revisions\n", encoding="utf-8")

    with pytest.raises(RegistryError, match="invalid TOML"):
        _validate(context, joined, semantic_map, rendered)


def test_generated_tree_validation_refuses_stale_sibling_provenance(tmp_path: Path) -> None:
    """A provenance manifest beside the export directory, rather than inside it, is refused."""
    context, joined, semantic_map, rendered, export_root = write_isolated_generated_authority_tree(tmp_path)
    (export_root.parent / "export.provenance.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="stale sibling export provenance"):
        _validate(context, joined, semantic_map, rendered)


def test_generated_tree_validation_refuses_wrong_period_and_provenance_drift(tmp_path: Path) -> None:
    """The exact target must apply to its filing context and retain current authority evidence."""
    context, joined, semantic_map, rendered, _export_root = write_isolated_generated_authority_tree(tmp_path)

    with pytest.raises(RegistryError, match="no revision for year"):
        _validate(replace(context, period="1T"), joined, semantic_map, rendered)

    with pytest.raises(RegistryValidationError, match="'303'"):
        _validate(
            replace(context, target=context.target.model_copy(update={"modelo": "303"})),
            joined,
            semantic_map,
            rendered,
        )

    with pytest.raises(RegistryValidationError, match="'2026'"):
        _validate(
            replace(context, target=context.target.model_copy(update={"revision_id": "2026"})),
            joined,
            semantic_map,
            rendered,
        )

    manifest_path = isolated_export_root(context.registry_root) / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
    manifest_path.write_bytes(
        export_fragment_provenance_manifest_json_bytes(manifest.model_copy(update={"source_sha256": "b" * 64})),
    )
    with pytest.raises(RegistryValidationError, match="current generation authorities"):
        _validate(context, joined, semantic_map, rendered)
