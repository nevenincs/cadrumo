"""Read the local-only AEAT Sync workspace an installed session starts from.

Every fact this workspace shows is either observed AT the AEAT or derived from
comparing local records against such an observation, and the decision that
governs this surface is explicit: initial load is local-only, and reaching the
AEAT is always an operator action with visible progress and result.

So the projection a session opens with reports what is genuinely local — the
profile record and the local filing records — and states, per source, why the
rest is empty. An AEAT authority is NEVER CAPTURED because nothing has been
pulled yet; a local authority with no installed row reader is UNAVAILABLE. A
zero filing count is neither of those: it is an observed zero, and it stays
distinguishable from both.

What the workspace does offer, even before a pull, are the pull actions
themselves, joined to the operation contracts the session actually composed —
which is what makes the destination worth reaching in a fresh session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ..operations.models import OperationDefinitionId
from ..operations.registry import OperationFrontendProjection
from ..operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from ..operator_actions.models import ActionReference
from .workspace import (
    AeatSyncAeatObservationState,
    AeatSyncDiscrepancyKind,
    AeatSyncJustificanteState,
    AeatSyncLocalFilingState,
    AeatSyncOverviewArea,
    AeatSyncSourceState,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceFactV1,
    AeatSyncWorkspaceFiledDeclarationRowV1,
    AeatSyncWorkspaceOverviewRowV1,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceSource,
    AeatSyncWorkspaceSourceObservationV1,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneObservationV1,
    aeat_sync_workspace_sources,
    project_aeat_sync_workspace,
)

if TYPE_CHECKING:
    from ...core.time.utc import UtcInstant
    from ...domain.modelos.filing_record import ModeloRecord
    from ..operations.registry import OperationPublicContractSetV1

_AEAT_SOURCES: Final[frozenset[AeatSyncWorkspaceSource]] = frozenset(
    {
        AeatSyncWorkspaceSource.AEAT_CENSUS,
        AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
        AeatSyncWorkspaceSource.AEAT_NOTIFICATIONS,
    }
)

_NEVER_PULLED: Final[str] = "workbench.aeat_sync.never_pulled"
_NO_LOCAL_ROW_READER: Final[str] = "workbench.aeat_sync.local_row_reader_unavailable"

_OVERVIEW_ACTIONS: Final[dict[AeatSyncOverviewArea, tuple[str, ...]]] = {
    AeatSyncOverviewArea.CENSUS: ("operator.profile.edit",),
    AeatSyncOverviewArea.FILED_DECLARATIONS: ("operator.live.filed.pull_all", "operator.modelo.filing_record.list"),
    AeatSyncOverviewArea.NOTIFICATIONS: ("operator.live.notifications.list",),
    AeatSyncOverviewArea.EVIDENCE_COMPARISON: ("operator.overview.explain",),
    AeatSyncOverviewArea.RECONCILIATION: ("operator.overview.explain",),
}
"""The catalogue actions each overview area may offer before any pull."""

_OVERVIEW_OPERATIONS: Final[dict[AeatSyncOverviewArea, tuple[str, ...]]] = {
    AeatSyncOverviewArea.CENSUS: ("user-profile.censo-review",),
    AeatSyncOverviewArea.FILED_DECLARATIONS: ("live.filed-history.pull",),
    AeatSyncOverviewArea.NOTIFICATIONS: (),
    AeatSyncOverviewArea.EVIDENCE_COMPARISON: ("live.filed-history.pull",),
    AeatSyncOverviewArea.RECONCILIATION: (),
}


def _local_observation(
    source: AeatSyncWorkspaceSource,
    *,
    observed_at: UtcInstant,
    item_count: int | None,
) -> AeatSyncWorkspaceSourceObservationV1:
    if item_count is None:
        return AeatSyncWorkspaceSourceObservationV1(
            source=source,
            availability=AeatSyncWorkspaceAvailability.UNAVAILABLE,
            refusal=_NO_LOCAL_ROW_READER,
        )
    return AeatSyncWorkspaceSourceObservationV1(
        source=source,
        availability=AeatSyncWorkspaceAvailability.AVAILABLE,
        observed_at=observed_at,
        item_count=item_count,
    )


def _observation(
    source: AeatSyncWorkspaceSource,
    *,
    observed_at: UtcInstant,
    profile_count: int,
    filing_count: int,
) -> AeatSyncWorkspaceSourceObservationV1:
    if source in _AEAT_SOURCES:
        return AeatSyncWorkspaceSourceObservationV1(
            source=source,
            availability=AeatSyncWorkspaceAvailability.NEVER_CAPTURED,
            refusal=_NEVER_PULLED,
        )
    counts = {
        AeatSyncWorkspaceSource.LOCAL_PROFILE: profile_count,
        AeatSyncWorkspaceSource.LOCAL_FILINGS: filing_count,
        AeatSyncWorkspaceSource.LOCAL_NOTIFICATION_CUSTODY: None,
        AeatSyncWorkspaceSource.LOCAL_RECONCILIATION: None,
    }
    return _local_observation(source, observed_at=observed_at, item_count=counts[source])


def _admitted_capabilities(
    area: AeatSyncOverviewArea,
    contracts: OperationPublicContractSetV1,
) -> tuple[tuple[ActionReference, ...], tuple[OperationDefinitionId, ...]]:
    """Offer only the actions whose operations this session actually composed."""
    admitted = {
        contract.definition_id: contract
        for contract in contracts.definitions
        if OperationFrontendProjection.TUI in contract.permitted_frontends
    }
    operations = tuple(
        definition_id for definition_id in admitted if str(definition_id) in set(_OVERVIEW_OPERATIONS[area])
    )
    joined_actions = tuple(
        reference for definition_id in operations if (reference := admitted[definition_id].action_reference) is not None
    )
    actions = tuple(
        ActionReference(action_id=OPERATOR_ACTION_CATALOGUE.lookup(action_id).action_id)
        for action_id in _OVERVIEW_ACTIONS[area]
        if action_id not in {"operator.live.filed.pull", "operator.live.filed.pull_all"}
        or any(str(joined.action_id) == action_id for joined in joined_actions)
    )
    return actions, operations


def _overview_row(
    area: AeatSyncOverviewArea,
    *,
    observed_at: UtcInstant,
    filing_count: int,
    contracts: OperationPublicContractSetV1,
) -> AeatSyncWorkspaceOverviewRowV1:
    """State only what the local side genuinely observed for this area.

    The AEAT side is never observed before a pull, so every area's comparison
    is UNOBSERVED. Census is the one area whose local side is a fact the
    session already holds: the profile record it authenticated against.
    """
    local_state = AeatSyncSourceState.NOT_OBSERVED
    local_observed_at = None
    if area is AeatSyncOverviewArea.CENSUS or (area is AeatSyncOverviewArea.FILED_DECLARATIONS and filing_count):
        local_state = AeatSyncSourceState.PRESENT
        local_observed_at = observed_at
    actions, operations = _admitted_capabilities(area, contracts)
    return AeatSyncWorkspaceOverviewRowV1(
        area=area,
        local_state=local_state,
        aeat_state=AeatSyncSourceState.NOT_OBSERVED,
        local_observed_at=local_observed_at,
        discrepancy_kind=AeatSyncDiscrepancyKind.UNOBSERVED,
        supported_actions=actions,
        supported_operations=operations,
    )



def _filed_declaration_rows(
    *,
    bucket_id: str,
    subject_key: str,
    filings: tuple[ModeloRecord, ...],
    contracts: OperationPublicContractSetV1,
) -> tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceFiledDeclarationRowV1], ...]:
    """Show what this profile filed locally, with the AEAT side unobserved.

    The local half of this comparison is a fact the session already holds, and
    withholding it until a pull happens would understate what the operator has
    done. The AEAT half is NOT OBSERVED until they pull, and the justificante
    with it -- a receipt cannot be confident about a submission nobody has
    looked for.

    One row per address. A superseded record and its replacement describe the
    same declaration, so the row carries the LATEST filing for each address
    rather than one row per revision.
    """
    actions, operations = _admitted_capabilities(AeatSyncOverviewArea.FILED_DECLARATIONS, contracts)
    latest: dict[tuple[str, int, str], ModeloRecord] = {}
    for record in filings:
        key = (str(record.modelo), int(record.filing_year), record.period.registry_token)
        current = latest.get(key)
        if current is None or record.filed_at > current.filed_at:
            latest[key] = record
    return tuple(
        AeatSyncWorkspaceFactV1(
            bucket_id=bucket_id,
            subject_key=subject_key,
            row=AeatSyncWorkspaceFiledDeclarationRowV1(
                modelo=record.modelo,
                filing_year=record.filing_year,
                period=record.period,
                local_filing_state=AeatSyncLocalFilingState.FILED,
                local_filed_at=record.filed_at,
                aeat_observation_state=AeatSyncAeatObservationState.NOT_OBSERVED,
                justificante_state=AeatSyncJustificanteState.NOT_OBSERVED,
                supported_actions=actions,
                supported_operations=operations,
            ),
        )
        for record in sorted(latest.values(), key=lambda item: (str(item.modelo), item.filing_year))
    )


def read_local_aeat_sync_workspace_projection(
    *,
    bucket_id: str,
    subject_key: str,
    observed_at: UtcInstant,
    filings: tuple[ModeloRecord, ...],
    operation_contracts: OperationPublicContractSetV1,
) -> AeatSyncWorkspaceProjectionV1:
    """Project the pre-pull AEAT Sync workspace for one authenticated profile."""
    return project_aeat_sync_workspace(
        bucket_id=bucket_id,
        subject_key=subject_key,
        zone_observations=tuple(
            AeatSyncWorkspaceZoneObservationV1(
                zone=zone,
                sources=tuple(
                    _observation(
                        source,
                        observed_at=observed_at,
                        profile_count=1,
                        filing_count=len(filings),
                    )
                    for source in aeat_sync_workspace_sources(zone)
                ),
            )
            for zone in AeatSyncWorkspaceZone
        ),
        action_catalogue=OPERATOR_ACTION_CATALOGUE,
        operation_contracts=operation_contracts,
        overview=tuple(
            AeatSyncWorkspaceFactV1(
                bucket_id=bucket_id,
                subject_key=subject_key,
                row=_overview_row(
                    area,
                    observed_at=observed_at,
                    filing_count=len(filings),
                    contracts=operation_contracts,
                ),
            )
            for area in AeatSyncOverviewArea
        ),
        filed_declarations=_filed_declaration_rows(
            bucket_id=bucket_id,
            subject_key=subject_key,
            filings=filings,
            contracts=operation_contracts,
        ),
    )


__all__ = ["read_local_aeat_sync_workspace_projection"]
