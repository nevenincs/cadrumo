"""Regex-driven field extraction for AEAT justificante PDFs (#44).

This module translates the raw text of a justificante (as returned by one of
the backends in :mod:`aeat.justificante._parsers`) into a
:class:`Justificante` pydantic record. The regex patterns deliberately
accept both accented ("Código Seguro de Verificación") and stripped
("Codigo Seguro de Verificacion") label variants because AEAT's historical
PDF corpus mixes the two depending on the year and font embedding.

The extractor is **deterministic**: same input bytes → same output record.
All monetary values are parsed via :class:`decimal.Decimal` to preserve the
receipt precision; never floats.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from aeat.logging import get_logger

from ._errors import JustificanteCsvNotFoundError, JustificanteParseError
from ._schema import Justificante

_logger = get_logger(__name__)


# The CSV is 16 uppercase alphanumeric characters in the modern AEAT
# format, but historical receipts sometimes stretch to 20. We therefore
# accept 8..24 [A-Z0-9] to stay robust while still rejecting obvious noise.
_CSV_LABEL_RE = re.compile(
    r"C[óo]digo\s+Seguro\s+de\s+Verificaci[óo]n\s*[:\-]?\s*([A-Z0-9]{8,24})",
    re.IGNORECASE,
)
_CSV_FALLBACK_RE = re.compile(r"\bCSV\s*[:\-]?\s*([A-Z0-9]{8,24})", re.IGNORECASE)

_MODELO_RE = re.compile(r"Modelo\s*[:\-]?\s*([0-9]{3}[A-Z]?)", re.IGNORECASE)
_PERIOD_RE = re.compile(r"Per[íi]odo\s*[:\-]?\s*([0-9A-Z]{1,8})", re.IGNORECASE)
_EJERCICIO_RE = re.compile(r"Ejercicio\s*[:\-]?\s*([0-9]{4})", re.IGNORECASE)
_NIF_RE = re.compile(r"NIF\s*[:\-]?\s*([0-9A-Z]{8,12})", re.IGNORECASE)
_PRESENTATION_ID_RE = re.compile(
    r"N[úu]mero\s+de\s+justificante\s*[:\-]?\s*([0-9A-Z]{10,40})",
    re.IGNORECASE,
)
_PRESENTED_AT_RE = re.compile(
    r"Fecha\s+y\s+hora\s+de\s+presentaci[óo]n\s*[:\-]?\s*"
    r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)",
    re.IGNORECASE,
)
_TOTAL_INGRESAR_RE = re.compile(
    r"Total\s+a\s+ingresar\s*[:\-]?\s*([0-9][0-9\.,]*)",
    re.IGNORECASE,
)
_TOTAL_DEVOLVER_RE = re.compile(
    r"Total\s+a\s+devolver\s*[:\-]?\s*([0-9][0-9\.,]*)",
    re.IGNORECASE,
)
_URL_RE = re.compile(
    r"https?://[A-Za-z0-9.\-_/%?&=:#~+]+",
)


def _strip_accents(value: str) -> str:
    """Return ``value`` with Unicode combining marks removed.

    The extractor is tolerant of accented / unaccented label variants by
    matching the regexes case-insensitively and with ``[íi]`` / ``[óo]``
    character classes, but falling back via ``_strip_accents`` lets us
    recover ``Código`` fields printed with odd combining sequences.
    """
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))


def _parse_decimal(raw: str) -> Decimal:
    """Parse an AEAT-formatted decimal string (``1.234,56`` or ``1234.56``).

    Args:
        raw: Raw numeric substring captured from the PDF.

    Returns:
        A :class:`decimal.Decimal` preserving the printed precision.

    Raises:
        JustificanteParseError: If the string is not a recognisable number.
    """
    cleaned = raw.strip().replace(" ", "")
    if "," in cleaned and "." in cleaned:
        # Spanish thousands + comma decimal: 1.234,56 → 1234.56
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise JustificanteParseError(f"invalid decimal literal: {raw!r}") from exc


def _parse_datetime(raw: str) -> datetime:
    """Parse the ``YYYY-MM-DD HH:MM[:SS]`` timestamps AEAT stamps on receipts.

    The timestamp is returned as a *naive* datetime because AEAT does not
    print a timezone; callers that need UTC must apply the known Europe/Madrid
    offset themselves.
    """
    normalised = raw.replace("T", " ").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(normalised, fmt)
        except ValueError:
            continue
    raise JustificanteParseError(f"unrecognised datetime literal: {raw!r}")


def _sha256_file(path: Path) -> str:
    """Return the lowercase hex sha-256 of the bytes at ``path``."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _require(match: re.Match[str] | None, field: str) -> str:
    """Return ``match.group(1)`` or raise a parse error naming ``field``."""
    if match is None:
        raise JustificanteParseError(f"could not locate required field: {field}")
    return match.group(1).strip()


def extract_justificante(text: str, pdf_path: Path) -> Justificante:
    """Extract a :class:`Justificante` from the raw text of a receipt PDF.

    Args:
        text: Full concatenated text returned by a parser backend.
        pdf_path: Path of the source PDF (used for ``source_pdf_path`` and
            the sha-256 digest).

    Returns:
        A fully populated :class:`Justificante` record.

    Raises:
        JustificanteCsvNotFoundError: If no CSV can be located in ``text``.
        JustificanteParseError: If any other required field is missing or
            cannot be coerced into its target type.
    """
    if not text.strip():
        raise JustificanteParseError(f"empty text extracted from {pdf_path}")

    normalised = _strip_accents(text)

    csv_match = _CSV_LABEL_RE.search(text) or _CSV_LABEL_RE.search(normalised)
    if csv_match is None:
        csv_match = _CSV_FALLBACK_RE.search(normalised)
    if csv_match is None:
        raise JustificanteCsvNotFoundError(f"no Código Seguro de Verificación found in {pdf_path}")
    csv_value = csv_match.group(1).upper()

    modelo = _require(_MODELO_RE.search(normalised), "modelo")
    period = _require(_PERIOD_RE.search(normalised), "period")
    nif = _require(_NIF_RE.search(normalised), "tax_id").upper()

    presented_match = _PRESENTED_AT_RE.search(normalised)
    presented_raw = _require(presented_match, "presented_at")
    presented_at = _parse_datetime(presented_raw)

    presentation_match = _PRESENTATION_ID_RE.search(normalised)
    presentation_id = presentation_match.group(1).strip() if presentation_match else None

    ingresar_match = _TOTAL_INGRESAR_RE.search(normalised)
    total_ingresar: Decimal | None = _parse_decimal(ingresar_match.group(1)) if ingresar_match else None

    devolver_match = _TOTAL_DEVOLVER_RE.search(normalised)
    total_devolver: Decimal | None = _parse_decimal(devolver_match.group(1)) if devolver_match else None

    url_match = _URL_RE.search(text)
    if url_match is None:
        raise JustificanteParseError(f"no verification URL found in {pdf_path}")
    verification_url_raw = url_match.group(0).rstrip(".,);")
    try:
        verification_url = TypeAdapter(AnyHttpUrl).validate_python(verification_url_raw)
    except ValidationError as exc:
        raise JustificanteParseError(f"invalid verification URL in {pdf_path}: {verification_url_raw!r}") from exc

    sha256 = _sha256_file(pdf_path)
    parsed_at = datetime.now(tz=UTC)

    try:
        return Justificante(
            csv=csv_value,
            modelo=modelo,
            period=period,
            presentation_id=presentation_id,
            presented_at=presented_at,
            tax_id=nif,
            total_a_ingresar=total_ingresar,
            total_a_devolver=total_devolver,
            verification_url=verification_url,
            source_pdf_path=pdf_path,
            source_pdf_sha256=sha256,
            parsed_at=parsed_at,
        )
    except ValidationError as exc:
        raise JustificanteParseError(f"failed to validate Justificante for {pdf_path}: {exc}") from exc
