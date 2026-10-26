"""The development cache key for compiler output.

What a compile produces depends on the compiler code and the libraries it runs
with, so development caches of compiled and validated authorities key on both;
a republication after a compiler or dependency change must compile afresh
rather than reuse an earlier result. The key is derived before anything is
loaded and hashes whole source trees and the dependency manifests, so it
over-invalidates. It is never recorded in an authority, whose identity is its
legal inputs alone.
"""

from __future__ import annotations

from functools import cache
from importlib.metadata import version
from pathlib import Path
from sys import version_info
from typing import Final

import cadrumo
from cadrumo.core.hashing import content_hash_hex, sha256_hex

__all__ = ["compiler_source_tree_digest"]

_DEVELOPMENT_ROOT: Final = Path(__file__).resolve().parents[1]
_REPOSITORY_ROOT: Final = _DEVELOPMENT_ROOT.parents[1]
_EXCLUDED_SEGMENTS: Final = frozenset({"tests", "__pycache__"})


@cache
def compiler_source_tree_digest() -> str:
    """Hash every non-test compiler, domain and application source and the dependency set.

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
    return content_hash_hex(
        {
            "schema": "authority-compiler-source-tree/v1",
            "sources": sorted(sources),
            "python": f"{version_info.major}.{version_info.minor}",
            "dependency_manifests": {
                "pyproject.toml": _source_digest(_REPOSITORY_ROOT / "pyproject.toml"),
                "uv.lock": _source_digest(_REPOSITORY_ROOT / "uv.lock"),
            },
            "dependencies": {"pydantic": version("pydantic"), "pydantic-core": version("pydantic-core")},
        }
    )


def _source_digest(path: Path) -> str:
    return sha256_hex(path.read_bytes().replace(b"\r\n", b"\n"))
