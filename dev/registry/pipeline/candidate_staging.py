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
) -> Path:
    """Stage one revision's complete non-export authority through a single boundary.

    The candidate holds the target as its modelo's only edition. An edition
    naming a predecessor states only the rows it changed, and pruning its
    siblings deletes the chain the rest come from, so such a target is staged as
    the complete edition the loader resolves for it, naming no predecessor. An
    edition whose named predecessor is absent is refused by that resolution.
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
    edition = materialise_edition(source_modelo_root, revision)
    _stage_shared_candidate_authority(source_root, candidate_root, modelos={modelo, *supporting_modelos})
    staged_modelo_root = _stage_candidate_modelo(
        source_modelo_root,
        candidate_root,
        modelo,
        revision,
        edition,
        bootstrap_target,
    )
    _stage_supporting_modelos(source_root, candidate_root, supporting_modelos)
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
