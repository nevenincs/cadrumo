"""Sole production composition seam for the supervised operation platform."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta

from ..adapters.persistence.operations import (
    OperationJournalRepository,
    OperationLeaseFilesystemRepository,
    operation_secure_reference_repository,
)
from ..adapters.persistence.profile import SyncRunRecordRepository
from ..application.auth import build_auth_operation_definitions, build_auth_operation_registrations
from ..application.live import (
    build_filed_history_operation_definition,
    build_filed_history_operation_registration,
)
from ..application.operations import (
    OperationCancellationService,
    OperationDetachService,
    OperationObservationService,
    OperationRegistry,
    OperationResponseControlService,
    OperationReviewProjectionService,
    OperationSecureResponseAuthority,
    OperationSupervisor,
    OperationWorkspaceRefreshTargetService,
)
from ..application.user_profile import (
    CENSAL_OPERATION_DEFINITION,
    build_censal_operation_registration,
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from ..core.config import Settings, load_settings
from ..core.paths import effective_storage_root
from ..core.time import now

_LEASE_DURATION = timedelta(minutes=10)
_EXECUTION_TIMEOUT = timedelta(hours=1)
_CLEANUP_TIMEOUT = timedelta(minutes=2)


@dataclass(frozen=True, slots=True)
class OperationProductionDependencies:
    """One reusable production graph shared by every inbound frontend."""

    registry: OperationRegistry
    supervisor: OperationSupervisor
    observation: OperationObservationService
    review: OperationReviewProjectionService
    refresh: OperationWorkspaceRefreshTargetService
    cancellation: OperationCancellationService
    detach: OperationDetachService

    async def shutdown(self) -> None:
        """Settle supervisor-owned tasks and resources before process exit."""
        await self.supervisor.shutdown()

    def response(self, authority: OperationSecureResponseAuthority) -> OperationResponseControlService:
        """Bind response inspection to a separately held runtime authority."""
        return OperationResponseControlService(
            reader=self.observation.reader,
            registry=self.registry,
            authority=authority,
        )


def compose_operation_dependencies(
    *,
    settings: Settings | None = None,
) -> OperationProductionDependencies:
    """Compose the immutable production registry and all public services.

    Construction is deliberately explicit and effect-light: it opens no
    browser and starts no operation. Profile-bound repositories resolve only
    when an operation uses them, so the same graph can own pre-login and
    post-login execution without retaining a stale profile repository.
    """
    resolved_settings = settings or load_settings()
    storage_root = effective_storage_root(settings=resolved_settings)
    auth_definitions = build_auth_operation_definitions()
    profile_definitions = build_user_profile_operation_definitions()
    filed_history_definition = build_filed_history_operation_definition(
        sync_run_repository_factory=SyncRunRecordRepository
    )
    definitions = tuple(
        sorted(
            (*auth_definitions, *profile_definitions, CENSAL_OPERATION_DEFINITION, filed_history_definition),
            key=lambda item: item.definition_id,
        )
    )
    registrations = tuple(
        sorted(
            (
                *build_auth_operation_registrations(auth_definitions),
                *build_user_profile_operation_registrations(profile_definitions),
                build_censal_operation_registration(CENSAL_OPERATION_DEFINITION),
                build_filed_history_operation_registration(filed_history_definition),
            ),
            key=lambda item: item.contract.definition_id,
        )
    )
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    journal = OperationJournalRepository(storage_root=storage_root)
    leases = OperationLeaseFilesystemRepository(storage_root=storage_root)
    operands = operation_secure_reference_repository()
    supervisor = OperationSupervisor(
        registry=registry,
        journal=journal,
        event_stream=journal,
        leases=leases,
        operands=operands,
        owner_id=secrets.token_hex(32),
        lease_token_factory=lambda: secrets.token_hex(32),
        clock=now,
        lease_duration=_LEASE_DURATION,
        execution_timeout=_EXECUTION_TIMEOUT,
        cleanup_timeout=_CLEANUP_TIMEOUT,
    )
    return OperationProductionDependencies(
        registry=registry,
        supervisor=supervisor,
        observation=OperationObservationService(reader=journal, registry=registry),
        review=OperationReviewProjectionService(reader=journal, registry=registry, operands=operands, clock=now),
        refresh=OperationWorkspaceRefreshTargetService(reader=journal, registry=registry),
        cancellation=OperationCancellationService(reader=journal, registry=registry, supervisor=supervisor),
        detach=OperationDetachService(reader=journal, registry=registry, supervisor=supervisor),
    )


__all__ = ["OperationProductionDependencies", "compose_operation_dependencies"]
