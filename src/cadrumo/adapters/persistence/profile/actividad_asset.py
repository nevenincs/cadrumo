"""Encrypted SQL repository for append-only IRPF activity-asset history."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from ....application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from ....core.logging import get_logger
from ....domain.renta.actividad_asset.claims import AmortizationClaim
from ....domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ..storage.secure_object_namespaces import PROFILE_ACTIVIDAD_ASSET_HISTORY_NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository
from ._secure_model_document import (
    ProfileBareModelSecurePersistence,
    resolve_profile_secure_object_repository,
)

_log = get_logger(__name__)

ACTIVIDAD_ASSET_HISTORY_FILENAME = "actividad-asset-history.secure-object"


class ActividadAssetHistoryPersistenceError(RuntimeError):
    """Raised when encrypted activity-asset history cannot be reopened safely."""


class ActividadAssetHistoryRepository:
    """Persist one complete immutable asset history through encrypted SQL."""

    def __init__(
        self,
        *,
        bucket_id: str | None = None,
        objects: SecureObjectRepository | None = None,
    ) -> None:
        """Bind the repository to an explicit or active profile secure-object store."""
        self._storage = ProfileBareModelSecurePersistence(
            objects=resolve_profile_secure_object_repository(objects=objects, bucket_id=bucket_id),
            definition=PROFILE_ACTIVIDAD_ASSET_HISTORY_NAMESPACE,
            model_type=ActivityAssetHistory,
            empty_document=ActivityAssetHistory,
        )

    @property
    def envelope_path(self) -> Path:
        """Return the logical secure-object path for user-facing storage diagnostics."""
        return self._storage.logical_path(ACTIVIDAD_ASSET_HISTORY_FILENAME)

    def load(self) -> ActivityAssetHistory:
        """Reopen all immutable revisions and claims, or the empty history when absent."""
        try:
            return self._storage.load()
        except (OSError, ValidationError) as exc:
            _log.debug(
                "activity asset history load failed",
                extra={
                    "namespace": self._storage.namespace,
                    "object_key": self._storage.object_key,
                    "error_type": type(exc).__name__,
                },
            )
        raise ActividadAssetHistoryPersistenceError(
            f"unable to load activity asset history: {self._storage.object_key}",
        ) from None

    def append_revision(self, revision: ActivityAssetRevision) -> ActivityAssetHistory:
        """Atomically append one immutable revision under the secure-object CAS guard."""
        return self._storage.mutate(lambda current: current.append_revision(revision))

    def record_claim(self, claim: AmortizationClaim) -> ActivityAssetHistoryClaimResult:
        """Atomically record, replay, or refuse one claim without plaintext fallback."""
        current = self.load()
        replay = current.record_claim(claim)
        if replay.reused_existing_claim:
            return replay

        mutation_result: list[ActivityAssetHistoryClaimResult] = []

        def _record(history: ActivityAssetHistory) -> ActivityAssetHistory:
            result = history.record_claim(claim)
            mutation_result[:] = [result]
            return result.history

        persisted = self._storage.mutate(_record)
        result = mutation_result[0]
        return ActivityAssetHistoryClaimResult(
            history=persisted,
            claim=result.claim,
            reused_existing_claim=result.reused_existing_claim,
        )


__all__ = ["ActividadAssetHistoryPersistenceError", "ActividadAssetHistoryRepository"]
