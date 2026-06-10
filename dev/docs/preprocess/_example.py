"""Minimal worked-example extractor validating the sidecar contract shape.

This is the single end-to-end proof that the :class:`PreprocessOutput`
schema, the sidecar writer/loader, and the walker pickup all fit together.
It is intentionally minimal: it extracts one BOE normatives HTML article
into one :class:`PreprocessUnit` by stripping tags around the
``<h5 class="articulo">`` title and the ``<p class="parrafo">`` body. It is
NOT the production normatives preprocessor -- that implements the full
delimiter-aware splitter, TOC-link-farm stripping, and the bulk run over the
13 MB normatives corpus against this same contract. This stub exists only to
prove the contract end-to-end with one real corpus file.
"""

from __future__ import annotations

import re
from pathlib import Path

from ._schema import (
    ExtractionStatus,
    PreprocessOutput,
    PreprocessUnit,
    SourceDocumentKind,
)
from ._sidecar import sha256_of

#: Stable id for this worked-example extractor (distinct from the production
#: preprocessor id so a sidecar's provenance names exactly what produced it).
EXAMPLE_EXTRACTOR_ID = "normatives-html-example"

#: Version of the worked-example extractor.
EXAMPLE_EXTRACTOR_VERSION = "0.1"

#: AEAT/BOE corpus reuse requires attribution. The production normatives
#: preprocessor resolves the precise BOE permalink from the sibling
#: normatives manifest; the worked example carries the standing obligation.
_NORMATIVES_ATTRIBUTION = (
    "Source: Boletin Oficial del Estado (BOE) / Agencia Estatal de "
    "Administracion Tributaria. Reused with attribution; consult the "
    "sibling normatives manifest for the BOE permalink."
)

_TAG = re.compile(r"<[^>]+>")
_ARTICULO = re.compile(
    r'<h5[^>]*class="articulo"[^>]*>(?P<title>.*?)</h5>',
    re.IGNORECASE | re.DOTALL,
)
_PARRAFO = re.compile(
    r'<p[^>]*class="parrafo"[^>]*>(?P<body>.*?)</p>',
    re.IGNORECASE | re.DOTALL,
)


def _strip(markup: str) -> str:
    return _TAG.sub("", markup).strip()


def extract_normatives_html(source: Path, *, repo_root: Path) -> PreprocessOutput:
    """Extract one BOE normatives HTML article into a :class:`PreprocessOutput`.

    Args:
        source: Path to the ``.html`` article slice.
        repo_root: Repository root, used to compute the POSIX-relative
            source locator stored in the sidecar provenance.

    Returns:
        A validated :class:`PreprocessOutput` carrying one unit (title =
        the articulo heading, text = the parrafo body) or an ``empty``
        record when no recognisable article markup is present.
    """
    markup = source.read_text(encoding="utf-8")
    title_match = _ARTICULO.search(markup)
    body_parts = [_strip(m.group("body")) for m in _PARRAFO.finditer(markup)]
    body = "\n\n".join(part for part in body_parts if part)

    relpath = source.resolve().relative_to(repo_root.resolve()).as_posix()
    digest = sha256_of(source)

    units: tuple[PreprocessUnit, ...] = ()
    status = ExtractionStatus.EMPTY
    if body:
        title = _strip(title_match.group("title")) if title_match else None
        units = (PreprocessUnit(text=body, title=title or None),)
        status = ExtractionStatus.OK

    return PreprocessOutput(
        source_kind=SourceDocumentKind.NORMATIVES_HTML,
        status=status,
        source_relpath=relpath,
        source_sha256=digest,
        preprocessor_id=EXAMPLE_EXTRACTOR_ID,
        preprocessor_version=EXAMPLE_EXTRACTOR_VERSION,
        attribution=_NORMATIVES_ATTRIBUTION,
        units=units,
    )
