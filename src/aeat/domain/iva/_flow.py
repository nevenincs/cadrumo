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
    """

    REPERCUTIDO = "repercutido"
    SOPORTADO = "soportado"
    INVERSION_SUJETO_PASIVO = "inversion_sujeto_pasivo"


_REVERSE_CHARGE_CATEGORIES: frozenset[IvaCategory] = frozenset(
    {
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
    },
)
"""IVA categories that route to ``INVERSION_SUJETO_PASIVO`` regardless of the
invoice direction. The substrate's classifier emits these values from
the rule set R01-R03 (domestic RC) and R11/R13 (intra-community
acquisitions / EU services received)."""


def derive_flow_for_classification(
    *,
    category: IvaCategory,
    invoice_direction: InvoiceKind,
) -> IvaFlowDirection:
    """Return the IVA flow direction for a substrate-classified line.

    The mapping is:

    * Reverse-charge categories (domestic RC, intra-community
      acquisition RC) always resolve to
      :attr:`IvaFlowDirection.INVERSION_SUJETO_PASIVO`, irrespective of the
      invoice direction. The substrate's classifier emits these for
      operations where the recipient self-assesses both output and
      input IVA on the same operation.
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
    if category in _REVERSE_CHARGE_CATEGORIES:
        return IvaFlowDirection.INVERSION_SUJETO_PASIVO
    if invoice_direction is InvoiceKind.ISSUED:
        return IvaFlowDirection.REPERCUTIDO
    return IvaFlowDirection.SOPORTADO


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
}
"""Closed mapping from flow direction to the settlement side(s) it
contributes to. INVERSION_SUJETO_PASIVO is the only flow that contributes to
both sides on the same operation (LIVA art. 84.Uno.2 mechanism)."""

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

    Args:
        flow: The :class:`IvaFlowDirection` to classify.

    Returns:
        Frozenset of :class:`IvaSettlementSide` values: ``{DEVENGADA}`` for
        :attr:`IvaFlowDirection.REPERCUTIDO`, ``{DEDUCIBLE}`` for
        :attr:`IvaFlowDirection.SOPORTADO`, ``{DEVENGADA, DEDUCIBLE}`` for
        :attr:`IvaFlowDirection.INVERSION_SUJETO_PASIVO`.
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
    "is_deducible_flow",
    "is_devengada_flow",
    "settlement_sides_for_flow",
]
