"""Portable identity of the code and dependencies that produce an authority."""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from importlib.metadata import version
from pathlib import Path
from sys import version_info

import cadrumo
from cadrumo.core.hashing import content_hash_hex, sha256_hex


def authority_compiler_identity(*, source_roots: Mapping[str, Path] | None = None) -> str:
    """Hash compiler and domain semantics, excluding tests and authoring data.

    The digest over the package's own sources is computed once per process:
    the code it hashes is the code this process already imported, so it
    cannot change underneath a running compile. Explicit ``source_roots``
    are hashed afresh on every call.
    """
    if source_roots is None:
        return _bundled_compiler_identity()
    return _compiler_identity(source_roots=source_roots)


@cache
def _bundled_compiler_identity() -> str:
    return _compiler_identity(source_roots=None)


def _compiler_identity(*, source_roots: Mapping[str, Path] | None) -> str:
    package = Path(cadrumo.__file__).resolve().parent
    development = Path(__file__).resolve().parents[1]
    roots = (
        source_roots
        if source_roots is not None
        else {
            "core": package / "core",
            "domain": package / "domain",
            "application": package / "application",
            "compiler": development / "compiler",
            "publication": development / "pipeline",
        }
    )
    if not roots or any(not root.is_dir() for root in roots.values()):
        raise ValueError("authority compiler identity requires existing source directories")
    sources = [
        (f"{name}/{path.relative_to(root).as_posix()}", sha256_hex(path.read_bytes().replace(b"\r\n", b"\n")))
        for name, root in roots.items()
        for path in root.rglob("*.py")
        if not {"tests", "__pycache__"}.intersection(path.relative_to(root).parts)
    ]
    return content_hash_hex(
        {
            "schema": "authority-compiler-identity/v1",
            "sources": sorted(sources),
            "python": list(version_info[:2]),
            "dependency_manifests": {
                name: sha256_hex((development.parents[1] / name).read_bytes().replace(b"\r\n", b"\n"))
                for name in ("pyproject.toml", "uv.lock")
            }
            if source_roots is None
            else {},
            "dependencies": {name: version(name) for name in ("pydantic", "pydantic-core")},
        }
    )
