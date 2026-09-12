"""Canonical staged resolver ownership for the production modelo calculation route."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.binding_provider_registration import (
    BINDING_PROVIDER_REGISTRATIONS,
    RouteOwnership,
)
from ..aggregation.atribucion_member import AtribucionMemberSourceResolver
from ..aggregation.foreign_assets import ForeignAssetsAggregationSourceResolver
from ..aggregation.inventory import InventorySourceResolver
from ..aggregation.modelo_bindings import (
    LedgerImpatriadoIncomeAggregationSourceResolver,
    LedgerIrnrIncomeAggregationSourceResolver,
    LedgerIvaAggregationSourceResolver,
    LedgerRentaGastosPagoFraccionadoAggregationSourceResolver,
    LedgerRentaIncomeAggregationSourceResolver,
)
from ..aggregation.modelo_bindings_renta_expenses import LedgerRentaGastosEstimacionDirectaAggregationSourceResolver
from ..aggregation.modelo_bindings_retenciones import RetencionesAggregationSourceResolver
from ..aggregation.oss_ioss import OssIossLedgerSourceResolver
from ..aggregation.source_mesh import (
    ModeloSourceResolver,
)
from ..aggregation.source_profile import ProfileSourceResolver
from ..aggregation.withholding_source import WithholdingSourceResolver
from ..calculations.bienes_inversion_regularizacion import BienesInversionRegularizacionSourceResolver
from ..calculations.iva_compensation_annual_partition import IvaCompensationAnnualPartitionSourceResolver
from ..calculations.iva_wallet_reconciliation import IvaWalletDecisionSourceResolver
from ..calculations.m303_regimen_simplificado_annual_summary import M303RegimenSimplificadoAnnualSummarySourceResolver
from ..calculations.multi_year import PreviousFilingSourceResolver
from ..calculations.prorrata_regularizacion import ProrrataRegularizacionSourceResolver
from ..calculations.relation_prefill import RelationPrefillSourceResolver
from ..invoices.source_resolver import InvoiceCatalogueSourceResolver
from .borrador_binding import Modelo100BorradorSourceResolver

type CalculationRouteResolverStage = Literal["pre_mesh", "mesh", "conditional", "post_mesh"]
type CalculationRouteStage = CalculationRouteResolverStage | Literal["manual"]
MANUAL_INPUT_RESOLVER_ID = "manual_input"
DESIGN_CONSTANT_RESOLVER_ID = "design_constant"


@dataclass(frozen=True, slots=True)
class CalculationRouteResolverOwnership:
    """One class-owned resolver identity at its production route stage."""

    stage: CalculationRouteResolverStage
    resolver_type: type[ModeloSourceResolver]
    resolver_id: str
    owned_sources: tuple[BindingSourceKind, ...]


@dataclass(frozen=True, slots=True)
class CalculationRouteManualOwnership:
    """The sole manual-input pseudo-owner on the production route."""

    stage: Literal["manual"]
    resolver_type: Literal[None]
    resolver_id: Literal["manual_input"]
    owned_sources: tuple[Literal[BindingSourceKind.MANUAL_INPUT]]


@dataclass(frozen=True, slots=True)
class CalculationRouteDesignConstantOwnership:
    """The sole design-constant pseudo-owner on the production route.

    A SIBLING of the manual-input pseudo-owner rather than a widening of it, and
    the distinction is the point: manual input arrives from the operator, while a
    design constant is already carried on its own binding selector because AEAT's
    diseño fixes it. Folding the second into the first would have meant relaxing
    that row's ``Literal`` pins until they admitted a second member -- exactly the
    widen-the-matcher move the governing decision refuses. Declaring a new owner
    keeps every existing pin intact and makes the new route enumerable.

    Neither pseudo-owner names a resolver class: there is no aggregation to run,
    so there is nothing for a ``ModeloSourceResolver`` to do. Enrolment here is
    what keeps the kind out of the novel-source refusal, which exists so a source
    nobody routed cannot resolve to a silent blank.
    """

    stage: Literal["manual"]
    resolver_type: Literal[None]
    resolver_id: Literal["design_constant"]
    owned_sources: tuple[Literal[BindingSourceKind.DESIGN_CONSTANT]]


type CalculationRouteOwnership = (
    CalculationRouteResolverOwnership | CalculationRouteManualOwnership | CalculationRouteDesignConstantOwnership
)


def _resolver_ownership(
    stage: CalculationRouteStage,
    resolver_type: type[ModeloSourceResolver],
) -> CalculationRouteResolverOwnership:
    if stage == "manual":
        raise RuntimeError("manual input is not a class-owned resolver")
    return CalculationRouteResolverOwnership(
        stage=stage,
        resolver_type=resolver_type,
        resolver_id=resolver_type.resolver_id,
        owned_sources=resolver_type.owned_sources,
    )


_CANONICAL_RESOLVER_STAGES: tuple[tuple[CalculationRouteStage, type[ModeloSourceResolver]], ...] = (
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
    ("mesh", InventorySourceResolver),
    ("mesh", PreviousFilingSourceResolver),
    ("mesh", RelationPrefillSourceResolver),
    ("mesh", IvaCompensationAnnualPartitionSourceResolver),
    ("conditional", M303RegimenSimplificadoAnnualSummarySourceResolver),
    ("post_mesh", ProrrataRegularizacionSourceResolver),
    ("post_mesh", BienesInversionRegularizacionSourceResolver),
)
_MANUAL_INPUT_OWNER = CalculationRouteManualOwnership(
    stage="manual",
    resolver_type=None,
    resolver_id=MANUAL_INPUT_RESOLVER_ID,
    owned_sources=(BindingSourceKind.MANUAL_INPUT,),
)

_DESIGN_CONSTANT_OWNER = CalculationRouteDesignConstantOwnership(
    stage="manual",
    resolver_type=None,
    resolver_id=DESIGN_CONSTANT_RESOLVER_ID,
    owned_sources=(BindingSourceKind.DESIGN_CONSTANT,),
)

CALCULATION_ROUTE_RESOLVER_OWNERSHIP: tuple[CalculationRouteOwnership, ...] = (
    *(_resolver_ownership(stage, resolver_type) for stage, resolver_type in _CANONICAL_RESOLVER_STAGES),
    _MANUAL_INPUT_OWNER,
    _DESIGN_CONSTANT_OWNER,
)


def _canonical_stage_map() -> dict[type[ModeloSourceResolver], CalculationRouteResolverStage]:
    """Return the canonical executable-resolver stage map after checking its shape."""
    canonical_stages: dict[type[ModeloSourceResolver], CalculationRouteResolverStage] = {
        resolver_type: cast(CalculationRouteResolverStage, stage) for stage, resolver_type in _CANONICAL_RESOLVER_STAGES
    }
    if len(canonical_stages) != len(_CANONICAL_RESOLVER_STAGES):
        raise RuntimeError("canonical calculation route repeats a resolver type")
    return canonical_stages


def _require_unique_resolver_ids(ownership: tuple[CalculationRouteOwnership, ...]) -> None:
    resolver_ids = tuple(row.resolver_id for row in ownership)
    if len(set(resolver_ids)) != len(resolver_ids):
        raise RuntimeError("calculation route resolver ids must be unique")


def _require_complete_resolver_coverage(
    ownership: tuple[CalculationRouteOwnership, ...],
    canonical_stages: dict[type[ModeloSourceResolver], CalculationRouteResolverStage],
) -> None:
    declared_resolver_types = {
        row.resolver_type for row in ownership if isinstance(row, CalculationRouteResolverOwnership)
    }
    if declared_resolver_types != set(canonical_stages):
        raise RuntimeError("calculation route must contain every canonical executable resolver exactly once")


def _require_one_pseudo_owner(
    ownership: tuple[CalculationRouteOwnership, ...],
    owner_type: type[CalculationRouteManualOwnership] | type[CalculationRouteDesignConstantOwnership],
    message: str,
) -> None:
    if sum(isinstance(row, owner_type) for row in ownership) != 1:
        raise RuntimeError(message)


def _validate_route_shape(
    ownership: tuple[CalculationRouteOwnership, ...],
) -> dict[type[ModeloSourceResolver], CalculationRouteResolverStage]:
    """Validate route-wide uniqueness and complete owner coverage."""
    canonical_stages = _canonical_stage_map()
    _require_unique_resolver_ids(ownership)
    _require_complete_resolver_coverage(ownership, canonical_stages)
    _require_one_pseudo_owner(
        ownership,
        CalculationRouteManualOwnership,
        "calculation route must contain exactly one manual-input pseudo-owner",
    )
    _require_one_pseudo_owner(
        ownership,
        CalculationRouteDesignConstantOwnership,
        "calculation route must contain exactly one design-constant pseudo-owner",
    )
    return canonical_stages


def _validate_manual_owner(row: CalculationRouteManualOwnership) -> None:
    if row != _MANUAL_INPUT_OWNER:
        raise RuntimeError("calculation route permits only the canonical manual-input pseudo-owner")


def _validate_design_constant_owner(row: CalculationRouteDesignConstantOwnership) -> None:
    # Pinned to the one canonical instance for the same reason the manual owner
    # is: a pseudo-owner names no resolver class, so the drift checks below have
    # nothing to compare against and equality with the declared row is the
    # whole guard.
    if row != _DESIGN_CONSTANT_OWNER:
        raise RuntimeError("calculation route permits only the canonical design-constant pseudo-owner")


def _validate_resolver_owner(
    row: CalculationRouteResolverOwnership,
    canonical_stages: dict[type[ModeloSourceResolver], CalculationRouteResolverStage],
) -> None:
    expected_stage = canonical_stages.get(row.resolver_type)
    if expected_stage is None:
        raise RuntimeError(f"calculation route contains an invented resolver: {row.resolver_type!r}")
    identity_checks = (
        (
            row.stage,
            expected_stage,
            f"calculation route resolver {row.resolver_id!r} must use stage {expected_stage!r}",
        ),
        (
            row.resolver_id,
            row.resolver_type.resolver_id,
            f"calculation route resolver id drifted: {row.resolver_type.__name__}",
        ),
        (
            row.owned_sources,
            row.resolver_type.owned_sources,
            f"calculation route resolver sources drifted: {row.resolver_type.__name__}",
        ),
    )
    for actual, expected, message in identity_checks:
        if actual != expected:
            raise RuntimeError(message)


def _validate_owner(
    row: CalculationRouteOwnership,
    canonical_stages: dict[type[ModeloSourceResolver], CalculationRouteResolverStage],
) -> None:
    """Validate one executable or pseudo-owner against canonical authority."""
    if isinstance(row, CalculationRouteManualOwnership):
        _validate_manual_owner(row)
        return
    if isinstance(row, CalculationRouteDesignConstantOwnership):
        _validate_design_constant_owner(row)
        return
    _validate_resolver_owner(row, canonical_stages)


def _claim_owned_sources(row: CalculationRouteOwnership, source_owners: dict[BindingSourceKind, str]) -> None:
    if not row.owned_sources:
        raise RuntimeError(f"calculation route resolver {row.resolver_id!r} owns no source")
    for source_kind in row.owned_sources:
        prior = source_owners.get(source_kind)
        if prior is not None:
            raise RuntimeError(
                f"calculation route source {source_kind.value!r} has duplicate owners: {prior!r}, {row.resolver_id!r}",
            )
        source_owners[source_kind] = row.resolver_id


def validate_calculation_route_resolver_ownership(
    ownership: tuple[CalculationRouteOwnership, ...],
) -> None:
    """Refuse identity, stage, pseudo-owner, and source-disposition drift."""
    canonical_stages = _validate_route_shape(ownership)
    source_owners: dict[BindingSourceKind, str] = {}
    for row in ownership:
        _validate_owner(row, canonical_stages)
        _claim_owned_sources(row, source_owners)


validate_calculation_route_resolver_ownership(CALCULATION_ROUTE_RESOLVER_OWNERSHIP)

MESH_ONLY_SOURCES: frozenset[BindingSourceKind] = frozenset(
    {BindingSourceKind.BORRADOR, BindingSourceKind.IVA_WALLET_DECISION},
)
"""The two routed sources no registry row may declare.

They own a resolver but are absent from the binding provider union on purpose:
an AEAT borrador value and a wallet decision arrive at runtime, so "not a
registry binding source" is a type error rather than a hand-written refusal.
They are therefore the only sources the route may own without a registration.
"""


def _route_owner_by_source(
    ownership: tuple[CalculationRouteOwnership, ...],
) -> dict[BindingSourceKind, tuple[str, CalculationRouteStage]]:
    return {source_kind: (row.resolver_id, row.stage) for row in ownership for source_kind in row.owned_sources}


def _require_registered_route_agreement(
    routed: dict[BindingSourceKind, tuple[str, CalculationRouteStage]],
) -> None:
    for kind, registration in BINDING_PROVIDER_REGISTRATIONS.items():
        declared = routed.get(kind)
        if isinstance(registration.route, RouteOwnership):
            expected = (registration.route.resolver_id, registration.route.stage)
            if declared is None:
                raise RuntimeError(f"binding provider {kind.value!r} claims route owner {expected!r} but is unrouted")
            if declared != expected:
                raise RuntimeError(
                    f"binding provider {kind.value!r} declares route {expected!r} "
                    f"but the calculation route owns it at {declared!r}",
                )
            continue
        if declared is not None:
            raise RuntimeError(
                f"binding provider {kind.value!r} declares no runtime owner but the calculation "
                f"route owns it at {declared!r}",
            )


def _require_no_unregistered_route_sources(
    routed: dict[BindingSourceKind, tuple[str, CalculationRouteStage]],
) -> None:
    unregistered = frozenset(routed) - frozenset(BINDING_PROVIDER_REGISTRATIONS)
    if unregistered != MESH_ONLY_SOURCES:
        raise RuntimeError(
            "the calculation route may own exactly the mesh-only sources without a binding registration; "
            f"found {sorted(kind.value for kind in unregistered)}",
        )


def validate_calculation_route_against_binding_registrations(
    ownership: tuple[CalculationRouteOwnership, ...],
) -> frozenset[BindingSourceKind]:
    """Refuse any disagreement between the route table and the registration table.

    The binding registrations are the enrollment authority and carry each kind's
    resolver id and stage; the route table is where those resolvers actually
    live. Only this module sees both, because the domain registration table must
    not import application code, so the join is asserted here at import time and
    a drift in either direction -- a registration naming a route that does not
    exist, a deferred kind that turns out to be routed, or a routed source with
    no registration at all -- refuses before anything resolves.

    Returns the enrolled source set, so the published constant cannot be built
    from an unverified table.
    """
    routed = _route_owner_by_source(ownership)
    _require_registered_route_agreement(routed)
    _require_no_unregistered_route_sources(routed)
    return frozenset(routed)


CALCULATION_ROUTE_ENROLLED_SOURCES = validate_calculation_route_against_binding_registrations(
    CALCULATION_ROUTE_RESOLVER_OWNERSHIP,
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
    "DESIGN_CONSTANT_RESOLVER_ID",
    "MANUAL_INPUT_RESOLVER_ID",
    "MESH_ONLY_SOURCES",
    "CalculationRouteDesignConstantOwnership",
    "CalculationRouteManualOwnership",
    "CalculationRouteResolverOwnership",
    "CalculationRouteStage",
    "require_calculation_route_resolver",
    "validate_calculation_route_against_binding_registrations",
    "validate_calculation_route_resolver_ownership",
]
