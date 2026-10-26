"""Publish assembly candidates while reusing only immutable, verified old members."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from .hashing import digest
from .platforms.posix import native_image


class AssemblyReuse:
    """Reuse bytes from the previous package, never writable producer inputs."""

    def __init__(self, previous: Path, candidate: Path, manifest_name: str, *, rewrite_native: bool = True) -> None:
        """Load the prior package receipt without changing any installed files."""
        self.previous = previous
        self.candidate = candidate
        self.rewrite_native = rewrite_native
        self.manifest: dict[str, Any] = {}
        manifest = previous / manifest_name
        if previous.is_symlink() or previous.is_junction():
            raise ValueError("Assembly destination cannot be linked")
        if manifest.is_file():
            self.manifest = json.loads(manifest.read_text(encoding="utf-8"))

    def verified(self, member: str) -> Path | None:
        """Return an old file only when its complete bytes match the package receipt."""
        relative = PurePosixPath(member)
        if relative.is_absolute() or ".." in relative.parts or "\\" in member or ":" in member:
            return None
        expected = self.manifest.get("files", {}).get(member)
        path = self.previous / member
        if not isinstance(expected, str) or not path.is_file():
            return None
        if any(parent.is_symlink() or parent.is_junction() for parent in (path, *path.parents)):
            return None
        return path if digest(path) == expected else None

    def copy(self, source: str | Path, destination: str | Path) -> str:
        """Link equal immutable final bytes; isolate every file an adapter may rewrite."""
        source, destination = Path(source), Path(destination)
        member = destination.relative_to(self.candidate).as_posix()
        if destination.exists():
            # A later producer may replace a member linked by an earlier phase.
            destination.unlink()
        # Platform adapters patch these sources and rewrite every native image.
        mutable = member.endswith(("pypdfium2_raw/bindings.py", "win32com/__init__.py")) or (
            self.rewrite_native and native_image(source)
        )
        layout = self.manifest.get("layout", {}).get("paths", {})
        if "packages" in layout and "authority" in layout:
            authority_source = PurePosixPath(layout["packages"]) / "cadrumo/_data/registry/authority"
            relative = PurePosixPath(member)
            if relative.is_relative_to(authority_source):
                # Assembly moves the published registry out of site-packages.
                # Its immutable bytes live only at this final path in the old stage.
                member = (PurePosixPath(layout["authority"]) / relative.relative_to(authority_source)).as_posix()
        if not self.rewrite_native:
            # Windows moves PE modules without rewriting their contents.
            member = self.manifest.get("relocation", {}).get(member, member)
        previous = None if mutable else self.verified(member)
        if (
            previous is not None
            and source.stat().st_mode == previous.stat().st_mode
            and digest(source) == self.manifest["files"][member]
        ):
            try:
                os.link(previous, destination)
                return str(destination)
            except OSError:
                # Filesystems without hardlinks retain correct isolated copies.
                pass
        return str(shutil.copy2(source, destination))

    def link(self, previous: Path, destination: Path) -> None:
        """Reuse a verified generated output that no subsequent phase modifies."""
        try:
            os.link(previous, destination)
        except OSError:
            shutil.copy2(previous, destination)


@contextmanager
def assembly_candidate(
    destination: Path, manifest_name: str, *, rewrite_native: bool = True
) -> Generator[tuple[Path, AssemblyReuse]]:
    """Keep the previous package until the candidate has assembled successfully."""
    destination = destination.absolute()
    if destination.is_symlink() or destination.is_junction():
        raise ValueError("Assembly destination cannot be linked")
    if destination.exists() and not destination.is_dir():
        raise ValueError("Assembly destination must be a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    candidate = destination.with_name(f".{destination.name}-assembly-{uuid4().hex}")
    # Python's Windows mkdtemp creates a protected private DACL. Published
    # packages must inherit the build stage's access rules, including after rename.
    candidate.mkdir(mode=0o755)
    backup = candidate.with_name(candidate.name + "-previous")
    try:
        reuse = AssemblyReuse(destination, candidate, manifest_name, rewrite_native=rewrite_native)
        yield candidate, reuse
        if destination.exists():
            destination.rename(backup)
        try:
            candidate.rename(destination)
        except BaseException:
            if backup.exists():
                backup.rename(destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if candidate.exists():
            shutil.rmtree(candidate)
