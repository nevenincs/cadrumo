"""Source catalogue integrity helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from ._errors import RegistryValidationError
from ._schema import SourceReference


def verify_source_file(root: Path, source: SourceReference) -> None:
    """Verify one source reference against the local repository filesystem."""

    repo_root = root.resolve()
    path = _resolve_corpus_path(repo_root, source)
    if repo_root not in path.parents and path != repo_root:
        raise RegistryValidationError(f"source {source.id!r} escapes repository root")
    if not path.is_file():
        raise RegistryValidationError(f"source {source.id!r} missing corpus file {source.corpus_path!r}")
    stat = path.stat()
    length, actual_sha256 = _source_file_fingerprint(str(path), stat.st_size, stat.st_mtime_ns)
    if length != source.bytes:
        raise RegistryValidationError(f"source {source.id!r} byte count mismatch")
    if actual_sha256 != source.sha256:
        raise RegistryValidationError(f"source {source.id!r} sha256 mismatch")


def _resolve_corpus_path(root: Path, source: SourceReference) -> Path:
    direct = (root / source.corpus_path).resolve()
    if direct.is_file():
        return direct
    packaged = (root / "src" / "aeat" / "_data" / source.corpus_path).resolve()
    if packaged.is_file():
        return packaged
    return direct


@lru_cache(maxsize=2048)
def _source_file_fingerprint(path: str, byte_count: int, modified_ns: int) -> tuple[int, str]:
    del byte_count, modified_ns
    digest = hashlib.sha256()
    length = 0
    with Path(path).open("rb") as handle:
        while chunk := handle.read(65_536):
            digest.update(chunk)
            length += len(chunk)
    return length, digest.hexdigest()


def verify_source_catalogue(root: Path, sources: Mapping[str, SourceReference]) -> None:
    """Verify every source reference in a source catalogue mapping."""

    verified: set[tuple[Path, int, str]] = set()
    for source in sources.values():
        key = ((root / source.corpus_path).resolve(), source.bytes, source.sha256)
        if key in verified:
            continue
        verify_source_file(root, source)
        verified.add(key)
