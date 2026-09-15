"""Install a proven registry source tree without overwriting concurrent edits."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from .transformation_proof import fingerprint_source_tree


def fingerprint(directory: Path) -> dict[str, str]:
    """Identify the complete source input set, including non-TOML provenance."""
    return {item.relative_path: item.sha256 for item in fingerprint_source_tree(directory).files}


def _replace_if_unchanged(target: Path, replacement: Path | None, expected: str | None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".registry-install-", delete=False) as stream:
        pending = Path(stream.name)
    displaced: Path | None = None
    try:
        if replacement is not None:
            shutil.copy2(replacement, pending)
        if expected is not None:
            with tempfile.NamedTemporaryFile(
                dir=target.parent, prefix=".registry-install-displaced-", delete=False
            ) as stream:
                displaced = Path(stream.name)
            displaced.unlink()
            target.rename(displaced)
            if hashlib.sha256(displaced.read_bytes()).hexdigest() != expected:
                raise ValueError(f"concurrent edit captured at {displaced}")
        if replacement is not None:
            os.link(pending, target)
        elif target.exists():
            raise ValueError(f"concurrent file appeared at {target}")
    except BaseException:
        if displaced is not None and displaced.exists():
            try:
                os.link(displaced, target)
            except FileExistsError as exc:
                raise ValueError(f"concurrent target preserved at {target}; displaced bytes retained at {displaced}") from exc
            displaced.unlink()
        raise
    else:
        if displaced is not None:
            if hashlib.sha256(displaced.read_bytes()).hexdigest() != expected:
                raise ValueError(f"captured source changed during installation; retained at {displaced}")
            displaced.unlink()
    finally:
        pending.unlink(missing_ok=True)


def install_proven_tree(directory: Path, staged: Path, originals: Path, before: dict[str, str]) -> None:
    """Install exact file changes and roll back this call's writes after a late refusal."""
    after = fingerprint(staged)
    if fingerprint(directory) != before:
        raise ValueError("source changed before installation; nothing installed")
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    before_directories = {path.relative_to(directory) for path in directory.rglob("*") if path.is_dir()}
    after_directories = {path.relative_to(staged) for path in staged.rglob("*") if path.is_dir()}
    completed: list[str] = []
    try:
        for name in changed:
            target = directory / name
            actual = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
            if actual != before.get(name):
                raise ValueError(f"concurrent edit at {target}")
            completed.append(name)
            _replace_if_unchanged(target, staged / name if name in after else None, before.get(name))
        for relative in sorted(before_directories - after_directories, key=lambda path: len(path.parts), reverse=True):
            (directory / relative).rmdir()
        live_directories = {path.relative_to(directory) for path in directory.rglob("*") if path.is_dir()}
        if live_directories != after_directories:
            raise ValueError("source directory set changed during installation")
        if fingerprint(directory) != after:
            raise ValueError("source changed during installation")
    except BaseException as exc:
        conflicts: list[str] = []
        for relative in sorted(before_directories, key=lambda path: len(path.parts)):
            (directory / relative).mkdir(parents=True, exist_ok=True)
        for name in reversed(completed):
            target = directory / name
            actual = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
            if actual != after.get(name):
                conflicts.append(name)
                continue
            try:
                _replace_if_unchanged(target, originals / name if name in before else None, after.get(name))
            except (OSError, ValueError) as recovery_error:
                conflicts.append(f"{name}: {recovery_error}")
        raise ValueError(
            f"installation refused: {exc}; prior writes rolled back except concurrent edits {conflicts}; "
            f"original backup retained at {originals}"
        ) from exc


__all__ = ["fingerprint", "install_proven_tree"]
