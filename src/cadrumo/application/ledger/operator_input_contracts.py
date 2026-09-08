"""Canonical operator-input identities for ledger application actions.

Presentation adapters may choose help text, but they derive parameter names,
tokens, requiredness, and value types from these application-owned contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class OperatorInputContract:
    """Transport-neutral identity and value type of one operator input."""

    name: str
    tokens: tuple[str, ...]
    value_module: str
    value_name: str
    required: bool = False


INVOICE_KIND_INPUT: Final = OperatorInputContract(
    name="kind",
    tokens=("--kind",),
    value_module="cadrumo.domain.iva.classification",
    value_name="InvoiceKind",
    required=True,
)
INVOICE_CLASS_INPUT: Final = OperatorInputContract(
    "invoice_class", ("--invoice-class",), "cadrumo.domain.invoices.enums", "InvoiceClass"
)
IVA_AMOUNT_INPUT: Final = OperatorInputContract("iva_amount", ("--iva-amount",), "builtins", "str")
IVA_CATEGORY_INPUT: Final = OperatorInputContract(
    "iva_category", ("--iva-category",), "cadrumo.domain.iva.schema", "IvaCategory"
)
DEDUCTION_FACT_KIND_INPUT: Final = OperatorInputContract(
    "deduction_fact_kind", ("--deduction-kind",), "cadrumo.core.iva_deduction_fact", "IvaDeductionFactKind"
)
COUNTERPARTY_IDENTIFICATION_STATE_INPUT: Final = OperatorInputContract(
    "counterparty_identification_state",
    ("--counterparty-identification-state",),
    "cadrumo.domain.iva.schema",
    "EUMemberState",
)
NOTES_INPUT: Final = OperatorInputContract("notes", ("--notes",), "builtins", "str")


__all__ = [
    "COUNTERPARTY_IDENTIFICATION_STATE_INPUT",
    "DEDUCTION_FACT_KIND_INPUT",
    "INVOICE_CLASS_INPUT",
    "INVOICE_KIND_INPUT",
    "IVA_AMOUNT_INPUT",
    "IVA_CATEGORY_INPUT",
    "NOTES_INPUT",
    "OperatorInputContract",
]
