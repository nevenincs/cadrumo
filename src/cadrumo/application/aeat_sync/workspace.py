"""Safe immutable projection for the six-zone AEAT Sync workspace."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any, Final, Protocol, Self, override

from pydantic import BaseModel, Field, NonNegativeInt, TypeAdapter, model_validator

from ...core.filing_year import FilingYear
from ...core.identifier_grammar import NamespacedId
from ...core.identity import BucketId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.time.utc import UtcInstant
from ...domain.modelos.codes import ModeloCode
from ..operations.models import OperationDefinitionId
from ..operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from ..operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE, ActionCatalogue
from ..operator_actions.models import ActionReference

AEAT_SYNC_WORKSPACE_CONTRACT_VERSION: Final[int] = 1


class AeatSyncWorkspaceProjectionError(ValueError):
    """Already-loaded authorities cannot form one safe snapshot."""


class AeatSyncWorkspaceZone(StrEnum):
    """Closed workspace areas."""

    OVERVIEW = "overview"
    CENSUS = "census"
    FILED_DECLARATIONS = "filed_declarations"
    NOTIFICATIONS = "notifications"
    EVIDENCE_COMPARISON = "evidence_comparison"
    RECONCILIATION = "reconciliation"


class AeatSyncWorkspaceSource(StrEnum):
    """Canonical local and AEAT source authorities."""

    LOCAL_PROFILE = "local.profile"
    LOCAL_FILINGS = "local.filings"
    LOCAL_NOTIFICATION_CUSTODY = "local.notification_custody"
    LOCAL_RECONCILIATION = "local.reconciliation"
    AEAT_CENSUS = "aeat.census"
    AEAT_FILED_DECLARATIONS = "aeat.filed_declarations"
    AEAT_NOTIFICATIONS = "aeat.notifications"


class AeatSyncWorkspaceAvailability(StrEnum):
    """Availability and freshness of one source observation."""

    AVAILABLE = "available"
    LOCKED = "locked"
    STALE = "stale"
    NEVER_CAPTURED = "never_captured"
    UNAVAILABLE = "unavailable"


class AeatSyncSourceState(StrEnum):
    """Safe observed state of one comparison side."""

    NOT_OBSERVED = "not_observed"
    ABSENT = "absent"
    PRESENT = "present"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONFLICT = "conflict"


class AeatSyncDiscrepancyKind(StrEnum):
    """Closed comparison outcomes."""

    NONE = "none"
    LOCAL_ONLY = "local_only"
    AEAT_ONLY = "aeat_only"
    STATE_MISMATCH = "state_mismatch"
    CONTRADICTORY_SOURCE = "contradictory_source"
    UNOBSERVED = "unobserved"


class AeatSyncOverviewArea(StrEnum):
    """Closed overview areas."""

    CENSUS = "census"
    FILED_DECLARATIONS = "filed_declarations"
    NOTIFICATIONS = "notifications"
    EVIDENCE_COMPARISON = "evidence_comparison"
    RECONCILIATION = "reconciliation"


class AeatSyncCensusCategory(StrEnum):
    """Safe census field categories."""

    ADDRESS = "address"
    ACTIVITY = "activity"
    OBLIGATION = "obligation"
    CONTACT = "contact"
    OTHER = "other"


class AeatSyncCensusStatus(StrEnum):
    """Safe census comparison outcomes."""

    ADOPTED = "adopted"
    CONFLICT = "conflict"
    UNCHANGED = "unchanged"
    UNSET = "unset"


class AeatSyncLocalFilingState(StrEnum):
    """Local filing states."""

    NOT_OBSERVED = "not_observed"
    DRAFT = "draft"
    READY = "ready"
    FILED = "filed"


class AeatSyncAeatObservationState(StrEnum):
    """AEAT declaration observation states."""

    NOT_OBSERVED = "not_observed"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class AeatSyncJustificanteState(StrEnum):
    """Justificante availability states."""

    NOT_OBSERVED = "not_observed"
    UNAVAILABLE = "unavailable"
    AVAILABLE = "available"
    VERIFIED = "verified"


class AeatSyncNotificationCategory(StrEnum):
    """Safe notification categories."""

    FORMAL = "formal"
    COMMUNICATION = "communication"
    PENDING = "pending"
    OTHER = "other"


class AeatSyncNotificationReadState(StrEnum):
    """Notification read states."""

    UNKNOWN = "unknown"
    UNREAD = "unread"
    READ = "read"


class AeatSyncDocumentCustodyState(StrEnum):
    """Encrypted document custody states."""

    NOT_CAPTURED = "not_captured"
    HELD = "held"
    REFUSED = "refused"
    UNAVAILABLE = "unavailable"


class AeatSyncReconciliationState(StrEnum):
    """Closed reconciliation outcomes."""

    UNRESOLVED = "unresolved"
    KEEP_LOCAL = "keep_local"
    ACCEPT_AEAT = "accept_aeat"
    DISMISSED = "dismissed"
    NO_ACTION = "no_action"


class AeatSyncWorkspaceSourceObservationV1(BaseModel):
    """One authority's independent availability/freshness/count axis."""

    model_config = STRICT_FROZEN_CONFIG
    source: AeatSyncWorkspaceSource
    availability: AeatSyncWorkspaceAvailability
    observed_at: UtcInstant | None = None
    refusal: NamespacedId | None = None
    item_count: NonNegativeInt | None = None

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        observable = _observable(self.availability)
        if observable != (self.observed_at is not None and self.item_count is not None):
            raise ValueError("source observability contradicts its time/count")
        if self.availability is AeatSyncWorkspaceAvailability.AVAILABLE:
            if self.refusal is not None:
                raise ValueError("available source cannot carry refusal")
        elif self.refusal is None:
            raise ValueError("non-available source requires refusal")
        return self


class AeatSyncWorkspaceZoneObservationV1(BaseModel):
    """Independent source observations for one zone."""

    model_config = STRICT_FROZEN_CONFIG
    zone: AeatSyncWorkspaceZone
    sources: tuple[AeatSyncWorkspaceSourceObservationV1, ...]

    @model_validator(mode="after")
    def _unique(self) -> Self:
        ids = tuple(item.source for item in self.sources)
        if len(ids) != len(set(ids)):
            raise ValueError("zone source observations must be unique")
        return self


class AeatSyncWorkspaceZoneStateV1(BaseModel):
    """Projected zone state retaining its independent sources."""

    model_config = STRICT_FROZEN_CONFIG
    zone: AeatSyncWorkspaceZone
    availability: AeatSyncWorkspaceAvailability
    sources: tuple[AeatSyncWorkspaceSourceObservationV1, ...]
    item_count: NonNegativeInt | None

    @property
    def measured_count(self) -> NonNegativeInt | None:
        """Return the count only when at least one source was observable."""
        return self.item_count


class _ActionRow(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    supported_actions: tuple[ActionReference, ...] = ()
    supported_operations: tuple[OperationDefinitionId, ...] = ()


class AeatSyncWorkspaceOverviewRowV1(_ActionRow):
    """Safe public overview row."""

    area: AeatSyncOverviewArea
    local_state: AeatSyncSourceState
    aeat_state: AeatSyncSourceState
    local_observed_at: UtcInstant | None = None
    aeat_observed_at: UtcInstant | None = None
    discrepancy_kind: AeatSyncDiscrepancyKind

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        _dual(self.local_state, self.local_observed_at, self.aeat_state, self.aeat_observed_at)
        _discrepancy(self.local_state, self.aeat_state, self.discrepancy_kind)
        return self


class AeatSyncWorkspaceCensusRowV1(BaseModel):
    """Safe public census row without values."""

    model_config = STRICT_FROZEN_CONFIG
    path: str = Field(min_length=1, max_length=256)
    category: AeatSyncCensusCategory
    status: AeatSyncCensusStatus


class AeatSyncWorkspaceFiledDeclarationRowV1(BaseModel):
    """Safe public filed-declaration comparison."""

    model_config = STRICT_FROZEN_CONFIG
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    local_filing_state: AeatSyncLocalFilingState
    local_filed_at: UtcInstant | None = None
    aeat_observation_state: AeatSyncAeatObservationState
    aeat_observed_at: UtcInstant | None = None
    justificante_state: AeatSyncJustificanteState
    justificante_observed_at: UtcInstant | None = None

    @property
    def aeat_submission_state(self) -> AeatSyncAeatObservationState:
        """Return the AEAT declaration state."""
        return self.aeat_observation_state

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("period and filing year disagree")
        if (self.local_filing_state is AeatSyncLocalFilingState.FILED) != (self.local_filed_at is not None):
            raise ValueError("only filed local state carries filing time")
        _optional_time(self.aeat_observation_state, self.aeat_observed_at, AeatSyncAeatObservationState.NOT_OBSERVED)
        confident = self.justificante_state in {AeatSyncJustificanteState.AVAILABLE, AeatSyncJustificanteState.VERIFIED}
        if confident != (self.justificante_observed_at is not None):
            raise ValueError("justificante state contradicts time")
        if confident and self.aeat_observation_state is AeatSyncAeatObservationState.NOT_OBSERVED:
            raise ValueError("justificante cannot be confident without AEAT observation")
        return self


class AeatSyncWorkspaceNotificationRowV1(BaseModel):
    """Safe public notification metadata."""

    model_config = STRICT_FROZEN_CONFIG
    issued_on: date
    read_on: date | None = None
    read_state: AeatSyncNotificationReadState
    category: AeatSyncNotificationCategory
    document_custody_state: AeatSyncDocumentCustodyState
    document_custody_observed_at: UtcInstant | None = None

    @property
    def issue_date(self) -> date:
        """Return the notification issue date."""
        return self.issued_on

    @property
    def read_date(self) -> date | None:
        """Return the optional notification read date."""
        return self.read_on

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if (self.read_state is AeatSyncNotificationReadState.READ) != (self.read_on is not None):
            raise ValueError("only read state carries read date")
        if self.read_on is not None and self.read_on < self.issued_on:
            raise ValueError("read date precedes issue date")
        held = self.document_custody_state is AeatSyncDocumentCustodyState.HELD
        if held != (self.document_custody_observed_at is not None):
            raise ValueError("custody state contradicts time")
        if held and self.read_state is not AeatSyncNotificationReadState.READ:
            raise ValueError("held document requires read state")
        return self


class _DualRow(_ActionRow):
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    local_state: AeatSyncSourceState
    aeat_state: AeatSyncSourceState
    local_observed_at: UtcInstant | None = None
    aeat_observed_at: UtcInstant | None = None
    discrepancy_kind: AeatSyncDiscrepancyKind

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("period and filing year disagree")
        _dual(self.local_state, self.local_observed_at, self.aeat_state, self.aeat_observed_at)
        _discrepancy(self.local_state, self.aeat_state, self.discrepancy_kind)
        return self


class AeatSyncWorkspaceEvidenceComparisonRowV1(_DualRow):
    """Safe public local-versus-AEAT evidence comparison."""

    pass


class AeatSyncWorkspaceReconciliationRowV1(_DualRow):
    """Safe public reconciliation row."""

    reconciliation_state: AeatSyncReconciliationState

    @model_validator(mode="after")
    def _reconciled(self) -> Self:
        no_action = self.reconciliation_state is AeatSyncReconciliationState.NO_ACTION
        if (self.discrepancy_kind is AeatSyncDiscrepancyKind.NONE) != no_action:
            raise ValueError("reconciliation state contradicts discrepancy")
        if no_action and self.supported_actions:
            raise ValueError("NO_ACTION cannot carry actions")
        return self

    @override
    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
        """Keep state/action closure intact across mutation-test copies."""
        if update is None:
            return super().model_copy(deep=deep)
        return type(self).model_validate({**self.model_dump(), **update})


@dataclass(frozen=True, slots=True)
class AeatSyncWorkspaceFactV1[RowT: BaseModel]:
    """Admission-only scope/private identity projected away from ``row``."""

    bucket_id: BucketId
    subject_key: str
    row: RowT
    private_identity: str | None = None

    def __post_init__(self) -> None:
        """Reject absent or blank provenance coordinates."""
        TypeAdapter(BucketId).validate_python(self.bucket_id)
        if not self.subject_key.strip():
            raise ValueError("subject key cannot be blank")
        if self.private_identity is not None and not self.private_identity.strip():
            raise ValueError("private identity cannot be blank")


class AeatSyncWorkspaceProjectionV1(BaseModel):
    """Public result, physically free of protected admission fields."""

    model_config = STRICT_FROZEN_CONFIG
    contract_version: int = AEAT_SYNC_WORKSPACE_CONTRACT_VERSION
    zones: tuple[AeatSyncWorkspaceZoneStateV1, ...]
    overview: tuple[AeatSyncWorkspaceOverviewRowV1, ...] = ()
    census: tuple[AeatSyncWorkspaceCensusRowV1, ...] = ()
    filed_declarations: tuple[AeatSyncWorkspaceFiledDeclarationRowV1, ...] = ()
    notifications: tuple[AeatSyncWorkspaceNotificationRowV1, ...] = ()
    evidence_comparison: tuple[AeatSyncWorkspaceEvidenceComparisonRowV1, ...] = ()
    reconciliation: tuple[AeatSyncWorkspaceReconciliationRowV1, ...] = ()

    @model_validator(mode="after")
    def _six_zones(self) -> Self:
        if tuple(item.zone for item in self.zones) != tuple(AeatSyncWorkspaceZone):
            raise ValueError("zones must cover the closed catalogue")
        return self


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
    for facts in groups.values():
        for fact in facts:
            if fact.bucket_id != bucket_id:
                raise AeatSyncWorkspaceProjectionError("foreign bucket")
            if fact.subject_key != subject_key:
                raise AeatSyncWorkspaceProjectionError("mixed subjects")
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
    out_notifications = tuple(
        _public_row(f.row, AeatSyncWorkspaceNotificationRowV1)
        for f in sorted(notifications, key=lambda f: (f.row.issued_on, f.private_identity or ""))
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


def _actions(
    groups: dict[AeatSyncWorkspaceZone, tuple[Any, ...]],
    catalogue: ActionCatalogue,
    contracts: OperationPublicContractSetV1,
) -> None:
    contract_by_id = {contract.definition_id: contract for contract in contracts.definitions}
    for zone, facts in groups.items():
        for fact in facts:
            ids = tuple(str(item.action_id) for item in getattr(fact.row, "supported_actions", ()))
            _unique(ids, "row actions")
            key = f"overview:{fact.row.area.value}" if zone is AeatSyncWorkspaceZone.OVERVIEW else zone.value
            for action_id in ids:
                try:
                    catalogue.lookup(action_id)
                except KeyError as error:
                    raise AeatSyncWorkspaceProjectionError("action is not admitted by catalogue") from error
            if not set(ids) <= _ALLOWED[key]:
                raise AeatSyncWorkspaceProjectionError("action is not allowed for row area/state")
            operation_ids = tuple(getattr(fact.row, "supported_operations", ()))
            _unique(operation_ids, "row operations")
            allowed_operations = _ALLOWED_OPERATIONS[key]
            for operation_id in operation_ids:
                contract = contract_by_id.get(operation_id)
                if contract is None or OperationFrontendProjection.TUI not in contract.permitted_frontends:
                    raise AeatSyncWorkspaceProjectionError("operation is not admitted by public contracts")
            if not set(operation_ids) <= allowed_operations:
                raise AeatSyncWorkspaceProjectionError("operation is not allowed for row area/state")
            for action in getattr(fact.row, "supported_actions", ()):
                joined = tuple(
                    contract
                    for contract in contracts.definitions
                    if contract.action_reference == action and contract.definition_id in operation_ids
                )
                if not joined and action.action_id in {
                    "operator.live.filed.pull",
                    "operator.live.filed.pull_all",
                }:
                    raise AeatSyncWorkspaceProjectionError("pull action lacks its exact public operation join")


def _public_row[RowT: BaseModel](row: BaseModel, row_type: type[RowT]) -> RowT:
    """Strip subclass and extra state by rebuilding the exact public class."""
    return row_type.model_validate(row.model_dump(include=set(row_type.model_fields)))


def _source_claims(
    groups: dict[AeatSyncWorkspaceZone, tuple[Any, ...]],
    observations: dict[AeatSyncWorkspaceZone, AeatSyncWorkspaceZoneObservationV1],
) -> None:
    for zone, facts in groups.items():
        sources = {item.source: item for item in observations[zone].sources}
        if facts and not any(_observable(item.availability) for item in sources.values()):
            raise AeatSyncWorkspaceProjectionError("unobservable zone carries rows")
        for fact in facts:
            row = fact.row
            if isinstance(row, AeatSyncWorkspaceOverviewRowV1):
                local_source, aeat_source = _OVERVIEW_SOURCES[row.area]
                _require(row.local_state is AeatSyncSourceState.NOT_OBSERVED, sources[local_source], "local")
                _require(row.aeat_state is AeatSyncSourceState.NOT_OBSERVED, sources[aeat_source], "AEAT")
            if isinstance(row, AeatSyncWorkspaceCensusRowV1):
                _require(False, sources[AeatSyncWorkspaceSource.LOCAL_PROFILE], "local census")
                _require(False, sources[AeatSyncWorkspaceSource.AEAT_CENSUS], "AEAT census")
            if isinstance(row, _DualRow):
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
            if isinstance(row, AeatSyncWorkspaceFiledDeclarationRowV1):
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
            if isinstance(row, AeatSyncWorkspaceNotificationRowV1):
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


def _require(unconfident: bool, source: AeatSyncWorkspaceSourceObservationV1, axis: str) -> None:
    if not unconfident and (not _observable(source.availability) or source.item_count == 0):
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


def _zone_state(observation: AeatSyncWorkspaceZoneObservationV1, count: int) -> AeatSyncWorkspaceZoneStateV1:
    states = tuple(item.availability for item in observation.sources)
    seen = any(_observable(item) for item in states)
    if all(item is AeatSyncWorkspaceAvailability.AVAILABLE for item in states):
        availability = AeatSyncWorkspaceAvailability.AVAILABLE
    elif seen:
        availability = AeatSyncWorkspaceAvailability.STALE
    elif AeatSyncWorkspaceAvailability.LOCKED in states:
        availability = AeatSyncWorkspaceAvailability.LOCKED
    elif all(item is AeatSyncWorkspaceAvailability.NEVER_CAPTURED for item in states):
        availability = AeatSyncWorkspaceAvailability.NEVER_CAPTURED
    else:
        availability = AeatSyncWorkspaceAvailability.UNAVAILABLE
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


def _observable(value: AeatSyncWorkspaceAvailability) -> bool:
    return value in {AeatSyncWorkspaceAvailability.AVAILABLE, AeatSyncWorkspaceAvailability.STALE}


def _optional_time(state: object, when: UtcInstant | None, missing: object) -> None:
    if (state is missing) == (when is not None):
        raise ValueError("state contradicts observation time")


def _dual(
    local: AeatSyncSourceState, local_at: UtcInstant | None, aeat: AeatSyncSourceState, aeat_at: UtcInstant | None
) -> None:
    _optional_time(local, local_at, AeatSyncSourceState.NOT_OBSERVED)
    _optional_time(aeat, aeat_at, AeatSyncSourceState.NOT_OBSERVED)


def _discrepancy(local: AeatSyncSourceState, aeat: AeatSyncSourceState, kind: AeatSyncDiscrepancyKind) -> None:
    if AeatSyncSourceState.NOT_OBSERVED in {local, aeat}:
        expected = AeatSyncDiscrepancyKind.UNOBSERVED
    elif local == aeat:
        expected = AeatSyncDiscrepancyKind.NONE
    elif local is AeatSyncSourceState.ABSENT:
        expected = AeatSyncDiscrepancyKind.AEAT_ONLY
    elif aeat is AeatSyncSourceState.ABSENT:
        expected = AeatSyncDiscrepancyKind.LOCAL_ONLY
    elif AeatSyncSourceState.CONFLICT in {local, aeat}:
        expected = AeatSyncDiscrepancyKind.CONTRADICTORY_SOURCE
    else:
        expected = AeatSyncDiscrepancyKind.STATE_MISMATCH
    if kind is not expected:
        raise ValueError("discrepancy contradicts source states")
