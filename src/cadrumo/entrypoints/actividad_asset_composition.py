"""Compose worker-bound activity-asset history and retained authority reads."""

from __future__ import annotations

from ..adapters.persistence.profile.actividad_asset import ActividadAssetHistoryRepository
from ..application.actividad_asset.activity_asset_contracts import ActivityAssetOperationPorts
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from .adapter_composition import build_pinned_profile_read_ports


def build_activity_asset_operation_ports(
    *, bucket_id: str, operation: PinnedAuthorityOperation
) -> ActivityAssetOperationPorts:
    """Bind both canonical history and profile reads to the worker profile."""
    return ActivityAssetOperationPorts(
        history_repository=ActividadAssetHistoryRepository(bucket_id=bucket_id),
        profile_path_values=build_pinned_profile_read_ports(bucket_id=bucket_id, operation=operation).path_values,
    )
