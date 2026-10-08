"""Apply a prepared AEIP plan after rechecking its source-native targets."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from pathlib import Path

from cadrumo.core.atomic_write import atomic_write_text
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from .types import AeipApplyPlan, AeipStampWrite

__all__ = ("apply_prepared_plan",)


def apply_prepared_plan(plan: AeipApplyPlan) -> tuple[int, int]:
    """Apply a ready plan after re-reading every target for concurrent edits."""
    if not plan.ready:
        raise RegistryLoadError("refusing AEIP apply because preflight has refusals: " + "; ".join(plan.refusals))
    from dev.registry.analysis.casilla_lineage_seed_writer import insert_lineage_keys

    stamp_rows = _apply_stamp_writes(plan.stamp_writes, insert_lineage_keys)
    evolution_records = _apply_evolution_writes(plan)
    return stamp_rows, evolution_records


def _apply_stamp_writes(
    stamp_writes: tuple[AeipStampWrite, ...],
    insert_lineage_keys: Callable[[str, str, Mapping[str, Mapping[str, str]]], tuple[str, set[str]]],
) -> int:
    stamp_rows = 0
    by_path: dict[Path, list[AeipStampWrite]] = defaultdict(list)
    for write in stamp_writes:
        by_path[write.path].append(write)
    for path, path_writes in sorted(by_path.items(), key=lambda item: str(item[0])):
        if path.is_symlink() or not path.is_file():
            raise RegistryLoadError(f"concurrent AEIP casilla target became missing or unsafe: {path}")
        try:
            current_text = path.read_text(encoding=UTF_8_ENCODING)
        except (OSError, UnicodeError) as error:
            raise RegistryLoadError(f"cannot re-read AEIP casilla target {path}: {error}") from error
        edits = {write.casilla_id: write.key_map for write in path_writes}
        try:
            new_text, done = insert_lineage_keys(current_text, path_writes[0].revision_id, edits)
        except ValueError as error:
            raise RegistryLoadError(f"concurrent AEIP casilla change conflicts at {path}: {error}") from error
        expected = set(edits)
        if done != expected:
            raise RegistryLoadError(
                f"concurrent AEIP casilla change moved rows at {path}: expected {sorted(expected)}, got {sorted(done)}"
            )
        if new_text != current_text:
            atomic_write_text(path, new_text, encoding=UTF_8_ENCODING)
            stamp_rows += len(done)

    return stamp_rows


def _apply_evolution_writes(plan: AeipApplyPlan) -> int:
    evolution_records = 0
    for write in plan.evolution_writes:
        path = write.path
        if path.parent.is_symlink() or path.is_symlink():
            raise RegistryLoadError(f"concurrent AEIP evolution target became symlink: {path}")
        if path.exists():
            try:
                current = path.read_text(encoding=UTF_8_ENCODING)
            except (OSError, UnicodeError) as error:
                raise RegistryLoadError(f"cannot re-read AEIP evolution target {path}: {error}") from error
            if current != write.content:
                raise RegistryLoadError(f"concurrent AEIP evolution change conflicts at {path}")
            continue
        atomic_write_text(path, write.content, encoding=UTF_8_ENCODING)
        evolution_records += 1
    return evolution_records
