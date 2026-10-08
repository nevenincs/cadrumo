"""Canonical ordered wizard refusal provenance and closed encrypted field facts."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.invoices.errors import InvoiceValidationError
from ....domain.iva.classification import InvoiceKind
from ..catalogue_intake_refusal import (
    INVOICE_WIZARD_FIELD_ERRORS_TRANSLATION,
    MAX_INVOICE_WIZARD_FIELD_REASON_CHARACTERS,
    InvoiceWizardFieldsValidationError,
    InvoiceWizardValidationRefusalProjection,
)
from ..creation_wizard import InvoiceWizardFieldError, create_invoice_via_wizard
from ._catalogue_creation_fakes import in_memory_catalogue_creation_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PROFILE = UUID("29292929-2929-4292-8292-292929292929")


def _rows() -> tuple[InvoiceWizardFieldError, ...]:
    return (
        InvoiceWizardFieldError(field="invoice_date", reason="must be an ISO date"),
        InvoiceWizardFieldError(field="taxable_base", reason="invalid decimal amount"),
        InvoiceWizardFieldError(field="series", reason="must not be blank"),
    )


def test_canonical_carrier_keeps_frozen_order_and_exact_existing_presentation() -> None:
    rows = _rows()
    error = InvoiceWizardFieldsValidationError(rows)
    assert isinstance(error, InvoiceValidationError) and error.field_errors is rows
    assert error.translated_message == INVOICE_WIZARD_FIELD_ERRORS_TRANSLATION
    assert error.context == {
        "field_count": "3",
        "fields": "invoice_date, taxable_base, series",
        "detail": "invoice_date: must be an ISO date; taxable_base: invalid decimal amount; series: must not be blank",
    }
    with pytest.raises(AttributeError):
        error.__setattr__("field_errors", ())
    with pytest.raises(ValidationError):
        rows[0].__setattr__("reason", "changed")


def test_projection_uses_typed_rows_even_when_generic_exception_content_is_mutated() -> None:
    error = InvoiceWizardFieldsValidationError(_rows())
    assert error.context is not None
    error.context["detail"] = "UNRELATED-EXCEPTION-CONTEXT"
    error.context["credential"] = "UNRELATED-CREDENTIAL"
    projection = InvoiceWizardValidationRefusalProjection.from_error(error, profile_id=_PROFILE)
    decoded = InvoiceWizardValidationRefusalProjection.model_validate_json(projection.model_dump_json())
    restored = decoded.to_validation_error()
    assert type(restored) is InvoiceValidationError
    code = get_registered_error_code(restored)
    assert code.code == "ERROR_INVOICE_VALIDATION" and code.category is ErrorCategory.ERROR
    assert restored.context == projection.presentation_context()
    assert restored.translated_message == INVOICE_WIZARD_FIELD_ERRORS_TRANSLATION
    assert "UNRELATED" not in projection.model_dump_json()
    assert [row.field for row in projection.field_errors] == [row.field for row in _rows()]


def test_general_invoice_exception_cannot_supply_a_wizard_refusal() -> None:
    error = InvoiceValidationError(
        "UNRELATED-EXCEPTION-MESSAGE",
        translated_message=INVOICE_WIZARD_FIELD_ERRORS_TRANSLATION,
        context={"field_count": "1", "fields": "series", "detail": "UNRELATED-CONTEXT"},
    )
    with pytest.raises(ValueError, match="exact canonical field carrier"):
        InvoiceWizardValidationRefusalProjection.from_error(error, profile_id=_PROFILE)


@pytest.mark.parametrize(
    "field_errors",
    [
        (),
        ({"field": "undeclared_field", "reason": "not allowed"},),
        ({"field": "series", "reason": "first"}, {"field": "series", "reason": "second"}),
        ({"field": "series", "reason": ""},),
        ({"field": "series", "reason": "bounded", "exception_context": "UNRELATED"},),
    ],
)
def test_projection_rejects_empty_unknown_duplicate_or_open_field_facts(field_errors: tuple[object, ...]) -> None:
    with pytest.raises(ValidationError):
        InvoiceWizardValidationRefusalProjection.model_validate({"profile_id": _PROFILE, "field_errors": field_errors})


def test_projection_retains_expanded_canonical_reason_without_truncation() -> None:
    # This is the owning validator's actual repr expansion shape for a bounded
    # request field containing nonprintable code points, not exception scraping.
    raw = "\U000e0001" * 16_384
    reason = f"invalid decimal amount: {raw!r}"
    assert len(reason) < MAX_INVOICE_WIZARD_FIELD_REASON_CHARACTERS
    error = InvoiceWizardFieldsValidationError((InvoiceWizardFieldError(field="taxable_base", reason=reason),))
    projection = InvoiceWizardValidationRefusalProjection.from_error(error, profile_id=_PROFILE)
    assert projection.field_errors[0].reason == reason
    assert projection.to_validation_error().context == error.context


def test_canonical_wizard_raises_typed_ordered_field_carrier_before_any_write(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    ports = in_memory_catalogue_creation_ports()
    with validating_governed_facts(authority_operation), pytest.raises(InvoiceWizardFieldsValidationError) as refused:
        create_invoice_via_wizard(
            bucket_id=str(_PROFILE),
            kind=InvoiceKind.RECEIVED,
            counterparty_nif="A58818501",
            counterparty_name="",
            invoice_number="SYNTHETIC-WIZARD",
            invoice_date="2026-05-01",
            taxable_base="invalid",
            iva_rate="21",
            currency="EUR",
            country_code="ES",
            series=" ",
            ports=ports,
            operation=authority_operation,
        )
    carrier = refused.value
    assert [row.field for row in carrier.field_errors] == ["counterparty_name", "taxable_base", "series"]
    projection = InvoiceWizardValidationRefusalProjection.from_error(carrier, profile_id=_PROFILE)
    assert projection.presentation_context() == carrier.context
    assert projection.to_validation_error().context == carrier.context
    assert len(ports.invoice_repository.load()) == 0 and not ports.event_repository.load().events
