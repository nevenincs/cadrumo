"""Versioned strict schema for interim preprocess extraction sidecars.

The :class:`PreprocessOutput` record is the contract the four project-side
preprocessors (normatives HTML, Disenos de Registro workbooks, corpus PDFs,
the unsupported-text tail) emit against. It is a forward-compatible
precursor of the generic upstream ``vaultspec-rag`` preprocess-output
schema: a versioned envelope of extracted text or pre-chunked units, each
carrying ``text`` plus an optional title, section, and anchor, with a
source locator, extractor provenance, and a ``schema_version``. Every field
present here maps one-to-one onto a field the upstream generic schema is
specified to carry, so migration to the upstream hook is a mechanical
re-serialisation rather than a re-extraction.

Provenance is declared data cross-checked against physical evidence (the
``fixture-provenance-declared-in-sidecar`` discipline): the sidecar records
the origin file's POSIX-relative path and its content hash, the extractor
id and version, and the extraction run identifier, so a stale or
mis-extracted sidecar (origin hash no longer matching the file on disk) is
detectable by a gate without an allowlist.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

#: Current sidecar schema version. Bump on any breaking field change; the
#: loader refuses an unknown version rather than silently coercing.
PREPROCESS_SCHEMA_VERSION = "1.0"


class SourceDocumentKind(StrEnum):
    """Closed set of source formats the interim preprocessors extract.

    One member per project-side preprocessor family. The value is the stable
    extraction-origin axis recorded in every sidecar's provenance so a
    consumer can filter or weight by origin format without re-sniffing the
    source file.
    """

    NORMATIVES_HTML = "normatives_html"
    DISENO_REGISTRO_WORKBOOK = "diseno_registro_workbook"
    CORPUS_PDF = "corpus_pdf"
    UNSUPPORTED_TEXT = "unsupported_text"


class ExtractionStatus(StrEnum):
    """Closed set of extraction outcomes (the skip-and-report axis).

    ``ok`` carries usable units. ``empty`` records that the source held no
    extractable text (a cover-page-only PDF, an empty workbook sheet) so the
    sidecar is not mistaken for a failed run. ``partial`` records that some
    units extracted but the preprocessor flagged a degraded result (an
    unparseable sheet inside an otherwise-extracted workbook). These mirror
    the upstream contract's hard-fail-versus-skip-and-report semantics: a
    preprocessor that cannot extract at all raises instead of writing an
    ``ok`` sidecar.
    """

    OK = "ok"
    EMPTY = "empty"
    PARTIAL = "partial"


class PreprocessUnit(BaseModel):
    """One pre-chunked extracted text unit inside a :class:`PreprocessOutput`.

    A unit is the granularity the preprocessor chooses to surface: a BOE
    article (split on the ``<h5 class="articulo">`` delimiter), one Disenos
    de Registro sheet's casilla-to-field table, a PDF page or section. The
    walker re-chunks the rendered sidecar text itself, so a unit is a
    semantic boundary hint, not a hard chunk; ``title`` and ``anchor`` let a
    downstream chunk-to-target resolver map a hit back to its origin
    location.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    text: str = Field(min_length=1)
    title: str | None = None
    section: str | None = None
    anchor: str | None = None


class PreprocessOutput(BaseModel):
    """Versioned strict record of one source file's extracted text.

    Serialised as the ``*.extracted.json`` provenance sidecar; the rendered
    plain text is written alongside as ``*.extracted.md`` (the surface the
    walker indexes). The two are written and loaded together by
    :func:`~dev.docs.preprocess.write_sidecar` /
    :func:`~dev.docs.preprocess.load_sidecar`.

    Field-to-upstream mapping (precursor of the generic preprocess-output
    schema requested from the ``vaultspec-rag`` team):

    * ``schema_version`` -> upstream versioned-envelope version.
    * ``units`` (text + optional title/section/anchor) -> upstream
      pre-chunked-units list.
    * ``source_relpath`` + ``source_sha256`` -> upstream source locator and
      cache key (the upstream cache keys on source content hash plus
      preprocessor identity/version).
    * ``preprocessor_id`` + ``preprocessor_version`` -> upstream producing
      preprocessor id and version (the other half of the cache key).
    * ``source_kind`` + ``status`` -> upstream metadata and skip-and-report
      semantics.
    * ``attribution`` -> the BOE/AEAT licence obligation carried with the
      extracted text (research P5; corpus text reuse requires attribution).
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    schema_version: str = Field(default=PREPROCESS_SCHEMA_VERSION, min_length=1)
    source_kind: SourceDocumentKind
    status: ExtractionStatus
    source_relpath: str = Field(
        min_length=1,
        description="POSIX-relative path of the origin file from the repo root.",
    )
    source_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
        description="Hex sha256 of the origin file's bytes, for stale detection.",
    )
    preprocessor_id: str = Field(
        min_length=1,
        description="Stable id of the extractor that produced this sidecar.",
    )
    preprocessor_version: str = Field(
        min_length=1,
        description="Version of the extractor, part of the cache identity.",
    )
    attribution: str = Field(
        min_length=1,
        description=(
            "Licence/attribution string for the extracted text (BOE/AEAT "
            "corpus reuse requires attribution per research P5)."
        ),
    )
    units: tuple[PreprocessUnit, ...] = Field(default=())

    def render_text(self) -> str:
        """Render the indexable plain-text body written to ``*.extracted.md``.

        Concatenates every unit's title (as a Markdown ``#`` heading when
        present) and text into one document the walker chunks. The rendered
        form is deterministic so the sidecar text round-trips and a drift
        gate can compare a regenerated render against the committed one.
        """
        blocks: list[str] = []
        for unit in self.units:
            if unit.title:
                blocks.append(f"# {unit.title}\n\n{unit.text}")
            else:
                blocks.append(unit.text)
        return "\n\n".join(blocks)
