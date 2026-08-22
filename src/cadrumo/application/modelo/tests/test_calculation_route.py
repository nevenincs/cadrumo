"""Canonical production calculation-route ownership gates."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ....core import BindingSourceKind
from ...aggregation import AggregationValidationError, BindingSourceDisposition
from ...calculations import M303RegimenSimplificadoAnnualSummarySourceResolver
from .. import (
    CALCULATION_ROUTE_ENROLLED_SOURCES,
    CALCULATION_ROUTE_RESOLVER_OWNERSHIP,
    CALCULATION_ROUTE_SOURCE_DISPOSITIONS,
    CalculationRouteResolverOwnership,
    validate_calculation_route_resolver_ownership,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_production_route_is_the_total_unique_source_disposition_authority() -> None:
    assert set(CALCULATION_ROUTE_SOURCE_DISPOSITIONS) == set(BindingSourceKind)
    declared_sources = tuple(
        source for ownership in CALCULATION_ROUTE_RESOLVER_OWNERSHIP for source in ownership.owned_sources
    )
    assert len(declared_sources) == len(set(declared_sources))
    assert frozenset(declared_sources) == CALCULATION_ROUTE_ENROLLED_SOURCES
    assert {
        source
        for source, disposition in CALCULATION_ROUTE_SOURCE_DISPOSITIONS.items()
        if disposition is BindingSourceDisposition.ENROLLED
    } == set(declared_sources)
    assert all(
        source not in declared_sources
        for source, disposition in CALCULATION_ROUTE_SOURCE_DISPOSITIONS.items()
        if disposition in {BindingSourceDisposition.DEFERRED, BindingSourceDisposition.RESERVED}
    )


def test_route_reads_class_level_identity_and_declares_every_stage_and_manual_owner() -> None:
    class_owned = tuple(row for row in CALCULATION_ROUTE_RESOLVER_OWNERSHIP if row.resolver_type is not None)
    assert all(row.resolver_id == row.resolver_type.resolver_id for row in class_owned)
    assert all(row.owned_sources == row.resolver_type.owned_sources for row in class_owned)
    assert {row.stage for row in CALCULATION_ROUTE_RESOLVER_OWNERSHIP} == {
        "pre_mesh",
        "mesh",
        "conditional",
        "post_mesh",
        "manual",
    }
    conditional = tuple(row for row in class_owned if row.stage == "conditional")
    assert tuple(row.resolver_type for row in conditional) == (M303RegimenSimplificadoAnnualSummarySourceResolver,)
    manual = tuple(row for row in CALCULATION_ROUTE_RESOLVER_OWNERSHIP if row.stage == "manual")
    assert manual == (
        CalculationRouteResolverOwnership(
            stage="manual",
            resolver_type=None,
            resolver_id="manual_input",
            owned_sources=(BindingSourceKind.MANUAL_INPUT,),
        ),
    )


def test_route_refuses_duplicate_ids_duplicate_sources_omission_and_invented_owner() -> None:
    first, second, *remaining = CALCULATION_ROUTE_RESOLVER_OWNERSHIP
    with pytest.raises(RuntimeError, match="resolver ids must be unique"):
        validate_calculation_route_resolver_ownership(
            (first, replace(second, resolver_id=first.resolver_id), *remaining),
        )
    with pytest.raises(RuntimeError, match="duplicate owners"):
        validate_calculation_route_resolver_ownership(
            (first, replace(second, owned_sources=first.owned_sources), *remaining),
        )
    with pytest.raises(AggregationValidationError):
        validate_calculation_route_resolver_ownership(CALCULATION_ROUTE_RESOLVER_OWNERSHIP[:-1])
    invented = CalculationRouteResolverOwnership(
        stage="manual",
        resolver_type=None,
        resolver_id="invented-deferred-owner",
        owned_sources=(BindingSourceKind.RELATED_PARTY_OPERATION,),
    )
    with pytest.raises(AggregationValidationError):
        validate_calculation_route_resolver_ownership((*CALCULATION_ROUTE_RESOLVER_OWNERSHIP, invented))
