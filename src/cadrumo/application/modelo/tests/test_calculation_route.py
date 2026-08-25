"""Canonical production calculation-route ownership gates."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ....core import BindingSourceKind, ModeloCalculationRouteId
from ...aggregation import AggregationValidationError, BindingSourceDisposition
from ...calculations import M303RegimenSimplificadoAnnualSummarySourceResolver
from .. import (
    CALCULATION_ROUTE_ENROLLED_SOURCES,
    CALCULATION_ROUTE_ID,
    CALCULATION_ROUTE_RESOLVER_OWNERSHIP,
    CALCULATION_ROUTE_SOURCE_DISPOSITIONS,
    MANUAL_INPUT_RESOLVER_ID,
    CalculationRouteManualOwnership,
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
    assert CALCULATION_ROUTE_ID is ModeloCalculationRouteId.MODELO_WORK_CALCULATION
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
        CalculationRouteManualOwnership(
            stage="manual",
            resolver_type=None,
            resolver_id=MANUAL_INPUT_RESOLVER_ID,
            owned_sources=(BindingSourceKind.MANUAL_INPUT,),
        ),
    )


def test_route_refuses_duplicate_ids_duplicate_sources_omission_and_invented_owner() -> None:
    first, second, *remaining = CALCULATION_ROUTE_RESOLVER_OWNERSHIP
    assert isinstance(first, CalculationRouteResolverOwnership)
    assert isinstance(second, CalculationRouteResolverOwnership)
    with pytest.raises(RuntimeError, match="resolver ids must be unique"):
        validate_calculation_route_resolver_ownership(
            (first, replace(second, resolver_id=first.resolver_id), *remaining),
        )
    with pytest.raises(RuntimeError, match="resolver sources drifted"):
        validate_calculation_route_resolver_ownership(
            (first, replace(second, owned_sources=first.owned_sources), *remaining),
        )
    with pytest.raises(AggregationValidationError):
        validate_calculation_route_resolver_ownership(CALCULATION_ROUTE_RESOLVER_OWNERSHIP[:-1])
    invented = CalculationRouteManualOwnership(
        stage="manual",
        resolver_type=None,
        resolver_id=MANUAL_INPUT_RESOLVER_ID,
        owned_sources=(BindingSourceKind.MANUAL_INPUT,),
    )
    object.__setattr__(invented, "resolver_id", "invented-deferred-owner")
    object.__setattr__(invented, "owned_sources", (BindingSourceKind.RELATED_PARTY_OPERATION,))
    with pytest.raises(RuntimeError, match="only the canonical manual-input pseudo-owner"):
        validate_calculation_route_resolver_ownership((*CALCULATION_ROUTE_RESOLVER_OWNERSHIP, invented))


def test_route_refuses_resolver_class_identity_mutations() -> None:
    profile, *remaining = CALCULATION_ROUTE_RESOLVER_OWNERSHIP
    assert isinstance(profile, CalculationRouteResolverOwnership)
    with pytest.raises(RuntimeError, match="resolver id drifted"):
        validate_calculation_route_resolver_ownership(
            (replace(profile, resolver_id="renamed-profile"), *remaining),
        )
    with pytest.raises(RuntimeError, match="resolver sources drifted"):
        validate_calculation_route_resolver_ownership(
            (replace(profile, owned_sources=(BindingSourceKind.RELATED_PARTY_OPERATION,)), *remaining),
        )
    invented = replace(profile)
    object.__setattr__(invented, "resolver_type", None)
    with pytest.raises(RuntimeError, match="contains an invented resolver"):
        validate_calculation_route_resolver_ownership(
            (invented, *remaining),
        )


def test_route_refuses_additional_or_typed_manual_pseudo_owners() -> None:
    manual = CALCULATION_ROUTE_RESOLVER_OWNERSHIP[-1]
    assert isinstance(manual, CalculationRouteManualOwnership)
    invented_pseudo_owner = replace(manual)
    object.__setattr__(invented_pseudo_owner, "resolver_id", "second-manual-owner")
    with pytest.raises(RuntimeError, match="only the canonical manual-input pseudo-owner"):
        validate_calculation_route_resolver_ownership(
            (*CALCULATION_ROUTE_RESOLVER_OWNERSHIP, invented_pseudo_owner),
        )
    with pytest.raises(RuntimeError, match="resolver ids must be unique"):
        validate_calculation_route_resolver_ownership((*CALCULATION_ROUTE_RESOLVER_OWNERSHIP, manual))

    profile = CALCULATION_ROUTE_RESOLVER_OWNERSHIP[0]
    assert isinstance(profile, CalculationRouteResolverOwnership)
    typed_manual_owner = replace(manual)
    object.__setattr__(typed_manual_owner, "resolver_type", profile.resolver_type)
    with pytest.raises(RuntimeError, match="only the canonical manual-input pseudo-owner"):
        validate_calculation_route_resolver_ownership(
            (
                *CALCULATION_ROUTE_RESOLVER_OWNERSHIP[:-1],
                typed_manual_owner,
            ),
        )


@pytest.mark.parametrize(
    ("index", "wrong_stage"),
    tuple(
        (index, next(stage for stage in ("pre_mesh", "mesh", "conditional", "post_mesh") if stage != row.stage))
        for index, row in enumerate(CALCULATION_ROUTE_RESOLVER_OWNERSHIP)
        if row.resolver_type is not None
    ),
)
def test_route_refuses_each_resolver_moved_from_its_canonical_stage(index: int, wrong_stage: str) -> None:
    mutated = list(CALCULATION_ROUTE_RESOLVER_OWNERSHIP)
    mutated[index] = replace(mutated[index], stage=wrong_stage)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="must use stage"):
        validate_calculation_route_resolver_ownership(tuple(mutated))
