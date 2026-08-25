"""Corpus PDF text extractor for the dev-side RAG index.

Extracts the 72 tracked corpus PDFs - the AEAT Manuales Practicos (IRPF/IVA
definition prose) and the official Diseno de Registro instruction PDFs -
into schema-conformant sidecars so the resident ``vaultspec-rag`` walker
indexes the BOE/AEAT definition surface that is otherwise structurally
invisible (PDFs are not a walker-supported extension). The manuales are the
authoritative Spanish definition prose a "what does X mean" query needs.

Text is read with ``pdfplumber`` (a locked dependency, built on the
pure-Python ``pdfminer.six`` - no native runtime, honouring the
offline-hermetic build constraint). One :class:`PreprocessUnit` is produced
per page; a manual that extracts to more text than the walker's 10 MB file
cap is split across multiple sidecar parts via the shared budget splitter so
every committed ``.extracted.md`` stays indexable.

Attribution is pulled from the source's ``manifest.json``, which ships in
two shapes: the Diseno-de-registro manifest (one directory above ``files/``,
with a per-artefact ``url`` matched by ``stored_path``) and the manuales
manifest (a sibling of the PDF, with a flat ``source_pdf_url``). Both honour
the BOE/AEAT reuse-with-attribution obligation.

This is the production corpus-PDF preprocessor. When the upstream
``vaultspec-rag`` preprocess-hook lands, this module re-targets the upstream
sink and the committed sidecars are retired; ``PreprocessOutput`` is the
forward-compatible precursor that makes that migration mechanical.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, cast

from ..._paths import UTF_8
from ._parts import (
    split_units_by_budget,
    stamp_part_anchors,
    write_part_sidecars,
)

_UTF_8: Final[str] = UTF_8
from ._schema import (
    ExtractionStatus,
    PreprocessOutput,
    PreprocessUnit,
    SourceDocumentKind,
)
from ._sidecar import PreprocessSidecarError, sha256_of

#: Stable id of this extractor, recorded in every sidecar's provenance.
PDF_EXTRACTOR_ID = "corpus-pdf"

#: Version of this extractor; part of the cache identity. Bump when the
#: rendering changes so a regeneration is distinguishable from a no-op.
PDF_EXTRACTOR_VERSION = "1.0"

#: Standing AEAT attribution used when a manifest cannot pin a precise URL.
_BASE_ATTRIBUTION = "Source: Agencia Estatal de Administracion Tributaria (AEAT). Reused with attribution."


def _attribution_for(source: Path) -> str:
    """Resolve the attribution string for a corpus PDF from its manifest.

    Handles both shipped manifest shapes:

    * Diseno de registro: ``manifest.json`` one directory above ``files/``,
      carrying an ``artefacts`` list whose matching entry has a ``url``.
    * Manuales practicos: a sibling ``manifest.json`` carrying a flat
      ``source_pdf_url``.

    Falls back to the standing AEAT attribution when no manifest or matching
    entry is found, so a PDF never ships corpus text with no attribution.
    """
    # Manuales: sibling manifest with a flat source_pdf_url.
    sibling = source.parent / "manifest.json"
    url = _manuals_url(sibling, source)
    if url:
        return f"{_BASE_ATTRIBUTION} Official source: {url}"

    # Diseno de registro: manifest one level above the files/ directory.
    diseno = source.parent.parent / "manifest.json"
    url = _diseno_url(diseno, source)
    if url:
        return f"{_BASE_ATTRIBUTION} Official source: {url}"

    return _BASE_ATTRIBUTION


def _load_manifest(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding=_UTF_8))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _manuals_url(manifest_path: Path, source: Path) -> str:
    """Return the manuales ``source_pdf_url`` when this manifest describes the PDF."""
    manifest = _load_manifest(manifest_path)
    if manifest is None:
        return ""
    rel_value = manifest.get("relative_pdf_path")
    rel = rel_value.strip() if isinstance(rel_value, str) else ""
    # The manuales manifest names the PDF it describes; only trust its URL
    # when the named file is this source (a directory may hold one PDF).
    if rel and rel != source.name:
        return ""
    url = manifest.get("source_pdf_url")
    return url.strip() if isinstance(url, str) else ""


def _diseno_url(manifest_path: Path, source: Path) -> str:
    """Return the matching Diseno artefact ``url`` for this PDF, if any."""
    manifest = _load_manifest(manifest_path)
    if manifest is None:
        return ""
    artefacts = manifest.get("artefacts")
    if not isinstance(artefacts, list):
        return ""
    for entry in artefacts:
        if not isinstance(entry, dict):
            continue
        # JSON-boundary cast: the manifest is untyped data; the dict is
        # invariant so the narrowed `dict[Unknown, Unknown]` needs a cast to
        # a concrete value type before key access (the third-party data
        # boundary, documented per the type-escape rule).
        artefact = cast("dict[str, object]", entry)
        stored = artefact.get("stored_path")
        if isinstance(stored, str) and stored.endswith(source.name):
            url = artefact.get("url")
            return url.strip() if isinstance(url, str) else ""
    return ""


def _read_pages(source: Path) -> list[str]:
    """Read a PDF page-by-page and return one stripped string per page.

    Uses ``pdfplumber`` (pure-Python pdfminer.six backend). Empty pages
    preserve their slot as the empty string so page numbering is faithful.
    """
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(source) as pdf:
        for page in pdf.pages:
            pages.append((page.extract_text() or "").strip())
    return pages


def build_outputs(source: Path, *, repo_root: Path) -> list[PreprocessOutput]:
    """Extract a corpus PDF into one or more records.

    One :class:`PreprocessUnit` is produced per non-empty page (titled by its
    page number). When the combined text would exceed the per-sidecar byte
    budget the units are grouped so each :class:`PreprocessOutput` renders
    under the walker's file cap, and every unit carries a ``part-N`` anchor.

    Args:
        source: Path to the ``.pdf`` file.
        repo_root: Repository root for the POSIX-relative source locator.

    Returns:
        A list of validated records (one per sidecar pair to write).

    Raises:
        PreprocessSidecarError: If the PDF cannot be read at all (a hard
            failure - never a silently empty ``ok`` sidecar).
    """
    if source.suffix.lower() != ".pdf":
        raise PreprocessSidecarError(f"unsupported extension {source.suffix!r} for PDF extractor: {source}")
    try:
        pages = _read_pages(source)
    except Exception as exc:  # reader-specific failure: hard-fail, do not skip
        raise PreprocessSidecarError(f"cannot read PDF {source}: {exc}") from exc

    relpath = source.resolve().relative_to(repo_root.resolve()).as_posix()
    digest = sha256_of(source)
    attribution = _attribution_for(source)

    units: list[PreprocessUnit] = []
    for page_number, text in enumerate(pages, start=1):
        if text:
            title = f"Pag. {page_number}"
            units.append(PreprocessUnit(text=text, title=title, section=title))

    if not units:
        return [
            PreprocessOutput(
                source_kind=SourceDocumentKind.CORPUS_PDF,
                status=ExtractionStatus.EMPTY,
                source_relpath=relpath,
                source_sha256=digest,
                preprocessor_id=PDF_EXTRACTOR_ID,
                preprocessor_version=PDF_EXTRACTOR_VERSION,
                attribution=attribution,
                units=(),
            ),
        ]

    groups = stamp_part_anchors(split_units_by_budget(units))
    return [
        PreprocessOutput(
            source_kind=SourceDocumentKind.CORPUS_PDF,
            status=ExtractionStatus.OK,
            source_relpath=relpath,
            source_sha256=digest,
            preprocessor_id=PDF_EXTRACTOR_ID,
            preprocessor_version=PDF_EXTRACTOR_VERSION,
            attribution=attribution,
            units=tuple(group),
        )
        for group in groups
    ]


def extract_pdf(source: Path, *, repo_root: Path) -> list[Path]:
    """Extract a corpus PDF and write its committed sidecar pair(s).

    Args:
        source: Path to the ``.pdf`` file.
        repo_root: Repository root for the POSIX-relative source locator.

    Returns:
        The list of ``*.extracted.md`` text-sidecar paths written (one per
        part), in part order.

    Raises:
        PreprocessSidecarError: If the PDF cannot be read or a sidecar cannot
            be written.
    """
    outputs = build_outputs(source, repo_root=repo_root)
    return write_part_sidecars(source, outputs)
