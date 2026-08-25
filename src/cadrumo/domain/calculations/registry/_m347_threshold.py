"""The Modelo 347 per-counterparty declaration floor, in one place.

Two binding families reach the same declarable set: the counterpart aggregation
and the invoice resolver. They differ only in which observation type they sum
and how they read an amount off it, so the summation stays with each family and
only the regulatory comparison lives here.

This is a leaf module on purpose. ``counterpart_bindings`` already imports from
``_invoice_bindings``, so putting the shared predicate in either one would make
the dependency circular. Neither family owns the threshold; the regulation does.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ....core import M347_THRESHOLD_EUR

__all__ = ["m347_declarable_party_ids"]


def m347_declarable_party_ids(totals: Mapping[str, Decimal]) -> frozenset[str]:
    """Return the party ids whose summed Modelo 347 total passes the declaration floor.

    The floor is *exceeded*, never merely reached: a counterparty landing exactly
    on the figure is not declarable (RD 1065/2007 art. 31). The operator is
    therefore ``>``, and a ``>=`` here would over-declare every counterparty
    sitting on the threshold -- which is the mutation this function's single home
    exists to make visible.

    Before this module the comparison was written out separately in each family,
    byte-identical in two of them, so mutating one left the other's tests green
    and the duplication invisible to any test that did not know to look for it.

    Args:
        totals: Summed Modelo 347 amount per party tax id.

    Returns:
        The party tax ids that must be declared.
    """
    return frozenset(party_tax_id for party_tax_id, total in totals.items() if total > M347_THRESHOLD_EUR)
