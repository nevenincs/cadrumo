"""The intra-community branches turn on the identifying State, not on the place.

LIVA art. 25.Uno states the condition in its own words, and the bundled
consolidated text is the authority this module reads it from
(``_data/corpus/normatives/html/ley-37-1992-art-25.html``): the exemption applies
"siempre que el adquirente sea un empresario o profesional ... que disponga de un
número de identificación a efectos del Impuesto sobre el Valor Añadido asignado
por un Estado miembro distinto del Reino de España". What the acquirer must hold
is a REGISTRATION in another Member State. Where the acquirer has its sede or its
establecimiento permanente is a different fact, governed by arts. 69-70, and
art. 25 does not ask about it.

**The defect this module gates.** The four intra-community rows each declared the
identification consumed while every one of their predicates read only the
territorial scopes. The declaration and the code therefore disagreed, and the
disagreement had a direction: a party holding a non-Spanish VAT identification
whose establishment resolved to anything other than ``EU_MEMBER`` fell through
the intra-community row and landed on the export or import row instead — a
legitimate entrega intracomunitaria exenta reported in the wrong box and left off
the declaración recapitulativa, with nothing anywhere saying so.

**Both directions are gated, because the migration must not trade a refusal for a
wrong exemption.** An operation carrying no identification at all, and one
carrying a Spanish identification, must reach no intra-community row: art. 25
requires a State "distinto del Reino de España", and exempting without that
condition would be silent under-declaration. The honest outcome there is the
``R99`` sentinel, which is a refusal an operator resolves — not a category.

**On the oracle.** The positive art. 25 case already has an external authority:
:mod:`.test_place_of_supply_manual_oracle` replays a worked example from the AEAT
Manual práctico IVA 2025 whose customer is recorded with an identifying Member
State. What this module adds is the DISCRIMINATION the manual does not exercise —
which fact the row turns on — and there is no numeric authority for a predicate's
shape. So the expectations here are grounded on the statutory text quoted above
and gate wiring and refusal behaviour, never a manufactured figure.

See Also:
    :func:`~domain.iva.classify_iva`
        The single rule table under test.
    :class:`~domain.iva.PartyFact`
        The two facts these rows keep apart.
"""

from __future__ import annotations

from datetime import date

import pytest

from .. import (
    CustomerTaxStatus,
    EUMemberState,
    InvoiceKind,
    IvaCategory,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    PartyFact,
    TransactionKind,
    classify_iva,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DATE = date(2025, 6, 15)

_R99 = "R99_fallthrough"


def _criteria(**overrides: object) -> IvaInvoiceClassificationCriteria:
    """Build criteria for a cross-border B2B operation, overriding one axis at a time."""
    base: dict[str, object] = {
        "transaction_date": _DATE,
        "issuer_residency": IvaTerritorialScope.ES_MAINLAND,
        "customer_residency": IvaTerritorialScope.EU_MEMBER,
        "customer_tax_status": CustomerTaxStatus.B2B_IVA_REGISTERED,
        "kind": TransactionKind.GOODS,
        "direction": InvoiceKind.ISSUED,
    }
    base.update(overrides)
    return IvaInvoiceClassificationCriteria.model_validate(base)


class TestTheSupplyExemptionFollowsTheAcquirersRegistration:
    """Art. 25.Uno: the acquirer holds a number assigned by another Member State."""

    def test_an_acquirer_identified_elsewhere_is_exempt_though_established_outside_the_union(self) -> None:
        """The case that failed: identification in Germany, establishment not EU.

        A party established outside the Union may hold a German VAT
        identification and buy under it, and art. 25 asks for exactly that
        number. Keyed on establishment the operation fell to the export row,
        which relieves the same money under art. 21 while filing it in the wrong
        box and omitting it from the declaración recapitulativa the exemption is
        conditioned on.
        """
        result = classify_iva(
            _criteria(
                customer_residency=IvaTerritorialScope.THIRD_COUNTRY,
                customer_identification_state=EUMemberState.DE,
            ),
        )

        assert result.category is IvaCategory.INTRA_COMMUNITY_SUPPLY
        assert result.matched_rule_id == "R10_intra_community_supply"

    def test_an_acquirer_with_no_identification_is_never_exempted(self) -> None:
        """The opposite direction: no number, no art. 25 relief.

        This is the under-declaration guard. The row previously granted the
        exemption on establishment alone, so an EU-established acquirer who never
        communicated a NIF-IVA was zero-rated on a condition the statute makes
        explicit and nobody had checked.
        """
        result = classify_iva(_criteria())

        assert result.category is not IvaCategory.INTRA_COMMUNITY_SUPPLY
        assert result.matched_rule_id == _R99

    def test_a_spanish_identification_is_not_another_member_state(self) -> None:
        """The statute names Spain as the excluded State: "distinto del Reino de España"."""
        result = classify_iva(_criteria(customer_identification_state=EUMemberState.ES))

        assert result.category is not IvaCategory.INTRA_COMMUNITY_SUPPLY
        assert result.matched_rule_id == _R99


class TestTheAcquisitionFollowsTheSuppliersRegistration:
    """The received leg, mirrored: the transmitting party's identifying State."""

    def test_a_supplier_identified_elsewhere_reverse_charges_though_established_outside_the_union(self) -> None:
        result = classify_iva(
            _criteria(
                issuer_residency=IvaTerritorialScope.THIRD_COUNTRY,
                issuer_identification_state=EUMemberState.DE,
                customer_residency=IvaTerritorialScope.ES_MAINLAND,
                direction=InvoiceKind.RECEIVED,
            ),
        )

        assert result.category is IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE
        assert result.requires_reverse_charge is True

    def test_a_supplier_with_no_identification_is_never_an_intra_community_acquisition(self) -> None:
        result = classify_iva(
            _criteria(
                issuer_residency=IvaTerritorialScope.EU_MEMBER,
                customer_residency=IvaTerritorialScope.ES_MAINLAND,
                direction=InvoiceKind.RECEIVED,
            ),
        )

        assert result.category is not IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE
        assert result.matched_rule_id == _R99


class TestTheServiceRowsReadTheIdentificationTheyDeclare:
    """A B2B service reported on the declaración recapitulativa needs the NIF-IVA.

    The place-of-supply half of these rows stays on the establishment, because
    arts. 69 and 84 locate a B2B service by where the recipient is established and
    ask nothing about registration. What the identification adds is the condition
    that makes the operation a REPORTABLE intra-community service rather than a
    plain non-subject supply: both categories these rows assign are the ones that
    select a Modelo 349 clave against a counterparty NIF-IVA, so assigning them
    without one would file a line VIES cannot match.
    """

    def test_an_outbound_service_with_no_counterparty_identification_does_not_place(self) -> None:
        result = classify_iva(_criteria(kind=TransactionKind.SERVICES_GENERAL))

        assert result.matched_rule_id == _R99

    def test_an_outbound_service_places_once_the_counterparty_is_identified(self) -> None:
        result = classify_iva(
            _criteria(
                kind=TransactionKind.SERVICES_GENERAL,
                customer_identification_state=EUMemberState.FR,
            ),
        )

        assert result.matched_rule_id == "R12_services_b2b_eu_outbound"
        assert result.category is IvaCategory.DOMESTIC_NOT_SUBJECT

    def test_an_inbound_service_with_no_supplier_identification_does_not_place(self) -> None:
        result = classify_iva(
            _criteria(
                issuer_residency=IvaTerritorialScope.EU_MEMBER,
                customer_residency=IvaTerritorialScope.ES_MAINLAND,
                kind=TransactionKind.SERVICES_GENERAL,
                direction=InvoiceKind.RECEIVED,
            ),
        )

        assert result.matched_rule_id == _R99

    def test_an_inbound_service_places_once_the_supplier_is_identified(self) -> None:
        result = classify_iva(
            _criteria(
                issuer_residency=IvaTerritorialScope.EU_MEMBER,
                issuer_identification_state=EUMemberState.FR,
                customer_residency=IvaTerritorialScope.ES_MAINLAND,
                kind=TransactionKind.SERVICES_GENERAL,
                direction=InvoiceKind.RECEIVED,
            ),
        )

        assert result.matched_rule_id == "R13_services_b2b_eu_inbound"
        assert result.category is IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE


class TestEveryRowDeclaringTheIdentificationTurnsOnIt:
    """The declaration and the predicate must agree, row by row.

    Scoped to the four rows that declare the fact, and proven by REMOVAL rather
    than by reading the declaration back: each case classifies an operation that
    reaches the row, drops the identification, and requires the verdict to move.
    A row that declared the fact and ignored it would keep its verdict, which is
    exactly the state this module was written against.
    """

    @pytest.mark.parametrize(
        ("rule_id", "overrides", "identification_field"),
        [
            (
                "R10_intra_community_supply",
                {"customer_identification_state": EUMemberState.DE},
                "customer_identification_state",
            ),
            (
                "R11_intra_community_acquisition",
                {
                    "issuer_residency": IvaTerritorialScope.EU_MEMBER,
                    "issuer_identification_state": EUMemberState.DE,
                    "customer_residency": IvaTerritorialScope.ES_MAINLAND,
                    "direction": InvoiceKind.RECEIVED,
                },
                "issuer_identification_state",
            ),
            (
                "R12_services_b2b_eu_outbound",
                {
                    "kind": TransactionKind.SERVICES_GENERAL,
                    "customer_identification_state": EUMemberState.DE,
                },
                "customer_identification_state",
            ),
            (
                "R13_services_b2b_eu_inbound",
                {
                    "issuer_residency": IvaTerritorialScope.EU_MEMBER,
                    "issuer_identification_state": EUMemberState.DE,
                    "customer_residency": IvaTerritorialScope.ES_MAINLAND,
                    "kind": TransactionKind.SERVICES_GENERAL,
                    "direction": InvoiceKind.RECEIVED,
                },
                "issuer_identification_state",
            ),
        ],
    )
    def test_dropping_the_identification_moves_the_verdict(
        self,
        rule_id: str,
        overrides: dict[str, object],
        identification_field: str,
    ) -> None:
        with_identification = classify_iva(_criteria(**overrides))
        assert with_identification.matched_rule_id == rule_id
        assert PartyFact.VAT_IDENTIFICATION_STATE in with_identification.consumes_party_facts

        without = dict(overrides)
        without[identification_field] = None
        assert classify_iva(_criteria(**without)).matched_rule_id != rule_id
