"""Interim extraction-sidecar contract for the dev-side RAG index.

Defines the versioned :class:`PreprocessOutput` schema that the
project-side document preprocessors (BOE normatives HTML, Disenos de
Registro workbooks, corpus PDFs, the unsupported-text tail) emit so the
binary and unsupported-extension grounding corpus becomes indexable by the
resident ``vaultspec-rag`` walker. The walker has no preprocess-hook
capability yet, so this package materialises extracted text as committed
``*.extracted.md`` sidecars next to each source file plus a
``*.extracted.json`` provenance sidecar; the walker already indexes ``.md``,
so the sidecars enter the code index with zero upstream change.

This is the interim path adjudicated in the ``docs-terminology-search``
ADR decision D6 (the index-capability prerequisite). It is a
forward-compatible precursor of the generic upstream preprocess-output
schema requested from the ``vaultspec-rag`` team: when the upstream hook
lands, the preprocessors emit the upstream schema directly and this sidecar
tree is retired. The sidecar fields are a subset/precursor of that upstream
contract so the migration is mechanical.

Major declarations:

* :class:`PreprocessOutput` -- the versioned strict extraction record.
* :class:`PreprocessUnit` -- one pre-chunked text unit (text plus optional
  title/section/anchor) inside a :class:`PreprocessOutput`.
* :class:`SourceDocumentKind` -- the closed source-format axis.
* :class:`ExtractionStatus` -- the closed extraction-outcome axis.
* :func:`write_sidecar` / :func:`load_sidecar` -- the thin
  writer/loader for the ``*.extracted.md`` + ``*.extracted.json`` pair.
* :data:`PREPROCESS_SCHEMA_VERSION` -- the current schema version string.
"""

from __future__ import annotations

from ._schema import (
    PREPROCESS_SCHEMA_VERSION,
    ExtractionStatus,
    PreprocessOutput,
    PreprocessUnit,
    SourceDocumentKind,
)
from ._sidecar import (
    EXTRACTED_JSON_SUFFIX,
    EXTRACTED_TEXT_SUFFIX,
    PreprocessSidecarError,
    load_sidecar,
    sidecar_paths_for,
    write_sidecar,
)

__all__ = [
    "EXTRACTED_JSON_SUFFIX",
    "EXTRACTED_TEXT_SUFFIX",
    "PREPROCESS_SCHEMA_VERSION",
    "ExtractionStatus",
    "PreprocessOutput",
    "PreprocessSidecarError",
    "PreprocessUnit",
    "SourceDocumentKind",
    "load_sidecar",
    "sidecar_paths_for",
    "write_sidecar",
]
