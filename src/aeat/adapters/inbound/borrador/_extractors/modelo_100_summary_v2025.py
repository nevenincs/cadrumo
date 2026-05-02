"""Modelo 100 (IRPF / Renta) summary-block extractor for año 2025.

Targets the ~30 casillas every Renta artefact prints in its summary
block (ingresos totales, deducciones, base imponible, cuota líquida,
cuota diferencial). Full anexo coverage (A, B, C, D, H, Ñ) is out of
scope.

Casilla IDs are the AEAT-published Modelo 100 identifiers; the
extractor uses a narrow slice that every life shape encounters. The
concrete extractor is :class:`Modelo100SummaryV2025Extractor` and is
registered by :mod:`aeat.adapters.inbound.borrador._extractors`.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

from ...pdf._label_regex import SPANISH_AMOUNT_GROUP, apply_label_regex
from ...pdf._shared import ExtractedCasilla
from .._errors import BorradorParseError
from .._parsers import extract_pages_text
from .._schema import ArtefactKind, BorradorFiling

# Summary-block casilla IDs — narrow MVP subset; see the AEAT Modelo 100
# 2024 instruction manual chapter "Liquidación. Resultado".
_SUMMARY_CASILLAS: tuple[str, ...] = (
    # Rendimientos netos.
    "0022",  # Rendimiento neto rendimientos del trabajo
    "0049",  # Rendimiento neto capital mobiliario
    "0107",  # Rendimiento neto capital inmobiliario
    "0175",  # Rendimiento neto actividades económicas (estimación directa)
    # Ganancias y pérdidas patrimoniales.
    "0400",  # Ganancia o pérdida patrimonial total
    # Base imponible general + del ahorro.
    "0435",  # Base imponible general
    "0460",  # Base imponible del ahorro
    # Mínimo personal + familiar.
    "0500",  # Mínimo personal y familiar
    "0505",  # Mínimo del contribuyente
    "0510",  # Mínimo por descendientes
    "0515",  # Mínimo por ascendientes
    "0520",  # Mínimo por discapacidad
    # Base liquidable.
    "0545",  # Base liquidable general
    "0555",  # Base liquidable del ahorro
    # Cuota íntegra.
    "0550",  # Cuota íntegra general estatal
    "0551",  # Cuota íntegra general autonómica
    "0560",  # Cuota íntegra del ahorro estatal
    "0561",  # Cuota íntegra del ahorro autonómica
    "0595",  # Cuota íntegra total (estatal + autonómica)
    # Deducciones.
    "0620",  # Deducciones estatales
    "0622",  # Deducciones autonómicas
    "0630",  # Total deducciones
    # Cuota líquida.
    "0698",  # Cuota líquida total
    # Retenciones / pagos a cuenta.
    "0699",  # Retenciones e ingresos a cuenta
    "0700",  # Pagos fraccionados (incluido Modelo 130)
    # Resultado.
    "0720",  # Cuota resultante de la autoliquidación
    "0721",  # Resultado a ingresar / a devolver
)

_LABEL_REGEX_MAP: dict[str, re.Pattern[str]] = {
    casilla_id: re.compile(
        rf"(?m)^\s*{casilla_id}\s[^\n]{{0,120}}?{SPANISH_AMOUNT_GROUP}",
        re.IGNORECASE,
    )
    for casilla_id in _SUMMARY_CASILLAS
}

_NIF_RE = re.compile(r"NIF\s*[:\-]?\s*([0-9A-Z]{8,12})", re.IGNORECASE)
_EJERCICIO_RE = re.compile(r"Ejercicio\s*[:\-]?\s*([0-9]{4})", re.IGNORECASE)
_CSV_RE = re.compile(
    r"C[óo]digo\s+Seguro\s+de\s+Verificaci[óo]n\s*[:\-]?\s*([A-Z0-9]{8,24})",
    re.IGNORECASE,
)


class Modelo100SummaryV2025Extractor:
    """Concrete Modelo 100 summary-block extractor for año 2025.

    Reads the printed text via :func:`extract_pages_text`, locates the
    summary-block casillas with :func:`apply_label_regex`, and returns a
    strict :class:`~aeat.adapters.inbound.borrador._schema.BorradorFiling`.

    Attributes:
        año: The tax year this extractor targets.
    """

    año: ClassVar[int] = 2025

    def extract(self, pdf_path: Path, artefact_kind: ArtefactKind) -> BorradorFiling:
        """Parse ``pdf_path`` into a :class:`~aeat.adapters.inbound.borrador._schema.BorradorFiling`.

        Args:
            pdf_path: Path to the Modelo 100 PDF.
            artefact_kind: The artefact kind discovered by
                :func:`aeat.adapters.inbound.borrador._detect.detect_artefact_kind`
                (or supplied by the caller as an override).

        Returns:
            The strict :class:`~aeat.adapters.inbound.borrador._schema.BorradorFiling`
            with summary-block casillas extracted.

        Raises:
            :exc:`aeat.adapters.inbound.borrador._errors.BorradorParseError`:
                When required header fields are missing, or when a
                ``DECLARACION`` artefact lacks a CSV stamp.
        """
        pages = extract_pages_text(pdf_path)
        text = "\n".join(pages)

        tax_id = _require_match(_NIF_RE, text, "tax_id (NIF)")
        ejercicio = _require_match(_EJERCICIO_RE, text, "ejercicio")

        csv_match = _CSV_RE.search(text)
        csv_value = csv_match.group(1).upper() if csv_match else None
        if artefact_kind is ArtefactKind.DECLARACION and csv_value is None:
            raise BorradorParseError("DECLARACION artefact must carry a CSV stamp but none was found")

        hits = apply_label_regex(text, _LABEL_REGEX_MAP)

        values: list[ExtractedCasilla] = []
        warnings: list[str] = []
        for casilla_id in _SUMMARY_CASILLAS:
            hit = hits.get(casilla_id)
            if hit is None:
                continue
            if not isinstance(hit.decimal_value, Decimal):
                # Audit M2: surface unparseable values as warnings instead
                # of silently dropping them, matching the Modelo 303 path.
                warnings.append(f"casilla {casilla_id}: value {hit.raw_value!r} is not a number")
                continue
            values.append(
                ExtractedCasilla(
                    casilla_id=casilla_id,
                    printed_value=hit.decimal_value,
                    source_page=1,
                    source_bbox=None,
                    extraction_confidence=1.0,
                )
            )

        return BorradorFiling(
            modelo="100",
            ejercicio=ejercicio,
            tax_id=tax_id.upper(),
            artefact_kind=artefact_kind,
            values=tuple(values),
            source_pdf_path=pdf_path.resolve(),
            source_pdf_sha256=_sha256_file(pdf_path),
            parsed_at=datetime.now(tz=UTC),
            csv=csv_value,
            warnings=tuple(warnings),
        )


def _require_match(pattern: re.Pattern[str], text: str, field: str) -> str:
    """Return the first capturing-group match or raise a parse error."""
    match = pattern.search(text)
    if match is None:
        raise BorradorParseError(f"could not locate required field: {field}")
    return match.group(1).strip()


def _sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 of the file at ``path``."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


__all__ = ["_SUMMARY_CASILLAS", "Modelo100SummaryV2025Extractor"]
