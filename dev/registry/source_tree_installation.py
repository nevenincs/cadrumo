"""Install a proven registry source tree without overwriting concurrent edits."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from cadrumo.core.hashing import sha256_file

from .transformation_proof import fingerprint_source_tree


def fingerprint(directory: Path) -> dict[str, str]:
    """Identify the complete source input set, including non-TOML provenance."""
    return {item.relative_path: item.sha256 for item in fingerprint_source_tree(directory).files}


def toml_comments(text: str) -> list[str]:
    """Retain full-line and trailing comments without treating hashes in strings as comments."""
    comments: list[str] = []
    quote = ""
    index = 0
    while index < len(text):
        if quote:
            if quote.startswith('"') and text[index] == "\\":
                index += 2
                continue
            if text.startswith(quote, index):
                index += len(quote)
                quote = ""
                continue
        elif text[index] in {"'", '"'}:
            quote = text[index] * (3 if text.startswith(text[index] * 3, index) else 1)
            index += len(quote)
            continue
        elif text[index] == "#":
            end = text.find("\n", index)
            if end < 0:
                end = len(text)
            comments.append(text[index:end].rstrip("\r"))
            index = end
        index += 1
    return comments


def _pending_install_file(target: Path) -> Path:
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".registry-install-", delete=False) as stream:
        return Path(stream.name)


def _displace_target(target: Path) -> Path:
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".registry-install-displaced-", delete=False) as stream:
        displaced = Path(stream.name)
    displaced.unlink()
    target.rename(displaced)
    return displaced


def _verify_displaced_target(displaced: Path, expected: str) -> None:
    if sha256_file(displaced) != expected:
        raise ValueError(f"concurrent edit captured at {displaced}")


def _link_pending_file(target: Path, replacement: Path | None, pending: Path) -> None:
    if replacement is not None:
        os.link(pending, target)
    elif target.exists():
        raise ValueError(f"concurrent file appeared at {target}")


def _restore_displaced_target(target: Path, displaced: Path | None) -> None:
    if displaced is None or not displaced.exists():
        return
    try:
        os.link(displaced, target)
    except FileExistsError as exc:
        raise ValueError(f"concurrent target preserved at {target}; displaced bytes retained at {displaced}") from exc
    displaced.unlink()


def _finish_displaced_target(displaced: Path | None, expected: str | None) -> None:
    if displaced is None:
        return
    if sha256_file(displaced) != expected:
        raise ValueError(f"captured source changed during installation; retained at {displaced}")
    displaced.unlink()


def replace_file_if_unchanged(target: Path, replacement: Path | None, expected: str | None) -> None:
    """Replace or delete ``target`` only while it still holds the bytes hashed as ``expected``.

    ``replacement`` of ``None`` deletes the target; ``expected`` of ``None`` requires the target
    to be absent. The target is displaced before its hash is checked, so a concurrent edit is
    captured and restored in place rather than overwritten, and the call refuses with a
    ``ValueError`` naming where the concurrent bytes were preserved.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    pending = _pending_install_file(target)
    displaced: Path | None = None
    try:
        if replacement is not None:
            shutil.copy2(replacement, pending)
        if expected is not None:
            displaced = _displace_target(target)
            _verify_displaced_target(displaced, expected)
        _link_pending_file(target, replacement, pending)
    except BaseException:
        _restore_displaced_target(target, displaced)
        raise
    else:
        _finish_displaced_target(displaced, expected)
    finally:
        pending.unlink(missing_ok=True)


def _tree_directory_sets(directory: Path, staged: Path) -> tuple[set[Path], set[Path]]:
    before_directories = {path.relative_to(directory) for path in directory.rglob("*") if path.is_dir()}
    after_directories = {path.relative_to(staged) for path in staged.rglob("*") if path.is_dir()}
    return before_directories, after_directories


def _apply_changed_files(
    directory: Path,
    staged: Path,
    changed: list[str],
    before: dict[str, str],
    after: dict[str, str],
    completed: list[str],
) -> None:
    for name in changed:
        target = directory / name
        actual = sha256_file(target) if target.exists() else None
        if actual != before.get(name):
            raise ValueError(f"concurrent edit at {target}")
        completed.append(name)
        replace_file_if_unchanged(target, staged / name if name in after else None, before.get(name))


def _remove_obsolete_directories(directory: Path, before: set[Path], after: set[Path]) -> None:
    obsolete = sorted(before - after, key=lambda path: len(path.parts), reverse=True)
    for relative in obsolete:
        (directory / relative).rmdir()


def _verify_installed_tree(directory: Path, after_directories: set[Path], after: dict[str, str]) -> None:
    live_directories = {path.relative_to(directory) for path in directory.rglob("*") if path.is_dir()}
    if live_directories != after_directories:
        raise ValueError("source directory set changed during installation")
    if fingerprint(directory) != after:
        raise ValueError("source changed during installation")


def _restore_original_directories(directory: Path, before_directories: set[Path]) -> None:
    ordered = sorted(before_directories, key=lambda path: len(path.parts))
    for relative in ordered:
        (directory / relative).mkdir(parents=True, exist_ok=True)


def _rollback_completed_file(
    directory: Path,
    originals: Path,
    name: str,
    before: dict[str, str],
    after: dict[str, str],
) -> str | None:
    target = directory / name
    actual = sha256_file(target) if target.exists() else None
    if actual != after.get(name):
        return name
    try:
        replace_file_if_unchanged(target, originals / name if name in before else None, after.get(name))
    except (OSError, ValueError) as recovery_error:
        return f"{name}: {recovery_error}"
    return None


def _rollback_installed_changes(
    directory: Path,
    originals: Path,
    before: dict[str, str],
    after: dict[str, str],
    before_directories: set[Path],
    completed: list[str],
) -> list[str]:
    _restore_original_directories(directory, before_directories)
    conflicts: list[str] = []
    for name in reversed(completed):
        conflict = _rollback_completed_file(directory, originals, name, before, after)
        if conflict is not None:
            conflicts.append(conflict)
    return conflicts


def install_proven_tree(directory: Path, staged: Path, originals: Path, before: dict[str, str]) -> None:
    """Install exact file changes and roll back this call's writes after a late refusal."""
    after = fingerprint(staged)
    if fingerprint(directory) != before:
        raise ValueError("source changed before installation; nothing installed")
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    before_directories, after_directories = _tree_directory_sets(directory, staged)
    completed: list[str] = []
    try:
        _apply_changed_files(directory, staged, changed, before, after, completed)
        _remove_obsolete_directories(directory, before_directories, after_directories)
        _verify_installed_tree(directory, after_directories, after)
    except BaseException as exc:
        conflicts = _rollback_installed_changes(directory, originals, before, after, before_directories, completed)
        raise ValueError(
            f"installation refused: {exc}; prior writes rolled back except concurrent edits {conflicts}; "
            f"original backup retained at {originals}"
        ) from exc


__all__ = ["fingerprint", "install_proven_tree", "replace_file_if_unchanged", "toml_comments"]
