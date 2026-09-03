"""A classification carries the provision that placed it, or it refuses.

The decision table's predicates say WHERE an operation lands; until the result
carried its grounding, the article that establishes the landing lived only in
Python prose. These tests exercise the real resolver against the real bundled
table and hold four properties.

The provision is keyed by the RULE and never by the category. Arts. 68, 69 and
70 fork on goods versus services, so two rules can reach one category from
different articles; a category-keyed answer would flatten that.

An absent nature is a finding. A rule whose provisions do not fix whether goods
or services were supplied carries a row that is present, grounded, and silent on
the axis -- which is a claim about the statute, and is readable as different from
both a stamped nature and a resolution that never happened.

A resolution that cannot be performed raises. It does not arrive as an absent
field, because an absent field is what a hand-built result carries and the two
must stay apart.

The resolution consults the transaction date, so a rule whose grounding stops
covering a year stops answering for it.
"""

from __future__ import annotations

from datetime import date

import pytest

from ..classification import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    TransactionKind,
    classify_iva,
)
from ..errors import IvaCatalogueError
from ..place_of_supply import required_supply_nature_for_rule
from ..schema import EUMemberState, IvaCategory, IvaRateKind
from ..supply_nature import SupplyNature

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_GROUNDED_DAY = date(2025, 6, 15)
"""A day inside every grounded rule's declared span."""

_FIRST_GROUNDED_DAY = date(2022, 1, 1)
_LAST_GROUNDED_DAY = date(2026, 12, 31)
_BEFORE_GROUNDING = date(2021, 12, 31)
_AFTER_GROUNDING = date(2027, 1, 1)


def _services_b2b_eu_outbound(*, on: date = _GROUNDED_DAY) -> IvaInvoiceClassificationCriteria:
    """A B2B service supplied from the peninsula to a German-identified acquirer (``R12``)."""
    return IvaInvoiceClassificationCriteria(
        transaction_date=on,
        issuer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_residency=IvaTerritorialScope.EU_MEMBER,
        customer_identification_state=EUMemberState.DE,
        customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
        kind=TransactionKind.SERVICES_GENERAL,
        direction=InvoiceKind.ISSUED,
    )


def _distance_sale_b2c(*, on: date = _GROUNDED_DAY) -> IvaInvoiceClassificationCriteria:
    """A B2C goods distance sale from the peninsula into the Union (``R15``)."""
    return IvaInvoiceClassificationCriteria(
        transaction_date=on,
        issuer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_residency=IvaTerritorialScope.EU_MEMBER,
        customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
        kind=TransactionKind.GOODS,
        direction=InvoiceKind.ISSUED,
    )


def _domestic_at_general_rate(*, on: date = _GROUNDED_DAY) -> IvaInvoiceClassificationCriteria:
    """An ES-to-ES supply settled by its rate tier (``R05``)."""
    return IvaInvoiceClassificationCriteria(
        transaction_date=on,
        issuer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
        kind=TransactionKind.SERVICES_GENERAL,
        direction=InvoiceKind.ISSUED,
        rate_tier=IvaRateKind.GENERAL,
    )


def test_cross_border_result_carries_its_governing_article_and_nature() -> None:
    """``R12`` arrives with art. 69 as its establishing provision and the services nature."""
    result = classify_iva(_services_b2b_eu_outbound())

    assert result.matched_rule_id == "R12_services_b2b_eu_outbound"
    grounding = result.place_of_supply
    assert grounding is not None
    assert grounding.rule_id == result.matched_rule_id
    assert grounding.establishing_reference == "ley-37-1992:art-69"
    assert grounding.establishing_reference in grounding.legal_references
    assert grounding.supply_nature is SupplyNature.SERVICES
    # The stamped nature is the table's, not a second opinion assembled in the
    # classifier: it must equal what the owning module answers for the same
    # rule on the same day.
    assert grounding.supply_nature == required_supply_nature_for_rule(
        result.matched_rule_id,
        on=_GROUNDED_DAY,
    )


def test_a_silent_nature_is_present_and_grounded_rather_than_missing() -> None:
    """``R05`` carries a grounded row whose articles say nothing about the nature."""
    result = classify_iva(_domestic_at_general_rate())

    assert result.matched_rule_id == "R05_domestic_at_rate_tier"
    grounding = result.place_of_supply
    # Present: something was resolved.
    assert grounding is not None
    # Grounded: it cites articles and names the one that decides, so the
    # silence below is not an unfinished row.
    assert not grounding.legal_basis_exempt
    assert grounding.legal_references
    assert grounding.establishing_reference == "ley-37-1992:art-68"
    # Silent: both placement rules put the operation in the same territory, so
    # the articles fix no nature and the rate tier settles the treatment.
    assert grounding.supply_nature is None


def test_a_resolution_that_cannot_be_performed_raises_instead_of_arriving_absent() -> None:
    """The failure mode is an exception, which is what keeps it apart from a silent nature.

    Run beside :func:`test_a_silent_nature_is_present_and_grounded_rather_than_missing`
    the pair is the whole distinction: there, ``place_of_supply`` is present and
    ``supply_nature`` is ``None``; here nothing is returned at all. Neither
    state can be mistaken for the other, and neither is the ``None`` field a
    hand-assembled result carries.
    """
    with pytest.raises(IvaCatalogueError, match=r"place-of-supply|grounding"):
        classify_iva(_domestic_at_general_rate(on=_AFTER_GROUNDING))


def test_the_provision_is_resolved_from_the_rule_and_not_from_the_category() -> None:
    """Two rules reaching one category carry different articles and different natures.

    ``R12`` and ``R15`` both resolve to
    :attr:`~cadrumo.domain.iva.IvaCategory.DOMESTIC_NOT_SUBJECT`, and they rest
    on different provisions: art. 69 locates the service, art. 68 locates the
    goods. A grounding derived from the category could not tell them apart.
    """
    services = classify_iva(_services_b2b_eu_outbound())
    goods = classify_iva(_distance_sale_b2c())

    assert services.category is goods.category is IvaCategory.DOMESTIC_NOT_SUBJECT
    assert services.matched_rule_id != goods.matched_rule_id

    services_grounding = services.place_of_supply
    goods_grounding = goods.place_of_supply
    assert services_grounding is not None
    assert goods_grounding is not None
    assert services_grounding.establishing_reference == "ley-37-1992:art-69"
    assert goods_grounding.establishing_reference == "ley-37-1992:art-68"
    assert services_grounding.establishing_reference != goods_grounding.establishing_reference
    assert services_grounding.supply_nature is SupplyNature.SERVICES
    assert goods_grounding.supply_nature is SupplyNature.GOODS


def test_the_grounding_is_resolved_against_the_transaction_date() -> None:
    """The same rule answers inside its declared span and refuses outside it.

    Every row in the bundled table declares one span, so there is no year at
    which a rule's provision or nature CHANGES to assert against. What is
    assertable, and what this holds, is that the date is consulted rather than
    ignored: the first and last grounded days resolve, and the days either side
    of them refuse. A row whose span later stops short of a filing year will
    stop answering for it here rather than answering from a rule that no longer
    applies.
    """
    for day in (_FIRST_GROUNDED_DAY, _LAST_GROUNDED_DAY):
        grounding = classify_iva(_services_b2b_eu_outbound(on=day)).place_of_supply
        assert grounding is not None
        assert grounding.establishing_reference == "ley-37-1992:art-69"
        assert grounding.window is not None
        assert grounding.window.covers_year(day.year)

    for day in (_BEFORE_GROUNDING, _AFTER_GROUNDING):
        with pytest.raises(IvaCatalogueError, match=str(day.year)):
            classify_iva(_services_b2b_eu_outbound(on=day))


def test_the_fallthrough_carries_the_row_that_says_it_grounds_nothing() -> None:
    """``R99`` is stamped too, with the exempt row rather than with an absence.

    An unclassifiable operation codifies no treatment, so its row cites no
    provision by declaration. Carrying that row is what lets a consumer read
    "the table says there is nothing to cite here" instead of guessing at an
    empty field.
    """
    unclassifiable = IvaInvoiceClassificationCriteria(
        transaction_date=_GROUNDED_DAY,
        issuer_residency=IvaTerritorialScope.THIRD_COUNTRY,
        customer_residency=IvaTerritorialScope.THIRD_COUNTRY,
        customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
        kind=TransactionKind.SERVICES_GENERAL,
        direction=InvoiceKind.ISSUED,
    )
    result = classify_iva(unclassifiable)

    assert result.category is IvaCategory.UNKNOWN
    grounding = result.place_of_supply
    assert grounding is not None
    assert grounding.rule_id == "R99_fallthrough"
    assert grounding.legal_basis_exempt
    assert grounding.legal_references == ()
    assert grounding.supply_nature is None
