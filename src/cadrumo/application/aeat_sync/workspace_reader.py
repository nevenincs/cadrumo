"""Read the local-only AEAT Sync workspace an installed session starts from.

Every fact this workspace shows is either observed AT the AEAT or derived from
comparing local records against such an observation, and the decision that
governs this surface is explicit: initial load is local-only, and reaching the
AEAT is always an operator action with visible progress and result.

The projection restores the profile, local filing records, stored census
evidence and stored filed-declaration captures. The latter use the same
evidence join as the overview calendar. Sources without a stored capture remain
NEVER_CAPTURED; a local authority without a reader is UNAVAILABLE. Observed
zero records stay distinguishable from both.

What the workspace does offer, even before a pull, are the pull actions
themselves, joined to the operation contracts the session actually composed —
which is what makes the destination worth reaching in a fresh session.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

from ...core.errors.hierarchy import InternalInvariantError
from ...domain.modelos.codes import ModeloCode
from ..operations.models import OperationDefinitionId
from ..operations.registry import OperationFrontendProjection
from ..operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from ..operator_actions.models import ActionReference
from ..overview.calendar_models import OverviewAeatSubmissionState
from ..overview.home import HomeAvailability
from ..user_profile.censal_observation import CensalObservation
from ..user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS, censal_facts_from_read
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
    AeatSyncWorkspaceProjectionError,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceSource,
    AeatSyncWorkspaceSourceObservationV1,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneObservationV1,
    aeat_sync_workspace_sources,
    project_aeat_sync_workspace,
)

if TYPE_CHECKING:
    from ...core.period import Period
    from ...core.time.utc import UtcInstant
    from ...domain.modelos.filing_record import ModeloRecord
    from ..operations.registry import OperationPublicContractSetV1, OperationPublicDefinitionContractV1
    from ..overview.calendar_models import OverviewCalendarFilingEvidence
    from ..overview.evidence import CalendarEvidenceProjection

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
    AeatSyncOverviewArea.NOTIFICATIONS: ("live.notifications.list",),
    AeatSyncOverviewArea.EVIDENCE_COMPARISON: ("live.filed-history.pull",),
    AeatSyncOverviewArea.RECONCILIATION: (),
}

_OPERATION_ACTION_IDS: Final[frozenset[str]] = frozenset(
    {
        "operator.live.filed.pull",
        "operator.live.filed.pull_all",
        "operator.live.notifications.list",
    }
)


_LOCAL_REFUSALS: Final[dict[AeatSyncWorkspaceSource, str]] = {
    AeatSyncWorkspaceSource.LOCAL_NOTIFICATION_CUSTODY: _READER_NOT_COMPOSED,
}
"""Sources whose refusal is a composition gap rather than a missing authority."""

_AEAT_FIGURES_NOT_READ: Final[str] = "workbench.aeat_sync.aeat_figures_not_read"
"""Filed-declaration captures were read, but they hold no declaration figures.

Evidence comparison compares figures. A captured register row names a
submission, not its casilla values, so that zone's AEAT side stays unread:
reporting it observable would publish zero discrepancies for a comparison
nobody ran.
"""

_AEAT_OBSERVATION_STATES: Final[dict[OverviewAeatSubmissionState, AeatSyncAeatObservationState]] = {
    OverviewAeatSubmissionState.SUBMITTED_OBSERVED: AeatSyncAeatObservationState.SUBMITTED,
    OverviewAeatSubmissionState.ACCEPTED: AeatSyncAeatObservationState.ACCEPTED,
    # A verified receipt is carried on the justificante axis; the submission
    # axis claims no more than the register showed.
    OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED: AeatSyncAeatObservationState.SUBMITTED,
}

type _NaturalKey = tuple[str, int, str]


def _observed_filings(
    filed_evidence: CalendarEvidenceProjection | None,
) -> dict[_NaturalKey, OverviewCalendarFilingEvidence]:
    """Index the uncontested AEAT filings the shared calendar evidence join observed.

    Rows whose register evidence conflicts or raises a concern are not
    promoted: they cannot establish a submission, and this surface has no
    state that would show them as anything but observed.
    """
    if filed_evidence is None:
        return {}
    return {
        (str(row.modelo), int(row.filing_year), row.period.registry_token): row
        for row in filed_evidence.evidence
        if row.modelo is not None
        and row.filing_year is not None
        and row.period is not None
        and row.aeat_filed
        and row.aeat_submission_state in _AEAT_OBSERVATION_STATES
    }


def _filed_source_observation(
    filed_evidence: CalendarEvidenceProjection | None,
    *,
    observed_count: int,
) -> AeatSyncWorkspaceSourceObservationV1:
    """Carry the stored filed-declaration read's own availability and capture time.

    `None` means this session composed no read of the stored captures, which
    keeps the pre-pull answer. Otherwise the calendar read's availability is
    preserved: never captured, unavailable and stale stay distinct, and an
    available read with no observed filing is an observed zero.
    """
    state = None if filed_evidence is None else filed_evidence.aeat_state
    if state is None or state.availability is HomeAvailability.NEVER_CAPTURED:
        return AeatSyncWorkspaceSourceObservationV1(
            source=AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
            availability=AeatSyncWorkspaceAvailability.NEVER_CAPTURED,
            refusal=_NEVER_PULLED,
        )
    availability = AeatSyncWorkspaceAvailability(state.availability.value)
    if availability not in {AeatSyncWorkspaceAvailability.AVAILABLE, AeatSyncWorkspaceAvailability.STALE}:
        return AeatSyncWorkspaceSourceObservationV1(
            source=AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
            availability=availability,
            refusal=state.reason_code,
        )
    if state.observed_at is None:
        raise AeatSyncWorkspaceProjectionError("observed filed-declaration evidence lacks its capture time")
    return AeatSyncWorkspaceSourceObservationV1(
        source=AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
        availability=availability,
        observed_at=state.observed_at,
        refusal=state.reason_code,
        item_count=observed_count,
    )


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
    zone: AeatSyncWorkspaceZone,
    observed_at: UtcInstant,
    profile_count: int,
    filing_count: int,
    custody_count: int | None,
    census_observation: CensalObservation | None,
    filed_source: AeatSyncWorkspaceSourceObservationV1,
) -> AeatSyncWorkspaceSourceObservationV1:
    if source is AeatSyncWorkspaceSource.AEAT_CENSUS and census_observation is not None:
        return AeatSyncWorkspaceSourceObservationV1(
            source=source,
            availability=AeatSyncWorkspaceAvailability.AVAILABLE,
            observed_at=census_observation.captured_at,
            item_count=1,
        )
    if source is AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS:
        if zone is AeatSyncWorkspaceZone.EVIDENCE_COMPARISON and filed_source.observed_at is not None:
            return AeatSyncWorkspaceSourceObservationV1(
                source=source,
                availability=AeatSyncWorkspaceAvailability.UNAVAILABLE,
                refusal=_AEAT_FIGURES_NOT_READ,
            )
        return filed_source
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
    admitted = _tui_contracts(contracts)
    operations = _area_operations(area, admitted)
    joined_actions = _joined_action_references(operations, admitted)
    return _area_actions(area, joined_actions), operations


def _tui_contracts(
    contracts: OperationPublicContractSetV1,
) -> dict[OperationDefinitionId, OperationPublicDefinitionContractV1]:
    """Index the operation contracts this session can render in the TUI."""
    return {
        contract.definition_id: contract
        for contract in contracts.definitions
        if OperationFrontendProjection.TUI in contract.permitted_frontends
    }


def _area_operations(
    area: AeatSyncOverviewArea,
    admitted: Mapping[OperationDefinitionId, OperationPublicDefinitionContractV1],
) -> tuple[OperationDefinitionId, ...]:
    """Keep admitted operation IDs in registry order for one overview area."""
    area_operation_ids = set(_OVERVIEW_OPERATIONS[area])
    return tuple(definition_id for definition_id in admitted if str(definition_id) in area_operation_ids)


def _joined_action_references(
    operations: tuple[OperationDefinitionId, ...],
    admitted: Mapping[OperationDefinitionId, OperationPublicDefinitionContractV1],
) -> tuple[ActionReference, ...]:
    """Collect action references attached to the area's admitted operations."""
    return tuple(
        reference for definition_id in operations if (reference := admitted[definition_id].action_reference) is not None
    )


def _area_actions(
    area: AeatSyncOverviewArea,
    joined_actions: tuple[ActionReference, ...],
) -> tuple[ActionReference, ...]:
    """Project catalogue actions, gating pull actions on composed operations."""
    return tuple(
        ActionReference(action_id=OPERATOR_ACTION_CATALOGUE.lookup(action_id).action_id)
        for action_id in _OVERVIEW_ACTIONS[area]
        if _action_is_admitted(action_id, joined_actions)
    )


def _action_is_admitted(action_id: str, joined_actions: tuple[ActionReference, ...]) -> bool:
    """Return whether an operation-backed action has its exact operation."""
    return action_id not in _OPERATION_ACTION_IDS or any(
        str(joined.action_id) == action_id for joined in joined_actions
    )


_LOCALLY_READ_AREAS: Final[frozenset[AeatSyncOverviewArea]] = frozenset(
    {
        AeatSyncOverviewArea.CENSUS,
        AeatSyncOverviewArea.FILED_DECLARATIONS,
        AeatSyncOverviewArea.EVIDENCE_COMPARISON,
    }
)
"""Areas whose local authority this session reads unconditionally.

Census reads the authenticated profile record; filed declarations and evidence
comparison both declare local.filings as their local source, and the door loads
that catalogue.

Notifications is NOT here because whether it was read is a fact about this
session rather than about the area: custody is read when the door composed a
reader and not read when it did not, and `_locally_read_areas` decides that per
call. Reconciliation is absent outright -- nothing in the codebase records a
local reconciliation decision, so there is no authority to read.
"""


def _locally_read_areas(*, custody_count: int | None) -> frozenset[AeatSyncOverviewArea]:
    """Which areas this particular session actually read a local authority for.

    Notifications joins only when custody was read. `None` means the door
    composed no custody reader, and reporting the area as observed-and-empty
    would claim a look that never happened.
    """
    if custody_count is None:
        return _LOCALLY_READ_AREAS
    return _LOCALLY_READ_AREAS | {AeatSyncOverviewArea.NOTIFICATIONS}


def _local_area_is_populated(
    area: AeatSyncOverviewArea,
    *,
    filing_count: int,
    custody_count: int | None,
) -> bool:
    """Whether the local authority this area reads holds anything."""
    if area is AeatSyncOverviewArea.CENSUS:
        # The profile record exists by construction: the session authenticated
        # against it before any of this ran.
        return True
    if area is AeatSyncOverviewArea.NOTIFICATIONS:
        # Reached only when custody was read, so a zero here is a proven zero:
        # documents are in custody, or genuinely none are.
        return bool(custody_count)
    return filing_count > 0


def _aeat_side(
    area: AeatSyncOverviewArea,
    *,
    filed_source: AeatSyncWorkspaceSourceObservationV1,
    census_observation: CensalObservation | None,
) -> tuple[AeatSyncSourceState, UtcInstant | None]:
    """State what stored AEAT evidence establishes for one area, and when."""
    if area is AeatSyncOverviewArea.CENSUS and census_observation is not None:
        return AeatSyncSourceState.PRESENT, census_observation.captured_at
    if area is AeatSyncOverviewArea.FILED_DECLARATIONS and filed_source.observed_at is not None:
        present = bool(filed_source.item_count)
        return (AeatSyncSourceState.PRESENT if present else AeatSyncSourceState.ABSENT), filed_source.observed_at
    return AeatSyncSourceState.NOT_OBSERVED, None


def _area_discrepancy(local: AeatSyncSourceState, aeat: AeatSyncSourceState) -> AeatSyncDiscrepancyKind:
    """Name the area-level outcome the two observed sides support."""
    if AeatSyncSourceState.NOT_OBSERVED in {local, aeat}:
        return AeatSyncDiscrepancyKind.UNOBSERVED
    if local is aeat:
        return AeatSyncDiscrepancyKind.NONE
    if local is AeatSyncSourceState.ABSENT:
        return AeatSyncDiscrepancyKind.AEAT_ONLY
    if aeat is AeatSyncSourceState.ABSENT:
        return AeatSyncDiscrepancyKind.LOCAL_ONLY
    return AeatSyncDiscrepancyKind.STATE_MISMATCH


def _overview_row(
    area: AeatSyncOverviewArea,
    *,
    observed_at: UtcInstant,
    filing_count: int,
    custody_count: int | None,
    contracts: OperationPublicContractSetV1,
    filed_source: AeatSyncWorkspaceSourceObservationV1,
    census_observation: CensalObservation | None = None,
) -> AeatSyncWorkspaceOverviewRowV1:
    """State only what the local side genuinely observed for this area.

    Stored filed-declaration captures establish the filed area's AEAT side;
    evidence comparison stays unobserved because captures hold no figures.
    Stored census evidence independently establishes the census area's AEAT side.

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
    if area in _locally_read_areas(custody_count=custody_count):
        local_state = (
            AeatSyncSourceState.PRESENT
            if _local_area_is_populated(area, filing_count=filing_count, custody_count=custody_count)
            else AeatSyncSourceState.ABSENT
        )
        local_observed_at = observed_at
    actions, operations = _admitted_capabilities(area, contracts)
    aeat_state, aeat_observed_at = _aeat_side(area, filed_source=filed_source, census_observation=census_observation)
    return AeatSyncWorkspaceOverviewRowV1(
        area=area,
        local_state=local_state,
        aeat_state=aeat_state,
        aeat_observed_at=aeat_observed_at,
        local_observed_at=local_observed_at,
        discrepancy_kind=_area_discrepancy(local_state, aeat_state),
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
    raise InternalInvariantError("census categories and the censal adoptable paths disagree")


def _census_rows(
    *,
    bucket_id: str,
    subject_key: str,
    censo_values: Mapping[str, str],
    contracts: OperationPublicContractSetV1,
    observation: CensalObservation | None = None,
) -> tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceCensusRowV1], ...]:
    """Compare populated remote facts with the local profile's declared values.

    Missing remote facts remain unobserved: historical captures cannot prove
    an explicit blank. The complete captured evidence is projected separately.
    """
    actions, operations = _admitted_capabilities(AeatSyncOverviewArea.CENSUS, contracts)
    remote = {} if observation is None else {fact.path: str(fact.value) for fact in censal_facts_from_read(observation)}
    return tuple(
        AeatSyncWorkspaceFactV1(
            bucket_id=bucket_id,
            subject_key=subject_key,
            row=AeatSyncWorkspaceCensusRowV1(
                path=path,
                category=_CENSUS_FIELD_CATEGORIES[path],
                status=(
                    AeatSyncCensusStatus.NOT_COMPARED
                    if path not in remote
                    else AeatSyncCensusStatus.UNCHANGED
                    if censo_values.get(path, "").strip() == remote.get(path, "").strip()
                    else AeatSyncCensusStatus.UNSET
                    if not censo_values.get(path, "")
                    else AeatSyncCensusStatus.CONFLICT
                ),
                local_value=censo_values.get(path, ""),
                aeat_value=remote.get(path),
                supported_actions=actions,
                supported_operations=operations,
            ),
        )
        for path in CENSAL_ADOPTABLE_PATHS
    )


def _filed_declaration_rows(
    *,
    bucket_id: str,
    subject_key: str,
    filings: tuple[ModeloRecord, ...],
    contracts: OperationPublicContractSetV1,
    observed: Mapping[_NaturalKey, OverviewCalendarFilingEvidence],
    aeat_observed_at: UtcInstant | None,
) -> tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceFiledDeclarationRowV1], ...]:
    """Join what this profile filed locally with what stored AEAT captures observed.

    The local half is a fact the session already holds, and withholding it
    until a pull happens would understate what the operator has done. The AEAT
    half comes from the shared calendar evidence join over stored captures:
    an observed submission and a verified justificante stay separate axes, and
    a declaration AEAT shows with no local filing still earns a row. Without a
    capture both AEAT axes stay NOT OBSERVED.

    One row per address. A superseded record and its replacement describe the
    same declaration, so the row carries the LATEST filing for each address
    rather than one row per revision.
    """
    actions, operations = _admitted_capabilities(AeatSyncOverviewArea.FILED_DECLARATIONS, contracts)
    latest: dict[_NaturalKey, ModeloRecord] = {}
    for record in filings:
        key = (str(record.modelo), int(record.filing_year), record.period.registry_token)
        current = latest.get(key)
        if current is None or record.filed_at > current.filed_at:
            latest[key] = record
    rows: list[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceFiledDeclarationRowV1]] = []
    for key in sorted(latest.keys() | observed.keys()):
        record, evidence = latest.get(key), observed.get(key)
        aeat_at = None if evidence is None else aeat_observed_at
        verified = evidence is not None and evidence.justificante_verified
        rows.append(
            AeatSyncWorkspaceFactV1(
                bucket_id=bucket_id,
                subject_key=subject_key,
                row=AeatSyncWorkspaceFiledDeclarationRowV1(
                    modelo=record.modelo if record is not None else ModeloCode(key[0]),
                    filing_year=key[1],
                    period=record.period if record is not None else _evidence_period(evidence),
                    local_filing_state=(
                        AeatSyncLocalFilingState.NOT_OBSERVED if record is None else AeatSyncLocalFilingState.FILED
                    ),
                    local_filed_at=None if record is None else record.filed_at,
                    aeat_observation_state=(
                        AeatSyncAeatObservationState.NOT_OBSERVED
                        if evidence is None
                        else _AEAT_OBSERVATION_STATES[evidence.aeat_submission_state]
                    ),
                    aeat_observed_at=aeat_at,
                    justificante_state=(
                        AeatSyncJustificanteState.VERIFIED if verified else AeatSyncJustificanteState.NOT_OBSERVED
                    ),
                    justificante_observed_at=aeat_at if verified else None,
                    supported_actions=actions,
                    supported_operations=operations,
                ),
            )
        )
    return tuple(rows)


def _evidence_period(evidence: OverviewCalendarFilingEvidence | None) -> Period:
    """Return the period of an indexed AEAT observation, which always carries one."""
    if evidence is None or evidence.period is None:
        raise InternalInvariantError("an AEAT-only filed row requires its observed period")
    return evidence.period


def read_local_aeat_sync_workspace_projection(
    *,
    bucket_id: str,
    subject_key: str,
    observed_at: UtcInstant,
    filings: tuple[ModeloRecord, ...],
    operation_contracts: OperationPublicContractSetV1,
    custody_count: int | None = None,
    censo_values: Mapping[str, str] | None = None,
    census_observation: CensalObservation | None = None,
    filed_evidence: CalendarEvidenceProjection | None = None,
) -> AeatSyncWorkspaceProjectionV1:
    """Project the local AEAT Sync workspace and its stored filing captures for one profile.

    `filed_evidence` is the calendar evidence join over this profile's stored
    filed-declaration captures, already scoped to `subject_key`. `None` means
    this session composed no such read, and the AEAT filing side stays never
    captured; otherwise its availability and capture time are preserved.

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

    Core types:
    :class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`.
    """
    # Refused before any fact is built: a row carrying a blank subject would
    # otherwise fail as a bare ValueError instead of the projection refusal.
    if not subject_key.strip():
        raise AeatSyncWorkspaceProjectionError("subject key cannot be blank")
    observed_filings = _observed_filings(filed_evidence)
    filed_source = _filed_source_observation(filed_evidence, observed_count=len(observed_filings))
    return project_aeat_sync_workspace(
        bucket_id=bucket_id,
        subject_key=subject_key,
        zone_observations=tuple(
            AeatSyncWorkspaceZoneObservationV1(
                zone=zone,
                sources=tuple(
                    _observation(
                        source,
                        zone=zone,
                        observed_at=observed_at,
                        profile_count=1,
                        filing_count=len(filings),
                        custody_count=custody_count,
                        census_observation=census_observation,
                        filed_source=filed_source,
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
                    custody_count=custody_count,
                    contracts=operation_contracts,
                    census_observation=census_observation,
                    filed_source=filed_source,
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
                observation=census_observation,
            )
        ),
        census_observation=(
            None
            if census_observation is None
            else AeatSyncWorkspaceFactV1(
                bucket_id=bucket_id,
                subject_key=subject_key,
                row=census_observation,
            )
        ),
        filed_declarations=_filed_declaration_rows(
            bucket_id=bucket_id,
            subject_key=subject_key,
            filings=filings,
            contracts=operation_contracts,
            observed=observed_filings,
            aeat_observed_at=filed_source.observed_at,
        ),
    )


__all__ = ["read_local_aeat_sync_workspace_projection"]
