"""Real registry-authority proofs for generated export-tree validation."""

from __future__ import annotations

import ast
import inspect
from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryError, RegistryValidationError

from ..pipeline._export_tree import RenderedExportTree, render_complete_export_tree
from ..pipeline._provenance_manifest import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    ExportFragmentTarget,
    export_fragment_provenance_manifest_json_bytes,
    load_export_fragment_provenance_manifest,
)
from ..pipeline._semantic_map import SemanticMap
from ..pipeline._semantic_map_join import JoinedRecordDesign
from ..pipeline._tree_validation import (
    GeneratedExportTreeValidationContext,
    validate_generated_export_tree,
)
from .test_export_tree import _wire_evidence, _wire_profile
from .test_generated_export_trees import (
    _authorities as _enrolled_authorities,
)
from .test_generated_export_trees import (
    _GeneratedTree,
    _isolated_authority,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


#: Floor for the parsed surface below. Live: 116 referenced names.
_MINIMUM_VALIDATION_NAMES = 38

#: Floor for the ATTRIBUTE surface of the same parse. The floor above counts
#: ast.Name nodes and does not reach these: a module can hold plenty of names
#: while its attribute set empties, and the forbidden entries most likely to
#: return -- ``shutil.copytree``, ``path.read_text`` -- are ATTRIBUTES, so the
#: unguarded claim was the load-bearing one. Live: 36 attribute names.
_MINIMUM_VALIDATION_ATTRIBUTES = 12


def _real_authorities(tree: _GeneratedTree):
    """Return the real (joined, semantic map, transport, render profile, evidence).

    A thin adapter over the enrolled drift gate's own `_authorities`, so this
    fixture and that gate cannot disagree about how a generated tree is built.
    """
    semantic_map, render_profile, joined, evidence, transport = _enrolled_authorities(tree)
    return joined, semantic_map, transport, render_profile, evidence


#: The enrolled generated tree this fixture materialises in isolation.
#:
#: It used to hand-assemble a synthetic modelo/revision and render a two-sheet
#: toy layout into it. The export-completeness gate reads the REAL design named
#: by the revision's `source_refs`, so that layout covered 3 of the 41 positions
#: modelo 130's diseño requires and validation refused -- correctly. No synthetic
#: layout can satisfy that gate against a real design, and no bundled design is
#: small enough to be covered by a toy.
#:
#: Modelo 184 is used instead because it is ENROLLED in the generated-tree drift
#: gate, so its real diseño and real semantic map are already proven to render a
#: complete, valid tree. It also carries NO supporting modelo and exactly ONE
#: revision, so the isolated candidate needs no staged neighbour -- modelo 202,
#: the first choice, folds in modelo 200 and the candidate root must contain
#: exactly the target modelo.
#:
#: It no longer carries exactly one revision: the split at Orden HAC/1430/2025's
#: boundary gave it `2015-2024` and `2025-y-siguientes`, so the isolation does
#: prune a sibling now. The tree named here is the later half, which is the one
#: the 2025 design and its `2025` epoch belong to.
_ISOLATED_TREE: Final[_GeneratedTree] = _GeneratedTree(
    "184", "2025-y-siguientes", "aeat-dr-184-2025", "2025", 2025, "0A"
)


def _isolated_render_profile():
    """The REAL render profile for the isolated tree, and its source evidence.

    Validation checks the profile's design identity against the tree's, so the
    synthetic wire profile cannot be passed alongside a real generated tree.
    """
    _joined, _map, _transport, render_profile, evidence = _real_authorities(_ISOLATED_TREE)
    return render_profile, evidence


def _write_isolated_generated_authority_tree(
    tmp_path: Path,
    snapshot=None,
) -> tuple[GeneratedExportTreeValidationContext, JoinedRecordDesign, SemanticMap, RenderedExportTree, Path]:
    """Materialise the target's real NON-export authority plus a freshly rendered export.

    The export directory is never copied: it is written solely through the
    export-tree renderer, so generated-tree validation cannot pass by loading an
    older fragment tree. Everything else comes from the shipped registry through
    the same two helpers the enrolled drift gate uses, so this fixture cannot
    drift from what a real generated tree looks like.

    ``snapshot`` is accepted and ignored: callers pass a revision inspection that
    the real authorities now supersede.
    """
    registry_root = _isolated_authority(_ISOLATED_TREE, tmp_path / "candidate")
    joined, semantic_map, transport, render_profile, render_evidence = _real_authorities(_ISOLATED_TREE)

    export_root = registry_root / "modelos" / _ISOLATED_TREE.modelo / "revisions" / _ISOLATED_TREE.revision / "export"
    assert not export_root.exists(), "the authority fixture must not copy legacy export fragments"
    rendered = render_complete_export_tree(
        export_root,
        revision_id=_ISOLATED_TREE.revision,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=transport,
        render_profile=render_profile,
        render_profile_source_evidence=render_evidence,
    )
    context = GeneratedExportTreeValidationContext(
        registry_root=registry_root,
        source_root=bundled_path(),
        target=ExportFragmentTarget(
            modelo=_ISOLATED_TREE.modelo,
            revision_id=_ISOLATED_TREE.revision,
            design_epoch=_ISOLATED_TREE.epoch,
        ),
        filing_year=_ISOLATED_TREE.filing_year,
        period=_ISOLATED_TREE.period,
    )
    return context, joined, semantic_map, rendered, export_root


def test_generated_tree_validation_requires_real_loader_and_authority_selection(
    m130_inspection_snapshot, tmp_path
) -> None:
    """A fresh target must compile, attest, and select through the production authority."""
    context, joined, semantic_map, rendered, _export_root = _write_isolated_generated_authority_tree(
        tmp_path,
        m130_inspection_snapshot,
    )

    validated = validate_generated_export_tree(
        context=context,
        joined=joined,
        semantic_map=semantic_map,
        rendered=rendered,
        render_profile=_isolated_render_profile()[0],
        render_profile_source_evidence=_isolated_render_profile()[1],
    )

    assert validated.target == context.target
    assert validated.layout == rendered.layout
    assert validated.provenance_manifest == rendered.provenance_manifest
    assert validated.snapshot.modelo.id == _ISOLATED_TREE.modelo
    assert validated.snapshot.revision.id == _ISOLATED_TREE.revision
    assert validated.snapshot.revision.export_layouts == (rendered.layout,)


def test_generated_tree_validation_refuses_partial_or_non_generated_export_siblings(
    m130_inspection_snapshot, tmp_path
) -> None:
    """Missing output and a legacy-style sibling both refuse before any publication path exists."""
    context, joined, semantic_map, rendered, export_root = _write_isolated_generated_authority_tree(
        tmp_path,
        m130_inspection_snapshot,
    )
    (export_root / rendered.output_files[-1]).unlink()

    with pytest.raises(RegistryValidationError, match="exactly the current rendered outputs"):
        validate_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )

    context, joined, semantic_map, rendered, export_root = _write_isolated_generated_authority_tree(
        tmp_path / "sibling",
        m130_inspection_snapshot,
    )
    (export_root / "0003-unreviewed-layout.toml").write_text(
        """
[revisions."2025"]
[[revisions."2025".export_layouts]]
id = "unreviewed-layout"
format = "fixed_width"
source_refs = ["aeat-dr-130-2019-v12"]
legal_refs = ["rd-439-2007:art-110"]
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(RegistryValidationError, match="exactly the current rendered outputs"):
        validate_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )


def test_generated_tree_validation_refuses_direct_revision_legacy_and_loader_breakage(
    m130_inspection_snapshot, tmp_path
) -> None:
    """No single-file modelo, direct revision fallback, or malformed output reaches authority selection."""
    context, joined, semantic_map, rendered, _export_root = _write_isolated_generated_authority_tree(
        tmp_path,
        m130_inspection_snapshot,
    )
    (context.registry_root / "modelos" / "200.toml").write_text("[modelo]\nid = '200'\n", encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="generated registry modelos root must contain exactly"):
        validate_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )

    context, joined, semantic_map, rendered, export_root = _write_isolated_generated_authority_tree(
        tmp_path / "malformed",
        m130_inspection_snapshot,
    )
    (export_root / rendered.output_files[0]).write_text("[revisions\n", encoding="utf-8")

    with pytest.raises(RegistryError):
        validate_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_wire_profile(),
            render_profile_source_evidence=_wire_evidence(),
        )


def test_generated_tree_validation_refuses_stale_sibling_provenance(m130_inspection_snapshot, tmp_path) -> None:
    """The former outside-export attestation path cannot survive the hard cutover."""
    context, joined, semantic_map, rendered, export_root = _write_isolated_generated_authority_tree(
        tmp_path,
        m130_inspection_snapshot,
    )
    (export_root.parent / "export.provenance.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="stale sibling export provenance"):
        validate_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )


def test_generated_tree_validation_refuses_wrong_period_and_provenance_drift(
    m130_inspection_snapshot, tmp_path
) -> None:
    """The exact target must apply to its filing context and retain current authority evidence."""
    context, joined, semantic_map, rendered, _export_root = _write_isolated_generated_authority_tree(
        tmp_path,
        m130_inspection_snapshot,
    )

    with pytest.raises(RegistryError, match="no revision for year"):
        validate_generated_export_tree(
            context=replace(context, period="1T"),
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )

    with pytest.raises(RegistryValidationError, match="'303'"):
        validate_generated_export_tree(
            context=replace(
                context,
                target=context.target.model_copy(update={"modelo": "303"}),
            ),
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )

    with pytest.raises(RegistryValidationError, match="'2026'"):
        validate_generated_export_tree(
            context=replace(
                context,
                target=context.target.model_copy(update={"revision_id": "2026"}),
            ),
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )

    manifest_path = (
        context.registry_root
        / "modelos"
        / _ISOLATED_TREE.modelo
        / "revisions"
        / _ISOLATED_TREE.revision
        / "export"
        / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    )
    manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
    manifest_path.write_bytes(
        export_fragment_provenance_manifest_json_bytes(manifest.model_copy(update={"source_sha256": "b" * 64})),
    )
    with pytest.raises(RegistryValidationError, match="current generation authorities"):
        validate_generated_export_tree(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=_isolated_render_profile()[0],
            render_profile_source_evidence=_isolated_render_profile()[1],
        )


def test_generated_tree_validation_module_has_no_legacy_loader_surface() -> None:
    """The generated-tree validation boundary must not reintroduce legacy reader or fallback APIs."""
    # The module was renamed and rehomed in the authoring-tree deconflation:
    # `dev/registry/_generated_tree_validation.py` is now
    # `dev/registry/pipeline/_tree_validation.py`. The import was left behind, so
    # this case died on ImportError rather than proving anything about the
    # boundary it guards.
    from ..pipeline import _tree_validation

    module = ast.parse(inspect.getsource(_tree_validation))
    referenced_names = {node.id for node in ast.walk(module) if isinstance(node, ast.Name)}

    # An absence claim over an EMPTY surface is satisfied by construction.
    # This module carries 116 referenced names today; a gutted or stubbed
    # one would satisfy every forbidden-name assertion below without the
    # boundary existing at all. A floor, not a pinned count.
    assert len(referenced_names) >= _MINIMUM_VALIDATION_NAMES, (
        f"the validation boundary parsed to only {len(referenced_names)} referenced name(s); below "
        "this an absence claim proves nothing about the boundary it guards"
    )
    attribute_names = {node.attr for node in ast.walk(module) if isinstance(node, ast.Attribute)}
    assert len(attribute_names) >= _MINIMUM_VALIDATION_ATTRIBUTES, (
        f"the validation boundary parsed to only {len(attribute_names)} attribute name(s); below "
        "this the forbidden-attribute claim below holds because the parse reached no "
        "attributes, not because the boundary is clean"
    )
    forbidden = {
        "bundled_authority",
        "load_modelo_file",
        "load_modelo_path",
        "resolve_export_layout",
        "copytree",
    }

    assert not forbidden.intersection(referenced_names)
    assert not forbidden.intersection(attribute_names)
