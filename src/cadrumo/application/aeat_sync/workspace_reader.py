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

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

from ..operations.models import OperationDefinitionId
from ..operations.registry import OperationFrontendProjection
from ..operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from ..operator_actions.models import ActionReference
from ..user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS
from .workspace import (
    AeatSyncAeatObservationState,
    AeatSyncCensusCategory,
    AeatSyncCensusStatus,
    AeatSyncDiscrepancyKind,
    AeatSyncJustificanteState,
    AeatSyncLocalFilingState,
    AeatSyncOverviewArea,
    AeatSyncSourceState,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceCensusRowV1,
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
"""No local authority produces these rows at all.

True of LOCAL_RECONCILIATION: nothing in the codebase records local
reconciliation decisions, so there is nothing for a session to read.
"""

_READER_NOT_COMPOSED: Final[str] = "workbench.aeat_sync.local_reader_not_composed"
"""The authority EXISTS but this session does not read it.

Distinct from `_NO_LOCAL_ROW_READER`, which claims no reader exists, and from
`_NEVER_PULLED`, which claims nothing has been captured. Both would be false of
LOCAL_NOTIFICATION_CUSTODY: `NotificationDocumentService.list_documents` reads
local custody and answers before any pull -- with an empty tuple when custody
is empty, which is a proven zero rather than an absence. Naming it a missing
reader points whoever picks this up at writing one that is already written; the
gap is composition, and saying so is the difference between a task and a
wild-goose chase."""

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


_LOCAL_REFUSALS: Final[dict[AeatSyncWorkspaceSource, str]] = {
    AeatSyncWorkspaceSource.LOCAL_NOTIFICATION_CUSTODY: _READER_NOT_COMPOSED,
}
"""Sources whose refusal is a composition gap rather than a missing authority."""


def _local_observation(
    source: AeatSyncWorkspaceSource,
    *,
    observed_at: UtcInstant,
    item_count: int | None,
    refusal: str = _NO_LOCAL_ROW_READER,
) -> AeatSyncWorkspaceSourceObservationV1:
    if item_count is None:
        return AeatSyncWorkspaceSourceObservationV1(
            source=source,
            availability=AeatSyncWorkspaceAvailability.UNAVAILABLE,
            refusal=refusal,
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
    custody_count: int | None,
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
        AeatSyncWorkspaceSource.LOCAL_NOTIFICATION_CUSTODY: custody_count,
        AeatSyncWorkspaceSource.LOCAL_RECONCILIATION: None,
    }
    return _local_observation(
        source,
        observed_at=observed_at,
        item_count=counts[source],
        refusal=_LOCAL_REFUSALS.get(source, _NO_LOCAL_ROW_READER),
    )


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


_LOCALLY_READ_AREAS: Final[frozenset[AeatSyncOverviewArea]] = frozenset(
    {
        AeatSyncOverviewArea.CENSUS,
        AeatSyncOverviewArea.FILED_DECLARATIONS,
        AeatSyncOverviewArea.EVIDENCE_COMPARISON,
    }
)
"""Areas whose local authority this session actually reads.

Census reads the authenticated profile record; filed declarations and evidence
comparison both declare local.filings as their local source, and the door loads
that catalogue. Notifications and reconciliation have no local reader here, so
their local side is genuinely unobserved rather than observed-and-empty.
"""


def _local_area_is_populated(area: AeatSyncOverviewArea, *, filing_count: int) -> bool:
    """Whether the local authority this area reads holds anything."""
    if area is AeatSyncOverviewArea.CENSUS:
        # The profile record exists by construction: the session authenticated
        # against it before any of this ran.
        return True
    return filing_count > 0


def _overview_row(
    area: AeatSyncOverviewArea,
    *,
    observed_at: UtcInstant,
    filing_count: int,
    contracts: OperationPublicContractSetV1,
) -> AeatSyncWorkspaceOverviewRowV1:
    """State only what the local side genuinely observed for this area.

    The AEAT side is never observed before a pull, so every area's comparison
    is UNOBSERVED.

    The local side is a THREE-way answer, not two. An area whose local source
    this session read reports PRESENT when it holds records and ABSENT when it
    genuinely holds none -- an observed zero. NOT_OBSERVED is reserved for an
    area whose local authority was never read at all. Collapsing the observed
    zero into NOT_OBSERVED would report a source the session did read as one it
    did not, and would contradict this projection's own source observation,
    which already says available with a count of zero.
    """
    local_state = AeatSyncSourceState.NOT_OBSERVED
    local_observed_at = None
    if area in _LOCALLY_READ_AREAS:
        local_state = (
            AeatSyncSourceState.PRESENT
            if _local_area_is_populated(area, filing_count=filing_count)
            else AeatSyncSourceState.ABSENT
        )
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



_CENSUS_FIELD_CATEGORIES: Final[dict[str, AeatSyncCensusCategory]] = {
    "contact.fiscal_address": AeatSyncCensusCategory.ADDRESS,
    "contact.postcode": AeatSyncCensusCategory.ADDRESS,
    "contact.fiscal_address_cadastral_reference": AeatSyncCensusCategory.ADDRESS,
}
"""Which censo field each comparable path belongs to.

Keyed by `CENSAL_ADOPTABLE_PATHS` rather than by a list written here, because
that tuple is the authority on which profile paths an AEAT censal read can
speak to at all. Inventing a wider set would produce rows that a real pull
could never fill, and the module-load check below fails the moment the two
drift apart -- a path added there and forgotten here is otherwise a row that
silently disappears from the operator's census.
"""

if set(_CENSUS_FIELD_CATEGORIES) != set(CENSAL_ADOPTABLE_PATHS):  # pragma: no cover - guarded at import
    raise RuntimeError("census categories and the censal adoptable paths disagree")


def _census_rows(
    *,
    bucket_id: str,
    subject_key: str,
    censo_values: Mapping[str, str],
    contracts: OperationPublicContractSetV1,
) -> tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceCensusRowV1], ...]:
    """Show what the profile holds for each censo-comparable field, uncompared.

    One row per path in `CENSAL_ADOPTABLE_PATHS`, always -- including the paths
    the profile leaves empty. A field the operator has not filled in is exactly
    the field a censo pull is most likely to change, so dropping its row would
    hide the comparison worth making from the surface whose job is to offer it.

    The local side distinguishes two things the projection would otherwise
    conflate. A path the record carries is its value. A path the record does
    not carry is the empty string -- OBSERVED and blank, because the profile
    was read and genuinely holds nothing there. Neither is `None`, which on
    this row means nobody looked, and nobody-looked is false of a record this
    session read to build the row in the first place.

    The AEAT side is `None` on every row and the status is NOT_COMPARED,
    because no pull has happened. That pairing is enforced on the row itself,
    so a later producer cannot leave the status behind when it starts filling
    the AEAT column in.
    """
    actions, operations = _admitted_capabilities(AeatSyncOverviewArea.CENSUS, contracts)
    return tuple(
        AeatSyncWorkspaceFactV1(
            bucket_id=bucket_id,
            subject_key=subject_key,
            row=AeatSyncWorkspaceCensusRowV1(
                path=path,
                category=_CENSUS_FIELD_CATEGORIES[path],
                status=AeatSyncCensusStatus.NOT_COMPARED,
                local_value=censo_values.get(path),  # defect: blank collapses to unobserved
                aeat_value=None,
                supported_actions=actions,
                supported_operations=operations,
            ),
        )
        for path in CENSAL_ADOPTABLE_PATHS
        if path in censo_values  # defect: blank fields dropped
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
    custody_count: int | None = None,
    censo_values: Mapping[str, str] | None = None,
) -> AeatSyncWorkspaceProjectionV1:
    """Project the pre-pull AEAT Sync workspace for one authenticated profile.

    `custody_count` is how many notification documents this profile already
    holds locally. `None` means this session did not read the store -- distinct
    from `0`, which means it read and found nothing, a proven zero the operator
    can act on.

    `censo_values` is the profile's own censo field values, keyed by schema
    path. `None` means this session did not read the profile record, and the
    census zone stays empty; an empty mapping means it read one that declares
    none of those fields, which still produces a full set of rows carrying
    observed blanks. The two are different answers and the census zone shows
    them differently.
    """
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
                        custody_count=custody_count,
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
        census=(
            ()
            if censo_values is None
            else _census_rows(
                bucket_id=bucket_id,
                subject_key=subject_key,
                censo_values=censo_values,
                contracts=operation_contracts,
            )
        ),
        filed_declarations=_filed_declaration_rows(
            bucket_id=bucket_id,
            subject_key=subject_key,
            filings=filings,
            contracts=operation_contracts,
        ),
    )


__all__ = ["read_local_aeat_sync_workspace_projection"]
