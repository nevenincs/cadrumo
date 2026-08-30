"""A service leaving the Comunidad is located by WHO receives it, not only where.

LIVA art. 69 forks on the recipient's condition and the two limbs land in
opposite places. 69.Uno.1.º puts the supply at the recipient, but only when that
recipient is an *empresario o profesional que actúe como tal*. 69.Uno.2.º puts a
B2C supply at the SUPPLIER, so a mainland issuer's is realizada en el TAI and
taxed here.

The row this suite gates read establishment alone, so both limbs reached the
not-subject outcome and every B2C service outside the Comunidad was booked
outside Spanish IVA. Two populations under-declared, and the second was
self-inflicted: the row read ``THIRD_COUNTRY`` until the art. 3 definitional
chain widened it to every territory outside the Comunidad -- right for goods and
for the B2B limb, and straight into the paragraph that excepts Canarias, Ceuta
and Melilla by name.

**Every case here carries its own control.** The B2B limb runs through the same
three territories, because a suite that only proves refusals would pass just as
well over a row that refused everything.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ..classification import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    TransactionKind,
    classify_iva,
)
from ..schema import IvaArt69DosService, IvaCategory, IvaRateKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The three territories art. 3 places outside the Comunidad, which is the reach
#: the goods export row needs and the B2B services row shares.
_OUTSIDE_THE_COMUNIDAD = (
    IvaTerritorialScope.THIRD_COUNTRY,
    IvaTerritorialScope.ES_CANARIAS,
    IvaTerritorialScope.ES_CEUTA_MELILLA,
)

#: Categories that leave the operation inside Spanish IVA at a rate.
_SUBJECT_AT_A_SPANISH_RATE = frozenset(
    {
        IvaCategory.DOMESTIC_GENERAL,
        IvaCategory.DOMESTIC_REDUCED,
        IvaCategory.DOMESTIC_SUPER_REDUCED,
    },
)


def _outbound_service(
    *,
    customer_residency: IvaTerritorialScope,
    customer_tax_status: CustomerTaxStatus,
    rate_tier: IvaRateKind | None = IvaRateKind.GENERAL,
    art_69_dos_service: IvaArt69DosService | None = None,
) -> IvaInvoiceClassificationCriteria:
    """A mainland issuer's general service, billed outward."""
    return IvaInvoiceClassificationCriteria.model_validate(
        {
            "transaction_date": date(2025, 6, 15),
            "issuer_residency": IvaTerritorialScope.ES_MAINLAND,
            "customer_residency": customer_residency,
            "customer_tax_status": customer_tax_status,
            "kind": TransactionKind.SERVICES_GENERAL,
            "direction": InvoiceKind.ISSUED,
            "rate_tier": rate_tier,
            "art_69_dos_service": art_69_dos_service,
        },
    )


def _establishment_only_would_have_matched(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """The predicate as it stood before the fork, restated to drive the proof.

    Deliberately a restatement rather than an import: the shipped row no longer
    has this shape, and the case is worthless unless it can show the OLD shape
    matching the criteria the NEW shape refuses. Kept beside its cases so it
    cannot drift out of sight of what it is proving.
    """
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency in _OUTSIDE_THE_COMUNIDAD
        and criteria.kind is TransactionKind.SERVICES_GENERAL
        and criteria.direction is InvoiceKind.ISSUED
    )


# --------------------------------------------------------------------------
# The B2C limb: art. 69.Uno.2.º keeps the supply here.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("customer_residency", _OUTSIDE_THE_COMUNIDAD, ids=lambda scope: scope.value)
def test_a_b2c_service_outside_the_comunidad_stays_taxed_here(
    customer_residency: IvaTerritorialScope,
) -> None:
    """The under-declaration, closed: not-subject required a fact nobody had.

    Art. 69.Uno.2.º places a B2C service where the SUPPLIER is established, so a
    mainland issuer's lands in the TAI whatever the consumer's country. Booking
    it not-subject relieved a taxable supply on the strength of the customer's
    address alone.
    """
    result = classify_iva(
        _outbound_service(customer_residency=customer_residency, customer_tax_status=CustomerTaxStatus.B2C_CONSUMER)
    )

    assert result.category is not IvaCategory.OPERACION_NO_SUJETA
    assert result.category in _SUBJECT_AT_A_SPANISH_RATE
    assert result.matched_rule_id == "R24_services_outbound_b2c_at_rate_tier"


@pytest.mark.parametrize("customer_residency", _OUTSIDE_THE_COMUNIDAD, ids=lambda scope: scope.value)
def test_the_pre_change_row_would_have_booked_each_of_them_not_subject(
    customer_residency: IvaTerritorialScope,
) -> None:
    """The mutation proof: the fork is what bites, not something else.

    Without it the cases above could pass because some unrelated row moved. Here
    the row's own former predicate is run against the same criteria and matches
    every one of them, which is exactly the population it was sending to
    not-subject.
    """
    criteria = _outbound_service(
        customer_residency=customer_residency,
        customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
    )

    assert _establishment_only_would_have_matched(criteria), (
        "the former predicate no longer matches this case, so it proves nothing about the change"
    )
    assert classify_iva(criteria).category is not IvaCategory.OPERACION_NO_SUJETA


def test_the_spanish_territories_are_the_ones_art_69_dos_names_back_in() -> None:
    """The sharper half, because here the statute is express rather than inferred.

    Art. 69.Dos excepts a closed list of B2C services when the recipient is
    established outside the Comunidad, and states its own limit in the same
    sentence: "salvo en el caso de que dicho destinatario esté establecido o
    tenga su domicilio o residencia habitual en las Islas Canarias, Ceuta o
    Melilla". So even a service ON that list stays taxed here for those
    recipients, and no reading of the exception can reach them.
    """
    for customer_residency in (IvaTerritorialScope.ES_CANARIAS, IvaTerritorialScope.ES_CEUTA_MELILLA):
        result = classify_iva(
            _outbound_service(
                customer_residency=customer_residency,
                customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
            ),
        )
        assert result.category in _SUBJECT_AT_A_SPANISH_RATE, (
            f"a B2C service to {customer_residency.value} is inside the TAI by art. 69.Dos's own carve-back"
        )


def test_the_b2c_branch_demands_the_tier_that_selects_its_category() -> None:
    """A supply taxed here needs the rate that taxes it.

    The tier is not decoration on this branch: it is what picks the domestic
    category. Defaulting it would pick GENERAL for a service that may be
    reduced, which is a silent wrong answer rather than a refusal.
    """
    # Pydantic wraps the domain refusal on the way out of ``model_validate``, so
    # the surfaced type is its own; the message is the domain's.
    with pytest.raises(ValidationError, match="rate_tier is required"):
        _outbound_service(
            customer_residency=IvaTerritorialScope.THIRD_COUNTRY,
            customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
            rate_tier=None,
        )


# --------------------------------------------------------------------------
# Art. 69.Dos: the closed list that lifts a B2C service back out of the TAI.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("service", list(IvaArt69DosService), ids=lambda item: item.value)
def test_every_listed_service_to_a_third_country_consumer_leaves_the_tai(
    service: IvaArt69DosService,
) -> None:
    """The exception, per item across the whole enum rather than on a sample.

    Driven from the enum so a member added later is covered without editing this
    file -- and so a member added WITHOUT the row reading it fails here instead
    of quietly staying taxed.
    """
    result = classify_iva(
        _outbound_service(
            customer_residency=IvaTerritorialScope.THIRD_COUNTRY,
            customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
            art_69_dos_service=service,
        ),
    )

    assert result.category is IvaCategory.OPERACION_NO_SUJETA
    assert result.matched_rule_id == "R25_services_outbound_b2c_art_69_dos"


@pytest.mark.parametrize(
    "customer_residency",
    [IvaTerritorialScope.ES_CANARIAS, IvaTerritorialScope.ES_CEUTA_MELILLA],
    ids=lambda scope: scope.value,
)
@pytest.mark.parametrize("service", list(IvaArt69DosService), ids=lambda item: item.value)
def test_the_same_listed_service_stays_taxed_for_the_spanish_territories(
    service: IvaArt69DosService,
    customer_residency: IvaTerritorialScope,
) -> None:
    """The exception's own limit, which is the half most easily lost.

    Canarias, Ceuta and Melilla ARE outside the Comunidad, so a reading that
    stopped at "fuera de la Comunidad" would except them. Art. 69.Dos names them
    back out in the same sentence, so every listed service stays realizada en el
    TAI for those recipients. Same items as the case above, opposite answer.
    """
    result = classify_iva(
        _outbound_service(
            customer_residency=customer_residency,
            customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
            art_69_dos_service=service,
        ),
    )

    assert result.category in _SUBJECT_AT_A_SPANISH_RATE
    assert result.category is not IvaCategory.OPERACION_NO_SUJETA


def test_an_unstated_item_does_not_lift_the_supply_out_of_the_tai() -> None:
    """Absence is not evidence, on the axis where reading it as evidence relieves tax.

    Nobody having said which lettered service applies is not a finding that none
    does. Treating the empty field as "not on the list" would be the correct
    answer often and a silent relief the rest of the time.
    """
    result = classify_iva(
        _outbound_service(
            customer_residency=IvaTerritorialScope.THIRD_COUNTRY,
            customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
            art_69_dos_service=None,
        ),
    )

    assert result.category is not IvaCategory.OPERACION_NO_SUJETA
    assert result.category in _SUBJECT_AT_A_SPANISH_RATE


def test_the_excepted_branch_is_not_asked_for_a_tier_it_never_uses() -> None:
    """A supply outside the TAI bears no Spanish rate, so no tier selects it.

    The sibling B2C branch refuses without one. Demanding it here too would ask
    the operator for a fact the branch they landed on does not read.
    """
    result = classify_iva(
        _outbound_service(
            customer_residency=IvaTerritorialScope.THIRD_COUNTRY,
            customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
            art_69_dos_service=IvaArt69DosService.ART_69_DOS_C,
            rate_tier=None,
        ),
    )

    assert result.category is IvaCategory.OPERACION_NO_SUJETA


@pytest.mark.parametrize("customer_residency", _OUTSIDE_THE_COMUNIDAD, ids=lambda scope: scope.value)
def test_a_stated_item_moves_nothing_on_the_b2b_limb(
    customer_residency: IvaTerritorialScope,
) -> None:
    """Art. 69.Dos excepts from 69.Uno.2.º, which is the B2C paragraph alone.

    A B2B service was never placed by that paragraph, so a stated item has
    nothing to except it from. This is where a fix reaching one row too far
    would show: the B2B answer must be identical with and without the item.
    """
    stated = classify_iva(
        _outbound_service(
            customer_residency=customer_residency,
            customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
            art_69_dos_service=IvaArt69DosService.ART_69_DOS_D,
        ),
    )
    unstated = classify_iva(
        _outbound_service(
            customer_residency=customer_residency,
            customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
        ),
    )

    assert stated.category is unstated.category
    assert stated.matched_rule_id == unstated.matched_rule_id == "R22_services_outbound_b2b"


# --------------------------------------------------------------------------
# The B2B limb, unchanged: the control that keeps the cases above honest.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("customer_residency", _OUTSIDE_THE_COMUNIDAD, ids=lambda scope: scope.value)
@pytest.mark.parametrize(
    "customer_tax_status",
    [CustomerTaxStatus.B2B_IVA_REGISTERED, CustomerTaxStatus.B2B_NOT_REGISTERED],
    ids=["registered", "not-registered"],
)
def test_a_b2b_service_outside_the_comunidad_is_still_not_subject(
    customer_residency: IvaTerritorialScope,
    customer_tax_status: CustomerTaxStatus,
) -> None:
    """The outcome that was already right, through the same three territories.

    Both business statuses, because art. 69.Uno.1.º asks for an *empresario o
    profesional que actúe como tal* and says nothing about registration. Keying
    the limb on a valid IVA number would drop every unregistered business into
    the taxed branch, which is the mirror error of the one this change fixes.
    """
    result = classify_iva(
        _outbound_service(customer_residency=customer_residency, customer_tax_status=customer_tax_status),
    )

    assert result.category is IvaCategory.OPERACION_NO_SUJETA
    assert result.matched_rule_id == "R22_services_outbound_b2b"


# --------------------------------------------------------------------------
# Neither limb: the conditions the article does not settle.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "customer_tax_status",
    [CustomerTaxStatus.UNKNOWN, CustomerTaxStatus.PUBLIC_ADMINISTRATION],
    ids=["unknown", "public-administration"],
)
def test_a_condition_the_article_does_not_settle_reaches_neither_limb(
    customer_tax_status: CustomerTaxStatus,
) -> None:
    """Fail toward asking, on both of the statuses art. 69.Uno does not place.

    ``UNKNOWN`` is the absence of the fact, and an absence cannot satisfy a
    condition -- letting it fall through to not-subject would grant the relief on
    nothing at all. ``PUBLIC_ADMINISTRATION`` is a real ruling deferred rather
    than an oversight: art. 69.Tres.4.º treats a legal person holding an IVA
    identification as an empresario for these rules even when it does not act as
    one, and that needs its own grounding.
    """
    result = classify_iva(
        _outbound_service(
            customer_residency=IvaTerritorialScope.THIRD_COUNTRY,
            customer_tax_status=customer_tax_status,
        ),
    )

    assert result.category is IvaCategory.UNKNOWN
    assert result.category is not IvaCategory.OPERACION_NO_SUJETA
