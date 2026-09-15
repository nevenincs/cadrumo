"""The Modelo 349 clave a classified intra-community operation actually files under.

Two things were already covered separately and neither covers the join. The
classifier suite proves ``R13`` resolves an EU inbound B2B services leg to the
services acquisition category, and the resolver suite proves an invoice already
carrying that category maps to clave ``I``. Neither runs the chain, so a change
that re-pointed ``R13`` at the goods category would leave both green while filing
every acquired service against VIES as an adquisición de bienes.

That is the defect this module exists to catch, and it is a filing defect rather
than a calculation one: Modelo 303 combines the legs — official boxes 10/11 are
titled "adquisiciones intracomunitarias de bienes y servicios" — so the goods and
services categories select the same bindings there and either would settle
correctly. The separation only becomes load-bearing at the Modelo 349 surface,
which is exactly where nothing was checking it.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ....core.aggregation import IntracomOperationType
from ....domain.calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ....domain.iva.classification import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    TransactionKind,
    classify_iva,
)
from ....domain.iva.schema import EUMemberState, IvaCategory, IvaRateKind
from ..source_resolver import iva_category_for_operation_type

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _eu_inbound_b2b(*, kind: TransactionKind) -> IvaInvoiceClassificationCriteria:
    """EU_MEMBER to ES B2B RECEIVED criteria differing only by supply ``kind``."""
    return IvaInvoiceClassificationCriteria.model_validate(
        {
            "transaction_date": date(2026, 3, 1),
            "issuer_residency": IvaTerritorialScope.from_registry("eu_member"),
            "issuer_identification_state": EUMemberState.from_registry("de"),
            "customer_residency": IvaTerritorialScope.from_registry("es_mainland"),
            "customer_tax_status": CustomerTaxStatus.from_registry("b2b_iva_registered"),
            "kind": kind,
            "direction": InvoiceKind.RECEIVED,
            "rate_tier": IvaRateKind("general"),
        },
    )


def test_an_acquired_service_files_under_a_different_clave_than_acquired_goods() -> None:
    """The classifier's own output, carried through to the clave it files under.

    The assertion that matters is the last one. The two claves must DIFFER: a
    services leg reaching the goods clave is the wrong-clave defect, and it would
    be invisible to any test that starts from a category rather than from the
    facts the classifier reads.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        goods = classify_iva(_eu_inbound_b2b(kind=TransactionKind("goods")), operation=_authority_operation_for_test)
        services = classify_iva(
            _eu_inbound_b2b(kind=TransactionKind("services_general")), operation=_authority_operation_for_test
        )

        assert goods.matched_rule_id == "R11_intra_community_acquisition"
        assert services.matched_rule_id == "R13_services_b2b_eu_inbound"

        catalogue = resolve_iva_category_catalogue()
        goods_clave = IntracomOperationType(
            catalogue.operation_type("received.intra_community_acquisition_reverse_charge"),
        )
        services_clave = IntracomOperationType(
            catalogue.operation_type("received.intra_community_service_acquisition_reverse_charge"),
        )

        assert goods_clave.value == "A"
        assert services_clave.value == "I"
        assert goods_clave is not services_clave
        assert iva_category_for_operation_type(goods_clave) == goods.category
        assert iva_category_for_operation_type(services_clave) == services.category


def test_every_category_the_inbound_classifier_can_emit_for_the_eu_has_a_clave() -> None:
    """A category the classifier can produce must be filable, not just expressible.

    The clave table is keyed by category, so a new intra-community category added
    to the classifier without a table entry would raise a ``KeyError`` deep in the
    M349 path rather than at the point the category was introduced. Asserting
    membership from the CLASSIFIER's side rather than restating the table means
    the two cannot drift apart silently.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        catalogue = resolve_iva_category_catalogue()
        operation_by_category = {
            IvaCategory("intra_community_acquisition_reverse_charge"): IntracomOperationType(
                catalogue.operation_type("received.intra_community_acquisition_reverse_charge"),
            ),
            IvaCategory("intra_community_service_acquisition_reverse_charge"): IntracomOperationType(
                catalogue.operation_type("received.intra_community_service_acquisition_reverse_charge"),
            ),
        }
        for kind in (TransactionKind("goods"), TransactionKind("services_general")):
            verdict = classify_iva(_eu_inbound_b2b(kind=kind), operation=_authority_operation_for_test)
            clave = operation_by_category[verdict.category]
            assert iva_category_for_operation_type(clave) == verdict.category


def test_the_goods_and_services_acquisition_categories_are_distinct_members() -> None:
    """Positive control for the comparison above.

    If the two categories were ever collapsed into one member, the clave
    comparison would compare a value against itself and pass while the defect it
    guards was fully present. This makes that collapse fail here instead.
    """
    assert IvaCategory("intra_community_acquisition_reverse_charge") != IvaCategory(
        "intra_community_service_acquisition_reverse_charge"
    )
