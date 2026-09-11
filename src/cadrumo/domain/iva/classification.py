"""Generic IVA classification mechanics (issuer / customer / kind / direction).

Layered on top of the :mod:`cadrumo.domain.iva` substrate (the
:class:`cadrumo.domain.iva.IvaCategory` enum, :class:`cadrumo.domain.iva.IvaRateRecord`
records, and :func:`cadrumo.domain.iva.lookup_rate`), this module adds the
classification axes needed to tag a transaction deterministically based on
the parties' tax residency, the customer's IVA status, the transaction kind,
and the invoice direction.

The legal decision table is registry-owned. This module supplies only the
typed criteria/result records and the first-match evaluator that consumes a
registry-projected sequence of rule definitions. No legal rows, labels,
priorities, or fallback treatment are authored here.

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
    >>> classify_iva(criteria, rules=registry_rules).category
    <IvaCategory.INTRA_COMMUNITY_SUPPLY: 'intra_community_supply'>
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import NamedTuple

from pydantic import Field, model_validator

from ...core.logging import get_logger
from .errors import IvaRateNotFoundError, IvaValidationError
from .lookup import lookup_rate
from .place_of_supply import IvaPlaceOfSupplyRule, place_of_supply_rule
from .schema import (
    EUMemberState,
    IvaArt69DosService,
    IvaCategory,
    IvaExemptionArticle,
    IvaRateKind,
    IvaRateRecord,
    IvaStrictFrozen,
)

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


def domestic_rate_tier_is_required(
    *,
    issuer_residency: IvaTerritorialScope,
    customer_residency: IvaTerritorialScope,
    kind: TransactionKind,
    customer_tax_status: CustomerTaxStatus | None = None,
    art_69_dos_service: IvaArt69DosService | None = None,
    exempt_kinds: frozenset[TransactionKind] = frozenset(),
    outside_territories: frozenset[IvaTerritorialScope] = frozenset(),
) -> bool:
    """Return whether the supplied axes require a rate tier.

    Any registry-declared exceptions and outside territories are supplied by
    the caller, keeping this reusable predicate free of a second legal table.
    """
    if kind in exempt_kinds:
        return False
    if issuer_residency is IvaTerritorialScope.ES_MAINLAND and customer_residency is IvaTerritorialScope.ES_MAINLAND:
        return True
    return (
        issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and customer_residency in outside_territories
        and kind is TransactionKind.SERVICES_GENERAL
        and (customer_tax_status is None or customer_tax_status is CustomerTaxStatus.B2C_CONSUMER)
        and art_69_dos_service is None
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
        """Keep criteria validation independent from registry-owned facts."""
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
            supplied by the selected registry revision.
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
        place_of_supply: The registry row that grounds the matched rule's
            placement in the operation's filing year — which provision locates
            the operation, and whether that provision fixes the nature of the
            supply. :func:`classify_iva` always stamps it; ``None`` survives
            only on a result assembled by hand, and therefore means "no
            placement was resolved", never "the resolution failed". A lookup
            that fails raises out of :func:`classify_iva` instead of arriving
            here as an absence.

            Read the nature off
            :attr:`~cadrumo.domain.iva.place_of_supply.IvaPlaceOfSupplyRule.supply_nature`:
            a ``None`` there is the third state, and it is a statement about
            the statute — the cited provisions are silent on whether goods or
            services were supplied. It is never an unfilled row.

            What this carries is registry-declared authority for the rule the
            table matched. It is not an AEAT ruling on the specific operation,
            and a consumer must not present it as one.
    """

    category: IvaCategory = Field(description="Resolved IVA category.")
    rate: IvaRateRecord | None = Field(default=None, description="Applicable :class:`IvaRateRecord`, when relevant.")
    requires_reverse_charge: bool = Field(default=False, description="True ⇒ inversión del sujeto pasivo.")
    matched_rule_id: str = Field(description="Stable rule id supplied by registry authority.")
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
    place_of_supply: IvaPlaceOfSupplyRule | None = Field(
        default=None,
        description=(
            "Registry-declared grounding of the matched rule's placement:"
            " which provision locates the operation, and whether that"
            " provision fixes the supply's nature. Stamped by"
            " :func:`classify_iva`; ``None`` means no placement was resolved,"
            " not that resolving one failed. A ``supply_nature`` of ``None``"
            " inside the row means the cited articles are silent on the"
            " nature. Registry authority, not an AEAT ruling on the"
            " operation."
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


def domestic_categories_by_rate_kind(
    mapping: Mapping[IvaRateKind, IvaCategory] | None = None,
) -> Mapping[IvaRateKind, IvaCategory]:
    """Expose a registry-projected rate/category mapping as a read-only view."""
    if mapping is None:
        raise IvaValidationError("IVA rate/category mapping must be supplied by registry authority")
    return MappingProxyType(dict(mapping))


def rate_kind_for_domestic_category(
    category: IvaCategory,
    mapping: Mapping[IvaRateKind, IvaCategory] | None = None,
) -> IvaRateKind | None:
    """Resolve a domestic category through a caller-supplied registry mapping."""
    if mapping is None:
        raise IvaValidationError("IVA rate/category mapping must be supplied by registry authority")
    return next((tier for tier, mapped_category in mapping.items() if mapped_category is category), None)


class IvaClassificationRule(NamedTuple):
    """One registry-projected classification row consumed by the evaluator."""

    rule_id: str
    predicate: Callable[[IvaInvoiceClassificationCriteria], bool]
    category: IvaCategory | None = None
    description: str = ""
    consumes: frozenset[PartyFact] = frozenset()
    requires_reverse_charge: bool = False


# -- Public resolver ------------------------------------------------------


def _registry_iva_classification_catalogue(effective_date: date) -> ResolvedMappingFact:
    """Resolve the dated IVA catalogue consumed by the generic evaluator."""
    from ...domain.calculations.registry.authority import bundled_authority
    from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
    from ...domain.calculations.registry.schema_base import DateAxis

    authority = bundled_authority()
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="iva-invoice-classification-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise IvaValidationError("IVA classification catalogue must resolve as a mapping fact")
    return resolved


def classifiable_categories(
    rules: Iterable[IvaClassificationRule],
    *,
    consuming: PartyFact | None = None,
) -> frozenset[IvaCategory]:
    """Return categories projected by the supplied registry rows."""
    return frozenset(
        rule.category
        for rule in rules
        if rule.category is not None and (consuming is None or consuming in rule.consumes)
    )


def classify_iva(
    criteria: IvaInvoiceClassificationCriteria,
    *,
    rules: Iterable[IvaClassificationRule] | None = None,
    rate_categories: Mapping[IvaRateKind, IvaCategory] | None = None,
    rate_territories: frozenset[IvaTerritorialScope] | None = None,
) -> IvaClassificationResult:
    """Evaluate registry-projected rows in their supplied order.

    This function intentionally has no module-owned table or fallthrough row.
    Callers must project the selected registry revision into ``rules`` and,
    when a matched row derives a category from a rate tier, provide the
    registry-owned ``rate_categories`` and ``rate_territories`` mappings.
    """
    _registry_iva_classification_catalogue(criteria.transaction_date)
    if rules is None:
        raise IvaValidationError("IVA classification rows must be supplied by registry authority")
    projected_rules = tuple(rules)
    for rule in projected_rules:
        if not rule.predicate(criteria):
            continue
        category = rule.category
        if category is None:
            if criteria.rate_tier is None or rate_categories is None:
                raise IvaValidationError("matched IVA row requires a registry rate/category mapping")
            try:
                category = rate_categories[criteria.rate_tier]
            except KeyError as exc:
                raise IvaValidationError("registry rate/category mapping has no matched rate tier") from exc
        rate = _resolve_rate_for_category(
            criteria,
            category,
            rate_categories=rate_categories,
            rate_territories=rate_territories,
        )
        return IvaClassificationResult(
            category=category,
            rate=rate,
            requires_reverse_charge=rule.requires_reverse_charge,
            matched_rule_id=rule.rule_id,
            notes=rule.description,
            consumes_party_facts=rule.consumes,
            place_of_supply=place_of_supply_rule(rule.rule_id, on=criteria.transaction_date),
        )
    raise IvaValidationError("no registry IVA classification row matched the supplied criteria")


def _resolve_rate_for_category(
    criteria: IvaInvoiceClassificationCriteria,
    category: IvaCategory,
    *,
    rate_categories: Mapping[IvaRateKind, IvaCategory] | None,
    rate_territories: frozenset[IvaTerritorialScope] | None,
) -> IvaRateRecord | None:
    """Resolve a rate through caller-supplied registry mappings."""
    if rate_categories is None or rate_territories is None:
        return None
    tier = next((candidate for candidate, mapped in rate_categories.items() if mapped is category), None)
    if tier is None:
        return None
    if criteria.issuer_residency not in rate_territories:
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
    "IvaClassificationRule",
    "IvaInvoiceClassificationCriteria",
    "IvaTerritorialScope",
    "PartyFact",
    "TransactionKind",
    "classifiable_categories",
    "classify_iva",
    "domestic_categories_by_rate_kind",
    "rate_kind_for_domestic_category",
]
