"""Regex-driven field extraction for AEAT justificante receipt PDFs.

This module translates the raw text of a justificante (as returned by one of
the backends in :mod:`adapters.inbound.justificante._parsers`) into a
:class:`~domain.justificante.Justificante` pydantic record. It extracts
receipt metadata only: CSV, modelo, period/ejercicio, taxpayer, presentation
timestamp, optional payment totals, and the verification URL. Casilla-level
filing values belong to the declaración/borrador adapters, not this receipt
surface.

The regex patterns deliberately accept both accented ("Código Seguro de
Verificación") and stripped ("Codigo Seguro de Verificacion") label variants
because AEAT's historical PDF corpus mixes the two depending on the year and
font embedding.

The extractor is **deterministic**: same input bytes produce the same output
record. All monetary values are parsed via :class:`decimal.Decimal` to
preserve the receipt precision; never floats. Parse failures populate the
structured attributes on
:class:`~domain.justificante.JustificanteParseError` so callers and tests
do not need to parse message strings.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from ....core.aeat_csv import is_aeat_csv, normalise_aeat_csv
from ....core.decimal._grammar import european_thousands_reading_is_ambiguous
from ....core.logging import get_logger
from ....core.period import Period, PeriodError
from ....core.text_fold import fold_diacritics
from ....core.time.clock import now
from ....domain.justificante import (
    Justificante,
    JustificanteCsvNotFoundError,
    JustificanteParseError,
)
from ..pdf._label_regex import EJERCICIO_LABEL, MODELO_LABEL, PRESENTADOR_NIF_LABEL, parse_spanish_decimal
from ..pdf._utils import sha256_file, source_pdf_reference_path

_logger = get_logger(__name__)
_ANY_HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


# Each tier captures a candidate at the canonical AEAT CSV width
# (:data:`core.AEAT_CSV_PATTERN`, 8..32 uppercase alphanumeric); the capture is
# then confirmed against :func:`core.is_aeat_csv` in :func:`_extract_csv`. The
# tiers previously stopped at 24, so a legitimately longer CSV was truncated
# to a wrong identifier or missed entirely.
_CSV_LABEL_RE = re.compile(
    r"C[óo]digo\s+Seguro\s+de\s+Verificaci[óo]n\s*[:\-]?\s*([A-Z0-9]{8,32})\b",
    re.IGNORECASE,
)
# Older AEAT layouts (Modelo 100 pre-2022) render labels on the right
# column and values on the left, so pdfplumber's top-down / left-right
# traversal emits VALUE then LABEL.
_CSV_LABEL_INVERTED_RE = re.compile(
    r"\b([A-Z0-9]{8,32})\s+C[óo]digo\s+Seguro\s+de\s+Verificaci[óo]n",
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
    r"de\s+Verificaci[óo]n\s+([A-Z0-9]{8,32})\b",
    re.IGNORECASE,
)
# AEAT also serves the receipt in English when the user files via
# the English-language sede UI. pdfplumber sees
# "Secure Verification Code: <csv>" in place of the Spanish label.
_CSV_LABEL_EN_RE = re.compile(
    r"Secure\s+Verification\s+Code\s*[:\-]?\s*([A-Z0-9]{8,32})\b",
    re.IGNORECASE,
)
# Used only as a last resort: the 'CSV' token is noisy in normalised
# text ("Presentador" includes the letter sequence), so we require a
# colon/dash separator and the 'CSV=' equality form.
_CSV_FALLBACK_RE = re.compile(r"\bCSV\s*[=:]\s*([A-Z0-9]{8,32})\b", re.IGNORECASE)

_MODELO_RE = re.compile(
    # Spanish "Modelo <N>" or English "Form <N>" (English-language
    # AEAT receipts use the latter). Both layouts also accept
    # uppercase ("MODELO <code>" / "FORM <code>"). The label alternation is
    # shared with the declaración adapter, which parses the same receipts.
    rf"{MODELO_LABEL}\s*[:\-]?\s*([0-9]{{3}}[A-Z]?)",
    re.IGNORECASE,
)

# Spanish period tokens always contain at least one digit (``1T``,
# ``0A``, ``4T``, ``2023``). Requiring a digit in the captured group
# stops the regex from picking up nearby words like "impositivo" out
# of "Período impositivo".
_PERIOD_RE = re.compile(r"Per[íi]odo\s*[:\-]?\s*([0-9A-Z]*\d[0-9A-Z]*)", re.IGNORECASE)
# Quarterly modelos often print the period
# in a positional layout that pdfplumber merges as
# ``[<NIF>] <YYYY> <period>`` on a single line, with no "Período"
# label.
#
# The period token must be either ``0A`` (annual) or ``[1-4]T``
# (quarterly). The earlier ``0[1-9]|1[0-2]`` monthly alternation
# was over-broad — pdfplumber emits ``Ejercicio (con 4 cifras)
# ....... 2024 01`` on M190 *Resumen anual* receipts, where the
# trailing ``01`` is a casilla number, not a monthly period. The
# annual fallback to ``ejercicio`` then mislabelled the row.
# Drop monthly until a real monthly modelo enters the corpus and
# we have a layout to validate against.
_PERIOD_POSITIONAL_RE = re.compile(
    r"(?:[A-Z][0-9A-Z]{7,9}\s+)?"  # optional NIF/NIE prefix
    r"\b(?P<year>\d{4})\s+"
    r"(?P<period>0A|[1-4]T)\b",
)
_EJERCICIO_RE = re.compile(
    # Spanish "Ejercicio <year>" or English "Financial year <year>"
    # (English-language M390/2021 captured live).
    rf"{EJERCICIO_LABEL}\s*[:\-]?\s*([0-9]{{4}})",
    re.IGNORECASE,
)
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
# Some annual receipts print only the ejercicio and omit a separate period
# label. The parser preserves the observed year in that case; application
# import/reconciliation code performs canonical period conversion.
_NIF_RE = re.compile(
    # Spanish tax-id shape: a natural-person NIF/NIE or a legal-entity CIF,
    # all represented as one leading letter/digit, seven digits, and a final
    # letter or digit. Total length is nine characters in practice.
    # The shape constraint excludes the word "PRESENTADOR" that the
    # ``NIF Presentador: <value>`` register-printed shape places after
    # the label.
    rf"{PRESENTADOR_NIF_LABEL}\s*[:\-]?\s*([A-Z\d]\d{{7}}[A-Z\d])",
    re.IGNORECASE,
)
# Legacy 2021 modelos (iText 2.1.4 producer) print value-then-label
# in column-split layout, so the NIF value precedes the
# ``NIF Presentador:`` label after pdfplumber's left-right
# traversal. The label alternation (Spanish or English render) is shared
# with the declaración adapter, which parses the same receipt family.
_NIF_INVERTED_RE = re.compile(
    rf"\b([A-Z\d]\d{{7}}[A-Z\d])\s+{PRESENTADOR_NIF_LABEL}\s*[:\-]?",
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
# both orderings.
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
# English-language receipts: "Filed on DD-MM-YYYY at HH:MM:SS".
_PRESENTED_AT_EN_RE = re.compile(
    r"Filed\s+on\s*[:\-]?\s*"
    r"(\d{2}-\d{2}-\d{4})\s+at\s+(\d{2}:\d{2}(?::\d{2})?)",
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
# "Total a ingresar" wording).
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
    return fold_diacritics(value)


def _parse_decimal(raw: str, field: str | None = None) -> Decimal:
    r"""Parse an AEAT-formatted decimal string (``1.234,56`` or ``1234.56``).

    Args:
        raw: Raw numeric substring captured from the PDF.
        field: Optional field name to populate ``malformed`` on the raised error.

    Returns:
        A :class:`decimal.Decimal` preserving the printed precision.

    Raises:
        JustificanteParseError: If the string is not a recognisable number, or
            if it carries a dot that could equally mean thousands or decimals.
            When ``field`` is supplied, ``malformed=(field,)`` is set on the
            exception so callers can assert on the structured attribute.

    The receipt's amount regexes capture ``([0-9][0-9\\.,]*)`` and so, unlike
    :data:`~adapters.inbound.pdf.SPANISH_AMOUNT_GROUP`, do not require the
    ``,NN`` tail that makes a printed Spanish amount unambiguous. A bare
    ``1.234`` reaching :func:`~adapters.inbound.pdf.parse_spanish_decimal`
    decodes as one point two three four, so a receipt total of one thousand two
    hundred thirty-four would be recorded a thousandfold small. AEAT prints the
    tail on money, so refusing the ambiguous shape rejects nothing a real
    receipt carries -- and a justificante total is filing evidence, where a hard
    refusal the operator can act on beats a plausible wrong number.
    """
    if european_thousands_reading_is_ambiguous(raw.strip()):
        malformed = (field,) if field is not None else ()
        raise JustificanteParseError(
            f"ambiguous thousands-or-decimal reading: {raw!r}",
            malformed=malformed,
        )
    parsed = parse_spanish_decimal(raw)
    if parsed is None:
        malformed = (field,) if field is not None else ()
        raise JustificanteParseError(
            f"invalid decimal literal: {raw!r}",
            malformed=malformed,
        )
    return parsed


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
        except ValueError as fmt_exc:
            _logger.debug(
                "justificante extract: datetime format %r did not match %r (%s); trying next",
                fmt,
                normalised,
                fmt_exc,
            )
            continue
    raise JustificanteParseError(f"unrecognised datetime literal: {raw!r}", malformed=("presented_at",))


def _require(match: re.Match[str] | None, field: str) -> str:
    """Return ``match.group(1)`` or raise a parse error naming ``field``.

    The raised :exc:`JustificanteParseError` has ``missing=(field,)`` set so
    callers can assert on the structured attribute rather than the message string.
    """
    if match is None:
        raise JustificanteParseError(f"could not locate required field: {field}", missing=(field,))
    return _match_group_text(match, 1, field)


def _match_group_text(match: re.Match[str], group: int | str, field: str) -> str:
    """Return a regex capture as text, refusing an ill-typed parser result."""
    value = match.group(group)
    if not isinstance(value, str):
        raise JustificanteParseError(
            f"regex capture for {field} did not contain text",
            malformed=(field,),
        )
    return value.strip()


def extract_justificante(text: str, pdf_path: Path) -> Justificante:
    """Extract a :class:`Justificante` from the raw text of a receipt PDF.

    This path-based helper computes the PDF digest itself before delegating to
    ``extract_justificante_from_digest``.

    Args:
        text: Full concatenated text returned by a parser backend.
        pdf_path: Path of the source PDF (used to compute the
            privacy-preserving ``source_pdf_path`` reference and sha-256
            digest).

    Returns:
        A fully populated :class:`Justificante` record.

    Raises:
        JustificanteParseError: If any required field is missing or cannot be
            coerced into its target type.
    """
    sha256 = sha256_file(pdf_path)
    return extract_justificante_from_digest(
        text,
        source_pdf_sha256=sha256,
        source_label=pdf_path,
    )


def extract_justificante_from_digest(
    text: str,
    *,
    source_pdf_sha256: str,
    source_label: object = "<input-pdf>",
) -> Justificante:
    """Extract a :class:`Justificante` when the caller already has the PDF digest.

    The digest is converted into the persisted ``source_pdf_path`` reference, so
    callers that parse bytes from secure storage can retain provenance without
    writing those bytes to disk.

    Raises:
        JustificanteParseError: If receipt text is empty, a required field is
            missing, a captured value is malformed, or the final strict record
            fails validation.
    """
    if not text.strip():
        raise JustificanteParseError(f"empty text extracted from {source_label}", missing=("text",))
    normalised = _strip_accents(text)
    csv_value = _extract_csv(text, normalised, source_label)
    modelo = _require(_MODELO_RE.search(normalised), "modelo")
    period, ejercicio = _extract_period_and_ejercicio(normalised)
    if ejercicio is None or not ejercicio.isdigit():
        raise JustificanteParseError(
            f"could not resolve a filing year for period {period!r} in {source_label}",
            missing=("ejercicio",),
        )
    try:
        typed_period = Period.from_year_and_code(int(ejercicio), period)
    except PeriodError as exc:
        raise JustificanteParseError(
            f"invalid filing period {period!r} for ejercicio {ejercicio!r} in {source_label}",
            malformed=("period",),
        ) from exc
    nif_match = _NIF_RE.search(normalised) or _NIF_INVERTED_RE.search(normalised)
    nif = _require(nif_match, "tax_id").upper()
    presented_at = _extract_presented_at(normalised)
    presentation_id = _extract_presentation_id(normalised)
    total_ingresar, total_devolver = _extract_totals(normalised)
    verification_url = _extract_verification_url(text, source_label)
    source_pdf_path = source_pdf_reference_path(source_pdf_sha256)
    parsed_at = now()
    try:
        record = Justificante(
            csv=csv_value,
            modelo=modelo,
            period=typed_period,
            ejercicio=ejercicio,
            presentation_id=presentation_id,
            presented_at=presented_at,
            tax_id=nif,
            total_a_ingresar=total_ingresar,
            total_a_devolver=total_devolver,
            verification_url=verification_url,
            source_pdf_path=source_pdf_path,
            source_pdf_sha256=source_pdf_sha256,
            parsed_at=parsed_at,
        )
    except ValidationError as exc:
        raise JustificanteParseError(
            f"failed to validate Justificante for {source_label}: {exc}",
            malformed=("record",),
        ) from exc
    _logger.info(
        "extract_justificante: parsed modelo=%s period=%s ejercicio=%s csv=%s",
        modelo,
        period,
        ejercicio,
        csv_value,
    )
    return record


def _extract_csv(text: str, normalised: str, source_label: object) -> str:
    """Locate the Código Seguro de Verificación across the five regex tiers."""
    csv_match = (
        _CSV_AUTHENTICITY_FOOTER_RE.search(text)
        or _CSV_AUTHENTICITY_FOOTER_RE.search(normalised)
        or _CSV_LABEL_RE.search(text)
        or _CSV_LABEL_RE.search(normalised)
        or _CSV_LABEL_INVERTED_RE.search(text)
        or _CSV_LABEL_INVERTED_RE.search(normalised)
        or _CSV_LABEL_EN_RE.search(text)
        or _CSV_LABEL_EN_RE.search(normalised)
        or _CSV_FALLBACK_RE.search(normalised)
    )
    if csv_match is None:
        raise JustificanteCsvNotFoundError(f"no Código Seguro de Verificación found in {source_label}")
    csv = normalise_aeat_csv(csv_match.group(1))
    if not is_aeat_csv(csv):
        raise JustificanteCsvNotFoundError(
            f"Código Seguro de Verificación {csv!r} in {source_label} does not match the AEAT shape",
        )
    return csv


def _extract_period_and_ejercicio(normalised: str) -> tuple[str, str | None]:
    """Resolve the (period, ejercicio) pair from four regex tiers.

    1. Labelled "Período <token>" (Modelo 100 modern body, M303).
    2. Positional "[<NIF>] <YYYY> <token>" lines that pdfplumber reads
       in form-laid-out quarterly receipts.
    3. Anything else with an ejercicio: resolve the annual filing token
       ``0A``.
    4. Anything without period or ejercicio fails hard.
    """
    ejercicio_match = _EJERCICIO_RE.search(normalised) or _EJERCICIO_LOOSE_RE.search(normalised)
    ejercicio = _match_group_text(ejercicio_match, 1, "ejercicio") if ejercicio_match else None
    period_match = _PERIOD_RE.search(normalised)
    if period_match is not None:
        return _match_group_text(period_match, 1, "period"), ejercicio
    positional_match = _PERIOD_POSITIONAL_RE.search(normalised)
    if positional_match is not None:
        period = _match_group_text(positional_match, "period", "period")
        # Quarterly modelos older than 2024 print only the positional
        # ``Y0000001S 2022 4T`` line — there is no labelled
        # ``Ejercicio 2022``. Promote the year captured by the
        # positional regex when the labelled extractors found nothing,
        # so downstream code (and the deep-extractor binding) sees a
        # populated year.
        if ejercicio is None:
            ejercicio = _match_group_text(positional_match, "year", "ejercicio")
        return period, ejercicio
    if ejercicio is not None:
        return "0A", ejercicio
    raise JustificanteParseError("could not locate required field: period", missing=("period",))


def _extract_presented_at(normalised: str) -> datetime:
    """Resolve the presentation timestamp from one of three regex shapes."""
    presented_match = _PRESENTED_AT_RE.search(normalised)
    if presented_match is not None:
        return _parse_datetime(presented_match.group(1))
    annual_match = (
        _PRESENTED_AT_ANNUAL_RE.search(normalised)
        or _PRESENTED_AT_ANNUAL_INVERTED_RE.search(normalised)
        or _PRESENTED_AT_EN_RE.search(normalised)
    )
    if annual_match is None:
        raise JustificanteParseError("could not locate required field: presented_at", missing=("presented_at",))
    return _parse_datetime(f"{annual_match.group(1)} {annual_match.group(2)}")


def _extract_presentation_id(normalised: str) -> str | None:
    """Optional presentation identifier; either standard or annual regex shape."""
    presentation_match = _PRESENTATION_ID_RE.search(normalised) or _PRESENTATION_ID_ANNUAL_RE.search(normalised)
    return _match_group_text(presentation_match, 1, "presentation_id") if presentation_match else None


def _extract_totals(normalised: str) -> tuple[Decimal | None, Decimal | None]:
    """Resolve the (total_a_ingresar, total_a_devolver) pair from regex matches."""
    ingresar_match = _TOTAL_INGRESAR_RE.search(normalised) or _NRC_IMPORTE_RE.search(normalised)
    total_ingresar: Decimal | None = _parse_decimal(ingresar_match.group(1)) if ingresar_match else None
    devolver_match = _TOTAL_DEVOLVER_RE.search(normalised)
    total_devolver: Decimal | None = _parse_decimal(devolver_match.group(1)) if devolver_match else None
    return total_ingresar, total_devolver


def _extract_verification_url(text: str, source_label: object) -> AnyHttpUrl:
    """Locate the verification URL and validate it as an AnyHttpUrl."""
    url_match = _URL_RE.search(text)
    if url_match is None:
        raise JustificanteParseError(f"no verification URL found in {source_label}", missing=("verification_url",))
    verification_url_raw = url_match.group(0).rstrip(".,);")
    try:
        # CAST-RATIONALE-JUSTIFICANTE-EXTRACT-TYPEADAPTER: pydantic's
        # TypeAdapter.validate_python() is typed as returning Any in pydantic's
        # public stubs; the caller constrains the return to AnyHttpUrl via the
        # function's own -> AnyHttpUrl annotation.  The PDF text-extraction
        # boundary does not permit a narrower construction without an explicit
        # cast that would add noise without safety benefit.
        return _ANY_HTTP_URL_ADAPTER.validate_python(verification_url_raw)
    except ValidationError as exc:
        raise JustificanteParseError(
            f"invalid verification URL in {source_label}: {verification_url_raw!r}",
            malformed=("verification_url",),
        ) from exc
