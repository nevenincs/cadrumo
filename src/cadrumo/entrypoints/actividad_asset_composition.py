"""Compose worker-bound activity-asset history and retained authority reads.

The worker profile supplies the :class:`TransactionCatalogueRepository` used by register operations.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ..adapters.persistence.profile.actividad_asset import ActividadAssetHistoryRepository
from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ..application.actividad_asset.activity_asset_contracts import ActivityAssetOperationPorts
from ..application.modelo.activity_asset_claim_consumers import calculation_revisions_consuming_claim
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from .adapter_composition_ports import build_modelo_history_ports, build_pinned_profile_read_ports


def build_activity_asset_operation_ports(
    *, bucket_id: str, operation: PinnedAuthorityOperation
) -> ActivityAssetOperationPorts:
    """Bind both canonical history and profile reads to the worker profile."""
    history_ports = build_modelo_history_ports(bucket_id=bucket_id, operation=operation)

    def claim_consumers(claim_ids: Iterable[str]) -> Mapping[str, tuple[str, ...]]:
        revisions = history_ports.calculation_repository.load(operation=operation).revisions.values()
        work_units = history_ports.work_unit_repository.load()
        return {
            claim_id: tuple(
                revision.calculation_revision_id
                for revision in calculation_revisions_consuming_claim(
                    claim_id,
                    bucket_id=bucket_id,
                    revisions=revisions,
                    work_units=work_units,
                )
            )
            for claim_id in claim_ids
        }

    return ActivityAssetOperationPorts(
        history_repository=ActividadAssetHistoryRepository(bucket_id=bucket_id),
        ledger=TransactionCatalogueRepository(bucket_id=bucket_id),
        profile_path_values=build_pinned_profile_read_ports(bucket_id=bucket_id, operation=operation).path_values,
        claim_consumers=claim_consumers,
    )
