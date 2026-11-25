"""Registered no-effect read of the signed-in profile's operation history.

`operations.history.list` lists the runs the operation journal holds for one
exact profile, newest first and a page at a time. A row is a public projection:
the run's identity, its lifecycle state and effect as the journal recorded them
(``UNKNOWN`` and ``SETTLING`` stay what they are), and the terminal receipt
summary once the run settled. No request payload, result, secret, diagnostic or
review material is read into a row.

The journal is shared by every profile of the installation. A run belongs to
this profile only when its encrypted admission record, held in this profile's
own custody, names this profile and the same invocation. A record that cannot
be read, or that names this profile without being provable, is counted and
reported with the page, so a damaged journal never reads as an empty history.
The read itself is ephemeral and never enters the journal, so listing the
history adds no run to it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...core.time.utc import validate_utc_aware
from ..operations.access_resolution import (
    LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_replayed_period_independent_access,
)
from ..operations.capabilities import EPHEMERAL_CREDENTIAL_FREE_READ_CAPABILITIES
from ..operations.events import OperationEventCode
from ..operations.models import (
    CredentialFreeOperationRequest,
    OperationDefinitionId,
    OperationFailureErrorCode,
    OperationId,
    OperationReference,
    OperationRequest,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.operation_pages import operation_destination
from ..operations.owner import OperationExecutorContext
from ..operations.persistence.journal import (
    OperationPersistedSnapshot,
    OperationRecoveryInventoryDelta,
    OperationRecoveryInventoryDisposition,
)
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.provenance import OperationAdmissionProvenance
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..persistence_errors import PersistenceDegradationError
from ..user_profile.access_errors import ProfileAccessRefusedError

OPERATIONS_HISTORY_LIST_DEFINITION_ID: Final = "operations.history.list"

OPERATIONS_HISTORY_PAGE_SIZE_DEFAULT: Final = 25
OPERATIONS_HISTORY_PAGE_SIZE_MAX: Final = 100


class OperationHistoryCursorV1(BaseModel):
    """The position after one listed run, in the newest-first order of ``started_at`` then identity."""

    model_config = STRICT_FROZEN_CONFIG

    started_at: datetime
    operation_id: OperationId

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _utc(self) -> Self:
        validate_utc_aware(self.started_at)
        return self


class OperationHistoryListRequest(CredentialFreeOperationRequest):
    """List one page of the profile's runs, newest first, after an optional cursor."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    limit: Annotated[int, Field(ge=1, le=OPERATIONS_HISTORY_PAGE_SIZE_MAX)] = OPERATIONS_HISTORY_PAGE_SIZE_DEFAULT
    after: OperationHistoryCursorV1 | None = None


class OperationHistoryReceiptV1(BaseModel):
    """The terminal receipt of a settled run, without its result or diagnostic references."""

    model_config = STRICT_FROZEN_CONFIG

    condition: OperationTerminalCondition
    effect: OperationEffect
    settled_at: datetime
    result_stored: bool
    refusal_ref: OperationReference | None
    failure_error_code: OperationFailureErrorCode | None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _utc(self) -> Self:
        validate_utc_aware(self.settled_at)
        return self


class OperationHistoryRowV1(BaseModel):
    """One run of the profile as the journal recorded it."""

    model_config = STRICT_FROZEN_CONFIG

    operation_id: OperationId
    definition_id: OperationDefinitionId
    register_page: str | None
    started_at: datetime
    updated_at: datetime
    lifecycle: OperationLifecycle
    effect: OperationEffect
    phase_code: OperationEventCode | None
    cancellation_requested: bool
    receipt: OperationHistoryReceiptV1 | None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _consistent(self) -> Self:
        validate_utc_aware(self.started_at)
        validate_utc_aware(self.updated_at)
        if self.updated_at < self.started_at:
            raise ValueError("a run cannot update before it starts")
        if (self.lifecycle is OperationLifecycle.TERMINAL) != (self.receipt is not None):
            raise ValueError("exactly a terminal run carries a receipt")
        if self.receipt is not None and self.receipt.effect is not self.effect:
            raise ValueError("a run's effect is its receipt's effect")
        return self

    @property
    def cursor(self) -> OperationHistoryCursorV1:
        """The position of this run in the listing order."""
        return OperationHistoryCursorV1(started_at=self.started_at, operation_id=self.operation_id)


class OperationHistoryResultV1(BaseModel):
    """One page of the profile's runs and what the scan could not account for."""

    model_config = STRICT_FROZEN_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    observed_at: datetime
    runs: tuple[OperationHistoryRowV1, ...]
    run_count: NonNegativeInt
    next_cursor: OperationHistoryCursorV1 | None
    unreadable_records: NonNegativeInt
    unverifiable_records: NonNegativeInt

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _page(self) -> Self:
        validate_utc_aware(self.observed_at)
        keys = [(row.started_at, row.operation_id) for row in self.runs]
        if keys != sorted(set(keys), reverse=True):
            raise ValueError("history rows are unique and listed newest first")
        if len(self.runs) > self.run_count:
            raise ValueError("a page cannot hold more runs than the profile has")
        if self.next_cursor is not None and (not self.runs or self.next_cursor != self.runs[-1].cursor):
            raise ValueError("the continuation cursor names the last listed run")
        return self


@dataclass(frozen=True, slots=True)
class OperationHistoryPorts:
    """Readers over the shared journal and this profile's own admission custody.

    ``inventory`` and ``load`` refuse with :class:`PersistenceDegradationError`
    when the journal or one record cannot be read. ``admission`` answers
    ``None`` when this profile's custody holds no such record, and refuses the
    same way when it holds one it cannot read.
    """

    bucket_id: str
    inventory: Callable[[], Awaitable[OperationRecoveryInventoryDelta]]
    load: Callable[[OperationId], Awaitable[OperationPersistedSnapshot]]
    admission: Callable[[ContentDigest], Awaitable[OperationAdmissionProvenance | None]]


type OperationHistoryPortsFactory = Callable[[str], OperationHistoryPorts]
"""Bind the readers to one exact profile bucket."""


class _Attribution(StrEnum):
    """Whose run a journal record is, as far as this profile's custody can prove."""

    OWN = "own"
    OTHER = "other"
    UNVERIFIABLE = "unverifiable"


def _names_another_profile(subject_ref: str, own_subject: str) -> bool:
    return subject_ref != own_subject and subject_ref.startswith(profile_operation_subject(""))


async def _attribute(
    ports: OperationHistoryPorts, snapshot: OperationPersistedSnapshot, *, profile_id: UUID
) -> _Attribution:
    """Decide whose run ``snapshot`` is from this profile's own admission record.

    A record whose admission this custody does not hold belongs to another
    profile, unless its own subject names this profile: that record claims to
    be ours and cannot be proven, so it is reported, not dropped.
    """
    identity = snapshot.identity
    own_subject = profile_operation_subject(str(profile_id))
    claims_another = _names_another_profile(identity.subject_ref, own_subject)
    reference = snapshot.admission_provenance_reference
    if reference is None:
        return _Attribution.OTHER if claims_another else _Attribution.UNVERIFIABLE
    try:
        provenance = await ports.admission(reference)
    except PersistenceDegradationError:
        return _Attribution.UNVERIFIABLE
    if provenance is None:
        return _Attribution.UNVERIFIABLE if identity.subject_ref == own_subject else _Attribution.OTHER
    if provenance.identity != identity or provenance.profile_binding.profile_id != profile_id:
        return _Attribution.UNVERIFIABLE
    return _Attribution.OWN


def _row(snapshot: OperationPersistedSnapshot) -> OperationHistoryRowV1:
    """Project one journal snapshot onto its public row, reading no request, result or diagnostic."""
    receipt = snapshot.terminal_receipt
    return OperationHistoryRowV1(
        operation_id=snapshot.operation_id,
        definition_id=snapshot.identity.definition_id,
        register_page=operation_destination(snapshot.identity.definition_id),
        started_at=snapshot.started_at,
        updated_at=snapshot.updated_at,
        lifecycle=snapshot.lifecycle,
        effect=snapshot.effect,
        phase_code=snapshot.phase_code,
        cancellation_requested=snapshot.cancellation_requested_at is not None,
        receipt=None
        if receipt is None
        else OperationHistoryReceiptV1(
            condition=receipt.condition,
            effect=receipt.effect,
            settled_at=receipt.settled_at,
            result_stored=receipt.result_ref is not None,
            refusal_ref=receipt.refusal_ref,
            failure_error_code=receipt.failure_error_code,
        ),
    )


async def read_operation_history(
    ports: OperationHistoryPorts,
    *,
    profile_id: UUID,
    limit: int,
    after: OperationHistoryCursorV1 | None,
    observed_at: datetime,
) -> OperationHistoryResultV1:
    """Scan the journal once and page the runs this profile's custody proves are its own.

    Pages are not a snapshot of one instant: each read scans the journal again,
    and the order never moves because it follows the immutable start time.
    """
    if ports.bucket_id != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    inventory = await ports.inventory()
    unreadable = 0
    unverifiable = 0
    own: list[OperationHistoryRowV1] = []
    for entry in inventory.entries:
        if entry.disposition is OperationRecoveryInventoryDisposition.REFUSED:
            unreadable += 1
            continue
        try:
            snapshot = await ports.load(entry.operation_id)
        except PersistenceDegradationError:
            unreadable += 1
            continue
        attribution = await _attribute(ports, snapshot, profile_id=profile_id)
        if attribution is _Attribution.OWN:
            own.append(_row(snapshot))
        elif attribution is _Attribution.UNVERIFIABLE:
            unverifiable += 1
    own.sort(key=lambda row: (row.started_at, row.operation_id), reverse=True)
    later = (
        own
        if after is None
        else [row for row in own if (row.started_at, row.operation_id) < (after.started_at, after.operation_id)]
    )
    page = tuple(later[:limit])
    return OperationHistoryResultV1(
        profile_id=profile_id,
        observed_at=observed_at,
        runs=page,
        run_count=len(own),
        next_cursor=page[-1].cursor if len(later) > limit else None,
        unreadable_records=unreadable,
        unverifiable_records=unverifiable,
    )


class OperationHistoryListExecutor:
    """Read the history inside the exact profile worker, journaling nothing."""

    def __init__(self, factory: OperationHistoryPortsFactory) -> None:
        """Retain only composition's profile-bound reader factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[OperationHistoryListRequest], context: OperationExecutorContext
    ) -> str:
        """Store the page as one no-effect result."""
        payload = request.payload
        if request.definition_id != OPERATIONS_HISTORY_LIST_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(OPERATIONS_HISTORY_LIST_DEFINITION_ID)
        ports = self._factory(str(payload.profile_id))

        async def capture() -> str:
            result = await read_operation_history(
                ports, profile_id=payload.profile_id, limit=payload.limit, after=payload.after, observed_at=now()
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="operations-history-list")


def build_operation_history_list_definition(factory: OperationHistoryPortsFactory) -> OperationDefinition:
    """Declare the no-effect, exact-profile history read."""
    return build_single_phase_definition(
        definition_id=OPERATIONS_HISTORY_LIST_DEFINITION_ID,
        request_type=OperationHistoryListRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=OperationHistoryResultV1,
        executor_type=OperationHistoryListExecutor,
        build=lambda: OperationHistoryListExecutor(factory),
        capabilities=EPHEMERAL_CREDENTIAL_FREE_READ_CAPABILITIES,
    )


def resolve_operation_history_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Admit the signed-in profile's own period-independent read of its history."""
    require_access_request_profile_payload(
        request,
        definition_id=OPERATIONS_HISTORY_LIST_DEFINITION_ID,
        payload_type=OperationHistoryListRequest,
        access_profile_id=context.profile_id,
    )
    return bind_replayed_period_independent_access(
        context,
        LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
        definition_id=OPERATIONS_HISTORY_LIST_DEFINITION_ID,
    )


def build_operation_history_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the request and result schemas to the profile-bound read access."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=OperationHistoryResultV1,
        access_resolver=resolve_operation_history_access,
    )


__all__ = [
    "OPERATIONS_HISTORY_LIST_DEFINITION_ID",
    "OPERATIONS_HISTORY_PAGE_SIZE_DEFAULT",
    "OPERATIONS_HISTORY_PAGE_SIZE_MAX",
    "OperationHistoryCursorV1",
    "OperationHistoryListExecutor",
    "OperationHistoryListRequest",
    "OperationHistoryPorts",
    "OperationHistoryPortsFactory",
    "OperationHistoryReceiptV1",
    "OperationHistoryResultV1",
    "OperationHistoryRowV1",
    "build_operation_history_list_definition",
    "build_operation_history_list_registration",
    "read_operation_history",
    "resolve_operation_history_access",
]
