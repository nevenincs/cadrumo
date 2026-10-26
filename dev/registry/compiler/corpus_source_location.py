"""Locate one corpus file named by a registry source reference.

A corpus path is stated relative to the data root, and that root appears in
three places depending on how the tree is read: directly under the source root,
under the packaged ``src/cadrumo/_data`` tree of a checkout, or mirrored in the
mandatory ``cadrumo_data`` companion namespace that carries the binaries the
command-bearing wheel sheds. This module is the one place that order is
stated, so every verifier that reads a cited source reads the same file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from cadrumo.core.resources.bundled_data import resolve_companion_binary

PACKAGED_DATA_ROOT: Final = Path("src") / "cadrumo" / "_data"


class CorpusPathEscapeError(OSError):
    """A corpus path resolves outside the root it is stated relative to."""


def locate_corpus_file(source_root: Path, corpus_path: str) -> Path | None:
    """Return the existing file ``corpus_path`` names, or ``None`` when no location holds it.

    Locations are tried in order: ``source_root`` itself, its packaged data
    tree, then the companion namespace. A candidate that resolves outside
    ``source_root`` is refused rather than skipped, because a path that climbs
    out of the corpus is a defect in the declaration and not an absent file.

    Raises:
        CorpusPathEscapeError: A source-root or packaged candidate leaves ``source_root``.
    """
    root = source_root.expanduser().resolve()
    for base in (root, root / PACKAGED_DATA_ROOT):
        candidate = (base / corpus_path).expanduser().resolve()
        if root not in candidate.parents and candidate != root:
            raise CorpusPathEscapeError(f"corpus path {corpus_path!r} escapes its source root")
        if candidate.is_file():
            return candidate
    companion = resolve_companion_binary(*corpus_path.split("/"))
    if companion is not None and companion.is_file():
        return companion
    return None
