"""Isolated generated-tree fixtures that never enumerate bundled modelos."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Final

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

from ..compiler.loader import load_modelo_directory, load_shared_catalogues
from ._export_tree import ExportTreeTransportProfile, RenderedExportTree, render_complete_export_tree
from ._tree_validation import GeneratedExportTreeValidationContext
from .candidate_staging import (
    generated_export_bootstrap_target,
    stage_continuity_metadata,
    stage_generated_export_candidate,
)
from .export_fragment_provenance import ExportFragmentTarget
from .generated_tree_inventory import GeneratedExportTree
from .joined_record_design import JoinedRecordDesign, join_record_design_semantics
from .record_design_intermediate import load_record_design_intermediate
from .render_profile import (
    RenderProfile,
    RenderProfileSourceEvidence,
    load_render_profile,
    load_render_profile_source_evidence,
)
from .semantic_map import SemanticMap, load_semantic_map

#: The enrolled generated tree the isolated fixtures materialise.
#:
#: The export-completeness gate reads the real record design named by the
#: revision's ``source_refs``, so only a real bundled tree can pass generated-tree
#: validation. Modelo 184 is used because its storage-only ancestry exercises
#: detached target staging while its filing-grade authority remains selectable
#: at the catalogue-derived supported coordinate.
ISOLATED_TREE: Final[GeneratedExportTree] = GeneratedExportTree(
    "184", "2025-y-siguientes", "aeat-dr-184-2025", "2025", 2025, "0A"
)


def isolated_authority(tree: GeneratedExportTree, root: Path) -> Path:
    """Stage one modelo's non-export authority without loading unrelated modelos."""
    registry_root = root / "registry" / "aeat"
    catalogues = load_shared_catalogues(bundled_path("registry", "aeat"))
    source = catalogues.sources.get(tree.source_ref)
    if source is None:
        raise AssertionError(f"{tree}: declared render source {tree.source_ref!r} is absent")
    bootstrap_target = generated_export_bootstrap_target(
        modelo=tree.modelo,
        revision=tree.revision,
        source_ref=tree.source_ref,
        source_sha256=source.sha256,
    )
    modelo_root = stage_generated_export_candidate(
        bundled_path("registry", "aeat"),
        registry_root,
        modelo=tree.modelo,
        revision=tree.revision,
        supporting_modelos=_supporting_modelos(tree),
        bootstrap_target=bootstrap_target,
    )
    if (modelo_root / "revisions" / tree.revision / "export").exists():
        raise AssertionError("the isolated candidate copied its generated export")
    if (modelo_root / "revisions" / tree.revision / "export_layouts").exists():
        raise AssertionError("the isolated candidate copied its superseded export layouts")
    return registry_root


_SOURCE_MODELO_RE: Final[re.Pattern[str]] = re.compile(
    r'^\s*source_modelo\s*=\s*"(?P<modelo>[^"]+)"',
    re.MULTILINE,
)


def _supporting_modelos(tree: GeneratedExportTree) -> frozenset[str]:
    modelo_root = bundled_path("registry", "aeat", "modelos", tree.modelo)
    referenced: set[str] = set()
    for path in modelo_root.rglob("*.toml"):
        referenced.update(match.group("modelo") for match in _SOURCE_MODELO_RE.finditer(path.read_text("utf-8")))
    return frozenset(
        modelo for modelo in referenced - {tree.modelo} if bundled_path("registry", "aeat", "modelos", modelo).is_dir()
    )


@cache
def bundled_revision_inspection(modelo: str, revision: str) -> RegistryRevisionInspection:
    """The static admission facts of one bundled revision, loaded through the canonical directory loader.

    Memoised per coordinate: the inspection is frozen and its inputs are
    checked-in registry sources that a test session never mutates.
    """
    registry_root = bundled_path("registry", "aeat")
    catalogues = load_shared_catalogues(registry_root)
    definition = load_modelo_directory(registry_root / "modelos" / modelo)
    return RegistryRevisionInspection.from_revision(
        modelo=definition,
        revision=definition.revisions[revision],
        source_root=bundled_path(),
        sources=catalogues.sources,
        legal_ref_ids=frozenset(catalogues.legal),
    )


@cache
def isolated_authorities(
    tree: GeneratedExportTree,
) -> tuple[JoinedRecordDesign, SemanticMap, ExportTreeTransportProfile, RenderProfile, RenderProfileSourceEvidence]:
    """Return the real (joined, semantic map, transport, render profile, evidence) for one tree.

    Loads only the selected modelo plus its shared catalogue and source evidence.
    The result is memoised per tree: every returned model is frozen, and its
    inputs are checked-in authoring sources that a test session never mutates.
    Tests derive defects with ``model_copy`` and stage their own on-disk trees.
    """
    semantic_map = load_semantic_map(Path(f"dev/registry/mappings/modelo_{tree.modelo}") / tree.epoch)
    render_profile = load_render_profile(Path(f"dev/registry/render_profiles/modelo_{tree.modelo}") / tree.epoch)
    catalogues = load_shared_catalogues(bundled_path("registry", "aeat"))
    inspection = bundled_revision_inspection(tree.modelo, tree.revision)
    intermediate = load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref=tree.source_ref,
        filing_year=tree.filing_year,
        design_epoch=tree.epoch,
    )
    joined = join_record_design_semantics(semantic_map, intermediate, inspection)
    transport = ExportTreeTransportProfile(
        modelo=tree.modelo,
        design_epoch=tree.epoch,
        source_ref=tree.source_ref,
        source_sha256=intermediate.source.source_sha256,
        layout_id=tree.layout_id,
        format="fixed_width",
        encoding=ExportEncoding.ISO_8859_1,
        line_ending="crlf",
        serializer_convention="rtoml-pretty-v1",
    )
    claims_official = any(
        rule.evidence.authority_kind != "reviewed_policy"
        for rule in (*render_profile.singleton_rules, *render_profile.width_17_rules)
    )
    evidence = (
        load_render_profile_source_evidence(
            bundled_path() / catalogues.sources[tree.source_ref].corpus_path,
            render_profile,
        )
        if claims_official
        else RenderProfileSourceEvidence(design_identity=render_profile.design_identity, entries=())
    )
    return joined, semantic_map, transport, render_profile, evidence


def isolated_render_profile() -> tuple[RenderProfile, RenderProfileSourceEvidence]:
    """The real render profile for the isolated tree, and its source evidence.

    Validation checks the profile's design identity against the tree's, so a
    synthetic profile cannot stand in for the real one beside a real tree.
    """
    _joined, _map, _transport, render_profile, evidence = isolated_authorities(ISOLATED_TREE)
    return render_profile, evidence


def isolated_export_root(registry_root: Path) -> Path:
    """The isolated tree's export directory beneath one staged registry root."""
    return registry_root / "modelos" / ISOLATED_TREE.modelo / "revisions" / ISOLATED_TREE.revision / "export"


def stage_isolated_validation_context(root: Path) -> GeneratedExportTreeValidationContext:
    """Stage the isolated tree's non-export authority and continuity witness, without an export."""
    return GeneratedExportTreeValidationContext(
        registry_root=isolated_authority(ISOLATED_TREE, root / "candidate"),
        source_root=bundled_path(),
        target=ExportFragmentTarget(
            modelo=ISOLATED_TREE.modelo,
            revision_id=ISOLATED_TREE.revision,
            design_epoch=ISOLATED_TREE.epoch,
        ),
        filing_year=ISOLATED_TREE.filing_year,
        period=ISOLATED_TREE.period,
        continuity_metadata_modelo_root=stage_continuity_metadata(
            bundled_path("registry", "aeat", "modelos", ISOLATED_TREE.modelo),
            root,
            revision=ISOLATED_TREE.revision,
        ),
    )


def render_isolated_export(registry_root: Path) -> tuple[JoinedRecordDesign, SemanticMap, RenderedExportTree, Path]:
    """Render the isolated tree's export afresh into one staged registry root.

    The export directory is never copied: it is written solely through the
    export-tree renderer, so a validation cannot pass by loading an older
    fragment tree.
    """
    joined, semantic_map, transport, render_profile, render_evidence = isolated_authorities(ISOLATED_TREE)
    export_root = isolated_export_root(registry_root)
    if export_root.exists():
        raise AssertionError("the isolated authority must not carry an export before rendering")
    rendered = render_complete_export_tree(
        export_root,
        revision_id=ISOLATED_TREE.revision,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=transport,
        render_profile=render_profile,
        render_profile_source_evidence=render_evidence,
    )
    return joined, semantic_map, rendered, export_root


def write_isolated_generated_authority_tree(
    root: Path,
) -> tuple[GeneratedExportTreeValidationContext, JoinedRecordDesign, SemanticMap, RenderedExportTree, Path]:
    """Materialise the isolated tree's real non-export authority plus a freshly rendered export."""
    context = stage_isolated_validation_context(root)
    joined, semantic_map, rendered, export_root = render_isolated_export(context.registry_root)
    return context, joined, semantic_map, rendered, export_root
