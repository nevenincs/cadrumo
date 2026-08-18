"""Read-only reproducibility proof for one published generated export tree.

The checker renders from the supplied current generation authorities into an
empty, isolated candidate registry.  It then proves that candidate through the
real S10 loader boundary before comparing it byte-for-byte and semantically to
the published target.  The published target is observed only: this module has
no publication, recovery, migration, or repair operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cadrumo.core import iter_directory
from cadrumo.domain.calculations.registry import (
    ExportLayoutDefinition,
    RegistryError,
    RegistryValidationError,
    load_modelo_directory,
)

from ._export_tree import ExportTreeTransportProfile, render_complete_export_tree
from ._provenance_manifest import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    ExportFragmentProvenanceManifest,
    ExportFragmentTarget,
    normalised_loader_semantics,
    verify_export_fragment_provenance_manifest,
)
from ._render_profile import RenderProfile, RenderProfileSourceEvidence
from ._semantic_map import SemanticMap
from ._semantic_map_join import JoinedRecordDesign
from ._tree_validation import (
    GeneratedExportTreeValidationContext,
    ValidatedGeneratedExportTree,
    validate_generated_export_tree,
)

__all__ = [
    "CheckedGeneratedExportTree",
    "GeneratedExportTreeCheckContext",
    "check_generated_export_tree",
]


@dataclass(frozen=True, slots=True)
class GeneratedExportTreeCheckContext:
    """Explicit roots for an isolated candidate and a published target.

    ``validation.registry_root`` must already contain the target's authored
    non-export registry authority beneath ``temporary_root``.  It must not
    contain an ``export/`` directory: check mode always creates that candidate
    afresh and leaves target material untouched.
    """

    validation: GeneratedExportTreeValidationContext
    temporary_root: Path
    target_registry_root: Path
    target_export_root: Path
    published_modelo_root: Path | None = None
    """Caller-staged published modelo with sibling revisions pruned.

    Optional. Absent, the published layout load derives the modelo root from
    the published export path inside ``target_registry_root``, which requires
    the published modelo to hold exactly the target revision. A multi-revision
    modelo therefore stages this copy -- check mode itself copies and removes
    nothing.
    """


@dataclass(frozen=True, slots=True)
class CheckedGeneratedExportTree:
    """The independently validated candidate and the matching target evidence."""

    candidate: ValidatedGeneratedExportTree
    published_layout: ExportLayoutDefinition
    published_manifest: ExportFragmentProvenanceManifest


def check_generated_export_tree(
    *,
    context: GeneratedExportTreeCheckContext,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> CheckedGeneratedExportTree:
    """Regenerate and compare one target without writing, repairing, or publishing it.

    The candidate is rendered only into the caller's isolated temporary
    registry.  S10 validates it through the real loader and registry authority.
    The published export must independently attest to the same current
    authorities, have identical normalized loader semantics, and have the
    exact same regular members and bytes as the fresh candidate.
    """
    candidate_export_root, published_export_root = _prepare_check_roots(context)
    rendered = render_complete_export_tree(
        candidate_export_root,
        revision_id=context.validation.target.revision_id,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=transport_profile,
        render_profile=render_profile,
        render_profile_source_evidence=render_profile_source_evidence,
    )
    candidate = validate_generated_export_tree(
        context=context.validation,
        joined=joined,
        semantic_map=semantic_map,
        rendered=rendered,
        render_profile=render_profile,
        render_profile_source_evidence=render_profile_source_evidence,
    )
    if context.published_modelo_root is None:
        published_modelo_root = _published_modelo_root_from_export_root(
            published_export_root,
            target=context.validation.target,
            target_registry_root=context.target_registry_root,
        )
    else:
        # A multi-revision modelo publishes several revisions, so its published
        # layout load must see exactly the target. The CALLER stages the
        # published modelo with siblings pruned into its own temporary root;
        # check mode itself copies and removes nothing.
        published_modelo_root = _require_descendant_directory(
            context.published_modelo_root,
            root=context.temporary_root,
            subject="generated check staged published modelo root",
        )
    published_layout = _load_exact_published_layout(
        published_modelo_root,
        target=context.validation.target,
    )
    published_manifest = verify_export_fragment_provenance_manifest(
        export_root=published_export_root,
        joined=joined,
        semantic_map=semantic_map,
        target=context.validation.target,
        loaded_layout=published_layout,
        field_derivations=rendered.field_derivations,
        render_profile=render_profile,
        render_profile_source_evidence=render_profile_source_evidence,
    )
    if normalised_loader_semantics(published_layout) != normalised_loader_semantics(candidate.layout):
        raise RegistryValidationError("published export loader semantics do not match fresh generated semantics")
    _require_exact_tree_bytes(
        published_export_root,
        candidate_export_root,
    )
    return CheckedGeneratedExportTree(
        candidate=candidate,
        published_layout=published_layout,
        published_manifest=published_manifest,
    )


def _prepare_check_roots(context: GeneratedExportTreeCheckContext) -> tuple[Path, Path, Path]:
    temporary_root = _require_narrow_root(context.temporary_root, subject="generated check temporary root")
    candidate_registry_root = _require_descendant_directory(
        context.validation.registry_root,
        root=temporary_root,
        subject="generated check candidate registry root",
    )
    target_registry_root = _require_narrow_root(
        context.target_registry_root,
        subject="generated check target registry root",
    )
    if _contains(temporary_root, target_registry_root) or _contains(target_registry_root, temporary_root):
        raise RegistryValidationError("generated check temporary and target registry roots must be disjoint")

    modelo_id = str(context.validation.target.modelo)
    revision_id = str(context.validation.target.revision_id)
    candidate_export_root = candidate_registry_root / "modelos" / modelo_id / "revisions" / revision_id / "export"
    _require_existing_link_free_descendant(
        candidate_export_root.parent,
        root=candidate_registry_root,
        subject="generated check candidate revision root",
    )
    if candidate_export_root.exists() or candidate_export_root.is_symlink() or candidate_export_root.is_junction():
        raise RegistryValidationError(
            f"generated check candidate export must be absent before fresh rendering: {candidate_export_root}",
        )
    _require_no_obsolete_sibling_manifest(candidate_export_root.parent, subject="generated check candidate revision")

    expected_published_export_root = target_registry_root / "modelos" / modelo_id / "revisions" / revision_id / "export"
    _require_existing_link_free_descendant(
        expected_published_export_root,
        root=target_registry_root,
        subject="generated check published export root",
    )
    published_export_root = _require_descendant_directory(
        context.target_export_root,
        root=target_registry_root,
        subject="generated check published export root",
    )
    if published_export_root != expected_published_export_root:
        raise RegistryValidationError(
            f"generated check published export root must be {expected_published_export_root}, "
            f"got {published_export_root}",
        )
    _require_no_obsolete_direct_paths(
        target_registry_root,
        modelo_id=modelo_id,
        revision_id=revision_id,
    )
    _require_no_obsolete_sibling_manifest(published_export_root.parent, subject="generated check published revision")
    return candidate_export_root, published_export_root


def _published_modelo_root_from_export_root(
    published_export_root: Path,
    *,
    target: ExportFragmentTarget,
    target_registry_root: Path,
) -> Path:
    """Derive and identity-check the published modelo root for the target."""
    modelo_id = str(target.modelo)
    modelo_root = published_export_root.parent.parent.parent
    expected_modelo_root = target_registry_root.resolve() / "modelos" / modelo_id
    if modelo_root != expected_modelo_root:
        raise RegistryValidationError(
            f"generated check published modelo root must be {expected_modelo_root}, got {modelo_root}",
        )
    return modelo_root


def _load_exact_published_layout(
    published_modelo_root: Path,
    *,
    target: ExportFragmentTarget,
) -> ExportLayoutDefinition:
    """Load exactly one target layout from a published single-revision staging."""
    modelo_id = str(target.modelo)
    revision_id = str(target.revision_id)
    try:
        definition = load_modelo_directory(published_modelo_root)
    except RegistryError as exc:
        raise RegistryValidationError(
            f"generated check published export cannot load through the directory authority: {published_modelo_root}",
        ) from exc
    if str(definition.id) != modelo_id:
        raise RegistryValidationError(
            f"generated check published modelo loads {definition.id!r}, expected {modelo_id!r}",
        )
    if tuple(definition.revisions) != (revision_id,):
        raise RegistryValidationError(
            f"generated check published modelo must load exactly revision {revision_id!r}, "
            f"got {tuple(definition.revisions)!r}",
        )
    layouts = definition.revisions[revision_id].export_layouts
    if len(layouts) != 1:
        raise RegistryValidationError("generated check published revision must have exactly one export layout")
    return layouts[0]


def _require_exact_tree_bytes(published_root: Path, candidate_root: Path) -> None:
    published_members = _read_regular_tree_bytes(published_root, subject="generated check published export")
    candidate_members = _read_regular_tree_bytes(candidate_root, subject="generated check candidate export")
    if published_members != candidate_members:
        missing = sorted(candidate_members.keys() - published_members.keys())
        extra = sorted(published_members.keys() - candidate_members.keys())
        changed = sorted(
            path
            for path in candidate_members.keys() & published_members.keys()
            if candidate_members[path] != published_members[path]
        )
        raise RegistryValidationError(
            "published export does not exactly match fresh generated members and bytes; "
            f"missing={missing!r}, extra={extra!r}, changed={changed!r}",
        )


def _read_regular_tree_bytes(root: Path, *, subject: str) -> dict[str, bytes]:
    _require_existing_non_link(root, subject=subject)
    if not root.is_dir():
        raise RegistryValidationError(f"{subject} must be a directory: {root}")
    members: dict[str, bytes] = {}

    def visit(directory: Path) -> None:
        # require_root: the root is guarded above, but this recursion is not. An
        # unreadable subdirectory returning empty would drop its members from the
        # comparison silently, so the tree would compare equal on content it never
        # read. Reading nothing is a broken tree here, never an empty one.
        for child in sorted(iter_directory(directory, require_root=True), key=lambda path: path.name):
            if child.is_symlink() or child.is_junction():
                raise RegistryValidationError(f"{subject} contains a linked member: {child}")
            relative = child.relative_to(root).as_posix()
            if child.is_dir():
                visit(child)
            elif child.is_file():
                members[relative] = child.read_bytes()
            else:
                raise RegistryValidationError(f"{subject} contains a non-regular member: {child}")

    visit(root)
    if not members:
        raise RegistryValidationError(f"{subject} must not be empty: {root}")
    if EXPORT_FRAGMENT_PROVENANCE_FILENAME not in members:
        raise RegistryValidationError(f"{subject} lacks internal provenance manifest")
    return members


def _require_narrow_root(path: Path, *, subject: str) -> Path:
    _require_existing_non_link(path, subject=subject)
    if not path.is_dir():
        raise RegistryValidationError(f"{subject} must be a directory: {path}")
    resolved = path.resolve()
    workspace_root = Path.cwd().resolve()
    if resolved == resolved.parent or resolved == workspace_root or _contains(resolved, workspace_root):
        raise RegistryValidationError(f"{subject} is too broad: {path}")
    if (resolved / ".git").exists():
        raise RegistryValidationError(f"{subject} must not be a workspace root: {path}")
    return resolved


def _require_descendant_directory(path: Path, *, root: Path, subject: str) -> Path:
    _require_existing_non_link(path, subject=subject)
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise RegistryValidationError(f"{subject} must resolve within its explicit root: {path}") from exc
    if not relative.parts:
        raise RegistryValidationError(f"{subject} must be a strict descendant of its explicit root: {path}")
    if not resolved.is_dir():
        raise RegistryValidationError(f"{subject} must be a directory: {path}")
    return resolved


def _require_existing_link_free_descendant(path: Path, *, root: Path, subject: str) -> None:
    """Reject every link in one pre-existing explicit-root path before I/O."""
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise RegistryValidationError(f"{subject} must be within its explicit root: {path}") from exc
    if not relative.parts:
        raise RegistryValidationError(f"{subject} must be a strict descendant of its explicit root: {path}")
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        _require_existing_non_link(cursor, subject=subject)


def _require_existing_non_link(path: Path, *, subject: str) -> None:
    if path.is_symlink() or path.is_junction():
        raise RegistryValidationError(f"{subject} must not be a link: {path}")
    if not path.exists():
        raise RegistryValidationError(f"{subject} is missing: {path}")


def _require_no_obsolete_sibling_manifest(revision_root: Path, *, subject: str) -> None:
    obsolete = revision_root / "export.provenance.json"
    if obsolete.exists() or obsolete.is_symlink() or obsolete.is_junction():
        raise RegistryValidationError(f"{subject} refuses obsolete sibling provenance manifest: {obsolete}")


def _require_no_obsolete_direct_paths(
    target_registry_root: Path,
    *,
    modelo_id: str,
    revision_id: str,
) -> None:
    direct_modelo = target_registry_root / "modelos" / f"{modelo_id}.toml"
    direct_revision = target_registry_root / "modelos" / modelo_id / "revisions" / f"{revision_id}.toml"
    for path in (direct_modelo, direct_revision):
        if path.exists() or path.is_symlink() or path.is_junction():
            raise RegistryValidationError(f"generated check refuses obsolete direct registry path: {path}")


def _contains(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True
