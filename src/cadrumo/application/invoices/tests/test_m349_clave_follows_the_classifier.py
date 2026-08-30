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

from ....domain.iva.classification import CustomerTaxStatus, InvoiceKind, IvaInvoiceClassificationCriteria, IvaTerritorialScope, TransactionKind, classify_iva
from ....domain.iva.schema import EUMemberState, IvaCategory, IvaRateKind
from .._source_resolver import _CLAVE_BY_KIND_AND_CATEGORY

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _eu_inbound_b2b(*, kind: TransactionKind) -> IvaInvoiceClassificationCriteria:
    """EU_MEMBER to ES B2B RECEIVED criteria differing only by supply ``kind``."""
    return IvaInvoiceClassificationCriteria.model_validate(
        {
            "transaction_date": date(2026, 3, 1),
            "issuer_residency": IvaTerritorialScope.EU_MEMBER,
            "issuer_identification_state": EUMemberState.DE,
            "customer_residency": IvaTerritorialScope.ES_MAINLAND,
            "customer_tax_status": CustomerTaxStatus.B2B_IVA_REGISTERED,
            "kind": kind,
            "direction": InvoiceKind.RECEIVED,
            "rate_tier": IvaRateKind.GENERAL,
        },
    )


def test_an_acquired_service_files_under_a_different_clave_than_acquired_goods() -> None:
    """The classifier's own output, carried through to the clave it files under.

    The assertion that matters is the last one. The two claves must DIFFER: a
    services leg reaching the goods clave is the wrong-clave defect, and it would
    be invisible to any test that starts from a category rather than from the
    facts the classifier reads.
    """
    goods = classify_iva(_eu_inbound_b2b(kind=TransactionKind.GOODS))
    services = classify_iva(_eu_inbound_b2b(kind=TransactionKind.SERVICES_GENERAL))

    assert goods.matched_rule_id == "R11_intra_community_acquisition"
    assert services.matched_rule_id == "R13_services_b2b_eu_inbound"

    goods_clave = _CLAVE_BY_KIND_AND_CATEGORY[(InvoiceKind.RECEIVED, goods.category)]
    services_clave = _CLAVE_BY_KIND_AND_CATEGORY[(InvoiceKind.RECEIVED, services.category)]

    assert goods_clave.value == "A"
    assert services_clave.value == "I"
    assert goods_clave is not services_clave


def test_every_category_the_inbound_classifier_can_emit_for_the_eu_has_a_clave() -> None:
    """A category the classifier can produce must be filable, not just expressible.

    The clave table is keyed by category, so a new intra-community category added
    to the classifier without a table entry would raise a ``KeyError`` deep in the
    M349 path rather than at the point the category was introduced. Asserting
    membership from the CLASSIFIER's side rather than restating the table means
    the two cannot drift apart silently.
    """
    for kind in (TransactionKind.GOODS, TransactionKind.SERVICES_GENERAL):
        verdict = classify_iva(_eu_inbound_b2b(kind=kind))
        assert (InvoiceKind.RECEIVED, verdict.category) in _CLAVE_BY_KIND_AND_CATEGORY, verdict.category


def test_the_goods_and_services_acquisition_categories_are_distinct_members() -> None:
    """Positive control for the comparison above.

    If the two categories were ever collapsed into one member, the clave
    comparison would compare a value against itself and pass while the defect it
    guards was fully present. This makes that collapse fail here instead.
    """
    assert (
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE
        is not IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE
    )
