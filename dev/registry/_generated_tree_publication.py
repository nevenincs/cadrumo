"""Atomic, fail-closed publication for one validated generated revision tree.

This developer-only boundary is intentionally narrow.  The caller supplies the
isolated registry that S10 validates and an explicit revision destination; this
module never discovers an installed registry tree, reads destination content to
derive output, or merges a candidate into an older revision.  The whole revision
directory is the publication unit because its adjacent provenance manifest must
arrive with its generated ``export/`` directory.
"""

from __future__ import annotations

import os
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path

from cadrumo.domain.calculations.registry import RegistryValidationError

from ._export_tree import RenderedExportTree
from ._generated_tree_validation import (
    GeneratedExportTreeValidationContext,
    ValidatedGeneratedExportTree,
    validate_generated_export_tree,
)
from ._provenance_manifest import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ._semantic_map import SemanticMap
from ._semantic_map_join import JoinedRecordDesign

__all__ = [
    "GeneratedExportTreePublicationContext",
    "PublishedGeneratedExportTree",
    "publish_validated_generated_export_tree",
]


@dataclass(frozen=True, slots=True)
class GeneratedExportTreePublicationContext:
    """Explicit roots and S10 inputs for one revision-directory cutover."""

    validation: GeneratedExportTreeValidationContext
    temporary_root: Path
    target_root: Path
    target_revision_root: Path


@dataclass(frozen=True, slots=True)
class PublishedGeneratedExportTree:
    """The target that received the immediately-prevalidated candidate."""

    validated: ValidatedGeneratedExportTree
    revision_root: Path
    export_root: Path
    provenance_manifest_path: Path


def publish_validated_generated_export_tree(
    *,
    context: GeneratedExportTreePublicationContext,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
) -> PublishedGeneratedExportTree:
    """Validate then atomically replace one complete revision directory.

    Validation is deliberately the last non-mutating prerequisite.  Once it
    succeeds, the candidate is cut over with two directory renames: an existing
    target moves to a unique sibling rollback directory, then the candidate
    moves into the target path.  A failed second rename restores the old target.
    A successful cutover deletes the rollback directory; it is never retained as
    a runtime recovery or compatibility surface.
    """
    candidate_revision_root, target_revision_root = _prepare_publication_paths(context)

    # S10 is the immediate pre-mutation gate.  Do not move, delete, create, or
    # infer from either target before this real loader-and-authority proof ends.
    validated = validate_generated_export_tree(
        context=context.validation,
        joined=joined,
        semantic_map=semantic_map,
        rendered=rendered,
    )

    rollback_root = _rollback_sibling(target_revision_root)
    had_target = target_revision_root.exists()
    if had_target:
        _require_complete_regular_tree(target_revision_root, subject="existing publication target")

    moved_target = False
    try:
        if had_target:
            os.replace(target_revision_root, rollback_root)
            moved_target = True
        try:
            os.replace(candidate_revision_root, target_revision_root)
        except OSError as publish_error:
            _restore_target_or_raise(
                target_revision_root=target_revision_root,
                rollback_root=rollback_root,
                publish_error=publish_error,
            )
        if moved_target:
            _delete_rollback_tree(rollback_root)
    except OSError as exc:
        raise RegistryValidationError(
            f"cannot atomically publish generated revision {target_revision_root}: {exc}",
        ) from exc

    return PublishedGeneratedExportTree(
        validated=validated,
        revision_root=target_revision_root,
        export_root=target_revision_root / "export",
        provenance_manifest_path=target_revision_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    )


def _prepare_publication_paths(context: GeneratedExportTreePublicationContext) -> tuple[Path, Path]:
    temporary_root = _require_narrow_root(context.temporary_root, subject="generated temporary root")
    target_root = _require_narrow_root(context.target_root, subject="generated publication target root")
    _require_disjoint_roots(temporary_root, target_root)

    candidate_registry_root = _require_descendant_directory(
        context.validation.registry_root,
        root=temporary_root,
        subject="generated candidate registry root",
    )
    modelo_id = str(context.validation.target.modelo)
    revision_id = str(context.validation.target.revision_id)
    candidate_revision_root = _require_descendant_directory(
        candidate_registry_root / "modelos" / modelo_id / "revisions" / revision_id,
        root=temporary_root,
        subject="generated candidate revision root",
    )

    target_revision_root = _require_target_revision_root(
        context.target_revision_root,
        target_root=target_root,
        modelo_id=modelo_id,
        revision_id=revision_id,
    )
    _require_complete_regular_tree(candidate_revision_root, subject="generated candidate revision root")
    return candidate_revision_root, target_revision_root


def _require_narrow_root(path: Path, *, subject: str) -> Path:
    if path.is_symlink() or path.is_junction():
        raise RegistryValidationError(f"{subject} must not be a symbolic link or junction: {path}")
    if not path.is_dir():
        raise RegistryValidationError(f"{subject} must be an existing directory: {path}")
    resolved = path.resolve()
    if resolved == resolved.parent:
        raise RegistryValidationError(f"{subject} must not be a filesystem root: {path}")
    workspace_root = Path.cwd().resolve()
    if resolved == workspace_root or _contains(resolved, workspace_root):
        raise RegistryValidationError(f"{subject} is too broad for generated publication: {path}")
    if (resolved / ".git").exists():
        raise RegistryValidationError(f"{subject} must not be a workspace root: {path}")
    return resolved


def _require_disjoint_roots(temporary_root: Path, target_root: Path) -> None:
    if _contains(temporary_root, target_root) or _contains(target_root, temporary_root):
        raise RegistryValidationError(
            "generated temporary and publication target roots must be disjoint; overlapping roots are unsafe",
        )


def _require_descendant_directory(path: Path, *, root: Path, subject: str) -> Path:
    resolved = _require_descendant(path, root=root, subject=subject)
    _require_existing_link_free_path(resolved, root=root, subject=subject)
    if not resolved.is_dir():
        raise RegistryValidationError(f"{subject} must be a directory: {path}")
    return resolved


def _require_target_revision_root(
    path: Path,
    *,
    target_root: Path,
    modelo_id: str,
    revision_id: str,
) -> Path:
    resolved = _require_descendant(path, root=target_root, subject="generated target revision root")
    expected = target_root / "modelos" / modelo_id / "revisions" / revision_id
    if resolved != expected:
        raise RegistryValidationError(
            "generated target revision root must be the explicit target modelo/revision path; "
            f"expected {expected}, got {resolved}",
        )
    parent = resolved.parent
    _require_existing_link_free_path(parent, root=target_root, subject="generated target revision parent")
    if not parent.is_dir():
        raise RegistryValidationError(f"generated target revision parent must be a directory: {parent}")
    if resolved.exists() and (resolved.is_symlink() or resolved.is_junction() or not resolved.is_dir()):
        raise RegistryValidationError(f"generated target revision root must be a non-linked directory: {resolved}")
    return resolved


def _require_descendant(path: Path, *, root: Path, subject: str) -> Path:
    if path.is_symlink() or path.is_junction():
        raise RegistryValidationError(f"{subject} must not be a symbolic link or junction: {path}")
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise RegistryValidationError(f"{subject} must resolve within its explicit caller root: {path}") from exc
    if not relative.parts:
        raise RegistryValidationError(f"{subject} must be a strict descendant of its explicit caller root: {path}")
    return resolved


def _require_existing_link_free_path(path: Path, *, root: Path, subject: str) -> None:
    relative = path.relative_to(root)
    cursor = root
    if cursor.is_symlink() or cursor.is_junction():
        raise RegistryValidationError(f"{subject} caller root is a symbolic link or junction: {root}")
    for part in relative.parts:
        cursor = cursor / part
        if not cursor.exists():
            raise RegistryValidationError(f"{subject} is missing: {cursor}")
        if cursor.is_symlink() or cursor.is_junction():
            raise RegistryValidationError(f"{subject} contains a symbolic link or junction: {cursor}")


def _require_complete_regular_tree(path: Path, *, subject: str) -> None:
    """Reject linked, special, or empty candidates before any cutover begins."""
    if path.is_symlink() or path.is_junction() or not path.is_dir():
        raise RegistryValidationError(f"{subject} must be a non-linked directory: {path}")
    children = tuple(path.iterdir())
    if not children:
        raise RegistryValidationError(f"{subject} must not be empty: {path}")
    for child in children:
        if child.is_symlink() or child.is_junction():
            raise RegistryValidationError(f"{subject} contains a symbolic link or junction: {child}")
        if child.is_dir():
            _require_complete_regular_tree(child, subject=subject)
        elif not child.is_file():
            raise RegistryValidationError(f"{subject} contains a non-regular member: {child}")


def _rollback_sibling(target_revision_root: Path) -> Path:
    rollback = target_revision_root.with_name(
        f".{target_revision_root.name}.generator-rollback-{secrets.token_hex(16)}",
    )
    if rollback.exists() or rollback.is_symlink() or rollback.is_junction():
        raise RegistryValidationError(f"generated rollback sibling unexpectedly exists: {rollback}")
    return rollback


def _restore_target_or_raise(
    *,
    target_revision_root: Path,
    rollback_root: Path,
    publish_error: OSError,
) -> None:
    if not rollback_root.exists():
        raise RegistryValidationError(
            "generated revision publication failed before a rollback target existed: "
            f"{publish_error}",
        ) from publish_error
    try:
        os.replace(rollback_root, target_revision_root)
    except OSError as restore_error:
        raise RegistryValidationError(
            "generated revision publication failed and its previous target could not be restored; "
            f"publication_error={publish_error}; restoration_error={restore_error}",
        ) from restore_error
    raise RegistryValidationError(
        "generated revision publication failed; the previous target was restored: "
        f"{publish_error}",
    ) from publish_error


def _delete_rollback_tree(rollback_root: Path) -> None:
    _require_complete_regular_tree(rollback_root, subject="generated rollback directory")
    try:
        shutil.rmtree(rollback_root)
    except OSError as exc:
        raise RegistryValidationError(
            f"generated publication completed but cannot delete its rollback directory: {rollback_root}: {exc}",
        ) from exc
    if rollback_root.exists():
        raise RegistryValidationError(f"generated publication left rollback residue: {rollback_root}")


def _contains(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True
