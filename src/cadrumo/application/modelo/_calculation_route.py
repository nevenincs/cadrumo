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
MANUAL_INPUT_RESOLVER_ID = "manual_input"


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


_CANONICAL_RESOLVER_STAGES: tuple[tuple[CalculationRouteStage, type[_ResolverClass]], ...] = (
    ("pre_mesh", ProfileSourceResolver),
    ("pre_mesh", Modelo100BorradorSourceResolver),
    ("pre_mesh", IvaWalletDecisionSourceResolver),
    ("mesh", LedgerIvaAggregationSourceResolver),
    ("mesh", LedgerRentaGastosEstimacionDirectaAggregationSourceResolver),
    ("mesh", LedgerRentaIncomeAggregationSourceResolver),
    ("mesh", LedgerRentaGastosPagoFraccionadoAggregationSourceResolver),
    ("mesh", LedgerImpatriadoIncomeAggregationSourceResolver),
    ("mesh", LedgerIrnrIncomeAggregationSourceResolver),
    ("mesh", OssIossLedgerSourceResolver),
    ("mesh", RetencionesAggregationSourceResolver),
    ("mesh", WithholdingSourceResolver),
    ("mesh", InvoiceCatalogueSourceResolver),
    ("mesh", ForeignAssetsAggregationSourceResolver),
    ("mesh", AtribucionMemberSourceResolver),
    ("mesh", PreviousFilingSourceResolver),
    ("mesh", RelationPrefillSourceResolver),
    ("mesh", IvaCompensationAnnualPartitionSourceResolver),
    ("conditional", M303RegimenSimplificadoAnnualSummarySourceResolver),
    ("post_mesh", ProrrataRegularizacionSourceResolver),
    ("post_mesh", BienesInversionRegularizacionSourceResolver),
)
_MANUAL_INPUT_OWNER = CalculationRouteResolverOwnership(
    stage="manual",
    resolver_type=None,
    resolver_id=MANUAL_INPUT_RESOLVER_ID,
    owned_sources=(BindingSourceKind.MANUAL_INPUT,),
)

CALCULATION_ROUTE_RESOLVER_OWNERSHIP: tuple[CalculationRouteResolverOwnership, ...] = (
    *(_resolver_ownership(stage, resolver_type) for stage, resolver_type in _CANONICAL_RESOLVER_STAGES),
    _MANUAL_INPUT_OWNER,
)


def validate_calculation_route_resolver_ownership(
    ownership: tuple[CalculationRouteResolverOwnership, ...],
) -> None:
    """Refuse identity, stage, pseudo-owner, and source-disposition drift."""
    canonical_stages = {resolver_type: stage for stage, resolver_type in _CANONICAL_RESOLVER_STAGES}
    if len(canonical_stages) != len(_CANONICAL_RESOLVER_STAGES):
        raise RuntimeError("canonical calculation route repeats a resolver type")
    resolver_ids = tuple(row.resolver_id for row in ownership)
    if len(set(resolver_ids)) != len(resolver_ids):
        raise RuntimeError("calculation route resolver ids must be unique")
    source_owners: dict[BindingSourceKind, str] = {}
    for row in ownership:
        if row.resolver_type is None:
            if row != _MANUAL_INPUT_OWNER:
                raise RuntimeError("calculation route permits only the canonical manual-input pseudo-owner")
        else:
            expected_stage = canonical_stages.get(row.resolver_type)
            if expected_stage is None:
                raise RuntimeError(f"calculation route contains an invented resolver: {row.resolver_type!r}")
            if row.stage != expected_stage:
                raise RuntimeError(
                    f"calculation route resolver {row.resolver_id!r} must use stage {expected_stage!r}",
                )
            if row.resolver_id != row.resolver_type.resolver_id:
                raise RuntimeError(f"calculation route resolver id drifted: {row.resolver_type.__name__}")
            if row.owned_sources != row.resolver_type.owned_sources:
                raise RuntimeError(f"calculation route resolver sources drifted: {row.resolver_type.__name__}")
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
    "MANUAL_INPUT_RESOLVER_ID",
    "CalculationRouteResolverOwnership",
    "CalculationRouteStage",
    "require_calculation_route_resolver",
    "validate_calculation_route_resolver_ownership",
]
