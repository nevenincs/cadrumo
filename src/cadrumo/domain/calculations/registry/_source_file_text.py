"""Raw text of a bundled source file, read at catalogue-build time.

The content validators that check a source's own file for the material it
claims to carry run BEFORE an :class:`EvidenceValidator` is necessarily in
scope for that source, so they cannot go through its cached, PDF-sidecar-aware
resolver. They read the file directly instead -- correct while every source
checked this way is text.

This module exists because two validators each carried their own reader and
they had drifted: one resolved three candidate locations, the other only the
first, while its docstring claimed to mirror the first. A reader that silently
returns ``None`` does not fail -- it SKIPS the check, so the narrower copy
quietly disabled content validation for any source the wider one would have
found.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ....core.external_constants import UTF_8_ENCODING
from ....core.resources.bundled_data import resolve_companion_binary

if TYPE_CHECKING:
    from .schema_references import SourceReference

__all__ = ["read_source_file_text"]


def read_source_file_text(source_root: Path, source: SourceReference) -> str | None:
    """Return the bundled file's raw text, or ``None`` when it cannot be read here.

    ``None`` means "not readable from this position", which every caller treats
    as "skip this check" rather than as a failure, so the resolution order is
    part of the contract: a location dropped here silently removes coverage.
    """
    candidates = (
        source_root / source.corpus_path,
        source_root / "src" / "cadrumo" / "_data" / source.corpus_path,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding=UTF_8_ENCODING, errors="replace")
    companion = resolve_companion_binary(*source.corpus_path.split("/"))
    if companion is not None and companion.is_file():
        return companion.read_text(encoding=UTF_8_ENCODING, errors="replace")
    return None
