"""Canonical staged resolver ownership for the production modelo calculation route."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Protocol

from ...core import BindingSourceKind
from ..aggregation import (
    AtribucionMemberSourceResolver,
    BindingSourceDisposition,
    ForeignAssetsAggregationSourceResolver,
    LedgerImpatriadoIncomeAggregationSourceResolver,
    LedgerIrnrIncomeAggregationSourceResolver,
    LedgerIvaAggregationSourceResolver,
    LedgerRentaGastosEstimacionDirectaAggregationSourceResolver,
    LedgerRentaGastosPagoFraccionadoAggregationSourceResolver,
    LedgerRentaIncomeAggregationSourceResolver,
    OssIossLedgerSourceResolver,
    ProfileSourceResolver,
    RetencionesAggregationSourceResolver,
    WithholdingSourceResolver,
    build_binding_source_dispositions,
)
from ..calculations import (
    BienesInversionRegularizacionSourceResolver,
    IvaCompensationAnnualPartitionSourceResolver,
    IvaWalletDecisionSourceResolver,
    M303RegimenSimplificadoAnnualSummarySourceResolver,
    PreviousFilingSourceResolver,
    ProrrataRegularizacionSourceResolver,
    RelationPrefillSourceResolver,
)
from ..invoices import InvoiceCatalogueSourceResolver
from ._borrador_binding import Modelo100BorradorSourceResolver

type CalculationRouteStage = Literal["pre_mesh", "mesh", "conditional", "post_mesh", "manual"]


class _ResolverClass(Protocol):
    resolver_id: str
    owned_sources: tuple[BindingSourceKind, ...]


@dataclass(frozen=True, slots=True)
class CalculationRouteResolverOwnership:
    """One class-owned resolver identity at its production route stage."""

    stage: CalculationRouteStage
    resolver_type: type[_ResolverClass] | None
    resolver_id: str
    owned_sources: tuple[BindingSourceKind, ...]


def _resolver_ownership(
    stage: CalculationRouteStage,
    resolver_type: type[_ResolverClass],
) -> CalculationRouteResolverOwnership:
    return CalculationRouteResolverOwnership(
        stage=stage,
        resolver_type=resolver_type,
        resolver_id=resolver_type.resolver_id,
        owned_sources=resolver_type.owned_sources,
    )


CALCULATION_ROUTE_RESOLVER_OWNERSHIP: tuple[CalculationRouteResolverOwnership, ...] = (
    _resolver_ownership("pre_mesh", ProfileSourceResolver),
    _resolver_ownership("pre_mesh", Modelo100BorradorSourceResolver),
    _resolver_ownership("pre_mesh", IvaWalletDecisionSourceResolver),
    _resolver_ownership("mesh", LedgerIvaAggregationSourceResolver),
    _resolver_ownership("mesh", LedgerRentaGastosEstimacionDirectaAggregationSourceResolver),
    _resolver_ownership("mesh", LedgerRentaIncomeAggregationSourceResolver),
    _resolver_ownership("mesh", LedgerRentaGastosPagoFraccionadoAggregationSourceResolver),
    _resolver_ownership("mesh", LedgerImpatriadoIncomeAggregationSourceResolver),
    _resolver_ownership("mesh", LedgerIrnrIncomeAggregationSourceResolver),
    _resolver_ownership("mesh", OssIossLedgerSourceResolver),
    _resolver_ownership("mesh", RetencionesAggregationSourceResolver),
    _resolver_ownership("mesh", WithholdingSourceResolver),
    _resolver_ownership("mesh", InvoiceCatalogueSourceResolver),
    _resolver_ownership("mesh", ForeignAssetsAggregationSourceResolver),
    _resolver_ownership("mesh", AtribucionMemberSourceResolver),
    _resolver_ownership("mesh", PreviousFilingSourceResolver),
    _resolver_ownership("mesh", RelationPrefillSourceResolver),
    _resolver_ownership("mesh", IvaCompensationAnnualPartitionSourceResolver),
    _resolver_ownership("conditional", M303RegimenSimplificadoAnnualSummarySourceResolver),
    _resolver_ownership("post_mesh", ProrrataRegularizacionSourceResolver),
    _resolver_ownership("post_mesh", BienesInversionRegularizacionSourceResolver),
    CalculationRouteResolverOwnership(
        stage="manual",
        resolver_type=None,
        resolver_id="manual_input",
        owned_sources=(BindingSourceKind.MANUAL_INPUT,),
    ),
)


def validate_calculation_route_resolver_ownership(
    ownership: tuple[CalculationRouteResolverOwnership, ...],
) -> None:
    """Refuse duplicate, missing, or disposition-inventing route ownership."""
    resolver_ids = tuple(row.resolver_id for row in ownership)
    if len(set(resolver_ids)) != len(resolver_ids):
        raise RuntimeError("calculation route resolver ids must be unique")
    source_owners: dict[BindingSourceKind, str] = {}
    for row in ownership:
        if not row.owned_sources:
            raise RuntimeError(f"calculation route resolver {row.resolver_id!r} owns no source")
        for source_kind in row.owned_sources:
            prior = source_owners.get(source_kind)
            if prior is not None:
                raise RuntimeError(
                    f"calculation route source {source_kind.value!r} has duplicate owners: "
                    f"{prior!r}, {row.resolver_id!r}",
                )
            source_owners[source_kind] = row.resolver_id
    dispositions = build_binding_source_dispositions(frozenset(source_owners))
    for source_kind, disposition in dispositions.items():
        has_owner = source_kind in source_owners
        if (disposition is BindingSourceDisposition.ENROLLED) != has_owner:
            raise RuntimeError(f"calculation route disposition disagrees with ownership: {source_kind.value}")


validate_calculation_route_resolver_ownership(CALCULATION_ROUTE_RESOLVER_OWNERSHIP)

CALCULATION_ROUTE_SOURCE_DISPOSITIONS = MappingProxyType(
    dict(
        build_binding_source_dispositions(
            frozenset(source for row in CALCULATION_ROUTE_RESOLVER_OWNERSHIP for source in row.owned_sources),
        ),
    ),
)
CALCULATION_ROUTE_ENROLLED_SOURCES = frozenset(
    source
    for source, disposition in CALCULATION_ROUTE_SOURCE_DISPOSITIONS.items()
    if disposition is BindingSourceDisposition.ENROLLED
)
CALCULATION_ROUTE_PRE_MESH_SOURCES = frozenset(
    source for row in CALCULATION_ROUTE_RESOLVER_OWNERSHIP if row.stage == "pre_mesh" for source in row.owned_sources
)


def require_calculation_route_resolver(stage: CalculationRouteStage, resolver: object) -> None:
    """Refuse a runtime resolver absent from its canonical production stage."""
    matching = tuple(
        row
        for row in CALCULATION_ROUTE_RESOLVER_OWNERSHIP
        if row.stage == stage and row.resolver_type is type(resolver)
    )
    if len(matching) != 1:
        raise RuntimeError(f"runtime calculation resolver is not declared at {stage}: {type(resolver).__name__}")
    declaration = matching[0]
    if (
        getattr(resolver, "resolver_id", None) != declaration.resolver_id
        or getattr(resolver, "owned_sources", None) != declaration.owned_sources
    ):
        raise RuntimeError(f"runtime calculation resolver identity drifted: {declaration.resolver_id}")


__all__ = [
    "CALCULATION_ROUTE_ENROLLED_SOURCES",
    "CALCULATION_ROUTE_PRE_MESH_SOURCES",
    "CALCULATION_ROUTE_RESOLVER_OWNERSHIP",
    "CALCULATION_ROUTE_SOURCE_DISPOSITIONS",
    "CalculationRouteResolverOwnership",
    "CalculationRouteStage",
    "require_calculation_route_resolver",
    "validate_calculation_route_resolver_ownership",
]
