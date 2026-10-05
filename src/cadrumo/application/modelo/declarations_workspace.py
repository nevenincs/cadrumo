"""Compose safe declaration rows from coherent preloaded catalogues.

Core types: :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`,
:class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

from ...core.identity.bucket import BucketId
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
)
from ...domain.modelos.filing_record import (
    ModeloRecord,
    ModeloRecordCatalogue,
)
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from .declarations_workspace_contracts import (
    DeclarationResultCasillaReaderV1,
    DeclarationsSanitizedLifecycleFactV1,
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceCalculationRevisionRefV1,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceFilingRefV1,
    DeclarationsWorkspaceLifecycleRefV1,
    DeclarationsWorkspaceProjectionError,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceSource,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneObservationV1,
    DeclarationsWorkspaceZoneStateV1,
    SettledResultRevisionV1,
    SettledResultUnitV1,
)
from .declarations_workspace_joins import validate_declarations_catalogue_joins

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


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


def _validate_current_revisions(
    revisions: tuple[CalculationRevision, ...],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    from .calculation_revision_gate import require_calculation_revision_coordinates_current

    for revision in revisions:
        require_calculation_revision_coordinates_current(revision, operation=operation)


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
    operation: PinnedAuthorityOperation,
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
    _validate_current_revisions(revisions, operation=operation)
    filings = tuple(filing_records.records.values())
    validate_declarations_catalogue_joins(
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
            origin=record.origin,
            confirmation=record.confirmation,
            declaration_kind=record.declaration_kind,
            amends_filing_record_id=record.amends_filing_record_id,
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
