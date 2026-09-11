"""Projection and authority checks for the AEAT Sync workspace.

The public workspace module owns the row models and their invariants.  This
module owns the projection pipeline: admission scope, capability joins,
source claims, deterministic ordering, and zone summaries.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Final, Protocol

from pydantic import BaseModel, TypeAdapter

from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.period import Period
from ...domain.modelos.codes import ModeloCode
from ..operations.models import OperationDefinitionId
from ..operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from ..operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE, ActionCatalogue
from ..operator_actions.models import ActionReference
from .workspace import (
    COMPARED_CENSUS_STATUSES,
    AeatSyncAeatObservationState,
    AeatSyncDocumentCustodyState,
    AeatSyncLocalFilingState,
    AeatSyncNotificationReadState,
    AeatSyncNotificationSelectionKey,
    AeatSyncOverviewArea,
    AeatSyncSourceState,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceCensusRowV1,
    AeatSyncWorkspaceEvidenceComparisonRowV1,
    AeatSyncWorkspaceFactV1,
    AeatSyncWorkspaceFiledDeclarationRowV1,
    AeatSyncWorkspaceNotificationRowV1,
    AeatSyncWorkspaceOverviewRowV1,
    AeatSyncWorkspaceProjectionError,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceReconciliationRowV1,
    AeatSyncWorkspaceSource,
    AeatSyncWorkspaceSourceObservationV1,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneObservationV1,
    AeatSyncWorkspaceZoneStateV1,
)
from .workspace import (
    source_observation_is_observable as _observable,
)

_SOURCES: Final = {
    AeatSyncWorkspaceZone.OVERVIEW: tuple(AeatSyncWorkspaceSource),
    AeatSyncWorkspaceZone.CENSUS: (AeatSyncWorkspaceSource.LOCAL_PROFILE, AeatSyncWorkspaceSource.AEAT_CENSUS),
    AeatSyncWorkspaceZone.FILED_DECLARATIONS: (
        AeatSyncWorkspaceSource.LOCAL_FILINGS,
        AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
    ),
    AeatSyncWorkspaceZone.NOTIFICATIONS: (
        AeatSyncWorkspaceSource.AEAT_NOTIFICATIONS,
        AeatSyncWorkspaceSource.LOCAL_NOTIFICATION_CUSTODY,
    ),
    AeatSyncWorkspaceZone.EVIDENCE_COMPARISON: (
        AeatSyncWorkspaceSource.LOCAL_FILINGS,
        AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
    ),
    AeatSyncWorkspaceZone.RECONCILIATION: (
        AeatSyncWorkspaceSource.LOCAL_FILINGS,
        AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
        AeatSyncWorkspaceSource.LOCAL_RECONCILIATION,
    ),
}

_ALLOWED: Final = {
    "overview:census": frozenset({"operator.profile.edit"}),
    "overview:filed_declarations": frozenset({"operator.live.filed.pull_all", "operator.modelo.filing_record.list"}),
    "overview:notifications": frozenset({"operator.live.notifications.list"}),
    "overview:evidence_comparison": frozenset({"operator.overview.explain"}),
    "overview:reconciliation": frozenset({"operator.overview.explain"}),
    "census": frozenset({"operator.profile.edit"}),
    "filed_declarations": frozenset({"operator.live.filed.pull", "operator.modelo.filing_record.list"}),
    "notifications": frozenset({"operator.live.notifications.list"}),
    "evidence_comparison": frozenset({"operator.overview.explain"}),
    "reconciliation": frozenset({"operator.overview.explain"}),
}
_ALLOWED_OPERATIONS: Final[dict[str, frozenset[str]]] = {
    "overview:census": frozenset({"user-profile.censo-review"}),
    "overview:filed_declarations": frozenset({"live.filed-history.pull"}),
    "overview:notifications": frozenset(),
    "overview:evidence_comparison": frozenset({"live.filed-history.pull"}),
    "overview:reconciliation": frozenset(),
    "census": frozenset({"user-profile.censo-review"}),
    "filed_declarations": frozenset({"live.filed-history.pull"}),
    "notifications": frozenset(),
    "evidence_comparison": frozenset({"live.filed-history.pull"}),
    "reconciliation": frozenset(),
}
_OVERVIEW_SOURCES: Final = {
    AeatSyncOverviewArea.CENSUS: (
        AeatSyncWorkspaceSource.LOCAL_PROFILE,
        AeatSyncWorkspaceSource.AEAT_CENSUS,
    ),
    AeatSyncOverviewArea.FILED_DECLARATIONS: (
        AeatSyncWorkspaceSource.LOCAL_FILINGS,
        AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
    ),
    AeatSyncOverviewArea.NOTIFICATIONS: (
        AeatSyncWorkspaceSource.LOCAL_NOTIFICATION_CUSTODY,
        AeatSyncWorkspaceSource.AEAT_NOTIFICATIONS,
    ),
    AeatSyncOverviewArea.EVIDENCE_COMPARISON: (
        AeatSyncWorkspaceSource.LOCAL_FILINGS,
        AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
    ),
    AeatSyncOverviewArea.RECONCILIATION: (
        AeatSyncWorkspaceSource.LOCAL_FILINGS,
        AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
    ),
}


def aeat_sync_workspace_sources(zone: AeatSyncWorkspaceZone) -> tuple[AeatSyncWorkspaceSource, ...]:
    """Return the canonical independent sources required by one zone."""
    return _SOURCES[zone]


def project_aeat_sync_workspace(
    *,
    bucket_id: BucketId,
    subject_key: str,
    zone_observations: tuple[AeatSyncWorkspaceZoneObservationV1, ...],
    action_catalogue: ActionCatalogue,
    operation_contracts: OperationPublicContractSetV1,
    overview: tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceOverviewRowV1], ...] = (),
    census: tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceCensusRowV1], ...] = (),
    filed_declarations: tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceFiledDeclarationRowV1], ...] = (),
    notifications: tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceNotificationRowV1], ...] = (),
    evidence_comparison: tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceEvidenceComparisonRowV1], ...] = (),
    reconciliation: tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceReconciliationRowV1], ...] = (),
) -> AeatSyncWorkspaceProjectionV1:
    """Project already-loaded, scoped facts without retaining their scope."""
    TypeAdapter(BucketId).validate_python(bucket_id)
    if not subject_key.strip():
        raise AeatSyncWorkspaceProjectionError("subject key cannot be blank")
    obs = _observations(zone_observations)
    _validate_action_catalogue(action_catalogue)
    groups = {
        AeatSyncWorkspaceZone.OVERVIEW: overview,
        AeatSyncWorkspaceZone.CENSUS: census,
        AeatSyncWorkspaceZone.FILED_DECLARATIONS: filed_declarations,
        AeatSyncWorkspaceZone.NOTIFICATIONS: notifications,
        AeatSyncWorkspaceZone.EVIDENCE_COMPARISON: evidence_comparison,
        AeatSyncWorkspaceZone.RECONCILIATION: reconciliation,
    }
    _validate_fact_scope(groups, bucket_id=bucket_id, subject_key=subject_key)
    _duplicates(overview, census, filed_declarations, notifications, evidence_comparison, reconciliation)
    _actions(groups, action_catalogue, operation_contracts)
    _source_claims(groups, obs)
    out_overview = tuple(
        sorted((_public_row(f.row, AeatSyncWorkspaceOverviewRowV1) for f in overview), key=lambda row: row.area.value)
    )
    out_census = tuple(
        sorted(
            (_public_row(f.row, AeatSyncWorkspaceCensusRowV1) for f in census),
            key=lambda row: _canonical_census_path(row.path),
        )
    )
    out_filed = tuple(
        sorted((_public_row(f.row, AeatSyncWorkspaceFiledDeclarationRowV1) for f in filed_declarations), key=_natural)
    )
    out_notifications = _project_notification_rows(
        notifications,
    )
    out_comparison = tuple(
        sorted(
            (_public_row(f.row, AeatSyncWorkspaceEvidenceComparisonRowV1) for f in evidence_comparison), key=_natural
        )
    )
    out_reconciliation = tuple(
        sorted((_public_row(f.row, AeatSyncWorkspaceReconciliationRowV1) for f in reconciliation), key=_natural)
    )
    public = dict(
        zip(
            AeatSyncWorkspaceZone,
            (out_overview, out_census, out_filed, out_notifications, out_comparison, out_reconciliation),
            strict=True,
        )
    )
    zones = tuple(_zone_state(obs[zone], len(public[zone])) for zone in AeatSyncWorkspaceZone)
    return AeatSyncWorkspaceProjectionV1(
        zones=zones,
        overview=out_overview,
        census=out_census,
        filed_declarations=out_filed,
        notifications=out_notifications,
        evidence_comparison=out_comparison,
        reconciliation=out_reconciliation,
    )


def _validate_fact_scope(
    groups: Mapping[AeatSyncWorkspaceZone, tuple[Any, ...]],
    *,
    bucket_id: BucketId,
    subject_key: str,
) -> None:
    for facts in groups.values():
        for fact in facts:
            if fact.bucket_id != bucket_id:
                raise AeatSyncWorkspaceProjectionError("foreign bucket")
            if fact.subject_key != subject_key:
                raise AeatSyncWorkspaceProjectionError("mixed subjects")


def _observations(
    values: tuple[AeatSyncWorkspaceZoneObservationV1, ...],
) -> dict[AeatSyncWorkspaceZone, AeatSyncWorkspaceZoneObservationV1]:
    if tuple(item.zone for item in values) != tuple(AeatSyncWorkspaceZone):
        raise AeatSyncWorkspaceProjectionError("observations must cover six zones in order")
    for item in values:
        if tuple(source.source for source in item.sources) != _SOURCES[item.zone]:
            raise AeatSyncWorkspaceProjectionError("source observations incomplete or unordered")
    return {item.zone: item for item in values}


def _duplicates(
    overview: tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceOverviewRowV1], ...],
    census: tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceCensusRowV1], ...],
    filed: tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceFiledDeclarationRowV1], ...],
    notifications: tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceNotificationRowV1], ...],
    comparison: tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceEvidenceComparisonRowV1], ...],
    reconciliation: tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceReconciliationRowV1], ...],
) -> None:
    _unique((f.row.area for f in overview), "overview areas")
    _unique((_canonical_census_path(f.row.path) for f in census), "census paths")
    _unique((_natural(f.row) for f in filed), "filed addresses")
    if any(f.private_identity is None for f in notifications):
        raise AeatSyncWorkspaceProjectionError("notification requires private identity")
    _unique((f.private_identity for f in notifications), "notification identities")
    _unique((_natural(f.row) for f in comparison), "comparison addresses")
    _unique((_natural(f.row) for f in reconciliation), "reconciliation addresses")


def _action_row_key(zone: AeatSyncWorkspaceZone, row: BaseModel) -> str:
    if zone is AeatSyncWorkspaceZone.OVERVIEW:
        if not isinstance(row, AeatSyncWorkspaceOverviewRowV1):
            raise AeatSyncWorkspaceProjectionError("overview facts require overview rows")
        return f"overview:{row.area.value}"
    return zone.value


def _validate_action_ids(
    ids: tuple[str, ...],
    *,
    key: str,
    catalogue: ActionCatalogue,
) -> None:
    for action_id in ids:
        try:
            catalogue.lookup(action_id)
        except KeyError as error:
            raise AeatSyncWorkspaceProjectionError("action is not admitted by catalogue") from error
    if not set(ids) <= _ALLOWED[key]:
        raise AeatSyncWorkspaceProjectionError("action is not allowed for row area/state")


def _validate_operation_ids(
    operation_ids: tuple[OperationDefinitionId, ...],
    *,
    key: str,
    contract_by_id: Mapping[OperationDefinitionId, Any],
) -> set[str]:
    operation_id_values: set[str] = {str(item) for item in operation_ids}
    _unique(operation_ids, "row operations")
    for operation_id in operation_ids:
        contract = contract_by_id.get(operation_id)
        if contract is None or OperationFrontendProjection.TUI not in contract.permitted_frontends:
            raise AeatSyncWorkspaceProjectionError("operation is not admitted by public contracts")
    if not set(operation_ids) <= _ALLOWED_OPERATIONS[key]:
        raise AeatSyncWorkspaceProjectionError("operation is not allowed for row area/state")
    return operation_id_values


def _validate_action_operation_joins(
    actions: tuple[ActionReference, ...],
    *,
    operation_id_values: set[str],
    contracts: OperationPublicContractSetV1,
) -> None:
    for action in actions:
        joined = tuple(
            contract
            for contract in contracts.definitions
            if contract.action_reference == action and str(contract.definition_id) in operation_id_values
        )
        if not joined and str(action.action_id) in {
            "operator.live.filed.pull",
            "operator.live.filed.pull_all",
        }:
            raise AeatSyncWorkspaceProjectionError("pull action lacks its exact public operation join")


def _actions(
    groups: dict[AeatSyncWorkspaceZone, tuple[Any, ...]],
    catalogue: ActionCatalogue,
    contracts: OperationPublicContractSetV1,
) -> None:
    contract_by_id = {contract.definition_id: contract for contract in contracts.definitions}
    for zone, facts in groups.items():
        for fact in facts:
            if isinstance(fact.row, AeatSyncWorkspaceNotificationRowV1):
                continue
            action_row = fact.row
            actions = action_row.supported_actions
            ids = tuple(str(item.action_id) for item in actions)
            _unique(ids, "row actions")
            key = _action_row_key(zone, fact.row)
            _validate_action_ids(ids, key=key, catalogue=catalogue)
            operation_ids = action_row.supported_operations
            operation_id_values = _validate_operation_ids(
                operation_ids,
                key=key,
                contract_by_id=contract_by_id,
            )
            _validate_action_operation_joins(
                actions,
                operation_id_values=operation_id_values,
                contracts=contracts,
            )


def _public_row[RowT: BaseModel](row: BaseModel, row_type: type[RowT]) -> RowT:
    """Strip subclass and extra state by rebuilding the exact public class."""
    return row_type.model_validate(row.model_dump(include=set(row_type.model_fields)))


def _require_overview_sources(
    row: AeatSyncWorkspaceOverviewRowV1,
    sources: Mapping[AeatSyncWorkspaceSource, AeatSyncWorkspaceSourceObservationV1],
) -> None:
    local_source, aeat_source = _OVERVIEW_SOURCES[row.area]
    _require(
        row.local_state is AeatSyncSourceState.NOT_OBSERVED,
        sources[local_source],
        "local",
        absent=row.local_state is AeatSyncSourceState.ABSENT,
    )
    _require(
        row.aeat_state is AeatSyncSourceState.NOT_OBSERVED,
        sources[aeat_source],
        "AEAT",
        absent=row.aeat_state is AeatSyncSourceState.ABSENT,
    )


def _require_census_sources(
    row: AeatSyncWorkspaceCensusRowV1,
    sources: Mapping[AeatSyncWorkspaceSource, AeatSyncWorkspaceSourceObservationV1],
) -> None:
    # The local side is required for every census row: the row exists because
    # the profile was read. The AEAT side is required only for a row that claims
    # a VERDICT; NOT_COMPARED means no AEAT observation exists.
    _require(False, sources[AeatSyncWorkspaceSource.LOCAL_PROFILE], "local census")
    if row.status in COMPARED_CENSUS_STATUSES:
        _require(False, sources[AeatSyncWorkspaceSource.AEAT_CENSUS], "AEAT census")


def _require_dual_sources(
    row: AeatSyncWorkspaceEvidenceComparisonRowV1 | AeatSyncWorkspaceReconciliationRowV1,
    sources: Mapping[AeatSyncWorkspaceSource, AeatSyncWorkspaceSourceObservationV1],
) -> None:
    _require(
        row.local_state is AeatSyncSourceState.NOT_OBSERVED,
        sources[AeatSyncWorkspaceSource.LOCAL_FILINGS],
        "local",
    )
    _require(
        row.aeat_state is AeatSyncSourceState.NOT_OBSERVED,
        sources[AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS],
        "AEAT",
    )


def _require_filed_declaration_sources(
    row: AeatSyncWorkspaceFiledDeclarationRowV1,
    sources: Mapping[AeatSyncWorkspaceSource, AeatSyncWorkspaceSourceObservationV1],
) -> None:
    _require(
        row.local_filing_state is AeatSyncLocalFilingState.NOT_OBSERVED,
        sources[AeatSyncWorkspaceSource.LOCAL_FILINGS],
        "local filing",
    )
    _require(
        row.aeat_observation_state is AeatSyncAeatObservationState.NOT_OBSERVED,
        sources[AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS],
        "AEAT filing",
    )


def _require_notification_sources(
    row: AeatSyncWorkspaceNotificationRowV1,
    sources: Mapping[AeatSyncWorkspaceSource, AeatSyncWorkspaceSourceObservationV1],
) -> None:
    _require(
        row.read_state is AeatSyncNotificationReadState.UNKNOWN,
        sources[AeatSyncWorkspaceSource.AEAT_NOTIFICATIONS],
        "AEAT notification",
    )
    missing = row.document_custody_state in {
        AeatSyncDocumentCustodyState.NOT_CAPTURED,
        AeatSyncDocumentCustodyState.UNAVAILABLE,
    }
    _require(missing, sources[AeatSyncWorkspaceSource.LOCAL_NOTIFICATION_CUSTODY], "notification custody")


def _source_claims_for_row(
    row: BaseModel,
    sources: Mapping[AeatSyncWorkspaceSource, AeatSyncWorkspaceSourceObservationV1],
) -> None:
    if isinstance(row, AeatSyncWorkspaceOverviewRowV1):
        _require_overview_sources(row, sources)
    if isinstance(row, AeatSyncWorkspaceCensusRowV1):
        _require_census_sources(row, sources)
    if isinstance(row, (AeatSyncWorkspaceEvidenceComparisonRowV1, AeatSyncWorkspaceReconciliationRowV1)):
        _require_dual_sources(row, sources)
    if isinstance(row, AeatSyncWorkspaceFiledDeclarationRowV1):
        _require_filed_declaration_sources(row, sources)
    if isinstance(row, AeatSyncWorkspaceNotificationRowV1):
        _require_notification_sources(row, sources)


def _source_claims(
    groups: dict[AeatSyncWorkspaceZone, tuple[Any, ...]],
    observations: dict[AeatSyncWorkspaceZone, AeatSyncWorkspaceZoneObservationV1],
) -> None:
    for zone, facts in groups.items():
        sources = {item.source: item for item in observations[zone].sources}
        if facts and not any(_observable(item.availability) for item in sources.values()):
            raise AeatSyncWorkspaceProjectionError("unobservable zone carries rows")
        for fact in facts:
            _source_claims_for_row(fact.row, sources)


def _require(
    unconfident: bool,
    source: AeatSyncWorkspaceSourceObservationV1,
    axis: str,
    *,
    absent: bool = False,
) -> None:
    """Refuse a confident row state its own source cannot support.

    A row asserting something POSITIVE about a side needs a source that was
    observable and actually contributed items. A row asserting ABSENCE needs
    only that the source was observable: an observed zero is precisely a
    readable source with nothing in it, and requiring a non-zero count there
    would make an observed empty catalogue inexpressible -- forcing it to be
    reported as never observed, which is the collapse this contract exists to
    prevent.
    """
    if unconfident:
        return
    if not _observable(source.availability):
        raise AeatSyncWorkspaceProjectionError(f"confident {axis} state lacks observable source")
    if not absent and source.item_count == 0:
        raise AeatSyncWorkspaceProjectionError(f"confident {axis} state lacks observable source")


def _validate_action_catalogue(catalogue: ActionCatalogue) -> None:
    """Require every supplied declaration to equal the canonical authority."""
    for supplied in catalogue.entries:
        try:
            canonical = OPERATOR_ACTION_CATALOGUE.lookup(supplied.action_id)
        except KeyError as error:
            raise AeatSyncWorkspaceProjectionError("action catalogue contains unknown declaration") from error
        if supplied != canonical:
            raise AeatSyncWorkspaceProjectionError("action catalogue declaration differs from canonical authority")


def _canonical_census_path(path: str) -> str:
    """Normalize insignificant whitespace and case for logical identity."""
    return " ".join(path.split()).casefold()


_COMPARISON_ZONES: Final = frozenset(
    {
        AeatSyncWorkspaceZone.EVIDENCE_COMPARISON,
        AeatSyncWorkspaceZone.RECONCILIATION,
    }
)
"""Zones whose rows are a COMPARISON and cannot exist from one side alone.

A list zone can be counted as soon as any one of its sources is readable: the
count is of what that source holds. A comparison zone cannot. Its rows are
discrepancies BETWEEN sources, so with the AEAT half never pulled there is no
count to report -- and reporting the local half's zero as the zone's count
tells the operator "no discrepancies" when the truth is "never compared".
Those are exactly the two states `no-silent-under-declaration` forbids
collapsing into one.
"""


def _zone_seen(
    zone: AeatSyncWorkspaceZone,
    states: tuple[AeatSyncWorkspaceAvailability, ...],
) -> bool:
    if zone in _COMPARISON_ZONES:
        return all(_observable(item) for item in states)
    return any(_observable(item) for item in states)


def _zone_availability(
    states: tuple[AeatSyncWorkspaceAvailability, ...],
    *,
    seen: bool,
) -> AeatSyncWorkspaceAvailability:
    if all(item is AeatSyncWorkspaceAvailability.AVAILABLE for item in states):
        return AeatSyncWorkspaceAvailability.AVAILABLE
    if seen:
        return AeatSyncWorkspaceAvailability.STALE
    if AeatSyncWorkspaceAvailability.LOCKED in states:
        return AeatSyncWorkspaceAvailability.LOCKED
    if all(item is AeatSyncWorkspaceAvailability.NEVER_CAPTURED for item in states):
        return AeatSyncWorkspaceAvailability.NEVER_CAPTURED
    return AeatSyncWorkspaceAvailability.UNAVAILABLE


def _zone_state(observation: AeatSyncWorkspaceZoneObservationV1, count: int) -> AeatSyncWorkspaceZoneStateV1:
    states = tuple(item.availability for item in observation.sources)
    seen = _zone_seen(observation.zone, states)
    availability = _zone_availability(states, seen=seen)
    return AeatSyncWorkspaceZoneStateV1(
        zone=observation.zone,
        availability=availability,
        sources=observation.sources,
        item_count=count if seen else None,
    )


def _unique(values: Iterable[object], label: str) -> None:
    items = tuple(values)
    if len(items) != len(set(items)):
        raise AeatSyncWorkspaceProjectionError(f"duplicate {label}")


class _NaturalRow(Protocol):
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period


def _natural(row: _NaturalRow) -> tuple[str, int, str]:
    return (str(row.modelo), row.filing_year, row.period.registry_token)


def _project_notification_rows(
    facts: tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceNotificationRowV1], ...],
) -> tuple[AeatSyncWorkspaceNotificationRowV1, ...]:
    """Project notification rows with opaque keys and protected-value-free ordering."""
    from . import workspace as workspace_contracts

    keyed: list[
        tuple[AeatSyncNotificationSelectionKey, AeatSyncWorkspaceFactV1[AeatSyncWorkspaceNotificationRowV1]]
    ] = []
    for fact in facts:
        if fact.private_identity is None:
            raise AeatSyncWorkspaceProjectionError("notification requires private identity")
        keyed.append((workspace_contracts.notification_selection_key(fact.private_identity), fact))
    _unique((key for key, _ in keyed), "notification selection identities")
    return tuple(
        workspace_contracts.public_notification_row(fact.row, key)
        for key, fact in sorted(keyed, key=lambda item: (item[1].row.issued_on, item[0]))
    )
