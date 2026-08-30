"""Contracts for the ledger invoice-validation terminal projection."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.errors import InvoiceValidationError
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva import InvoiceKind
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.cli_runner import invoke_cached_cli
from .._common import cli_policy_refusal_projection
from .._ledger_support import _ledger_invoice_validation_no_recovery

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id="00000000-0000-4000-8000-000000000130",
)

_EXPECTED_ACTION = {
    "failed_condition_id": "cli.ledger.invoice.valid",
    "evidence": [
        {
            "condition_id": "cli.ledger.invoice.valid",
            "evidence_id": "cli.ledger.invoice.valid.observation",
            "provenance": "runtime_observation",
            "values": {"invoice_valid": False},
        },
    ],
    "action": None,
    "argument_bindings": [],
    "missing_argument_names": [],
    "conditionality": "not_applicable",
    "no_recovery_outcome": "operator_decision",
}


def _assert_invoice_terminal(error: InvoiceValidationError | ValidationError) -> None:
    """Assert the exact canonical fact-only terminal projection."""
    projected = _ledger_invoice_validation_no_recovery(error)
    assert projected is not None
    refusal = cli_policy_refusal_projection(projected)
    assert refusal is not None
    assert refusal.precondition_action.model_dump(mode="json") == _EXPECTED_ACTION


def _invoice_line_validation(*, description: str, quantity: object) -> ValidationError:
    """Produce a real Pydantic invoice-line validation transport."""
    with pytest.raises(ValidationError) as raised:
        InvoiceLine.model_validate(
            {
                "description": description,
                "quantity": quantity,
                "unit_price": Decimal("100"),
                "subtotal": Decimal("100"),
                "iva_rate": IvaRate.RATE_21,
                "iva_amount": Decimal("21"),
            },
        )
    return raised.value


def _nested_invoice_line_validation() -> ValidationError:
    """Produce the Pydantic transport shape that preserves a domain error."""
    return _invoice_line_validation(description="   ", quantity=Decimal("1"))


def _invoice_payload(*, counterparty_country: object = "DE") -> dict[str, object]:
    """Return one otherwise-valid Invoice payload for a boundary coercion test."""
    return {
        "kind": InvoiceKind.ISSUED,
        "invoice_number": "S130-ORDINARY-COERCION",
        "issued_at": date(2026, 3, 15),
        "counterparty_name": "Test Counterparty GmbH",
        "counterparty_tax_id": "DE123456789",
        "counterparty_country": counterparty_country,
        "base_total": Decimal("100.00"),
        "iva_total": Decimal("21.00"),
        "grand_total": Decimal("121.00"),
        "currency": "EUR",
        "lines": (
            InvoiceLine(
                description="Consultoría tecnológica",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                subtotal=Decimal("100.00"),
                iva_rate=IvaRate.RATE_21,
                iva_amount=Decimal("21.00"),
            ),
        ),
        "payment_status": PaymentStatus.PENDING,
    }


def _invoice_validation(*, counterparty_country: object) -> ValidationError:
    """Produce a real Invoice Pydantic coercion failure without domain errors."""
    with pytest.raises(ValidationError) as raised:
        Invoice.model_validate(_invoice_payload(counterparty_country=counterparty_country))
    return raised.value


def _nested_invoice_error_count(error: ValidationError) -> int:
    """Return the number of Pydantic details preserving the domain exception."""
    return sum(
        isinstance(
            context.get("error") if isinstance(context := detail.get("ctx"), Mapping) else None,
            InvoiceValidationError,
        )
        for detail in error.errors(include_url=False)
    )


@pytest.mark.parametrize(
    "error",
    (
        InvoiceValidationError("invoice field violates its declared invariant"),
        _nested_invoice_line_validation(),
    ),
)
def test_invoice_projection_accepts_direct_and_nested_domain_transport(
    error: InvoiceValidationError | ValidationError,
) -> None:
    """Both real transports receive the one exact ledger condition once."""
    _assert_invoice_terminal(error)


def test_invoice_projection_does_not_reclassify_catalogue_load_corruption() -> None:
    """Persisted catalogue corruption retains its persistence owner."""
    with pytest.raises(ValidationError) as raised:
        InvoiceCatalogue.model_validate({"bare_catalogue_payload": {}})

    assert raised.value.title == "InvoiceCatalogue"
    assert _ledger_invoice_validation_no_recovery(raised.value) is None


def test_invoice_projection_does_not_hide_ordinary_coercion_in_a_mixed_invoice_line() -> None:
    """A mixed wrapper retains the ordinary coercion owner rather than projecting it."""
    error = _invoice_line_validation(description="   ", quantity="not-a-decimal")

    assert error.title == "InvoiceLine"
    assert len(error.errors(include_url=False)) == 2
    assert _nested_invoice_error_count(error) == 1
    assert _ledger_invoice_validation_no_recovery(error) is None


@pytest.mark.parametrize(
    ("error", "title"),
    (
        (_invoice_line_validation(description="Valid description", quantity="not-a-decimal"), "InvoiceLine"),
        (_invoice_validation(counterparty_country=123), "Invoice"),
    ),
)
def test_invoice_projection_does_not_reclassify_pure_ordinary_pydantic_coercion(
    error: ValidationError,
    title: str,
) -> None:
    """Ordinary Invoice and InvoiceLine coercion wrappers stay unprojected."""
    assert error.title == title
    assert _nested_invoice_error_count(error) == 0
    assert _ledger_invoice_validation_no_recovery(error) is None


def test_invoice_add_pydantic_invoice_validation_emits_the_canonical_terminal_action() -> None:
    """The real ledger command preserves the nested invoice condition in JSON."""
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "invoice",
            "add",
            "--kind",
            "received",
            "--counterparty-nif",
            "12345678Z",
            "--counterparty-name",
            "Contraparte S.L.",
            "--invoice-number",
            "S130-NESTED-001",
            "--invoice-date",
            "2026-03-15",
            "--taxable-base",
            "100.00",
            "--country-code",
            "ES",
            "--retention-rate",
            "0.15",
        ],
    )

    assert result.exit_code != 0, result.output
    envelope = json.loads(result.output)
    assert envelope["error"]["action"] == _EXPECTED_ACTION
