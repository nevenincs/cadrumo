"""Safe paths and registry loading for staged edition delta work."""

from __future__ import annotations

from pathlib import Path

from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from dev._paths import REPO_ROOT
from dev.registry.compiler.loader import load_modelo_directory

from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_fields as _edition_delta_fields


def _load(registry_root: Path, modelo_id: str) -> ModeloDefinition:
    """Load the modelo being migrated without validating unrelated registry state.

    ``load_modelo_directory`` performs the canonical typed load, including
    predecessor materialisation and the modelo-local structural checks.  The
    migration's round-trip gate subsequently validates the staged authority
    when an export scenario needs filing behaviour.  Compiling the complete
    registry here made an unrelated governed-fact error prevent the tool from
    planning any modelo at all.
    """
    return load_modelo_directory(registry_root / _edition_delta_fields._MODELOS / modelo_id)


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def _resolve_work_directory(registry_root: Path, work_dir: Path) -> tuple[Path, Path]:
    """Resolve and validate source and scratch roots before any tree read or write.

    Migration scratch is deliberately kept away from both the registry it is
    about to copy and the repository's production ``src`` tree. Resolving
    first also closes symlink and ``..`` spellings of those forbidden
    locations. The directory must not exist: the migration owns its complete
    contents and cannot safely merge into a caller's existing tree.
    """
    resolved_registry_root = registry_root.resolve()
    resolved_work_dir = work_dir.resolve()
    production_src_root = (REPO_ROOT / "src").resolve()
    if _inside(resolved_work_dir, resolved_registry_root):
        raise _edition_delta_errors.MigrationRefusedError(
            f"work directory {resolved_work_dir} is inside registry root {resolved_registry_root}; "
            "choose a separate scratch directory",
        )
    if _inside(resolved_work_dir, production_src_root):
        raise _edition_delta_errors.MigrationRefusedError(
            f"work directory {resolved_work_dir} is inside production source tree {production_src_root}; "
            "choose a separate scratch directory",
        )
    if resolved_work_dir.exists() or work_dir.is_symlink():
        raise _edition_delta_errors.MigrationRefusedError(f"work directory {resolved_work_dir} already exists")
    return resolved_registry_root, resolved_work_dir


def _scratch_path(work_dir: Path, *parts: str) -> Path:
    """Return a scratch child and refuse path components that escape ``work_dir``."""
    candidate = work_dir.joinpath(*parts).resolve()
    if not _inside(candidate, work_dir):
        raise _edition_delta_errors.MigrationRefusedError(f"scratch path {candidate} escapes work directory {work_dir}")
    return candidate
