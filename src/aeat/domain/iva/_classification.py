"""Closed-table IVA classification (issuer / customer / kind / direction).

Layered on top of the :mod:`aeat.domain.iva` substrate (the
:class:`aeat.domain.iva.IvaCategory` enum, :class:`aeat.domain.iva.IvaRateRecord`
records, and :func:`aeat.domain.iva.lookup_rate`), this module adds the
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
    ...     customer_member_state=EUMemberState.DE,
    ...     customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
    ...     kind=TransactionKind.GOODS,
    ...     direction=InvoiceKind.ISSUED,
    ... )
    >>> classify_iva(criteria).category
    <IvaCategory.INTRA_COMMUNITY_SUPPLY: 'intra_community_supply'>
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from enum import StrEnum
from typing import NamedTuple

from pydantic import Field, model_validator

from ...core.logging import get_logger
from ._errors import IvaRateNotFoundError, IvaValidationError
from ._lookup import lookup_rate
from ._schema import (
    EUMemberState,
    IvaCategory,
    IvaExemptionArticle,
    IvaRateKind,
    IvaRateRecord,
    _IvaStrictFrozen,
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
    :attr:`aeat.domain.iva.IvaCategory.DOMESTIC_NOT_SUBJECT` for issuers
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
        B2B_NOT_REGISTERED: Business customer without a IVA-ID.
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

    Drives place-of-supply rules (services general vs. land-related vs.
    digital), reverse-charge sub-rules (construction, waste, consumer
    electronics) and rate-tier defaulting (passenger transport at 10 %,
    restaurants at 10 %). Kind is orthogonal to rate tier;
    :attr:`IvaInvoiceClassificationCriteria.rate_tier` is the explicit rate-tier axis
    the caller supplies for ES-to-ES domestic rules.

    Attributes:
        GOODS: Tangible goods supply.
        SERVICES_GENERAL: Services not covered by a specialised category.
        SERVICES_DIGITAL_B2C_OSS: Digital services routed through OSS.
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
            goods routed through Esquema Unión. LIVA art. 163 unvicies.
        OSS_UNION_GOODS_INTERFACE_FACILITATED: Interior supply of goods
            facilitated by an electronic interface, routed through Esquema
            Unión. LIVA art. 163 unvicies.
        OSS_UNION_SERVICES: Services from an EU-established taxable person
            to a consumer in another Member State routed through Esquema
            Unión. LIVA art. 163 unvicies. Distinct from
            :attr:`SERVICES_DIGITAL_B2C_OSS`, which the existing classifier
            uses for the legacy R14 digital-services-only rule.
        IOSS_DISTANCE_SALE_LOW_VALUE: Distance sale of imported goods with
            intrinsic value at or below 150 EUR routed through Esquema de
            Importación (IOSS). LIVA art. 163 quinvicies.
    """

    GOODS = "goods"
    SERVICES_GENERAL = "services_general"
    SERVICES_DIGITAL_B2C_OSS = "services_digital_b2c_oss"
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


class IvaInvoiceClassificationCriteria(_IvaStrictFrozen):
    """Input record for :func:`classify_iva`.

    Carries every axis the closed decision table inspects. The record is
    strict and frozen so it can be used as a dict key in upstream caches.

    Attributes:
        transaction_date: When the supply takes place.
        issuer_residency: Issuer's tax residency.
        customer_residency: Customer's tax residency.
        customer_tax_status: Customer's IVA status.
        kind: Kind of supply.
        direction: ``ISSUED`` or ``RECEIVED``.
        issuer_member_state: Issuer's :class:`aeat.domain.iva.EUMemberState`,
            required when :attr:`issuer_residency` is
            :attr:`IvaTerritorialScope.EU_MEMBER`.
        customer_member_state: Customer's
            :class:`aeat.domain.iva.EUMemberState`, required when
            :attr:`customer_residency` is :attr:`IvaTerritorialScope.EU_MEMBER`.
        rate_tier: Explicit rate-tier axis for ES-to-ES domestic rules.
    """

    transaction_date: date = Field(description="When the supply takes place.")
    issuer_residency: IvaTerritorialScope = Field(description="Issuer's tax residency.")
    customer_residency: IvaTerritorialScope = Field(description="Customer's tax residency.")
    customer_tax_status: CustomerTaxStatus = Field(description="Customer's IVA status.")
    kind: TransactionKind = Field(description="Kind of supply.")
    direction: InvoiceKind = Field(description="ISSUED or RECEIVED.")
    issuer_member_state: EUMemberState | None = Field(
        default=None,
        description="Issuer's :class:`EUMemberState` (required when EU_MEMBER).",
    )
    customer_member_state: EUMemberState | None = Field(
        default=None,
        description="Customer's :class:`EUMemberState` (required when EU_MEMBER).",
    )
    rate_tier: IvaRateKind | None = Field(
        default=None,
        description=(
            "Explicit rate-tier axis the caller resolves at invoice "
            "generation time (e.g. ``GENERAL`` for 21 % goods, "
            "``REDUCED`` for restaurants, ``SUPER_REDUCED`` for basic "
            "food). The classifier consults it for ES-to-ES domestic "
            "rules to pick between ``DOMESTIC_GENERAL_21`` / "
            "``DOMESTIC_REDUCED_10`` / ``DOMESTIC_SUPER_REDUCED_4`` / "
            "``DOMESTIC_ZERO``. Ignored for non-domestic rules."
        ),
    )

    @model_validator(mode="after")
    def _validate_member_state_consistency(self) -> IvaInvoiceClassificationCriteria:
        """Enforce residency and rate-tier invariants.

        Three checks, each raising :exc:`IvaValidationError` on violation:

        * ``issuer_residency == EU_MEMBER`` requires ``issuer_member_state``.
        * ``customer_residency == EU_MEMBER`` requires
          ``customer_member_state``.
        * ES-to-ES domestic transactions (both residencies ``ES_MAINLAND``)
          that would fall through to the ``R05`` ``DOMESTIC_*`` rule require
          an explicit :attr:`rate_tier`. The classifier never silently
          defaults to ``GENERAL``; the caller must supply the tier that
          applied at invoice time. Dedicated reverse-charge
          :class:`TransactionKind` values (``CONSTRUCTION``, ``WASTE``,
          ``ELECTRONICS``) are exempted because rules ``R01`` through ``R03``
          route them to :attr:`aeat.domain.iva.IvaCategory.DOMESTIC_REVERSE_CHARGE`
          before ``R05`` runs, so their rate tier is a payload concern not a
          classification axis.
        """
        if self.issuer_residency is IvaTerritorialScope.EU_MEMBER and self.issuer_member_state is None:
            raise IvaValidationError("issuer_member_state is required when issuer_residency is EU_MEMBER")
        if self.customer_residency is IvaTerritorialScope.EU_MEMBER and self.customer_member_state is None:
            raise IvaValidationError("customer_member_state is required when customer_residency is EU_MEMBER")
        if (
            self.issuer_residency is IvaTerritorialScope.ES_MAINLAND
            and self.customer_residency is IvaTerritorialScope.ES_MAINLAND
            and self.kind
            not in {
                TransactionKind.CONSTRUCTION_REVERSE_CHARGE,
                TransactionKind.WASTE_REVERSE_CHARGE,
                TransactionKind.ELECTRONICS_REVERSE_CHARGE,
                TransactionKind.IMMOVABLE_PROPERTY,
            }
            and self.rate_tier is None
        ):
            raise IvaValidationError(
                "rate_tier is required for ES-to-ES domestic transactions; "
                "supply GENERAL / REDUCED / SUPER_REDUCED / ZERO / EXEMPT explicitly",
            )
        return self


class IvaClassificationResult(_IvaStrictFrozen):
    """Output record returned by :func:`classify_iva`.

    Exposes the matched :class:`aeat.domain.iva.IvaCategory`, the resolved
    :class:`aeat.domain.iva.IvaRateRecord` (or ``None`` for rate-irrelevant
    categories), a reverse-charge flag, the matched rule identifier, and any
    free-form note the resolver emits (typically used for fall-through
    documentation).

    Attributes:
        category: Resolved IVA category.
        rate: Applicable :class:`aeat.domain.iva.IvaRateRecord`, when relevant.
        requires_reverse_charge: ``True`` when the rule triggers
            *inversión del sujeto pasivo*.
        matched_rule_id: Stable rule identifier (e.g.
            ``R10_intra_community_supply``).
        notes: Free-form explanatory note.
    """

    category: IvaCategory = Field(description="Resolved IVA category.")
    rate: IvaRateRecord | None = Field(default=None, description="Applicable :class:`IvaRateRecord`, when relevant.")
    requires_reverse_charge: bool = Field(default=False, description="True ⇒ inversión del sujeto pasivo.")
    matched_rule_id: str = Field(description="Stable rule id (e.g. ``R10_intra_community_supply``).")
    notes: str = Field(default="", description="Free-form explanatory note.")
    exemption_article: IvaExemptionArticle | None = Field(
        default=None,
        description=(
            "Optional Ley 37/1992 Art. 20 sub-article discriminator. Stamped"
            " only when ``category`` is :attr:`IvaCategory.DOMESTIC_EXEMPT`"
            " and the classification chain (or operator) has determined the"
            " specific sub-article. Routes downstream calculation chains"
            " (e.g. Modelo 303 casilla 61) to sub-article-specific casillas."
            " See ``2026-06-03-iva-exemption-article-adr``."
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


def _r10_ic_supply_goods(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an ES to EU_MEMBER B2B goods supply (Art. 25 exempt)."""
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency is IvaTerritorialScope.EU_MEMBER
        and criteria.customer_tax_status is CustomerTaxStatus.B2B_IVA_REGISTERED
        and criteria.kind is TransactionKind.GOODS
        and criteria.direction is InvoiceKind.ISSUED
    )


def _r11_ic_acquisition_goods(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an EU_MEMBER to ES B2B goods acquisition (Art. 13 + reverse charge)."""
    return (
        criteria.issuer_residency is IvaTerritorialScope.EU_MEMBER
        and criteria.customer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_tax_status is CustomerTaxStatus.B2B_IVA_REGISTERED
        and criteria.kind is TransactionKind.GOODS
        and criteria.direction is InvoiceKind.RECEIVED
    )


def _r12_services_b2b_eu_outbound(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an ES to EU_MEMBER B2B services supply (Art. 69, place of supply at destination)."""
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency is IvaTerritorialScope.EU_MEMBER
        and criteria.customer_tax_status is CustomerTaxStatus.B2B_IVA_REGISTERED
        and criteria.kind is TransactionKind.SERVICES_GENERAL
        and criteria.direction is InvoiceKind.ISSUED
    )


def _r13_services_b2b_eu_inbound(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an EU_MEMBER to ES B2B services supply (Art. 84.Uno.2º.a reverse charge at ES)."""
    return (
        criteria.issuer_residency is IvaTerritorialScope.EU_MEMBER
        and criteria.customer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_tax_status is CustomerTaxStatus.B2B_IVA_REGISTERED
        and criteria.kind is TransactionKind.SERVICES_GENERAL
        and criteria.direction is InvoiceKind.RECEIVED
    )


def _r14_digital_b2c_oss_outbound(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an ES to EU_MEMBER B2C digital service routed via OSS (Art. 70.Uno.4º)."""
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency is IvaTerritorialScope.EU_MEMBER
        and criteria.customer_tax_status is CustomerTaxStatus.B2C_CONSUMER
        and criteria.kind is TransactionKind.SERVICES_DIGITAL_B2C_OSS
        and criteria.direction is InvoiceKind.ISSUED
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


def _r20_export_goods(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an ES to THIRD_COUNTRY goods export (Art. 21, exención plena)."""
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency is IvaTerritorialScope.THIRD_COUNTRY
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


def _r22_services_outbound_third_country(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Match an ES to THIRD_COUNTRY services supply (Art. 69, place of supply outside TAI)."""
    return (
        criteria.issuer_residency is IvaTerritorialScope.ES_MAINLAND
        and criteria.customer_residency is IvaTerritorialScope.THIRD_COUNTRY
        and criteria.kind is TransactionKind.SERVICES_GENERAL
        and criteria.direction is InvoiceKind.ISSUED
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
    IvaRateKind.GENERAL: IvaCategory.DOMESTIC_GENERAL_21,
    IvaRateKind.REDUCED: IvaCategory.DOMESTIC_REDUCED_10,
    IvaRateKind.SUPER_REDUCED: IvaCategory.DOMESTIC_SUPER_REDUCED_4,
    IvaRateKind.ZERO: IvaCategory.DOMESTIC_ZERO,
    IvaRateKind.EXEMPT: IvaCategory.DOMESTIC_EXEMPT,
}


_CATEGORY_TO_RATE_TIER: dict[IvaCategory, IvaRateKind] = {
    category: tier for tier, category in _RATE_TIER_TO_CATEGORY.items()
}


class _IvaClassificationRule(NamedTuple):
    """Module-private decision-table row.

    Attributes:
        rule_id: Stable string identifier (e.g. ``R10_intra_community_supply``).
        description: Human-readable summary surfaced as
            :attr:`IvaClassificationResult.notes`.
        predicate: Predicate over a :class:`IvaInvoiceClassificationCriteria`.
        category: Concrete :class:`aeat.domain.iva.IvaCategory` to assign on a
            match, or ``None`` when the resolver derives the category from
            other inputs (used by ``R05`` against
            :attr:`IvaInvoiceClassificationCriteria.rate_tier`).
    """

    rule_id: str
    description: str
    predicate: Callable[[IvaInvoiceClassificationCriteria], bool]
    category: IvaCategory | None  # None ⇒ rule resolves to a derived category


_CLASSIFICATION_RULES: tuple[_IvaClassificationRule, ...] = (
    _IvaClassificationRule(
        "R01_construction_reverse_charge",
        "ES-to-ES construction RC",
        _r01_construction_rc,
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
    ),
    _IvaClassificationRule(
        "R02_waste_reverse_charge",
        "ES-to-ES waste RC",
        _r02_waste_rc,
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
    ),
    _IvaClassificationRule(
        "R03_electronics_reverse_charge",
        "ES-to-ES B2B electronics RC",
        _r03_electronics_rc,
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
    ),
    _IvaClassificationRule(
        "R04_immovable_property_exempt",
        "ES-to-ES immovable B2C exempt",
        _r04_immovable_b2c_exempt,
        IvaCategory.DOMESTIC_EXEMPT,
    ),
    _IvaClassificationRule(
        "R05_domestic_at_rate_tier",
        "ES-to-ES default by rate_tier",
        _r05_domestic_at_rate,
        None,
    ),
    _IvaClassificationRule(
        "R10_intra_community_supply",
        "ES to EU_MEMBER B2B goods supply",
        _r10_ic_supply_goods,
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
    ),
    _IvaClassificationRule(
        "R11_intra_community_acquisition",
        "EU_MEMBER to ES B2B goods acquisition",
        _r11_ic_acquisition_goods,
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
    ),
    _IvaClassificationRule(
        "R12_services_b2b_eu_outbound",
        "ES to EU_MEMBER B2B services",
        _r12_services_b2b_eu_outbound,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
    ),
    _IvaClassificationRule(
        "R13_services_b2b_eu_inbound",
        "EU_MEMBER to ES B2B services",
        _r13_services_b2b_eu_inbound,
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
    ),
    _IvaClassificationRule(
        "R14_digital_b2c_oss",
        "ES to EU_MEMBER B2C digital OSS",
        _r14_digital_b2c_oss_outbound,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
    ),
    _IvaClassificationRule(
        "R15_distance_sales_b2c",
        "ES to EU_MEMBER B2C distance sales",
        _r15_distance_sales_b2c_outbound,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
    ),
    _IvaClassificationRule(
        "R16_external_scheme_services",
        "3rd-country to EU_MEMBER B2C services routed through Esquema Exterior",
        _r16_external_scheme_services,
        IvaCategory.OPERACION_NO_SUJETA,
    ),
    _IvaClassificationRule(
        "R17_oss_union_goods_distance_sale",
        "ES to EU_MEMBER B2C OSS-Union goods distance sale",
        _r17_oss_union_goods_distance_sale,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
    ),
    _IvaClassificationRule(
        "R18_oss_union_goods_interface_facilitated",
        "ES to EU_MEMBER B2C OSS-Union interface-facilitated supply",
        _r18_oss_union_goods_interface_facilitated,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
    ),
    _IvaClassificationRule(
        "R19_oss_union_services",
        "ES to EU_MEMBER B2C OSS-Union services",
        _r19_oss_union_services,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
    ),
    _IvaClassificationRule(
        "R20_export_goods",
        "ES to 3rd-country goods export",
        _r20_export_goods,
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
    ),
    _IvaClassificationRule(
        "R21_import_goods",
        "3rd-country to ES goods import",
        _r21_import_goods,
        IvaCategory.IMPORT_THIRD_COUNTRY,
    ),
    _IvaClassificationRule(
        "R22_services_outbound_third_country",
        "ES to 3rd-country services",
        _r22_services_outbound_third_country,
        IvaCategory.OPERACION_NO_SUJETA,
    ),
    _IvaClassificationRule(
        "R23_ioss_distance_sale_low_value",
        "Low-value imported-goods distance sale routed through IOSS",
        _r23_ioss_distance_sale_low_value,
        IvaCategory.OPERACION_NO_SUJETA,
    ),
    _IvaClassificationRule(
        "R30_canarias_ceuta_melilla",
        "Issuer outside TAI",
        _r30_canarias_ceuta_melilla,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
    ),
)


_R99_FALLTHROUGH_ID = "R99_fallthrough"


# -- Public resolver ------------------------------------------------------


def classify_iva(criteria: IvaInvoiceClassificationCriteria) -> IvaClassificationResult:
    """Apply the closed decision table; first match wins.

    Iterates the module-level rule table in declaration order, returning the
    first :class:`IvaClassificationResult` whose predicate accepts ``criteria``.
    Falls through to the ``R99`` sentinel
    (:attr:`aeat.domain.iva.IvaCategory.UNKNOWN`) only when no rule matches —
    a state that requires human review per the
    :class:`aeat.domain.iva.IvaCategory.UNKNOWN` contract.

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
            # R05 — domestic-by-rate-tier; pick the right DOMESTIC_*.
            tier = criteria.rate_tier if criteria.rate_tier is not None else IvaRateKind.GENERAL
            if criteria.rate_tier is None:
                _logger.debug(
                    "classify_iva: R05 rate_tier is None; defaulting to GENERAL (issuer=%s customer=%s kind=%s)",
                    criteria.issuer_residency.value,
                    criteria.customer_residency.value,
                    criteria.kind.value,
                )
            category = _RATE_TIER_TO_CATEGORY.get(tier, IvaCategory.DOMESTIC_GENERAL_21)
            if category is IvaCategory.DOMESTIC_GENERAL_21 and tier not in _RATE_TIER_TO_CATEGORY:
                _logger.debug(
                    "classify_iva: R05 tier=%s not in mapping; fell back to DOMESTIC_GENERAL_21",
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
    )


def _resolve_rate_for_category(
    criteria: IvaInvoiceClassificationCriteria,
    category: IvaCategory,
) -> IvaRateRecord | None:
    """Resolve the :class:`aeat.domain.iva.IvaRateRecord` applicable to ``category``.

    Returns ``None`` for categories whose rate is not directly derivable from
    the substrate (intracomunitarias, exports, imports, exempt, not-subject,
    reverse-charge — the cuota is self-assessed, declared zero, or computed
    from a downstream invoice line). For ``DOMESTIC_*`` categories the rate
    is looked up against the issuer's residency on the transaction date.

    Args:
        criteria: The classification criteria; used for the issuer's member
            state and the transaction date.
        category: The category whose rate to resolve.

    Returns:
        The matched :class:`aeat.domain.iva.IvaRateRecord`, or ``None`` when the
        category does not carry a directly-derivable rate or when
        :func:`aeat.domain.iva.lookup_rate` cannot find one.
    """
    tier = _CATEGORY_TO_RATE_TIER.get(category)
    if tier is None:
        return None
    member_state = criteria.issuer_member_state if criteria.issuer_member_state is not None else EUMemberState.ES
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
    "TransactionKind",
    "classify_iva",
]
