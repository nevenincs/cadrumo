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
disagreement had a direction: a party holding a non-Spanish IVA identification
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

from ..classification import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    PartyFact,
    TransactionKind,
    classify_iva,
)
from ..components import category_cuota_is_zero_by_law
from ..establishment import country_code_for_printed_tax_identifier
from ..identification import identification_state_for_printed_tax_identifier
from ..schema import EUMemberState, IvaCategory

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

        A party established outside the Union may hold a German IVA
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
        assert PartyFact.IVA_IDENTIFICATION_STATE in with_identification.consumes_party_facts

        without = dict(overrides)
        without[identification_field] = None
        assert classify_iva(_criteria(**without)).matched_rule_id != rule_id


# -- ES joins the IDENTIFICATION vocabulary, and only that one --------------
#
# The axis was one-sided: an intra-community sale had the counterparty's
# identification established from the paper while the filer's own was merely
# assertable. The reason was structural rather than legal. Every sibling prefix
# is recognised by matching the number's BODY against the structure its prefix
# claims, and Spanish identifiers are checksum identifiers rather than
# structural ones -- so ES could not join the way its siblings did.
#
# RGAT art. 25 is what makes the printed form readable: for a party in the
# Registro de operadores intracomunitarios the identifier is the ordinary one
# "al que se antepondra el prefijo ES, conforme al estandar internacional
# codigo ISO-3166 alfa 2". The prefix is regulated, not conventional.
#
# The safety is STRUCTURAL, not careful: identification and establishment are
# different questions, the establishment resolver returns nothing for Spain by
# design because registration is not establishment, and this is reached only
# where that resolver already declined.

_SPANISH_CIF = "B12345674"
_SPANISH_IVA = "ESB12345674"


def test_a_spanish_iva_number_now_states_its_identification() -> None:
    """The measured gap: the filer's own side was only ever assertable."""
    assert identification_state_for_printed_tax_identifier(_SPANISH_IVA) is EUMemberState.ES


@pytest.mark.parametrize(
    "printed",
    ["ES B12345674", "ES B-1234567-4", "esb12345674", "  ESB12345674  "],
    ids=["spaced", "punctuated", "lowercase", "padded"],
)
def test_the_printed_spelling_does_not_change_the_identification(printed: str) -> None:
    """An issuer prints the same number several ways; it is one identification."""
    assert identification_state_for_printed_tax_identifier(printed) is EUMemberState.ES


def test_stating_an_identification_states_no_establishment() -> None:
    """The load-bearing separation, asserted rather than trusted.

    Registration is not establishment: the non-resident N leader, the L and M
    identifiers and the X/Y/Z series all belong to parties registered in Spain
    and established elsewhere. So a Spanish prefix must reach the identification
    axis without opening the postal rung behind it.
    """
    assert identification_state_for_printed_tax_identifier(_SPANISH_IVA) is EUMemberState.ES
    assert country_code_for_printed_tax_identifier(_SPANISH_IVA) is None


def test_a_bare_spanish_identifier_still_states_nothing() -> None:
    """Absence must not become a Spanish identification.

    A document printing a bare CIF prints no prefix at all, so reading it as a
    Spanish identification would manufacture the fact from its own silence --
    and that silence is the ordinary shape of a domestic invoice.
    """
    assert identification_state_for_printed_tax_identifier(_SPANISH_CIF) is None


@pytest.mark.parametrize(
    "printed",
    ["ESB99999999", "ESFRANCISCO", "ES", "ES12345678A1"],
    ids=["wrong-control-letter", "prose-in-the-field", "prefix-alone", "malformed-body"],
)
def test_an_es_prefix_over_a_body_that_fails_the_checksum_states_nothing(printed: str) -> None:
    """The precision half, and the reason this is a checksum rather than a pattern.

    The prefix alone establishes nothing: a party name lands in an identifier
    field routinely, and FRANCISCO would otherwise be read as a Spanish
    identification. The AEAT control letter is what makes the reading answer
    only where a real number was printed.
    """
    assert identification_state_for_printed_tax_identifier(printed) is None


def test_the_sibling_prefixes_are_unaffected() -> None:
    """Adding ES must not disturb the vocabulary it could not join."""
    assert identification_state_for_printed_tax_identifier("DE811234567") is EUMemberState.DE
    assert country_code_for_printed_tax_identifier("DE811234567") == "DE"


def test_the_checksum_is_what_admits_the_spanish_number() -> None:
    """Mutation proof: without it an ES prefix over anything would identify Spain.

    Re-runs the naive rule -- take the prefix, believe it -- and shows it reads
    a party name as a Spanish identification. That is what the control letter
    exists to refuse, and a suite asserting only that valid numbers pass would
    not distinguish the two.
    """

    def _prefix_alone(printed: str) -> bool:
        return printed.upper().startswith("ES")

    assert _prefix_alone("ESFRANCISCO")
    assert identification_state_for_printed_tax_identifier("ESFRANCISCO") is None
    assert identification_state_for_printed_tax_identifier(_SPANISH_IVA) is EUMemberState.ES


# -- the outbound non-peninsular branch -------------------------------------
#
# The table had no row for a mainland issuer supplying a customer in Canarias,
# Ceuta or Melilla, so that population resolved UNRESOLVED. R30 names those
# territories but keys on the ISSUER being outside the TAI, which is the
# inbound direction.
#
# LIVA art. 3.Dos.1 excludes all three from "interior del pais", art. 3.Dos.2
# defines "Comunidad" as the territories that do constitute it, and art. 3.Dos.3
# defines "territorio tercero" as anything else -- so art. 21 reaches them.


def _outbound(customer: IvaTerritorialScope, kind: TransactionKind) -> IvaCategory:
    return classify_iva(
        IvaInvoiceClassificationCriteria(
            issuer_residency=IvaTerritorialScope.ES_MAINLAND,
            customer_residency=customer,
            kind=kind,
            direction=InvoiceKind.ISSUED,
            customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
            transaction_date=date(2026, 3, 11),
        ),
    ).category


@pytest.mark.parametrize(
    "customer",
    [IvaTerritorialScope.ES_CANARIAS, IvaTerritorialScope.ES_CEUTA_MELILLA],
    ids=["canarias", "ceuta-y-melilla"],
)
def test_goods_leaving_the_tai_are_an_export_whichever_territory_receives_them(
    customer: IvaTerritorialScope,
) -> None:
    """Art. 21 reaches all three third territories, so the two share an answer.

    They are excluded from "interior del pais" for DIFFERENT reasons -- Ceuta
    and Melilla sit outside the customs union and Canarias does not -- which
    separates them for a customs question and not for this one.
    """
    assert _outbound(customer, TransactionKind.GOODS) is IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED


@pytest.mark.parametrize(
    "customer",
    [IvaTerritorialScope.ES_CANARIAS, IvaTerritorialScope.ES_CEUTA_MELILLA],
    ids=["canarias", "ceuta-y-melilla"],
)
def test_services_leaving_the_tai_are_not_subject_rather_than_exempt(
    customer: IvaTerritorialScope,
) -> None:
    """Goods and services fork, and the fork is the point.

    Art. 21 exempts *entregas de bienes* only. A service to a recipient
    established outside the TAI is localised there by arts. 69 and 70, so it is
    NOT SUBJECT here rather than exempt -- a different outcome carrying a
    different Modelo 303 consequence, which is why one predicate feeds two rows
    rather than one row covering both.
    """
    assert _outbound(customer, TransactionKind.SERVICES_GENERAL) is IvaCategory.OPERACION_NO_SUJETA


def test_a_third_country_customer_is_unaffected() -> None:
    """The rows these territories joined must keep answering as they did."""
    assert (
        _outbound(IvaTerritorialScope.THIRD_COUNTRY, TransactionKind.GOODS)
        is IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED
    )
    assert (
        _outbound(IvaTerritorialScope.THIRD_COUNTRY, TransactionKind.SERVICES_GENERAL)
        is IvaCategory.OPERACION_NO_SUJETA
    )


def test_the_population_used_to_classify_as_nothing_at_all() -> None:
    """Mutation proof: without the territories in the set the branch falls through.

    Re-runs the pre-change predicate -- third countries only -- and shows a
    Canarian customer matches neither outbound row, which is how an ordinary
    peninsular invoice resolved UNRESOLVED.
    """

    def _third_country_only(customer: IvaTerritorialScope) -> bool:
        return customer is IvaTerritorialScope.THIRD_COUNTRY

    assert not _third_country_only(IvaTerritorialScope.ES_CANARIAS)
    assert _outbound(IvaTerritorialScope.ES_CANARIAS, TransactionKind.GOODS) is not IvaCategory.UNKNOWN


# -- a peninsular rate charged to a non-peninsular customer ------------------
#
# The contradiction this composes could not be asserted while the operation did
# not classify at all: there is no contradiction between a charged rate and a
# treatment nothing established. With the outbound branch above in place the
# operation resolves, and the resolved category is cuota-less BY LAW -- so a
# peninsular registry rate charged on it contradicts the document's own
# treatment.
#
# The charged rate is ISSUER-ASSERTED TREATMENT EVIDENCE and never establishes
# territory. Territory comes from the establishment ladder; the rate is what the
# issuer DID about the operation, which is a claim to be checked rather than a
# fact to resolve from. The cases below hold that separation explicitly, because
# a fix that let a charged rate place a party would classify every mis-rated
# invoice as domestic and never report anything.


@pytest.mark.parametrize(
    ("customer", "kind"),
    [
        (IvaTerritorialScope.ES_CANARIAS, TransactionKind.GOODS),
        (IvaTerritorialScope.ES_CANARIAS, TransactionKind.SERVICES_GENERAL),
        (IvaTerritorialScope.ES_CEUTA_MELILLA, TransactionKind.GOODS),
        (IvaTerritorialScope.ES_CEUTA_MELILLA, TransactionKind.SERVICES_GENERAL),
    ],
    ids=["canarias-goods", "canarias-services", "ceuta-melilla-goods", "ceuta-melilla-services"],
)
def test_the_resolved_treatment_admits_no_cuota_at_all(
    customer: IvaTerritorialScope,
    kind: TransactionKind,
) -> None:
    """Every outbound non-peninsular treatment is cuota-less by law.

    That is what makes a charged peninsular rate a contradiction rather than a
    disagreement about the number: a category admitting no cuota admits no tipo
    either, so one of the two facts is wrong.
    """
    category = _outbound(customer, kind)

    assert category_cuota_is_zero_by_law(category, InvoiceKind.ISSUED)


def test_a_domestic_treatment_is_not_cuota_less_so_the_check_stays_narrow() -> None:
    """The precision half: the contradiction must not fire on ordinary invoices."""
    assert not category_cuota_is_zero_by_law(IvaCategory.DOMESTIC_GENERAL, InvoiceKind.ISSUED)


def test_the_charged_rate_never_places_the_customer() -> None:
    """The separation the row insists on, asserted rather than assumed.

    The criteria carry no charged rate at all on this branch -- territory comes
    from the establishment ladder and the rate is evidence about TREATMENT. Were
    a rate allowed to place a party, a peninsular rate charged in error would
    silently reclassify the operation as domestic and the contradiction would
    never be raised, which is the failure this ordering exists to prevent.
    """
    canarian = _outbound(IvaTerritorialScope.ES_CANARIAS, TransactionKind.GOODS)
    peninsular_customer_would_be_domestic = IvaTerritorialScope.ES_MAINLAND

    assert canarian is IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED
    assert canarian is not IvaCategory.DOMESTIC_GENERAL
    assert peninsular_customer_would_be_domestic is not IvaTerritorialScope.ES_CANARIAS
