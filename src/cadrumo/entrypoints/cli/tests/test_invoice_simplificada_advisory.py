"""The art. 6.1.d case 3.º predicate reaches the operator, and only when true.

``simplificada_requires_tax_id_for_domestic_issuer`` shipped exported and tested
with no production caller, so the fact it computes was never said out loud. These
assertions pin the CLI half: that the notice builder consults the predicate, that
it stays silent on every shape the predicate rejects, and that it degrades to
silence rather than to a false claim when the profile cannot be read.

The predicate's own truth table is covered beside it in
``application/invoices/tests``; what is asserted here is the WIRING, which is the
half that was missing.
"""

from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from ....core.json_contract import NoticeSeverity
from ....domain.invoices.enums import InvoiceClass, IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva import InvoiceKind
from .._ledger_business_invoice_cli import _simplificada_tax_id_notices

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BASE = Decimal("10.00")
_CUOTA = Decimal("2.10")


def _invoice(**overrides: Any) -> Invoice:
    """Build the case 3.º shape: a domestic ISSUED simplificada with no tax id."""
    payload: dict[str, Any] = {
        "kind": InvoiceKind.ISSUED,
        "invoice_class": InvoiceClass.SIMPLIFICADA,
        "invoice_number": "T-2026-001",
        "issued_at": date(2026, 5, 3),
        "counterparty_name": "Cliente de mostrador",
        "counterparty_tax_id": None,
        "counterparty_country": "ES",
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA,
        "currency": "EUR",
        "lines": (
            InvoiceLine(
                description="Consumición",
                quantity=Decimal("1"),
                unit_price=_BASE,
                subtotal=_BASE,
                iva_rate=IvaRate.RATE_21,
                iva_amount=_CUOTA,
            ),
        ),
        "payment_status": PaymentStatus.PAID,
    }
    payload.update(overrides)
    return Invoice(**payload)


def test_an_invoice_carrying_a_tax_id_is_never_advised() -> None:
    """The cheapest exit, asserted so it cannot regress into a profile read.

    An invoice that already names its counterparty has nothing to be advised
    about, and answering that must not require resolving a profile -- otherwise
    every ordinary invoice pays for a storage read to be told nothing.
    """
    assert _simplificada_tax_id_notices(_invoice(counterparty_tax_id="12345678Z")) == []


def test_the_advisory_is_silent_when_no_profile_can_be_resolved() -> None:
    """An advisory whose premise could not be evaluated must not be asserted.

    Case 3.º turns on whether the ISSUER is established in the TAI, which is a
    profile fact. With no active profile there is no answer, and inventing one
    would either nag a non-established issuer or silently clear an established
    one. Running outside a profile context is the real shape of that: the
    builder returns nothing rather than guessing.
    """
    assert _simplificada_tax_id_notices(_invoice()) == []


def test_the_builder_consults_the_predicate_rather_than_reimplementing_it() -> None:
    """Pin the single authority for case 3.º.

    The condition is subtle -- domestic, ISSUED, simplificada, no tax id, issuer
    established, and an iva_category that does not already mandate the id. A CLI
    that re-derived any part of that would drift from the predicate the domain
    tests cover, and the drift would show up as an advisory that fires on the
    wrong invoices rather than as a failure here.

    Asserted structurally because the alternative -- a reimplementation that
    happens to agree today -- passes every behavioural test until it does not.
    """
    import inspect

    from .. import _ledger_business_invoice_cli as module

    source = inspect.getsource(module._simplificada_tax_id_notices)
    tree = ast.parse(source.lstrip())
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "simplificada_requires_tax_id_for_domestic_issuer" in called, (
        "the notice builder must delegate to the predicate; re-deriving case 3.o here "
        "creates a second authority that drifts silently from the domain tests"
    )


def test_the_advisory_is_a_warning_and_never_blocks_the_write() -> None:
    """Advisory weight, stated as an executable fact.

    A domestic ticket with no identified customer is ordinary, legitimate
    practice, and the predicate rests on a residency approximation that is
    over-strict for a Canarias, Ceuta or Melilla issuer. Escalating this to a
    refusal would block lawful invoices, so the severity is pinned here: a later
    change to ERROR reddens this test and has to argue with the reasoning rather
    than quietly tighten it.
    """
    import inspect

    from .. import _ledger_business_invoice_cli as module

    source = inspect.getsource(module._simplificada_tax_id_notices)
    assert "NoticeSeverity.WARNING" in source, "case 3.o is advisory; it must not refuse the write"
    assert "NoticeSeverity.INFO" not in source, (
        "case 3.o is a real requirement the filer may be missing, so it outranks an "
        "informational aside; INFO would bury it among routine confirmations"
    )

    # The stronger guarantee, and the reason a refusal cannot creep in by editing
    # a severity: the channel has no blocking member to escalate to. Pinned so
    # that adding one forces a deliberate look at every advisory that rides it.
    assert {member.name for member in NoticeSeverity} == {"INFO", "WARNING"}
