"""Canonical public projection contracts for prorrata operation results."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.external_constants import OutputLanguage
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.prorrata_register.register import (
    ProrrataOperatorGrossDeclaration,
    ProrrataRegisterEntry,
    SectorDefinition,
)
from ..operations.error_detail import MAX_OPERATION_ERROR_WORDS_LENGTH
from ..operations.public_scalar import PublicDecimal
from . import operation_requests
from .seed import ProrrataPriorDefinitivaSeed, ProrrataSeedFinding

type ProrrataRefusalReason = Literal[
    "validation",
    "provenance_required",
    "provenance_not_electable",
    "reference_required",
    "reference_not_permitted",
    "seed_source_absent",
    "seed_source_blocked",
    "seed_existing_blocked",
    "regulated_override_standing",
    "sector_prior_definitive_absent",
    "sector_settlement_entry_absent",
    "gross_declaration_duplicate",
    "gross_declaration_absent",
    "gross_declaration_sector_unknown",
]

type ProrrataRefusalCode = Literal[
    "REFUSED_PROFILE_PRORRATA_REGISTER_VALIDATION",
    "REFUSED_PRORRATA_ELECTION",
    "REFUSED_PROFILE_PRORRATA_WHOLE_SEED",
    "REFUSED_PROFILE_PRORRATA_SECTOR_LIFECYCLE",
]

PRORRATA_VALIDATION_REFUSAL_CODE = "REFUSED_PROFILE_PRORRATA_REGISTER_VALIDATION"

PRORRATA_ELECTION_REFUSAL_CODE = "REFUSED_PRORRATA_ELECTION"

PRORRATA_WHOLE_SEED_REFUSAL_CODE = "REFUSED_PROFILE_PRORRATA_WHOLE_SEED"

PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE = "REFUSED_PROFILE_PRORRATA_SECTOR_LIFECYCLE"

GROSS_DECLARATION_OPERATION_IDS: frozenset[operation_requests.ProrrataOperationId] = frozenset(
    {"declare_gross", "remove_gross"}
)
"""Operations whose result arm is one operator gross declaration."""


class ProrrataSnapshotRefProjection(BaseModel):
    """Schema-safe projection of one registry coordinate cited by an entry."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: str
    revision_id: str
    modelo_year: int
    period: str


class ProrrataEspecialTransitionProjection(BaseModel):
    """Complete bounded option or revocation evidence carried by an entry."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: str
    evidence_reference: str


class ProrrataEntryProjection(BaseModel):
    """Complete result projection of one canonical cross-period register entry."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    ejercicio: int
    regime: str
    especial_transition: ProrrataEspecialTransitionProjection | None
    sector_id: str | None
    interrupted: bool
    provisional_percentage: PublicDecimal | None
    provisional_provenance: str | None
    authorisation_reference: str | None
    definitive_percentage: PublicDecimal | None
    definitive_volume_con_derecho: PublicDecimal | None
    definitive_volume_sin_derecho: PublicDecimal | None
    source_observation_ref: str | None
    source_registry_snapshot_refs: tuple[ProrrataSnapshotRefProjection, ...]
    schema_version: str

    @classmethod
    def from_entry(cls, entry: ProrrataRegisterEntry) -> ProrrataEntryProjection:
        """Project every persisted register field without exposing opaque token schemas."""
        transition = entry.especial_transition
        return cls(
            ejercicio=entry.ejercicio,
            regime=entry.regime.value,
            especial_transition=(
                ProrrataEspecialTransitionProjection(
                    kind=transition.kind.value,
                    evidence_reference=transition.evidence_reference,
                )
                if transition is not None
                else None
            ),
            sector_id=entry.sector_id,
            interrupted=entry.interrupted,
            provisional_percentage=_public_decimal(entry.provisional_percentage),
            provisional_provenance=(
                entry.provisional_provenance.value
                if (entry.provisional_provenance is not None and entry.provisional_provenance)
                else None
            ),
            authorisation_reference=entry.authorisation_reference,
            definitive_percentage=_public_decimal(entry.definitive_percentage),
            definitive_volume_con_derecho=_public_decimal(entry.definitive_volume_con_derecho),
            definitive_volume_sin_derecho=_public_decimal(entry.definitive_volume_sin_derecho),
            source_observation_ref=entry.source_observation_ref,
            source_registry_snapshot_refs=tuple(
                ProrrataSnapshotRefProjection(
                    modelo=reference.modelo,
                    revision_id=reference.revision_id,
                    modelo_year=reference.modelo_year,
                    period=reference.period,
                )
                for reference in entry.source_registry_snapshot_refs
            ),
            schema_version=entry.schema_version,
        )


class ProrrataListedEntryProjection(ProrrataEntryProjection):
    """One listed entry with the reference that names its percentage in force.

    An entry whose regime has no reference, or which holds no percentage, has
    neither field.
    """

    reference_id: str | None
    reference_kind: str | None


class ProrrataSectorDefinitionProjection(BaseModel):
    """Complete projection of one operator-authored differentiated-sector row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    sector_id: str
    letra: str
    member_activity_codes: tuple[str, ...]

    @classmethod
    def from_definition(cls, definition: SectorDefinition) -> ProrrataSectorDefinitionProjection:
        """Project every canonical sector coordinate."""
        return cls(
            sector_id=definition.sector_id,
            letra=definition.letra.value,
            member_activity_codes=definition.member_activity_codes,
        )


class ProrrataGrossDeclarationProjection(BaseModel):
    """Complete projection of one operator-declared earlier-period gross cuota."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    ejercicio: int
    period: str
    sector_id: str | None
    gross_cuota: PublicDecimal
    evidence_reference: str
    provenance: Literal["operator_declared"]
    declared_at: datetime

    @classmethod
    def from_declaration(cls, declaration: ProrrataOperatorGrossDeclaration) -> ProrrataGrossDeclarationProjection:
        """Project every persisted declaration field."""
        return cls(
            ejercicio=declaration.ejercicio,
            period=declaration.period.registry_token,
            sector_id=declaration.sector_id,
            gross_cuota=PublicDecimal(decimal=str(declaration.gross_cuota)),
            evidence_reference=declaration.evidence_reference,
            provenance=declaration.provenance,
            declared_at=declaration.declared_at,
        )


class ProrrataFindingProjection(BaseModel):
    """Complete source-finding details for seed advisory and refusal surfaces."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: str
    blocking: bool
    message: str
    source_modelo: str
    source_filing_year: int
    source_period: str
    stamped_revision_id: str
    selected_revision_id: str | None

    @classmethod
    def from_finding(cls, finding: ProrrataSeedFinding) -> ProrrataFindingProjection:
        """Project the complete application finding without reducing it to a flag."""
        return cls(
            code=finding.code,
            blocking=finding.blocking,
            message=finding.message,
            source_modelo=finding.source_modelo,
            source_filing_year=finding.source_filing_year,
            source_period=finding.source_period,
            stamped_revision_id=finding.stamped_revision_id,
            selected_revision_id=finding.selected_revision_id,
        )


class ProrrataSeedSourceProjection(BaseModel):
    """Identity of the local stamped observation, or the stated box, that supplied a carried seed.

    ``operator_stated`` marks the taxpayer's statement: the coordinate is then
    the prior annual summary box it stands in for, not a held observation.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: str
    filing_year: int
    period: str
    casilla_id: str
    stamped_revision_id: str
    authority: Literal["local_prior_observation", "operator_stated"] = "local_prior_observation"

    @classmethod
    def from_seed(cls, seed: ProrrataPriorDefinitivaSeed) -> ProrrataSeedSourceProjection:
        """Project all safe source coordinates from the canonical seed result."""
        return cls(
            modelo=seed.source_modelo,
            filing_year=seed.source_filing_year,
            period=seed.source_period,
            casilla_id=seed.source_casilla_id,
            stamped_revision_id=seed.stamped_revision_id,
            authority="operator_stated" if seed.operator_stated else "local_prior_observation",
        )


class ProrrataRefusalProjection(BaseModel):
    """Finite typed explanation for a known refusal that committed no mutation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: ProrrataRefusalCode
    reason: ProrrataRefusalReason
    detail: str
    ejercicio: int | None = None
    sector_id: str | None = None
    findings: tuple[ProrrataFindingProjection, ...] = ()
    accepted_provenances: tuple[str, ...] = ()
    existing_provenance: str | None = None
    #: The finished sentence a frontend shows for the refusal and the language it is in, served by the
    #: operation so no frontend words a reason of its own.
    refusal_words: str | None = Field(default=None, min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)
    refusal_words_language: OutputLanguage | None = None

    @model_validator(mode="after")
    def _words_name_their_language(self) -> ProrrataRefusalProjection:
        if (self.refusal_words is None) != (self.refusal_words_language is None):
            raise ValueError("served words name the language they are in")
        return self

    @model_validator(mode="after")
    def _standing_provenance_is_exact(self) -> ProrrataRefusalProjection:
        if (self.reason == "regulated_override_standing") != (self.existing_provenance is not None):
            raise ValueError("whole-seed standing refusal must retain the actual provisional provenance")
        return self


class ProrrataListProjection(BaseModel):
    """Complete all-period list result for the profile's prorrata singleton, with its declared gross cuotas."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    entries: tuple[ProrrataListedEntryProjection, ...]
    sectors: tuple[ProrrataSectorDefinitionProjection, ...]
    gross_declarations: tuple[ProrrataGrossDeclarationProjection, ...]
    count: NonNegativeInt

    @model_validator(mode="after")
    def _count_matches_entries(self) -> ProrrataListProjection:
        if self.count != len(self.entries):
            raise ValueError("prorrata list count differs from its complete entry rows")
        return self


class ProrrataMutationProjection(BaseModel):
    """Closed CLI/external client/TUI projection for one prorrata mutation or its refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: operation_requests.ProrrataOperationId
    profile_id: UUID
    outcome: Literal["success", "refused"]
    entry: ProrrataEntryProjection | None = None
    sector_definition: ProrrataSectorDefinitionProjection | None = None
    gross_declaration: ProrrataGrossDeclarationProjection | None = None
    seed_source: ProrrataSeedSourceProjection | None = None
    findings: tuple[ProrrataFindingProjection, ...] = ()
    prior_ejercicio: int | None = None
    count: NonNegativeInt | None = None
    refusal: ProrrataRefusalProjection | None = None

    @model_validator(mode="after")
    def _projection_arm_is_closed(self) -> ProrrataMutationProjection:
        _validate_mutation_projection(self)
        return self


def _public_decimal(value: Decimal | None) -> PublicDecimal | None:
    return PublicDecimal(decimal=str(value)) if value is not None else None


def _validate_mutation_projection(projection: ProrrataMutationProjection) -> None:
    if projection.operation_id == "list":
        raise ValueError("prorrata mutation projection cannot describe a list operation")
    if projection.outcome == "refused":
        _validate_refused_mutation_projection(projection)
    else:
        _validate_successful_mutation_projection(projection)


def _validate_refused_mutation_projection(projection: ProrrataMutationProjection) -> None:
    if (
        projection.refusal is None
        or any(
            value is not None
            for value in (
                projection.entry,
                projection.sector_definition,
                projection.gross_declaration,
                projection.seed_source,
                projection.prior_ejercicio,
                projection.count,
            )
        )
        or projection.findings
    ):
        raise ValueError("prorrata refusal projection is incomplete")


def _validate_successful_mutation_projection(projection: ProrrataMutationProjection) -> None:
    _require_success_projection_completion(projection)
    _validate_mutation_projection_arm(projection)
    _validate_mutation_projection_seed_metadata(projection)


def _require_success_projection_completion(projection: ProrrataMutationProjection) -> None:
    if projection.refusal is not None or projection.count is None:
        raise ValueError("prorrata success projection is incomplete")


def _require_gross_projection_payload(projection: ProrrataMutationProjection) -> None:
    if projection.gross_declaration is None or projection.entry is not None or projection.sector_definition is not None:
        raise ValueError("prorrata gross declaration projection has an incompatible payload")


def _validate_mutation_projection_arm(projection: ProrrataMutationProjection) -> None:
    if projection.operation_id in GROSS_DECLARATION_OPERATION_IDS:
        _require_gross_projection_payload(projection)
    elif projection.gross_declaration is not None:
        raise ValueError("prorrata projection carries a gross declaration outside its operations")
    elif projection.operation_id == "declare_sector":
        if projection.sector_definition is None or projection.entry is not None:
            raise ValueError("prorrata sector projection has an incompatible payload")
    elif projection.entry is None or projection.sector_definition is not None:
        raise ValueError("prorrata entry projection is incomplete")


def _validate_mutation_projection_seed_metadata(projection: ProrrataMutationProjection) -> None:
    if (projection.operation_id == "seed") != (projection.seed_source is not None):
        raise ValueError("prorrata seed projection is missing its source identity")
    if (projection.operation_id == "seed_sector") != (projection.prior_ejercicio is not None):
        raise ValueError("prorrata sector seed projection is missing its prior year")
    if projection.operation_id != "seed" and projection.findings:
        raise ValueError("non-seed prorrata result contains seed findings")


__all__ = [
    "GROSS_DECLARATION_OPERATION_IDS",
    "PRORRATA_ELECTION_REFUSAL_CODE",
    "PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE",
    "PRORRATA_VALIDATION_REFUSAL_CODE",
    "PRORRATA_WHOLE_SEED_REFUSAL_CODE",
    "ProrrataEntryProjection",
    "ProrrataEspecialTransitionProjection",
    "ProrrataFindingProjection",
    "ProrrataGrossDeclarationProjection",
    "ProrrataListProjection",
    "ProrrataListedEntryProjection",
    "ProrrataMutationProjection",
    "ProrrataRefusalCode",
    "ProrrataRefusalProjection",
    "ProrrataRefusalReason",
    "ProrrataSectorDefinitionProjection",
    "ProrrataSeedSourceProjection",
    "ProrrataSnapshotRefProjection",
]
