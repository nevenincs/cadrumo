"""Pure, frontend-neutral projection for the Declarations workspace.

Callers preload the secure Modelo catalogues and provide explicit source
observations.  This module validates their joins and projects only natural
declaration coordinates, lifecycle states, and non-sensitive timestamps.  It
does not resolve repositories, contact AEAT, or retain financial/evidence
payloads for serialization.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.filing_year import FilingYear
from ...core.identifier_grammar import NamespacedId
from ...core.identity import BucketId, CalculationRevisionId, FilingRecordId, WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.time.utc import UtcInstant
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
)
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.filing_record import (
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
)
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState

DECLARATIONS_WORKSPACE_CONTRACT_VERSION: Final[int] = 1


class DeclarationsWorkspaceProjectionError(ValueError):
    """The supplied authorities cannot form one coherent safe snapshot."""


class DeclarationsWorkspaceZone(StrEnum):
    """Exact read areas owned by the Declarations landing."""

    DECLARATIONS = "declarations"
    CALCULATION_REVISIONS = "calculation_revisions"
    FILING_HISTORY = "filing_history"


class DeclarationsWorkspaceSource(StrEnum):
    """Canonical source axes retained by the projection."""

    LOCAL_DECLARATIONS = "local.declarations"
    LOCAL_CALCULATIONS = "local.calculations"
    LOCAL_FILINGS = "local.filings"
    LOCAL_LIFECYCLE = "local.lifecycle"
    AEAT_EVIDENCE = "aeat.evidence"


class DeclarationsWorkspaceAvailability(StrEnum):
    """Whether a source snapshot can make an authoritative claim."""

    AVAILABLE = "available"
    LOCKED = "locked"
    STALE = "stale"
    NEVER_CAPTURED = "never_captured"
    UNAVAILABLE = "unavailable"


class DeclarationsLifecycleKind(StrEnum):
    """Sanitized lifecycle meanings accepted from the lifecycle authority."""

    CREATED = "created"
    RENAMED = "renamed"
    CALCULATED = "calculated"
    VERIFIED = "verified"
    FILED = "filed"
    SUPERSEDED = "superseded"
    AMENDED = "amended"
    DISCARDED = "discarded"
    EXTERNAL_EVIDENCE_IMPORTED = "external_evidence_imported"
    EXPORTED = "exported"


class DeclarationsWorkspaceZoneObservationV1(BaseModel):
    """Caller-observed availability before any rows are projected."""

    model_config = STRICT_FROZEN_CONFIG

    zone: DeclarationsWorkspaceZone
    availability: DeclarationsWorkspaceAvailability
    observed_at: UtcInstant | None = None
    reason_code: NamespacedId | None = None

    @model_validator(mode="after")
    def _availability_has_truthful_evidence(self) -> Self:
        observable = self.availability in {
            DeclarationsWorkspaceAvailability.AVAILABLE,
            DeclarationsWorkspaceAvailability.STALE,
        }
        if observable and self.observed_at is None:
            raise ValueError("an available or stale Declarations zone requires an observation time")
        if self.availability is DeclarationsWorkspaceAvailability.AVAILABLE and self.reason_code is not None:
            raise ValueError("an available Declarations zone cannot carry a reason")
        if self.availability is not DeclarationsWorkspaceAvailability.AVAILABLE and self.reason_code is None:
            raise ValueError("a non-available Declarations zone requires a reason")
        if self.availability is DeclarationsWorkspaceAvailability.NEVER_CAPTURED and self.observed_at is not None:
            raise ValueError("a never-captured Declarations zone cannot carry an observation time")
        return self


class DeclarationsWorkspaceZoneStateV1(DeclarationsWorkspaceZoneObservationV1):
    """One zone's authority, freshness, and measured cardinality."""

    sources: tuple[DeclarationsWorkspaceSource, ...]
    item_count: NonNegativeInt | None = None

    @model_validator(mode="after")
    def _count_matches_observability(self) -> Self:
        observable = self.availability in {
            DeclarationsWorkspaceAvailability.AVAILABLE,
            DeclarationsWorkspaceAvailability.STALE,
        }
        if observable != (self.item_count is not None):
            raise ValueError("only observable Declarations zones carry a measured item count")
        if not self.sources or len(self.sources) != len(set(self.sources)):
            raise ValueError("a Declarations zone requires unique source authorities")
        return self


class DeclarationsWorkspaceDeclarationRefV1(BaseModel):
    """Safe natural coordinate for one local declaration."""

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: WorkUnitId = Field(exclude=True, repr=False)
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    state: WorkUnitState
    has_current_calculation: bool
    has_current_filing: bool

    @model_validator(mode="after")
    def _period_matches_year(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("declaration period must match its filing year")
        return self


class DeclarationsWorkspaceCalculationRevisionRefV1(BaseModel):
    """Safe state reference for one calculation version."""

    model_config = STRICT_FROZEN_CONFIG

    calculation_revision_id: CalculationRevisionId = Field(exclude=True, repr=False)
    work_unit_id: WorkUnitId = Field(exclude=True, repr=False)
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    state: CalculationRevisionState
    created_at: UtcInstant
    updated_at: UtcInstant
    is_current: bool
    is_filed: bool

    @model_validator(mode="after")
    def _period_matches_year(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("calculation revision period must match its filing year")
        return self


class DeclarationsWorkspaceFilingRefV1(BaseModel):
    """Safe local filing currency and separately observed AEAT evidence."""

    model_config = STRICT_FROZEN_CONFIG

    filing_record_id: FilingRecordId = Field(exclude=True, repr=False)
    work_unit_id: WorkUnitId = Field(exclude=True, repr=False)
    calculation_revision_id: CalculationRevisionId = Field(exclude=True, repr=False)
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    filed_at: UtcInstant
    local_status: ModeloRecordStatus
    aeat_accepted: bool
    evidence_kind: ExternalEvidenceKind | None = None

    @model_validator(mode="after")
    def _evidence_axes_are_truthful(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("filing period must match its filing year")
        if self.aeat_accepted != (self.evidence_kind is not None):
            raise ValueError("AEAT acceptance and external evidence presence must agree")
        return self


class DeclarationsSanitizedLifecycleFactV1(BaseModel):
    """Payload-free lifecycle fact supplied by an application authority."""

    model_config = STRICT_FROZEN_CONFIG

    fact_id: str = Field(exclude=True, repr=False, min_length=1, max_length=128)
    work_unit_id: WorkUnitId = Field(exclude=True, repr=False)
    occurred_at: UtcInstant
    kind: DeclarationsLifecycleKind


class DeclarationsWorkspaceLifecycleRefV1(BaseModel):
    """Sanitized lifecycle fact joined to its natural declaration address."""

    model_config = STRICT_FROZEN_CONFIG

    fact_id: str = Field(exclude=True, repr=False, min_length=1, max_length=128)
    work_unit_id: WorkUnitId = Field(exclude=True, repr=False)
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    occurred_at: UtcInstant
    kind: DeclarationsLifecycleKind


class DeclarationsWorkspaceProjectionV1(BaseModel):
    """Immutable safe index over one coherent preloaded Declarations snapshot."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: int = DECLARATIONS_WORKSPACE_CONTRACT_VERSION
    bucket_id: BucketId = Field(exclude=True, repr=False)
    zones: tuple[DeclarationsWorkspaceZoneStateV1, ...]
    declarations: tuple[DeclarationsWorkspaceDeclarationRefV1, ...]
    calculation_revisions: tuple[DeclarationsWorkspaceCalculationRevisionRefV1, ...]
    filings: tuple[DeclarationsWorkspaceFilingRefV1, ...]
    lifecycle: tuple[DeclarationsWorkspaceLifecycleRefV1, ...]

    @model_validator(mode="after")
    def _zones_are_total_and_ordered(self) -> Self:
        if tuple(state.zone for state in self.zones) != tuple(DeclarationsWorkspaceZone):
            raise ValueError("Declarations zones must cover the closed catalogue in canonical order")
        return self


_SOURCES_BY_ZONE: Final = {
    DeclarationsWorkspaceZone.DECLARATIONS: (DeclarationsWorkspaceSource.LOCAL_DECLARATIONS,),
    DeclarationsWorkspaceZone.CALCULATION_REVISIONS: (
        DeclarationsWorkspaceSource.LOCAL_DECLARATIONS,
        DeclarationsWorkspaceSource.LOCAL_CALCULATIONS,
    ),
    DeclarationsWorkspaceZone.FILING_HISTORY: (
        DeclarationsWorkspaceSource.LOCAL_DECLARATIONS,
        DeclarationsWorkspaceSource.LOCAL_CALCULATIONS,
        DeclarationsWorkspaceSource.LOCAL_FILINGS,
        DeclarationsWorkspaceSource.LOCAL_LIFECYCLE,
        DeclarationsWorkspaceSource.AEAT_EVIDENCE,
    ),
}


def project_declarations_workspace(
    *,
    bucket_id: BucketId,
    work_units: WorkUnitCatalogue,
    calculation_revisions: CalculationRevisionCatalogue,
    filing_records: ModeloRecordCatalogue,
    lifecycle_facts: tuple[DeclarationsSanitizedLifecycleFactV1, ...],
    zone_observations: tuple[DeclarationsWorkspaceZoneObservationV1, ...],
) -> DeclarationsWorkspaceProjectionV1:
    """Validate and safely project already-loaded local authorities."""
    observations = _validate_observations(zone_observations)
    units = tuple(work_units.values())
    revisions = tuple(calculation_revisions.values())
    filings = tuple(filing_records.records.values())
    _validate_catalogue_joins(
        bucket_id=bucket_id,
        units=units,
        revisions=revisions,
        filings=filings,
        lifecycle_facts=lifecycle_facts,
    )

    observable = {
        zone
        for zone, observation in observations.items()
        if observation.availability
        in {DeclarationsWorkspaceAvailability.AVAILABLE, DeclarationsWorkspaceAvailability.STALE}
    }
    declaration_rows = _declaration_rows(units) if DeclarationsWorkspaceZone.DECLARATIONS in observable else ()
    revision_rows = (
        _revision_rows(revisions, {unit.work_unit_id: unit for unit in units})
        if DeclarationsWorkspaceZone.CALCULATION_REVISIONS in observable
        else ()
    )
    filing_rows = _filing_rows(filings) if DeclarationsWorkspaceZone.FILING_HISTORY in observable else ()
    lifecycle_rows = (
        _lifecycle_rows(lifecycle_facts, {unit.work_unit_id: unit for unit in units})
        if DeclarationsWorkspaceZone.FILING_HISTORY in observable
        else ()
    )
    counts = {
        DeclarationsWorkspaceZone.DECLARATIONS: len(declaration_rows),
        DeclarationsWorkspaceZone.CALCULATION_REVISIONS: len(revision_rows),
        DeclarationsWorkspaceZone.FILING_HISTORY: len(filing_rows) + len(lifecycle_rows),
    }
    zones = tuple(
        DeclarationsWorkspaceZoneStateV1(
            **observations[zone].model_dump(),
            sources=_SOURCES_BY_ZONE[zone],
            item_count=counts[zone] if zone in observable else None,
        )
        for zone in DeclarationsWorkspaceZone
    )
    return DeclarationsWorkspaceProjectionV1(
        bucket_id=bucket_id,
        zones=zones,
        declarations=declaration_rows,
        calculation_revisions=revision_rows,
        filings=filing_rows,
        lifecycle=lifecycle_rows,
    )


def _validate_observations(
    observations: tuple[DeclarationsWorkspaceZoneObservationV1, ...],
) -> dict[DeclarationsWorkspaceZone, DeclarationsWorkspaceZoneObservationV1]:
    expected = tuple(DeclarationsWorkspaceZone)
    if tuple(item.zone for item in observations) != expected:
        raise DeclarationsWorkspaceProjectionError(
            "zone observations must cover the closed Declarations catalogue in canonical order"
        )
    return {item.zone: item for item in observations}


def _validate_catalogue_joins(
    *,
    bucket_id: BucketId,
    units: tuple[WorkUnit, ...],
    revisions: tuple[CalculationRevision, ...],
    filings: tuple[ModeloRecord, ...],
    lifecycle_facts: tuple[DeclarationsSanitizedLifecycleFactV1, ...],
) -> None:
    unit_by_id = {unit.work_unit_id: unit for unit in units}
    revision_by_id = {revision.calculation_revision_id: revision for revision in revisions}
    filing_by_id = {record.filing_record_id: record for record in filings}
    if any(unit.bucket_id != bucket_id for unit in units):
        raise DeclarationsWorkspaceProjectionError("work catalogue contains a foreign bucket")
    natural_addresses = tuple((unit.modelo, unit.filing_year, unit.period) for unit in units)
    if len(natural_addresses) != len(set(natural_addresses)):
        raise DeclarationsWorkspaceProjectionError("work catalogue contains duplicate declaration addresses")
    if len({fact.fact_id for fact in lifecycle_facts}) != len(lifecycle_facts):
        raise DeclarationsWorkspaceProjectionError("lifecycle facts contain duplicate identities")

    for revision in revisions:
        if revision.work_unit_id not in unit_by_id:
            raise DeclarationsWorkspaceProjectionError("calculation revision has no declaration")
    for unit in units:
        for revision_id in (unit.current_calculation_revision_id, unit.filed_calculation_revision_id):
            if revision_id is None:
                continue
            revision = revision_by_id.get(revision_id)
            if revision is None or revision.work_unit_id != unit.work_unit_id:
                raise DeclarationsWorkspaceProjectionError("declaration revision pointer is missing or contradictory")
        filed_revision_id = unit.filed_calculation_revision_id
        current_filing_id = unit.current_filing_record_id
        if (filed_revision_id is None) != (current_filing_id is None):
            raise DeclarationsWorkspaceProjectionError("declaration filing pointers must be present or absent together")
        if filed_revision_id is not None and current_filing_id is not None:
            revision = revision_by_id.get(filed_revision_id)
            record = filing_by_id.get(current_filing_id)
            if (
                revision is None
                or record is None
                or revision.work_unit_id != unit.work_unit_id
                or record.work_unit_id != unit.work_unit_id
                or record.calculation_revision_id != revision.calculation_revision_id
                or record.status is not ModeloRecordStatus.VIGENTE
                or revision.state is not CalculationRevisionState.PRESENTADO
            ):
                raise DeclarationsWorkspaceProjectionError(
                    "declaration filing pointers do not resolve to one current filing"
                )

    for record in filings:
        unit = unit_by_id.get(record.work_unit_id)
        revision = revision_by_id.get(record.calculation_revision_id)
        if record.bucket_id != bucket_id or unit is None or revision is None:
            raise DeclarationsWorkspaceProjectionError("filing record has no same-bucket declaration and revision")
        if revision.work_unit_id != unit.work_unit_id:
            raise DeclarationsWorkspaceProjectionError("filing revision belongs to another declaration")
        if (record.modelo, record.filing_year, record.period) != (unit.modelo, unit.filing_year, unit.period):
            raise DeclarationsWorkspaceProjectionError("filing address contradicts its declaration")
        if record.status is ModeloRecordStatus.VIGENTE and (
            unit.current_filing_record_id != record.filing_record_id
            or unit.filed_calculation_revision_id != record.calculation_revision_id
            or revision.state is not CalculationRevisionState.PRESENTADO
        ):
            raise DeclarationsWorkspaceProjectionError("current filing pointers or revision state contradict")
        if record.status is ModeloRecordStatus.SUPERSEDIDO:
            successor = filing_by_id.get(record.superseded_by_filing_record_id or "")
            if (
                revision.state is not CalculationRevisionState.PRESENTADO_SUPERSEDIDO
                or successor is None
                or successor.work_unit_id != record.work_unit_id
                or (
                    successor.modelo,
                    successor.filing_year,
                    successor.period,
                    successor.member_nif,
                )
                != (record.modelo, record.filing_year, record.period, record.member_nif)
            ):
                raise DeclarationsWorkspaceProjectionError("superseded filing successor is missing or contradictory")

    records_by_revision: dict[str, list[ModeloRecord]] = {}
    for record in filings:
        records_by_revision.setdefault(record.calculation_revision_id, []).append(record)
    for revision in revisions:
        matching_records = records_by_revision.get(revision.calculation_revision_id, [])
        if revision.state is CalculationRevisionState.PRESENTADO and not any(
            record.status is ModeloRecordStatus.VIGENTE for record in matching_records
        ):
            raise DeclarationsWorkspaceProjectionError("current filed revision has no current filing record")
        if revision.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO and not any(
            record.status is ModeloRecordStatus.SUPERSEDIDO for record in matching_records
        ):
            raise DeclarationsWorkspaceProjectionError("superseded revision has no superseded filing record")

    if any(fact.work_unit_id not in unit_by_id for fact in lifecycle_facts):
        raise DeclarationsWorkspaceProjectionError("lifecycle fact has no declaration")


def _declaration_rows(units: tuple[WorkUnit, ...]) -> tuple[DeclarationsWorkspaceDeclarationRefV1, ...]:
    return tuple(
        DeclarationsWorkspaceDeclarationRefV1(
            work_unit_id=unit.work_unit_id,
            modelo=unit.modelo,
            filing_year=unit.filing_year,
            period=unit.period,
            state=unit.state,
            has_current_calculation=unit.current_calculation_revision_id is not None,
            has_current_filing=unit.current_filing_record_id is not None,
        )
        for unit in sorted(
            units,
            key=lambda item: (str(item.modelo), item.filing_year, item.period.registry_token, item.work_unit_id),
        )
    )


def _revision_rows(
    revisions: tuple[CalculationRevision, ...],
    unit_by_id: dict[str, WorkUnit],
) -> tuple[DeclarationsWorkspaceCalculationRevisionRefV1, ...]:
    return tuple(
        DeclarationsWorkspaceCalculationRevisionRefV1(
            calculation_revision_id=revision.calculation_revision_id,
            work_unit_id=revision.work_unit_id,
            modelo=unit_by_id[revision.work_unit_id].modelo,
            filing_year=unit_by_id[revision.work_unit_id].filing_year,
            period=unit_by_id[revision.work_unit_id].period,
            state=revision.state,
            created_at=revision.created_at,
            updated_at=revision.updated_at,
            is_current=unit_by_id[revision.work_unit_id].current_calculation_revision_id
            == revision.calculation_revision_id,
            is_filed=unit_by_id[revision.work_unit_id].filed_calculation_revision_id
            == revision.calculation_revision_id,
        )
        for revision in sorted(
            revisions,
            key=lambda item: (
                str(unit_by_id[item.work_unit_id].modelo),
                unit_by_id[item.work_unit_id].filing_year,
                unit_by_id[item.work_unit_id].period.registry_token,
                item.created_at,
                item.calculation_revision_id,
            ),
        )
    )


def _filing_rows(filings: tuple[ModeloRecord, ...]) -> tuple[DeclarationsWorkspaceFilingRefV1, ...]:
    return tuple(
        DeclarationsWorkspaceFilingRefV1(
            filing_record_id=record.filing_record_id,
            work_unit_id=record.work_unit_id,
            calculation_revision_id=record.calculation_revision_id,
            modelo=record.modelo,
            filing_year=record.filing_year,
            period=record.period,
            filed_at=record.filed_at,
            local_status=record.status,
            aeat_accepted=record.aeat_accepted,
            evidence_kind=record.external_evidence.kind if record.external_evidence is not None else None,
        )
        for record in sorted(
            filings,
            key=lambda item: (
                str(item.modelo),
                item.filing_year,
                item.period.registry_token,
                item.filed_at,
                item.filing_record_id,
            ),
        )
    )


def _lifecycle_rows(
    facts: tuple[DeclarationsSanitizedLifecycleFactV1, ...],
    unit_by_id: dict[str, WorkUnit],
) -> tuple[DeclarationsWorkspaceLifecycleRefV1, ...]:
    return tuple(
        DeclarationsWorkspaceLifecycleRefV1(
            fact_id=fact.fact_id,
            work_unit_id=fact.work_unit_id,
            modelo=unit_by_id[fact.work_unit_id].modelo,
            filing_year=unit_by_id[fact.work_unit_id].filing_year,
            period=unit_by_id[fact.work_unit_id].period,
            occurred_at=fact.occurred_at,
            kind=fact.kind,
        )
        for fact in sorted(facts, key=lambda item: (item.occurred_at, item.fact_id))
    )


__all__ = [
    "DECLARATIONS_WORKSPACE_CONTRACT_VERSION",
    "DeclarationsLifecycleKind",
    "DeclarationsSanitizedLifecycleFactV1",
    "DeclarationsWorkspaceAvailability",
    "DeclarationsWorkspaceCalculationRevisionRefV1",
    "DeclarationsWorkspaceDeclarationRefV1",
    "DeclarationsWorkspaceFilingRefV1",
    "DeclarationsWorkspaceLifecycleRefV1",
    "DeclarationsWorkspaceProjectionError",
    "DeclarationsWorkspaceProjectionV1",
    "DeclarationsWorkspaceSource",
    "DeclarationsWorkspaceZone",
    "DeclarationsWorkspaceZoneObservationV1",
    "DeclarationsWorkspaceZoneStateV1",
    "project_declarations_workspace",
]
