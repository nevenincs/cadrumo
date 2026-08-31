"""Modelo 100 (IRPF / Renta) observed-value extractor implementation.

The extractor reads printed casilla/value rows from a Renta artefact using the
year-stable ``NNNN label amount`` grammar used by the supported 2021-2025
extractor registrations and exercised by the checked 2021-2023 fixture PDFs
plus the generated 2025 parser tests. The class name records the original 2025
implementation point, but :mod:`adapters.inbound.borrador._extractors`
deliberately maps every supported year to this implementation while the observed
row grammar remains stable.

This is a read-only inbound adapter. It does not define Modelo 100
completeness, resolve a
:class:`~domain.calculations.registry.RegistrySnapshot`, or make
filing-grade authority decisions. When callers pass a
:class:`~adapters.inbound.borrador._schema.BorradorExtractionProfile`, the
extractor filters to that profile and fails hard if observed coverage is
insufficient.

Rows are extracted from the concatenated text stream, so
:class:`~adapters.inbound.pdf.ExtractedCasilla` records preserve the
printed value and confidence but do not capture per-row bounding boxes.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

from .....core.aeat_csv import normalise_aeat_csv
from .....core.modelo import Modelo
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.time.clock import now
from ...pdf import (
    SPANISH_AMOUNT_GROUP,
    ExtractedCasilla,
    parse_spanish_decimal,
    sha256_file,
    source_pdf_reference_path,
)
from .._parsers._pdfplumber_backend import extract_pages_text
from .._schema import ArtefactKind, BorradorExtractionProfile, InboundBorradorObservation
from ..errors import BorradorParseError

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
    """Concrete Modelo 100 observed-value extractor implementation.

    Reads the printed text via the backend facade's ``extract_pages_text``
    primitive, locates printed casilla rows, and returns a strict
    :class:`~adapters.inbound.borrador._schema.InboundBorradorObservation`.

    Attributes:
        año: The original implementation year. The extractor registry may map
            additional years to this class while the observed row grammar stays
            compatible.
    """

    año: ClassVar[int] = 2025

    def extract(
        self,
        pdf_path: Path,
        artefact_kind: ArtefactKind,
        extraction_profile: BorradorExtractionProfile | None = None,
    ) -> InboundBorradorObservation:
        """Parse ``pdf_path`` into a :class:`~adapters.inbound.borrador._schema.InboundBorradorObservation`.

        Args:
            pdf_path: Path to the Modelo 100 PDF.
            artefact_kind: The artefact kind discovered by
                :func:`~adapters.inbound.borrador._detect.detect_artefact_kind`
                (or supplied by the caller as an override).
            extraction_profile: Optional caller-supplied registry-profile
                projection that declares target casillas and minimum coverage
                for this parse.

        Returns:
            The strict :class:`~adapters.inbound.borrador._schema.InboundBorradorObservation`
            with observed casillas extracted.

        Raises:
            BorradorParseError: When required header fields are missing, when a
                ``DECLARACION`` artefact lacks a CSV stamp, or when a supplied
                registry-profile projection does not meet its minimum coverage.
        """
        pages = extract_pages_text(pdf_path)
        text = "\n".join(pages)

        tax_id = _require_match(_NIF_RE, text, "tax_id (NIF)")
        ejercicio = _require_match(_EJERCICIO_RE, text, "ejercicio")

        csv_match = _CSV_RE.search(text)
        csv_value = normalise_aeat_csv(csv_match.group(1)) if csv_match else None
        if artefact_kind is ArtefactKind.DECLARACION and csv_value is None:
            raise BorradorParseError("DECLARACION artefact must carry a CSV stamp but none was found")
        if artefact_kind is not ArtefactKind.DECLARACION:
            csv_value = None

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
        return InboundBorradorObservation(
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
    """Extract first-seen four-digit casilla amount rows from ``text``.

    Duplicate casilla IDs and unparseable values are advisory warnings, not
    immediate parse failures. Coverage-sensitive callers get hard failures later
    when the filtered observed set is compared with the supplied extraction
    profile.
    """
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
    """Return the first capturing-group match or raise :class:`BorradorParseError`."""
    match = pattern.search(text)
    if match is None:
        raise BorradorParseError(f"could not locate required field: {field}")
    captured = match.group(1)
    if not isinstance(captured, str):
        raise BorradorParseError(f"required field {field} did not contain text")
    return captured.strip()


__all__ = ["Modelo100ObservedV2025Extractor"]
