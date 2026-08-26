"""Closed-table IVA classification (issuer / customer / kind / direction).

Layered on top of the :mod:`cadrumo.domain.iva` substrate (the
:class:`cadrumo.domain.iva.IvaCategory` enum, :class:`cadrumo.domain.iva.IvaRateRecord`
records, and :func:`cadrumo.domain.iva.lookup_rate`), this module adds the
classification axes needed to tag a transaction deterministically based on
the parties' tax residency, the customer's IVA status, the transaction kind,
and the invoice direction.

The resolver implementation is a closed first-match-wins decision table over
the rules ``R01`` through ``R99``. Each rule is a plain
:class:`typing.NamedTuple` carrying a stable identifier, a description and a
predicate; the table itself is a module-level constant. There is no dynamic
dispatch, no string expression evaluation, no caller-supplied callback —
every classification outcome is reproducible by replaying the same
:class:`IvaInvoiceClassificationCriteria`.

Examples:
    >>> from datetime import date
    >>> from . import (
    ...     IvaTerritorialScope,
    ...     CustomerTaxStatus,
    ...     EUMemberState,
    ...     IvaTerritorialScope,
    ...     InvoiceKind,
    ...     TransactionKind,
    ...     IvaRateKind,
    ...     IvaInvoiceClassificationCriteria,
    ...     classify_iva,
    ... )
    >>> criteria = IvaInvoiceClassificationCriteria(
    ...     transaction_date=date(2025, 6, 15),
    ...     issuer_residency=IvaTerritorialScope.ES_MAINLAND,
    ...     customer_residency=IvaTerritorialScope.EU_MEMBER,
    ...     customer_identification_state=EUMemberState.DE,
    ...     customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
    ...     kind=TransactionKind.GOODS,
    ...     direction=InvoiceKind.ISSUED,
    ... )
    >>> classify_iva(criteria).category
    <IvaCategory.INTRA_COMMUNITY_SUPPLY: 'intra_community_supply'>
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NamedTuple

from pydantic import Field, model_validator

from ...core.logging import get_logger
from ._lookup import lookup_rate
from ._schema import (
    EUMemberState,
    IvaArt69DosService,
    IvaCategory,
    IvaExemptionArticle,
    IvaRateKind,
    IvaRateRecord,
    IvaStrictFrozen,
)
from .errors import IvaRateNotFoundError, IvaValidationError

_logger = get_logger(__name__)


# -- Closed enumerations --------------------------------------------------


class IvaTerritorialScope(StrEnum):
    """Territorial-scope classification of an invoice party.

    Per Ley 37/1992 Art. 3.Dos and Arts. 68-72, the substrate segments
    parties by ``territorio de aplicación del impuesto`` and the
    ``lugar de realización`` rules rather than tax residency in the
    civil-law sense. The five values partition that territorial scope
    for both issuer and customer roles via field-name semantics
    (``issuer_residency: IvaTerritorialScope``,
    ``customer_residency: IvaTerritorialScope`` — the field name keeps
    the role label; the type carries the territorial framing). Parties
    in Canarias, Ceuta or Melilla are NOT subject to LIVA; the
    classifier short-circuits to
    :attr:`cadrumo.domain.iva.IvaCategory.DOMESTIC_NOT_SUBJECT` for issuers
    in those territories (out of TAI).

    Attributes:
        ES_MAINLAND: Spanish mainland and Balearic Islands (TAI).
        ES_CANARIAS: Canary Islands — IGIC territory, out of LIVA.
        ES_CEUTA_MELILLA: Ceuta and Melilla — IPSI territory, out of LIVA.
        EU_MEMBER: Any of the other 26 EU member states.
        THIRD_COUNTRY: Any non-EU jurisdiction.
    """

    ES_MAINLAND = "es_mainland"
    ES_CANARIAS = "es_canarias"
    ES_CEUTA_MELILLA = "es_ceuta_melilla"
    EU_MEMBER = "eu_member"
    THIRD_COUNTRY = "third_country"


class PartyFact(StrEnum):
    """The two legally distinct facts a rule may need about a party.

    They were one output before they were two, and the conflation had a
    direction. A printed foreign IVA prefix was read as decisive EVIDENCE OF
    PLACE, so a German-identified entity actually established in Spain resolved
    silently to :attr:`IvaTerritorialScope.EU_MEMBER` and fed the table as
    settled fact — while the mirror case, a non-resident holding a Spanish
    registration, was correctly refused. Every Member State registers
    non-residents on the same terms Spain does, so the two are one situation seen
    from two sides; splitting the fact restores the symmetry at the principle
    instead of patching it at one rung.

    Naming them lets a branch DECLARE which it consumes, so an operator is asked
    only for what the branch it lands on actually turns on. The domestic and
    territorial rules need the place and not the identification. The
    intra-community families need the identification, and need the place only
    narrowly beside it — not to say which Member State a party belongs to, which
    is the conflation, but to place the supply in the peninsula and keep the
    Spanish territories out of "otro Estado miembro". A row that reads a
    residency is not thereby reading it as a registration.

    Attributes:
        IVA_IDENTIFICATION_STATE: The Member State under whose IVA
            identification the party operates, carried as
            :class:`cadrumo.domain.iva.EUMemberState`. Registration evidence
            settles it decisively, because registration is precisely what it
            asserts.
        TERRITORIAL_ESTABLISHMENT: Where the party has its *sede de actividad
            económica* or an *establecimiento permanente* (Ley 37/1992
            arts. 69-70), carried as :class:`IvaTerritorialScope`. NO
            registration evidences it, foreign or Spanish.
    """

    IVA_IDENTIFICATION_STATE = "iva_identification_state"
    TERRITORIAL_ESTABLISHMENT = "territorial_establishment"


class InvoiceKind(StrEnum):
    """Whether the autónomo issued or received the invoice.

    Single canonical enum spanning both the substrate classifier
    (``IvaInvoiceClassificationCriteria.direction``) and ledger / invoice
    records (``Invoice.kind``). Replaces the prior split between
    ``InvoiceDirection`` (substrate) and :class:`InvoiceKind` (invoices)
    that carried identical semantics with mismatched lowercase / uppercase
    string values. Values are lowercase to align with TOML registry selectors
    (``invoice_direction = "issued"``).

    Attributes:
        ISSUED: The autónomo is the issuer (sale).
        RECEIVED: The autónomo is the recipient (purchase).
    """

    ISSUED = "issued"
    RECEIVED = "received"


class CustomerTaxStatus(StrEnum):
    """IVA-status classification of the customer.

    Classifier rules that depend on reverse-charge mechanics check
    :attr:`B2B_IVA_REGISTERED`, which requires a valid NIF-IVA on record.
    :attr:`UNKNOWN` is a sentinel for transactions whose counterparty status
    has not been resolved upstream.

    Attributes:
        B2B_IVA_REGISTERED: Business customer with a valid IVA-ID.
        B2B_NOT_REGISTERED: Business customer without an IVA-ID.
        B2C_CONSUMER: Private individual.
        PUBLIC_ADMINISTRATION: Public-sector body.
        UNKNOWN: Counterparty status unresolved.
    """

    B2B_IVA_REGISTERED = "b2b_iva_registered"
    B2B_NOT_REGISTERED = "b2b_not_registered"
    B2C_CONSUMER = "b2c_consumer"
    PUBLIC_ADMINISTRATION = "public_administration"
    UNKNOWN = "unknown"


class TransactionKind(StrEnum):
    """Kind-of-supply classification.

    Drives place-of-supply rules (services general vs. land-related vs. OSS),
    reverse-charge sub-rules (construction, waste, consumer electronics) and
    rate-tier defaulting (passenger transport at 10 %, restaurants at 10 %).
    Kind is orthogonal to rate tier;
    :attr:`IvaInvoiceClassificationCriteria.rate_tier` is the explicit rate-tier axis
    the caller supplies for ES-to-ES domestic rules.

    Attributes:
        GOODS: Tangible goods supply.
        SERVICES_GENERAL: Services not covered by a specialised category.
        SERVICES_LAND_RELATED: Land-related services (Art. 70).
        SERVICES_PASSENGER_TRANSPORT: Passenger transport service.
        SERVICES_RESTAURANT: Restaurant or catering service.
        IMMOVABLE_PROPERTY: Real-estate transaction.
        PASSENGER_CAR: Private-use passenger vehicle (deductibility flag).
        CONSTRUCTION_REVERSE_CHARGE: Art. 84.Uno.2º.f construction works.
        WASTE_REVERSE_CHARGE: Art. 84.Uno.2º.c waste / recovery materials.
        ELECTRONICS_REVERSE_CHARGE: Art. 84.Uno.2º.g B2B consumer electronics.
        EXTERNAL_SCHEME_SERVICES: Services from a non-EU taxable person to
            an EU-resident consumer routed through Esquema Exterior. LIVA
            art. 163 octiesdecies.
        OSS_UNION_GOODS_DISTANCE_SALE: Intra-community distance sale of
            goods routed through Esquema Unión. Admitted to the scheme by
            LIVA art. 163 unvicies; located as a supply of goods by art. 68.
        OSS_UNION_GOODS_INTERFACE_FACILITATED: Interior supply of goods
            facilitated by an electronic interface, routed through Esquema
            Unión. Admitted by LIVA art. 163 unvicies; located by art. 68.
        OSS_UNION_SERVICES: Services from an EU-established taxable person
            to a consumer in another Member State routed through Esquema
            Unión. Admitted by LIVA art. 163 unvicies; located as a supply of
            services by art. 69.

        IOSS_DISTANCE_SALE_LOW_VALUE: Distance sale of imported goods with
            intrinsic value at or below 150 EUR routed through Esquema de
            Importación (IOSS). LIVA art. 163 quinvicies.

    **Art. 163 unvicies admits an operation to the Union scheme; it does not say
    which limb the operation is.** Its own scope paragraph reaches "presten
    servicios" and "ventas a distancia intracomunitarias de bienes" alike, so
    citing it alone establishes neither. The three Union-scheme members above
    were previously documented as resting on it for their goods-or-services
    character, and two separate readers took that at face value and derived the
    wrong nature before going to the statute. What fixes the nature is the
    placement article: art. 68 for *entregas de bienes*, art. 69 for
    *prestaciones de servicios*.
    """

    GOODS = "goods"
    SERVICES_GENERAL = "services_general"
    SERVICES_LAND_RELATED = "services_land_related"
    SERVICES_PASSENGER_TRANSPORT = "services_passenger_transport"
    SERVICES_RESTAURANT = "services_restaurant"
    IMMOVABLE_PROPERTY = "immovable_property"
    PASSENGER_CAR = "passenger_car"
    CONSTRUCTION_REVERSE_CHARGE = "construction_reverse_charge"
    WASTE_REVERSE_CHARGE = "waste_reverse_charge"
    ELECTRONICS_REVERSE_CHARGE = "electronics_reverse_charge"
    EXTERNAL_SCHEME_SERVICES = "external_scheme_services"
    OSS_UNION_GOODS_DISTANCE_SALE = "oss_union_goods_distance_sale"
    OSS_UNION_GOODS_INTERFACE_FACILITATED = "oss_union_goods_interface_facilitated"
    OSS_UNION_SERVICES = "oss_union_services"
    IOSS_DISTANCE_SALE_LOW_VALUE = "ioss_distance_sale_low_value"


# -- Criteria and classification records ----------------------------------


#: Domestic kinds whose rate tier is a payload concern, not a classification axis.
#:
#: Rules ``R01`` through ``R03`` route the three dedicated reverse-charge kinds
#: to ``DOMESTIC_REVERSE_CHARGE`` before ``R05`` runs, and immovable property
#: likewise, so the tier never selects their category and demanding it would ask
#: for a fact no branch they can reach turns on.
_DOMESTIC_RATE_TIER_EXEMPT_KINDS: Final[frozenset[TransactionKind]] = frozenset(
    {
        TransactionKind.CONSTRUCTION_REVERSE_CHARGE,
        TransactionKind.WASTE_REVERSE_CHARGE,
        TransactionKind.ELECTRONICS_REVERSE_CHARGE,
        TransactionKind.IMMOVABLE_PROPERTY,
    },
)


def domestic_rate_tier_is_required(
    *,
    issuer_residency: IvaTerritorialScope,
    customer_residency: IvaTerritorialScope,
    kind: TransactionKind,
    customer_tax_status: CustomerTaxStatus | None = None,
    art_69_dos_service: IvaArt69DosService | None = None,
) -> bool:
    """Whether this operation reaches a rate-tier branch and so needs a tier.

    The single home of a condition two layers must agree on. The criteria model
    RAISES when it holds and no tier was supplied, and a producer assembling
    those criteria must be able to ask the same question BEFORE it builds them --
    otherwise the raise surfaces as an unclassifiable probe, and a caller that
    treats an unclassifiable probe as "this branch might need everything" then
    reports the wrong missing input entirely.

    That is not hypothetical: an ES-to-ES domestic operation with no readable
    tier was reported as missing the counterparty's IVA identification state, a
    fact the domestic branch provably does not consume, while the tier that
    actually blocked it was never named. Restating the condition in the producer
    would have fixed that instance and left the two free to drift; asking the
    same predicate cannot.

    Args:
        issuer_residency: Where the issuing party is established.
        customer_residency: Where the party billed is established.
        kind: The nature of the supply.
        customer_tax_status: The recipient's condition, where it is settled.
            ``None`` means it is still open, and an open status demands the tier
            rather than excusing it.
        art_69_dos_service: The lettered art. 69.Dos item, where one was stated.
            A stated item on a third-country recipient lifts the supply out of
            the TAI, so no Spanish rate applies and no tier is wanted.

    Returns:
        ``True`` when a tier must be supplied for the operation to classify.
    """
    if kind in _DOMESTIC_RATE_TIER_EXEMPT_KINDS:
        return False
    if issuer_residency is IvaTerritorialScope.ES_MAINLAND and customer_residency is IvaTerritorialScope.ES_MAINLAND:
        return True
    if art_69_dos_exception_applies(
        customer_residency=customer_residency,
        art_69_dos_service=art_69_dos_service,
    ):
        return False
    # Art. 69.Uno.2.º keeps a B2C service in the TAI when the supplier is
    # established here, so it is taxed at a Spanish rate exactly as a domestic
    # supply is -- and picking WHICH domestic category needs the tier just the
    # same. ``None`` demands it too: the status is still open, the operation may
    # yet land on this branch, and failing toward asking is the rule everywhere
    # else on this axis.
    return (
        issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and customer_residency in _OUTSIDE_THE_COMUNIDAD
        and kind is TransactionKind.SERVICES_GENERAL
        and (customer_tax_status is None or customer_tax_status is CustomerTaxStatus.B2C_CONSUMER)
    )


class IvaInvoiceClassificationCriteria(IvaStrictFrozen):
    """Input record for :func:`classify_iva`.

    Carries every axis the closed decision table inspects. The record is
    strict and frozen so it can be used as a dict key in upstream caches.

    **The two party facts are carried separately and are never derived from each
    other** (:class:`PartyFact`). The residency fields are the TERRITORIAL
    ESTABLISHMENT fact; the identification-state fields are the IVA
    IDENTIFICATION STATE fact. A party may hold a German identification while
    being established in Spain, or a Spanish one while established abroad — both
    are ordinary, and a model that could not express them forced the reader to
    pick one meaning for a value that had two.

    Attributes:
        transaction_date: When the supply takes place.
        issuer_residency: Where the issuer is ESTABLISHED — its sede or
            establecimiento permanente under Ley 37/1992 arts. 69-70. Never a
            statement about where it is registered. The field name keeps the
            role label; the type carries the territorial framing.
        customer_residency: The same for the customer.
        customer_tax_status: Customer's IVA status.
        kind: Kind of supply.
        direction: ``ISSUED`` or ``RECEIVED``.
        issuer_identification_state: The
            :class:`cadrumo.domain.iva.EUMemberState` under whose IVA
            identification the issuer operates, where established. Optional
            independently of :attr:`issuer_residency`: an EU establishment does
            not supply an identification and an identification does not supply
            an establishment, so demanding one because of the other would be the
            conflation :class:`PartyFact` exists to end. Branches that need it
            declare so, and the producer demands it only for those.
        customer_identification_state: The same for the customer.
        rate_tier: Explicit rate-tier axis for ES-to-ES domestic rules.
    """

    transaction_date: date = Field(description="When the supply takes place.")
    issuer_residency: IvaTerritorialScope = Field(description="Where the issuer is established (LIVA arts. 69-70).")
    customer_residency: IvaTerritorialScope = Field(
        description="Where the customer is established (LIVA arts. 69-70).",
    )
    customer_tax_status: CustomerTaxStatus = Field(description="Customer's IVA status.")
    kind: TransactionKind = Field(description="Kind of supply.")
    direction: InvoiceKind = Field(description="ISSUED or RECEIVED.")
    issuer_identification_state: EUMemberState | None = Field(
        default=None,
        description="Member State of the issuer's IVA identification; independent of its establishment.",
    )
    customer_identification_state: EUMemberState | None = Field(
        default=None,
        description="Member State of the customer's IVA identification; independent of its establishment.",
    )
    art_69_dos_service: IvaArt69DosService | None = Field(
        default=None,
        description=(
            "The lettered item of Ley 37/1992 art. 69.Dos this service is, "
            "stated by the operator. Absent by default, and absence is not "
            "evidence that no item applies: an unstated service stays taxed in "
            "the TAI rather than being lifted out of it on a fact nobody gave."
        ),
    )
    rate_tier: IvaRateKind | None = Field(
        default=None,
        description=(
            "Explicit rate-tier axis the caller resolves at invoice "
            "generation time (e.g. ``GENERAL`` for 21 % goods, "
            "``REDUCED`` for restaurants, ``SUPER_REDUCED`` for basic "
            "food). The classifier consults it for ES-to-ES domestic "
            "rules to pick between ``DOMESTIC_GENERAL`` / "
            "``DOMESTIC_REDUCED`` / ``DOMESTIC_SUPER_REDUCED`` / "
            "``DOMESTIC_ZERO``. Ignored for non-domestic rules."
        ),
    )

    @model_validator(mode="after")
    def _validate_member_state_consistency(self) -> IvaInvoiceClassificationCriteria:
        """Enforce the rate-tier invariant.

        **An EU establishment no longer demands an identification state**, and
        the removal is the substance of the split rather than a relaxation. That
        check read "this party is established in another Member State, so name
        the State it is registered in", which is only sound while the two facts
        are one — it is exactly the inference that made a German prefix
        establish a German place. Which branches genuinely need the
        identification is now declared by the branches themselves
        (:attr:`_IvaClassificationRule.consumes`), so the demand is made where
        the law makes it and nowhere else. The field stays optional here because
        an unestablished identification is a normal reading outcome, and the
        producer refuses ahead of the table when a consuming branch needs one.

        One check remains, raising :exc:`IvaValidationError` on violation:

        * ES-to-ES domestic transactions (both residencies ``ES_MAINLAND``)
          that would fall through to the ``R05`` ``DOMESTIC_*`` rule require
          an explicit :attr:`rate_tier`. The classifier never silently
          defaults to ``GENERAL``; the caller must supply the tier that
          applied at invoice time. Dedicated reverse-charge
          :class:`TransactionKind` values (``CONSTRUCTION``, ``WASTE``,
          ``ELECTRONICS``) are exempted because rules ``R01`` through ``R03``
          route them to :attr:`cadrumo.domain.iva.IvaCategory.DOMESTIC_REVERSE_CHARGE`
          before ``R05`` runs, so their rate tier is a payload concern not a
          classification axis.
        """
        if (
            domestic_rate_tier_is_required(
                issuer_residency=self.issuer_residency,
                customer_residency=self.customer_residency,
                kind=self.kind,
                customer_tax_status=self.customer_tax_status,
                art_69_dos_service=self.art_69_dos_service,
            )
            and self.rate_tier is None
        ):
            raise IvaValidationError(
                "rate_tier is required for operations taxed at a Spanish rate: ES-to-ES domestic, "
                "and a B2C service outside the Comunidad, which LIVA art. 69.Uno.2.º keeps in the TAI. "
                "Supply GENERAL / REDUCED / SUPER_REDUCED / ZERO / EXEMPT explicitly",
            )
        return self


class IvaClassificationResult(IvaStrictFrozen):
    """Output record returned by :func:`classify_iva`.

    Exposes the matched :class:`cadrumo.domain.iva.IvaCategory`, the resolved
    :class:`cadrumo.domain.iva.IvaRateRecord` (or ``None`` for rate-irrelevant
    categories), a reverse-charge flag, the matched rule identifier, and any
    free-form note the resolver emits (typically used for fall-through
    documentation).

    Attributes:
        category: Resolved IVA category.
        rate: Applicable :class:`cadrumo.domain.iva.IvaRateRecord`, when relevant.
        requires_reverse_charge: ``True`` when the rule triggers
            *inversión del sujeto pasivo*.
        matched_rule_id: Stable rule identifier (e.g.
            ``R10_intra_community_supply``).
        notes: Free-form explanatory note.
        consumes_party_facts: Which :class:`PartyFact` values the matched branch
            actually turns on. This is how a producer assembling the criteria
            learns what to demand without holding a second copy of the law: it
            asks the table which facts the branch consumes rather than
            hand-writing a rule about the territorial scopes, which is the
            duplication the lazy-requirement mechanism already refuses
            elsewhere. Defaults to BOTH facts, so a row or result that forgets
            to declare demands everything — the fail-toward-asking direction,
            and the one where forgetting costs a question rather than a silent
            classification on a fact nobody supplied.
    """

    category: IvaCategory = Field(description="Resolved IVA category.")
    rate: IvaRateRecord | None = Field(default=None, description="Applicable :class:`IvaRateRecord`, when relevant.")
    requires_reverse_charge: bool = Field(default=False, description="True ⇒ inversión del sujeto pasivo.")
    matched_rule_id: str = Field(description="Stable rule id (e.g. ``R10_intra_community_supply``).")
    notes: str = Field(default="", description="Free-form explanatory note.")
    consumes_party_facts: frozenset[PartyFact] = Field(
        default=frozenset(PartyFact),
        description="Which :class:`PartyFact` values the matched branch turns on.",
    )
    exemption_article: IvaExemptionArticle | None = Field(
        default=None,
        description=(
            "Optional Ley 37/1992 Art. 20 sub-article discriminator. Stamped"
            " only when ``category`` is :attr:`IvaCategory.DOMESTIC_EXEMPT`"
            " and the classification chain (or operator) has determined the"
            " specific sub-article. It adds classification context without"
            " creating a separate Modelo 303 route."
        ),
    )

    @model_validator(mode="after")
    def _exemption_article_consistent_with_category(self) -> IvaClassificationResult:
        if self.exemption_article is not None and self.category is not IvaCategory.DOMESTIC_EXEMPT:
            raise IvaValidationError(
                f"exemption_article {self.exemption_article.value!r} is only valid when "
                f"category is DOMESTIC_EXEMPT; got category {self.category.value!r}",
            )
        return self


# -- Predicate-driven decision table --------------------------------------


def _is_es(residency: IvaTerritorialScope) -> bool:
    """Return ``True`` when ``residency`` is mainland Spain (TAI)."""
    return residency is IvaTerritorialScope.ES_MAINLAND


def _r01_construction_rc(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match ES-to-ES construction reverse-charge under Art. 84.Uno.2º.f."""
    return (
        _is_es(criteria.issuer_residency)
        and _is_es(criteria.customer_residency)
        and criteria.customer_tax_status
        in {
            CustomerTaxStatus.B2B_IVA_REGISTERED,
            CustomerTaxStatus.B2B_NOT_REGISTERED,
            CustomerTaxStatus.PUBLIC_ADMINISTRATION,
        }
        and criteria.kind is TransactionKind.CONSTRUCTION_REVERSE_CHARGE
    )


def _r02_waste_rc(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match ES-to-ES waste / recovery reverse-charge under Art. 84.Uno.2º.c."""
    return (
        _is_es(criteria.issuer_residency)
        and _is_es(criteria.customer_residency)
        and criteria.customer_tax_status
        in {
            CustomerTaxStatus.B2B_IVA_REGISTERED,
            CustomerTaxStatus.B2B_NOT_REGISTERED,
            CustomerTaxStatus.PUBLIC_ADMINISTRATION,
        }
        and criteria.kind is TransactionKind.WASTE_REVERSE_CHARGE
    )


def _r03_electronics_rc(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match ES-to-ES B2B consumer-electronics reverse-charge under Art. 84.Uno.2º.g."""
    return (
        _is_es(criteria.issuer_residency)
        and _is_es(criteria.customer_residency)
        and criteria.customer_tax_status is CustomerTaxStatus.B2B_IVA_REGISTERED
        and criteria.kind is TransactionKind.ELECTRONICS_REVERSE_CHARGE
    )


def _r04_immovable_b2c_exempt(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match ES-to-ES second-and-later immovable supplies (Art. 20.Uno.22º exempt)."""
    return (
        _is_es(criteria.issuer_residency)
        and _is_es(criteria.customer_residency)
        and criteria.customer_tax_status in {CustomerTaxStatus.B2C_CONSUMER, CustomerTaxStatus.PUBLIC_ADMINISTRATION}
        and criteria.kind is TransactionKind.IMMOVABLE_PROPERTY
    )


def _r05_domestic_at_rate(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match the ES-to-ES default; downstream picks a domestic category from ``rate_tier``."""
    return (
        _is_es(criteria.issuer_residency)
        and _is_es(criteria.customer_residency)
        and criteria.kind
        not in {
            TransactionKind.CONSTRUCTION_REVERSE_CHARGE,
            TransactionKind.WASTE_REVERSE_CHARGE,
            TransactionKind.ELECTRONICS_REVERSE_CHARGE,
        }
    )


def _identified_in_another_member_state(state: EUMemberState | None) -> bool:
    """Whether a party holds an IVA identification assigned by a State other than Spain.

    The literal condition art. 25.Uno places on the acquirer — "que disponga de un
    número de identificación a efectos del Impuesto sobre el Valor Añadido
    asignado por un Estado miembro distinto del Reino de España" — and the same
    condition the received leg places on the transmitting party.

    ``None`` is a refusal and not a permissive default: nothing established which
    State identifies the party, and reading that silence as "somewhere in the
    Union" would relieve a taxable supply on a condition the statute states
    explicitly and nobody checked. :attr:`EUMemberState.ES` is refused because
    the statute names Spain as the excluded State.
    """
    return state is not None and state is not EUMemberState.ES


def _r10_ic_supply_goods(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an intra-community B2B goods supply out of the peninsula (Art. 25 exempt).

    **The acquirer's condition is its REGISTRATION, not its place.** Art. 25.Uno
    exempts on the acquirer holding an IVA identification assigned by another
    Member State, and says nothing about where it has its sede — which arts. 69-70
    govern and which this row therefore does not read of the customer. Keyed on
    establishment instead, this row silently dropped every acquirer buying under a
    Member State's number from outside the Union, sending a legitimate entrega
    intracomunitaria exenta to the export row and off the declaración
    recapitulativa.

    What the customer's establishment still does here is exclude the Spanish
    territories, because art. 25 requires the goods be transported "al territorio
    de otro Estado miembro" and Canarias, Ceuta and Melilla are not that.
    """
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency not in _SPANISH_SCOPES
        and _identified_in_another_member_state(criteria.customer_identification_state)
        and criteria.customer_tax_status is CustomerTaxStatus.B2B_IVA_REGISTERED
        and criteria.kind is TransactionKind.GOODS
        and criteria.direction is InvoiceKind.ISSUED
    )


def _r11_ic_acquisition_goods(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an intra-community B2B goods acquisition into the peninsula (Art. 13 + reverse charge).

    The mirror of :func:`_r10_ic_supply_goods`, and keyed the same way for the
    same reason: what makes the operation an adquisición intracomunitaria is the
    transmitting party supplying under another Member State's identification, not
    where it keeps its sede. Its establishment is read only to exclude the
    Spanish territories, which supply into the peninsula under IGIC or IPSI rules
    rather than through art. 13.
    """
    return (
        criteria.issuer_residency not in _SPANISH_SCOPES
        and _identified_in_another_member_state(criteria.issuer_identification_state)
        and criteria.customer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_tax_status is CustomerTaxStatus.B2B_IVA_REGISTERED
        and criteria.kind is TransactionKind.GOODS
        and criteria.direction is InvoiceKind.RECEIVED
    )


def _r12_services_b2b_eu_outbound(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an ES to EU_MEMBER B2B services supply (Art. 69, place of supply at destination).

    **The services pair keeps the establishment and ADDS the identification**,
    which is the asymmetry against the goods pair above rather than an
    inconsistency with it. Art. 69.Uno.1.o locates a B2B service where the
    recipient has its sede or establecimiento permanente, so the place is the
    statutory condition here and no registration can supply it. The
    identification is what makes the located operation a REPORTABLE
    intra-community service: the category this row assigns selects a Modelo 349
    clave against the counterparty's NIF-IVA, so assigning it to a counterparty
    with no identifying State would file a line VIES cannot match.
    """
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency is IvaTerritorialScope.EU_MEMBER
        and _identified_in_another_member_state(criteria.customer_identification_state)
        and criteria.customer_tax_status is CustomerTaxStatus.B2B_IVA_REGISTERED
        and criteria.kind is TransactionKind.SERVICES_GENERAL
        and criteria.direction is InvoiceKind.ISSUED
    )


def _r13_services_b2b_eu_inbound(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an EU_MEMBER to ES B2B services supply (Art. 84.Uno.2º.a reverse charge at ES).

    Establishment and identification on the same split as
    :func:`_r12_services_b2b_eu_outbound`: art. 84.Uno.2.o.a turns the recipient
    into the sujeto pasivo because the supplier is not established in the TAI,
    and the supplier's identifying State is what files the resulting operation
    under the Modelo 349 services clave.
    """
    return (
        criteria.issuer_residency is IvaTerritorialScope.EU_MEMBER
        and _identified_in_another_member_state(criteria.issuer_identification_state)
        and criteria.customer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_tax_status is CustomerTaxStatus.B2B_IVA_REGISTERED
        and criteria.kind is TransactionKind.SERVICES_GENERAL
        and criteria.direction is InvoiceKind.RECEIVED
    )


def _r15_distance_sales_b2c_outbound(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an ES to EU_MEMBER B2C distance-sales supply (caller enforces threshold)."""
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency is IvaTerritorialScope.EU_MEMBER
        and criteria.customer_tax_status is CustomerTaxStatus.B2C_CONSUMER
        and criteria.kind is TransactionKind.GOODS
        and criteria.direction is InvoiceKind.ISSUED
    )


def _r16_external_scheme_services(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match a THIRD_COUNTRY to EU_MEMBER B2C service routed through Esquema Exterior (LIVA art. 163 octiesdecies)."""
    return (
        criteria.issuer_residency is IvaTerritorialScope.THIRD_COUNTRY
        and criteria.customer_residency is IvaTerritorialScope.EU_MEMBER
        and criteria.customer_tax_status is CustomerTaxStatus.B2C_CONSUMER
        and criteria.kind is TransactionKind.EXTERNAL_SCHEME_SERVICES
        and criteria.direction is InvoiceKind.ISSUED
    )


def _r17_oss_union_goods_distance_sale(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an ES to EU_MEMBER B2C OSS-Unión goods distance sale (LIVA art. 163 unvicies)."""
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency is IvaTerritorialScope.EU_MEMBER
        and criteria.customer_tax_status is CustomerTaxStatus.B2C_CONSUMER
        and criteria.kind is TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE
        and criteria.direction is InvoiceKind.ISSUED
    )


def _r18_oss_union_goods_interface_facilitated(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match ES to EU_MEMBER B2C OSS-Unión interface-facilitated goods."""
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency is IvaTerritorialScope.EU_MEMBER
        and criteria.customer_tax_status is CustomerTaxStatus.B2C_CONSUMER
        and criteria.kind is TransactionKind.OSS_UNION_GOODS_INTERFACE_FACILITATED
        and criteria.direction is InvoiceKind.ISSUED
    )


def _r19_oss_union_services(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an ES to EU_MEMBER B2C OSS-Unión services supply (LIVA art. 163 unvicies)."""
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency is IvaTerritorialScope.EU_MEMBER
        and criteria.customer_tax_status is CustomerTaxStatus.B2C_CONSUMER
        and criteria.kind is TransactionKind.OSS_UNION_SERVICES
        and criteria.direction is InvoiceKind.ISSUED
    )


#: The customer-side territories LIVA art. 3 places outside the Comunidad.
#:
#: Read from the law's own definitional chain rather than assembled by judgement.
#: Art. 3.Dos.1 excludes from "Estado miembro" / "interior del país" both Ceuta
#: y Melilla -- "en cuanto territorios no comprendidos en la Unión Aduanera" --
#: and, on separate grounds, Canarias. Art. 3.Dos.2 then defines "Comunidad" as
#: the set of territories that DO constitute "interior del país", and art.
#: 3.Dos.3 defines "territorio tercero" as "cualquier territorio distinto de los
#: definidos como interior del país". All three are therefore third territories,
#: and art. 21 -- which exempts "las entregas de bienes expedidos o transportados
#: fuera de la Comunidad" -- reaches them.
#:
#: The two exclusions differ in their REASON and coincide in their effect here:
#: Ceuta and Melilla sit outside the customs union while Canarias does not, which
#: separates them for customs and not for this axis. Collapsing them into one set
#: is therefore correct for IVA and would be wrong for a customs question.
#:
#: Without this a mainland business invoicing a Canarian customer -- an ordinary
#: operation, not an edge -- matched no row at all and resolved UNRESOLVED.
_OUTSIDE_THE_COMUNIDAD: Final[frozenset[IvaTerritorialScope]] = frozenset(
    {
        IvaTerritorialScope.THIRD_COUNTRY,
        IvaTerritorialScope.ES_CANARIAS,
        IvaTerritorialScope.ES_CEUTA_MELILLA,
    },
)


def _r20_export_goods(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an ES goods export outside the Comunidad (Art. 21, exención plena).

    Reaches the non-peninsular Spanish territories as well as third countries,
    because art. 3 places all three outside the Comunidad; see
    :data:`_OUTSIDE_THE_COMUNIDAD` for the definitional chain.
    """
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency in _OUTSIDE_THE_COMUNIDAD
        and criteria.kind is TransactionKind.GOODS
        and criteria.direction is InvoiceKind.ISSUED
    )


def _r21_import_goods(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match a THIRD_COUNTRY to ES goods import (Art. 18)."""
    return (
        criteria.issuer_residency is IvaTerritorialScope.THIRD_COUNTRY
        and criteria.customer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.kind is TransactionKind.GOODS
        and criteria.direction is InvoiceKind.RECEIVED
    )


#: The condition art. 69.Uno.1.º places on the recipient: "que el destinatario
#: sea un empresario o profesional que actúe como tal".
#:
#: Registration is NOT what the article asks for, so an unregistered business is
#: squarely inside it. ``PUBLIC_ADMINISTRATION`` is deliberately outside: art.
#: 69.Tres.4.º treats a legal person holding an IVA identification as an
#: empresario for these rules even when it does not act as one, and ruling on
#: that needs its own grounding. ``UNKNOWN`` is outside because it is the
#: absence of the fact, and an absence cannot satisfy a condition.
_EMPRESARIO_O_PROFESIONAL: Final[frozenset[CustomerTaxStatus]] = frozenset(
    {
        CustomerTaxStatus.B2B_IVA_REGISTERED,
        CustomerTaxStatus.B2B_NOT_REGISTERED,
    },
)


def _r22_services_outbound_b2b(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match a B2B services supply localised outside the TAI (Art. 69.Uno.1.º).

    Goods and services FORK here, which is why this stays a separate row rather
    than sharing art. 21's: that article exempts *entregas de bienes* only. A
    service to a business established outside the TAI is localised there by
    arts. 69 and 70, so it is NOT SUBJECT here rather than exempt -- a different
    outcome with a different Modelo 303 consequence.

    **The recipient's CONDITION is half the rule, not a refinement of it.**
    Art. 69.Uno.1.º places the supply at the recipient only when that recipient
    is an *empresario o profesional que actúe como tal*; 69.Uno.2.º places a B2C
    supply at the SUPPLIER instead, which for a mainland issuer is the TAI. This
    row read establishment alone and sent both limbs here, so every B2C service
    outside the Comunidad was booked not-subject -- an under-declaration in the
    ordinary case rather than an edge.
    """
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency in _OUTSIDE_THE_COMUNIDAD
        and criteria.customer_tax_status in _EMPRESARIO_O_PROFESIONAL
        and criteria.kind is TransactionKind.SERVICES_GENERAL
        and criteria.direction is InvoiceKind.ISSUED
    )


def _is_outbound_b2c_service(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """The shape both art. 69 B2C rows share, before the exception splits them."""
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency in _OUTSIDE_THE_COMUNIDAD
        and criteria.customer_tax_status is CustomerTaxStatus.B2C_CONSUMER
        and criteria.kind is TransactionKind.SERVICES_GENERAL
        and criteria.direction is InvoiceKind.ISSUED
    )


def art_69_dos_exception_applies(
    *,
    customer_residency: IvaTerritorialScope,
    art_69_dos_service: IvaArt69DosService | None,
) -> bool:
    """Whether art. 69.Dos lifts a B2C service out of the TAI.

    The single home of the exception's own two conditions, so the classification
    rows and the rate-tier demand cannot answer it differently.

    The recipient test is ``THIRD_COUNTRY`` and nothing else, and that is the
    statute's own arithmetic rather than a simplification: art. 69.Dos excepts a
    recipient established "fuera de la Comunidad", then limits itself in the same
    sentence -- "salvo en el caso de que dicho destinatario esté establecido o
    tenga su domicilio o residencia habitual en las Islas Canarias, Ceuta o
    Melilla". Those territories are outside the Comunidad and expressly outside
    the exception, so what remains is a third country.

    An absent item does not satisfy it. Nobody having stated which lettered
    service applies is not evidence that none does, and reading it that way would
    lift a supply out of Spanish IVA on a fact nobody supplied.

    Args:
        customer_residency: Where the recipient is established.
        art_69_dos_service: The lettered item the operator stated, or ``None``.

    Returns:
        ``True`` when the supply is not realizada en el TAI under art. 69.Dos.
    """
    return art_69_dos_service is not None and customer_residency is IvaTerritorialScope.THIRD_COUNTRY


def _r24_services_outbound_b2c(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match a B2C services supply the TAI keeps (Art. 69.Uno.2.º).

    The other limb of the same article, and it lands in the opposite place: a
    service to someone who is not an empresario o profesional is realizada where
    the SUPPLIER is established, so a mainland issuer's B2C service is inside the
    TAI and taxed at its Spanish rate. Downstream picks the domestic category
    from ``rate_tier``, exactly as the ES-to-ES default does, because a supply
    located here is taxed here on the same terms.

    Everything art. 69.Dos does not except lands here, including a recipient in
    Canarias, Ceuta or Melilla whose service IS on that list -- the paragraph
    names those three territories back out of its own exception.
    """
    return _is_outbound_b2c_service(criteria) and not art_69_dos_exception_applies(
        customer_residency=criteria.customer_residency,
        art_69_dos_service=criteria.art_69_dos_service,
    )


def _r25_services_outbound_b2c_art_69_dos(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match the B2C services art. 69.Dos lifts back out of the TAI.

    Twelve lettered items -- derechos de autor, publicidad, asesoramiento,
    tratamiento de datos, traducción, seguro, cesión de personal, arrendamiento
    de bienes muebles corporales and the rest -- excepted from art. 69.Uno.2.º
    when the recipient is established in a third country.

    **The operator states the item and nothing reads it off the page.** The list
    is a closed vocabulary the statute fixes, which is the only reason it can be
    consulted at all. Deciding which letter an invoice falls under from its own
    prose would be the rule-table-as-model this domain refuses by name.
    """
    return _is_outbound_b2c_service(criteria) and art_69_dos_exception_applies(
        customer_residency=criteria.customer_residency,
        art_69_dos_service=criteria.art_69_dos_service,
    )


def _r23_ioss_distance_sale_low_value(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match a low-value imported-goods distance sale routed through IOSS (LIVA art. 163 quinvicies)."""
    return (
        criteria.customer_residency is IvaTerritorialScope.EU_MEMBER
        and criteria.customer_tax_status is CustomerTaxStatus.B2C_CONSUMER
        and criteria.kind is TransactionKind.IOSS_DISTANCE_SALE_LOW_VALUE
        and criteria.direction is InvoiceKind.ISSUED
    )


def _r30_canarias_ceuta_melilla(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match issuers based in Canarias / Ceuta / Melilla (out of TAI)."""
    return criteria.issuer_residency in {
        IvaTerritorialScope.ES_CANARIAS,
        IvaTerritorialScope.ES_CEUTA_MELILLA,
    }


_RATE_TIER_TO_CATEGORY: dict[IvaRateKind, IvaCategory] = {
    IvaRateKind.GENERAL: IvaCategory.DOMESTIC_GENERAL,
    IvaRateKind.REDUCED: IvaCategory.DOMESTIC_REDUCED,
    IvaRateKind.SUPER_REDUCED: IvaCategory.DOMESTIC_SUPER_REDUCED,
    IvaRateKind.ZERO: IvaCategory.DOMESTIC_ZERO,
    IvaRateKind.EXEMPT: IvaCategory.DOMESTIC_EXEMPT,
}


_CATEGORY_TO_RATE_TIER: dict[IvaCategory, IvaRateKind] = {
    category: tier for tier, category in _RATE_TIER_TO_CATEGORY.items()
}


def domestic_categories_by_rate_kind() -> Mapping[IvaRateKind, IvaCategory]:
    """Return the closed rate-kind to domestic-category mapping.

    The single authority for "which DOMESTIC_* category does this rate tier
    denote". Exposed as a read-only view so a cross-package consumer reaches it
    through the package facade rather than re-declaring the table; three
    independent copies of this mapping existed before it was promoted, none
    sharing an identifier with another, so no symbol search would have found
    them.

    Callers needing the reverse direction want
    :func:`rate_kind_for_domestic_category`. Callers needing "which rate kinds
    exist" should iterate :class:`IvaRateKind` itself — using this mapping's
    key set for that is the conflation that let one copy drift a member short.
    """
    return MappingProxyType(_RATE_TIER_TO_CATEGORY)


def rate_kind_for_domestic_category(category: IvaCategory) -> IvaRateKind | None:
    """Return the rate tier a domestic category denotes, or ``None`` if it is not one.

    ``None`` is the honest answer for every non-domestic category —
    intra-community, export, import, reverse-charge and recargo operations
    carry no rate tier derivable from the category alone.
    """
    return _CATEGORY_TO_RATE_TIER.get(category)


class _IvaClassificationRule(NamedTuple):
    """Module-private decision-table row.

    Attributes:
        rule_id: Stable string identifier (e.g. ``R10_intra_community_supply``).
        description: Human-readable summary surfaced as
            :attr:`IvaClassificationResult.notes`.
        predicate: Predicate over a :class:`IvaInvoiceClassificationCriteria`.
        category: Concrete :class:`cadrumo.domain.iva.IvaCategory` to assign on a
            match, or ``None`` when the resolver derives the category from
            other inputs (used by ``R05`` against
            :attr:`IvaInvoiceClassificationCriteria.rate_tier`).
        consumes: The :class:`PartyFact` values this branch turns on, declared
            per row so a producer can demand exactly them and nothing more.
            **The declaration is a claim about the predicate, and the predicate
            is what must honour it** — the two disagreed once, with all four
            intra-community rows declaring the identification while no predicate
            in the table read either identification field, so the declaration
            read as evidence of a migration that had not happened.

            Every row consumes :attr:`PartyFact.TERRITORIAL_ESTABLISHMENT`,
            because every predicate reads at least one residency. Only the
            intra-community rows add
            :attr:`PartyFact.IVA_IDENTIFICATION_STATE`, and they read it: the
            goods pair because arts. 25 and 13 make the counterparty's
            registration in another Member State the operative condition, the
            services pair because their categories select a Modelo 349 clave
            against that counterparty's NIF-IVA. Everywhere else the identifying
            State cannot change the outcome and is not declared.
    """

    rule_id: str
    description: str
    predicate: Callable[[IvaInvoiceClassificationCriteria], bool]
    category: IvaCategory | None  # None ⇒ rule resolves to a derived category
    consumes: frozenset[PartyFact]


_SPANISH_SCOPES: Final[frozenset[IvaTerritorialScope]] = frozenset(
    {
        IvaTerritorialScope.ES_MAINLAND,
        IvaTerritorialScope.ES_CANARIAS,
        IvaTerritorialScope.ES_CEUTA_MELILLA,
    },
)
"""The establishments the Spanish rate schedule can price a supply for."""


_ESTABLISHMENT_ONLY: Final[frozenset[PartyFact]] = frozenset({PartyFact.TERRITORIAL_ESTABLISHMENT})
"""What a branch consumes when the identification State cannot change its outcome."""

_ESTABLISHMENT_AND_IDENTIFICATION: Final[frozenset[PartyFact]] = frozenset(PartyFact)
"""What an intra-community branch consumes: the place AND the identifying State."""


_CLASSIFICATION_RULES: tuple[_IvaClassificationRule, ...] = (
    _IvaClassificationRule(
        "R01_construction_reverse_charge",
        "ES-to-ES construction RC",
        _r01_construction_rc,
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R02_waste_reverse_charge",
        "ES-to-ES waste RC",
        _r02_waste_rc,
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R03_electronics_reverse_charge",
        "ES-to-ES B2B electronics RC",
        _r03_electronics_rc,
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R04_immovable_property_exempt",
        "ES-to-ES immovable B2C exempt",
        _r04_immovable_b2c_exempt,
        IvaCategory.DOMESTIC_EXEMPT,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R05_domestic_at_rate_tier",
        "ES-to-ES default by rate_tier",
        _r05_domestic_at_rate,
        None,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R10_intra_community_supply",
        "ES to EU_MEMBER B2B goods supply",
        _r10_ic_supply_goods,
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        consumes=_ESTABLISHMENT_AND_IDENTIFICATION,
    ),
    _IvaClassificationRule(
        "R11_intra_community_acquisition",
        "EU_MEMBER to ES B2B goods acquisition",
        _r11_ic_acquisition_goods,
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        consumes=_ESTABLISHMENT_AND_IDENTIFICATION,
    ),
    _IvaClassificationRule(
        "R12_services_b2b_eu_outbound",
        "ES to EU_MEMBER B2B services",
        _r12_services_b2b_eu_outbound,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
        consumes=_ESTABLISHMENT_AND_IDENTIFICATION,
    ),
    # A service received resolves to the SERVICES category, not the goods one,
    # because the two surfaces need different things from it. Modelo 303
    # combines the legs — official boxes 10/11 and 36/37 are titled
    # "adquisiciones intracomunitarias de bienes y servicios" — so both
    # categories select the same bindings and either would settle correctly
    # there. Modelo 349 keeps them apart: `_intracommunity_clave` files the
    # goods category under clave "A" (adquisiciones intracomunitarias sujetas)
    # and this one under clave "I" (adquisiciones intracomunitarias de
    # servicios), so resolving a service to the goods category would declare it
    # as an adquisición de bienes against VIES.
    #
    # The services category may only be emitted here because the M303 bindings
    # select it; before they did, this rule resolving to it would have routed
    # the cuota to no casilla at all.
    _IvaClassificationRule(
        "R13_services_b2b_eu_inbound",
        "EU_MEMBER to ES B2B services",
        _r13_services_b2b_eu_inbound,
        IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
        consumes=_ESTABLISHMENT_AND_IDENTIFICATION,
    ),
    _IvaClassificationRule(
        "R15_distance_sales_b2c",
        "ES to EU_MEMBER B2C distance sales",
        _r15_distance_sales_b2c_outbound,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R16_external_scheme_services",
        "3rd-country to EU_MEMBER B2C services routed through Esquema Exterior",
        _r16_external_scheme_services,
        IvaCategory.OPERACION_NO_SUJETA,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R17_oss_union_goods_distance_sale",
        "ES to EU_MEMBER B2C OSS-Union goods distance sale",
        _r17_oss_union_goods_distance_sale,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R18_oss_union_goods_interface_facilitated",
        "ES to EU_MEMBER B2C OSS-Union interface-facilitated supply",
        _r18_oss_union_goods_interface_facilitated,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R19_oss_union_services",
        "ES to EU_MEMBER B2C OSS-Union services",
        _r19_oss_union_services,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R20_export_goods",
        "ES goods export outside the Comunidad",
        _r20_export_goods,
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R21_import_goods",
        "3rd-country to ES goods import",
        _r21_import_goods,
        IvaCategory.IMPORT_THIRD_COUNTRY,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R22_services_outbound_b2b",
        "ES B2B services localised outside the TAI",
        _r22_services_outbound_b2b,
        IvaCategory.OPERACION_NO_SUJETA,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R25_services_outbound_b2c_art_69_dos",
        "ES B2C services art. 69.Dos lifts out of the TAI",
        _r25_services_outbound_b2c_art_69_dos,
        IvaCategory.OPERACION_NO_SUJETA,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R24_services_outbound_b2c_at_rate_tier",
        "ES B2C services the TAI keeps, by rate_tier",
        _r24_services_outbound_b2c,
        None,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R23_ioss_distance_sale_low_value",
        "Low-value imported-goods distance sale routed through IOSS",
        _r23_ioss_distance_sale_low_value,
        IvaCategory.OPERACION_NO_SUJETA,
        consumes=_ESTABLISHMENT_ONLY,
    ),
    _IvaClassificationRule(
        "R30_canarias_ceuta_melilla",
        "Issuer outside TAI",
        _r30_canarias_ceuta_melilla,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
        consumes=_ESTABLISHMENT_ONLY,
    ),
)


_R99_FALLTHROUGH_ID = "R99_fallthrough"


# -- Public resolver ------------------------------------------------------


def classifiable_categories(*, consuming: PartyFact | None = None) -> frozenset[IvaCategory]:
    """Return the categories the decision table can mint, optionally narrowed by fact.

    Answers what the closed rule table declares, without publishing the table
    itself: the rows are an implementation detail whose shape is free to
    change, while "which categories can this table produce, and which of them
    turn on a given :class:`PartyFact`" is a stable question a consumer outside
    the domain legitimately asks.

    The narrowed form exists for the reporting-parity direction: a category
    cannot enter a Modelo 349 reported population without its minting branch
    declaring that it consumes the counterparty's identifying State, or the
    producer silently stops demanding an identification for an operation that
    files one.

    Excludes the ``R05`` domestic-by-rate-tier row, whose category is derived
    from the criteria rather than declared, and the ``R99`` fallthrough, which
    is not a rule row at all.

    Args:
        consuming: When given, restrict the answer to the categories whose
            minting branch declares it reads this fact. ``None`` returns every
            declared category.

    Returns:
        The matching :class:`cadrumo.domain.iva.IvaCategory` members.
    """
    return frozenset(
        rule.category
        for rule in _CLASSIFICATION_RULES
        if rule.category is not None and (consuming is None or consuming in rule.consumes)
    )


def classify_iva(criteria: IvaInvoiceClassificationCriteria) -> IvaClassificationResult:
    """Apply the closed decision table; first match wins.

    Iterates the module-level rule table in declaration order, returning the
    first :class:`IvaClassificationResult` whose predicate accepts ``criteria``.
    Falls through to the ``R99`` sentinel
    (:attr:`cadrumo.domain.iva.IvaCategory.UNKNOWN`) only when no rule matches —
    a state that requires human review per the
    :class:`cadrumo.domain.iva.IvaCategory.UNKNOWN` contract.

    Args:
        criteria: The :class:`IvaInvoiceClassificationCriteria` carrying every
            classification axis.

    Returns:
        A :class:`IvaClassificationResult` with the resolved category, rate,
        reverse-charge flag, matched rule identifier, and any explanatory
        note.
    """
    for rule in _CLASSIFICATION_RULES:
        if not rule.predicate(criteria):
            continue
        category = rule.category
        if category is None:
            # A rate-tier row: the ES-to-ES default, and the B2C service art.
            # 69.Uno.2.º keeps in the TAI. Both are taxed here, so both pick
            # their DOMESTIC_* from the tier.
            tier = criteria.rate_tier if criteria.rate_tier is not None else IvaRateKind.GENERAL
            if criteria.rate_tier is None:
                _logger.debug(
                    "classify_iva: R05 rate_tier is None; defaulting to GENERAL (issuer=%s customer=%s kind=%s)",
                    criteria.issuer_residency.value,
                    criteria.customer_residency.value,
                    criteria.kind.value,
                )
            category = _RATE_TIER_TO_CATEGORY.get(tier, IvaCategory.DOMESTIC_GENERAL)
            if category is IvaCategory.DOMESTIC_GENERAL and tier not in _RATE_TIER_TO_CATEGORY:
                _logger.debug(
                    "classify_iva: R05 tier=%s not in mapping; fell back to DOMESTIC_GENERAL",
                    tier.value if hasattr(tier, "value") else tier,
                )
        rate = _resolve_rate_for_category(criteria, category)
        requires_rc = category in {
            IvaCategory.DOMESTIC_REVERSE_CHARGE,
            IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        }
        _logger.debug(
            "classify_iva: matched rule=%s category=%s",
            rule.rule_id,
            category.value,
        )
        return IvaClassificationResult(
            category=category,
            rate=rate,
            requires_reverse_charge=requires_rc,
            matched_rule_id=rule.rule_id,
            notes=rule.description,
            consumes_party_facts=rule.consumes,
        )

    _logger.debug(
        "classify_iva: no rule matched issuer=%s customer=%s kind=%s direction=%s; returning UNKNOWN",
        criteria.issuer_residency.value,
        criteria.customer_residency.value,
        criteria.kind.value,
        criteria.direction.value,
    )
    return IvaClassificationResult(
        category=IvaCategory.UNKNOWN,
        rate=None,
        requires_reverse_charge=False,
        matched_rule_id=_R99_FALLTHROUGH_ID,
        notes="No classification rule matched the supplied criteria.",
        # An operation no rule placed declares BOTH facts consumed, and this is
        # the same guard the lazy-requirement probe applies to its own axes: an
        # unplaced operation agrees with itself about everything, so reading its
        # silence as "this fact could not have mattered" would certify
        # indifference from the fact that nothing was decided. Demanding both is
        # the only honest reading of a branch that does not exist.
        consumes_party_facts=frozenset(PartyFact),
    )


def _resolve_rate_for_category(
    criteria: IvaInvoiceClassificationCriteria,
    category: IvaCategory,
) -> IvaRateRecord | None:
    """Resolve the :class:`cadrumo.domain.iva.IvaRateRecord` applicable to ``category``.

    Returns ``None`` for categories whose rate is not directly derivable from
    the substrate (intracomunitarias, exports, imports, exempt, not-subject,
    reverse-charge — the cuota is self-assessed, declared zero, or computed
    from a downstream invoice line). For ``DOMESTIC_*`` categories the rate
    is looked up against the issuer's residency on the transaction date.

    **The schedule is selected by where the issuer is ESTABLISHED, never by
    which State identifies it** — this branch consumes
    :attr:`PartyFact.TERRITORIAL_ESTABLISHMENT` and nothing else. The rate a
    supply bears is fixed by the territory that taxes it, so an issuer
    established in the peninsula charges Spanish rates whichever Member State
    registered it. Reading the identification field here would have been the
    conflation reappearing at the money: after the split a Spanish-established
    party may legitimately carry a German identification, and the previous
    ``issuer_member_state or ES`` would then have priced a domestic Spanish
    supply off the German schedule.

    Args:
        criteria: The classification criteria; used for the issuer's
            establishment and the transaction date.
        category: The category whose rate to resolve.

    Returns:
        The matched :class:`cadrumo.domain.iva.IvaRateRecord`, or ``None`` when the
        category does not carry a directly-derivable rate, when the issuer is not
        established in Spain, or when
        :func:`cadrumo.domain.iva.lookup_rate` cannot find one.
    """
    tier = _CATEGORY_TO_RATE_TIER.get(category)
    if tier is None:
        return None
    if criteria.issuer_residency not in _SPANISH_SCOPES:
        # Every tiered category above is a DOMESTIC_* one, which only an issuer
        # inside Spain can reach. Returning nothing rather than defaulting to the
        # Spanish schedule keeps an unreachable combination unpriced instead of
        # priced wrongly.
        return None
    member_state = EUMemberState.ES
    try:
        return lookup_rate(member_state, tier, criteria.transaction_date)
    except IvaRateNotFoundError:
        _logger.debug(
            "classify_iva: lookup_rate(%s, %s, %s) failed; returning rate=None",
            member_state.value,
            tier.value,
            criteria.transaction_date.isoformat(),
        )
        return None


__all__ = [
    "CustomerTaxStatus",
    "InvoiceKind",
    "IvaClassificationResult",
    "IvaInvoiceClassificationCriteria",
    "IvaTerritorialScope",
    "PartyFact",
    "TransactionKind",
    "classifiable_categories",
    "classify_iva",
]
