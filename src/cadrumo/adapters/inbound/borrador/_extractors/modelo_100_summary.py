"""Modelo 100 (IRPF / Renta) observed-value extractor implementation.

The extractor reads printed casilla/value rows from a Renta artefact using the
``NNNN label amount`` grammar, which does not vary by year in the fixture PDFs and
generated parser tests that exercise it. One implementation therefore serves every
year; the support envelope, not this adapter, decides which years are admitted.

This is a read-only inbound adapter. It does not define Modelo 100
completeness, resolve a
:class:`~domain.calculations.registry.schema.RegistrySnapshot`, or make
filing-grade authority decisions. When callers pass a
:class:`~adapters.inbound.borrador.schema.BorradorExtractionProfile`, the
extractor filters to that profile and fails hard if observed coverage is
insufficient.

Rows are extracted from the concatenated text stream, so
:class:`~adapters.inbound.pdf.extracted_casilla.ExtractedCasilla` records preserve the
printed value and confidence but do not capture per-row bounding boxes.
"""

from __future__ import annotations

import re
from decimal import Decimal

from .....core.aeat_csv import AEAT_CSV_PATTERN, normalise_aeat_csv
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.identity.digest import ContentDigest
from .....core.time.clock import now
from ...pdf.extracted_casilla import ExtractedCasilla
from ...pdf.label_regex import SPANISH_AMOUNT_GROUP, parse_spanish_decimal
from ...pdf.source_provenance import source_pdf_reference_path
from ..errors import BorradorParseError, BorradorRefusalReason
from ..schema import ArtefactKind, BorradorExtractionProfile, InboundBorradorObservation

_CASILLA_VALUE_RE = re.compile(
    rf"(?m)^\s*(?P<casilla_id>[0-9]{{4}})\s[^\n]{{0,160}}?{SPANISH_AMOUNT_GROUP}",
    re.IGNORECASE,
)

_NIF_RE = re.compile(r"NIF\s*[:\-]?\s*([0-9A-Z]{8,12})", re.IGNORECASE)
# A second declarant is only recognised where the page labels one. No specimen of
# a joint borrador is available, so wording beyond these labels is not guessed at;
# a joint document that prints none of them is not detected here.
_SECOND_DECLARANT_RE = re.compile(
    r"(?:NIF\s+(?:del\s+)?(?:c[óo]nyuge|declarante\s*2)"
    r"|(?:c[óo]nyuge|segundo\s+declarante|declarante\s*2)\b[^\n]{0,40}?\bNIF)",
    re.IGNORECASE,
)
_JOINT_FILING_RE = re.compile(
    r"(?:tributaci[óo]n|declaraci[óo]n)\s+conjunta(?!\s*[:\-]?\s*no\b)",
    re.IGNORECASE,
)
_EJERCICIO_RE = re.compile(r"Ejercicio\s*[:\-]?\s*([0-9]{4})", re.IGNORECASE)
# The capture is the canonical CSV shape, closed by a word boundary so a longer
# run is refused rather than truncated to a different identifier.
_CSV_RE = re.compile(
    rf"C[óo]digo\s+Seguro\s+de\s+Verificaci[óo]n\s*[:\-]?\s*({AEAT_CSV_PATTERN.pattern})\b",
    re.IGNORECASE,
)


class Modelo100ObservedExtractor:
    """Concrete Modelo 100 observed-value extractor implementation.

    Receives the printed page text the parser has read, locates printed
    casilla rows, and returns a strict
    :class:`~adapters.inbound.borrador.schema.InboundBorradorObservation`.
    """

    def extract_pages(
        self,
        pages: tuple[str, ...],
        artefact_kind: ArtefactKind,
        *,
        source_pdf_sha256: ContentDigest,
        extraction_profile: BorradorExtractionProfile | None = None,
    ) -> InboundBorradorObservation:
        """Extract the canonical observation from one captured page-text pass."""
        text = "\n".join(pages)

        tax_id, ejercicio, csv_value = _extract_header_values(text, artefact_kind)

        observed, warnings = _observed_values(text)
        target_casilla_ids = _profile_target_casilla_ids(extraction_profile)
        values, matched_targets = _observed_extracted_values(observed, target_casilla_ids)
        coverage = _profile_coverage(
            extraction_profile,
            target_casilla_ids=target_casilla_ids,
            matched_targets=matched_targets,
        )

        return InboundBorradorObservation(
            modelo="100",
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


def _extract_header_values(
    text: str,
    artefact_kind: ArtefactKind,
) -> tuple[str, str, str | None]:
    tax_id = _require_match(_NIF_RE, text, "tax_id (NIF)")
    _refuse_joint_declaration(text)
    ejercicio = _require_match(_EJERCICIO_RE, text, "ejercicio")
    csv_match = _CSV_RE.search(text)
    csv_value = normalise_aeat_csv(csv_match.group(1)) if csv_match else None
    if artefact_kind is ArtefactKind.DECLARACION and csv_value is None:
        raise BorradorParseError("DECLARACION artefact must carry a CSV stamp but none was found")
    if artefact_kind is not ArtefactKind.DECLARACION:
        csv_value = None
    return tax_id, ejercicio, csv_value


def _refuse_joint_declaration(text: str) -> None:
    """Refuse a document naming a second declarant or a joint filing.

    Every figure on such a page may belong to either declarant, and the header
    NIF names only the first, so ownership of a value cannot be settled here.
    """
    if _SECOND_DECLARANT_RE.search(text) or _JOINT_FILING_RE.search(text):
        raise BorradorParseError(
            "the document names a second declarant or a joint filing; its casillas are not one taxpayer's",
            reason=BorradorRefusalReason.JOINT_DECLARATION,
        )


def _profile_target_casilla_ids(
    extraction_profile: BorradorExtractionProfile | None,
) -> set[CasillaId] | None:
    if extraction_profile is None:
        return None
    return {target.casilla_id for target in extraction_profile.target_casillas}


def _observed_extracted_values(
    observed: dict[CasillaId, Decimal],
    target_casilla_ids: set[CasillaId] | None,
) -> tuple[tuple[ExtractedCasilla, ...], set[CasillaId]]:
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
    return tuple(values), matched_targets


def _profile_coverage(
    extraction_profile: BorradorExtractionProfile | None,
    *,
    target_casilla_ids: set[CasillaId] | None,
    matched_targets: set[CasillaId],
) -> Decimal | None:
    if extraction_profile is None:
        return None
    coverage = Decimal(len(matched_targets)) / Decimal(len(extraction_profile.target_casillas))
    if coverage < extraction_profile.min_coverage:
        missing_ids = tuple(
            sorted(
                target_casilla_ids - matched_targets
                if (target_casilla_ids is not None and target_casilla_ids)
                else set()
            )
        )
        raise BorradorParseError(
            "registry extraction profile coverage below minimum: "
            f"profile={extraction_profile.id!r} coverage={coverage} "
            f"minimum={extraction_profile.min_coverage} missing={list(missing_ids)!r}",
            missing=missing_ids,
            coverage=coverage,
        )
    return coverage


def _observed_values(text: str) -> tuple[dict[CasillaId, Decimal], list[str]]:
    """Extract first-seen four-digit casilla amount rows from ``text``.

    A casilla printed again with the same value is an advisory warning. One
    printed again with a different value is refused, because keeping the first
    would silently choose between two printed figures. Unparseable values are
    advisory too; coverage-sensitive callers get hard failures later when the
    filtered observed set is compared with the supplied extraction profile.
    """
    observed: dict[CasillaId, Decimal] = {}
    warnings: list[str] = []
    for match in _CASILLA_VALUE_RE.finditer(text):
        casilla_id = validated_casilla_id(
            match.group("casilla_id"),
            surface="Modelo 100 borrador observed casilla id",
        )
        raw_value = match.group(2)
        value = parse_spanish_decimal(raw_value)
        if casilla_id in observed:
            if value is not None and value != observed[casilla_id]:
                raise BorradorParseError(
                    f"casilla {casilla_id} is printed more than once with different values",
                    ambiguous=(casilla_id,),
                    reason=BorradorRefusalReason.CONFLICTING_DUPLICATE_ROW,
                )
            warnings.append(f"casilla {casilla_id}: duplicate printed value ignored")
            continue
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


__all__ = ["Modelo100ObservedExtractor"]
