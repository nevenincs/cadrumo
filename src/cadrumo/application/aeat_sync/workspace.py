"""Safe immutable projection for the six-zone AEAT Sync workspace."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Final, Protocol, Self, override

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints, TypeAdapter, model_validator

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

_NOTIFICATION_SELECTION_KEY: Final[bytes] = secrets.token_bytes(32)
_NOTIFICATION_SELECTION_PREFIX: Final[str] = "aeat_sync.notification."
_NOTIFICATION_SELECTION_DIGEST_LENGTH: Final[int] = 64

type AeatSyncNotificationSelectionKey = Annotated[
    str,
    StringConstraints(
        min_length=len(_NOTIFICATION_SELECTION_PREFIX) + _NOTIFICATION_SELECTION_DIGEST_LENGTH,
        max_length=len(_NOTIFICATION_SELECTION_PREFIX) + _NOTIFICATION_SELECTION_DIGEST_LENGTH,
        pattern=r"^aeat_sync\.notification\.[0-9a-f]{64}$",
    ),
]
"""Opaque, bounded identity for one projected notification row.

The admission coordinate remains on :class:`AeatSyncWorkspaceFactV1` only.
Projection derives this key from that coordinate and reconstructs the public
row, so the public snapshot retains a stable semantic focus address without
retaining the private notification identity.
"""


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


class AeatSyncWorkspaceActionRowV1(BaseModel):
    """Public immutable capability provenance shared by every workspace row."""

    model_config = STRICT_FROZEN_CONFIG
    supported_actions: tuple[ActionReference, ...] = ()
    supported_operations: tuple[OperationDefinitionId, ...] = ()


class AeatSyncWorkspaceOverviewRowV1(AeatSyncWorkspaceActionRowV1):
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


class AeatSyncWorkspaceCensusRowV1(AeatSyncWorkspaceActionRowV1):
    """One census field's local-versus-AEAT status.

    Carries no value yet, and the docstring no longer claims that as a safety
    property: it is a GAP. Nothing produces these rows outside fixtures, and
    their AEAT side stays never-captured until a pull happens, so there is no
    captured value to carry. When a producer exists the values belong here, on
    the same reasoning as every other authenticated surface.
    """

    path: str = Field(min_length=1, max_length=256)
    category: AeatSyncCensusCategory
    status: AeatSyncCensusStatus
    local_value: str | None = Field(default=None, max_length=256)
    """What the local profile holds for this field, or nothing when unobserved."""
    aeat_value: str | None = Field(default=None, max_length=256)
    """What the AEAT censo holds, or nothing when no pull has observed it.

    `None` on either side is UNOBSERVED, never an empty field. A censo entry the
    taxpayer has genuinely left blank is the empty string, and collapsing the
    two would tell an operator AEAT holds nothing where in truth nobody has
    looked -- which is the difference between "correct" and "unchecked" on a
    comparison whose entire purpose is to show what differs.
    """

    @model_validator(mode="after")
    def _conflict_needs_both_sides(self) -> Self:
        """A CONFLICT is a claim about two values, so it must carry both.

        Reporting a conflict while withholding one side asks the operator to
        accept a difference they cannot see, which is the same defect the
        invoice/entry suggestions carried before they showed the amounts they
        compared.
        """
        if self.status is AeatSyncCensusStatus.CONFLICT and (self.local_value is None or self.aeat_value is None):
            raise ValueError("a census conflict must carry both the local and the AEAT value")
        return self


class AeatSyncWorkspaceFiledDeclarationRowV1(AeatSyncWorkspaceActionRowV1):
    """Safe public filed-declaration comparison."""

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
    """Safe public notification metadata.

    ``selection_key`` is populated only by :func:`project_aeat_sync_workspace`.
    An admission row may leave it absent; the projector always replaces it
    from the fact's private coordinate before exposing the row publicly.
    """

    model_config = STRICT_FROZEN_CONFIG

    issued_on: date
    read_on: date | None = None
    read_state: AeatSyncNotificationReadState
    category: AeatSyncNotificationCategory
    document_custody_state: AeatSyncDocumentCustodyState
    document_custody_observed_at: UtcInstant | None = None
    selection_key: AeatSyncNotificationSelectionKey | None = None

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


class _DualRow(AeatSyncWorkspaceActionRowV1):
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    local_state: AeatSyncSourceState
    aeat_state: AeatSyncSourceState
    local_observed_at: UtcInstant | None = None
    aeat_observed_at: UtcInstant | None = None
    discrepancy_kind: AeatSyncDiscrepancyKind
    local_value: str | None = Field(default=None, max_length=256)
    """What the local record holds for the compared figure, or nothing.

    `None` is UNOBSERVED, not empty and not zero. A row can legitimately have
    no value on a side that was never read, and the state axis above already
    says which side that is.
    """
    aeat_value: str | None = Field(default=None, max_length=256)
    """What AEAT holds for the same figure, or nothing when unobserved."""

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("period and filing year disagree")
        _dual(self.local_state, self.local_observed_at, self.aeat_state, self.aeat_observed_at)
        _discrepancy(self.local_state, self.aeat_state, self.discrepancy_kind)
        _compared_values(self.discrepancy_kind, self.local_value, self.aeat_value)
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
        selection_keys = tuple(row.selection_key for row in self.notifications)
        if any(key is None for key in selection_keys):
            raise ValueError("projected notifications require selection keys")
        if len(selection_keys) != len(set(selection_keys)):
            raise ValueError("projected notification selection keys must be unique")
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
    out_notifications = _project_notification_rows(notifications)
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
            if isinstance(fact.row, AeatSyncWorkspaceNotificationRowV1):
                continue
            action_row = fact.row
            actions = action_row.supported_actions
            ids = tuple(str(item.action_id) for item in actions)
            _unique(ids, "row actions")
            if zone is AeatSyncWorkspaceZone.OVERVIEW:
                if not isinstance(fact.row, AeatSyncWorkspaceOverviewRowV1):
                    raise AeatSyncWorkspaceProjectionError("overview facts require overview rows")
                key = f"overview:{fact.row.area.value}"
            else:
                key = zone.value
            for action_id in ids:
                try:
                    catalogue.lookup(action_id)
                except KeyError as error:
                    raise AeatSyncWorkspaceProjectionError("action is not admitted by catalogue") from error
            if not set(ids) <= _ALLOWED[key]:
                raise AeatSyncWorkspaceProjectionError("action is not allowed for row area/state")
            operation_ids = action_row.supported_operations
            operation_id_values: set[str] = {str(item) for item in operation_ids}
            _unique(operation_ids, "row operations")
            allowed_operations = _ALLOWED_OPERATIONS[key]
            for operation_id in operation_ids:
                contract = contract_by_id.get(operation_id)
                if contract is None or OperationFrontendProjection.TUI not in contract.permitted_frontends:
                    raise AeatSyncWorkspaceProjectionError("operation is not admitted by public contracts")
            if not set(operation_ids) <= allowed_operations:
                raise AeatSyncWorkspaceProjectionError("operation is not allowed for row area/state")
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


_NOTIFICATION_SELECTION_NAMESPACE: Final[str] = "aeat_sync.notification.selection.v1"


def _notification_selection_key(private_identity: str) -> AeatSyncNotificationSelectionKey:
    """Derive a process-stable public focus key without retaining private data."""
    canonical = "\x1f".join((_NOTIFICATION_SELECTION_NAMESPACE, private_identity)).encode("utf-8")
    digest = hmac.digest(_NOTIFICATION_SELECTION_KEY, canonical, hashlib.sha256).hex()
    return f"{_NOTIFICATION_SELECTION_PREFIX}{digest}"


def _project_notification_rows(
    facts: tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceNotificationRowV1], ...],
) -> tuple[AeatSyncWorkspaceNotificationRowV1, ...]:
    """Project notification rows with opaque keys and protected-value-free ordering."""
    keyed: list[
        tuple[AeatSyncNotificationSelectionKey, AeatSyncWorkspaceFactV1[AeatSyncWorkspaceNotificationRowV1]]
    ] = []
    for fact in facts:
        if fact.private_identity is None:
            raise AeatSyncWorkspaceProjectionError("notification requires private identity")
        keyed.append((_notification_selection_key(fact.private_identity), fact))
    _unique((key for key, _ in keyed), "notification selection identities")
    return tuple(
        _public_notification_row(fact.row, key)
        for key, fact in sorted(keyed, key=lambda item: (item[1].row.issued_on, item[0]))
    )


def _public_notification_row(
    row: AeatSyncWorkspaceNotificationRowV1,
    selection_key: AeatSyncNotificationSelectionKey,
) -> AeatSyncWorkspaceNotificationRowV1:
    """Rebuild one notification row and inject only its safe selection key."""
    values = row.model_dump(include=set(AeatSyncWorkspaceNotificationRowV1.model_fields))
    values["selection_key"] = selection_key
    return AeatSyncWorkspaceNotificationRowV1.model_validate(values)


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


def _zone_state(observation: AeatSyncWorkspaceZoneObservationV1, count: int) -> AeatSyncWorkspaceZoneStateV1:
    states = tuple(item.availability for item in observation.sources)
    if observation.zone in _COMPARISON_ZONES:
        seen = all(_observable(item) for item in states)
    else:
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


def _compared_values(
    kind: AeatSyncDiscrepancyKind,
    local_value: str | None,
    aeat_value: str | None,
) -> None:
    """Refuse a difference claim that withholds one of the values it compares.

    STATE_MISMATCH and CONTRADICTORY_SOURCE both assert that two observed sides
    disagree. Making that claim while hiding a side leaves the operator to
    accept a difference they cannot inspect -- the same defect the invoice/entry
    suggestions carried before they showed their amounts.

    The one-sided kinds are deliberately exempt. LOCAL_ONLY and AEAT_ONLY say
    the other side is ABSENT, so there is no second value to carry; UNOBSERVED
    says nobody looked; NONE says the sides agree and needs no evidence of
    difference.
    """
    if kind not in {AeatSyncDiscrepancyKind.STATE_MISMATCH, AeatSyncDiscrepancyKind.CONTRADICTORY_SOURCE}:
        return
    if local_value is None or aeat_value is None:
        raise ValueError(f"a {kind.value} row must carry both the local and the AEAT value")


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
