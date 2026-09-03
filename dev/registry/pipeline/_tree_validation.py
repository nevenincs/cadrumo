"""Fail-closed validation for one un-published generated export revision.

This development-only boundary never locates an existing export tree, accepts a
single-file modelo, or publishes a candidate.  Its sole purpose is to prove
that the fresh isolated tree selected by the generator can survive both the
real directory loader and the validated registry authority before publication
is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.loader import (
    load_modelo_directory,
    load_registry_tree,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.domain.calculations.registry.validate_registry_scope import validate_registry_scope
from cadrumo.tests.registry_snapshot import build_snapshot

from ._export_tree import RenderedExportTree
from ._provenance_manifest import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    ExportFragmentProvenanceManifest,
    ExportFragmentTarget,
    verify_export_fragment_provenance_manifest,
)
from ._render_profile import RenderProfile, RenderProfileSourceEvidence
from ._semantic_map import SemanticMap
from ._semantic_map_join import JoinedRecordDesign
from ._tree_paths import require_existing_non_link

__all__ = [
    "GeneratedExportTreeValidationContext",
    "ValidatedGeneratedExportTree",
    "validate_generated_export_tree",
]


@dataclass(frozen=True, slots=True)
class GeneratedExportTreeValidationContext:
    """The one isolated candidate registry and filing selection to validate."""

    registry_root: Path
    source_root: Path
    target: ExportFragmentTarget
    filing_year: int
    period: str
    on: date | None = None
    #: Modelos other than the target that the candidate root is allowed to hold.
    #:
    #: The target's own validation resolves its cross-modelo folds against the
    #: LOADED registry, so a candidate holding only the target refuses every
    #: revision that reads another modelo -- Modelo 353's per-member fan-in over
    #: Modelo 322 is the worked case, and it refused with "references unknown
    #: source modelo" from an isolation the caller created, not an authoring gap.
    #: Naming them keeps the isolation bounded and auditable: anything staged
    #: beyond the target and this set is still refused, and the checks that
    #: actually pin the verdict -- the target directory loading exactly one
    #: revision, and the authority selecting exactly that modelo and revision --
    #: are unchanged and unaffected by a supporting modelo being present.
    supporting_modelos: frozenset[str] = frozenset()
    #: A separately staged, non-export witness for continuity predecessors.
    #:
    #: A generated candidate intentionally contains only its target revision.
    #: Strict continuidad evolutions, however, name real predecessor revisions.
    #: This optional directory-mode modelo supplies only those predecessors'
    #: scalar revision metadata, casilla continuity surfaces, and evolution
    #: declarations.  It is never part of the candidate registry, never
    #: rendered, compared, or published, and its target revision is refused:
    #: the rendered target remains the sole source of its own facts.
    continuity_metadata_modelo_root: Path | None = None
    #: Authority grade the caller is entitled to establish.  Existing check and
    #: validation callers keep the filing-grade default; bootstrap publication
    #: explicitly asks for calculation grade because a static generated layout
    #: does not establish filing readiness.
    required_grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING

    def __post_init__(self) -> None:
        if not self.period.strip():
            raise RegistryValidationError("generated-tree validation requires a non-empty filing period")
        if str(self.target.modelo) in self.supporting_modelos:
            raise RegistryValidationError(
                "generated-tree validation must not name the target modelo as a supporting modelo",
            )


@dataclass(frozen=True, slots=True)
class ValidatedGeneratedExportTree:
    """The authority-selected result of validating one fresh generated tree."""

    target: ExportFragmentTarget
    layout: ExportLayoutDefinition
    snapshot: RegistrySnapshot
    provenance_manifest: ExportFragmentProvenanceManifest


def validate_generated_export_tree(
    *,
    context: GeneratedExportTreeValidationContext,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> ValidatedGeneratedExportTree:
    """Prove that one complete, isolated generated tree is filing-selectable.

    The input is deliberately a target-only directory-mode registry.  Reusing a
    published registry, a direct revision file, an extra modelo, or a sibling
    under ``export/`` is a refusal because each would allow the real loader to
    admit facts that the current renderer did not produce.
    """
    registry_root = _require_directory(context.registry_root, subject="generated registry root")
    source_root = _require_directory(context.source_root, subject="generation source root")
    if registry_root == source_root / "registry" / "aeat":
        raise RegistryValidationError("generated-tree validation requires an isolated un-published registry root")

    modelo_id = str(context.target.modelo)
    revision_id = str(context.target.revision_id)
    modelo_root, _revision_root, export_root = _require_isolated_target_context(
        registry_root,
        modelo_id=modelo_id,
        revision_id=revision_id,
        supporting_modelos=context.supporting_modelos,
    )
    _require_exact_generated_outputs(export_root, rendered.output_files)

    definition = load_modelo_directory(modelo_root)
    if str(definition.id) != modelo_id:
        raise RegistryValidationError(
            f"generated modelo directory loads modelo {definition.id!r}, expected {modelo_id!r}",
        )
    if tuple(definition.revisions) != (revision_id,):
        raise RegistryValidationError(
            f"isolated generated modelo must load exactly revision {revision_id!r}, "
            f"got {tuple(definition.revisions)!r}",
        )
    loaded_revision = definition.revisions[revision_id]
    loaded_layout = _require_exact_generated_layout(
        loaded_revision.export_layouts,
        rendered=rendered,
        revision_id=revision_id,
    )
    provenance = verify_export_fragment_provenance_manifest(
        export_root=export_root,
        joined=joined,
        semantic_map=semantic_map,
        target=context.target,
        loaded_layout=loaded_layout,
        field_derivations=rendered.field_derivations,
        render_profile=render_profile,
        render_profile_source_evidence=render_profile_source_evidence,
    )

    snapshot = _validated_target_snapshot(
        context=context,
        registry_root=registry_root,
        source_root=source_root,
        modelo_id=modelo_id,
        revision_id=revision_id,
        target_definition=definition,
    )
    if str(snapshot.modelo.id) != modelo_id or str(snapshot.revision.id) != revision_id:
        raise RegistryValidationError(
            f"validated authority selected modelo/revision {snapshot.modelo.id!r}/{snapshot.revision.id!r}, "
            f"expected {modelo_id!r}/{revision_id!r}",
        )
    _require_exact_generated_layout(
        snapshot.revision.export_layouts,
        rendered=rendered,
        revision_id=revision_id,
    )
    return ValidatedGeneratedExportTree(
        target=context.target,
        layout=loaded_layout,
        snapshot=snapshot,
        provenance_manifest=provenance,
    )


def _validated_target_snapshot(
    *,
    context: GeneratedExportTreeValidationContext,
    registry_root: Path,
    source_root: Path,
    modelo_id: str,
    revision_id: str,
    target_definition: ModeloDefinition,
) -> RegistrySnapshot:
    """Select the target through canonical authority, with an optional continuity witness.

    Normal candidates retain the ordinary :class:`ValidatedRegistryAuthority`
    route.  A candidate that declares an incoming strict-continuity transition
    can instead carry a separate witness for the predecessor facts that are
    intentionally absent from its target-only tree.  That witness is checked by
    the existing registry-scope validator after replacing *only* its target
    revision with the freshly loaded candidate revision; it cannot validate a
    stale target by copying one into the witness.
    """
    if context.continuity_metadata_modelo_root is None:
        authority = ValidatedRegistryAuthority.load(registry_root, source_root=source_root)
        return authority.snapshot(
            modelo_id,
            filing_year=context.filing_year,
            period=context.period,
            on=context.on,
            revision_id=revision_id,
            grade=context.required_grade,
        )

    continuity_modelo = _load_continuity_metadata_modelo(
        context.continuity_metadata_modelo_root,
        modelo_id=modelo_id,
        revision_id=revision_id,
    )
    loaded_modelos, catalogues = load_registry_tree(registry_root)
    loaded_target = next((modelo for modelo in loaded_modelos if str(modelo.id) == modelo_id), None)
    if loaded_target is None:
        raise RegistryValidationError(f"generated target modelo {modelo_id!r} is absent from the isolated registry")
    if loaded_target != target_definition:
        raise RegistryValidationError("generated target loader result changed before continuity validation")

    witness = continuity_modelo.model_copy(
        update={
            "revisions": {
                **continuity_modelo.revisions,
                revision_id: target_definition.revisions[revision_id],
            },
        },
    )
    scoped_modelos = tuple(witness if str(modelo.id) == modelo_id else modelo for modelo in loaded_modelos)
    continuity_failures = validate_registry_scope(scoped_modelos)
    if continuity_failures:
        raise RegistryValidationError(
            "registry validation failed:\n" + "\n".join(f" - {failure}" for failure in continuity_failures)
        )

    # ``build_snapshot`` owns exactly the model-local validation and requested-grade
    # selection that the production authority delegates to after its registry
    # scope has passed.  The scope above is the same existing validator, with
    # the copied predecessor facts used only to make strict continuity answerable.
    return build_snapshot(
        target_definition,
        catalogues,
        source_root=source_root,
        filing_year=context.filing_year,
        period=context.period,
        on=context.on,
        revision_id=revision_id,
        grade=context.required_grade,
    )


def _load_continuity_metadata_modelo(
    metadata_root: Path,
    *,
    modelo_id: str,
    revision_id: str,
) -> ModeloDefinition:
    """Load source-copied predecessor facts without admitting another target."""
    resolved = _require_directory(metadata_root, subject="generated continuity metadata modelo root")
    modelo = load_modelo_directory(resolved)
    if str(modelo.id) != modelo_id:
        raise RegistryValidationError(
            f"generated continuity metadata loads modelo {modelo.id!r}, expected {modelo_id!r}",
        )
    if revision_id in modelo.revisions:
        raise RegistryValidationError(
            f"generated continuity metadata must not contain target revision {revision_id!r}",
        )
    if not modelo.revisions:
        raise RegistryValidationError("generated continuity metadata declares no sibling revisions")
    return modelo


def _require_isolated_target_context(
    registry_root: Path,
    *,
    modelo_id: str,
    revision_id: str,
    supporting_modelos: frozenset[str] = frozenset(),
) -> tuple[Path, Path, Path]:
    modelos_root = _require_directory(registry_root / "modelos", subject="generated registry modelos root")
    modelo_root = modelos_root / modelo_id
    _require_exact_children(
        modelos_root,
        expected={modelo_id, *supporting_modelos},
        subject="generated registry modelos root",
    )
    _require_directory(modelo_root, subject="generated modelo directory")
    _require_exact_children(
        modelo_root,
        expected={"manifest.toml", "revisions"},
        subject="generated modelo directory",
    )

    revisions_root = _require_directory(modelo_root / "revisions", subject="generated modelo revisions directory")
    revision_root = revisions_root / revision_id
    _require_exact_children(
        revisions_root,
        expected={revision_id},
        subject="generated modelo revisions directory",
    )
    _require_directory(revision_root, subject="generated target revision directory")
    for name in ("revision.toml", "export"):
        require_existing_non_link(revision_root / name, subject=f"generated target revision member {name!r}")
    stale_sibling_manifest = revision_root / "export.provenance.json"
    if stale_sibling_manifest.exists() or is_link_like(stale_sibling_manifest):
        raise RegistryValidationError(
            f"generated target revision refuses stale sibling export provenance manifest: {stale_sibling_manifest}",
        )
    export_root = _require_directory(revision_root / "export", subject="generated export directory")
    require_existing_non_link(
        export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME,
        subject="generated export provenance manifest",
    )
    return modelo_root, revision_root, export_root


def _require_exact_children(directory: Path, *, expected: set[str], subject: str) -> None:
    actual = {child.name for child in _children_without_links(directory, subject=subject)}
    if actual != expected:
        raise RegistryValidationError(
            f"{subject} must contain exactly {sorted(expected)!r}, got {sorted(actual)!r}",
        )


def _require_exact_generated_outputs(export_root: Path, output_files: tuple[str, ...]) -> None:
    expected_files = {_normalise_output_path(path) for path in output_files}
    if not expected_files:
        raise RegistryValidationError("generated render result declares no output files")
    actual_files, actual_directories = _collect_regular_tree_members(export_root)
    expected_directories = {
        parent.as_posix() for path in expected_files for parent in path.parents if parent != PurePosixPath(".")
    }
    manifest_path = PurePosixPath(EXPORT_FRAGMENT_PROVENANCE_FILENAME)
    actual_toml_files = actual_files - {manifest_path}
    if (
        actual_toml_files != expected_files
        or manifest_path not in actual_files
        or actual_directories != expected_directories
    ):
        raise RegistryValidationError(
            "generated export directory must contain exactly the current rendered outputs; "
            f"expected_files={sorted(path.as_posix() for path in expected_files)!r}, "
            f"actual_files={sorted(path.as_posix() for path in actual_toml_files)!r}, "
            f"expected_directories={sorted(expected_directories)!r}, "
            f"actual_directories={sorted(actual_directories)!r}",
        )


def _require_exact_generated_layout(
    layouts: tuple[ExportLayoutDefinition, ...],
    *,
    rendered: RenderedExportTree,
    revision_id: str,
) -> ExportLayoutDefinition:
    if layouts != (rendered.layout,):
        raise RegistryValidationError(
            f"generated revision {revision_id!r} loader semantics do not equal the current rendered layout",
        )
    return layouts[0]


def _normalise_output_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise RegistryValidationError(f"generated render result declares unsafe output path {value!r}")
    if path.suffix != ".toml":
        raise RegistryValidationError(f"generated render result declares non-TOML output path {value!r}")
    return path


def _collect_regular_tree_members(root: Path) -> tuple[set[PurePosixPath], set[str]]:
    files: set[PurePosixPath] = set()
    directories: set[str] = set()

    def visit(directory: Path) -> None:
        for child in _children_without_links(directory, subject="generated export directory"):
            relative = PurePosixPath(*child.relative_to(root).parts)
            if child.is_dir():
                directories.add(relative.as_posix())
                visit(child)
            elif child.is_file():
                files.add(relative)
            else:
                raise RegistryValidationError(f"generated export directory contains non-regular member {child}")

    visit(root)
    return files, directories


def _require_directory(path: Path, *, subject: str) -> Path:
    require_existing_non_link(path, subject=subject)
    if not path.is_dir():
        raise RegistryValidationError(f"{subject} is not a directory: {path}")
    return path.resolve()


def _children_without_links(directory: Path, *, subject: str) -> tuple[Path, ...]:
    # require_root: an unreadable directory yielding empty would pass the
    # link check below without inspecting anything, which is the failure this
    # helper exists to prevent. ``Path.iterdir`` raised here before the move
    # onto the shared scanner; this keeps that.
    children = tuple(sorted(iter_directory(directory, require_root=True), key=lambda path: path.name))
    for child in children:
        if is_link_like(child):
            raise RegistryValidationError(f"{subject} contains a linked member: {child}")
    return children
