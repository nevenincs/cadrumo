"""Stage isolated generated-export candidates with complete authority closure."""

from __future__ import annotations

import shutil
from collections.abc import Collection
from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path

from ..compiler.edition_materialisation import MaterialisedEdition, materialise_edition
from ..compiler.export_fragment_grammar import EXPORT_SECTION_DIRECTORY_NAMES
from ..compiler.loader import load_modelo_directory
from .bootstrap_construct_retarget import retarget_bootstrap_construct_export_layout
from .bootstrap_supersession import validate_bootstrap_manual_export_layout_supersession
from .bootstrap_targets import GeneratedExportBootstrapTarget
from .edition_candidate_staging import (
    drop_cross_edition_evolutions,
    edition_requires_detachment,
    write_complete_edition,
)
from .generated_export_inheritance_model import GeneratedExportInheritanceContext

__all__ = [
    "ignore_export_authority_directories",
    "stage_generated_export_candidate",
]


def ignore_export_authority_directories(_directory: str, names: Collection[str]) -> set[str]:
    """Return every loader-recognized export-authority directory in ``names``."""
    return set(EXPORT_SECTION_DIRECTORY_NAMES.intersection(names))


def stage_supplementary_orden_authority(
    source_root: Path,
    candidate_root: Path,
    *,
    modelos: Collection[str],
) -> None:
    """Copy supplementary Orden authority required by the staged modelo closure."""
    if "303" in modelos:
        shutil.copytree(source_root / "m303_orden_anual", candidate_root / "m303_orden_anual")


def _fact_provider_directories() -> frozenset[str]:
    root = bundled_path("registry", "aeat")
    skip = {"legal", "modelos", "user_profile", "m303_orden_anual"}
    return frozenset(entry.name for entry in root.iterdir() if entry.is_dir() and entry.name not in skip)


_FACT_PROVIDER_DIRECTORIES = _fact_provider_directories()


def stage_generated_export_candidate(
    source_root: Path,
    candidate_root: Path,
    *,
    modelo: str,
    revision: str,
    supporting_modelos: Collection[str],
    bootstrap_target: GeneratedExportBootstrapTarget | None = None,
    inheritance: GeneratedExportInheritanceContext | None = None,
) -> Path:
    """Stage the target's complete authority through the canonical loader.

    An ordinary candidate contains one detached complete edition. An attested
    generated-export child instead contains exactly its pinned baseline and
    thin child, retaining the storage chain needed to hydrate its layout.
    """
    if bootstrap_target is not None and (bootstrap_target.modelo, bootstrap_target.revision) != (modelo, revision):
        raise ValueError(
            f"bootstrap target {bootstrap_target.modelo}/{bootstrap_target.revision} cannot stage {modelo}/{revision}",
        )
    source_modelo_root = source_root / "modelos" / modelo
    source_revision_root = source_modelo_root / "revisions" / revision
    if bootstrap_target is not None and bootstrap_target.supersedes_layout_id is not None:
        validate_bootstrap_manual_export_layout_supersession(
            source_modelo_root,
            revision=revision,
            superseded_layout_id=bootstrap_target.supersedes_layout_id,
            expected_references=bootstrap_target.superseded_construct_references,
            generated_layout_id=bootstrap_target.layout_id,
            source_ref=bootstrap_target.source_ref,
            source_sha256=bootstrap_target.source_sha256,
            manual_origin_revision=bootstrap_target.manual_origin_revision,
        )
    elif (
        not (source_revision_root / "export").is_dir()
        and load_modelo_directory(source_modelo_root).revisions[revision].export_layouts
    ):
        raise ValueError(
            f"unreviewed hydrated manual export layout for {modelo}/{revision}; "
            "declare an exact bootstrap supersession before staging",
        )
    _stage_shared_candidate_authority(source_root, candidate_root, modelos={modelo, *supporting_modelos})
    if inheritance is None:
        edition = materialise_edition(source_modelo_root, revision)
        staged_modelo_root = _stage_candidate_modelo(
            source_modelo_root,
            candidate_root,
            modelo,
            revision,
            edition,
            bootstrap_target,
        )
    else:
        if bootstrap_target is not None:
            raise ValueError("generated export inheritance cannot share a manual-layout bootstrap")
        staged_modelo_root = stage_attested_inherited_modelo(
            source_modelo_root,
            candidate_root / "modelos" / modelo,
            revision=revision,
            inheritance=inheritance,
            include_target_export=False,
        )
    _stage_supporting_modelos(source_root, candidate_root, supporting_modelos)
    return staged_modelo_root


def stage_attested_inherited_modelo(
    source_modelo_root: Path,
    staged_modelo_root: Path,
    *,
    revision: str,
    inheritance: GeneratedExportInheritanceContext,
    include_target_export: bool,
) -> Path:
    """Stage the exact pinned ancestor chain and original thin child."""
    from .bootstrap_supersession import bootstrap_layout_supersession_fingerprint

    ancestors = inheritance.pinned_ancestors
    ancestor_ids = tuple(revision_id for revision_id, _digest in ancestors)
    if len(set((*ancestor_ids, revision))) != len(ancestor_ids) + 1:
        raise ValueError("generated export inheritance contains a repeated ancestor revision")
    for ancestor_id, digest in ancestors:
        ancestor_root = source_modelo_root / "revisions" / ancestor_id
        if bootstrap_layout_supersession_fingerprint(ancestor_root) != digest:
            raise ValueError(f"generated export inheritance ancestor {ancestor_id} changed before staging")
    if staged_modelo_root.exists():
        raise ValueError("generated export inheritance refuses an occupied staged modelo")
    revisions_root = staged_modelo_root / "revisions"
    revisions_root.mkdir(parents=True)
    shutil.copy2(source_modelo_root / "manifest.toml", staged_modelo_root / "manifest.toml")
    for selected_id in (*ancestor_ids, revision):
        source_revision_root = source_modelo_root / "revisions" / selected_id
        staged_revision_root = revisions_root / selected_id
        shutil.copytree(source_revision_root, staged_revision_root, ignore=ignore_export_authority_directories)
    root_id = ancestor_ids[0]
    root_edition = materialise_edition(source_modelo_root, root_id)
    write_complete_edition(revisions_root / root_id, root_edition)
    for ancestor_id in ancestor_ids:
        shutil.copytree(
            source_modelo_root / "revisions" / ancestor_id / "export",
            revisions_root / ancestor_id / "export",
        )
    if include_target_export:
        shutil.copytree(source_modelo_root / "revisions" / revision / "export", revisions_root / revision / "export")
    if include_target_export:
        loaded = load_modelo_directory(staged_modelo_root)
        if tuple(loaded.revisions) != (*ancestor_ids, revision):
            raise ValueError("generated export inheritance staged an unexpected revision")
        if loaded.revisions[ancestor_ids[-1]].export_layouts != (inheritance.baseline_layout,):
            raise ValueError("generated export inheritance staged a different baseline layout")
    return staged_modelo_root


def _stage_shared_candidate_authority(
    source_root: Path,
    candidate_root: Path,
    *,
    modelos: Collection[str],
) -> None:
    shutil.copytree(source_root / "legal", candidate_root / "legal")
    # The governed-fact provider directories are part of the authority a
    # candidate must validate against, not optional decoration: the registry
    # load resolves them by name, so a candidate root without them fails to
    # fingerprint rather than validating a narrower tree. Staged whole, like
    # `legal`, and staged by iteration so a directory added later is carried
    # without this list being the thing that remembered to mention it.
    for provider_directory in sorted(_FACT_PROVIDER_DIRECTORIES):
        source_provider = source_root / provider_directory
        if source_provider.is_dir():
            shutil.copytree(source_provider, candidate_root / provider_directory)
    stage_supplementary_orden_authority(source_root, candidate_root, modelos=modelos)


def _stage_candidate_modelo(
    source_modelo_root: Path,
    candidate_root: Path,
    modelo: str,
    revision: str,
    edition: MaterialisedEdition,
    bootstrap_target: GeneratedExportBootstrapTarget | None,
) -> Path:
    staged_modelo_root = candidate_root / "modelos" / modelo
    shutil.copytree(
        source_modelo_root,
        staged_modelo_root,
        ignore=ignore_export_authority_directories,
    )
    for sibling in (staged_modelo_root / "revisions").iterdir():
        if sibling.name != revision:
            shutil.rmtree(sibling)
    if edition_requires_detachment(edition):
        write_complete_edition(staged_modelo_root / "revisions" / revision, edition)
    drop_cross_edition_evolutions(staged_modelo_root / "revisions" / revision)
    if bootstrap_target is not None and bootstrap_target.supersedes_layout_id is not None:
        retarget_bootstrap_construct_export_layout(
            staged_modelo_root,
            revision=revision,
            superseded_layout_id=bootstrap_target.supersedes_layout_id,
            generated_layout_id=bootstrap_target.layout_id,
            expected_references=bootstrap_target.superseded_construct_references,
        )
    return staged_modelo_root


def _stage_supporting_modelos(
    source_root: Path,
    candidate_root: Path,
    supporting_modelos: Collection[str],
) -> None:
    for supporting_modelo in supporting_modelos:
        shutil.copytree(
            source_root / "modelos" / supporting_modelo,
            candidate_root / "modelos" / supporting_modelo,
        )
