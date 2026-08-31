"""Private IVA classification predicates consumed by the canonical decision table.

This module owns only the rule predicates and their private territorial sets.
The closed table, public models, and public resolver remain in ``classification``.
"""

from __future__ import annotations

from typing import Final

from .classification import (
    CustomerTaxStatus,
    EUMemberState,
    InvoiceKind,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    TransactionKind,
    art_69_dos_exception_applies,
)


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


_SPANISH_SCOPES: Final[frozenset[IvaTerritorialScope]] = frozenset(
    {
        IvaTerritorialScope.ES_MAINLAND,
        IvaTerritorialScope.ES_CANARIAS,
        IvaTerritorialScope.ES_CEUTA_MELILLA,
    },
)
