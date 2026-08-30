"""``m347_operation_clave`` classifies invoice direction into M347's clave A/B, never guesses the rest.

Grounded in RD 1065/2007 arts. 31/33 (recorded in the tui-architecture
modelo 347 contraparte binding inventory reference): a ``payable_invoice``
(an invoice the taxpayer must pay -- a purchase) is clave A, a
``collectible_invoice`` (an invoice the taxpayer will collect -- a sale) is
clave B. The remaining five claves (C-G) each key on a fact this function's
single ``source_kind`` argument cannot carry, so it returns ``None`` for
them rather than defaulting to a plausible-looking guess.
"""

from __future__ import annotations

import pytest

from .....core.aggregation import BindingSourceKind
from ..invoice_bindings import m347_operation_clave

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_payable_invoice_is_clave_a() -> None:
    """A purchase invoice is clave A, adquisiciones."""
    assert m347_operation_clave(BindingSourceKind.PAYABLE_INVOICE) == "A"


def test_collectible_invoice_is_clave_b() -> None:
    """A sale invoice is clave B, entregas."""
    assert m347_operation_clave(BindingSourceKind.COLLECTIBLE_INVOICE) == "B"


def test_a_value_equal_raw_string_classifies_identically_to_its_enum_member() -> None:
    """The bite proof: an ``is`` comparison would silently return None for this input.

    ``BindingSourceKind`` is a ``StrEnum``, so a raw string equal to a
    member's value is legitimate input at the registry's own TOML-to-enum
    hydration boundary -- and compares equal to the member, though never
    identical to it. A function using ``is`` here classifies a value-equal
    string as unclassifiable, indistinguishable from a genuinely unrelated
    source kind, on a filing-grade classification path.
    """
    assert m347_operation_clave("payable_invoice") == "A"
    assert m347_operation_clave("collectible_invoice") == "B"


def test_other_source_kinds_return_none_rather_than_a_guess() -> None:
    """Claves C-G each need a fact this function does not have; it must not guess."""
    assert m347_operation_clave(BindingSourceKind.LEDGER_TRANSACTION) is None
    assert m347_operation_clave(BindingSourceKind.PURCHASE_INVOICE_EVIDENCE) is None
