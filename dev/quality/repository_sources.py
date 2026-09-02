"""Read production source text from a caller-supplied git revision.

Extracted from the retired CLI action census, which was removed along with its
hand-maintained disposition ledger. Nothing here is an exemption list: the
revision is a required argument supplied by the caller, and the file set is
derived by walking what the revision actually contains.
"""

from __future__ import annotations

import io
import subprocess
import tarfile
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT

SOURCE_ROOT: Final[str] = "src/cadrumo"
_UTF_8: Final[str] = "utf-8"
_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".toml", ".json", ".md"})


def repository_sources(revision: str) -> tuple[tuple[str, str], ...]:
    """Read census-relevant repository text from one pinned revision.

    ``git archive`` is a single, revision-consistent object read. Calling
    ``git show`` per source file made a normal census operationally unbounded
    on this repository despite each individual lookup being cheap.

    Args:
        revision: Git revision to read, for example ``HEAD``.

    Returns:
        Sorted ``(repository-relative path, decoded text)`` pairs.
    """
    completed = subprocess.run(  # noqa: S603 - fixed executable and arguments
        ["git", "archive", "--format=tar", revision, SOURCE_ROOT],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    sources: list[tuple[str, str]] = []
    with tarfile.open(fileobj=io.BytesIO(completed.stdout), mode="r:") as archive:
        for member in archive:
            path = member.name
            if not member.isfile() or Path(path).suffix not in _SOURCE_SUFFIXES:
                continue
            source_file = archive.extractfile(member)
            if source_file is None:
                continue
            try:
                sources.append((path, source_file.read().decode(_UTF_8)))
            except UnicodeDecodeError:
                continue
    return tuple(sorted(sources))


def production_sources(revision: str) -> tuple[tuple[str, str], ...]:
    """Return the production-Python source universe at ``revision``.

    Args:
        revision: Git revision to read, for example ``HEAD``.

    Returns:
        Sorted ``(path, source)`` pairs for non-test Python modules.
    """
    return tuple(
        (path, source)
        for path, source in repository_sources(revision)
        if path.endswith(".py") and "/tests/" not in path and not Path(path).name.startswith("test_")
    )
