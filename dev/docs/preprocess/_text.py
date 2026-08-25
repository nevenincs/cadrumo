"""Retired text-extension passthrough extractor for the dev-side RAG index.

This interim passthrough closed the small text-extension tail the resident
``vaultspec-rag`` walker could not see: ``.txt``, ``.xml``, ``.xsd``, and the
cp1252 Modelo 100 ``.properties`` diccionario dictionaries (casilla-path to
description mappings). The walker has since added all four to its
supported-extension map and now indexes them raw (as it does HTML) - the exact
upstream extension-map addition this module's lifecycle names as its retirement
trigger.

The passthrough SWEEP is therefore retired: :data:`SUPPORTED_TEXT_EXTENSIONS`
is empty, so no file is swept and no sidecar overlaps the walker's raw index
(the dedup invariant). The retirement is gated by
``test_passthrough_is_retired_now_walker_covers_the_text_tail``: if the walker
ever drops one of the four, that gate fails and the sweep must re-cover it. The
extractor functions below are retained as the upstream-hook migration precursor.

FOLLOW-UP: the walker reads utf-8, so the cp1252 ``.properties`` diccionarios
lose the encoding fidelity the passthrough gave them; raise cp1252 handling with
the ``vaultspec-rag`` walker owner if diccionario search quality regresses.

The extraction is a near-passthrough: the file's text is read with an
encoding-detection fallback (UTF-8, then cp1252, then latin-1 - the AEAT
``.properties`` diccionarios ship as cp1252/latin-1), whitespace is lightly
normalised, and the whole text becomes one :class:`PreprocessUnit`. The
``.properties`` key=value structure is kept verbatim because it is already
human-readable and its structure is the grounding signal.

Attribution is pulled from the sibling Diseno-de-registro ``manifest.json``
(one directory above ``files/``) where the file is a catalogued artefact,
else the standing AEAT/BOE fallback - never unattributed.

This is the production text-tail preprocessor. When the upstream
``vaultspec-rag`` preprocess-hook (or its extension-map addition) lands, this
module is retired; ``PreprocessOutput`` is the forward-compatible precursor
that makes that migration mechanical.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final, cast

from ..._paths import UTF_8
from ._parts import split_units_by_budget, write_part_sidecars
from ._schema import (
    ExtractionStatus,
    PreprocessOutput,
    PreprocessUnit,
    SourceDocumentKind,
)
from ._sidecar import sha256_of

_UTF_8: Final[str] = UTF_8

#: Stable id of this extractor, recorded in every sidecar's provenance.
TEXT_EXTRACTOR_ID = "unsupported-text"

#: Version of this extractor; part of the cache identity. Bump when the
#: rendering changes so a regeneration is distinguishable from a no-op.
TEXT_EXTRACTOR_VERSION = "1.0"

#: Walker-invisible extensions the sweep covers. The resident vaultspec-rag
#: walker now natively indexes the entire former tail (.txt/.xml/.xsd/.properties)
#: raw, so the passthrough sweep is RETIRED (empty) to avoid raw-vs-sidecar
#: double-index; the no-overlap/retirement invariant is gated by
#: test_passthrough_is_retired_now_walker_covers_the_text_tail. The extractor
#: functions are retained as the upstream-hook migration precursor.
#: FOLLOW-UP: the walker reads utf-8, so the cp1252 Modelo-100 diccionario
#: (.properties) files lose the passthrough's cp1252 fidelity once their sidecars
#: are removed; raise cp1252 handling with the vaultspec-rag walker owner.
SUPPORTED_TEXT_EXTENSIONS: frozenset[str] = frozenset()

#: Encoding fallback chain. UTF-8 first; the AEAT .properties diccionarios and
#: some .xsd ship as cp1252; latin-1 is the never-fails final fallback so a
#: file is always decodable rather than silently dropped.
_ENCODINGS = ("utf-8", "cp1252", "latin-1")

#: Standing AEAT/BOE attribution used when no manifest pins a source URL.
_BASE_ATTRIBUTION = (
    "Source: Agencia Estatal de Administracion Tributaria (AEAT) / Boletin "
    "Oficial del Estado (BOE). Reused with attribution."
)

_TRAILING_WS = re.compile(r"[ \t]+(?=\n)")
_BLANKS = re.compile(r"\n{3,}")


def _read_text(source: Path) -> str:
    """Read a text file, trying each encoding in the fallback chain.

    Returns the decoded text from the first encoding that succeeds. ``latin-1``
    decodes any byte sequence, so this never raises for a readable file.
    """
    raw = source.read_bytes()
    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    # Unreachable in practice (latin-1 accepts every byte) but explicit.
    return raw.decode("latin-1", errors="replace")


def _normalise(text: str) -> str:
    """Lightly normalise text: unify newlines, trim trailing space, squeeze blanks.

    The structured content (``.properties`` key=value rows, ``.xml`` / ``.xsd``
    markup) is preserved verbatim otherwise - it is already human-readable and
    its structure is the grounding signal a search must keep.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _TRAILING_WS.sub("", text)
    return _BLANKS.sub("\n\n", text).strip()


def _load_manifest(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding=_UTF_8))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _artefact_url(source: Path) -> str:
    """Return the catalogued Diseno-de-registro artefact URL for this file.

    The Diseno manifest sits one directory above the ``files/`` folder and
    carries an ``artefacts`` list whose matching entry has a ``url``. Returns
    the empty string when no manifest or matching artefact is found.
    """
    manifest = _load_manifest(source.parent.parent / "manifest.json")
    if manifest is None:
        return ""
    artefacts = manifest.get("artefacts")
    if not isinstance(artefacts, list):
        return ""
    for entry in artefacts:
        if not isinstance(entry, dict):
            continue
        # JSON-boundary cast: the manifest is untyped data; the dict is
        # invariant so the narrowed value needs a cast before key access (the
        # third-party data boundary, documented per the type-escape rule).
        artefact = cast("dict[str, object]", entry)
        stored = artefact.get("stored_path")
        if isinstance(stored, str) and stored.endswith(source.name):
            url = artefact.get("url")
            return url.strip() if isinstance(url, str) else ""
    return ""


def _attribution_for(source: Path) -> str:
    """Compose the attribution string for a text-tail file."""
    url = _artefact_url(source)
    if url:
        return f"{_BASE_ATTRIBUTION} Official source: {url}"
    return _BASE_ATTRIBUTION


def build_outputs(source: Path, *, repo_root: Path) -> list[PreprocessOutput]:
    """Extract one unsupported-text-extension file into one or more records.

    The whole file text becomes one :class:`PreprocessUnit`. When that text
    would exceed the per-sidecar byte budget it is split so each
    :class:`PreprocessOutput` renders under the walker's file cap (rare at
    this scale; the largest member is under 1 MB).

    Args:
        source: Path to the ``.txt`` / ``.xml`` / ``.xsd`` / ``.properties``
            file.
        repo_root: Repository root for the POSIX-relative source locator.

    Returns:
        A list of validated records (one per sidecar pair to write).
    """
    text = _normalise(_read_text(source))

    relpath = source.resolve().relative_to(repo_root.resolve()).as_posix()
    digest = sha256_of(source)
    attribution = _attribution_for(source)

    if not text:
        return [
            PreprocessOutput(
                source_kind=SourceDocumentKind.UNSUPPORTED_TEXT,
                status=ExtractionStatus.EMPTY,
                source_relpath=relpath,
                source_sha256=digest,
                preprocessor_id=TEXT_EXTRACTOR_ID,
                preprocessor_version=TEXT_EXTRACTOR_VERSION,
                attribution=attribution,
                units=(),
            )
        ]

    title = source.name
    units = [PreprocessUnit(text=text, title=title, section=title)]
    groups = split_units_by_budget(units)
    return [
        PreprocessOutput(
            source_kind=SourceDocumentKind.UNSUPPORTED_TEXT,
            status=ExtractionStatus.OK,
            source_relpath=relpath,
            source_sha256=digest,
            preprocessor_id=TEXT_EXTRACTOR_ID,
            preprocessor_version=TEXT_EXTRACTOR_VERSION,
            attribution=attribution,
            units=tuple(group),
        )
        for group in groups
    ]


def extract_text_file(source: Path, *, repo_root: Path) -> list[Path]:
    """Extract a text-tail file and write its committed sidecar pair(s).

    Args:
        source: Path to the ``.txt`` / ``.xml`` / ``.xsd`` / ``.properties``
            file.
        repo_root: Repository root for the POSIX-relative source locator.

    Returns:
        The list of ``*.extracted.md`` text-sidecar paths written (one per
        part), in part order.

    Raises:
        PreprocessSidecarError: If a sidecar cannot be written.
    """
    outputs = build_outputs(source, repo_root=repo_root)
    return write_part_sidecars(source, outputs)
