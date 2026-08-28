"""IVA flow direction enum — repercutido / soportado / INVERSION_SUJETO_PASIVO.

Codifies the IVA collectability axis the ledger and modelo registries
need alongside the operation-kind axis (:class:`IvaCategory`) and the
rate axis (:class:`IvaRateKind`). Every IVA-bearing ledger line
classifies along all three axes:

* :class:`IvaCategory` — operation kind (domestic, intracomunitaria,
  recargo, OSS, etc.).
* :class:`IvaRateKind` — rate tier (general / reduced / super-reduced /
  zero / exempt).
* :class:`IvaFlowDirection` — flow direction (output / input /
  self-assessed reverse charge).

Together the triple resolves to a single ledger-bookable Cuota.

The three flow directions are anchored to LIVA articles:

* :attr:`IvaFlowDirection.REPERCUTIDO` — LIVA art. 88 (repercusión
  del impuesto). The sujeto pasivo charges IVA to its customer; the
  customer is the obligado a soportar.
* :attr:`IvaFlowDirection.SOPORTADO` — LIVA art. 92 (cuotas
  tributarias deducibles). The sujeto pasivo bears IVA via direct
  repercusión from suppliers and may deduct that IVA from its own
  output IVA.
* :attr:`IvaFlowDirection.INVERSION_SUJETO_PASIVO` — LIVA art. 84.Uno.2.º
  (inversión del sujeto pasivo). The recipient of certain
  operations (intra-community acquisitions, art. 84.Uno.2.º.f
  construction reverse charge, etc.) is the sujeto pasivo and
  self-assesses both an IVA repercutido entry (output) and a
  matching IVA soportado entry (input) on the same operation.

The :func:`derive_flow_for_classification` helper computes the flow
direction from the substrate's :class:`IvaCategory` plus the invoice
:class:`InvoiceKind` axis so consumers do not have to encode the
mapping by hand.

==============================================================
Settlement-side cornerstones — devengada vs deducible
==============================================================

The IVA settlement model rests on two cornerstone concepts:

* **IVA devengada** (output IVA, "cuota tributaria devengada") — the
  amount the sujeto pasivo OWES to the Treasury as the IVA chargeable
  on its sales. LIVA arts. 75-77 establish when IVA accrues
  (devengo); LIVA art. 88 governs how the sujeto pasivo charges it
  to the customer (repercusión).
* **IVA deducible** (input IVA, "cuotas tributarias deducibles") —
  the amount the sujeto pasivo may DEDUCT from its devengada because
  it bore IVA on inputs. LIVA art. 92 establishes the right to
  deduction; arts. 93-104 establish the conditions, scope, and
  limits.

The cuota neta a ingresar (or a devolver) at the period level is
**devengada - deducible**; this is the canonical Modelo 303 "resultado
régimen general" line.

Every :class:`IvaFlowDirection` member contributes to one or both
cornerstones:

=======================  =========  =========
Flow direction           Devengada  Deducible
=======================  =========  =========
REPERCUTIDO              ✓          ─
SOPORTADO                ─          ✓
INVERSION_SUJETO_PASIVO  ✓          ✓
=======================  =========  =========

INVERSION_SUJETO_PASIVO is the only flow that contributes to BOTH sides on
the SAME operation: the recipient self-assesses an output entry
(devengada) and a matching input entry (deducible) for the cuota
that would have been repercutida by a non-existent or non-EU
supplier. The two entries cancel arithmetically inside Modelo 303
(devengada - deducible = 0 for that line) but both must be booked
to satisfy the LIVA art. 84.Uno.2 inversión-del-sujeto-pasivo
mechanism.

The :class:`IvaSettlementSide` enum + :func:`settlement_sides_for_flow`
helper let the ledger and modelo registries categorize transactions
without re-deriving the mapping. The closed-set helpers
:func:`is_devengada_flow` and :func:`is_deducible_flow` are the
canonical predicates for "does this flow contribute to the cuota
devengada / cuota deducible total?".
"""

from __future__ import annotations

from enum import StrEnum

from ._classification import InvoiceKind
from ._schema import IvaCategory


class IvaFlowDirection(StrEnum):
    """Closed enumeration of the IVA flow directions.

    Members are kebab-case lowercase strings to align with TOML-driven
    binding selectors and ledger-side tagging.

    Attributes:
        REPERCUTIDO: Output IVA. The sujeto pasivo charges IVA to a
            customer in an invoice it issues. Anchored to LIVA art. 88.
        SOPORTADO: Input IVA. The sujeto pasivo bears IVA charged by a
            supplier via direct repercusión and may deduct it under
            LIVA art. 92.
        INVERSION_SUJETO_PASIVO: Self-assessed reverse charge. The sujeto
            pasivo is the recipient of an operation that triggers
            inversión del sujeto pasivo under LIVA art. 84.Uno.2.º
            (intra-community acquisitions, construction RC, waste RC,
            consumer-electronics RC, services received from EU
            non-established suppliers); the same operation lands as
            both a repercutido and a soportado entry in the books.
        OPERACION_CON_INVERSION: The SUPPLIER's side of an operation
            that triggers inversión del sujeto pasivo. The supplier
            makes a sujeta y no exenta supply and repercutes nothing,
            because LIVA art. 84.Uno.2.º makes the recipient the sujeto
            pasivo; so the operation is turnover that settles on
            NEITHER side. Distinct from
            :attr:`INVERSION_SUJETO_PASIVO`, which is the recipient's
            side of the same operation.

            The member exists because that is a fourth state rather
            than the absence of the other three, and because the axis
            previously could not express it: a supplier's reverse-charge
            invoice was routed to :attr:`INVERSION_SUJETO_PASIVO` and
            self-assessed as though the supplier were the recipient.
    """

    REPERCUTIDO = "repercutido"
    SOPORTADO = "soportado"
    INVERSION_SUJETO_PASIVO = "inversion_sujeto_pasivo"
    OPERACION_CON_INVERSION = "operacion_con_inversion"


def flow_direction_for_invoice_kind(invoice_kind: InvoiceKind) -> IvaFlowDirection:
    """Return the IVA flow direction an invoice's issuance side settles as.

    This is the base rule the tax itself states: an invoice the autónomo
    ISSUED charges output IVA onward (:attr:`IvaFlowDirection.REPERCUTIDO`);
    one it RECEIVED bears input IVA (:attr:`IvaFlowDirection.SOPORTADO`).
    :func:`derive_flow_for_classification` and
    :func:`~cadrumo.domain.iva.classify_invoice_line_for_iva` both call this
    for their standard-case resolution and OVERRIDE it for the special
    regimes (reverse charge, intra-community) that route the same members
    differently.
    """
    return IvaFlowDirection.REPERCUTIDO if invoice_kind is InvoiceKind.ISSUED else IvaFlowDirection.SOPORTADO


_RECIPIENT_ONLY_REVERSE_CHARGE_CATEGORIES: frozenset[IvaCategory] = frozenset(
    {
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        # A B2B service received from an EU supplier sits in the same
        # position as the goods acquisition above: art. 69.Uno.1.o locates
        # it in Spain because the recipient is established here, and art.
        # 84.Uno.2.o makes that recipient the sujeto pasivo. Its supply
        # counterpart is deliberately absent -- there the operation is not
        # located in Spain at all, so no Spanish cuota arises to self-assess.
        IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
    },
)
"""Reverse-charge categories that route to ``INVERSION_SUJETO_PASIVO`` on EITHER
invoice direction, because only the recipient's side exists.

Both are ACQUISITIONS. The supplier's counterpart of an intra-community
acquisition is a different category entirely (an exempt art. 25 supply, or an
operation not located in Spain), so no invoice direction can put this taxpayer on
the supplying side of one of these. Direction is therefore genuinely irrelevant
here, and collapsing it is correct.

``DOMESTIC_REVERSE_CHARGE`` is deliberately NOT a member. A domestic art. 84.Uno.2
operation has both of its sides in Spain, so the same category legitimately
describes a supply this taxpayer MADE and a purchase it RECEIVED -- and those
settle differently. It is handled by direction in
:func:`derive_flow_for_classification`."""


def derive_flow_for_classification(
    *,
    category: IvaCategory,
    invoice_direction: InvoiceKind,
) -> IvaFlowDirection:
    """Return the IVA flow direction for a substrate-classified line.

    The mapping is:

    * Recipient-only reverse-charge categories (the intra-community
      acquisitions in :data:`_RECIPIENT_ONLY_REVERSE_CHARGE_CATEGORIES`)
      resolve to :attr:`IvaFlowDirection.INVERSION_SUJETO_PASIVO`
      irrespective of the invoice direction, because their supply
      counterpart is not located in Spain and so raises no Spanish cuota
      to self-assess.
    * Domestic reverse charge resolves BY DIRECTION, because both sides
      of the operation are Spanish and the form asks for them
      separately: :attr:`InvoiceKind.RECEIVED` is the recipient
      self-assessing, so
      :attr:`IvaFlowDirection.INVERSION_SUJETO_PASIVO`;
      :attr:`InvoiceKind.ISSUED` is the supplier making a sujeta y no
      exenta supply that repercutes nothing, so
      :attr:`IvaFlowDirection.OPERACION_CON_INVERSION`. Collapsing the
      two once put the supplier's turnover on the recipient's line.
    * Otherwise: :attr:`InvoiceKind.ISSUED` resolves to
      :attr:`IvaFlowDirection.REPERCUTIDO` (the autónomo charged
      output IVA on a sale) and :attr:`InvoiceKind.RECEIVED`
      resolves to :attr:`IvaFlowDirection.SOPORTADO` (the autónomo
      bore input IVA on a purchase).

    Args:
        category: The :class:`IvaCategory` resolved by the substrate
            classifier.
        invoice_direction: Whether the invoice was issued or received
            by the autónomo.

    Returns:
        The :class:`IvaFlowDirection` that matches the classification.
    """
    if category in _RECIPIENT_ONLY_REVERSE_CHARGE_CATEGORIES:
        return IvaFlowDirection.INVERSION_SUJETO_PASIVO
    if category is IvaCategory.DOMESTIC_REVERSE_CHARGE:
        if invoice_direction is InvoiceKind.ISSUED:
            return IvaFlowDirection.OPERACION_CON_INVERSION
        return IvaFlowDirection.INVERSION_SUJETO_PASIVO
    return flow_direction_for_invoice_kind(invoice_direction)


class IvaSettlementSide(StrEnum):
    """Closed enumeration of the two cornerstones of IVA settlement.

    Modelo 303 / 322 / 353 / 309 / 390 settlement is the difference
    between the two sides; downstream filing and verification logic
    classify cuotas into these two buckets.

    Attributes:
        DEVENGADA: Output IVA — the amount owed to the Treasury,
            arising from sales (LIVA art. 88 repercusión) or
            self-assessed reverse-charge entries (LIVA art. 84.Uno.2).
        DEDUCIBLE: Input IVA — the amount deductible from the
            devengada total because the sujeto pasivo bore IVA on
            inputs (LIVA art. 92 cuotas tributarias deducibles).
    """

    DEVENGADA = "devengada"
    DEDUCIBLE = "deducible"


_FLOW_TO_SETTLEMENT_SIDES: dict[IvaFlowDirection, frozenset[IvaSettlementSide]] = {
    IvaFlowDirection.REPERCUTIDO: frozenset({IvaSettlementSide.DEVENGADA}),
    IvaFlowDirection.SOPORTADO: frozenset({IvaSettlementSide.DEDUCIBLE}),
    IvaFlowDirection.INVERSION_SUJETO_PASIVO: frozenset({IvaSettlementSide.DEVENGADA, IvaSettlementSide.DEDUCIBLE}),
    IvaFlowDirection.OPERACION_CON_INVERSION: frozenset(),
}
"""Closed mapping from flow direction to the settlement side(s) it
contributes to. INVERSION_SUJETO_PASIVO is the only flow that contributes to
both sides on the same operation (LIVA art. 84.Uno.2 mechanism).

OPERACION_CON_INVERSION is the only flow that contributes to NEITHER, and the
empty set is the whole point rather than a placeholder: the supplier in a
reverse-charge operation repercutes no cuota and bears none, so the operation is
turnover that belongs in volumen de operaciones and in no cuota total. Routing it
to either side invents a figure -- to DEVENGADA an output cuota never charged, to
DEDUCIBLE a deduction of input IVA never borne."""

_DEVENGADA_FLOWS: frozenset[IvaFlowDirection] = frozenset(
    flow for flow, sides in _FLOW_TO_SETTLEMENT_SIDES.items() if IvaSettlementSide.DEVENGADA in sides
)
"""Frozen set of flow directions that contribute to cuota devengada."""

_DEDUCIBLE_FLOWS: frozenset[IvaFlowDirection] = frozenset(
    flow for flow, sides in _FLOW_TO_SETTLEMENT_SIDES.items() if IvaSettlementSide.DEDUCIBLE in sides
)
"""Frozen set of flow directions that contribute to cuota deducible."""


def settlement_sides_for_flow(
    flow: IvaFlowDirection,
) -> frozenset[IvaSettlementSide]:
    """Return the settlement side(s) ``flow`` contributes to.

    This is the CUOTA axis: which side of the settlement a line's cuota is
    reckoned on. It is not the axis of which half of the return a line's
    amounts appear in, and the two come apart on every zero-cuota operation.
    An exempt sale is an output operation whose base belongs on the devengada
    half of the return while settling no cuota at all, so reading a
    ``{DEVENGADA}`` here as "this line owes output IVA" is wrong for it.

    That distinction is easy to lose, because the Axis-A component table's
    ``cuota_settlement`` column and this function look like two statements of
    one fact and are not. Compare the two directly and roughly half the
    arising pairs appear to disagree; every one of those apparent conflicts is
    a zero-cuota operation where the table says "no cuota arises" and this
    function says "output side", both of which are true. The check worth making
    is per consumer, not per pair.

    Both production consumers screen on a positive cuota before asking, so the
    zero-cuota rows never reach the question. A future consumer that does not
    screen first is the one that would be misled, and it is the reason this
    paragraph exists rather than a coherence gate over two axes that do not
    answer the same question.

    Args:
        flow: The :class:`IvaFlowDirection` to classify.

    Returns:
        Frozenset of :class:`IvaSettlementSide` values: ``{DEVENGADA}`` for
        :attr:`IvaFlowDirection.REPERCUTIDO`, ``{DEDUCIBLE}`` for
        :attr:`IvaFlowDirection.SOPORTADO`, ``{DEVENGADA, DEDUCIBLE}`` for
        :attr:`IvaFlowDirection.INVERSION_SUJETO_PASIVO`, and the empty set for
        :attr:`IvaFlowDirection.OPERACION_CON_INVERSION`, whose supplier
        repercutes no cuota and bears none.
    """
    return _FLOW_TO_SETTLEMENT_SIDES[flow]


def is_devengada_flow(flow: IvaFlowDirection) -> bool:
    """Return ``True`` iff ``flow`` contributes to cuota devengada.

    Canonical predicate for the ledger / modelo registries when
    aggregating cuota devengada totals — equivalent to
    ``flow in {REPERCUTIDO, INVERSION_SUJETO_PASIVO}`` but anchored to the
    substrate's settlement-side codification so downstream consumers
    don't have to re-enumerate the mapping.
    """
    return flow in _DEVENGADA_FLOWS


def is_deducible_flow(flow: IvaFlowDirection) -> bool:
    """Return ``True`` iff ``flow`` contributes to cuota deducible.

    Canonical predicate for the ledger / modelo registries when
    aggregating cuota deducible totals — equivalent to
    ``flow in {SOPORTADO, INVERSION_SUJETO_PASIVO}`` but anchored to the
    substrate's settlement-side codification.
    """
    return flow in _DEDUCIBLE_FLOWS


DEVENGADA_FLOW_DIRECTIONS: frozenset[IvaFlowDirection] = _DEVENGADA_FLOWS
"""Public frozen set of flow directions contributing to cuota devengada.

Re-exported for binding selectors and ledger filters that operate at the
flow-set level rather than the per-flow predicate level."""

DEDUCIBLE_FLOW_DIRECTIONS: frozenset[IvaFlowDirection] = _DEDUCIBLE_FLOWS
"""Public frozen set of flow directions contributing to cuota deducible."""


__all__ = [
    "DEDUCIBLE_FLOW_DIRECTIONS",
    "DEVENGADA_FLOW_DIRECTIONS",
    "IvaFlowDirection",
    "IvaSettlementSide",
    "derive_flow_for_classification",
    "flow_direction_for_invoice_kind",
    "is_deducible_flow",
    "is_devengada_flow",
    "settlement_sides_for_flow",
]
