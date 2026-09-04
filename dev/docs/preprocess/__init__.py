"""Corpus extraction: the product's committed text payload and the dev-index hook.

Defines the versioned :class:`PreprocessOutput` schema the project-side
document preprocessors (BOE normatives HTML, Disenos de Registro workbooks,
corpus PDFs, and Terminology Handbook concepts) emit, and serves two consumers
from that one extraction truth:

* **The committed sidecar payload** — ``*.extracted.md`` text plus
  ``*.extracted.json`` provenance next to each corpus source. These are
  PRODUCT data, not an indexing workaround: the wheel ships the extracted
  text while excluding the source binaries, the offline corpus search builds
  its lexical index from the ``*.html.extracted.json`` triples, and the
  manual-oracle grounding anchors cite line ranges inside ``*.extracted.md``.
  The freshness gate keeps them true to the sources.
* **The upstream preprocess hook** — :mod:`.hook` adapts the same extractor
  outputs onto the upstream ``vaultspec-rag`` ``PreprocOutput`` contract, so
  the resident dev index reads the corpus straight from the SOURCE files via
  the repo-root ``.vaultragpreprocess.toml`` rules (the sidecars are
  ``.vaultragignore``-excluded from that index to avoid double counting).

Major declarations:

* :class:`PreprocessOutput` -- the versioned strict extraction record.
* :class:`PreprocessUnit` -- one pre-chunked text unit (text plus optional
  title/section/anchor) inside a :class:`PreprocessOutput`.
* :class:`SourceDocumentKind` -- the closed source-format axis.
* :class:`ExtractionStatus` -- the closed extraction-outcome axis.
* :func:`write_sidecar` / :func:`load_sidecar` -- the thin
  writer/loader for the ``*.extracted.md`` + ``*.extracted.json`` pair.
* :data:`PREPROCESS_SCHEMA_VERSION` -- the current schema version string.
* :func:`render_normative_prose` -- the one BOE-markup-to-prose rendering,
  shared with any consumer that must compare an extracted sidecar's text
  against markup the sidecars do not cover.

Every symbol this package defines is imported from the module that defines it;
this initialiser is an inert namespace marker and forwards nothing.
"""
