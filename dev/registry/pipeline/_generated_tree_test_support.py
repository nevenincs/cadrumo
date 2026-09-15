"""Isolated generated-tree fixtures that never enumerate bundled modelos."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

from ..compiler.loader import load_modelo_directory, load_shared_catalogues
from ._export_tree import ExportTreeTransportProfile
from .candidate_staging import generated_export_bootstrap_target, stage_generated_export_candidate
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
        modelo
        for modelo in referenced - {tree.modelo}
        if bundled_path("registry", "aeat", "modelos", modelo).is_dir()
    )


def isolated_authorities(
    tree: GeneratedExportTree,
) -> tuple[SemanticMap, RenderProfile, JoinedRecordDesign, RenderProfileSourceEvidence, ExportTreeTransportProfile]:
    """Load only the selected modelo plus its shared catalogue and source evidence."""
    semantic_map = load_semantic_map(Path(f"dev/registry/mappings/modelo_{tree.modelo}") / tree.epoch)
    render_profile = load_render_profile(Path(f"dev/registry/render_profiles/modelo_{tree.modelo}") / tree.epoch)
    registry_root = bundled_path("registry", "aeat")
    catalogues = load_shared_catalogues(registry_root)
    modelo = load_modelo_directory(registry_root / "modelos" / tree.modelo)
    inspection = RegistryRevisionInspection.from_revision(
        modelo=modelo,
        revision=modelo.revisions[tree.revision],
        source_root=bundled_path(),
        sources=catalogues.sources,
        legal_ref_ids=frozenset(catalogues.legal),
    )
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
    return semantic_map, render_profile, joined, evidence, transport
