"""The four answers case 3.º can give, and why "unknown" is not "fine".

The distinction this module exists for is between an invoice the rule cleared
and an invoice the rule never ran against. Both used to be an empty list of
notices, so a filer whose profile store would not read lost a real legal
advisory and was never told the check had been skipped.

The predicate's own legality is covered by ``test_issuer_establishment``; these
tests cover the resolution around it and the states it must keep apart.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from ....domain.deadlines.models import FiscalResidency, IVARegime, TaxpayerProfile
from ....domain.invoices.enums import InvoiceClass, IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ..simplificada_advisory import SimplificadaTaxIdAdvisory, resolve_simplificada_tax_id_advisory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BASE = Decimal("40.00")
_CUOTA = Decimal("8.40")


def _profile(**overrides: Any) -> TaxpayerProfile:
    payload: dict[str, Any] = {"tax_id": "12345678Z", "iva_regime": IVARegime.GENERAL}
    payload.update(overrides)
    return TaxpayerProfile(**payload)  # type: ignore[arg-type]


def _invoice(**overrides: Any) -> Invoice:
    line = InvoiceLine(
        description="Reparación urgente",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.RATE_21,
        iva_amount=_CUOTA,
    )
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
        "lines": (line,),
        "payment_status": PaymentStatus.PAID,
    }
    payload.update(overrides)
    return Invoice(**payload)  # type: ignore[arg-type]


def test_a_domestic_ticket_from_an_established_issuer_wants_the_nif() -> None:
    """Case 3.º applying, so every refusal below is not vacuous."""
    outcome = resolve_simplificada_tax_id_advisory(
        invoice=_invoice(),
        profile_resolver=lambda: _profile(fiscal_residency=FiscalResidency.RESIDENT_IRPF),
    )

    assert outcome is SimplificadaTaxIdAdvisory.REQUIRED


def test_a_non_established_issuer_is_evaluated_and_cleared() -> None:
    """Answered no, which is a different fact from not being answered."""
    outcome = resolve_simplificada_tax_id_advisory(
        invoice=_invoice(),
        profile_resolver=lambda: _profile(
            fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
            tax_id="X1234567L",
            # Required by the domain when residency is NON_RESIDENT_IRNR
            # (TRLIRNR RDLeg 5/2004 art. 2); omitting it makes the profile
            # unconstructable and the negative case untestable.
            country_of_fiscal_residence="PT",
        ),
    )

    assert outcome is SimplificadaTaxIdAdvisory.NOT_REQUIRED


def test_an_unresolvable_issuer_is_reported_as_unknown_not_as_cleared() -> None:
    """The defect this module was written for.

    ``NOT_REQUIRED`` here would tell a filer with a degraded profile store that
    their invoice was checked and passed. It was not checked at all.
    """
    outcome = resolve_simplificada_tax_id_advisory(invoice=_invoice(), profile_resolver=lambda: None)

    assert outcome is SimplificadaTaxIdAdvisory.ISSUER_UNKNOWN


def test_an_identified_destinatario_is_answered_without_reading_a_profile() -> None:
    """Case 3.º is satisfied whoever issued it, so the profile is never consulted.

    Ordering matters rather than being incidental: resolving the profile first
    would turn an answerable invoice into ``ISSUER_UNKNOWN`` whenever the
    profile store happened to be unreadable.
    """
    consulted = False

    def resolver() -> TaxpayerProfile | None:
        nonlocal consulted
        consulted = True
        return None

    outcome = resolve_simplificada_tax_id_advisory(
        invoice=_invoice(counterparty_tax_id="B12345674"),
        profile_resolver=resolver,
    )

    assert outcome is SimplificadaTaxIdAdvisory.ALREADY_IDENTIFIED
    assert not consulted


def test_only_one_outcome_is_something_to_tell_the_operator() -> None:
    """Pinned so a fifth state has to say whether it warrants an advisory.

    Three of the four are silence for different reasons, and a surface that
    treated any of them as REQUIRED would nag on lawful invoices.
    """
    silent = set(SimplificadaTaxIdAdvisory) - {SimplificadaTaxIdAdvisory.REQUIRED}

    assert silent == {
        SimplificadaTaxIdAdvisory.NOT_REQUIRED,
        SimplificadaTaxIdAdvisory.ALREADY_IDENTIFIED,
        SimplificadaTaxIdAdvisory.ISSUER_UNKNOWN,
    }


def test_the_resolver_delegates_to_the_single_case_3_authority() -> None:
    """Pin the single authority for case 3.º.

    The condition is subtle -- domestic, ISSUED, simplificada, no tax id,
    issuer established. A re-derivation here would drift from the predicate the
    sibling tests cover, and the drift would show as an advisory firing on the
    wrong invoices rather than as a failure. Asserted structurally because a
    reimplementation that happens to agree today passes every behavioural test
    until it does not.
    """
    import ast
    import inspect

    from .. import simplificada_advisory as module

    source = inspect.getsource(module.resolve_simplificada_tax_id_advisory)
    tree = ast.parse(source.lstrip())
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}

    assert "simplificada_requires_tax_id_for_domestic_issuer" in called
