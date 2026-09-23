"""The source closure and environment a published authority was compiled by.

A publication records every compiler source file its process actually loaded,
each as a portable path and a line-ending-normalised content digest, together
with the interpreter and dependency environment. The compiler identity is the
content hash of that record, so a reader can recompute it from the rows it
admits and a currency check can re-hash exactly the recorded files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from ....core.hashing import content_hash_hex

__all__ = ["AuthorityCompilerClosure", "AuthorityCompilerEnvironment"]

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_PYTHON_VERSION: Final = re.compile(r"[0-9]+\.[0-9]+")
_COMPILER_IDENTITY_SCHEMA: Final = "authority-compiler-identity/v2"


@dataclass(frozen=True, slots=True)
class AuthorityCompilerEnvironment:
    """Interpreter, dependency manifests and validation library versions of one compile."""

    python: str
    pyproject_sha256: str
    uv_lock_sha256: str
    pydantic: str
    pydantic_core: str

    def __post_init__(self) -> None:
        """Refuse an environment whose members cannot identify a compiler."""
        if _PYTHON_VERSION.fullmatch(self.python) is None:
            raise ValueError("authority compiler environment python must be a major.minor version")
        if any(_SHA256.fullmatch(value) is None for value in (self.pyproject_sha256, self.uv_lock_sha256)):
            raise ValueError("authority compiler dependency manifests must be lowercase SHA-256 digests")
        if not self.pydantic.strip() or not self.pydantic_core.strip():
            raise ValueError("authority compiler dependency versions must be non-blank")


@dataclass(frozen=True, slots=True)
class AuthorityCompilerClosure:
    """Sorted ``(portable path, sha256)`` rows of the loaded compiler sources.

    Paths are POSIX spellings relative to a checkout-independent anchor, so an
    identical checkout at another absolute location records the same rows.
    """

    sources: tuple[tuple[str, str], ...]
    environment: AuthorityCompilerEnvironment

    def __post_init__(self) -> None:
        """Refuse unportable paths, malformed digests, duplicates and unsorted rows."""
        if not isinstance(self.environment, AuthorityCompilerEnvironment):
            raise TypeError("authority compiler closure requires a typed environment")
        paths = tuple(path for path, _digest in self.sources)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("authority compiler closure paths must be unique and sorted")
        for path, digest in self.sources:
            if not _is_portable_path(path):
                raise ValueError(f"authority compiler closure path is not portable: {path!r}")
            if _SHA256.fullmatch(digest) is None:
                raise ValueError(f"authority compiler closure digest for {path!r} is not a lowercase SHA-256")

    @property
    def identity_digest(self) -> str:
        """Return the compiler identity this closure and environment determine."""
        return content_hash_hex(
            {
                "schema": _COMPILER_IDENTITY_SCHEMA,
                "sources": [[path, digest] for path, digest in self.sources],
                "python": self.environment.python,
                "dependency_manifests": {
                    "pyproject.toml": self.environment.pyproject_sha256,
                    "uv.lock": self.environment.uv_lock_sha256,
                },
                "dependencies": {
                    "pydantic": self.environment.pydantic,
                    "pydantic-core": self.environment.pydantic_core,
                },
            }
        )


def _is_portable_path(path: str) -> bool:
    if not path or "\\" in path or ":" in path or path.startswith("/"):
        return False
    return all(segment not in {"", ".", ".."} for segment in path.split("/"))
