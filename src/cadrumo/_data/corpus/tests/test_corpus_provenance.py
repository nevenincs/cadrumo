"""Gate tests for corpus PROVENANCE.md documents.

Each AEAT corpus subdirectory that carries documents derived from
external authority (AEAT Sede, BOE) MUST declare a PROVENANCE.md
file at its root. The gate asserts:

1. The PROVENANCE.md file exists.
2. It enumerates every committed file under the corresponding
   ``files/`` subdirectory.
3. It declares the canonical Source, AEAT-page-last-updated, and
   corpus-capture-date sections.

Authored to protect the committed corpus provenance
documentation against silent drift (a corpus refresh that drops
the metadata file goes undetected without this gate).
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from ....core.directory_scan import iter_directory, scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


bundled_path = importlib.import_module("cadrumo.core.resources").bundled_path
_CORPUS_ROOT = bundled_path("corpus", "aeat_official", "instructions")


def _corpus_subdirectories_with_files() -> list[Path]:
    """Return every corpus subdirectory that has a populated ``files/`` child."""

    if not _CORPUS_ROOT.is_dir():
        return []
    return [
        subdir
        for subdir in scan_directory(_CORPUS_ROOT)
        if subdir.is_dir() and (subdir / "files").is_dir() and any(iter_directory(subdir / "files"))
    ]


def test_modelo_131_corpus_carries_provenance_document() -> None:
    """M131 instructions corpus MUST carry PROVENANCE.md.

    The PROVENANCE.md file documents the
    source URL, AEAT page-last-updated date, and corpus capture
    date. A future corpus refresh that drops or moves the file
    fails this gate; downstream consumers
    grounding claim) lose their provenance lineage without
    detection otherwise.
    """

    modelo_131_corpus = _CORPUS_ROOT / "modelo_131"
    assert modelo_131_corpus.is_dir(), "modelo_131 instructions corpus directory missing"

    provenance = modelo_131_corpus / "PROVENANCE.md"
    assert provenance.is_file(), (
        f"PROVENANCE.md missing at {provenance}; the cap predicate "
        "grounding claim depends on this document's existence and content"
    )

    body = provenance.read_text(encoding="utf-8")
    assert "## Source" in body, "PROVENANCE.md missing '## Source' section"
    assert "Last-update timestamps" in body or "last-updated" in body.lower(), (
        "PROVENANCE.md missing AEAT page last-updated timestamp"
    )
    assert "capture" in body.lower() or "Modified" in body, "PROVENANCE.md missing corpus capture date"


def test_modelo_131_corpus_provenance_lists_every_committed_file() -> None:
    """Every file under modelo_131/files/ MUST appear in PROVENANCE.md.

    Files added to the corpus without a PROVENANCE.md entry are
    structural drift. A future agent who adds a new AEAT-fetched
    HTML/PNG without documenting its source loses the audit trail.
    """

    files_dir = _CORPUS_ROOT / "modelo_131" / "files"
    provenance_body = (_CORPUS_ROOT / "modelo_131" / "PROVENANCE.md").read_text(encoding="utf-8")

    undocumented = [f.name for f in scan_directory(files_dir) if f.is_file() and f.name not in provenance_body]
    assert not undocumented, (
        f"modelo_131/files entries not listed in PROVENANCE.md: {undocumented!r}; "
        "add an entry to the Documents section before landing"
    )
