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
from ....domain.iva.classification import InvoiceKind, IvaCategory
from ..source_resolver import (
    _CLAVE_BY_KIND_AND_CATEGORY,
    _IVA_CATEGORY_BY_OPERATION_TYPE,
    iva_category_for_operation_type,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_every_inverse_entry_round_trips_through_the_forward_map() -> None:
    """A category implying a clave must be the category that clave declares.

    This is the drift the two maps could produce: the resolver files an invoice
    under clave X for category Y, while an operator selecting X is told the
    invoice is category Z.
    """
    disagreements = [
        f"({kind.value}, {category.value}) -> {clave.name}, but {clave.name} declares "
        f"{getattr(_IVA_CATEGORY_BY_OPERATION_TYPE.get(clave), 'value', None)}"
        for (kind, category), clave in _CLAVE_BY_KIND_AND_CATEGORY.items()
        if _IVA_CATEGORY_BY_OPERATION_TYPE.get(clave) is not category
    ]

    assert not disagreements, f"the clave/category relationship disagrees with itself: {disagreements}"


def test_no_clave_is_supplied_without_an_operator_facing_meaning() -> None:
    """Every clave the resolver can emit must be selectable and explicable."""
    emitted = set(_CLAVE_BY_KIND_AND_CATEGORY.values())

    assert emitted <= set(_IVA_CATEGORY_BY_OPERATION_TYPE)


def test_triangulation_is_forward_only_and_that_is_deliberate() -> None:
    """T is filed from either side, so a kind-keyed inverse cannot hold it.

    Pinned so the asymmetry reads as a decision rather than an omission the
    next reader "fixes" by inventing a kind for it.
    """
    assert iva_category_for_operation_type(IntracomOperationType.T) is IvaCategory.INTRA_COMMUNITY_TRIANGULATION
    assert IntracomOperationType.T not in set(_CLAVE_BY_KIND_AND_CATEGORY.values())


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
    issued = {kind for (kind, _category) in _CLAVE_BY_KIND_AND_CATEGORY} & {InvoiceKind.ISSUED}
    received = {kind for (kind, _category) in _CLAVE_BY_KIND_AND_CATEGORY} & {InvoiceKind.RECEIVED}

    assert issued and received
