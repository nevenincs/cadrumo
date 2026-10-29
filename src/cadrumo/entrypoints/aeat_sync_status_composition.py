"""Bind the AEAT sync status read to one profile's encrypted stored captures."""

from __future__ import annotations

import asyncio
from functools import cache
from typing import TYPE_CHECKING
from uuid import UUID

from ..application.aeat_sync.status_operation import AeatSyncStatusPorts

if TYPE_CHECKING:
    from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
    from ..core.config import Settings
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation


def compose_aeat_sync_status_ports(
    settings: Settings, bucket_id: str, operation: PinnedAuthorityOperation
) -> AeatSyncStatusPorts:
    """Bind one reader per stored capture to the exact profile, opening each store only when read."""
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.live.borrador_100 import Borrador100SnapshotService
    from ..application.live.notifications import NotificationsService
    from ..application.live.snapshot_base import SnapshotLifecycleState
    from ..application.live.verify import VerifyService
    from ..application.user_profile.profile_record_repository import ProfileRecordRepository
    from ..application.user_profile.projections import record_to_path_values
    from ..application.workbench_generation_calendar import declared_tax_id
    from ..core.sync_surface import SyncSurface
    from .adapter_composition_ports import build_borrador_100_snapshot_repository
    from .calendar_evidence_composition import compose_calendar_aeat_reader
    from .censal_readback_composition import read_stored_censal_observation
    from .live_state_composition import compose_notifications_ports
    from .operation_composition_inputs import verify_persistence

    @cache
    def objects() -> SecureObjectRepository:
        return secure_object_repository_for_bucket(bucket_id)

    def profile_tax_id() -> str | None:
        record = ProfileRecordRepository.for_current_session(
            bucket_id, profile_decode_context=operation.profile_decode_context()
        ).load(bucket_id)
        return declared_tax_id(record_to_path_values(record))

    def filed_attempt():
        from ..adapters.persistence.profile.sync_runs import SyncRunRecordRepository
        from ..application.aeat_sync.workspace_reader import AeatSyncAreaAttempt

        runs = [
            record
            for record in SyncRunRecordRepository(objects=objects()).iter_records()
            if record.surface is SyncSurface.FILED_DECLARATIONS
        ]
        latest = max(runs, key=lambda record: record.completed_at, default=None)
        return None if latest is None else AeatSyncAreaAttempt(latest.completed_at, latest.succeeded)

    def iva_wallet_captured_at():
        # The page brings this area with the Modelo 303 history capture, which
        # stores filed 303 observations and no wallet observation, so both
        # stores date the area.
        from ..adapters.outbound.aeat.sede.observation_store import (
            FiledDeclaracionObservationRepository,
            IvaCompensationWalletObservationRepository,
        )
        from ..core.modelo import Modelo

        wallet = (
            observation.captured_at
            for observation in IvaCompensationWalletObservationRepository(objects=objects()).iter_records()
        )
        history = (
            artefact.captured_at
            for observation in FiledDeclaracionObservationRepository(objects=objects()).iter_records()
            if observation.modelo == Modelo("303").value
            for artefact in observation.artefacts
        )
        return max((*wallet, *history), default=None)

    def filings():
        return tuple(ModeloRecordCatalogueRepository(bucket_id=bucket_id).load_revisioned()[0].records.values())

    def latest_notifications():
        return NotificationsService(ports=compose_notifications_ports(settings=settings)).latest(bucket_id=bucket_id)

    def borrador_snapshots():
        repository = build_borrador_100_snapshot_repository(bucket_id=bucket_id)
        return Borrador100SnapshotService(bucket_id=bucket_id, repository=repository).list_snapshots(
            state=SnapshotLifecycleState.ACTIVE, operation=operation
        )

    def verify_observations(nif: str):
        service = VerifyService(persistence=verify_persistence(settings, bucket_id))
        return service.list_observations(bucket_id=bucket_id, nif=nif)

    return AeatSyncStatusPorts(
        profile_tax_id=profile_tax_id,
        filings=filings,
        census_observation=lambda: asyncio.run(read_stored_censal_observation(UUID(bucket_id))),
        calendar_aeat_reader=compose_calendar_aeat_reader(operation),
        filed_attempt=filed_attempt,
        latest_notifications=latest_notifications,
        iva_wallet_captured_at=iva_wallet_captured_at,
        borrador_snapshots=borrador_snapshots,
        verify_observations=verify_observations,
    )


__all__ = ["compose_aeat_sync_status_ports"]
