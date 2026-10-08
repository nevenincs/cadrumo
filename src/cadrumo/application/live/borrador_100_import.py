"""Prepare one local PDF capture before entering snapshot lifecycle persistence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import InternalInvariantError
from ...core.hashing import sha256_hex
from ...core.identity.digest import ContentDigest
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema_extraction import ExtractionProfileDefinition, ExtractionSurface
from .borrador_100_operation_ports import (
    Borrador100ArtefactKind,
    Borrador100ImportObservation,
    Borrador100ImportParserPort,
    Borrador100PrintedValue,
)
from .errors import LiveApplicationInputError


@dataclass(frozen=True, slots=True)
class PreparedBorrador100Import:
    """Validated observed values; no retained PDF bytes or local source path."""

    extraction_profile_id: str
    extraction_coverage: Decimal
    artefact_kind: Borrador100ArtefactKind
    source_pdf_sha256: ContentDigest
    binding_values: Mapping[BindingId, Decimal | str]
    blank_casillas: tuple[CasillaId, ...]
    warnings: tuple[str, ...]

    @property
    def source_url(self) -> str:
        """Preserve the canonical human capture provenance spelling."""
        return "file-import:sha256:" + self.source_pdf_sha256


def prepare_borrador_100_import(
    source_path: Path,
    *,
    filing_year: int,
    period: Period,
    operation: PinnedAuthorityOperation,
    parser: Borrador100ImportParserPort,
) -> PreparedBorrador100Import:
    """Resolve authority, read once, and validate the parser receipt before writes."""
    profile = _resolve_import_profile(operation, filing_year=filing_year, period=period)
    pdf_bytes = source_path.read_bytes()
    digest = sha256_hex(pdf_bytes)
    observation = parser.parse(pdf_bytes, filing_year=filing_year, extraction_profile=profile)
    coverage = _require_parser_receipt(observation, profile=profile, digest=digest, filing_year=filing_year)
    binding_values, blanks = _collect_import_values(profile, observation.values)
    return PreparedBorrador100Import(
        extraction_profile_id=profile.id,
        extraction_coverage=coverage,
        artefact_kind=observation.artefact_kind,
        source_pdf_sha256=digest,
        binding_values=MappingProxyType(binding_values),
        blank_casillas=tuple(sorted(blanks)),
        warnings=observation.warnings,
    )


def _resolve_import_profile(
    operation: PinnedAuthorityOperation,
    *,
    filing_year: int,
    period: Period,
) -> ExtractionProfileDefinition:
    if period.filing_year != filing_year:
        raise ValueError("borrador import period differs from filing year")
    snapshot = operation.snapshot("100", filing_year=filing_year, period=period.registry_token)
    profiles = tuple(
        profile
        for profile in snapshot.extraction_profiles.values()
        if profile.surface == ExtractionSurface.BORRADOR_PDF
    )
    if len(profiles) != 1:
        raise LiveApplicationInputError(translated_message="cli.app.live.borrador.import_profile_unresolved")
    return profiles[0]


def _require_parser_receipt(
    observation: Borrador100ImportObservation,
    *,
    profile: ExtractionProfileDefinition,
    digest: ContentDigest,
    filing_year: int,
) -> Decimal:
    if observation.ejercicio != str(filing_year):
        raise LiveApplicationInputError(
            translated_message="cli.app.live.borrador.import_ejercicio_mismatch",
            context={"expected": filing_year, "actual": observation.ejercicio},
        )
    coverage = observation.extraction_coverage
    if coverage is None:
        raise LiveApplicationInputError(translated_message="cli.app.live.borrador.import_coverage_absent")
    if (
        observation.extraction_profile_id != profile.id
        or observation.source_pdf_sha256 != digest
        or not coverage.is_finite()
        or not profile.min_coverage <= coverage <= Decimal("1")
    ):
        raise InternalInvariantError("borrador parser receipt differs from its pinned source/profile")
    return coverage


def _collect_import_values(
    profile: ExtractionProfileDefinition,
    rows: tuple[Borrador100PrintedValue, ...],
) -> tuple[dict[BindingId, Decimal | str], list[CasillaId]]:
    targets = {target.casilla_id for target in profile.target_casillas}
    seen: set[CasillaId] = set()
    binding_values: dict[BindingId, Decimal | str] = {}
    blanks: list[CasillaId] = []
    for row in rows:
        if row.casilla_id not in targets or row.casilla_id in seen:
            raise InternalInvariantError("borrador parser returned duplicate or out-of-profile rows")
        seen.add(row.casilla_id)
        if row.value is None:
            blanks.append(row.casilla_id)
        else:
            if isinstance(row.value, Decimal) and not row.value.is_finite():
                raise InternalInvariantError("borrador parser returned a nonfinite value")
            binding_values["casilla." + row.casilla_id] = row.value
    return binding_values, blanks
