"""Build-time extractor: AEAT manual PDF corpus text to committed sidecars.

Extracts and normalises text from every AEAT manual PDF bundled under
``src/cadrumo/_data/corpus/`` and writes a content-keyed sidecar
``<source>.corpus_text.json`` into ``src/cadrumo/_data/manual_corpus_text/``,
mirroring each PDF's path relative to ``corpus/``.  The sidecar embeds the
sha256 of the source PDF bytes as its content key so it remains valid after
installation (unlike size/mtime, which change across environments).

At runtime :mod:`cadrumo.domain.calculations.registry._validate_evidence`
reads the shipped sidecar for every ``manual_pdf`` source reference, verifies
the sha256 against the deployed PDF bytes, and falls back to on-demand
pypdfium2 extraction only on a mismatch.  End-user machines should never
reach the fallback path: the shipped sidecar covers every ``manual_pdf``
reference the registry declares.

Usage::

    uv run --no-sync python -m dev.corpus.extract_manual_corpus_text
    uv run --no-sync python -m dev.corpus.extract_manual_corpus_text --check

The ``--check`` mode exits non-zero when any sidecar is stale or missing
without writing anything; it is suitable for CI freshness gates.

Operator-run corpus regeneration: run ``just regenerate-corpus-text`` (or the
``python -m`` form above) after a corpus PDF changes and commit the regenerated
sidecars; ``just check-corpus-text`` is the freshness gate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from cadrumo.core import (
    MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX,
    MANUAL_CORPUS_TEXT_SCHEMA_VERSION,
    MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX,
    ManualCorpusTextSidecar,
    normalise_corpus_text,
    scan_directory,
)
from cadrumo.core.hashing import sha256_file

from .._paths import REPO_ROOT, UTF_8

_UTF_8: Final[str] = UTF_8

# dev/corpus/extract_manual_corpus_text.py is two levels below the repo root.
_REPO_ROOT: Final[Path] = REPO_ROOT
_CORPUS_ROOT: Final[Path] = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus"
_SIDECAR_ROOT: Final[Path] = _REPO_ROOT / "src" / "cadrumo" / "_data" / "manual_corpus_text"


def _sidecar_path_for(pdf_path: Path) -> Path:
    """Return the committed sidecar path for a corpus PDF.

    The sidecar mirrors the PDF's path relative to ``_CORPUS_ROOT`` under
    ``_SIDECAR_ROOT``, appending the ``.corpus_text.json`` suffix so the
    sidecar is distinct from the source binary.  Forward slashes are used
    throughout for cross-platform determinism.

    Example: ``corpus/manuals/renta/2020/part1/source.pdf``
    → ``manual_corpus_text/manuals/renta/2020/part1/source.pdf.corpus_text.json``
    """
    relative_posix = pdf_path.relative_to(_CORPUS_ROOT).as_posix()
    return _SIDECAR_ROOT.joinpath(*relative_posix.split("/")).with_name(
        pdf_path.name + MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX
    )


def _is_current(pdf_path: Path, sha256: str) -> bool:
    """Return True when an up-to-date sidecar exists for ``pdf_path``.

    A sidecar is current when it exists and satisfies the very
    :class:`ManualCorpusTextSidecar` contract the runtime evidence validator
    admits it under -- pinned schema version, prefixed corpus path, hex-64
    content key, stamped extraction platform, non-empty text -- and its
    ``source_sha256`` equals the supplied ``sha256``.  Anything the runtime
    would refuse is stale here and gets regenerated, so the writer cannot
    leave behind a sidecar the reader silently falls back past.
    """
    sidecar_path = _sidecar_path_for(pdf_path)
    if not sidecar_path.is_file():
        return False
    try:
        sidecar = ManualCorpusTextSidecar.model_validate_json(sidecar_path.read_text(encoding=_UTF_8))
    except (OSError, UnicodeDecodeError, ValidationError):
        return False
    return sidecar.source_sha256 == sha256


def extract_raw_text(path: Path) -> str:
    """Extract raw page text from a PDF via pypdfium2.

    Public because the corpus sidecar-freshness gate re-runs this exact
    extraction to prove the committed sidecars still equal current output;
    a private name would force that gate to reach into module internals.

    This is the same extraction logic as
    :func:`cadrumo.domain.calculations.registry._validate_evidence._extract_pdf_text_impl`
    and must produce byte-identical output so runtime validation passes.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise SystemExit(
            "pypdfium2 is required to extract PDF text: uv run --no-sync python -m pip install pypdfium2"
        ) from exc
    pdf = pdfium.PdfDocument(str(path))
    pages: list[str] = []
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                text_page = page.get_textpage()
                try:
                    pages.append(text_page.get_text_range())
                finally:
                    text_page.close()
            finally:
                page.close()
    finally:
        pdf.close()
    return "\n".join(pages)


def _write_sidecar(pdf_path: Path, sha256: str, normalised_text: str) -> Path:
    """Write the corpus text sidecar and return its path."""
    sidecar_path = _sidecar_path_for(pdf_path)
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_path = MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX + pdf_path.relative_to(_CORPUS_ROOT).as_posix()
    payload = ManualCorpusTextSidecar(
        schema_version=MANUAL_CORPUS_TEXT_SCHEMA_VERSION,
        corpus_path=corpus_path,
        source_sha256=sha256,
        # pypdfium2 bundles a per-OS native pdfium binary whose text extraction
        # differs subtly across platforms, so the exact re-extraction equality
        # gate only holds on the platform that generated the sidecar.  Runtime
        # reads the committed text directly (keyed by source_sha256) on every
        # platform, so the variance is a build/test-only concern.
        extraction_platform=sys.platform,
        normalised_text=normalised_text,
    )
    # Compact JSON — this is a machine cache that can be megabytes of text.
    sidecar_path.write_text(
        payload.model_dump_json() + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    return sidecar_path


def extract_all(*, check: bool = False) -> int:
    """Extract text from every corpus PDF and write/verify content-keyed sidecars.

    Skips PDFs whose sidecar exists and whose sha256 already matches.  In
    ``check`` mode reports stale/missing sidecars and returns the count
    without writing anything.

    Returns:
        0 on success; the number of stale/missing sidecars in check mode.
    """
    pdf_paths = scan_directory(_CORPUS_ROOT, pattern="*.pdf", recursive=True)
    if not pdf_paths:
        print("No PDF files found under", _CORPUS_ROOT, file=sys.stderr)
        return 1

    stale: list[Path] = []
    for pdf_path in pdf_paths:
        sha256 = sha256_file(pdf_path)
        if _is_current(pdf_path, sha256):
            continue
        stale.append(pdf_path)
        if check:
            print(f"STALE  {pdf_path.relative_to(_REPO_ROOT).as_posix()}")
        else:
            rel = pdf_path.relative_to(_REPO_ROOT).as_posix()
            print(f"Extracting {rel} ...")
            raw_text = extract_raw_text(pdf_path)
            normalised = normalise_corpus_text(raw_text)
            sidecar_path = _write_sidecar(pdf_path, sha256, normalised)
            print(f"  -> {sidecar_path.relative_to(_REPO_ROOT).as_posix()}")

    if check:
        if stale:
            print(
                f"\n{len(stale)} sidecar(s) stale or missing."
                " Run: uv run --no-sync python -m dev.corpus.extract_manual_corpus_text",
                file=sys.stderr,
            )
            return len(stale)
        print(f"All {len(pdf_paths)} manual PDF sidecars are current.")
        return 0

    extracted = len(stale)
    unchanged = len(pdf_paths) - extracted
    print(f"\n{extracted} sidecar(s) written, {unchanged} already current.")
    return 0


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract AEAT manual PDF corpus text to committed content-keyed sidecars.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any sidecar is stale or missing (do not write).",
    )
    args = parser.parse_args()
    sys.exit(extract_all(check=args.check))


if __name__ == "__main__":
    main()
