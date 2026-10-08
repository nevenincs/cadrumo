"""Admit bounded registry paths and verify publication target state."""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from .bootstrap_supersession import validate_bootstrap_manual_export_layout_supersession
from .export_fragment_provenance import (
    LEGACY_EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    collect_export_fragment_output_digests,
)
from .tree_paths import contains
from .tree_publication_artifacts import _require_complete_regular_tree
from .tree_publication_contracts import (
    GeneratedExportTreePublicationContext,
    GeneratedExportTreeTargetStateReceipt,
    export_provenance_file_sha256,
)


def _prepare_candidate_publication_path(context: GeneratedExportTreePublicationContext) -> Path:
    """Admit only caller-owned candidate state before destination lock acquisition."""
    temporary_root = _require_narrow_root(context.temporary_root, subject="generated temporary root")
    target_root = _require_narrow_root(context.target_root, subject="generated publication target root")
    _require_disjoint_roots(temporary_root, target_root)
    origin_root = context.validation.source_chain_registry_root
    if origin_root is not None and origin_root.resolve() != target_root:
        raise RegistryValidationError("generated source-chain origin differs from the publication root")
    candidate_registry_root = _require_descendant_directory(
        context.validation.registry_root,
        root=temporary_root,
        subject="generated candidate registry root",
    )
    modelo_id = str(context.validation.target.modelo)
    revision_id = str(context.validation.target.revision_id)
    candidate_export_root = _require_descendant_directory(
        candidate_registry_root / "modelos" / modelo_id / "revisions" / revision_id / "export",
        root=temporary_root,
        subject="generated candidate export root",
    )
    _require_no_stale_sibling_manifest(candidate_export_root.parent, subject="generated candidate revision")
    _require_complete_regular_tree(candidate_export_root, subject="generated candidate export root")
    return candidate_export_root


def _admit_target_publication_path(context: GeneratedExportTreePublicationContext) -> Path:
    """Admit destination-owned state while holding its publication lock."""
    target_root = _require_narrow_root(context.target_root, subject="generated publication target root")
    modelo_id = str(context.validation.target.modelo)
    revision_id = str(context.validation.target.revision_id)
    target_export_root = _require_target_export_root(
        context.target_export_root,
        target_root=target_root,
        modelo_id=modelo_id,
        revision_id=revision_id,
    )
    _require_no_stale_sibling_manifest(target_export_root.parent, subject="generated target revision")
    if target_export_root.exists():
        _require_complete_regular_tree(target_export_root, subject="generated target export root")
    return target_export_root


def require_expected_target_state(context: GeneratedExportTreePublicationContext, target_export_root: Path) -> None:
    """Refuse a target that changed after the read-only preflight and before lock entry."""
    expected = context.expected_target_state
    if expected is None:
        if context.supersession is not None:
            raise RegistryValidationError("generated export supersession requires a check-time target receipt")
        return
    _require_target_export_receipt(target_export_root, expected)
    _require_supersession_source_receipt(context, target_export_root, expected)


def _require_target_export_receipt(
    target_export_root: Path,
    expected: GeneratedExportTreeTargetStateReceipt,
) -> None:
    if expected.manifest_sha256 is None:
        if target_export_root.exists():
            raise RegistryValidationError("generated export target appeared after check and before publication lock")
    elif (
        not target_export_root.exists()
        or export_provenance_file_sha256(target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME)
        != expected.manifest_sha256
        or collect_export_fragment_output_digests(target_export_root) != expected.output_files
    ):
        raise RegistryValidationError("generated export target changed after check and before publication lock")


def _require_supersession_source_receipt(
    context: GeneratedExportTreePublicationContext,
    target_export_root: Path,
    expected: GeneratedExportTreeTargetStateReceipt,
) -> None:
    supersession = context.supersession
    if supersession is None:
        if expected.supersession_source_sha256 is not None:
            raise RegistryValidationError("generated export target supersession pin changed after check")
        return
    if expected.supersession_source_sha256 != supersession.source_state_sha256:
        raise RegistryValidationError("generated export target supersession pin changed after check")
    try:
        observed_supersession_sha256 = validate_bootstrap_manual_export_layout_supersession(
            target_export_root.parent.parent.parent,
            revision=str(context.validation.target.revision_id),
            superseded_layout_id=supersession.superseded_layout_id,
            expected_references=supersession.expected_construct_references,
            source_ref=supersession.source_ref,
            source_sha256=supersession.source_sha256,
            manual_source_sha256=supersession.manual_source_sha256,
            manual_origin_revision=supersession.manual_origin_revision,
        )
    except (OSError, ValueError) as exc:
        raise RegistryValidationError(f"generated export supersession source changed after check: {exc}") from exc
    if observed_supersession_sha256 != supersession.source_state_sha256:
        raise RegistryValidationError("generated export supersession source changed after check")


def _require_narrow_root(path: Path, *, subject: str) -> Path:
    if is_link_like(path) or not path.is_dir():
        raise RegistryValidationError(f"{subject} must be an existing non-linked directory: {path}")
    resolved = path.resolve()
    workspace_root = Path.cwd().resolve()
    if resolved == resolved.parent or resolved == workspace_root or contains(resolved, workspace_root):
        raise RegistryValidationError(f"{subject} is too broad for generated publication: {path}")
    if (resolved / ".git").exists():
        raise RegistryValidationError(f"{subject} must not be a workspace root: {path}")
    return resolved


def _require_disjoint_roots(temporary_root: Path, target_root: Path) -> None:
    if contains(temporary_root, target_root) or contains(target_root, temporary_root):
        raise RegistryValidationError("generated temporary and publication target roots must be disjoint")


def _require_descendant_directory(path: Path, *, root: Path, subject: str) -> Path:
    resolved = _require_descendant(path, root=root, subject=subject)
    _require_existing_link_free_path(resolved, root=root, subject=subject)
    if not resolved.is_dir():
        raise RegistryValidationError(f"{subject} must be a directory: {path}")
    return resolved


def _require_target_export_root(
    path: Path,
    *,
    target_root: Path,
    modelo_id: str,
    revision_id: str,
) -> Path:
    resolved = _require_descendant(path, root=target_root, subject="generated target export root")
    expected = target_root / "modelos" / modelo_id / "revisions" / revision_id / "export"
    if resolved != expected:
        raise RegistryValidationError(
            f"generated target export root must be {expected}, got {resolved}",
        )
    _require_existing_link_free_path(resolved.parent, root=target_root, subject="generated target revision root")
    if not resolved.parent.is_dir():
        raise RegistryValidationError(f"generated target revision root must be a directory: {resolved.parent}")
    if resolved.exists() and (is_link_like(resolved) or not resolved.is_dir()):
        raise RegistryValidationError(f"generated target export root must be a non-linked directory: {resolved}")
    return resolved


def _require_descendant(path: Path, *, root: Path, subject: str) -> Path:
    if is_link_like(path):
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
    cursor = root
    for part in path.relative_to(root).parts:
        cursor = cursor / part
        if not cursor.exists():
            raise RegistryValidationError(f"{subject} is missing: {cursor}")
        if is_link_like(cursor):
            raise RegistryValidationError(f"{subject} contains a symbolic link or junction: {cursor}")


def _require_no_stale_sibling_manifest(revision_root: Path, *, subject: str) -> None:
    stale = revision_root / LEGACY_EXPORT_FRAGMENT_PROVENANCE_FILENAME
    if stale.exists() or is_link_like(stale):
        raise RegistryValidationError(f"{subject} refuses stale sibling provenance manifest: {stale}")
