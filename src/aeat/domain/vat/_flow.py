"""IVA flow direction enum — repercutido / soportado / autorepercutido.

Codifies the IVA collectability axis the ledger and modelo registries
need alongside the operation-kind axis (:class:`VATCategory`) and the
rate axis (:class:`VATRateKind`). Every IVA-bearing ledger line
classifies along all three axes:

* :class:`VATCategory` — operation kind (domestic, intracomunitaria,
  recargo, OSS, etc.).
* :class:`VATRateKind` — rate tier (general / reduced / super-reduced /
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
* :attr:`IvaFlowDirection.AUTOREPERCUTIDO` — LIVA art. 84.Uno.2.º
  (inversión del sujeto pasivo). The recipient of certain
  operations (intra-community acquisitions, art. 84.Uno.2.º.f
  construction reverse charge, etc.) is the sujeto pasivo and
  self-assesses both an IVA repercutido entry (output) and a
  matching IVA soportado entry (input) on the same operation.

The :func:`derive_flow_for_classification` helper computes the flow
direction from the substrate's :class:`VATCategory` plus the invoice
:class:`InvoiceDirection` axis so consumers do not have to encode the
mapping by hand.
"""

from __future__ import annotations

from enum import StrEnum

from ._classification import InvoiceDirection
from ._schema import VATCategory


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
        AUTOREPERCUTIDO: Self-assessed reverse charge. The sujeto
            pasivo is the recipient of an operation that triggers
            inversión del sujeto pasivo under LIVA art. 84.Uno.2.º
            (intra-community acquisitions, construction RC, waste RC,
            consumer-electronics RC, services received from EU
            non-established suppliers); the same operation lands as
            both a repercutido and a soportado entry in the books.
    """

    REPERCUTIDO = "repercutido"
    SOPORTADO = "soportado"
    AUTOREPERCUTIDO = "autorepercutido"


_REVERSE_CHARGE_CATEGORIES: frozenset[VATCategory] = frozenset(
    {
        VATCategory.DOMESTIC_REVERSE_CHARGE,
        VATCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
    }
)
"""VAT categories that route to ``AUTOREPERCUTIDO`` regardless of the
invoice direction. The substrate's classifier emits these values from
the rule set R01-R03 (domestic RC) and R11/R13 (intra-community
acquisitions / EU services received)."""


def derive_flow_for_classification(
    *,
    category: VATCategory,
    invoice_direction: InvoiceDirection,
) -> IvaFlowDirection:
    """Return the IVA flow direction for a substrate-classified line.

    The mapping is:

    * Reverse-charge categories (domestic RC, intra-community
      acquisition RC) always resolve to
      :attr:`IvaFlowDirection.AUTOREPERCUTIDO`, irrespective of the
      invoice direction. The substrate's classifier emits these for
      operations where the recipient self-assesses both output and
      input IVA on the same operation.
    * Otherwise: :attr:`InvoiceDirection.ISSUED` resolves to
      :attr:`IvaFlowDirection.REPERCUTIDO` (the autónomo charged
      output IVA on a sale) and :attr:`InvoiceDirection.RECEIVED`
      resolves to :attr:`IvaFlowDirection.SOPORTADO` (the autónomo
      bore input IVA on a purchase).

    Args:
        category: The :class:`VATCategory` resolved by the substrate
            classifier.
        invoice_direction: Whether the invoice was issued or received
            by the autónomo.

    Returns:
        The :class:`IvaFlowDirection` that matches the classification.
    """
    if category in _REVERSE_CHARGE_CATEGORIES:
        return IvaFlowDirection.AUTOREPERCUTIDO
    if invoice_direction is InvoiceDirection.ISSUED:
        return IvaFlowDirection.REPERCUTIDO
    return IvaFlowDirection.SOPORTADO


__all__ = [
    "IvaFlowDirection",
    "derive_flow_for_classification",
]
