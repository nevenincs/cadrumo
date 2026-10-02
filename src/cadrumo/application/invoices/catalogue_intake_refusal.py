"""Typed canonical wizard field refusals for encrypted operation disclosure."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import CadrumoError
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.invoices.errors import InvoiceValidationError

if TYPE_CHECKING:
    from .creation_wizard import InvoiceWizardFieldError

INVOICE_WIZARD_VALIDATION_REFUSAL_CODE = "REFUSED_INVOICE_WIZARD_VALIDATION"
INVOICE_WIZARD_FIELD_ERRORS_TRANSLATION = "application.invoices.wizard.errors.field_errors"
MAX_INVOICE_WIZARD_FIELD_ERRORS = 15
# A canonical repr can expand one nonprintable input character to ten printed
# characters. Preserve complete reasons for the existing 16384-character fields.
MAX_INVOICE_WIZARD_FIELD_REASON_CHARACTERS = 262_144

type InvoiceWizardFieldName = Literal[
    "country_code",
    "counterparty_nif",
    "counterparty_name",
    "invoice_number",
    "invoice_date",
    "operation_date",
    "taxable_base",
    "iva_rate",
    "currency",
    "retention_amount",
    "retention_rate",
    "invoice_class",
    "series",
    "rectifies_invoice_number",
    "recargo_amount",
]


class InvoiceWizardFieldFailure(BaseModel):
    """One bounded canonical field and its complete owning-validator reason."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    field: InvoiceWizardFieldName
    reason: Annotated[str, Field(min_length=1, max_length=MAX_INVOICE_WIZARD_FIELD_REASON_CHARACTERS)]


type InvoiceWizardFieldFailures = Annotated[
    tuple[InvoiceWizardFieldFailure, ...], Field(min_length=1, max_length=MAX_INVOICE_WIZARD_FIELD_ERRORS)
]


class InvoiceWizardFieldsValidationError(InvoiceValidationError):
    """Carry the canonical ordered frozen rows alongside their original presentation."""

    __slots__ = ("_field_errors",)

    def __init__(self, field_errors: tuple[InvoiceWizardFieldError, ...]) -> None:
        """Accept only owning wizard rows, preserving exact original translation facts."""
        from .creation_wizard import InvoiceWizardFieldError

        if (
            type(field_errors) is not tuple
            or not field_errors
            or any(type(row) is not InvoiceWizardFieldError for row in field_errors)
        ):
            raise ValueError("wizard field refusal requires canonical immutable rows")
        self._field_errors = field_errors
        joined = "; ".join(f"{row.field}: {row.reason}" for row in field_errors)
        super().__init__(
            f"invoice wizard refused {len(field_errors)} field(s): {joined}",
            translated_message=INVOICE_WIZARD_FIELD_ERRORS_TRANSLATION,
            context={
                "field_count": str(len(field_errors)),
                "fields": ", ".join(row.field for row in field_errors),
                "detail": joined,
            },
        )

    @property
    def field_errors(self) -> tuple[InvoiceWizardFieldError, ...]:
        """Return the original canonical order through a read-only immutable tuple."""
        return self._field_errors


class InvoiceWizardValidationRefusedError(CadrumoError):
    """Declare the operation's field-validation refusal code and REFUSED category."""


class InvoiceWizardValidationRefusalProjection(BaseModel):
    """Encrypted field facts; generic exception messages and contexts are excluded."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: Literal["field_errors"] = "field_errors"
    field_errors: InvoiceWizardFieldFailures

    @model_validator(mode="after")
    def _unique_fields(self) -> Self:
        if len({row.field for row in self.field_errors}) != len(self.field_errors):
            raise ValueError("wizard refusal must retain one reason per independent field")
        return self

    @classmethod
    def from_error(cls, error: InvoiceValidationError, *, profile_id: UUID) -> Self:
        """Copy only the exact canonical carrier, never arbitrary exception content."""
        if type(error) is not InvoiceWizardFieldsValidationError or not isinstance(
            error, InvoiceWizardFieldsValidationError
        ):
            raise ValueError("wizard refusal requires the exact canonical field carrier")
        return cls(
            profile_id=profile_id,
            field_errors=tuple(
                InvoiceWizardFieldFailure.model_validate({"field": row.field, "reason": row.reason}, strict=True)
                for row in error.field_errors
            ),
        )

    def presentation_context(self) -> dict[str, str]:
        """Derive the existing localized interpolation facts from the ordered rows."""
        return {
            "field_count": str(len(self.field_errors)),
            "fields": ", ".join(row.field for row in self.field_errors),
            "detail": "; ".join(f"{row.field}: {row.reason}" for row in self.field_errors),
        }

    def to_validation_error(self) -> InvoiceValidationError:
        """Restore the original human error code from validated canonical field facts."""
        context = self.presentation_context()
        return InvoiceValidationError(
            f"invoice wizard refused {len(self.field_errors)} field(s): {context['detail']}",
            translated_message=INVOICE_WIZARD_FIELD_ERRORS_TRANSLATION,
            context=context,
        )


__all__ = [
    "INVOICE_WIZARD_FIELD_ERRORS_TRANSLATION",
    "INVOICE_WIZARD_VALIDATION_REFUSAL_CODE",
    "MAX_INVOICE_WIZARD_FIELD_ERRORS",
    "MAX_INVOICE_WIZARD_FIELD_REASON_CHARACTERS",
    "InvoiceWizardFieldFailure",
    "InvoiceWizardFieldFailures",
    "InvoiceWizardFieldName",
    "InvoiceWizardFieldsValidationError",
    "InvoiceWizardValidationRefusalProjection",
    "InvoiceWizardValidationRefusedError",
]
