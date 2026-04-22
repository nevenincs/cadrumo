"""Modelo 130 v2025 declaración extractor.

Parses the AEAT-produced *copia de la declaración* for Modelo 130 tax
year 2025. Targets the label-anchored regex primitive (see
:mod:`aeat.declaracion._extract`) for all 7 casillas the current
runtime schema knows about (01, 02, 03, 04, 05, 06, 07).

The regex map below is curated to match both the AEAT's official
layout (Spanish labels printed in the form's left column) and the
synthetic-generator rendering under
``tests/fixtures/pdf_corpus/l3_synthetic/_generators/modelo_130_generator.py``.
Every label regex captures a single Spanish-formatted amount
(``1.234,56``) as group 1.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from ..._pdf_import._shared import ExtractedCasilla
from .._extract import apply_label_regex, parse_spanish_decimal
from .._extractor import DeclaracionExtractor
from .._parsers import extract_pages_text
from .._schema import (
    DeclaracionFiling,
    ExtractionStatus,
    ExtractionWarning,
    TemplateRevision,
)

_SPANISH_AMOUNT_GROUP = r"(-?[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})"

# Every casilla the Modelo 130 2025 schema enumerates. Order matters —
# the extractor attaches `source_page=1` to all hits and the validator
# presents them in this order.
_MODELO_130_CASILLAS: tuple[str, ...] = ("01", "02", "03", "04", "05", "06", "07")

_LABEL_REGEX_MAP: dict[str, re.Pattern[str]] = {
    casilla_id: re.compile(
        rf"(?m)^\s*0?{int(casilla_id)}\s[^\n]{{0,80}}?{_SPANISH_AMOUNT_GROUP}",
        re.IGNORECASE,
    )
    for casilla_id in _MODELO_130_CASILLAS
}

_REQUIRED_FOR_COMPLETE: frozenset[str] = frozenset(_MODELO_130_CASILLAS)

# Header-detection heuristics — tax id, ejercicio, período.
_TAX_ID_RE = re.compile(r"NIF\s*[:\-]?\s*([0-9A-Z]{8,12})", re.IGNORECASE)
_EJERCICIO_RE = re.compile(r"Ejercicio\s*[:\-]?\s*([0-9]{4})", re.IGNORECASE)
_PERIOD_RE = re.compile(r"Per[íi]odo\s*[:\-]?\s*([0-9A-Z]{1,8})", re.IGNORECASE)


class Modelo130V2025Extractor(DeclaracionExtractor):
    """Concrete extractor for Modelo 130 tax year 2025."""

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="130",
        año=2025,
        revision="2025.01",
    )

    def extract(self, pdf_path: Path) -> DeclaracionFiling:
        pages = extract_pages_text(pdf_path)
        full_text = "\n".join(pages)

        tax_id = _require_match(_TAX_ID_RE, full_text, "tax_id (NIF)")
        ejercicio = _require_match(_EJERCICIO_RE, full_text, "ejercicio")
        period_raw = _require_match(_PERIOD_RE, full_text, "período")
        period = _canonical_period(ejercicio, period_raw)

        hits = apply_label_regex(full_text, _LABEL_REGEX_MAP)

        values: list[ExtractedCasilla] = []
        warnings: list[ExtractionWarning] = []
        for casilla_id in _MODELO_130_CASILLAS:
            hit = hits.get(casilla_id)
            if hit is None:
                warnings.append(
                    ExtractionWarning(
                        casilla_id=casilla_id,
                        code="casilla-not-found",
                        message={
                            "es": f"Casilla {casilla_id}: no se ha encontrado el valor en el PDF.",
                            "en": f"Casilla {casilla_id}: value not found in the PDF.",
                            "hu": f"{casilla_id} casilla: érték nem található a PDF-ben.",
                        },
                        primitive_attempted="label_regex",
                    )
                )
                continue

            parsed = hit.decimal_value if hit.decimal_value is not None else parse_spanish_decimal(hit.raw_value)
            if parsed is None:
                warnings.append(
                    ExtractionWarning(
                        casilla_id=casilla_id,
                        code="value-unparseable",
                        message={
                            "es": f"Casilla {casilla_id}: el valor {hit.raw_value!r} no es numérico.",
                            "en": f"Casilla {casilla_id}: value {hit.raw_value!r} is not a number.",
                            "hu": f"{casilla_id} casilla: {hit.raw_value!r} érték nem szám.",
                        },
                        primitive_attempted="label_regex",
                    )
                )
                continue

            # Multi-match guard: if the label pattern hits > 1 time in
            # the text, extraction is ambiguous — first hit wins but we
            # drop confidence + emit a warning so the verification
            # classifier flags EXTRACTION_UNRELIABLE (audit H1).
            all_hits = _LABEL_REGEX_MAP[casilla_id].findall(full_text)
            confidence = 1.0
            if len(all_hits) > 1:
                confidence = 0.5
                warnings.append(
                    ExtractionWarning(
                        casilla_id=casilla_id,
                        code="ambiguous-label",
                        message={
                            "es": (
                                f"Casilla {casilla_id}: el patrón coincide {len(all_hits)} veces; se usa la primera."
                            ),
                            "en": (
                                f"Casilla {casilla_id}: label pattern matched "
                                f"{len(all_hits)} times; the first hit was used."
                            ),
                            "hu": (
                                f"{casilla_id} casilla: a minta {len(all_hits)} "
                                "helyen illeszkedik; az elsőt használjuk."
                            ),
                        },
                        primitive_attempted="label_regex",
                    )
                )

            values.append(
                ExtractedCasilla(
                    casilla_id=casilla_id,
                    printed_value=parsed,
                    source_page=1,
                    source_bbox=None,
                    extraction_confidence=confidence,
                )
            )

        # Structural integrity: casilla 03 = 01 - 02 (by Modelo 130 law).
        # Mismatch > 0.02 € → one of (01, 02, 03) was mis-extracted;
        # downgrade 03's confidence + emit ambiguous-label (audit H1).
        _structural_integrity_check_01_minus_02(values, warnings)

        status = _derive_status(values, warnings)

        return DeclaracionFiling(
            modelo="130",
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


def _structural_integrity_check_01_minus_02(
    values: list[ExtractedCasilla],
    warnings: list[ExtractionWarning],
) -> None:
    """Cross-check the 03 = 01 - 02 invariant; downgrade + warn on drift."""
    from decimal import Decimal

    by_id = {v.casilla_id: v for v in values}
    needed = {"01", "02", "03"}
    if not needed.issubset(by_id.keys()):
        return
    c01 = by_id["01"].printed_value
    c02 = by_id["02"].printed_value
    c03 = by_id["03"].printed_value
    if not all(isinstance(v, Decimal) for v in (c01, c02, c03)):
        return
    assert isinstance(c01, Decimal) and isinstance(c02, Decimal) and isinstance(c03, Decimal)
    if abs((c01 - c02) - c03) <= Decimal("0.02"):
        return
    # Structural drift — downgrade 03's confidence and warn.
    replacement = ExtractedCasilla(
        casilla_id="03",
        printed_value=c03,
        source_page=by_id["03"].source_page,
        source_bbox=by_id["03"].source_bbox,
        extraction_confidence=min(by_id["03"].extraction_confidence, 0.3),
    )
    for idx, existing in enumerate(values):
        if existing.casilla_id == "03":
            values[idx] = replacement
            break
    warnings.append(
        ExtractionWarning(
            casilla_id="03",
            code="ambiguous-label",
            message={
                "es": (f"Casilla 03: ruptura de integridad (01 - 02 = {c01 - c02} ≠ {c03})."),
                "en": (f"Casilla 03: structural integrity failed (01 - 02 = {c01 - c02} ≠ {c03})."),
                "hu": (f"03 casilla: strukturális ellentmondás (01 - 02 = {c01 - c02} ≠ {c03})."),
            },
            primitive_attempted="label_regex",
        )
    )


def _require_match(pattern: re.Pattern[str], text: str, field: str) -> str:
    """Return the first capturing-group match or raise a parse error."""
    from .._errors import DeclaracionParseError

    match = pattern.search(text)
    if match is None:
        raise DeclaracionParseError(f"could not locate required field: {field}")
    return match.group(1).strip()


def _canonical_period(ejercicio: str, raw_period: str) -> str:
    """Canonicalise the raw period token to ``YYYYQN`` where possible."""
    if re.fullmatch(r"[1-4]T", raw_period, re.IGNORECASE):
        return f"{ejercicio}Q{raw_period[0]}"
    if re.fullmatch(r"(0[1-9]|1[0-2])", raw_period):
        return f"{ejercicio}-{raw_period}"
    if raw_period.upper() == "0A":
        return f"{ejercicio}A"
    return raw_period


def _derive_status(
    values: list[ExtractedCasilla],
    warnings: list[ExtractionWarning],
) -> ExtractionStatus:
    # Aligned with GenericDeclaracionExtractor (#305 wave 18 H2): multi-hit
    # or structurally-downgraded casillas (confidence < 1.0) do NOT count
    # toward COMPLETE; they stay resolved for PARTIAL-coverage math only.
    resolved_ids = {v.casilla_id for v in values}
    reliable_ids = {v.casilla_id for v in values if v.extraction_confidence >= 1.0}
    required = _REQUIRED_FOR_COMPLETE
    if reliable_ids >= required:
        return ExtractionStatus.COMPLETE
    coverage = len(resolved_ids) / max(len(required), 1)
    if coverage >= 0.5:
        return ExtractionStatus.PARTIAL
    return ExtractionStatus.FAILED


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


__all__ = ["Modelo130V2025Extractor"]
