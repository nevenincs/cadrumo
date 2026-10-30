"""What the asset register yields now for the coordinates of a sealed revision.

The comparison runs through the same source owners a draft's verification reads, so a
filed revision and a draft cannot disagree about what the register says.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_sources import ActivityAssetConsumption
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ..aggregation.ledger_filing_snapshot import FiledRegisterReader
from ..aggregation.ledger_membership import LedgerMembershipPorts, query_ledger_membership
from ..aggregation.modelo_bindings import (
    LedgerRentaGastosPagoFraccionadoAggregationSourceResolver,
    LedgerRentaIncomeAggregationSourceResolver,
)
from ..aggregation.modelo_bindings_renta_expenses import LedgerRentaGastosEstimacionDirectaAggregationSourceResolver
from .profile_readiness_gate import load_modelo_work_profile
from .work_profile import ModeloWorkProfile

_REGISTER_SOURCES = frozenset(
    {
        *LedgerRentaGastosEstimacionDirectaAggregationSourceResolver.owned_sources,
        *LedgerRentaGastosPagoFraccionadoAggregationSourceResolver.owned_sources,
        *LedgerRentaIncomeAggregationSourceResolver.owned_sources,
    },
)
"""The source families that read the asset register; no other Modelo can drift against it."""


def filed_register_reader(
    *,
    bucket_id: str,
    work_units: WorkUnitCatalogue,
    ports: LedgerMembershipPorts,
    operation: PinnedAuthorityOperation,
) -> FiledRegisterReader:
    """Bind the register comparison to one profile, its work units and one authority pin.

    A revision outside this bucket or reading no register source answers with what it
    recorded, so it shows no drift here.  A profile, registry revision or source that
    cannot be read answers ``None``.

    Returns:
        A read-only reader of the register's current view of one revision.
    """
    profiles: list[ModeloWorkProfile | None] = []

    def read(target: CalculationRevision) -> ActivityAssetConsumption | None:
        recorded = target.activity_asset_consumption
        work_unit = work_units.get(target.work_unit_id)
        if work_unit is None or work_unit.bucket_id != bucket_id:
            return recorded
        try:
            revision = operation.revision(work_unit.modelo, work_unit.revision_id)
            if not {binding.source for binding in revision.bindings} & _REGISTER_SOURCES:
                return recorded
            if not ports.activity_asset_history_repository.load().revisions and recorded.is_empty:
                return recorded
            if not profiles:
                profiles.append(
                    load_modelo_work_profile(
                        bucket_id=bucket_id,
                        profile_decode_context=operation.profile_decode_context(),
                    ),
                )
        except (CadrumoError, LookupError):
            return None
        profile = profiles[0]
        if profile is None:
            return None
        membership = query_ledger_membership(
            target=target,
            work_unit=work_unit,
            revision=revision,
            profile=profile,
            ports=ports,
            operation=operation,
        )
        return membership.activity_asset_consumption if membership.available else None

    return read


__all__ = ["filed_register_reader"]
