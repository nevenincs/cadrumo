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

from cadrumo.core.external_constants import UTF_8_ENCODING
from dev.registry.compiler.corpus_source_location import locate_corpus_file

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema_references import SourceReference

__all__ = ["read_source_file_text"]


def read_source_file_text(source_root: Path, source: SourceReference) -> str | None:
    """Return the bundled file's raw text, or ``None`` when it cannot be read here.

    ``None`` means "not readable from this position", which every caller treats
    as "skip this check" rather than as a failure, so the resolution order is
    part of the contract: a location dropped here silently removes coverage.
    """
    located = locate_corpus_file(source_root, source.corpus_path)
    if located is None:
        return None
    return located.read_text(encoding=UTF_8_ENCODING, errors="replace")
