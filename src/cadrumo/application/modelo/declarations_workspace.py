"""Pure, frontend-neutral projection for the Declarations workspace.

Callers preload the secure Modelo catalogues and provide explicit source
observations.  This module validates their joins and projects only natural
declaration coordinates, lifecycle states, and non-sensitive timestamps.  It
does not resolve repositories, contact AEAT, or retain financial/evidence
payloads for serialization.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar, Final, Protocol, Self

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.casilla_id import CasillaId
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

    __bare_base_rationale__: ClassVar[str] = (
        "internal Declarations projector-integrity carrier; "
        "SecureProfileWorkbenchGenerationReadDoorV1.read_workbench_generation_inputs "
        "converts it into the unavailable Declarations source result"
    )


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
    """Sanitized lifecycle meanings accepted by the workspace projection.

    ``VERIFICATION_REFUSED`` exists because a refusal has nowhere else honest to
    go. Without it a surface reading the kind alone would either drop the event,
    which turns a refusal into an absence, or fold it into ``VERIFIED``, which
    reports a refused verification as a passed one.
    """

    CREATED = "created"
    RENAMED = "renamed"
    CALCULATED = "calculated"
    VERIFIED = "verified"
    VERIFICATION_REFUSED = "verification_refused"
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
    settled_result: str | None = None
    """The declaration's own settled figure, when the registry grounds one.

    `None` means the answer is UNKNOWN, and a surface must render it that way
    rather than as a blank or a zero. Three distinct situations reach it, and
    none of them is "the result is nothing": the modelo's settlement chain is
    not modelled (303 and 130 today declare no result role at all), no current
    calculation exists yet, or the calculation exists and has not computed that
    cell.
    """

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


def _validate_current_revisions(revisions: tuple[CalculationRevision, ...]) -> None:
    from .calculation_revision_gate import require_calculation_revision_coordinates_current

    for revision in revisions:
        require_calculation_revision_coordinates_current(revision)


def _observable_zones(
    observations: Mapping[DeclarationsWorkspaceZone, DeclarationsWorkspaceZoneObservationV1],
) -> set[DeclarationsWorkspaceZone]:
    return {
        zone
        for zone, observation in observations.items()
        if observation.availability
        in {DeclarationsWorkspaceAvailability.AVAILABLE, DeclarationsWorkspaceAvailability.STALE}
    }


def _declaration_rows_if_observable(
    observable: set[DeclarationsWorkspaceZone],
    units: tuple[WorkUnit, ...],
    revisions: tuple[CalculationRevision, ...],
    result_casilla_reader: DeclarationResultCasillaReaderV1 | None,
) -> tuple[DeclarationsWorkspaceDeclarationRefV1, ...]:
    if DeclarationsWorkspaceZone.DECLARATIONS not in observable:
        return ()
    return _declaration_rows(units, revisions, result_casilla_reader)


def _revision_rows_if_observable(
    observable: set[DeclarationsWorkspaceZone],
    revisions: tuple[CalculationRevision, ...],
    units: tuple[WorkUnit, ...],
) -> tuple[DeclarationsWorkspaceCalculationRevisionRefV1, ...]:
    if DeclarationsWorkspaceZone.CALCULATION_REVISIONS not in observable:
        return ()
    return _revision_rows(revisions, {unit.work_unit_id: unit for unit in units})


def _filing_history_rows_if_observable(
    observable: set[DeclarationsWorkspaceZone],
    filings: tuple[ModeloRecord, ...],
    lifecycle_facts: tuple[DeclarationsSanitizedLifecycleFactV1, ...],
    units: tuple[WorkUnit, ...],
) -> tuple[tuple[DeclarationsWorkspaceFilingRefV1, ...], tuple[DeclarationsWorkspaceLifecycleRefV1, ...]]:
    if DeclarationsWorkspaceZone.FILING_HISTORY not in observable:
        return (), ()
    filing_rows = _filing_rows(filings)
    unit_by_id = {unit.work_unit_id: unit for unit in units}
    lifecycle_rows = _lifecycle_rows(lifecycle_facts, unit_by_id)
    return filing_rows, lifecycle_rows


def _zone_item_counts(
    declaration_rows: tuple[DeclarationsWorkspaceDeclarationRefV1, ...],
    revision_rows: tuple[DeclarationsWorkspaceCalculationRevisionRefV1, ...],
    filing_rows: tuple[DeclarationsWorkspaceFilingRefV1, ...],
    lifecycle_rows: tuple[DeclarationsWorkspaceLifecycleRefV1, ...],
) -> dict[DeclarationsWorkspaceZone, int]:
    return {
        DeclarationsWorkspaceZone.DECLARATIONS: len(declaration_rows),
        DeclarationsWorkspaceZone.CALCULATION_REVISIONS: len(revision_rows),
        DeclarationsWorkspaceZone.FILING_HISTORY: len(filing_rows) + len(lifecycle_rows),
    }


def _zone_states(
    observations: Mapping[DeclarationsWorkspaceZone, DeclarationsWorkspaceZoneObservationV1],
    observable: set[DeclarationsWorkspaceZone],
    declaration_rows: tuple[DeclarationsWorkspaceDeclarationRefV1, ...],
    revision_rows: tuple[DeclarationsWorkspaceCalculationRevisionRefV1, ...],
    filing_rows: tuple[DeclarationsWorkspaceFilingRefV1, ...],
    lifecycle_rows: tuple[DeclarationsWorkspaceLifecycleRefV1, ...],
) -> tuple[DeclarationsWorkspaceZoneStateV1, ...]:
    counts = _zone_item_counts(declaration_rows, revision_rows, filing_rows, lifecycle_rows)
    return tuple(
        DeclarationsWorkspaceZoneStateV1(
            **observations[zone].model_dump(),
            sources=_SOURCES_BY_ZONE[zone],
            item_count=counts[zone] if zone in observable else None,
        )
        for zone in DeclarationsWorkspaceZone
    )


def project_declarations_workspace(
    *,
    bucket_id: BucketId,
    work_units: WorkUnitCatalogue,
    calculation_revisions: CalculationRevisionCatalogue,
    filing_records: ModeloRecordCatalogue,
    lifecycle_facts: tuple[DeclarationsSanitizedLifecycleFactV1, ...],
    zone_observations: tuple[DeclarationsWorkspaceZoneObservationV1, ...],
    result_casilla_reader: DeclarationResultCasillaReaderV1 | None = None,
) -> DeclarationsWorkspaceProjectionV1:
    """Validate and safely project already-loaded local authorities."""
    observations = _validate_observations(zone_observations)
    units = tuple(work_units.values())
    revisions = tuple(calculation_revisions.values())
    _validate_current_revisions(revisions)
    filings = tuple(filing_records.records.values())
    _validate_catalogue_joins(
        bucket_id=bucket_id,
        units=units,
        revisions=revisions,
        filings=filings,
        lifecycle_facts=lifecycle_facts,
    )

    observable = _observable_zones(observations)
    declaration_rows = _declaration_rows_if_observable(
        observable,
        units,
        revisions,
        result_casilla_reader,
    )
    revision_rows = _revision_rows_if_observable(
        observable,
        revisions,
        units,
    )
    filing_rows, lifecycle_rows = _filing_history_rows_if_observable(
        observable,
        filings,
        lifecycle_facts,
        units,
    )
    zones = _zone_states(
        observations,
        observable,
        declaration_rows,
        revision_rows,
        filing_rows,
        lifecycle_rows,
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
    _validate_work_catalogue(bucket_id, units)
    _validate_unique_lifecycle_facts(lifecycle_facts)
    _validate_revisions_have_declarations(revisions, unit_by_id)
    _validate_declaration_pointers(units, revision_by_id, filing_by_id)
    _validate_filing_records(bucket_id, filings, unit_by_id, revision_by_id, filing_by_id)
    _validate_revision_filing_records(revisions, filings)
    _validate_lifecycle_fact_declarations(lifecycle_facts, unit_by_id)


def _validate_work_catalogue(bucket_id: BucketId, units: tuple[WorkUnit, ...]) -> None:
    if any(unit.bucket_id != bucket_id for unit in units):
        raise DeclarationsWorkspaceProjectionError("work catalogue contains a foreign bucket")
    natural_addresses = tuple((unit.modelo, unit.filing_year, unit.period) for unit in units)
    if len(natural_addresses) != len(set(natural_addresses)):
        raise DeclarationsWorkspaceProjectionError("work catalogue contains duplicate declaration addresses")


def _validate_unique_lifecycle_facts(facts: tuple[DeclarationsSanitizedLifecycleFactV1, ...]) -> None:
    if len({fact.fact_id for fact in facts}) != len(facts):
        raise DeclarationsWorkspaceProjectionError("lifecycle facts contain duplicate identities")


def _validate_revisions_have_declarations(
    revisions: tuple[CalculationRevision, ...],
    unit_by_id: Mapping[str, WorkUnit],
) -> None:
    for revision in revisions:
        if revision.work_unit_id not in unit_by_id:
            raise DeclarationsWorkspaceProjectionError("calculation revision has no declaration")


def _validate_declaration_pointers(
    units: tuple[WorkUnit, ...],
    revision_by_id: Mapping[str, CalculationRevision],
    filing_by_id: Mapping[str, ModeloRecord],
) -> None:
    for unit in units:
        _validate_declaration_revision_pointers(unit, revision_by_id)
        _validate_declaration_filing_pointers(unit, revision_by_id, filing_by_id)


def _validate_declaration_revision_pointers(
    unit: WorkUnit,
    revision_by_id: Mapping[str, CalculationRevision],
) -> None:
    for revision_id in (unit.current_calculation_revision_id, unit.filed_calculation_revision_id):
        if revision_id is None:
            continue
        revision = revision_by_id.get(revision_id)
        if revision is None or revision.work_unit_id != unit.work_unit_id:
            raise DeclarationsWorkspaceProjectionError("declaration revision pointer is missing or contradictory")


def _validate_declaration_filing_pointers(
    unit: WorkUnit,
    revision_by_id: Mapping[str, CalculationRevision],
    filing_by_id: Mapping[str, ModeloRecord],
) -> None:
    filed_revision_id = unit.filed_calculation_revision_id
    current_filing_id = unit.current_filing_record_id
    if (filed_revision_id is None) != (current_filing_id is None):
        raise DeclarationsWorkspaceProjectionError("declaration filing pointers must be present or absent together")
    if filed_revision_id is None or current_filing_id is None:
        return
    revision = revision_by_id.get(filed_revision_id)
    record = filing_by_id.get(current_filing_id)
    if not _is_current_filing_pointer(unit, revision, record):
        raise DeclarationsWorkspaceProjectionError("declaration filing pointers do not resolve to one current filing")


def _is_current_filing_pointer(
    unit: WorkUnit,
    revision: CalculationRevision | None,
    record: ModeloRecord | None,
) -> bool:
    return (
        revision is not None
        and record is not None
        and revision.work_unit_id == unit.work_unit_id
        and record.work_unit_id == unit.work_unit_id
        and record.calculation_revision_id == revision.calculation_revision_id
        and record.status is ModeloRecordStatus.VIGENTE
        and revision.state is CalculationRevisionState.PRESENTADO
    )


def _validate_filing_records(
    bucket_id: BucketId,
    filings: tuple[ModeloRecord, ...],
    unit_by_id: Mapping[str, WorkUnit],
    revision_by_id: Mapping[str, CalculationRevision],
    filing_by_id: Mapping[str, ModeloRecord],
) -> None:
    for record in filings:
        _validate_filing_record(bucket_id, record, unit_by_id, revision_by_id, filing_by_id)


def _validate_filing_record(
    bucket_id: BucketId,
    record: ModeloRecord,
    unit_by_id: Mapping[str, WorkUnit],
    revision_by_id: Mapping[str, CalculationRevision],
    filing_by_id: Mapping[str, ModeloRecord],
) -> None:
    unit = unit_by_id.get(record.work_unit_id)
    revision = revision_by_id.get(record.calculation_revision_id)
    if record.bucket_id != bucket_id or unit is None or revision is None:
        raise DeclarationsWorkspaceProjectionError("filing record has no same-bucket declaration and revision")
    if revision.work_unit_id != unit.work_unit_id:
        raise DeclarationsWorkspaceProjectionError("filing revision belongs to another declaration")
    if (record.modelo, record.filing_year, record.period) != (unit.modelo, unit.filing_year, unit.period):
        raise DeclarationsWorkspaceProjectionError("filing address contradicts its declaration")
    if record.status is ModeloRecordStatus.VIGENTE and not _record_is_current(unit, revision, record):
        raise DeclarationsWorkspaceProjectionError("current filing pointers or revision state contradict")
    if record.status is ModeloRecordStatus.SUPERSEDIDO and not _record_has_valid_successor(
        record, revision, filing_by_id
    ):
        raise DeclarationsWorkspaceProjectionError("superseded filing successor is missing or contradictory")


def _record_is_current(unit: WorkUnit, revision: CalculationRevision, record: ModeloRecord) -> bool:
    return (
        unit.current_filing_record_id == record.filing_record_id
        and unit.filed_calculation_revision_id == record.calculation_revision_id
        and revision.state is CalculationRevisionState.PRESENTADO
    )


def _record_has_valid_successor(
    record: ModeloRecord,
    revision: CalculationRevision,
    filing_by_id: Mapping[str, ModeloRecord],
) -> bool:
    successor = filing_by_id.get(record.superseded_by_filing_record_id or "")
    return (
        revision.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO
        and successor is not None
        and successor.work_unit_id == record.work_unit_id
        and (
            successor.modelo,
            successor.filing_year,
            successor.period,
            successor.member_nif,
        )
        == (record.modelo, record.filing_year, record.period, record.member_nif)
    )


def _validate_revision_filing_records(
    revisions: tuple[CalculationRevision, ...],
    filings: tuple[ModeloRecord, ...],
) -> None:
    records_by_revision: dict[str, list[ModeloRecord]] = {}
    for record in filings:
        records_by_revision.setdefault(record.calculation_revision_id, []).append(record)
    for revision in revisions:
        _validate_revision_filing_record(revision, records_by_revision)


def _validate_revision_filing_record(
    revision: CalculationRevision,
    records_by_revision: Mapping[str, list[ModeloRecord]],
) -> None:
    matching_records = records_by_revision.get(revision.calculation_revision_id, [])
    if revision.state is CalculationRevisionState.PRESENTADO and not _has_record_status(
        matching_records, ModeloRecordStatus.VIGENTE
    ):
        raise DeclarationsWorkspaceProjectionError("current filed revision has no current filing record")
    if revision.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO and not _has_record_status(
        matching_records, ModeloRecordStatus.SUPERSEDIDO
    ):
        raise DeclarationsWorkspaceProjectionError("superseded revision has no superseded filing record")


def _has_record_status(records: list[ModeloRecord], status: ModeloRecordStatus) -> bool:
    return any(record.status is status for record in records)


def _validate_lifecycle_fact_declarations(
    facts: tuple[DeclarationsSanitizedLifecycleFactV1, ...],
    unit_by_id: Mapping[str, WorkUnit],
) -> None:
    if any(fact.work_unit_id not in unit_by_id for fact in facts):
        raise DeclarationsWorkspaceProjectionError("lifecycle fact has no declaration")


DeclarationResultCasillaReaderV1 = Callable[[ModeloCode, int, Period], str | None]
"""Names the casilla that settles one modelo revision, or nothing.

Injected rather than resolved here: this module joins already-loaded local
authorities and holds no registry access, and giving it some would put registry
loading inside a projection that is meant to be a pure join.
"""


class SettledResultUnitV1(Protocol):
    """The work-unit surface :func:`_settled_result` actually reads.

    Declared structurally so the reader's contract is the four attributes it
    consumes rather than the whole :class:`WorkUnit` aggregate. A caller that
    can supply a modelo, year, period and current calculation id is a valid
    argument, which is what the settlement tests exercise.
    """

    @property
    def modelo(self) -> ModeloCode: ...

    @property
    def filing_year(self) -> FilingYear: ...

    @property
    def period(self) -> Period: ...

    @property
    def current_calculation_revision_id(self) -> str | None: ...


class SettledResultRevisionV1(Protocol):
    """The calculation-revision surface :func:`_settled_result` actually reads."""

    @property
    def casilla_values(self) -> Mapping[CasillaId, Decimal]: ...


def _settled_result(
    unit: SettledResultUnitV1,
    revisions_by_id: Mapping[str, SettledResultRevisionV1],
    reader: DeclarationResultCasillaReaderV1 | None,
) -> str | None:
    """Read this declaration's settled figure, or nothing when it is not known.

    Every early return is a DIFFERENT unknown, and none of them is a zero: no
    reader bound, no current calculation, a modelo whose settlement chain the
    registry does not model, or a calculation that has not computed the cell.
    They collapse to `None` because the surface renders one "not available" for
    all of them -- but nothing here may turn any of them into a number.
    """
    if reader is None or unit.current_calculation_revision_id is None:
        return None
    revision = revisions_by_id.get(unit.current_calculation_revision_id)
    if revision is None:
        return None
    casilla_id = reader(unit.modelo, unit.filing_year, unit.period)
    if casilla_id is None:
        return None
    value = revision.casilla_values.get(casilla_id)
    return None if value is None else str(value)


def _declaration_rows(
    units: tuple[WorkUnit, ...],
    revisions: tuple[CalculationRevision, ...] = (),
    result_casilla_reader: DeclarationResultCasillaReaderV1 | None = None,
) -> tuple[DeclarationsWorkspaceDeclarationRefV1, ...]:
    by_id = {revision.calculation_revision_id: revision for revision in revisions}
    return tuple(
        DeclarationsWorkspaceDeclarationRefV1(
            work_unit_id=unit.work_unit_id,
            modelo=unit.modelo,
            filing_year=unit.filing_year,
            period=unit.period,
            state=unit.state,
            has_current_calculation=unit.current_calculation_revision_id is not None,
            has_current_filing=unit.current_filing_record_id is not None,
            settled_result=_settled_result(unit, by_id, result_casilla_reader),
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
