"""Prepare one local PDF capture before entering snapshot lifecycle persistence."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import InternalInvariantError
from ...core.hashing import sha256_hex
from ...core.identity.digest import ContentDigest
from ...core.identity.documents import IdentityError
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_extraction import ExtractionProfileDefinition, ExtractionSurface
from ...domain.calculations.registry.tax_id_runtime import validate_runtime_spanish_tax_id
from .borrador_100 import Borrador100PrintedObservation
from .borrador_100_keys import project_printed_casillas
from .borrador_100_operation_ports import (
    Borrador100ArtefactKind,
    Borrador100ImportObservation,
    Borrador100ImportParserPort,
    Borrador100PrintedValue,
)
from .errors import LiveApplicationInputError


@dataclass(frozen=True, slots=True)
class PreparedBorrador100Import:
    """Validated observed values; no retained PDF bytes or local source path.

    ``binding_values`` holds each printed value under the binding that owns its
    casilla in the pinned revision. ``printed_observations`` keeps every other
    printed box the revision declares, comparison-only and never a calculation
    input. ``unowned_casillas`` lists printed casillas the revision does not
    declare: they are reported, not stored.
    """

    extraction_profile_id: str
    extraction_coverage: Decimal
    artefact_kind: Borrador100ArtefactKind
    source_pdf_sha256: ContentDigest
    binding_values: Mapping[BindingId, Decimal | str]
    printed_observations: tuple[Borrador100PrintedObservation, ...]
    blank_casillas: tuple[CasillaId, ...]
    unowned_casillas: tuple[CasillaId, ...]
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
    profile_tax_id: Callable[[], str | None],
) -> PreparedBorrador100Import:
    """Resolve authority, read once, and validate the parser receipt before writes."""
    revision, profile = _resolve_import_profile(operation, filing_year=filing_year, period=period)
    pdf_bytes = source_path.read_bytes()
    digest = sha256_hex(pdf_bytes)
    observation = parser.parse(
        pdf_bytes,
        filing_year=filing_year,
        supported_filing_years=operation.supported_filing_years(),
        extraction_profile=profile,
    )
    coverage = _require_parser_receipt(observation, profile=profile, digest=digest, filing_year=filing_year)
    _require_document_belongs_to_profile(observation.tax_id, profile_tax_id())
    printed, blanks = _collect_printed_values(profile, observation.values)
    projection = project_printed_casillas(revision, printed, blank=blanks)
    return PreparedBorrador100Import(
        extraction_profile_id=profile.id,
        extraction_coverage=coverage,
        artefact_kind=observation.artefact_kind,
        source_pdf_sha256=digest,
        binding_values=MappingProxyType(dict(projection.binding_values)),
        printed_observations=tuple(
            Borrador100PrintedObservation(casilla_id=box.casilla_id, continuidad_id=box.continuidad_id, value=box.value)
            for box in projection.observed
        ),
        blank_casillas=tuple(sorted(blanks)),
        unowned_casillas=projection.unowned_casillas,
        warnings=observation.warnings,
    )


def _resolve_import_profile(
    operation: PinnedAuthorityOperation,
    *,
    filing_year: int,
    period: Period,
) -> tuple[ModeloRevision, ExtractionProfileDefinition]:
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
    return snapshot.revision, profiles[0]


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


def _canonical_tax_id(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    try:
        return validate_runtime_spanish_tax_id(value)
    except IdentityError:
        return None


def _require_document_belongs_to_profile(document_tax_id: str | None, recorded_tax_id: str | None) -> None:
    """Refuse a capture of another taxpayer, or one whose ownership cannot be confirmed.

    Both identifiers are compared in the canonical form the censal ownership guard uses.
    Absence or a malformed identifier on either side is not a match.
    """
    recorded = _canonical_tax_id(recorded_tax_id)
    if recorded is None:
        raise LiveApplicationInputError(translated_message="cli.app.live.borrador.import_profile_tax_id_unusable")
    printed = _canonical_tax_id(document_tax_id)
    if printed is None:
        raise LiveApplicationInputError(translated_message="cli.app.live.borrador.import_tax_id_unreadable")
    if printed != recorded:
        raise LiveApplicationInputError(translated_message="cli.app.live.borrador.import_tax_id_mismatch")


def _collect_printed_values(
    profile: ExtractionProfileDefinition,
    rows: tuple[Borrador100PrintedValue, ...],
) -> tuple[dict[CasillaId, Decimal | str], list[CasillaId]]:
    targets = {target.casilla_id for target in profile.target_casillas}
    seen: set[CasillaId] = set()
    printed: dict[CasillaId, Decimal | str] = {}
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
            printed[row.casilla_id] = row.value
    return printed, blanks
