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

from ..logging import get_logger
from ._errors import JustificanteCsvNotFoundError, JustificanteParseError
from ._schema import Justificante

_logger = get_logger(__name__)


# The CSV is 16 uppercase alphanumeric characters in the modern AEAT
# format, but historical receipts sometimes stretch to 20. We therefore
# accept 8..24 [A-Z0-9] to stay robust while still rejecting obvious noise.
_CSV_LABEL_RE = re.compile(
    r"C[óo]digo\s+Seguro\s+de\s+Verificaci[óo]n\s*[:\-]?\s*([A-Z0-9]{8,24})\b",
    re.IGNORECASE,
)
# Older AEAT layouts (Modelo 100 pre-2022) render labels on the right
# column and values on the left, so pdfplumber's top-down / left-right
# traversal emits VALUE then LABEL. Captured live on IRPF 2021.
_CSV_LABEL_INVERTED_RE = re.compile(
    r"\b([A-Z0-9]{8,24})\s+C[óo]digo\s+Seguro\s+de\s+Verificaci[óo]n",
    re.IGNORECASE,
)
# Every AEAT justificante ends with a stable authenticity footer:
#   "La autenticidad de este documento puede ser comprobada mediante
#    el Código Seguro [N] de Verificación XXXX en
#    https://sede.agenciatributaria.gob.es".
# The optional "[N]" is a page-number interstitial pdfplumber sometimes
# lifts into the text. This footer is the most reliable fallback.
_CSV_AUTHENTICITY_FOOTER_RE = re.compile(
    r"mediante\s+el\s+C[óo]digo\s+Seguro\s*(?:\d+\s+)?"
    r"de\s+Verificaci[óo]n\s+([A-Z0-9]{8,24})\b",
    re.IGNORECASE,
)
# Used only as a last resort: the 'CSV' token is noisy in normalised
# text ("Presentador" includes the letter sequence), so we require a
# colon/dash separator and the 'CSV=' equality form.
_CSV_FALLBACK_RE = re.compile(r"\bCSV\s*[=:]\s*([A-Z0-9]{8,24})\b", re.IGNORECASE)

_MODELO_RE = re.compile(r"Modelo\s*[:\-]?\s*([0-9]{3}[A-Z]?)", re.IGNORECASE)
# Spanish period tokens always contain at least one digit (``1T``,
# ``0A``, ``4T``, ``2023``). Requiring a digit in the captured group
# stops the regex from picking up nearby words like "impositivo" out
# of "Período impositivo".
_PERIOD_RE = re.compile(r"Per[íi]odo\s*[:\-]?\s*([0-9A-Z]*\d[0-9A-Z]*)", re.IGNORECASE)
# Quarterly modelos (130, 303, 111, 115, 123) often print the period
# in a positional layout that pdfplumber merges as
# ``[<NIF>] <YYYY> <period>`` on a single line, with no "Período"
# label. The period token is one of ``1T``, ``2T``, ``3T``, ``4T``,
# ``0A``, or a 1-2 digit month (``01``-``12``). Captured live across
# Modelos 130/303/111 (2026-04-25).
_PERIOD_POSITIONAL_RE = re.compile(
    r"(?:[A-Z][0-9A-Z]{7,9}\s+)?"  # optional NIF/NIE
    r"\b(?P<year>\d{4})\s+"
    r"(?P<period>0A|[1-4]T|0[1-9]|1[0-2])\b",
)
_EJERCICIO_RE = re.compile(r"Ejercicio\s*[:\-]?\s*([0-9]{4})", re.IGNORECASE)
# Some annual informativas (M190 "Resumen anual") print the ejercicio
# label with a parenthetical and a dotted leader before the value:
# ``Ejercicio (con 4 cifras) ....... 2024``. The parenthetical may
# contain digits ("con 4 cifras"); the regex tolerates short
# intervening text and pinpoints the 4-digit year via a single-line
# proximity match.
_EJERCICIO_LOOSE_RE = re.compile(
    r"Ejercicio\b[^\n]{0,80}?\b(20\d{2})\b",
    re.IGNORECASE,
)
# Annual informativas (190, 390, 347) print only "Anual" / "0A" or
# omit the period label entirely; the schema falls back to the
# ejercicio in that case (see :func:`extract_justificante`).
_NIF_RE = re.compile(
    # NIF / NIE shape: leading letter (NIE) or digit (NIF), 7-8 mid
    # digits, trailing checksum letter. Total length 9 in practice.
    # Stricter than the previous "[0-9A-Z]{8,12}" pattern, which
    # accidentally matched the word "PRESENTADOR" in the
    # ``NIF Presentador: <value>`` register-printed shape.
    r"NIF\s*(?:Presentador)?\s*[:\-]?\s*"
    r"([XYZ\d]\d{7}[A-Z])",
    re.IGNORECASE,
)
_PRESENTATION_ID_RE = re.compile(
    r"N[úu]mero\s+de\s+justificante\s*[:\-]?\s*([0-9A-Z]{10,40})",
    re.IGNORECASE,
)
_PRESENTED_AT_RE = re.compile(
    r"Fecha\s+y\s+hora\s+de\s+presentaci[óo]n\s*[:\-]?\s*"
    r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)",
    re.IGNORECASE,
)
# Annual modelos (100, 190, ...) print the timestamp as
# "Presentación realizada el: DD-MM-YYYY a las HH:MM:SS"
# on 2022+ layouts. 2021-era Modelo 100 PDFs are column-split so
# pdfplumber reads the value FIRST and the label AFTER; we accept
# both orderings. Captured live on Modelo 100 IRPF 2021-2023.
_PRESENTED_AT_ANNUAL_RE = re.compile(
    r"Presentaci[óo]n\s+realizada\s+el\s*[:\-]?\s*"
    r"(\d{2}-\d{2}-\d{4})\s+a\s+las\s+(\d{2}:\d{2}(?::\d{2})?)",
    re.IGNORECASE,
)
_PRESENTED_AT_ANNUAL_INVERTED_RE = re.compile(
    r"(\d{2}-\d{2}-\d{4})\s+a\s+las\s+(\d{2}:\d{2}(?::\d{2})?)\s+"
    r"Presentaci[óo]n\s+realizada\s+el",
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
# Modelo 100 annual receipts label the paid amount as
# "NRC: <code> IMPORTE: <decimal>" under an "INGRESAR" header (no
# "Total a ingresar" wording). Captured live 2026-04-24.
_NRC_IMPORTE_RE = re.compile(
    r"NRC\s*[:\-]?\s*[A-Z0-9]+\s+IMPORTE\s*[:\-]?\s*([0-9][0-9\.,]*)",
    re.IGNORECASE,
)
# Modelo 100 annual receipts sometimes label the payment id as
# "Número de justificante: 1004263812614" (13 digits) and then
# concatenate the NRC code ("1004263812614JFEDMJLLW") elsewhere.
_PRESENTATION_ID_ANNUAL_RE = re.compile(
    r"N[úu]mero\s+de\s+justificante\s*[:\-]?\s*([0-9]{10,40})",
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
    """Parse the receipt timestamps AEAT stamps on justificantes.

    AEAT uses two shapes across the modelo corpus:

    * Quarterly / periodic modelos:
      ``YYYY-MM-DD HH:MM[:SS]`` (ISO-like, as printed in "Fecha y hora
      de presentación").
    * Annual modelos (100, 190, etc.):
      ``DD-MM-YYYY HH:MM[:SS]`` (as printed in "Presentación realizada
      el: DD-MM-YYYY a las HH:MM:SS" — this function accepts either
      a single whitespace-joined string or a 2-tuple produced by the
      extractor's regex groups).

    The timestamp is returned as a *naive* datetime because AEAT does
    not print a timezone; callers that need UTC must apply the known
    Europe/Madrid offset themselves.
    """
    normalised = raw.replace("T", " ").strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
    ):
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

    csv_match = (
        _CSV_AUTHENTICITY_FOOTER_RE.search(text)
        or _CSV_AUTHENTICITY_FOOTER_RE.search(normalised)
        or _CSV_LABEL_RE.search(text)
        or _CSV_LABEL_RE.search(normalised)
        or _CSV_LABEL_INVERTED_RE.search(text)
        or _CSV_LABEL_INVERTED_RE.search(normalised)
        or _CSV_FALLBACK_RE.search(normalised)
    )
    if csv_match is None:
        raise JustificanteCsvNotFoundError(f"no Código Seguro de Verificación found in {pdf_path}")
    csv_value = csv_match.group(1).upper()

    modelo = _require(_MODELO_RE.search(normalised), "modelo")
    ejercicio_match = _EJERCICIO_RE.search(normalised) or _EJERCICIO_LOOSE_RE.search(normalised)
    ejercicio = ejercicio_match.group(1).strip() if ejercicio_match else None

    # Period extraction has three tiers:
    #   1. Labelled "Período <token>" (Modelo 100 modern body, M303).
    #   2. Positional "[<NIF>] <YYYY> <token>" lines that pdfplumber
    #      reads in form-laid-out quarterly receipts (M130, M111, ...).
    #   3. Annual informativas / metadata-only receipts: fall back to
    #      the ejercicio so the schema's non-empty constraint holds.
    period_match = _PERIOD_RE.search(normalised)
    if period_match is not None:
        period = period_match.group(1).strip()
    else:
        positional_match = _PERIOD_POSITIONAL_RE.search(normalised)
        if positional_match is not None:
            period = positional_match.group("period").strip()
        elif ejercicio is not None:
            period = ejercicio
        else:
            raise JustificanteParseError("could not locate required field: period")

    nif = _require(_NIF_RE.search(normalised), "tax_id").upper()

    # Three timestamp shapes in the wild (see _parse_datetime docstring).
    presented_at: datetime
    presented_match = _PRESENTED_AT_RE.search(normalised)
    if presented_match is not None:
        presented_at = _parse_datetime(presented_match.group(1))
    else:
        annual_match = _PRESENTED_AT_ANNUAL_RE.search(normalised) or _PRESENTED_AT_ANNUAL_INVERTED_RE.search(normalised)
        if annual_match is None:
            raise JustificanteParseError("could not locate required field: presented_at")
        presented_at = _parse_datetime(f"{annual_match.group(1)} {annual_match.group(2)}")

    presentation_match = _PRESENTATION_ID_RE.search(normalised)
    if presentation_match is None:
        presentation_match = _PRESENTATION_ID_ANNUAL_RE.search(normalised)
    presentation_id = presentation_match.group(1).strip() if presentation_match else None

    ingresar_match = _TOTAL_INGRESAR_RE.search(normalised) or _NRC_IMPORTE_RE.search(normalised)
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
            ejercicio=ejercicio,
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
