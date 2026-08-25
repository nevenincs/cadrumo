"""Preprocess committed Terminology Handbook concept fragments for RAG.

The Handbook is authored as TOML under ``_data/terminology/concepts``. TOML is
not admitted by vaultspec-rag's conventional source profile, so the resident
index receives these project-owned fragments through the same explicit hook
boundary used for the bundled corpus sources. The source path is preserved in
the upstream payload so the terminology resolver can map a hit to its concept
record without inventing a target.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from ..._paths import UTF_8
from ._parts import split_units_by_budget
from ._schema import ExtractionStatus, PreprocessOutput, PreprocessUnit, SourceDocumentKind
from ._sidecar import sha256_of

_UTF_8: Final[str] = UTF_8

# Stable extractor identity/version values are part of the upstream preprocess
# cache key and the repo-root rule's explicit version stamp.
TERMINOLOGY_EXTRACTOR_ID: Final[str] = "terminology-concept"
TERMINOLOGY_EXTRACTOR_VERSION: Final[str] = "1.0"
_ATTRIBUTION: Final[str] = (
    "Cadrumo Terminology Handbook; repository-authored concept fragment with "
    "source citations carried in the TOML record."
)


def build_outputs(source: Path, *, repo_root: Path) -> list[PreprocessOutput]:
    """Render one UTF-8 Handbook TOML fragment as upstream index units."""
    text = source.read_text(encoding=_UTF_8).replace("\r\n", "\n").replace("\r", "\n").strip()
    relpath = source.resolve().relative_to(repo_root.resolve()).as_posix()
    digest = sha256_of(source)
    if not text:
        return [
            PreprocessOutput(
                source_kind=SourceDocumentKind.TERMINOLOGY_CONCEPT,
                status=ExtractionStatus.EMPTY,
                source_relpath=relpath,
                source_sha256=digest,
                preprocessor_id=TERMINOLOGY_EXTRACTOR_ID,
                preprocessor_version=TERMINOLOGY_EXTRACTOR_VERSION,
                attribution=_ATTRIBUTION,
                units=(),
            )
        ]

    units = split_units_by_budget([PreprocessUnit(text=text, title=source.stem, section="concept")])
    return [
        PreprocessOutput(
            source_kind=SourceDocumentKind.TERMINOLOGY_CONCEPT,
            status=ExtractionStatus.OK,
            source_relpath=relpath,
            source_sha256=digest,
            preprocessor_id=TERMINOLOGY_EXTRACTOR_ID,
            preprocessor_version=TERMINOLOGY_EXTRACTOR_VERSION,
            attribution=_ATTRIBUTION,
            units=tuple(group),
        )
        for group in units
    ]
