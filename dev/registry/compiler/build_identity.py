"""Portable identities of the code and dependencies that produce an authority.

Two identities live here and neither substitutes for the other. The compiler
closure is observed after a complete publishing compile: the source files of
every loaded ``cadrumo`` and ``dev/registry`` module, which is exactly the code
that produced the artifact, and it is recorded in that artifact. The source-tree
digest is a pre-compile key for development caches, which must be derived
before anything is loaded; it hashes whole trees, so it over-invalidates and is
never recorded in an artifact.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Mapping
from functools import cache
from importlib.metadata import version
from pathlib import Path
from sys import version_info
from typing import Final

import cadrumo
from cadrumo.core.hashing import content_hash_hex, sha256_hex
from cadrumo.domain.calculations.registry.authority_compiler_closure import (
    AuthorityCompilerClosure,
    AuthorityCompilerEnvironment,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

__all__ = [
    "bundled_compiler_source_roots",
    "compiler_source_tree_digest",
    "live_compiler_closure",
    "live_compiler_environment",
    "observe_compiler_closure",
]

_DEVELOPMENT_ROOT: Final = Path(__file__).resolve().parents[1]
_REPOSITORY_ROOT: Final = _DEVELOPMENT_ROOT.parents[1]
_EXCLUDED_SEGMENTS: Final = frozenset({"tests", "__pycache__"})


def bundled_compiler_source_roots() -> dict[str, Path]:
    """Map each portable closure prefix to the directory it names in this checkout."""
    return {"cadrumo": Path(cadrumo.__file__).resolve().parent, "dev/registry": _DEVELOPMENT_ROOT}


def observe_compiler_closure(
    *,
    modules: Iterable[object] | None = None,
    roots: Mapping[str, Path] | None = None,
) -> AuthorityCompilerClosure:
    """Record the source files of the loaded compiler modules and the live environment.

    ``modules`` defaults to everything this process has imported and ``roots``
    to this checkout's package and ``dev/registry`` directories. A module whose
    file lies outside every root, or under a ``tests`` or ``__pycache__``
    segment, is not compiler code.
    """
    anchors = _resolved_roots(roots)
    loaded = tuple(sys.modules.values()) if modules is None else tuple(modules)
    sources: dict[str, str] = {}
    for module in loaded:
        location = getattr(module, "__file__", None)
        if not isinstance(location, str):
            continue
        path = Path(location).resolve()
        portable = _portable_path(path, anchors)
        if portable is not None:
            sources[portable] = _source_digest(path)
    if not sources:
        raise RegistryValidationError("no loaded module lies inside the authority compiler source roots")
    return AuthorityCompilerClosure(tuple(sorted(sources.items())), live_compiler_environment())


def live_compiler_closure(
    recorded: AuthorityCompilerClosure,
    *,
    roots: Mapping[str, Path] | None = None,
) -> AuthorityCompilerClosure:
    """Re-hash exactly the recorded closure paths as they stand in this checkout.

    A recorded file that is missing or unreadable is left out, so its absence
    changes the closure identity instead of passing unnoticed. A module can
    only join the closure through an import added to a file already in it, so
    re-hashing the recorded paths observes every change that could alter what
    the compiler loads.
    """
    anchors = _resolved_roots(roots)
    sources: list[tuple[str, str]] = []
    for portable, _recorded_digest in recorded.sources:
        path = _live_path(portable, anchors)
        if path is None:
            continue
        try:
            sources.append((portable, _source_digest(path)))
        except OSError:
            continue
    return AuthorityCompilerClosure(tuple(sources), live_compiler_environment())


def live_compiler_environment() -> AuthorityCompilerEnvironment:
    """Return the interpreter, dependency manifests and validation library versions in use."""
    return AuthorityCompilerEnvironment(
        python=f"{version_info.major}.{version_info.minor}",
        pyproject_sha256=_source_digest(_REPOSITORY_ROOT / "pyproject.toml"),
        uv_lock_sha256=_source_digest(_REPOSITORY_ROOT / "uv.lock"),
        pydantic=version("pydantic"),
        pydantic_core=version("pydantic-core"),
    )


@cache
def compiler_source_tree_digest() -> str:
    """Hash every non-test compiler, domain and application source as a development cache key.

    Computed once per process: the code it hashes is the code this process
    already imported, so it cannot change underneath a running compile.
    """
    package = Path(cadrumo.__file__).resolve().parent
    roots = {
        "core": package / "core",
        "domain": package / "domain",
        "application": package / "application",
        "compiler": _DEVELOPMENT_ROOT / "compiler",
        "publication": _DEVELOPMENT_ROOT / "pipeline",
    }
    sources = [
        (f"{name}/{path.relative_to(root).as_posix()}", _source_digest(path))
        for name, root in roots.items()
        for path in root.rglob("*.py")
        if not _EXCLUDED_SEGMENTS.intersection(path.relative_to(root).parts)
    ]
    environment = live_compiler_environment()
    return content_hash_hex(
        {
            "schema": "authority-compiler-source-tree/v1",
            "sources": sorted(sources),
            "python": environment.python,
            "dependency_manifests": {
                "pyproject.toml": environment.pyproject_sha256,
                "uv.lock": environment.uv_lock_sha256,
            },
            "dependencies": {"pydantic": environment.pydantic, "pydantic-core": environment.pydantic_core},
        }
    )


def _resolved_roots(roots: Mapping[str, Path] | None) -> dict[str, Path]:
    return {prefix: root.resolve() for prefix, root in (roots or bundled_compiler_source_roots()).items()}


def _portable_path(path: Path, anchors: Mapping[str, Path]) -> str | None:
    for prefix, root in anchors.items():
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if _EXCLUDED_SEGMENTS.intersection(relative.parts):
            return None
        return f"{prefix}/{relative.as_posix()}"
    return None


def _live_path(portable: str, anchors: Mapping[str, Path]) -> Path | None:
    for prefix, root in anchors.items():
        if portable.startswith(f"{prefix}/"):
            return root.joinpath(*portable.removeprefix(f"{prefix}/").split("/"))
    return None


def _source_digest(path: Path) -> str:
    return sha256_hex(path.read_bytes().replace(b"\r\n", b"\n"))
