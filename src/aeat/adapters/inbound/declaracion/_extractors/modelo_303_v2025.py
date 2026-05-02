"""Modelo 303 (autoliquidación IVA trimestral) declaración extractor.

Modelo 303 is the quarterly autoliquidación IVA covering VAT collected on
sales and paid on purchases. The runtime schema enumerates 33 casillas
spanning three apartados:

- **Apartado 1** — Régimen ordinario: 01-09 (base imponible, IVA, tipos
  impositivos, recargo de equivalencia).
- **Apartado 2** — Operaciones / actividades asimiladas: 28-43
  (autoconsumo, adquisiciones intracomunitarias, IVA soportado por tipo).
- **Apartado 3** — Resultado y sumas: 44, 45, 64-71 (cuota líquida,
  compensaciones, resultado).

The extractor uses a label-anchored regex primitive: each casilla has its
own line in the declaración's "Liquidación" block, prefixed by its ID and
followed by a Spanish-formatted amount. Two concrete extractors ship —
:class:`Modelo303V2025Extractor` for tax year 2025 and
:class:`Modelo303V2026Extractor` for 2026 — sharing the same form layout.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from ...pdf._label_regex import apply_label_regex, parse_spanish_decimal
from ...pdf._shared import ExtractedCasilla
from .._errors import DeclaracionParseError
from .._extractor import DeclaracionExtractor
from .._parsers import extract_pages_text
from .._schema import (
    DeclaracionFiling,
    ExtractionStatus,
    ExtractionWarning,
    TemplateRevision,
)

_SPANISH_AMOUNT_GROUP = r"(-?[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})"

_MODELO_303_CASILLAS: tuple[str, ...] = (
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "28",
    "29",
    "30",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "37",
    "38",
    "39",
    "40",
    "41",
    "42",
    "43",
    "44",
    "45",
    "64",
    "65",
    "66",
    "67",
    "69",
    "71",
)

_LABEL_REGEX_MAP: dict[str, re.Pattern[str]] = {
    casilla_id: re.compile(
        rf"(?m)^\s*{int(casilla_id):02d}\s[^\n]{{0,80}}?{_SPANISH_AMOUNT_GROUP}",
        re.IGNORECASE,
    )
    for casilla_id in _MODELO_303_CASILLAS
}

_REQUIRED_FOR_COMPLETE: frozenset[str] = frozenset(_MODELO_303_CASILLAS)

_TAX_ID_RE = re.compile(r"NIF\s*[:\-]?\s*([0-9A-Z]{8,12})", re.IGNORECASE)
_EJERCICIO_RE = re.compile(r"Ejercicio\s*[:\-]?\s*([0-9]{4})", re.IGNORECASE)
_PERIOD_RE = re.compile(r"Per[íi]odo\s*[:\-]?\s*([0-9A-Z]{1,8})", re.IGNORECASE)


class Modelo303V2025Extractor(DeclaracionExtractor):
    """Concrete extractor for Modelo 303 tax year 2025.

    Resolves the NIF, ejercicio, and período header fields, then walks
    every casilla in :data:`_MODELO_303_CASILLAS` via the shared
    label-anchored regex map.

    Attributes:
        template_revision: Identifier for this template version (modelo
            ``"303"``, año ``2025``, revision ``"2025.01"``).
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="303",
        año=2025,
        revision="2025.01",
    )

    def extract(self, pdf_path: Path) -> DeclaracionFiling:
        """Parse ``pdf_path`` into a strict :class:`DeclaracionFiling`.

        Args:
            pdf_path: Path to the Modelo 303 declaración PDF.

        Returns:
            A :class:`DeclaracionFiling` with the resolved casillas and
            any extraction warnings.

        Raises:
            :exc:`aeat.adapters.inbound.declaracion.DeclaracionParseError`:
                When required header fields (NIF, ejercicio, período)
                cannot be located.
        """
        pages = extract_pages_text(pdf_path)
        full_text = "\n".join(pages)

        tax_id = _require_match(_TAX_ID_RE, full_text, "tax_id (NIF)")
        ejercicio = _require_match(_EJERCICIO_RE, full_text, "ejercicio")
        period_raw = _require_match(_PERIOD_RE, full_text, "período")
        period = _canonical_period(ejercicio, period_raw)

        hits = apply_label_regex(full_text, _LABEL_REGEX_MAP)

        values: list[ExtractedCasilla] = []
        warnings: list[ExtractionWarning] = []
        for casilla_id in _MODELO_303_CASILLAS:
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

        status = _derive_status(values)

        return DeclaracionFiling(
            modelo="303",
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


def _require_match(pattern: re.Pattern[str], text: str, field: str) -> str:
    """Return the first capture group of ``pattern`` in ``text`` or raise."""
    match = pattern.search(text)
    if match is None:
        raise DeclaracionParseError(f"could not locate required field: {field}")
    return match.group(1).strip()


def _canonical_period(ejercicio: str, raw_period: str) -> str:
    """Return the canonical ``YYYY{Q,M,A}`` period for the printed token."""
    if re.fullmatch(r"[1-4]T", raw_period, re.IGNORECASE):
        return f"{ejercicio}Q{raw_period[0]}"
    if re.fullmatch(r"(0[1-9]|1[0-2])", raw_period):
        return f"{ejercicio}-{raw_period}"
    if raw_period.upper() == "0A":
        return f"{ejercicio}A"
    return raw_period


def _derive_status(values: list[ExtractedCasilla]) -> ExtractionStatus:
    """Derive the :class:`ExtractionStatus` from resolved casilla coverage."""
    resolved_ids = {v.casilla_id for v in values}
    if resolved_ids >= _REQUIRED_FOR_COMPLETE:
        return ExtractionStatus.COMPLETE
    coverage = len(resolved_ids) / max(len(_REQUIRED_FOR_COMPLETE), 1)
    if coverage >= 0.5:
        return ExtractionStatus.PARTIAL
    return ExtractionStatus.FAILED


def _sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 digest of the file at ``path``."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class Modelo303V2026Extractor(Modelo303V2025Extractor):
    """Modelo 303 v2026 extractor reusing the unchanged 2025 layout.

    Inherits the extraction logic from :class:`Modelo303V2025Extractor`
    and only overrides :attr:`template_revision`.

    Attributes:
        template_revision: Identifier (modelo ``"303"``, año ``2026``,
            revision ``"2026.01"``).
    """

    template_revision: ClassVar[TemplateRevision] = TemplateRevision(
        modelo="303",
        año=2026,
        revision="2026.01",
    )


__all__ = ["Modelo303V2025Extractor", "Modelo303V2026Extractor"]
