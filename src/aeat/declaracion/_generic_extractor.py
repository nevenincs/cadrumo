"""Generic quarterly-declaración extractor (EPIC #305 cluster D).

Every quarterly / monthly AEAT declaración the project supports shares
the same shape: an NIF + ejercicio + período header, then each casilla
as a line with its ID + label + a Spanish-formatted amount.
:class:`GenericDeclaracionExtractor` lets new modelos land as a
7-line subclass defining only the modelo, the template revision, and
the list of casilla IDs.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from .._pdf_import._label_regex import (
    SPANISH_AMOUNT_GROUP,
    apply_label_regex,
    parse_spanish_decimal,
)
from .._pdf_import._shared import ExtractedCasilla
from ._errors import DeclaracionParseError
from ._extractor import DeclaracionExtractor
from ._parsers import extract_pages_text
from ._schema import (
    DeclaracionFiling,
    ExtractionStatus,
    ExtractionWarning,
    TemplateRevision,
)

_TAX_ID_RE = re.compile(r"NIF\s*[:\-]?\s*([0-9A-Z]{8,12})", re.IGNORECASE)
_EJERCICIO_RE = re.compile(r"Ejercicio\s*[:\-]?\s*([0-9]{4})", re.IGNORECASE)
_PERIOD_RE = re.compile(r"Per[íi]odo\s*[:\-]?\s*([0-9A-Z]{1,8})", re.IGNORECASE)


class GenericDeclaracionExtractor(DeclaracionExtractor):
    """Line-anchored regex extractor shared across quarterly modelos.

    Subclasses declare:

    - ``template_revision``: one :class:`TemplateRevision` ClassVar.
    - ``casilla_ids``: ordered tuple of casilla IDs the modelo prints.
    - (optional) ``casilla_width``: width of the casilla-ID prefix
      ``{int(casilla_id):02d}`` by default (Modelo 100 overrides to 4).
    """

    template_revision: ClassVar[TemplateRevision]
    casilla_ids: ClassVar[tuple[str, ...]]
    casilla_width: ClassVar[int] = 2

    def _compiled_patterns(self) -> dict[str, re.Pattern[str]]:
        width = type(self).casilla_width
        return {
            casilla_id: re.compile(
                rf"(?m)^\s*{int(casilla_id):0{width}d}\s[^\n]{{0,80}}?{SPANISH_AMOUNT_GROUP}",
                re.IGNORECASE,
            )
            for casilla_id in type(self).casilla_ids
        }

    def extract(self, pdf_path: Path) -> DeclaracionFiling:
        pages = extract_pages_text(pdf_path)
        full_text = "\n".join(pages)

        tax_id = _require_match(_TAX_ID_RE, full_text, "tax_id (NIF)")
        ejercicio = _require_match(_EJERCICIO_RE, full_text, "ejercicio")
        period_raw = _require_match(_PERIOD_RE, full_text, "período")
        period = _canonical_period(ejercicio, period_raw)

        hits = apply_label_regex(full_text, self._compiled_patterns())

        values: list[ExtractedCasilla] = []
        warnings: list[ExtractionWarning] = []
        for casilla_id in type(self).casilla_ids:
            hit = hits.get(casilla_id)
            if hit is None:
                warnings.append(_not_found_warning(casilla_id))
                continue
            parsed = hit.decimal_value or parse_spanish_decimal(hit.raw_value)
            if parsed is None:
                warnings.append(_unparseable_warning(casilla_id, hit.raw_value))
                continue

            confidence = 0.5 if hit.match_count > 1 else 1.0
            if hit.match_count > 1:
                warnings.append(_ambiguous_warning(casilla_id, hit.match_count))

            values.append(
                ExtractedCasilla(
                    casilla_id=casilla_id,
                    printed_value=parsed,
                    source_page=1,
                    source_bbox=None,
                    extraction_confidence=confidence,
                )
            )

        status = _derive_status(values, tuple(type(self).casilla_ids))

        return DeclaracionFiling(
            modelo=type(self).template_revision.modelo,
            period=period,
            ejercicio=ejercicio,
            tax_id=tax_id.upper(),
            template_revision=type(self).template_revision,
            values=tuple(values),
            warnings=tuple(warnings),
            source_pdf_path=pdf_path.resolve(),
            source_pdf_sha256=_sha256_file(pdf_path),
            parsed_at=datetime.now(tz=UTC),
            extraction_status=status,
        )


def _not_found_warning(casilla_id: str) -> ExtractionWarning:
    return ExtractionWarning(
        casilla_id=casilla_id,
        code="casilla-not-found",
        message={
            "es": f"Casilla {casilla_id}: no se ha encontrado el valor en el PDF.",
            "en": f"Casilla {casilla_id}: value not found in the PDF.",
            "hu": f"{casilla_id} casilla: érték nem található a PDF-ben.",
        },
        primitive_attempted="label_regex",
    )


def _unparseable_warning(casilla_id: str, raw: str) -> ExtractionWarning:
    return ExtractionWarning(
        casilla_id=casilla_id,
        code="value-unparseable",
        message={
            "es": f"Casilla {casilla_id}: el valor {raw!r} no es numérico.",
            "en": f"Casilla {casilla_id}: value {raw!r} is not a number.",
            "hu": f"{casilla_id} casilla: {raw!r} érték nem szám.",
        },
        primitive_attempted="label_regex",
    )


def _ambiguous_warning(casilla_id: str, count: int) -> ExtractionWarning:
    return ExtractionWarning(
        casilla_id=casilla_id,
        code="ambiguous-label",
        message={
            "es": f"Casilla {casilla_id}: el patrón coincide {count} veces; se usa la primera.",
            "en": f"Casilla {casilla_id}: label pattern matched {count} times; the first hit was used.",
            "hu": f"{casilla_id} casilla: a minta {count} helyen illeszkedik; az elsőt használjuk.",
        },
        primitive_attempted="label_regex",
    )


def _require_match(pattern: re.Pattern[str], text: str, field: str) -> str:
    match = pattern.search(text)
    if match is None:
        raise DeclaracionParseError(f"could not locate required field: {field}")
    return match.group(1).strip()


def _canonical_period(ejercicio: str, raw_period: str) -> str:
    if re.fullmatch(r"[1-4]T", raw_period, re.IGNORECASE):
        return f"{ejercicio}Q{raw_period[0]}"
    if re.fullmatch(r"(0[1-9]|1[0-2])", raw_period):
        return f"{ejercicio}-{raw_period}"
    if raw_period.upper() == "0A":
        return f"{ejercicio}A"
    return raw_period


def _derive_status(
    values: list[ExtractedCasilla],
    required: tuple[str, ...],
) -> ExtractionStatus:
    resolved_ids = {v.casilla_id for v in values}
    required_set = set(required)
    # M1 closure: multi-hit casillas with confidence < 1 count as unresolved
    # for status-derivation purposes — the verification classifier still sees
    # them as EXTRACTION_UNRELIABLE, but the status downgrades accordingly.
    reliable_ids = {v.casilla_id for v in values if v.extraction_confidence >= 1.0}
    if reliable_ids >= required_set:
        return ExtractionStatus.COMPLETE
    coverage = len(resolved_ids) / max(len(required_set), 1)
    if coverage >= 0.5:
        return ExtractionStatus.PARTIAL
    return ExtractionStatus.FAILED


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


__all__ = ["GenericDeclaracionExtractor"]
