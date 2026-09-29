"""Closed public facts for one cross-period dependency inventory and verdict."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.filing_year import FilingYear
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.ids import LegalRefId, RevisionId, SourceRefId
from ...domain.modelos.filing_record import ExternalEvidenceKind
from ..calculations.cross_period_models import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyInventoryItem,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
)
from ..calculations.observations_repository import ObservationSourceKind
from ..operations.public_period import PublicPeriod


class DependencyRequirementSnapshot(BaseModel):
    """The complete declared requirement, with a public period address."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
    period: PublicPeriod
    source_casilla_ids: tuple[CasillaId, ...] = Field(min_length=1)
    required_source_casilla_ids: tuple[CasillaId, ...] | None = None
    source_presence_groups: tuple[tuple[CasillaId, ...], ...] = ()
    origin: CrossPeriodDependencyOrigin
    origin_ids: tuple[str, ...] = Field(min_length=1)
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    requires_member_fan_in: bool

    @classmethod
    def from_requirement(cls, requirement: CrossPeriodDependencyRequirement) -> Self:
        """Copy exactly the registry-derived fields already shown by the CLI."""
        return cls(
            source_modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period=PublicPeriod.from_period(requirement.period),
            source_casilla_ids=requirement.source_casilla_ids,
            required_source_casilla_ids=requirement.required_source_casilla_ids,
            source_presence_groups=requirement.source_presence_groups,
            origin=requirement.origin,
            origin_ids=requirement.origin_ids,
            legal_refs=requirement.legal_refs,
            source_refs=requirement.source_refs,
            requires_member_fan_in=requirement.requires_member_fan_in,
        )

    def to_requirement(self) -> CrossPeriodDependencyRequirement:
        """Use the canonical requirement invariant for this complete projection."""
        return CrossPeriodDependencyRequirement(
            source_modelo=self.source_modelo,
            filing_year=self.filing_year,
            period=self.period.to_period(),
            source_casilla_ids=self.source_casilla_ids,
            required_source_casilla_ids=self.required_source_casilla_ids,
            source_presence_groups=self.source_presence_groups,
            origin=self.origin,
            origin_ids=self.origin_ids,
            legal_refs=self.legal_refs,
            source_refs=self.source_refs,
            requires_member_fan_in=self.requires_member_fan_in,
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_requirement()
        return self


class DependencyInventoryItemSnapshot(BaseModel):
    """One target and its complete current registry dependency declarations."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    target_modelo: str = Field(min_length=1, max_length=8)
    target_revision_id: RevisionId
    target_filing_year: FilingYear
    target_period: PublicPeriod
    dependency_count: int = Field(ge=1)
    source_modelos: tuple[str, ...]
    dependencies: tuple[DependencyRequirementSnapshot, ...] = Field(min_length=1)

    @classmethod
    def from_item(cls, item: CrossPeriodDependencyInventoryItem) -> Self:
        """Retain canonical declaration order and the CLI's derived counts."""
        return cls(
            target_modelo=item.target_modelo,
            target_revision_id=item.target_revision_id,
            target_filing_year=item.target_filing_year,
            target_period=PublicPeriod.from_period(item.target_period),
            dependency_count=len(item.dependencies),
            source_modelos=item.source_modelos,
            dependencies=tuple(DependencyRequirementSnapshot.from_requirement(row) for row in item.dependencies),
        )

    def to_item(self) -> CrossPeriodDependencyInventoryItem:
        """Restore the complete canonical inventory item."""
        return CrossPeriodDependencyInventoryItem(
            target_modelo=self.target_modelo,
            target_revision_id=self.target_revision_id,
            target_filing_year=self.target_filing_year,
            target_period=self.target_period.to_period(),
            dependencies=tuple(row.to_requirement() for row in self.dependencies),
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        item = self.to_item()
        if self.dependency_count != len(item.dependencies) or self.source_modelos != item.source_modelos:
            raise ValueError("dependency inventory derived fields contradict declarations")
        return self


class DependencyEvidenceSnapshot(BaseModel):
    """Only the clean-state evidence fields the CLI currently discloses."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
    period: PublicPeriod
    clean: bool
    blockers: tuple[CrossPeriodCleanStateBlocker, ...]
    observation_source_kind: ObservationSourceKind | None
    filing_record_id: FilingRecordId | None
    calculation_revision_id: CalculationRevisionId | None
    external_evidence_kind: ExternalEvidenceKind | None
    expected_member_nifs: tuple[str, ...]
    observed_member_nifs: tuple[str, ...]
    missing_member_nifs: tuple[str, ...]
    unexpected_member_nifs: tuple[str, ...]

    @classmethod
    def from_evidence(cls, evidence: CrossPeriodDependencyEvidence) -> Self:
        """Copy no observation payload or omitted internal evidence records."""
        requirement = evidence.requirement
        return cls(
            source_modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period=PublicPeriod.from_period(requirement.period),
            clean=evidence.clean,
            blockers=evidence.blockers,
            observation_source_kind=evidence.observation_source_kind,
            filing_record_id=evidence.filing_record_id,
            calculation_revision_id=evidence.calculation_revision_id,
            external_evidence_kind=evidence.external_evidence_kind,
            expected_member_nifs=evidence.expected_member_nifs,
            observed_member_nifs=evidence.observed_member_nifs,
            missing_member_nifs=evidence.missing_member_nifs,
            unexpected_member_nifs=evidence.unexpected_member_nifs,
        )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("dependency evidence period differs from its filing year")
        if self.clean != (not self.blockers):
            raise ValueError("dependency evidence clean state contradicts blockers")
        return self


class DependencyCleanStateSnapshot(BaseModel):
    """One target's bounded evidence rows, including explicit member NIFs."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    target_modelo: str = Field(min_length=1, max_length=8)
    target_filing_year: FilingYear
    target_period: PublicPeriod
    requires_clean_state: bool
    clean: bool
    blockers: tuple[CrossPeriodCleanStateBlocker, ...]
    dependencies: tuple[DependencyEvidenceSnapshot, ...]

    @classmethod
    def from_verdict(cls, verdict: CrossPeriodCleanStateVerdict) -> Self:
        """Copy only the established CLI clean-state projection."""
        return cls(
            target_modelo=verdict.target_modelo,
            target_filing_year=verdict.target_filing_year,
            target_period=PublicPeriod.from_period(verdict.target_period),
            requires_clean_state=verdict.requires_clean_state,
            clean=verdict.clean,
            blockers=verdict.blockers,
            dependencies=tuple(DependencyEvidenceSnapshot.from_evidence(row) for row in verdict.dependencies),
        )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.target_period.filing_year != self.target_filing_year:
            raise ValueError("dependency target period differs from its filing year")
        blockers = tuple(dict.fromkeys(blocker for row in self.dependencies for blocker in row.blockers))
        if (
            self.requires_clean_state != bool(self.dependencies)
            or self.clean != all(row.clean for row in self.dependencies)
            or self.blockers != blockers
        ):
            raise ValueError("dependency clean state contradicts its evidence rows")
        return self


__all__ = [
    "DependencyCleanStateSnapshot",
    "DependencyEvidenceSnapshot",
    "DependencyInventoryItemSnapshot",
    "DependencyRequirementSnapshot",
]
