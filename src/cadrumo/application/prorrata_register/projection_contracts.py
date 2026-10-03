"""Canonical public projection contracts for prorrata operation results."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, NonNegativeInt, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.prorrata_register.register import ProrrataRegisterEntry, SectorDefinition
from ..operations.public_scalar import PublicDecimal
from . import operation_requests as _requests
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
            provisional_provenance=(entry.provisional_provenance.value if entry.provisional_provenance else None),
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
    """Identity of the local stamped observation that supplied a carried seed."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: str
    filing_year: int
    period: str
    casilla_id: str
    stamped_revision_id: str
    authority: Literal["local_prior_observation"] = "local_prior_observation"

    @classmethod
    def from_seed(cls, seed: ProrrataPriorDefinitivaSeed) -> ProrrataSeedSourceProjection:
        """Project all safe source coordinates from the canonical seed result."""
        return cls(
            modelo=seed.source_modelo,
            filing_year=seed.source_filing_year,
            period=seed.source_period,
            casilla_id=str(seed.source_casilla_id),
            stamped_revision_id=seed.stamped_revision_id,
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

    @model_validator(mode="after")
    def _standing_provenance_is_exact(self) -> ProrrataRefusalProjection:
        if (self.reason == "regulated_override_standing") != (self.existing_provenance is not None):
            raise ValueError("whole-seed standing refusal must retain the actual provisional provenance")
        return self


class ProrrataListProjection(BaseModel):
    """Complete all-period list result for the profile's prorrata singleton."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    entries: tuple[ProrrataEntryProjection, ...]
    sectors: tuple[ProrrataSectorDefinitionProjection, ...]
    count: NonNegativeInt

    @model_validator(mode="after")
    def _count_matches_entries(self) -> ProrrataListProjection:
        if self.count != len(self.entries):
            raise ValueError("prorrata list count differs from its complete entry rows")
        return self


class ProrrataMutationProjection(BaseModel):
    """Closed CLI/MCP/TUI projection for one prorrata mutation or its refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: _requests.ProrrataOperationId
    profile_id: UUID
    outcome: Literal["success", "refused"]
    entry: ProrrataEntryProjection | None = None
    sector_definition: ProrrataSectorDefinitionProjection | None = None
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


def _validate_mutation_projection_arm(projection: ProrrataMutationProjection) -> None:
    if projection.operation_id == "declare_sector":
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
    "PRORRATA_ELECTION_REFUSAL_CODE",
    "PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE",
    "PRORRATA_VALIDATION_REFUSAL_CODE",
    "PRORRATA_WHOLE_SEED_REFUSAL_CODE",
    "ProrrataEntryProjection",
    "ProrrataEspecialTransitionProjection",
    "ProrrataFindingProjection",
    "ProrrataListProjection",
    "ProrrataMutationProjection",
    "ProrrataRefusalCode",
    "ProrrataRefusalProjection",
    "ProrrataRefusalReason",
    "ProrrataSectorDefinitionProjection",
    "ProrrataSeedSourceProjection",
    "ProrrataSnapshotRefProjection",
]
