"""Canonical typed schema for the manual-PDF corpus-text sidecar.

The sidecar is the build-time extraction of an AEAT manual PDF's normalised
text, committed beside the corpus so an installed wheel never needs to run
pypdfium2 to verify a ``required_text`` citation. It is written by the
build-time extractor and read by the registry evidence validator, which are
in different packages; this module is the single declaration both consume so
the writer's guarantees and the reader's admission rules cannot drift.

The contract is deliberately strict and fail-closed. The reader falls back to
on-demand extraction from the real PDF bytes whenever validation refuses, so
refusing a malformed, truncated, or foreign sidecar costs correctness nothing
and never serves text the writer would not have produced.

:data:`MANUAL_CORPUS_TEXT_SCHEMA_VERSION` is pinned exactly: a sidecar
carrying any other version is refused rather than interpreted, and the
extractor regenerates it.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, Field, field_validator

from ..core.models import STRICT_FROZEN_CONFIG

from .hex import HEX_PATTERN_64

__all__ = [
    "MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX",
    "MANUAL_CORPUS_TEXT_SCHEMA_VERSION",
    "MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX",
    "ManualCorpusTextSchemaVersion",
    "ManualCorpusTextSidecar",
]

ManualCorpusTextSchemaVersion = Literal[2]
"""The one accepted sidecar schema version, as a type."""

MANUAL_CORPUS_TEXT_SCHEMA_VERSION: Final[ManualCorpusTextSchemaVersion] = 2
"""The one accepted sidecar schema version, as a value.

Pinned in lock-step with the :class:`ManualCorpusTextSidecar` field set: any
change to the fields is a version bump, and the extractor rewrites every
sidecar because the reader refuses the previous version outright.
"""

MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX: Final[str] = ".corpus_text.json"
"""Filename suffix appended to the source PDF name to address its sidecar."""

MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX: Final[str] = "corpus/"
"""Required prefix of :attr:`ManualCorpusTextSidecar.corpus_path`."""


class ManualCorpusTextSidecar(BaseModel):
    """One manual-PDF corpus-text sidecar payload.

    Args:
        schema_version: The pinned sidecar schema version.
        corpus_path: The source PDF's corpus-root-relative path, carrying the
            ``corpus/`` prefix, e.g.
            ``corpus/manuals/renta/2020/part1/source.pdf``. The reader compares
            it against the path it addressed, so a sidecar filed under the
            wrong name is refused rather than served.
        source_sha256: Lowercase hex SHA-256 of the source PDF bytes. This is
            the content key: it stays valid across installation, where size and
            mtime do not.
        extraction_platform: ``sys.platform`` of the machine that ran the
            extraction. pypdfium2 bundles a per-OS native binary whose text
            output differs subtly, so exact re-extraction equality only holds
            on the generating platform; runtime reads the committed text
            directly and is unaffected.
        normalised_text: The extracted text after
            :func:`~cadrumo.core.normalise_corpus_text`. Never empty: an empty
            extraction is a failed extraction, not a document with no text.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: ManualCorpusTextSchemaVersion
    corpus_path: str = Field(min_length=len(MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX) + 1, max_length=1024)
    source_sha256: str = Field(pattern=HEX_PATTERN_64)
    extraction_platform: str = Field(min_length=1, max_length=64)
    normalised_text: str = Field(min_length=1)

    @field_validator("corpus_path")
    @classmethod
    def _require_corpus_prefix(cls, value: str) -> str:
        if not value.startswith(MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX):
            raise ValueError(f"corpus_path must start with {MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX!r}")
        return value

    def addresses(self, corpus_path: str) -> bool:
        """Return whether this sidecar claims ``corpus_path`` as its source."""
        return self.corpus_path == corpus_path
