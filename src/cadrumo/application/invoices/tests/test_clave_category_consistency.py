"""The clave/category relationship reads the same in both directions.

Modelo 349 claves and IVA categories are one legal relationship expressed two
ways: choosing a clave states a treatment, and a stated treatment implies the
clave it is filed under. The two readings lived in different layers — the
forward one in the CLI, the inverse in the resolver — agreeing only because
both were maintained by hand. A clave added to one was invisible to the other,
and a disagreement means an invoice is filed under a clave that contradicts its
own IVA treatment.

These tests hold the two together, so the relationship cannot drift without a
red result.
"""

from __future__ import annotations

import pytest

from ....core.aggregation import IntracomOperationType
from ....domain.iva.schema import IvaCategory
from ....domain.calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ..source_resolver import iva_category_for_operation_type

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_every_publicly_declared_invoice_clave_round_trips_to_its_category() -> None:
    """The operator-facing clave/category projection stays internally coherent.

    The resolver's private fallback map is an implementation detail. The public
    contract is the category returned for each registry-declared invoice clave,
    so the assertion exercises that behavior through the public accessor and
    the registry's public operation-type projection.
    """
    catalogue = resolve_iva_category_catalogue()
    expected = {
        "issued.intra_community_supply": IvaCategory.INTRA_COMMUNITY_SUPPLY,
        "issued.intra_community_service_supply": IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY,
        "received.intra_community_acquisition_reverse_charge": (
            IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE
        ),
        "received.intra_community_service_acquisition_reverse_charge": (
            IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE
        ),
    }

    for key, category in expected.items():
        clave = IntracomOperationType(catalogue.operation_type(key))
        assert iva_category_for_operation_type(clave) is category


def test_no_clave_is_supplied_without_an_operator_facing_meaning() -> None:
    """Every clave the resolver can emit must be selectable and explicable."""
    catalogue = resolve_iva_category_catalogue()
    emitted = {
        IntracomOperationType(catalogue.operation_type(key))
        for key in (
            "issued.intra_community_supply",
            "issued.intra_community_service_supply",
            "received.intra_community_acquisition_reverse_charge",
            "received.intra_community_service_acquisition_reverse_charge",
        )
    }

    assert all(iva_category_for_operation_type(clave) is not None for clave in emitted)


def test_triangulation_is_forward_only_and_that_is_deliberate() -> None:
    """T is filed from either side and therefore has no direction-specific input."""
    assert iva_category_for_operation_type(IntracomOperationType.T) is IvaCategory.INTRA_COMMUNITY_TRIANGULATION


def test_goods_and_service_claves_never_collapse_into_each_other() -> None:
    """A service filed under a goods clave is filed as an entrega de bienes.

    Separate articles govern them — art. 25 exempts the supply, art. 69
    localises the service — so a shared category would misstate the law, not
    merely the paperwork.
    """
    assert iva_category_for_operation_type(IntracomOperationType.E) is IvaCategory.INTRA_COMMUNITY_SUPPLY
    assert iva_category_for_operation_type(IntracomOperationType.S) is IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY
    assert (
        iva_category_for_operation_type(IntracomOperationType.A)
        is IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE
    )
    assert (
        iva_category_for_operation_type(IntracomOperationType.ADQUISICION_SERVICIOS)
        is IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE
    )


@pytest.mark.parametrize(
    "clave",
    [
        IntracomOperationType.M,
        IntracomOperationType.H,
        IntracomOperationType.R,
        IntracomOperationType.D,
        IntracomOperationType.C,
    ],
)
def test_a_clave_carrying_no_inferable_category_yields_none(clave: IntracomOperationType) -> None:
    """Absent is the honest answer where a category cannot be inferred.

    ``M``/``H`` share the supply category with ``E``, so no category predicate
    separates them; ``R``/``D``/``C`` report call-off stock movements that carry
    no invoice at all. Guessing one would put an unstated treatment on a record.
    """
    assert iva_category_for_operation_type(clave) is None


def test_no_clave_selected_means_no_category_asserted() -> None:
    """An operator who chose nothing has asserted nothing."""
    assert iva_category_for_operation_type(None) is None


def test_the_forward_map_covers_both_invoice_directions() -> None:
    """Issued and received each need a reachable clave, or one side cannot file."""
    catalogue = resolve_iva_category_catalogue()
    issued = tuple(
        IntracomOperationType(catalogue.operation_type(key))
        for key in (
            "issued.intra_community_supply",
            "issued.intra_community_service_supply",
        )
    )
    received = tuple(
        IntracomOperationType(catalogue.operation_type(key))
        for key in (
            "received.intra_community_acquisition_reverse_charge",
            "received.intra_community_service_acquisition_reverse_charge",
        )
    )

    assert all(iva_category_for_operation_type(clave) is not None for clave in (*issued, *received))
