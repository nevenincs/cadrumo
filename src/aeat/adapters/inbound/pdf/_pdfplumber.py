"""Shared pdfplumber-backed page-text extraction.

Backs the per-format ``extract_pages_text`` / ``extract_pages_text_from_bytes``
public surfaces (borrador, declaracion, justificante). Each per-format
backend remains the public entry point and is responsible for binding
its own format identity to the primitive: it injects the format-specific
error class plus the diagnostic phrasing that error messages must carry.

Public surface
==============

Three return-shape families are supported:

* :func:`extract_pages_text_from_path` /
  :func:`extract_pages_text_from_bytes` — tuple-of-stripped-strings,
  empty-PDF guard raised as ``error_class``. Used by borrador and
  declaracion.
* :func:`extract_pages_text_concatenated` — single ``str`` joined from
  the non-empty pages, no empty-PDF guard. Used by justificante where
  layout-sensitive parsing happens downstream.
* :func:`extract_pages_text_with_fast_path` — wraps the path-based
  primitive with an optional caller-supplied fast-path extractor (e.g.
  the pypdfium2 path used by declaracion). The fast-path runs first; if
  it returns ``None`` the function falls back to pdfplumber.

The :func:`suppress_pdfminer_debug_logging` context manager raises the
``pdfminer`` logger to ``WARNING`` for the duration of the with-block.
The path-based and bytes-based primitives apply it automatically; the
concatenated helper applies it as well.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path

import pdfplumber


@contextmanager
def suppress_pdfminer_debug_logging() -> Iterator[None]:
    """Temporarily raise the ``pdfminer`` logger to ``WARNING``.

    pdfplumber delegates to pdfminer.six, which logs at DEBUG by
    default. Per-format backends use this manager to keep extraction
    quiet without permanently mutating root logger state.
    """

    logger = logging.getLogger("pdfminer")
    previous_level = logger.level
    if previous_level == logging.NOTSET or previous_level < logging.WARNING:
        logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        logger.setLevel(previous_level)


def extract_pages_text_from_path(
    pdf_path: Path,
    *,
    error_class: type[Exception],
    not_found_label: str,
    pdf_label: str,
) -> tuple[str, ...]:
    """Read ``pdf_path`` page-by-page and return one stripped string per page.

    Args:
        pdf_path: Filesystem path of the PDF to read.
        error_class: Format-specific exception class to raise on every
            failure mode (missing file, pdfplumber failure, empty PDF).
            Each per-format backend injects its own (e.g.
            ``BorradorParseError``, ``DeclaracionParseError``) so callers
            can ``except`` by their familiar concrete type.
        not_found_label: Prefix the file-not-found message uses (e.g.
            ``"Modelo 100 PDF not found"``, ``"declaración PDF not found"``).
        pdf_label: Article-prefixed phrase the empty-PDF message uses
            (e.g. ``"PDF"``, ``"the PDF"``) so the diagnostic reads
            naturally per format.

    Returns:
        Tuple of stripped per-page text in page order. Empty pages
        preserve their slot as the empty string.

    Raises:
        ``error_class``: When the file does not exist, when pdfplumber
            cannot open it, or when every page is empty (suggesting a
            scan-only / XFA PDF without an embedded text layer).
    """

    if not pdf_path.is_file():
        raise error_class(f"{not_found_label}: {pdf_path}")
    try:
        with suppress_pdfminer_debug_logging(), pdfplumber.open(pdf_path) as pdf:
            pages = tuple((page.extract_text() or "").strip() for page in pdf.pages)
    except Exception as exc:  # pragma: no cover — defensive; pdfplumber surface
        raise error_class(f"pdfplumber could not open {pdf_path}: {exc}") from exc

    if not any(pages):
        raise error_class(f"no text extracted from {pdf_path}; {pdf_label} may be scan-only or XFA")
    return pages


def extract_pages_text_from_bytes(
    pdf_bytes: bytes,
    *,
    error_class: type[Exception],
    pdf_label: str,
    source_label: str = "in-memory PDF",
) -> tuple[str, ...]:
    """Extract text from PDF bytes without materialising a plaintext file."""

    try:
        with suppress_pdfminer_debug_logging(), pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            pages = tuple((page.extract_text() or "").strip() for page in pdf.pages)
    except Exception as exc:  # pragma: no cover — defensive; pdfplumber surface
        raise error_class(f"pdfplumber could not open {source_label}: {exc}") from exc

    if not any(pages):
        raise error_class(f"no text extracted from {source_label}; {pdf_label} may be scan-only or XFA")
    return pages


def extract_pages_text_concatenated(
    pdf_path: Path,
    *,
    error_class: type[Exception],
) -> str:
    """Return the concatenated text of ``pdf_path`` using pdfplumber.

    Skips empty pages and joins the remaining ``page.extract_text()``
    output with newlines. Unlike :func:`extract_pages_text_from_path`,
    this helper does NOT raise on an all-empty PDF; downstream
    layout-sensitive parsers (justificante) decide what an empty
    document means in their own domain terms.

    Args:
        pdf_path: Filesystem path of the PDF to read.
        error_class: Format-specific exception raised when pdfplumber
            cannot open the file.

    Returns:
        Single string with every non-empty page's text joined by
        newlines. May be empty if every page is empty.

    Raises:
        ``error_class``: When pdfplumber cannot open the file.
    """

    try:
        with suppress_pdfminer_debug_logging(), pdfplumber.open(str(pdf_path)) as pdf:
            chunks: list[str] = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    chunks.append(text)
            return "\n".join(chunks)
    except error_class:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise error_class(f"pdfplumber failed to open {pdf_path}: {exc}") from exc


def extract_pages_text_with_fast_path(
    pdf_path: Path,
    *,
    error_class: type[Exception],
    not_found_label: str,
    pdf_label: str,
    fast_path_extractor: Callable[[Path], tuple[str, ...] | None] | None = None,
) -> tuple[str, ...]:
    """Try ``fast_path_extractor`` first, falling back to pdfplumber.

    The fast-path callable receives the same ``pdf_path`` and must
    return either a tuple of stripped per-page strings (consumed
    verbatim) or ``None`` to signal "fall through to pdfplumber".
    Format-specific extractors (e.g. the pypdfium2 path used by
    declaracion with declaration-content canary regexes) live in the
    calling module so the canonical primitive stays content-neutral.

    When ``fast_path_extractor`` is ``None`` this function is equivalent
    to :func:`extract_pages_text_from_path`.
    """

    if fast_path_extractor is not None and pdf_path.is_file():
        fast_pages = fast_path_extractor(pdf_path)
        if fast_pages is not None:
            return fast_pages
    return extract_pages_text_from_path(
        pdf_path,
        error_class=error_class,
        not_found_label=not_found_label,
        pdf_label=pdf_label,
    )


__all__ = [
    "extract_pages_text_concatenated",
    "extract_pages_text_from_bytes",
    "extract_pages_text_from_path",
    "extract_pages_text_with_fast_path",
    "suppress_pdfminer_debug_logging",
]
