"""Source catalogue integrity helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

from ._errors import RegistryValidationError
from ._schema import SourceReference


def verify_source_file(root: Path, source: SourceReference) -> None:
    """Verify one source reference against the local repository filesystem."""

    path = (root / source.corpus_path).resolve()
    repo_root = root.resolve()
    if repo_root not in path.parents and path != repo_root:
        raise RegistryValidationError(f"source {source.id!r} escapes repository root")
    if not path.is_file():
        raise RegistryValidationError(f"source {source.id!r} missing corpus file {source.corpus_path!r}")
    digest = hashlib.sha256()
    length = 0
    with path.open("rb") as handle:
        while chunk := handle.read(65_536):
            digest.update(chunk)
            length += len(chunk)
    if length != source.bytes:
        raise RegistryValidationError(f"source {source.id!r} byte count mismatch")
    if digest.hexdigest() != source.sha256:
        raise RegistryValidationError(f"source {source.id!r} sha256 mismatch")


def verify_source_catalogue(root: Path, sources: Mapping[str, SourceReference]) -> None:
    """Verify every source reference in a source catalogue mapping."""

    for source in sources.values():
        verify_source_file(root, source)
