"""Shared exclusions for isolated generated-export candidate authority.

Candidates must contain the authored revision authority and no pre-existing
export authority. The registry loader accepts both the current ``export/``
fragment directory and the superseded ``export_layouts/`` form, so excluding
only one lets a legacy tree participate in validation of its replacement.
"""

from __future__ import annotations

import shutil
import tomllib
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import rtoml

from cadrumo.domain.calculations.registry.loader import load_modelo_directory

__all__ = [
    "GeneratedExportBootstrapTarget",
    "generated_export_bootstrap_target",
    "ignore_export_authority_directories",
    "retarget_bootstrap_construct_export_layout",
    "stage_continuity_metadata",
    "stage_generated_export_candidate",
    "stage_supplementary_orden_authority",
]


_EXPORT_AUTHORITY_DIRECTORY_NAMES: Final[frozenset[str]] = frozenset({"export", "export_layouts"})
_BOOTSTRAP_TARGETS_PATH: Final[Path] = Path(__file__).with_name("generated_export_bootstrap_targets.toml")


@dataclass(frozen=True, slots=True)
class GeneratedExportBootstrapTarget:
    """One reviewed transport and supersession declaration for an unpublished tree."""

    modelo: str
    revision: str
    source_ref: str
    source_sha256: str
    layout_id: str
    line_ending: Literal["crlf", "lf", "none"]
    supersedes_layout_id: str | None
    superseded_construct_references: int


def generated_export_bootstrap_target(
    *,
    modelo: str,
    revision: str,
    source_ref: str,
    source_sha256: str,
) -> GeneratedExportBootstrapTarget | None:
    """Return the uniquely matching reviewed bootstrap declaration, if one exists."""
    payload = tomllib.loads(_BOOTSTRAP_TARGETS_PATH.read_text("utf-8"))
    matches = [
        row
        for row in payload.get("targets", [])
        if row.get("modelo") == modelo
        and row.get("revision") == revision
        and row.get("source_ref") == source_ref
        and row.get("source_sha256") == source_sha256
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError(f"multiple generated-export bootstrap targets match {modelo}/{revision}/{source_ref}")
    row = matches[0]
    line_ending = row.get("line_ending")
    if line_ending not in {"crlf", "lf", "none"}:
        raise ValueError("reviewed generated-export bootstrap target has invalid line ending")
    supersedes_layout_id = row.get("supersedes_layout_id")
    superseded_construct_references = row.get("superseded_construct_references", 0)
    if supersedes_layout_id is not None and (not isinstance(supersedes_layout_id, str) or not supersedes_layout_id):
        raise ValueError("reviewed generated-export bootstrap target has invalid superseded layout id")
    if not isinstance(superseded_construct_references, int) or superseded_construct_references < 0:
        raise ValueError("reviewed generated-export bootstrap target has invalid superseded construct-reference count")
    if (supersedes_layout_id is None) != (superseded_construct_references == 0):
        raise ValueError("reviewed generated-export bootstrap target must pair its superseded layout and references")
    return GeneratedExportBootstrapTarget(
        modelo=str(row["modelo"]),
        revision=str(row["revision"]),
        source_ref=str(row["source_ref"]),
        source_sha256=str(row["source_sha256"]),
        layout_id=str(row["layout_id"]),
        line_ending=line_ending,
        supersedes_layout_id=supersedes_layout_id,
        superseded_construct_references=superseded_construct_references,
    )


def ignore_export_authority_directories(_directory: str, names: Collection[str]) -> set[str]:
    """Return every loader-recognized export-authority directory in ``names``."""
    return set(_EXPORT_AUTHORITY_DIRECTORY_NAMES.intersection(names))


def stage_supplementary_orden_authority(
    source_root: Path,
    candidate_root: Path,
    *,
    modelos: Collection[str],
) -> None:
    """Copy supplementary Orden authority required by the staged modelo closure."""
    if "303" in modelos:
        shutil.copytree(source_root / "m303_orden_anual", candidate_root / "m303_orden_anual")


def stage_continuity_metadata(
    source_modelo_root: Path,
    staging_root: Path,
    *,
    revision: str,
) -> Path | None:
    """Stage the transitive predecessor facts required by strict continuity."""
    definition = load_modelo_directory(source_modelo_root)
    selected = definition.revisions.get(revision)
    if selected is None:
        raise ValueError(f"modelo {definition.id} declares no revision {revision!r}")

    pending = {str(item.from_revision) for item in selected.casilla_continuidad_evolutions}
    predecessors: set[str] = set()
    while pending:
        predecessor_id = min(pending)
        pending.remove(predecessor_id)
        if predecessor_id == revision:
            raise ValueError(f"revision {revision!r} continuity predecessor chain is cyclic")
        if predecessor_id in predecessors:
            continue
        predecessor = definition.revisions.get(predecessor_id)
        if predecessor is None:
            raise ValueError(
                f"revision {revision!r} continuity predecessor {predecessor_id!r} is not declared",
            )
        predecessors.add(predecessor_id)
        pending.update(str(item.from_revision) for item in predecessor.casilla_continuidad_evolutions)

    if not predecessors:
        return None
    metadata_modelo_root = staging_root / "continuity-metadata" / str(definition.id)
    metadata_modelo_root.mkdir(parents=True)
    shutil.copy2(source_modelo_root / "manifest.toml", metadata_modelo_root / "manifest.toml")
    for predecessor_id in sorted(predecessors):
        source_revision_root = source_modelo_root / "revisions" / predecessor_id
        target_revision_root = metadata_modelo_root / "revisions" / predecessor_id
        target_revision_root.mkdir(parents=True)
        shutil.copy2(source_revision_root / "revision.toml", target_revision_root / "revision.toml")
        for member in ("casillas", "casilla_continuidad_evolutions"):
            source_member = source_revision_root / member
            if source_member.is_dir():
                shutil.copytree(source_member, target_revision_root / member)
    return metadata_modelo_root


def stage_generated_export_candidate(
    source_root: Path,
    candidate_root: Path,
    *,
    modelo: str,
    revision: str,
    supporting_modelos: Collection[str],
    bootstrap_target: GeneratedExportBootstrapTarget | None = None,
) -> Path:
    """Stage one revision's complete non-export authority through a single boundary."""
    if bootstrap_target is not None and (bootstrap_target.modelo, bootstrap_target.revision) != (modelo, revision):
        raise ValueError(
            f"bootstrap target {bootstrap_target.modelo}/{bootstrap_target.revision} cannot stage {modelo}/{revision}",
        )
    shutil.copytree(source_root / "legal", candidate_root / "legal")
    stage_supplementary_orden_authority(
        source_root,
        candidate_root,
        modelos={modelo, *supporting_modelos},
    )
    source_modelo_root = source_root / "modelos" / modelo
    staged_modelo_root = candidate_root / "modelos" / modelo
    shutil.copytree(
        source_modelo_root,
        staged_modelo_root,
        ignore=ignore_export_authority_directories,
    )
    for sibling in (staged_modelo_root / "revisions").iterdir():
        if sibling.name != revision:
            shutil.rmtree(sibling)
    if bootstrap_target is not None and bootstrap_target.supersedes_layout_id is not None:
        retarget_bootstrap_construct_export_layout(
            staged_modelo_root,
            revision=revision,
            superseded_layout_id=bootstrap_target.supersedes_layout_id,
            generated_layout_id=bootstrap_target.layout_id,
            expected_references=bootstrap_target.superseded_construct_references,
        )
    for supporting_modelo in supporting_modelos:
        shutil.copytree(
            source_root / "modelos" / supporting_modelo,
            candidate_root / "modelos" / supporting_modelo,
        )
    return staged_modelo_root


def retarget_bootstrap_construct_export_layout(
    staged_modelo_root: Path,
    *,
    revision: str,
    superseded_layout_id: str,
    generated_layout_id: str,
    expected_references: int,
) -> None:
    """Retarget the explicitly pinned construct members in an isolated candidate."""
    replacements = 0
    updates: list[tuple[Path, dict[str, object]]] = []
    construct_root = staged_modelo_root / "revisions" / revision / "constructs"
    for path in sorted(construct_root.glob("*.toml")):
        payload = rtoml.load(path)
        revision_payload = payload.get("revisions", {}).get(revision, {})
        constructs = revision_payload.get("constructs", [])
        changed = False
        for construct in constructs:
            layout_ids = construct.get("export_layouts", [])
            occurrences = layout_ids.count(superseded_layout_id)
            if occurrences:
                construct["export_layouts"] = [
                    generated_layout_id if layout_id == superseded_layout_id else layout_id for layout_id in layout_ids
                ]
                replacements += occurrences
                changed = True
        if changed:
            updates.append((path, payload))
    if replacements != expected_references:
        raise ValueError(
            f"bootstrap superseded layout {superseded_layout_id!r} expected {expected_references} "
            f"construct reference(s), found {replacements}",
        )
    for path, payload in updates:
        path.write_text(rtoml.dumps(payload, pretty=True), encoding="utf-8", newline="")
