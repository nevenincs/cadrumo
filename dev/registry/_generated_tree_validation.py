"""Fail-closed validation for one un-published generated export revision.

This development-only boundary never locates an existing export tree, accepts a
single-file modelo, or publishes a candidate.  Its sole purpose is to prove
that the fresh isolated tree selected by the generator can survive both the
real directory loader and the validated registry authority before S11 is
allowed to publish it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

from cadrumo.domain.calculations.registry import (
    ExportLayoutDefinition,
    RegistrySnapshot,
    RegistryValidationError,
    ValidatedRegistryAuthority,
)
from cadrumo.domain.calculations.registry._loader import load_modelo_directory

from ._export_tree import RenderedExportTree
from ._provenance_manifest import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    ExportFragmentProvenanceManifest,
    ExportFragmentTarget,
    verify_export_fragment_provenance_manifest,
)
from ._semantic_map import SemanticMap
from ._semantic_map_join import JoinedRecordDesign

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

    def __post_init__(self) -> None:
        if not self.period.strip():
            raise RegistryValidationError("generated-tree validation requires a non-empty filing period")


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
    )

    authority = ValidatedRegistryAuthority.load(registry_root, source_root=source_root)
    snapshot = authority.snapshot(
        modelo_id,
        filing_year=context.filing_year,
        period=context.period,
        on=context.on,
        revision_id=revision_id,
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


def _require_isolated_target_context(
    registry_root: Path,
    *,
    modelo_id: str,
    revision_id: str,
) -> tuple[Path, Path, Path]:
    modelos_root = _require_directory(registry_root / "modelos", subject="generated registry modelos root")
    modelo_root = modelos_root / modelo_id
    _require_exact_children(
        modelos_root,
        expected={modelo_id},
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
    for name in ("revision.toml", "export", EXPORT_FRAGMENT_PROVENANCE_FILENAME):
        _require_existing_non_link(revision_root / name, subject=f"generated target revision member {name!r}")
    export_root = _require_directory(revision_root / "export", subject="generated export directory")
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
    if actual_files != expected_files or actual_directories != expected_directories:
        raise RegistryValidationError(
            "generated export directory must contain exactly the current rendered outputs; "
            f"expected_files={sorted(path.as_posix() for path in expected_files)!r}, "
            f"actual_files={sorted(path.as_posix() for path in actual_files)!r}, "
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
    _require_existing_non_link(path, subject=subject)
    if not path.is_dir():
        raise RegistryValidationError(f"{subject} is not a directory: {path}")
    return path.resolve()


def _require_existing_non_link(path: Path, *, subject: str) -> None:
    if path.is_symlink() or path.is_junction():
        raise RegistryValidationError(f"{subject} must not be a link: {path}")
    if not path.exists():
        raise RegistryValidationError(f"{subject} is missing: {path}")


def _children_without_links(directory: Path, *, subject: str) -> tuple[Path, ...]:
    children = tuple(sorted(directory.iterdir(), key=lambda path: path.name))
    for child in children:
        if child.is_symlink() or child.is_junction():
            raise RegistryValidationError(f"{subject} contains a linked member: {child}")
    return children
