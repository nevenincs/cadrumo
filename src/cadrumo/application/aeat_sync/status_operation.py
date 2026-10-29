"""Registered local read of the per-area AEAT sync standing.

`live.sync.status` answers, for census, filed declarations, notifications, the
IVA wallet, Borrador 100 and identity checks, whether the profile never brought
the area, holds a capture still inside its horizon, holds one that may be out of
date, or could not be read. It reads stored captures only: it contacts no AEAT
service and writes nothing, and it composes only the stores each area needs.

The profile's own tax number is resolved here, in the worker, from the profile
record. No frontend supplies it, and it never reaches the result.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final
from uuid import UUID

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.bucket_pointer import require_active_bucket_id
from ...core.identity.bucket import BucketId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ..live.live_operation_execution import (
    publish_live_read_report,
    require_exact_profile_worker,
    require_live_executor_identity,
)
from ..live.live_operation_registration import (
    build_live_operation_definition,
    resolve_whole_profile_read_access,
)
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from ..workbench_generation_calendar import project_calendar_aeat_filing_evidence
from .workspace import AeatSyncStatusArea, AeatSyncStatusV1
from .workspace_reader import (
    AeatSyncAreaAttempt,
    AeatSyncNotificationsCapture,
    AeatSyncStatusSources,
    read_aeat_sync_status,
)

if TYPE_CHECKING:
    from ...core.filing_year import FilingYear
    from ...core.identifier_grammar import NamespacedId
    from ...core.time.utc import UtcInstant
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.modelos.filing_record import ModeloRecord
    from ..live.borrador_100 import Borrador100Snapshot
    from ..live.notifications import PersistedNotificationsSnapshot
    from ..live.verify import VerifyObservation
    from ..overview.evidence import AeatCalendarEvidenceSources, CalendarEvidenceReadOutcome
    from ..user_profile.censal_observation import CensalObservation

LIVE_SYNC_STATUS_DEFINITION_ID: Final = "live.sync.status"
_PHASES: Final = ("sync-status.read", "sync-status.result")

_STORE_UNREADABLE: Final[NamespacedId] = "aeat_sync.status.store_unreadable"
_TAX_ID_MISSING: Final[NamespacedId] = "aeat_sync.status.profile_tax_id_missing"
"""The profile declares no tax number, so evidence cannot be scoped to it."""

_STORE_READ_FAILURES: Final = (LookupError, OSError, ValueError)
"""Failures that mean one store could not be read, as opposed to an access refusal."""


class AeatSyncStatusRequest(CredentialFreeOperationRequest):
    """Read the per-area sync standing of one exact profile."""

    profile_id: UUID


class AeatSyncStatusResultV1(BaseModel):
    """The per-area sync standing, bound to the profile it was read for."""

    model_config = STRICT_FROZEN_CONFIG
    bucket_id: BucketId
    status: AeatSyncStatusV1


@dataclass(frozen=True, slots=True)
class AeatSyncStatusPorts:
    """Lazy readers over the exact profile's stored captures, one per store.

    Each reader opens only its own store, so a store one area needs is not
    opened for another, and one unreadable store refuses only its areas.
    """

    profile_tax_id: Callable[[], str | None]
    filings: Callable[[], tuple[ModeloRecord, ...]]
    census_observation: Callable[[], CensalObservation | None]
    calendar_aeat_reader: Callable[[], CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources]]
    filed_attempt: Callable[[], AeatSyncAreaAttempt | None]
    latest_notifications: Callable[[], PersistedNotificationsSnapshot | None]
    iva_wallet_captured_at: Callable[[], UtcInstant | None]
    borrador_snapshots: Callable[[], tuple[Borrador100Snapshot, ...]]
    verify_observations: Callable[[str], tuple[VerifyObservation, ...]]


AeatSyncStatusPortsFactory = Callable[[str, "PinnedAuthorityOperation"], AeatSyncStatusPorts]
"""Bind the readers to one exact profile bucket and the operation's pinned authority."""


def _require_bucket(bucket_id: str, *stored: str) -> None:
    """Refuse a stored capture that belongs to another profile."""
    if any(owner != bucket_id for owner in stored):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def load_aeat_sync_status(
    ports: AeatSyncStatusPorts,
    *,
    bucket_id: str,
    observed_at: UtcInstant,
    operation: PinnedAuthorityOperation,
) -> AeatSyncStatusResultV1:
    """Read each store once and judge every area, naming the areas a store failed to serve."""
    unreadable: dict[AeatSyncStatusArea, NamespacedId] = {}

    def guarded[T](areas: tuple[AeatSyncStatusArea, ...], read: Callable[[], T], fallback: T) -> T:
        try:
            return read()
        except ProfileAccessRefusedError:
            raise
        except _STORE_READ_FAILURES:
            unreadable.update(dict.fromkeys(areas, _STORE_UNREADABLE))
            return fallback

    tax_areas = (AeatSyncStatusArea.FILED_DECLARATIONS, AeatSyncStatusArea.IDENTITY_CHECKS)
    tax_id = guarded(tax_areas, ports.profile_tax_id, None)
    if tax_id is None:
        unreadable.setdefault(AeatSyncStatusArea.FILED_DECLARATIONS, _TAX_ID_MISSING)
        unreadable.setdefault(AeatSyncStatusArea.IDENTITY_CHECKS, _TAX_ID_MISSING)

    filed_areas = (AeatSyncStatusArea.FILED_DECLARATIONS,)
    census = guarded((AeatSyncStatusArea.CENSUS,), ports.census_observation, None)
    filings = guarded(filed_areas, ports.filings, ())
    evidence = (
        None
        if AeatSyncStatusArea.FILED_DECLARATIONS in unreadable
        else guarded(
            filed_areas,
            lambda: project_calendar_aeat_filing_evidence(ports.calendar_aeat_reader(), expected_tax_id=tax_id),
            None,
        )
    )
    notifications = guarded((AeatSyncStatusArea.NOTIFICATIONS,), ports.latest_notifications, None)
    if notifications is not None:
        _require_bucket(bucket_id, notifications.bucket_id)
    borrador = guarded((AeatSyncStatusArea.BORRADOR_100,), ports.borrador_snapshots, ())
    _require_bucket(bucket_id, *(snapshot.bucket_id for snapshot in borrador))
    identity = (
        ()
        if tax_id is None
        else guarded((AeatSyncStatusArea.IDENTITY_CHECKS,), lambda: ports.verify_observations(tax_id), ())
    )
    _require_bucket(bucket_id, *(observation.bucket_id for observation in identity))

    sources = AeatSyncStatusSources(
        census_observation=census,
        filings=filings,
        filed_evidence=evidence,
        filed_attempt=guarded(filed_areas, ports.filed_attempt, None),
        notifications=(
            None
            if notifications is None
            else AeatSyncNotificationsCapture(
                captured_at=notifications.captured_at,
                unread_count=sum(1 for row in notifications.rows if row.leida is False),
            )
        ),
        iva_wallet_captured_at=guarded((AeatSyncStatusArea.IVA_WALLET,), ports.iva_wallet_captured_at, None),
        borrador_imported_at=max((snapshot.captured_at for snapshot in borrador), default=None),
        identity_checked_at=max((observation.checked_at for observation in identity), default=None),
        unreadable=unreadable,
    )
    years: tuple[FilingYear, ...] = tuple(sorted(operation.supported_filing_years().years))
    return AeatSyncStatusResultV1(
        bucket_id=bucket_id,
        status=read_aeat_sync_status(
            observed_at=observed_at,
            sources=sources,
            filed_declaration_years=years,
            iva_wallet_years=years,
        ),
    )


class AeatSyncStatusExecutor:
    """Judge the sync areas in the authenticated profile worker, contacting nothing."""

    def __init__(self, ports_factory: AeatSyncStatusPortsFactory) -> None:
        """Retain the entrypoint-composed store readers."""
        self._ports_factory = ports_factory

    async def execute(self, request: OperationRequest[AeatSyncStatusRequest], context: OperationExecutorContext) -> str:
        """Store the status read as one no-effect report."""
        bucket_id = require_exact_profile_worker(
            request.payload.profile_id, request.subject_ref, active_bucket_id=require_active_bucket_id()
        )
        require_live_executor_identity(request, context, definition_id=LIVE_SYNC_STATUS_DEFINITION_ID)
        await context.events.phase(_PHASES[0])
        operation = context.authority_operation

        def read() -> AeatSyncStatusResultV1:
            return load_aeat_sync_status(
                self._ports_factory(bucket_id, operation),
                bucket_id=bucket_id,
                observed_at=now(),
                operation=operation,
            )

        result = await asyncio.to_thread(read)
        return await publish_live_read_report(
            context,
            result,
            result_phase=_PHASES[1],
            effect=OperationEffect.NONE,
            task_name="sync-status-result",
        )


def build_aeat_sync_status_definition(ports_factory: AeatSyncStatusPortsFactory) -> OperationDefinition:
    """Declare the no-effect, no-network exact-profile status read."""
    return build_live_operation_definition(
        definition_id=LIVE_SYNC_STATUS_DEFINITION_ID,
        request_type=AeatSyncStatusRequest,
        result_type=AeatSyncStatusResultV1,
        executor_type=AeatSyncStatusExecutor,
        build=lambda: AeatSyncStatusExecutor(ports_factory),
        phase_codes=_PHASES,
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )


def resolve_aeat_sync_status_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact-profile whole-profile read access for the stored captures."""
    return resolve_whole_profile_read_access(
        request,
        context,
        definition_id=LIVE_SYNC_STATUS_DEFINITION_ID,
        payload_type=AeatSyncStatusRequest,
    )


def build_aeat_sync_status_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the request and result schemas to whole-profile read access."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=AeatSyncStatusResultV1,
        access_resolver=resolve_aeat_sync_status_access,
    )


__all__ = [
    "LIVE_SYNC_STATUS_DEFINITION_ID",
    "AeatSyncStatusExecutor",
    "AeatSyncStatusPorts",
    "AeatSyncStatusPortsFactory",
    "AeatSyncStatusRequest",
    "AeatSyncStatusResultV1",
    "build_aeat_sync_status_definition",
    "build_aeat_sync_status_registration",
    "load_aeat_sync_status",
    "resolve_aeat_sync_status_access",
]
