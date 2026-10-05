"""Read production source text from the enumerated working tree.

Extracted from the retired CLI action census, which was removed along with its
hand-maintained disposition ledger. Nothing here is an exemption list: the
file set is derived by enumerating what the tree actually contains under
the product package, honouring the repository's own ``.gitignore`` rules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8
from dev.first_party_source import PRODUCT_PACKAGE, is_production_source
from dev.source_tree import normalised_contents, repository_files

_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".toml", ".json", ".md"})


def repository_sources(root: Path = REPO_ROOT) -> tuple[tuple[str, str], ...]:
    """Read census-relevant repository text from the working tree at ``root``.

    Args:
        root: Repository root to enumerate. Defaults to the live tree.

    Returns:
        Sorted ``(repository-relative path, decoded text)`` pairs.
    """
    candidates = [
        relative
        for relative in repository_files(root, under=(PRODUCT_PACKAGE,))
        if Path(relative).suffix in _SOURCE_SUFFIXES
    ]
    sources: list[tuple[str, str]] = []
    for relative, content in normalised_contents(root, candidates):
        try:
            sources.append((relative, content.decode(UTF_8)))
        except UnicodeDecodeError:
            continue
    return tuple(sorted(sources))


def production_sources(root: Path = REPO_ROOT) -> tuple[tuple[str, str], ...]:
    """Return the production-Python source universe of the product package.

    Args:
        root: Repository root to enumerate. Defaults to the live tree.

    Returns:
        Sorted ``(path, source)`` pairs for non-test Python modules.
    """
    return tuple((path, source) for path, source in repository_sources(root) if is_production_source(path))
