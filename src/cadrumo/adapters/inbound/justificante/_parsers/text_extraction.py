"""Private text-backend dispatch for the inbound justificante adapter.

Callers outside :mod:`adapters.inbound.justificante` must never import
from here. Backends expose a common ``extract_text`` entry point that
returns the raw concatenated text of a justificante PDF; all field-level
extraction happens in :mod:`adapters.inbound.justificante._extract`.

The dispatch is keyed on
:class:`domain.justificante.JustificanteParserBackend`, and parse
failures are normalised as
:class:`domain.justificante.JustificanteParseError`. The path entry point
caches concatenated text by source digest, backend, size, and mtime; the bytes
entry point stays uncached so secure-storage callers do not need to materialise
or persist plaintext files.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from .....domain.justificante import JustificanteParseError, JustificanteParserBackend
from ...pdf._utils import sha256_file

_INPUT_PDF_SOURCE_LABEL = "<input-pdf>"
_TEXT_CACHE_MAXSIZE = 256
_TEXT_CACHE: OrderedDict[tuple[str, str, int, int], str] = OrderedDict()


def extract_text(pdf_path: Path, backend: JustificanteParserBackend) -> str:
    """Extract concatenated text from ``pdf_path`` using ``backend``.

    The path result is cached for stable file revisions so repeated corpus
    parses do not reopen the same PDF.

    Args:
        pdf_path: Absolute path to the PDF to read.
        backend: Which backend to dispatch to.

    Returns:
        The concatenated text of every page in the PDF, joined by newlines.

    Raises:
        JustificanteParseError: If the path cannot be read or the selected
            backend is not implemented.
    """
    try:
        resolved = pdf_path.expanduser().resolve()
        stat = resolved.stat()
        source_digest = sha256_file(resolved)
    except OSError as exc:
        raise JustificanteParseError(
            f"justificante PDF could not be read: {_INPUT_PDF_SOURCE_LABEL}",
            context={"path": _INPUT_PDF_SOURCE_LABEL},
            translated_message="adapters.inbound.justificante.errors.parse_failed",
            missing=("source_pdf",),
        ) from exc
    backend_value = backend.value if hasattr(backend, "value") else str(backend)
    cache_key = (source_digest, backend_value, stat.st_size, stat.st_mtime_ns)
    cached = _TEXT_CACHE.get(cache_key)
    if cached is not None:
        _TEXT_CACHE.move_to_end(cache_key)
        return cached

    text = _extract_text_uncached(resolved, backend_value)
    _TEXT_CACHE[cache_key] = text
    _TEXT_CACHE.move_to_end(cache_key)
    if len(_TEXT_CACHE) > _TEXT_CACHE_MAXSIZE:
        _TEXT_CACHE.popitem(last=False)
    return text


def extract_text_from_bytes(pdf_bytes: bytes, backend: JustificanteParserBackend) -> str:
    """Extract concatenated text from in-memory PDF bytes using ``backend``.

    Bytes are sent directly to the selected backend and are not cached, which
    keeps secure-storage and live-capture parsing free of plaintext filesystem
    artefacts.
    """
    backend_value = backend.value if hasattr(backend, "value") else str(backend)
    return _extract_text_from_bytes_uncached(pdf_bytes, backend_value)


def _extract_text_uncached(pdf_path: Path, backend_value: str) -> str:
    """Dispatch one uncached filesystem parse to the selected backend."""
    normalized_backend = backend_value.lower()
    if normalized_backend == JustificanteParserBackend.PDFPLUMBER.value.lower():
        from ._pdfplumber_backend import extract_text_pdfplumber

        return extract_text_pdfplumber(pdf_path)
    raise JustificanteParseError(f"unknown parser backend: {backend_value!r}")


def _extract_text_from_bytes_uncached(pdf_bytes: bytes, backend_value: str) -> str:
    """Dispatch one in-memory parse to the selected backend."""
    normalized_backend = backend_value.lower()
    if normalized_backend == JustificanteParserBackend.PDFPLUMBER.value.lower():
        from ._pdfplumber_backend import extract_text_pdfplumber_bytes

        return extract_text_pdfplumber_bytes(pdf_bytes)
    raise JustificanteParseError(f"unknown parser backend: {backend_value!r}")
