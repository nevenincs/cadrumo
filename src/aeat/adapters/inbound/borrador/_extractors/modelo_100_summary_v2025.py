"""Modelo 100 (IRPF / Renta) observed-value extractor for año 2025.

The extractor reads printed casilla/value rows from a Renta artefact.
It does not define Modelo 100 completeness or filing-grade authority.
When callers pass a registry extraction profile, the parser filters to
that profile and fails hard if the observed coverage is insufficient.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

from .....core import Modelo
from .....core.time import now
from .....domain.calculations.registry import CasillaId, validated_casilla_id
from ...pdf._label_regex import SPANISH_AMOUNT_GROUP, parse_spanish_decimal
from ...pdf._shared import ExtractedCasilla
from ...pdf._utils import sha256_file, source_pdf_reference_path
from .._errors import BorradorParseError
from .._parsers import extract_pages_text
from .._schema import ArtefactKind, BorradorExtractionProfile, BorradorObservation

_CASILLA_VALUE_RE = re.compile(
    rf"(?m)^\s*(?P<casilla_id>[0-9]{{4}})\s[^\n]{{0,160}}?{SPANISH_AMOUNT_GROUP}",
    re.IGNORECASE,
)

_NIF_RE = re.compile(r"NIF\s*[:\-]?\s*([0-9A-Z]{8,12})", re.IGNORECASE)
_EJERCICIO_RE = re.compile(r"Ejercicio\s*[:\-]?\s*([0-9]{4})", re.IGNORECASE)
_CSV_RE = re.compile(
    r"C[óo]digo\s+Seguro\s+de\s+Verificaci[óo]n\s*[:\-]?\s*([A-Z0-9]{8,24})",
    re.IGNORECASE,
)


class Modelo100ObservedV2025Extractor:
    """Concrete Modelo 100 observed-value extractor for año 2025.

    Reads the printed text via ``extract_pages_text``, locates
    printed casilla rows, and returns a
    strict :class:`~aeat.adapters.inbound.borrador._schema.BorradorObservation`.

    Attributes:
        año: The tax year this extractor targets.
    """

    año: ClassVar[int] = 2025

    def extract(
        self,
        pdf_path: Path,
        artefact_kind: ArtefactKind,
        extraction_profile: BorradorExtractionProfile | None = None,
    ) -> BorradorObservation:
        """Parse ``pdf_path`` into a :class:`~aeat.adapters.inbound.borrador._schema.BorradorObservation`.

        Args:
            pdf_path: Path to the Modelo 100 PDF.
            artefact_kind: The artefact kind discovered by
                :func:`aeat.adapters.inbound.borrador._detect.detect_artefact_kind`
                (or supplied by the caller as an override).
            extraction_profile: Optional registry profile that declares
                target casillas and minimum coverage for this parse.

        Returns:
            The strict :class:`~aeat.adapters.inbound.borrador._schema.BorradorObservation`
            with observed casillas extracted.

        Raises:
            BorradorParseError: When required header fields are missing, or when a
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

        observed, warnings = _observed_values(text)
        target_casilla_ids = {t.casilla_id for t in extraction_profile.target_casillas} if extraction_profile else None
        values: list[ExtractedCasilla] = []
        matched_targets: set[CasillaId] = set()
        for casilla_id, value in sorted(observed.items()):
            if target_casilla_ids is not None and casilla_id not in target_casilla_ids:
                continue
            matched_targets.add(casilla_id)
            values.append(
                ExtractedCasilla(
                    casilla_id=casilla_id,
                    printed_value=value,
                    source_page=1,
                    source_bbox=None,
                    extraction_confidence=1.0,
                ),
            )

        coverage: Decimal | None = None
        if extraction_profile is not None:
            coverage = Decimal(len(matched_targets)) / Decimal(len(extraction_profile.target_casillas))
            if coverage < extraction_profile.min_coverage:
                missing_ids = tuple(sorted(target_casilla_ids - matched_targets if target_casilla_ids else set()))
                raise BorradorParseError(
                    "registry extraction profile coverage below minimum: "
                    f"profile={extraction_profile.id!r} coverage={coverage} "
                    f"minimum={extraction_profile.min_coverage} missing={list(missing_ids)!r}",
                    missing=missing_ids,
                    coverage=coverage,
                )

        source_pdf_sha256 = sha256_file(pdf_path)
        return BorradorObservation(
            modelo=Modelo.M100,
            ejercicio=ejercicio,
            tax_id=tax_id.upper(),
            artefact_kind=artefact_kind,
            values=tuple(values),
            registry_extraction_profile_id=extraction_profile.id if extraction_profile else None,
            extraction_coverage=coverage,
            source_pdf_path=source_pdf_reference_path(source_pdf_sha256),
            source_pdf_sha256=source_pdf_sha256,
            parsed_at=now(),
            csv=csv_value,
            warnings=tuple(warnings),
        )


def _observed_values(text: str) -> tuple[dict[CasillaId, Decimal], list[str]]:
    observed: dict[CasillaId, Decimal] = {}
    warnings: list[str] = []
    for match in _CASILLA_VALUE_RE.finditer(text):
        casilla_id = validated_casilla_id(
            match.group("casilla_id"),
            surface="Modelo 100 borrador observed casilla id",
        )
        if casilla_id in observed:
            warnings.append(f"casilla {casilla_id}: duplicate printed value ignored")
            continue
        raw_value = match.group(2)
        value = parse_spanish_decimal(raw_value)
        if value is None:
            warnings.append(f"casilla {casilla_id}: value {raw_value!r} is not a number")
            continue
        observed[casilla_id] = value
    return observed, warnings


def _require_match(pattern: re.Pattern[str], text: str, field: str) -> str:
    """Return the first capturing-group match or raise a parse error."""
    match = pattern.search(text)
    if match is None:
        raise BorradorParseError(f"could not locate required field: {field}")
    return match.group(1).strip()


__all__ = ["Modelo100ObservedV2025Extractor"]
