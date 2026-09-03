"""Safe, immutable application projection for the AEAT Sync workspace.

The projector in this module consumes only already-loaded, typed facts.  It has
no repository, adapter, browser, network, clock, or filesystem dependency.
Its output is suitable for a frontend: every protected identity or payload
coordinate supplied by a reader is either used only to validate a join/order
or is omitted from the public representation entirely.

The six workspace zones are deliberately closed.  A zone's availability is
independent from its source state and from the rows it may expose.  Observable
zones (``AVAILABLE`` and ``STALE``) carry a last observation and a measured
count; non-observable zones carry a refusal and never masquerade as an empty
result.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.filing_year import FilingYear
from ...core.identifier_grammar import NamespacedId
from ...core.identity import BucketId
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from ...core.time.utc import UtcInstant
from ...domain.modelos.codes import ModeloCode

AEAT_SYNC_WORKSPACE_CONTRACT_VERSION: Final[int] = 1


class AeatSyncWorkspaceProjectionError(ValueError):
    """Already-loaded AEAT Sync authorities cannot form one safe snapshot."""


class AeatSyncWorkspaceZone(StrEnum):
    """The exact operator-facing areas owned by AEAT Sync."""

    OVERVIEW = "overview"
    CENSUS = "census"
    FILED_DECLARATIONS = "filed_declarations"
    NOTIFICATIONS = "notifications"
    EVIDENCE_COMPARISON = "evidence_comparison"
    RECONCILIATION = "reconciliation"


class AeatSyncWorkspaceSource(StrEnum):
    """Authorities which can contribute to an AEAT Sync zone."""

    LOCAL_PROFILE = "local.profile"
    LOCAL_FILINGS = "local.filings"
    LOCAL_NOTIFICATION_CUSTODY = "local.notification_custody"
    LOCAL_RECONCILIATION = "local.reconciliation"
    AEAT_CENSUS = "aeat.census"
    AEAT_FILED_DECLARATIONS = "aeat.filed_declarations"
    AEAT_NOTIFICATIONS = "aeat.notifications"


class AeatSyncWorkspaceAvailability(StrEnum):
    """Whether a zone has an authoritative observation available to render."""

    AVAILABLE = "available"
    LOCKED = "locked"
    STALE = "stale"
    NEVER_CAPTURED = "never_captured"
    UNAVAILABLE = "unavailable"


class AeatSyncSourceState(StrEnum):
    """Safe state of one side of a comparison.

    These values are deliberately not financial or taxpayer values.  They say
    only whether a source observed an item and the coarse outcome it declared.
    """

    NOT_OBSERVED = "not_observed"
    ABSENT = "absent"
    PRESENT = "present"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONFLICT = "conflict"


class AeatSyncDiscrepancyKind(StrEnum):
    """Closed safe vocabulary for source comparison outcomes."""

    NONE = "none"
    LOCAL_ONLY = "local_only"
    AEAT_ONLY = "aeat_only"
    STATE_MISMATCH = "state_mismatch"
    CONTRADICTORY_SOURCE = "contradictory_source"
    UNOBSERVED = "unobserved"


class AeatSyncSupportedAction(StrEnum):
    """Actions the application has explicitly admitted for an AEAT Sync row.

    This is intentionally an enum rather than a command string or URL.  A
    frontend may render only these application-owned capabilities and resolves
    any command path at its own live surface.
    """

    PULL_CENSUS = "pull_census"
    PULL_FILED_DECLARATIONS = "pull_filed_declarations"
    PULL_NOTIFICATIONS = "pull_notifications"
    COMPARE = "compare"
    REVIEW = "review"
    ADOPT_CENSUS = "adopt_census"
    RECONCILE = "reconcile"
    OPEN_LOCAL_FILING = "open_local_filing"


class AeatSyncOverviewArea(StrEnum):
    """Closed set of safe areas represented by an overview row."""

    CENSUS = "census"
    FILED_DECLARATIONS = "filed_declarations"
    NOTIFICATIONS = "notifications"
    EVIDENCE_COMPARISON = "evidence_comparison"
    RECONCILIATION = "reconciliation"


class AeatSyncCensusCategory(StrEnum):
    """Safe categories for censal paths; no observed value crosses the seam."""

    ADDRESS = "address"
    ACTIVITY = "activity"
    OBLIGATION = "obligation"
    CONTACT = "contact"
    OTHER = "other"


class AeatSyncCensusStatus(StrEnum):
    """Outcome of comparing one safe censal path with local profile state."""

    ADOPTED = "adopted"
    CONFLICT = "conflict"
    UNCHANGED = "unchanged"
    UNSET = "unset"


class AeatSyncLocalFilingState(StrEnum):
    """Application-side filing state, independent from AEAT observation."""

    NOT_OBSERVED = "not_observed"
    DRAFT = "draft"
    READY = "ready"
    FILED = "filed"


class AeatSyncAeatObservationState(StrEnum):
    """AEAT-side state observed for one natural filed-declaration address."""

    NOT_OBSERVED = "not_observed"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class AeatSyncJustificanteState(StrEnum):
    """Safe custody state for an AEAT justificante."""

    NOT_OBSERVED = "not_observed"
    UNAVAILABLE = "unavailable"
    AVAILABLE = "available"
    VERIFIED = "verified"


class AeatSyncNotificationCategory(StrEnum):
    """Safe notification class without the authority's free-text concept."""

    FORMAL = "formal"
    COMMUNICATION = "communication"
    PENDING = "pending"
    OTHER = "other"


class AeatSyncNotificationReadState(StrEnum):
    """AEAT read marker with unknown kept distinct from unread."""

    UNKNOWN = "unknown"
    UNREAD = "unread"
    READ = "read"


class AeatSyncDocumentCustodyState(StrEnum):
    """Whether encrypted document custody exists for a notification."""

    NOT_CAPTURED = "not_captured"
    HELD = "held"
    REFUSED = "refused"
    UNAVAILABLE = "unavailable"


class AeatSyncReconciliationState(StrEnum):
    """Safe reconciliation outcome, never a free-form adjudication note."""

    UNRESOLVED = "unresolved"
    KEEP_LOCAL = "keep_local"
    ACCEPT_AEAT = "accept_aeat"
    DISMISSED = "dismissed"
    NO_ACTION = "no_action"


class AeatSyncWorkspaceZoneObservationV1(BaseModel):
    """Caller-supplied availability/freshness observation for one zone."""

    model_config = STRICT_FROZEN_CONFIG

    zone: AeatSyncWorkspaceZone
    availability: AeatSyncWorkspaceAvailability
    observed_at: UtcInstant | None = None
    refusal: NamespacedId | None = None

    @property
    def reason_code(self) -> NamespacedId | None:
        """Return the refusal under the common application vocabulary."""
        return self.refusal

    @model_validator(mode="after")
    def _availability_has_truthful_evidence(self) -> Self:
        observable = self.availability in {
            AeatSyncWorkspaceAvailability.AVAILABLE,
            AeatSyncWorkspaceAvailability.STALE,
        }
        if observable and self.observed_at is None:
            raise ValueError("an available or stale AEAT Sync zone requires an observation time")
        if self.availability is AeatSyncWorkspaceAvailability.AVAILABLE and self.refusal is not None:
            raise ValueError("an available AEAT Sync zone cannot carry a refusal")
        if self.availability is not AeatSyncWorkspaceAvailability.AVAILABLE and self.refusal is None:
            raise ValueError("a non-available AEAT Sync zone requires a refusal")
        if self.availability is AeatSyncWorkspaceAvailability.NEVER_CAPTURED and self.observed_at is not None:
            raise ValueError("a never-captured AEAT Sync zone cannot carry an observation time")
        return self


class AeatSyncWorkspaceZoneStateV1(AeatSyncWorkspaceZoneObservationV1):
    """Zone observation plus its measured row cardinality and authorities."""

    sources: tuple[AeatSyncWorkspaceSource, ...]
    item_count: NonNegativeInt | None = None

    @property
    def measured_count(self) -> NonNegativeInt | None:
        """Return the measured count under the descriptive vocabulary."""
        return self.item_count

    @model_validator(mode="after")
    def _count_matches_observability(self) -> Self:
        observable = self.availability in {
            AeatSyncWorkspaceAvailability.AVAILABLE,
            AeatSyncWorkspaceAvailability.STALE,
        }
        if observable != (self.item_count is not None):
            raise ValueError("only observable AEAT Sync zones carry a measured item count")
        if not self.sources or len(self.sources) != len(set(self.sources)):
            raise ValueError("an AEAT Sync zone requires unique source authorities")
        return self


class AeatSyncWorkspaceOverviewRowV1(BaseModel):
    """Safe overview status with independent local and AEAT source axes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    area: AeatSyncOverviewArea
    local_state: AeatSyncSourceState
    aeat_state: AeatSyncSourceState
    local_observed_at: UtcInstant | None = None
    aeat_observed_at: UtcInstant | None = None
    discrepancy_kind: AeatSyncDiscrepancyKind
    supported_actions: tuple[AeatSyncSupportedAction, ...] = ()

    # Private validation/order coordinates and deliberately excluded payload.
    semantic_identity: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=256)
    bucket_id: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=128)
    subject_key: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=128)
    name: str | None = Field(default=None, exclude=True, repr=False)
    nif: str | None = Field(default=None, exclude=True, repr=False)
    source_url: str | None = Field(default=None, exclude=True, repr=False)
    concept: str | None = Field(default=None, exclude=True, repr=False)
    document_text: str | None = Field(default=None, exclude=True, repr=False)
    raw_evidence: object | None = Field(default=None, exclude=True, repr=False)
    secret: str | None = Field(default=None, exclude=True, repr=False)

    @model_validator(mode="after")
    def _source_axes_are_coherent(self) -> Self:
        _validate_source_axis(self.local_state, self.local_observed_at, axis="local")
        _validate_source_axis(self.aeat_state, self.aeat_observed_at, axis="AEAT")
        _validate_discrepancy(
            local_state=self.local_state,
            aeat_state=self.aeat_state,
            discrepancy_kind=self.discrepancy_kind,
        )
        return self


class AeatSyncWorkspaceCensusRowV1(BaseModel):
    """Sanitized census row: safe path/category and adoption outcome only."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    path: str = Field(min_length=1, max_length=256)
    category: AeatSyncCensusCategory
    status: AeatSyncCensusStatus

    # Private coordinates/payload accepted from a reader but never serialized.
    semantic_identity: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=256)
    bucket_id: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=128)
    subject_key: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=128)
    observed_value: str | None = Field(default=None, exclude=True, repr=False)
    local_value: str | None = Field(default=None, exclude=True, repr=False)
    name: str | None = Field(default=None, exclude=True, repr=False)
    nif: str | None = Field(default=None, exclude=True, repr=False)
    source_url: str | None = Field(default=None, exclude=True, repr=False)
    raw_evidence: object | None = Field(default=None, exclude=True, repr=False)
    secret: str | None = Field(default=None, exclude=True, repr=False)


class AeatSyncWorkspaceFiledDeclarationRowV1(BaseModel):
    """Natural filed-declaration address with independent local/AEAT axes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    local_filing_state: AeatSyncLocalFilingState
    local_filed_at: UtcInstant | None = None
    aeat_observation_state: AeatSyncAeatObservationState
    aeat_observed_at: UtcInstant | None = None
    justificante_state: AeatSyncJustificanteState
    justificante_observed_at: UtcInstant | None = None

    semantic_identity: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=256)
    bucket_id: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=128)
    subject_key: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=128)
    expediente_id: str | None = Field(default=None, exclude=True, repr=False)
    certificado_id: str | None = Field(default=None, exclude=True, repr=False)
    justificante_id: str | None = Field(default=None, exclude=True, repr=False)
    source_url: str | None = Field(default=None, exclude=True, repr=False)
    document_text: str | None = Field(default=None, exclude=True, repr=False)
    raw_evidence: object | None = Field(default=None, exclude=True, repr=False)
    name: str | None = Field(default=None, exclude=True, repr=False)
    nif: str | None = Field(default=None, exclude=True, repr=False)
    secret: str | None = Field(default=None, exclude=True, repr=False)

    @property
    def aeat_submission_state(self) -> AeatSyncAeatObservationState:
        """Return the AEAT axis under the filing-calendar vocabulary."""
        return self.aeat_observation_state

    @model_validator(mode="after")
    def _filing_axes_are_coherent(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("filed declaration period must match its filing year")
        if self.local_filing_state is AeatSyncLocalFilingState.FILED:
            if self.local_filed_at is None:
                raise ValueError("a filed local declaration requires its filing time")
        elif self.local_filed_at is not None:
            raise ValueError("only a filed local declaration may carry a local filing time")
        _validate_optional_state_time(
            self.aeat_observation_state,
            self.aeat_observed_at,
            missing=AeatSyncAeatObservationState.NOT_OBSERVED,
            axis="AEAT observation",
        )
        _validate_justificante_axis(
            aeat_state=self.aeat_observation_state,
            justificante_state=self.justificante_state,
            observed_at=self.justificante_observed_at,
        )
        return self


class AeatSyncWorkspaceNotificationRowV1(BaseModel):
    """Notification metadata with private semantic identity and custody state."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    semantic_identity: str = Field(min_length=1, max_length=256, exclude=True, repr=False)
    issued_on: date
    read_on: date | None = None
    read_state: AeatSyncNotificationReadState
    category: AeatSyncNotificationCategory
    document_custody_state: AeatSyncDocumentCustodyState
    document_custody_observed_at: UtcInstant | None = None

    bucket_id: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=128)
    subject_key: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=128)
    certificado_id: str | None = Field(default=None, exclude=True, repr=False)
    concepto: str | None = Field(default=None, exclude=True, repr=False)
    titular_nombre: str | None = Field(default=None, exclude=True, repr=False)
    destinatario_nombre: str | None = Field(default=None, exclude=True, repr=False)
    titular_nif: str | None = Field(default=None, exclude=True, repr=False)
    destinatario_nif: str | None = Field(default=None, exclude=True, repr=False)
    source_url: str | None = Field(default=None, exclude=True, repr=False)
    document_text: str | None = Field(default=None, exclude=True, repr=False)
    raw_evidence: object | None = Field(default=None, exclude=True, repr=False)
    secret: str | None = Field(default=None, exclude=True, repr=False)

    @property
    def issue_date(self) -> date:
        """Return the authority's issue date under an English display name."""
        return self.issued_on

    @property
    def read_date(self) -> date | None:
        """Return the optional authority read date."""
        return self.read_on

    @model_validator(mode="after")
    def _notification_axes_are_coherent(self) -> Self:
        if self.read_state is AeatSyncNotificationReadState.READ:
            if self.read_on is None:
                raise ValueError("a read notification requires its read date")
        elif self.read_on is not None:
            raise ValueError("only a read notification may carry a read date")
        if self.read_on is not None and self.read_on < self.issued_on:
            raise ValueError("notification read date cannot precede its issue date")
        if (
            self.category is AeatSyncNotificationCategory.PENDING
            and self.read_state is not AeatSyncNotificationReadState.UNKNOWN
        ):
            raise ValueError("a pending notification must retain an unknown read state")
        if self.document_custody_state is AeatSyncDocumentCustodyState.HELD:
            if self.read_state is not AeatSyncNotificationReadState.READ:
                raise ValueError("notification document custody requires AEAT read state")
            if self.document_custody_observed_at is None:
                raise ValueError("held notification custody requires an observation time")
        elif self.document_custody_observed_at is not None:
            raise ValueError("only held notification custody may carry an observation time")
        return self


class AeatSyncWorkspaceEvidenceComparisonRowV1(BaseModel):
    """One natural filing comparison with both source states retained."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    local_state: AeatSyncSourceState
    aeat_state: AeatSyncSourceState
    local_observed_at: UtcInstant | None = None
    aeat_observed_at: UtcInstant | None = None
    discrepancy_kind: AeatSyncDiscrepancyKind
    supported_actions: tuple[AeatSyncSupportedAction, ...] = ()

    semantic_identity: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=256)
    bucket_id: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=128)
    subject_key: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=128)
    source_url: str | None = Field(default=None, exclude=True, repr=False)
    raw_evidence: object | None = Field(default=None, exclude=True, repr=False)
    document_text: str | None = Field(default=None, exclude=True, repr=False)
    secret: str | None = Field(default=None, exclude=True, repr=False)

    @model_validator(mode="after")
    def _comparison_axes_are_coherent(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("evidence comparison period must match its filing year")
        _validate_source_axis(self.local_state, self.local_observed_at, axis="local")
        _validate_source_axis(self.aeat_state, self.aeat_observed_at, axis="AEAT")
        _validate_discrepancy(
            local_state=self.local_state,
            aeat_state=self.aeat_state,
            discrepancy_kind=self.discrepancy_kind,
        )
        return self


class AeatSyncWorkspaceReconciliationRowV1(BaseModel):
    """One safe reconciliation finding and only its admitted next actions."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    local_state: AeatSyncSourceState
    aeat_state: AeatSyncSourceState
    local_observed_at: UtcInstant | None = None
    aeat_observed_at: UtcInstant | None = None
    discrepancy_kind: AeatSyncDiscrepancyKind
    reconciliation_state: AeatSyncReconciliationState
    supported_actions: tuple[AeatSyncSupportedAction, ...] = ()

    semantic_identity: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=256)
    bucket_id: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=128)
    subject_key: str | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=128)
    source_url: str | None = Field(default=None, exclude=True, repr=False)
    raw_evidence: object | None = Field(default=None, exclude=True, repr=False)
    document_text: str | None = Field(default=None, exclude=True, repr=False)
    secret: str | None = Field(default=None, exclude=True, repr=False)

    @model_validator(mode="after")
    def _reconciliation_axes_are_coherent(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("reconciliation period must match its filing year")
        _validate_source_axis(self.local_state, self.local_observed_at, axis="local")
        _validate_source_axis(self.aeat_state, self.aeat_observed_at, axis="AEAT")
        _validate_discrepancy(
            local_state=self.local_state,
            aeat_state=self.aeat_state,
            discrepancy_kind=self.discrepancy_kind,
        )
        if self.discrepancy_kind is AeatSyncDiscrepancyKind.NONE:
            if self.reconciliation_state is not AeatSyncReconciliationState.NO_ACTION:
                raise ValueError("a matching reconciliation must have no action")
        elif self.reconciliation_state is AeatSyncReconciliationState.NO_ACTION:
            raise ValueError("a discrepant reconciliation cannot have no action")
        return self


class AeatSyncWorkspaceProjectionV1(BaseModel):
    """Complete immutable, redacted AEAT Sync snapshot for one profile bucket."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: int = AEAT_SYNC_WORKSPACE_CONTRACT_VERSION
    bucket_id: BucketId = Field(exclude=True, repr=False)
    zones: tuple[AeatSyncWorkspaceZoneStateV1, ...]
    overview: tuple[AeatSyncWorkspaceOverviewRowV1, ...] = ()
    census: tuple[AeatSyncWorkspaceCensusRowV1, ...] = ()
    filed_declarations: tuple[AeatSyncWorkspaceFiledDeclarationRowV1, ...] = ()
    notifications: tuple[AeatSyncWorkspaceNotificationRowV1, ...] = ()
    evidence_comparison: tuple[AeatSyncWorkspaceEvidenceComparisonRowV1, ...] = ()
    reconciliation: tuple[AeatSyncWorkspaceReconciliationRowV1, ...] = ()

    @model_validator(mode="after")
    def _zones_and_counts_are_total(self) -> Self:
        if self.contract_version != AEAT_SYNC_WORKSPACE_CONTRACT_VERSION:
            raise ValueError("unsupported AEAT Sync workspace contract version")
        if tuple(state.zone for state in self.zones) != tuple(AeatSyncWorkspaceZone):
            raise ValueError("AEAT Sync zones must cover the closed catalogue in canonical order")
        rows_by_zone: dict[AeatSyncWorkspaceZone, tuple[object, ...]] = {
            AeatSyncWorkspaceZone.OVERVIEW: self.overview,
            AeatSyncWorkspaceZone.CENSUS: self.census,
            AeatSyncWorkspaceZone.FILED_DECLARATIONS: self.filed_declarations,
            AeatSyncWorkspaceZone.NOTIFICATIONS: self.notifications,
            AeatSyncWorkspaceZone.EVIDENCE_COMPARISON: self.evidence_comparison,
            AeatSyncWorkspaceZone.RECONCILIATION: self.reconciliation,
        }
        for state in self.zones:
            rows = rows_by_zone[state.zone]
            observable = state.availability in {
                AeatSyncWorkspaceAvailability.AVAILABLE,
                AeatSyncWorkspaceAvailability.STALE,
            }
            if state.item_count != (len(rows) if observable else None):
                raise ValueError(f"AEAT Sync {state.zone.value} measured count contradicts its rows")
            if not observable and rows:
                raise ValueError(f"a non-observable AEAT Sync {state.zone.value} zone cannot carry rows")
        return self


_SOURCES_BY_ZONE: Final[dict[AeatSyncWorkspaceZone, tuple[AeatSyncWorkspaceSource, ...]]] = {
    AeatSyncWorkspaceZone.OVERVIEW: (
        AeatSyncWorkspaceSource.LOCAL_PROFILE,
        AeatSyncWorkspaceSource.LOCAL_FILINGS,
        AeatSyncWorkspaceSource.LOCAL_NOTIFICATION_CUSTODY,
        AeatSyncWorkspaceSource.LOCAL_RECONCILIATION,
        AeatSyncWorkspaceSource.AEAT_CENSUS,
        AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS,
        AeatSyncWorkspaceSource.AEAT_NOTIFICATIONS,
    ),
    AeatSyncWorkspaceZone.CENSUS: (
        AeatSyncWorkspaceSource.LOCAL_PROFILE,
        AeatSyncWorkspaceSource.AEAT_CENSUS,
    ),
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


def project_aeat_sync_workspace(
    *,
    bucket_id: BucketId,
    zone_observations: tuple[AeatSyncWorkspaceZoneObservationV1, ...],
    overview: tuple[AeatSyncWorkspaceOverviewRowV1, ...] = (),
    census: tuple[AeatSyncWorkspaceCensusRowV1, ...] = (),
    filed_declarations: tuple[AeatSyncWorkspaceFiledDeclarationRowV1, ...] = (),
    notifications: tuple[AeatSyncWorkspaceNotificationRowV1, ...] = (),
    evidence_comparison: tuple[AeatSyncWorkspaceEvidenceComparisonRowV1, ...] = (),
    reconciliation: tuple[AeatSyncWorkspaceReconciliationRowV1, ...] = (),
    subject_key: str | None = None,
) -> AeatSyncWorkspaceProjectionV1:
    """Build one deterministic projection from already-loaded safe facts.

    ``subject_key`` is an optional opaque composition-root coordinate.  When
    supplied, every row that carries one must match it; when omitted, all
    observable private subject coordinates must still agree with each other.
    It is never retained in the serialized projection.
    """
    observations = _validate_zone_observations(zone_observations)
    # The zones carry different row types, so the by-zone map is deliberately
    # widened for the scope and observability passes that read only the shared
    # coordinates.  Everything that reaches into a row's own fields takes the
    # concrete tuple instead.
    rows: dict[AeatSyncWorkspaceZone, tuple[object, ...]] = {
        AeatSyncWorkspaceZone.OVERVIEW: overview,
        AeatSyncWorkspaceZone.CENSUS: census,
        AeatSyncWorkspaceZone.FILED_DECLARATIONS: filed_declarations,
        AeatSyncWorkspaceZone.NOTIFICATIONS: notifications,
        AeatSyncWorkspaceZone.EVIDENCE_COMPARISON: evidence_comparison,
        AeatSyncWorkspaceZone.RECONCILIATION: reconciliation,
    }
    all_rows = tuple(row for group in rows.values() for row in group)
    _validate_scope(bucket_id=bucket_id, expected_subject=subject_key, rows=all_rows)
    _validate_duplicate_identities(
        overview=overview,
        census=census,
        filed_declarations=filed_declarations,
        notifications=notifications,
        evidence_comparison=evidence_comparison,
        reconciliation=reconciliation,
    )

    for zone, values in rows.items():
        if (
            observations[zone].availability
            not in {
                AeatSyncWorkspaceAvailability.AVAILABLE,
                AeatSyncWorkspaceAvailability.STALE,
            }
            and values
        ):
            raise AeatSyncWorkspaceProjectionError(
                f"non-observable AEAT Sync {zone.value} carries confident rows",
            )

    projected = {
        AeatSyncWorkspaceZone.OVERVIEW: _ordered_overview(overview),
        AeatSyncWorkspaceZone.CENSUS: _ordered_census(census),
        AeatSyncWorkspaceZone.FILED_DECLARATIONS: _ordered_filed_declarations(filed_declarations),
        AeatSyncWorkspaceZone.NOTIFICATIONS: _ordered_notifications(notifications),
        AeatSyncWorkspaceZone.EVIDENCE_COMPARISON: _ordered_comparisons(evidence_comparison),
        AeatSyncWorkspaceZone.RECONCILIATION: _ordered_reconciliations(reconciliation),
    }
    zones = tuple(
        AeatSyncWorkspaceZoneStateV1(
            zone=zone,
            availability=observations[zone].availability,
            observed_at=observations[zone].observed_at,
            refusal=observations[zone].refusal,
            sources=_SOURCES_BY_ZONE[zone],
            item_count=(len(projected[zone]) if _observable(observations[zone].availability) else None),
        )
        for zone in AeatSyncWorkspaceZone
    )
    return AeatSyncWorkspaceProjectionV1(
        bucket_id=bucket_id,
        zones=zones,
        overview=projected[AeatSyncWorkspaceZone.OVERVIEW],
        census=projected[AeatSyncWorkspaceZone.CENSUS],
        filed_declarations=projected[AeatSyncWorkspaceZone.FILED_DECLARATIONS],
        notifications=projected[AeatSyncWorkspaceZone.NOTIFICATIONS],
        evidence_comparison=projected[AeatSyncWorkspaceZone.EVIDENCE_COMPARISON],
        reconciliation=projected[AeatSyncWorkspaceZone.RECONCILIATION],
    )


def _validate_zone_observations(
    observations: tuple[AeatSyncWorkspaceZoneObservationV1, ...],
) -> dict[AeatSyncWorkspaceZone, AeatSyncWorkspaceZoneObservationV1]:
    expected = tuple(AeatSyncWorkspaceZone)
    actual = tuple(item.zone for item in observations)
    if actual != expected:
        raise AeatSyncWorkspaceProjectionError(
            "AEAT Sync zone observations must cover the closed catalogue in canonical order",
        )
    return {item.zone: item for item in observations}


def _validate_scope(
    *,
    bucket_id: BucketId,
    expected_subject: str | None,
    rows: tuple[object, ...],
) -> None:
    if expected_subject is not None and not expected_subject.strip():
        raise AeatSyncWorkspaceProjectionError("AEAT Sync subject key cannot be blank")
    observed_subjects: set[str] = set()
    for row in rows:
        row_bucket = getattr(row, "bucket_id", None)
        if row_bucket is not None and row_bucket != bucket_id:
            raise AeatSyncWorkspaceProjectionError("AEAT Sync facts contain a foreign bucket")
        row_subject = getattr(row, "subject_key", None)
        if row_subject is not None:
            if expected_subject is not None and row_subject != expected_subject:
                raise AeatSyncWorkspaceProjectionError("AEAT Sync facts mix subjects")
            observed_subjects.add(row_subject)
    if expected_subject is None and len(observed_subjects) > 1:
        raise AeatSyncWorkspaceProjectionError("AEAT Sync facts mix subjects")


def _validate_duplicate_identities(
    *,
    overview: tuple[AeatSyncWorkspaceOverviewRowV1, ...],
    census: tuple[AeatSyncWorkspaceCensusRowV1, ...],
    filed_declarations: tuple[AeatSyncWorkspaceFiledDeclarationRowV1, ...],
    notifications: tuple[AeatSyncWorkspaceNotificationRowV1, ...],
    evidence_comparison: tuple[AeatSyncWorkspaceEvidenceComparisonRowV1, ...],
    reconciliation: tuple[AeatSyncWorkspaceReconciliationRowV1, ...],
) -> None:
    # Every identity is checked independently at the source boundary.  Safe
    # natural addresses remain the fallback when a source intentionally does
    # not carry a private identity coordinate.
    _assert_unique(
        (identity for row in overview if (identity := row.semantic_identity) is not None),
        "overview semantic identities",
    )
    _assert_unique(
        ((row.path, row.category) for row in census),
        "census paths",
    )
    _assert_unique(
        (_natural_key(row) for row in filed_declarations),
        "filed declaration natural addresses",
    )
    _assert_unique(
        (row.semantic_identity for row in notifications),
        "notification semantic identities",
    )
    _assert_unique(
        (_natural_key(row) for row in evidence_comparison),
        "evidence comparison natural addresses",
    )
    _assert_unique(
        (_natural_key(row) for row in reconciliation),
        "reconciliation natural addresses",
    )


def _assert_unique(values: Iterable[object], label: str) -> None:
    materialized = tuple(values)
    if len(materialized) != len(set(materialized)):
        raise AeatSyncWorkspaceProjectionError(f"AEAT Sync facts contain duplicate {label}")


def _ordered_actions(actions: tuple[AeatSyncSupportedAction, ...]) -> tuple[AeatSyncSupportedAction, ...]:
    if len(actions) != len(set(actions)):
        raise AeatSyncWorkspaceProjectionError("AEAT Sync rows contain duplicate supported actions")
    return tuple(sorted(set(actions), key=lambda action: action.value))


def _ordered_overview(
    rows: tuple[AeatSyncWorkspaceOverviewRowV1, ...],
) -> tuple[AeatSyncWorkspaceOverviewRowV1, ...]:
    return tuple(
        row.model_copy(update={"supported_actions": _ordered_actions(row.supported_actions)})
        for row in sorted(
            rows,
            key=lambda row: (
                row.area.value,
                row.discrepancy_kind.value,
                row.semantic_identity or "",
            ),
        )
    )


def _ordered_census(rows: tuple[AeatSyncWorkspaceCensusRowV1, ...]) -> tuple[AeatSyncWorkspaceCensusRowV1, ...]:
    return tuple(sorted(rows, key=lambda row: (row.path, row.category.value, row.status.value)))


type _NaturalAddressRow = (
    AeatSyncWorkspaceFiledDeclarationRowV1
    | AeatSyncWorkspaceEvidenceComparisonRowV1
    | AeatSyncWorkspaceReconciliationRowV1
)


def _natural_key(row: _NaturalAddressRow) -> tuple[str, int, str]:
    return (str(row.modelo), row.filing_year, row.period.registry_token)


def _ordered_filed_declarations(
    rows: tuple[AeatSyncWorkspaceFiledDeclarationRowV1, ...],
) -> tuple[AeatSyncWorkspaceFiledDeclarationRowV1, ...]:
    return tuple(sorted(rows, key=lambda row: (*_natural_key(row), row.semantic_identity or "")))


def _ordered_notifications(
    rows: tuple[AeatSyncWorkspaceNotificationRowV1, ...],
) -> tuple[AeatSyncWorkspaceNotificationRowV1, ...]:
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.issued_on,
                row.read_on or date.max,
                row.category.value,
                row.semantic_identity,
            ),
        )
    )


def _ordered_comparisons(
    rows: tuple[AeatSyncWorkspaceEvidenceComparisonRowV1, ...],
) -> tuple[AeatSyncWorkspaceEvidenceComparisonRowV1, ...]:
    return tuple(
        row.model_copy(update={"supported_actions": _ordered_actions(row.supported_actions)})
        for row in sorted(rows, key=lambda row: (*_natural_key(row), row.semantic_identity or ""))
    )


def _ordered_reconciliations(
    rows: tuple[AeatSyncWorkspaceReconciliationRowV1, ...],
) -> tuple[AeatSyncWorkspaceReconciliationRowV1, ...]:
    return tuple(
        row.model_copy(update={"supported_actions": _ordered_actions(row.supported_actions)})
        for row in sorted(rows, key=lambda row: (*_natural_key(row), row.semantic_identity or ""))
    )


def _observable(availability: AeatSyncWorkspaceAvailability) -> bool:
    return availability in {
        AeatSyncWorkspaceAvailability.AVAILABLE,
        AeatSyncWorkspaceAvailability.STALE,
    }


def _validate_source_axis(
    state: AeatSyncSourceState,
    observed_at: UtcInstant | None,
    *,
    axis: str,
) -> None:
    if state is AeatSyncSourceState.NOT_OBSERVED:
        if observed_at is not None:
            raise ValueError(f"an unobserved {axis} source cannot carry an observation time")
    elif observed_at is None:
        raise ValueError(f"an observed {axis} source requires an observation time")


def _validate_optional_state_time(
    state: StrEnum,
    observed_at: UtcInstant | None,
    *,
    missing: StrEnum,
    axis: str,
) -> None:
    if state is missing and observed_at is not None:
        raise ValueError(f"an unobserved {axis} cannot carry an observation time")
    if state is not missing and observed_at is None:
        raise ValueError(f"an observed {axis} requires an observation time")


def _validate_justificante_axis(
    *,
    aeat_state: AeatSyncAeatObservationState,
    justificante_state: AeatSyncJustificanteState,
    observed_at: UtcInstant | None,
) -> None:
    if justificante_state in {
        AeatSyncJustificanteState.AVAILABLE,
        AeatSyncJustificanteState.VERIFIED,
    }:
        if observed_at is None:
            raise ValueError("an available or verified justificante requires an observation time")
        if aeat_state is AeatSyncAeatObservationState.NOT_OBSERVED:
            raise ValueError("a justificante cannot be confident before AEAT filing observation")
    elif observed_at is not None:
        raise ValueError("an unheld justificante state cannot carry an observation time")
    if (
        aeat_state is AeatSyncAeatObservationState.NOT_OBSERVED
        and justificante_state is not AeatSyncJustificanteState.NOT_OBSERVED
    ):
        raise ValueError("an unobserved AEAT filing cannot carry a justificante state")
    if aeat_state is AeatSyncAeatObservationState.REJECTED and justificante_state in {
        AeatSyncJustificanteState.AVAILABLE,
        AeatSyncJustificanteState.VERIFIED,
    }:
        raise ValueError("a rejected AEAT filing cannot carry a justificante")


def _expected_discrepancy(
    *,
    local_state: AeatSyncSourceState,
    aeat_state: AeatSyncSourceState,
) -> AeatSyncDiscrepancyKind:
    if local_state is AeatSyncSourceState.CONFLICT or aeat_state is AeatSyncSourceState.CONFLICT:
        return AeatSyncDiscrepancyKind.CONTRADICTORY_SOURCE
    if local_state is AeatSyncSourceState.NOT_OBSERVED or aeat_state is AeatSyncSourceState.NOT_OBSERVED:
        return AeatSyncDiscrepancyKind.UNOBSERVED
    if local_state is AeatSyncSourceState.ABSENT and aeat_state is not AeatSyncSourceState.ABSENT:
        return AeatSyncDiscrepancyKind.AEAT_ONLY
    if aeat_state is AeatSyncSourceState.ABSENT and local_state is not AeatSyncSourceState.ABSENT:
        return AeatSyncDiscrepancyKind.LOCAL_ONLY
    if local_state == aeat_state:
        return AeatSyncDiscrepancyKind.NONE
    return AeatSyncDiscrepancyKind.STATE_MISMATCH


def _validate_discrepancy(
    *,
    local_state: AeatSyncSourceState,
    aeat_state: AeatSyncSourceState,
    discrepancy_kind: AeatSyncDiscrepancyKind,
) -> None:
    expected = _expected_discrepancy(local_state=local_state, aeat_state=aeat_state)
    if discrepancy_kind is not expected:
        raise ValueError(
            "comparison discrepancy kind contradicts its independent local and AEAT source states",
        )


__all__ = [
    "AEAT_SYNC_WORKSPACE_CONTRACT_VERSION",
    "AeatSyncAeatObservationState",
    "AeatSyncCensusCategory",
    "AeatSyncCensusStatus",
    "AeatSyncDiscrepancyKind",
    "AeatSyncDocumentCustodyState",
    "AeatSyncJustificanteState",
    "AeatSyncLocalFilingState",
    "AeatSyncNotificationCategory",
    "AeatSyncNotificationReadState",
    "AeatSyncOverviewArea",
    "AeatSyncReconciliationState",
    "AeatSyncSourceState",
    "AeatSyncSupportedAction",
    "AeatSyncWorkspaceAvailability",
    "AeatSyncWorkspaceCensusRowV1",
    "AeatSyncWorkspaceEvidenceComparisonRowV1",
    "AeatSyncWorkspaceFiledDeclarationRowV1",
    "AeatSyncWorkspaceNotificationRowV1",
    "AeatSyncWorkspaceOverviewRowV1",
    "AeatSyncWorkspaceProjectionError",
    "AeatSyncWorkspaceProjectionV1",
    "AeatSyncWorkspaceReconciliationRowV1",
    "AeatSyncWorkspaceSource",
    "AeatSyncWorkspaceZone",
    "AeatSyncWorkspaceZoneObservationV1",
    "AeatSyncWorkspaceZoneStateV1",
    "project_aeat_sync_workspace",
]
