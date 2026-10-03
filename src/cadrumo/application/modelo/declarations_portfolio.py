"""Isolate declaration read failures while reusing the strict catalogue projector."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.errors.hierarchy import CadrumoError
from ...core.identity.bucket import BucketId
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.filing_record import ModeloRecordCatalogue
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from .declaration_summary import DeclarationSummary, DeclarationSummaryState
from .declaration_targets import declaration_targets
from .declarations_workspace import (
    DeclarationResultCasillaReaderV1,
    DeclarationsSanitizedLifecycleFactV1,
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceCalculationRevisionRefV1,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceFilingRefV1,
    DeclarationsWorkspaceLifecycleRefV1,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneObservationV1,
    project_declarations_workspace,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


def project_declarations_portfolio(
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
    """Keep each row visible; invalid joins or registry coordinates refuse only that row.

    The strict projector still admits every readable partition. A refused
    declaration carries only its natural address and an unreadable summary;
    its calculation, amount and filing history never become trusted facts.
    """
    empty = project_declarations_workspace(
        operation=operation,
        bucket_id=bucket_id,
        work_units=WorkUnitCatalogue(),
        calculation_revisions=CalculationRevisionCatalogue(),
        filing_records=ModeloRecordCatalogue(),
        lifecycle_facts=(),
        zone_observations=zone_observations,
    )
    declarations: list[DeclarationsWorkspaceDeclarationRefV1] = []
    revisions: list[DeclarationsWorkspaceCalculationRevisionRefV1] = []
    filings: list[DeclarationsWorkspaceFilingRefV1] = []
    lifecycle: list[DeclarationsWorkspaceLifecycleRefV1] = []
    refused = False
    declarations_observable = empty.zones[0].availability in {
        DeclarationsWorkspaceAvailability.AVAILABLE,
        DeclarationsWorkspaceAvailability.STALE,
    }
    for unit in work_units.values():
        try:
            # Read copies can bypass Pydantic construction. Re-run the owning
            # identity validator before trusting the row's joins or amount.
            WorkUnit.model_validate(unit.model_dump(mode="python"))
            part = project_declarations_workspace(
                operation=operation,
                bucket_id=bucket_id,
                work_units=WorkUnitCatalogue(work_units={unit.work_unit_id: unit}),
                calculation_revisions=CalculationRevisionCatalogue(
                    revisions={
                        key: item
                        for key, item in calculation_revisions.revisions.items()
                        if item.work_unit_id == unit.work_unit_id
                    }
                ),
                filing_records=ModeloRecordCatalogue(
                    records={
                        key: item
                        for key, item in filing_records.records.items()
                        if item.work_unit_id == unit.work_unit_id
                    }
                ),
                lifecycle_facts=tuple(item for item in lifecycle_facts if item.work_unit_id == unit.work_unit_id),
                zone_observations=zone_observations,
                result_casilla_reader=result_casilla_reader,
            )
        except (CadrumoError, ValueError, LookupError) as exc:
            refused = True
            if not declarations_observable:
                continue
            declarations.append(
                DeclarationsWorkspaceDeclarationRefV1(
                    work_unit_id=unit.work_unit_id,
                    modelo=unit.modelo,
                    filing_year=unit.filing_year,
                    period=unit.period,
                    state=unit.state,
                    has_current_calculation=unit.current_calculation_revision_id is not None,
                    has_current_filing=unit.current_filing_record_id is not None,
                    summary=DeclarationSummary(state=DeclarationSummaryState.UNREADABLE, technical_reason=str(exc)),
                )
            )
        else:
            declarations.extend(part.declarations)
            revisions.extend(part.calculation_revisions)
            filings.extend(part.filings)
            lifecycle.extend(part.lifecycle)
    # Orphaned history cannot disappear into a false complete history claim.
    known = frozenset(work_units.work_units)
    refused |= any(item.work_unit_id not in known for item in calculation_revisions.values())
    refused |= any(item.work_unit_id not in known for item in filing_records.records.values())
    refused |= any(item.work_unit_id not in known for item in lifecycle_facts)
    counts = {
        DeclarationsWorkspaceZone.DECLARATIONS: len(declarations),
        DeclarationsWorkspaceZone.CALCULATION_REVISIONS: len(revisions),
        DeclarationsWorkspaceZone.FILING_HISTORY: len(filings) + len(lifecycle),
    }
    zones = tuple(
        zone.model_copy(
            update={
                "item_count": counts[zone.zone],
                **(
                    {
                        "availability": DeclarationsWorkspaceAvailability.STALE,
                        "reason_code": "workbench.declarations.partial_read",
                    }
                    if refused
                    else {}
                ),
            }
        )
        if zone.availability in {DeclarationsWorkspaceAvailability.AVAILABLE, DeclarationsWorkspaceAvailability.STALE}
        else zone
        for zone in empty.zones
    )
    return DeclarationsWorkspaceProjectionV1(
        bucket_id=bucket_id,
        zones=zones,
        declarations=tuple(declarations),
        calculation_revisions=tuple(revisions),
        filings=tuple(filings),
        lifecycle=tuple(lifecycle),
        creation_targets=declaration_targets(operation),
    )
