"""Safe immutable projection for the six-zone AEAT Sync workspace."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import (
    Annotated,
    Final,
    Generic,
    NotRequired,
    Self,
    TypeAliasType,
    TypedDict,
    TypeVar,
    Unpack,
    override,
)

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints, TypeAdapter, field_validator, model_validator

from ...core.errors.hierarchy import CadrumoError, pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.hex import HEX_PATTERN_64, Hex64Str
from ...core.identifier_grammar import NamespacedId
from ...core.identity.bucket import BucketId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.time.utc import UtcInstant, validate_utc_aware
from ...domain.modelos.codes import ModeloCode
from ..modelo.reconciliation_evidence_kind import ModeloReconciliationEvidenceKind
from ..modelo.reconciliation_records import ModeloReconciliationDiff
from ..operations.models import OperationDefinitionId
from ..operations.registry import OperationPublicContractSetV1
from ..operator_actions.catalogue import ActionCatalogue
from ..operator_actions.models import ActionReference
from ..user_profile.censal_observation import CensalObservation

AEAT_SYNC_WORKSPACE_CONTRACT_VERSION: Final[int] = 1

_NOTIFICATION_SELECTION_KEY: Final[bytes] = secrets.token_bytes(32)
_NOTIFICATION_SELECTION_PREFIX: Final[str] = "aeat_sync.notification."
_NOTIFICATION_SELECTION_DIGEST_LENGTH: Final[int] = 64
_NOTIFICATION_SELECTION_PATTERN: Final[str] = (
    rf"^{re.escape(_NOTIFICATION_SELECTION_PREFIX)}{HEX_PATTERN_64.removeprefix('^').removesuffix('$')}$"
)

# Keep a named runtime alias while Semgrep cannot parse this PEP 695 declaration.
AeatSyncNotificationSelectionKey = TypeAliasType(  # noqa: UP040
    "AeatSyncNotificationSelectionKey",
    Annotated[
        str,
        StringConstraints(
            min_length=len(_NOTIFICATION_SELECTION_PREFIX) + _NOTIFICATION_SELECTION_DIGEST_LENGTH,
            max_length=len(_NOTIFICATION_SELECTION_PREFIX) + _NOTIFICATION_SELECTION_DIGEST_LENGTH,
            pattern=_NOTIFICATION_SELECTION_PATTERN,
        ),
    ],
)
"""Opaque, bounded identity for one projected notification row.

The admission coordinate remains on :class:`AeatSyncWorkspaceFactV1` only.
Projection derives this key from that coordinate and reconstructs the public
row, so the public snapshot retains a stable semantic focus address without
retaining the private notification identity.
"""


class AeatSyncWorkspaceProjectionError(CadrumoError):
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
    INCOMPLETE = "incomplete"


class AeatSyncDiscrepancyKind(StrEnum):
    """Closed comparison outcomes."""

    NONE = "none"
    LOCAL_ONLY = "local_only"
    AEAT_ONLY = "aeat_only"
    STATE_MISMATCH = "state_mismatch"
    CONTRADICTORY_SOURCE = "contradictory_source"
    UNOBSERVED = "unobserved"
    INCOMPLETE = "incomplete"


class AeatSyncOverviewArea(StrEnum):
    """Closed overview areas."""

    CENSUS = "census"
    FILED_DECLARATIONS = "filed_declarations"
    NOTIFICATIONS = "notifications"
    EVIDENCE_COMPARISON = "evidence_comparison"
    RECONCILIATION = "reconciliation"


class AeatSyncCensusCategory(StrEnum):
    """The censo field families a census row is grouped under."""

    ADDRESS = "address"
    ACTIVITY = "activity"
    OBLIGATION = "obligation"
    CONTACT = "contact"
    OTHER = "other"


class AeatSyncCensusStatus(StrEnum):
    """The census comparison verdicts, plus the state of having none yet.

    The first four are VERDICTS: each claims someone compared the local censo
    field against the AEAT one and says how they came out. ``NOT_COMPARED``
    claims the opposite -- that nobody has looked at the AEAT side at all --
    and exists because before a pull there is no honest verdict to give. Made
    to reuse one of the four, a pre-pull row would have to assert a comparison
    that never happened; ``UNSET`` in particular says the field HAS no value,
    which is a statement about the value rather than about whether anyone
    checked.
    """

    ADOPTED = "adopted"
    CONFLICT = "conflict"
    UNCHANGED = "unchanged"
    UNSET = "unset"
    NOT_COMPARED = "not_compared"


COMPARED_CENSUS_STATUSES: Final = frozenset(
    {
        AeatSyncCensusStatus.ADOPTED,
        AeatSyncCensusStatus.CONFLICT,
        AeatSyncCensusStatus.UNCHANGED,
        AeatSyncCensusStatus.UNSET,
    }
)
"""The census statuses that assert a comparison against the AEAT actually ran."""


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
    """The notification families the AEAT distinguishes."""

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
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
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


class AeatSyncWorkspaceActionRowV1(BaseModel):
    """Public immutable capability provenance shared by every workspace row."""

    model_config = STRICT_FROZEN_CONFIG
    supported_actions: tuple[ActionReference, ...] = ()
    supported_operations: tuple[OperationDefinitionId, ...] = ()


class AeatSyncWorkspaceOverviewRowV1(AeatSyncWorkspaceActionRowV1):
    """One area's local-versus-AEAT standing, with the actions it admits."""

    area: AeatSyncOverviewArea
    local_state: AeatSyncSourceState
    aeat_state: AeatSyncSourceState
    local_observed_at: UtcInstant | None = None
    aeat_observed_at: UtcInstant | None = None
    discrepancy_kind: AeatSyncDiscrepancyKind

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _coherent(self) -> Self:
        _dual(self.local_state, self.local_observed_at, self.aeat_state, self.aeat_observed_at)
        _discrepancy(self.local_state, self.aeat_state, self.discrepancy_kind)
        return self


class AeatSyncWorkspaceCensusRowV1(AeatSyncWorkspaceActionRowV1):
    """One profile field compared with its stored AEAT census evidence."""

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
    @pydantic_validation_boundary
    def _the_status_and_the_values_must_agree(self) -> Self:
        """A verdict must carry what it judged; a non-verdict must not pretend to.

        Both directions are defects, and neither is caught by the other.

        Reporting a CONFLICT while withholding a side asks the operator to
        accept a difference they cannot see -- the same defect the invoice and
        entry suggestions carried before they showed the amounts they compared.
        UNSET and UNCHANGED stay deliberately unconstrained, as they were:
        both are meaningful before either side has been read, and requiring
        values there would force a producer to invent them.

        NOT_COMPARED asserts that nobody looked at the AEAT. A row carrying an
        AEAT value under that status is self-contradicting: someone plainly
        did look, and the operator would be told the field is unchecked while
        the evidence sits in the same row.
        """
        if self.status is AeatSyncCensusStatus.CONFLICT and (self.local_value is None or self.aeat_value is None):
            raise ValueError("a census conflict must carry both the local and the AEAT value")
        if self.status is AeatSyncCensusStatus.NOT_COMPARED and self.aeat_value is not None:
            raise ValueError("a census row that was never compared cannot carry an AEAT value")
        return self


class AeatSyncWorkspaceFiledDeclarationRowV1(AeatSyncWorkspaceActionRowV1):
    """One declaration this profile filed, against what the AEAT shows for it."""

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
    @pydantic_validation_boundary
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
    """One notification's metadata, and the coordinate that opens its document.

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

    @model_validator(mode="after")
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
    def _coherent(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("period and filing year disagree")
        _dual(self.local_state, self.local_observed_at, self.aeat_state, self.aeat_observed_at)
        _discrepancy(self.local_state, self.aeat_state, self.discrepancy_kind)
        _compared_values(self.discrepancy_kind, self.local_value, self.aeat_value)
        return self


class AeatSyncWorkspaceEvidenceComparisonRowV1(_DualRow):
    """One declaration figure as the local record holds it and as the AEAT shows it."""

    pass


class AeatSyncWorkspaceReconciliationRowV1(_DualRow):
    """One reconciliation item, its two sides and how it was resolved."""

    reconciliation_state: AeatSyncReconciliationState
    evidence_kind: ModeloReconciliationEvidenceKind | None = None
    diffs: tuple[ModeloReconciliationDiff, ...] = ()
    advisory_count: NonNegativeInt = 0
    comparison_id: Hex64Str | None = None
    calculation_revision_id: Hex64Str | None = None
    work_unit_id: Hex64Str | None = None
    evidence_id: Hex64Str | None = None
    historical: bool = False

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _reconciled(self) -> Self:
        no_action = self.reconciliation_state is AeatSyncReconciliationState.NO_ACTION
        if (self.discrepancy_kind is AeatSyncDiscrepancyKind.NONE) != no_action:
            raise ValueError("reconciliation state contradicts discrepancy")
        if no_action and self.supported_actions:
            raise ValueError("NO_ACTION cannot carry actions")
        return self

    @override
    def model_copy(self, *, update: Mapping[str, object] | None = None, deep: bool = False) -> Self:
        """Keep state/action closure intact across mutation-test copies."""
        if update is None:
            return super().model_copy(deep=deep)
        return type(self).model_validate({**self.model_dump(), **update})


RowT = TypeVar("RowT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class AeatSyncWorkspaceFactV1(Generic[RowT]):  # noqa: UP046 -- Semgrep cannot parse the PEP 695 form.
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
    census_observation: CensalObservation | None = None
    filed_declarations: tuple[AeatSyncWorkspaceFiledDeclarationRowV1, ...] = ()
    notifications: tuple[AeatSyncWorkspaceNotificationRowV1, ...] = ()
    evidence_comparison: tuple[AeatSyncWorkspaceEvidenceComparisonRowV1, ...] = ()
    reconciliation: tuple[AeatSyncWorkspaceReconciliationRowV1, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _six_zones(self) -> Self:
        if tuple(item.zone for item in self.zones) != tuple(AeatSyncWorkspaceZone):
            raise ValueError("zones must cover the closed catalogue")
        selection_keys = tuple(row.selection_key for row in self.notifications)
        if any(key is None for key in selection_keys):
            raise ValueError("projected notifications require selection keys")
        if len(selection_keys) != len(set(selection_keys)):
            raise ValueError("projected notification selection keys must be unique")
        return self


AEAT_SYNC_STATUS_CONTRACT_VERSION: Final[int] = 1


class AeatSyncStatusArea(StrEnum):
    """The areas the AEAT sync page brings and judges, in the order a run brings them.

    Borrador 100 comes last because it is brought by importing a downloaded PDF
    and is never part of a run over everything.
    """

    CENSUS = "census"
    IDENTITY_CHECKS = "identity_checks"
    NOTIFICATIONS = "notifications"
    IVA_WALLET = "iva_wallet"
    FILED_DECLARATIONS = "filed_declarations"
    BORRADOR_100 = "borrador_100"


class AeatSyncAreaState(StrEnum):
    """What a stored capture establishes about one area right now.

    The four stay distinct: an area never brought has no capture, a current one
    has a capture inside its horizon, a possibly stale one has a capture older
    than its horizon, and an unavailable one could not be read at all.
    """

    NEVER_BROUGHT = "never_brought"
    CURRENT = "current"
    POSSIBLY_STALE = "possibly_stale"
    UNAVAILABLE = "unavailable"


AEAT_SYNC_STALENESS_HORIZONS: Final[Mapping[AeatSyncStatusArea, timedelta | None]] = MappingProxyType(
    {
        AeatSyncStatusArea.CENSUS: timedelta(days=90),
        AeatSyncStatusArea.IDENTITY_CHECKS: timedelta(days=90),
        AeatSyncStatusArea.NOTIFICATIONS: timedelta(days=7),
        AeatSyncStatusArea.IVA_WALLET: timedelta(days=30),
        AeatSyncStatusArea.FILED_DECLARATIONS: timedelta(days=90),
        # An imported Borrador 100 PDF is a document the person chose to bring;
        # no ruling gives it an age after which it may be out of date.
        AeatSyncStatusArea.BORRADOR_100: None,
    }
)
"""How old a successful capture may be before its area is possibly stale.

An area is possibly stale once its last successful capture is STRICTLY older than
its horizon; a capture exactly at the horizon is still current. ``None`` means
no ruling gives the area an age limit, so it is never judged stale.
"""


class AeatSyncFiledPeriodCountsV1(BaseModel):
    """How the filed periods this profile holds compare with the stored AEAT register.

    The four counts partition every period either side knows: ``matched`` is
    filed locally and shown by the AEAT register, ``aeat_only`` is shown by the
    register with no local filing, ``local_only`` is filed locally and absent
    from the register capture, and ``differing`` is shown by the register with
    evidence that conflicts or raises a concern and so cannot be matched.
    """

    model_config = STRICT_FROZEN_CONFIG
    matched: NonNegativeInt
    aeat_only: NonNegativeInt
    local_only: NonNegativeInt
    differing: NonNegativeInt


class AeatSyncFiledMatch(StrEnum):
    """How one declaration the AEAT register shows stands against this profile's records."""

    MATCHED = "matched"
    AEAT_ONLY = "aeat_only"
    LOCAL_ONLY = "local_only"
    DIFFERING = "differing"


class AeatSyncFiledLocalRecord(StrEnum):
    """What this profile itself holds for one declaration.

    A draft is an open work unit with no filing record; marked filed is a local
    filing record. Neither says anything about the AEAT.
    """

    NONE = "none"
    DRAFT = "draft"
    MARKED_FILED = "marked_filed"


class AeatSyncFiledDifference(StrEnum):
    """What the stored captures establish as differing for one declaration.

    ``STATUS`` means the register shows the declaration inactive, of unknown
    state, or with conflicting submissions, so it cannot be matched.
    """

    STATUS = "status"


class AeatSyncFiledRowV1(BaseModel):
    """One declaration either side knows, with its three facts kept apart.

    The local record, what the AEAT register showed and whether a receipt was
    verified are separate: a matching record is never a confirmed receipt.
    """

    model_config = STRICT_FROZEN_CONFIG
    modelo: Annotated[str, StringConstraints(min_length=3, max_length=3, pattern=r"^[0-9]{3}$")]
    filing_year: FilingYear
    period: Annotated[str, StringConstraints(min_length=1, max_length=8)] | None
    """The registry period token, or nothing for an annual declaration."""
    match: AeatSyncFiledMatch
    local_record: AeatSyncFiledLocalRecord
    local_record_at: datetime | None = None
    """When the draft was last changed or the record was marked filed."""
    aeat_shown_at: datetime | None = None
    """When the register capture that showed the declaration was made."""
    receipt_confirmed: bool = False
    differences: tuple[AeatSyncFiledDifference, ...] = ()

    @field_validator("local_record_at", "aeat_shown_at")
    @classmethod
    @pydantic_validation_boundary
    def _instants_are_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else validate_utc_aware(value)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _coherent(self) -> Self:
        if (self.local_record is AeatSyncFiledLocalRecord.NONE) != (self.local_record_at is None):
            raise ValueError("only a held local record carries its date")
        shown = self.aeat_shown_at is not None
        self._validate_match_group(shown=shown)
        if (self.match is AeatSyncFiledMatch.DIFFERING) != bool(self.differences):
            raise ValueError("only a differing declaration names what differs")
        if self.receipt_confirmed and not shown:
            raise ValueError("a confirmed receipt requires an AEAT observation")
        if self.receipt_confirmed and self.match is AeatSyncFiledMatch.DIFFERING:
            raise ValueError("a differing declaration cannot carry a confirmed receipt")
        return self

    def _validate_match_group(self, *, shown: bool) -> None:
        """Check the match claim against the independently held records."""
        filed = self.local_record is AeatSyncFiledLocalRecord.MARKED_FILED
        expected = {
            AeatSyncFiledMatch.MATCHED: shown and filed,
            AeatSyncFiledMatch.AEAT_ONLY: shown and not filed,
            AeatSyncFiledMatch.LOCAL_ONLY: filed and not shown,
            AeatSyncFiledMatch.DIFFERING: shown,
        }[self.match]
        if not expected:
            raise ValueError("match group contradicts the local record and the AEAT observation")


class AeatSyncAreaStatusV1(BaseModel):
    """One area's state, last successful capture and last attempt."""

    model_config = STRICT_FROZEN_CONFIG
    area: AeatSyncStatusArea
    state: AeatSyncAreaState
    last_brought_at: datetime | None = None
    """The UTC instant of the last successful capture, or nothing when none is known."""
    stale_after_days: NonNegativeInt | None = None
    """The horizon in whole days, or nothing when the area is never judged stale."""
    last_attempt_at: datetime | None = None
    last_attempt_succeeded: bool | None = None
    """Only areas whose runs leave a sync-run record carry an attempt."""
    refusal: NamespacedId | None = None
    unread_notification_count: NonNegativeInt | None = None
    filed_periods: AeatSyncFiledPeriodCountsV1 | None = None
    filed_rows: tuple[AeatSyncFiledRowV1, ...] | None = None
    """Each declaration the counts count, served with them and only with them."""

    @field_validator("last_brought_at", "last_attempt_at")
    @classmethod
    @pydantic_validation_boundary
    def _instants_are_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else validate_utc_aware(value)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _coherent(self) -> Self:
        brought = self.state in {AeatSyncAreaState.CURRENT, AeatSyncAreaState.POSSIBLY_STALE}
        if brought != (self.last_brought_at is not None):
            raise ValueError("only a brought area carries its capture time")
        if (self.state is AeatSyncAreaState.UNAVAILABLE) != (self.refusal is not None):
            raise ValueError("only an unavailable area carries a refusal")
        if (self.last_attempt_at is None) != (self.last_attempt_succeeded is None):
            raise ValueError("an attempt carries both its time and its outcome")
        if self.state is AeatSyncAreaState.POSSIBLY_STALE and self.stale_after_days is None:
            raise ValueError("a possibly stale area requires its horizon")
        self._validate_counts(brought=brought)
        return self

    def _validate_counts(self, *, brought: bool) -> None:
        """Require counts to belong to a captured area of the matching kind."""
        if not brought and (self.unread_notification_count is not None or self.filed_periods is not None):
            raise ValueError("counts require a brought area")
        if self.unread_notification_count is not None and self.area is not AeatSyncStatusArea.NOTIFICATIONS:
            raise ValueError("only notifications carry an unread count")
        if self.filed_periods is not None and self.area is not AeatSyncStatusArea.FILED_DECLARATIONS:
            raise ValueError("only filed declarations carry period counts")
        self._validate_filed_counts()

    def _validate_filed_counts(self) -> None:
        """Require filed rows and their group sizes to travel together."""
        if (self.filed_rows is None) != (self.filed_periods is None):
            raise ValueError("filed rows are served with their counts")
        if self.filed_rows is not None and self.filed_periods is not None:
            groups = Counter(row.match for row in self.filed_rows)
            counts = self.filed_periods
            if (counts.matched, counts.aeat_only, counts.local_only, counts.differing) != (
                groups[AeatSyncFiledMatch.MATCHED],
                groups[AeatSyncFiledMatch.AEAT_ONLY],
                groups[AeatSyncFiledMatch.LOCAL_ONLY],
                groups[AeatSyncFiledMatch.DIFFERING],
            ):
                raise ValueError("filed period counts must be the rows' group sizes")


class AeatSyncStatusV1(BaseModel):
    """Per-area AEAT sync standing, read from stored captures only."""

    model_config = STRICT_FROZEN_CONFIG
    contract_version: int = AEAT_SYNC_STATUS_CONTRACT_VERSION
    observed_at: datetime
    areas: tuple[AeatSyncAreaStatusV1, ...]
    filed_declaration_years: tuple[FilingYear, ...]
    iva_wallet_years: tuple[FilingYear, ...]

    @field_validator("observed_at")
    @classmethod
    @pydantic_validation_boundary
    def _observed_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _every_area_once(self) -> Self:
        if tuple(item.area for item in self.areas) != tuple(AeatSyncStatusArea):
            raise ValueError("areas must cover the closed catalogue in order")
        return self


def aeat_sync_workspace_sources(zone: AeatSyncWorkspaceZone) -> tuple[AeatSyncWorkspaceSource, ...]:
    """Return the canonical independent sources required by one zone."""
    from . import _workspace_projection

    return _workspace_projection.aeat_sync_workspace_sources(zone)


_NOTIFICATION_SELECTION_NAMESPACE: Final[str] = "aeat_sync.notification.selection.v1"


def notification_selection_key(private_identity: str) -> AeatSyncNotificationSelectionKey:
    """Derive a process-stable public focus key without retaining private data."""
    canonical = "\x1f".join((_NOTIFICATION_SELECTION_NAMESPACE, private_identity)).encode("utf-8")
    digest = hmac.digest(_NOTIFICATION_SELECTION_KEY, canonical, hashlib.sha256).hex()
    return f"{_NOTIFICATION_SELECTION_PREFIX}{digest}"


def public_notification_row(
    row: AeatSyncWorkspaceNotificationRowV1,
    selection_key: AeatSyncNotificationSelectionKey,
) -> AeatSyncWorkspaceNotificationRowV1:
    """Rebuild one notification row and inject only its safe selection key."""
    values = row.model_dump(include=set(AeatSyncWorkspaceNotificationRowV1.model_fields))
    values["selection_key"] = selection_key
    return AeatSyncWorkspaceNotificationRowV1.model_validate(values)


def source_observation_is_observable(value: AeatSyncWorkspaceAvailability) -> bool:
    """Return whether a source has an observation that can support a claim."""
    return value in {AeatSyncWorkspaceAvailability.AVAILABLE, AeatSyncWorkspaceAvailability.STALE}


_observable = source_observation_is_observable


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
    elif AeatSyncSourceState.INCOMPLETE in {local, aeat}:
        expected = AeatSyncDiscrepancyKind.INCOMPLETE
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


class _AeatSyncWorkspaceProjectionArguments(TypedDict):
    bucket_id: BucketId
    subject_key: str
    zone_observations: tuple[AeatSyncWorkspaceZoneObservationV1, ...]
    action_catalogue: ActionCatalogue
    operation_contracts: OperationPublicContractSetV1
    overview: NotRequired[tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceOverviewRowV1], ...]]
    census: NotRequired[tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceCensusRowV1], ...]]
    census_observation: NotRequired[AeatSyncWorkspaceFactV1[CensalObservation] | None]
    filed_declarations: NotRequired[tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceFiledDeclarationRowV1], ...]]
    notifications: NotRequired[tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceNotificationRowV1], ...]]
    evidence_comparison: NotRequired[tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceEvidenceComparisonRowV1], ...]]
    reconciliation: NotRequired[tuple[AeatSyncWorkspaceFactV1[AeatSyncWorkspaceReconciliationRowV1], ...]]


def project_aeat_sync_workspace(
    **arguments: Unpack[_AeatSyncWorkspaceProjectionArguments],
) -> AeatSyncWorkspaceProjectionV1:
    """Project already-loaded, scoped facts through the single projection owner."""
    from ._workspace_projection import project_aeat_sync_workspace as project

    return project(**arguments)
