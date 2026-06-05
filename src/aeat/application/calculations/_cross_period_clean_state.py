"""Clean-state proof for filing-grade cross-period modelo dependencies."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from ...domain.calculations.registry import (
    RegistryModeloObservationRequirement,
    RegistryRelationSourceRequirement,
    RegistrySnapshot,
    previous_filing_observation_requirements,
    relation_source_requirements,
)
from ...domain.modelos import (
    CalculationRevisionCatalogueRepositoryProtocol,
    CalculationRevisionState,
    ModeloRecordCatalogueRepositoryProtocol,
    ModeloRecordStatus,
    VerificationCompletenessStatus,
    VerificationReportCatalogueRepositoryProtocol,
)
from ._observations_repository import CalculationObservationRepository

_STRICT_FROZEN: Final = ConfigDict(strict=True, frozen=True, extra="forbid")
_OFFICIAL_SOURCE_KINDS: Final = frozenset(
    {
        "aeat_sede_justificante",
        "aeat_sede_live_capture",
        "aeat_csv_register",
    }
)


class CrossPeriodDependencyOrigin(StrEnum):
    """Registry source family that created a cross-period dependency."""

    PREVIOUS_FILING_BINDING = "previous_filing_binding"
    REGISTRY_RELATION = "registry_relation"


class CrossPeriodCleanStateBlocker(StrEnum):
    """Blocking reason codes for a cross-period clean-state verdict."""

    MISSING_OBSERVATION = "missing_observation"
    MISSING_OBSERVED_CASILLA = "missing_observed_casilla"
    MISSING_CURRENT_FILING_RECORD = "missing_current_filing_record"
    MISSING_CALCULATION_REVISION = "missing_calculation_revision"
    UNFILED_CALCULATION_REVISION = "unfiled_calculation_revision"
    MISSING_COMPLETE_VERIFICATION_REPORT = "missing_complete_verification_report"
    LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE = "local_filing_missing_external_evidence"
    MISSING_AEAT_ACCEPTANCE = "missing_aeat_acceptance"
    MISSING_EXTERNAL_EVIDENCE = "missing_external_evidence"
    OBSERVATION_REVISION_VALUE_DIVERGENCE = "observation_revision_value_divergence"
    OPERATOR_MANUAL_SOURCE = "operator_manual_source"
    INCOMPLETE_GROUP_MEMBER_COVERAGE = "incomplete_group_member_coverage"


class CrossPeriodDependencyRequirement(BaseModel):
    """One upstream filed declaration required by a target registry snapshot."""

    model_config = _STRICT_FROZEN

    source_modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    source_casillas: tuple[str, ...] = Field(min_length=1)
    origin: CrossPeriodDependencyOrigin
    origin_ids: tuple[str, ...] = Field(min_length=1)
    requires_member_fan_in: bool = False

    @property
    def key(self) -> tuple[str, int, str, CrossPeriodDependencyOrigin, tuple[str, ...]]:
        return (self.source_modelo, self.filing_year, self.period, self.origin, self.origin_ids)


class CrossPeriodDependencyEvidence(BaseModel):
    """Observed filing-state evidence for one dependency requirement."""

    model_config = _STRICT_FROZEN

    requirement: CrossPeriodDependencyRequirement
    observation_source_kind: str | None = None
    filing_record_id: str | None = None
    calculation_revision_id: str | None = None
    calculation_revision_state: CalculationRevisionState | None = None
    verification_status: VerificationCompletenessStatus | None = None
    aeat_accepted: bool | None = None
    external_evidence_kind: str | None = None
    blockers: tuple[CrossPeriodCleanStateBlocker, ...] = ()

    @property
    def clean(self) -> bool:
        return not self.blockers


class CrossPeriodCleanStateVerdict(BaseModel):
    """Clean-state result for every cross-period dependency in a target snapshot."""

    model_config = _STRICT_FROZEN

    bucket_id: str = Field(min_length=1)
    target_modelo: str = Field(min_length=1, max_length=8)
    target_filing_year: int = Field(ge=2000, le=2099)
    target_period: str = Field(min_length=1, max_length=8)
    dependencies: tuple[CrossPeriodDependencyEvidence, ...] = ()

    @property
    def requires_clean_state(self) -> bool:
        return bool(self.dependencies)

    @property
    def clean(self) -> bool:
        return all(item.clean for item in self.dependencies)

    @property
    def blockers(self) -> tuple[CrossPeriodCleanStateBlocker, ...]:
        return tuple(
            dict.fromkeys(blocker for item in self.dependencies for blocker in item.blockers)
        )


def cross_period_dependency_requirements(snapshot: RegistrySnapshot) -> tuple[CrossPeriodDependencyRequirement, ...]:
    """Return the registry-derived filed-history requirements for ``snapshot``."""
    requirements: dict[
        tuple[str, int, str, CrossPeriodDependencyOrigin, tuple[str, ...]],
        CrossPeriodDependencyRequirement,
    ] = {}
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        for item in _requirements_from_previous_filing(requirement, snapshot=snapshot):
            requirements.setdefault(item.key, item)
    for requirement in relation_source_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        for item in _requirements_from_relation(requirement):
            requirements.setdefault(item.key, item)
    return tuple(requirements.values())


def evaluate_cross_period_clean_state(
    snapshot: RegistrySnapshot,
    *,
    bucket_id: str,
    observation_repository: CalculationObservationRepository,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
) -> CrossPeriodCleanStateVerdict:
    """Evaluate whether every cross-period dependency is filing-grade clean."""
    filing_catalogue = filing_repository.load()
    calculation_catalogue = calculation_repository.load()
    verification_catalogue = verification_repository.load()
    dependencies = tuple(
        _evaluate_requirement(
            requirement,
            bucket_id=bucket_id,
            observation_repository=observation_repository,
            filing_catalogue=filing_catalogue,
            calculation_catalogue=calculation_catalogue,
            verification_catalogue=verification_catalogue,
        )
        for requirement in cross_period_dependency_requirements(snapshot)
    )
    return CrossPeriodCleanStateVerdict(
        bucket_id=bucket_id,
        target_modelo=str(snapshot.modelo.id),
        target_filing_year=snapshot.filing_year,
        target_period=snapshot.period,
        dependencies=dependencies,
    )


def _requirements_from_previous_filing(
    requirement: RegistryModeloObservationRequirement,
    *,
    snapshot: RegistrySnapshot,
) -> Iterable[CrossPeriodDependencyRequirement]:
    grouped_keys = _per_grupo_member_requirement_keys(snapshot)
    yield CrossPeriodDependencyRequirement(
        source_modelo=requirement.modelo,
        filing_year=requirement.filing_year,
        period=requirement.period,
        source_casillas=requirement.source_casillas,
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=requirement.binding_ids,
        requires_member_fan_in=(requirement.modelo, requirement.filing_year, requirement.period) in grouped_keys,
    )


def _requirements_from_relation(
    requirement: RegistryRelationSourceRequirement,
) -> Iterable[CrossPeriodDependencyRequirement]:
    for period in requirement.periods:
        yield CrossPeriodDependencyRequirement(
            source_modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period=period,
            source_casillas=(requirement.source_output,),
            origin=CrossPeriodDependencyOrigin.REGISTRY_RELATION,
            origin_ids=requirement.relation_ids,
        )


def _per_grupo_member_requirement_keys(snapshot: RegistrySnapshot) -> set[tuple[str, int, str]]:
    grouped_binding_ids = {
        binding.id
        for binding in snapshot.revision.bindings
        if binding.source == "previous_filing" and _selector_grouping(binding.selector) == "per_grupo_member"
    }
    if not grouped_binding_ids:
        return set()
    keys: set[tuple[str, int, str]] = set()
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        if any(binding_id in grouped_binding_ids for binding_id in requirement.binding_ids):
            keys.add((requirement.modelo, requirement.filing_year, requirement.period))
    return keys


def _selector_grouping(selector: object) -> object:
    if isinstance(selector, dict):
        return selector.get("grouping")
    return getattr(selector, "grouping", None)


def _evaluate_requirement(
    requirement: CrossPeriodDependencyRequirement,
    *,
    bucket_id: str,
    observation_repository: CalculationObservationRepository,
    filing_catalogue,
    calculation_catalogue,
    verification_catalogue,
) -> CrossPeriodDependencyEvidence:
    blockers: list[CrossPeriodCleanStateBlocker] = []
    member_payloads: tuple[object, ...] = ()
    payload = None
    if requirement.requires_member_fan_in:
        member_payloads = tuple(
            item
            for item in observation_repository.iter_modelo(requirement.source_modelo)
            if item.observation.filing_year == requirement.filing_year
            and item.observation.period == requirement.period
            and item.member_nif is not None
        )
        if not member_payloads:
            blockers.append(CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE)
    else:
        payload = observation_repository.load_observation(
            requirement.source_modelo,
            requirement.filing_year,
            requirement.period,
        )
    observation_source_kind: str | None = None
    observation_values: dict[str, object] = {}
    if requirement.requires_member_fan_in and member_payloads:
        observation_source_kind = _combined_source_kind(item.source_kind for item in member_payloads)
        if any(item.source_kind == "operator_manual" for item in member_payloads):
            blockers.append(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE)
        for item in member_payloads:
            for casilla_id in requirement.source_casillas:
                if casilla_id not in item.observation.casilla_values:
                    blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA)
    elif payload is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVATION)
    else:
        observation_source_kind = payload.source_kind
        observation_values = dict(payload.observation.casilla_values)
        if payload.source_kind == "operator_manual":
            blockers.append(CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE)
        for casilla_id in requirement.source_casillas:
            if casilla_id not in observation_values:
                blockers.append(CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA)

    filing = filing_catalogue.current_for(
        bucket_id=bucket_id,
        modelo=requirement.source_modelo,
        filing_year=requirement.filing_year,
        period=requirement.period,
    )
    if filing is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD)
        return CrossPeriodDependencyEvidence(
            requirement=requirement,
            observation_source_kind=observation_source_kind,
            blockers=_unique_blockers(blockers),
        )

    if filing.status is not ModeloRecordStatus.VIGENTE:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD)
    if not filing.aeat_accepted:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_AEAT_ACCEPTANCE)
    if filing.external_evidence is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE)
        if observation_source_kind not in _OFFICIAL_SOURCE_KINDS:
            blockers.append(CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE)

    revision = calculation_catalogue.get(filing.calculation_revision_id)
    revision_state: CalculationRevisionState | None = None
    if revision is None:
        blockers.append(CrossPeriodCleanStateBlocker.MISSING_CALCULATION_REVISION)
    else:
        revision_state = revision.state
        if revision.state is not CalculationRevisionState.PRESENTADO:
            blockers.append(CrossPeriodCleanStateBlocker.UNFILED_CALCULATION_REVISION)
        if requirement.requires_member_fan_in:
            member_totals = {
                casilla_id: sum(
                    (item.observation.casilla_values.get(casilla_id) for item in member_payloads),
                    start=0,
                )
                for casilla_id in requirement.source_casillas
                if member_payloads
                and all(casilla_id in item.observation.casilla_values for item in member_payloads)
            }
            for casilla_id, observed_total in member_totals.items():
                if revision.casilla_values.get(casilla_id) != observed_total:
                    blockers.append(CrossPeriodCleanStateBlocker.OBSERVATION_REVISION_VALUE_DIVERGENCE)
        else:
            for casilla_id in requirement.source_casillas:
                observed = observation_values.get(casilla_id)
                if observed is None:
                    continue
                if revision.casilla_values.get(casilla_id) != observed:
                    blockers.append(CrossPeriodCleanStateBlocker.OBSERVATION_REVISION_VALUE_DIVERGENCE)

    verification_status: VerificationCompletenessStatus | None = None
    if filing.external_evidence is None:
        complete_reports = tuple(
            report
            for report in verification_catalogue.for_calculation_revision(filing.calculation_revision_id)
            if report.granted_verificado_completo
            and report.completeness_status is VerificationCompletenessStatus.COMPLETE
        )
        if complete_reports:
            verification_status = complete_reports[-1].completeness_status
        else:
            blockers.append(CrossPeriodCleanStateBlocker.MISSING_COMPLETE_VERIFICATION_REPORT)

    return CrossPeriodDependencyEvidence(
        requirement=requirement,
        observation_source_kind=observation_source_kind,
        filing_record_id=filing.filing_record_id,
        calculation_revision_id=filing.calculation_revision_id,
        calculation_revision_state=revision_state,
        verification_status=verification_status,
        aeat_accepted=filing.aeat_accepted,
        external_evidence_kind=filing.external_evidence.kind.value if filing.external_evidence is not None else None,
        blockers=_unique_blockers(blockers),
    )


def _unique_blockers(
    blockers: Iterable[CrossPeriodCleanStateBlocker],
) -> tuple[CrossPeriodCleanStateBlocker, ...]:
    return tuple(dict.fromkeys(blockers))


def _combined_source_kind(source_kinds: Iterable[str]) -> str:
    unique = tuple(dict.fromkeys(source_kinds))
    if len(unique) == 1:
        return unique[0]
    return "mixed"


__all__ = [
    "CrossPeriodCleanStateBlocker",
    "CrossPeriodCleanStateVerdict",
    "CrossPeriodDependencyEvidence",
    "CrossPeriodDependencyOrigin",
    "CrossPeriodDependencyRequirement",
    "cross_period_dependency_requirements",
    "evaluate_cross_period_clean_state",
]
