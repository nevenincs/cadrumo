"""Private cash-accounting transaction invariant helpers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...core.decimal.constants import ZERO
from ..iva.schema import IvaCashAccountingPaymentEvidence, IvaCashAccountingTreatment
from .enums import TransactionDirection
from .errors import TransactionValidationError


def _required_operation_date(operation_date: date | None) -> date:
    """Return the operation date or raise the regime's required-field refusal."""
    if operation_date is None:
        raise TransactionValidationError(
            "operation_date is required when cash_accounting_treatment is not NONE",
        )
    return operation_date


def _require_payment_evidence(
    payment_evidence: tuple[IvaCashAccountingPaymentEvidence, ...],
) -> None:
    """Require at least one settlement event for a cash-accounting row."""
    if not payment_evidence:
        raise TransactionValidationError(
            "cash_accounting_payment_evidence is required for cash-accounting operations; "
            "wholly unpaid fallback-only operations are not yet represented",
        )


def _require_tax_substrate(
    taxable_base: Decimal | None,
    iva_amount: Decimal | None,
) -> tuple[Decimal, Decimal]:
    """Return the base and IVA facts needed to cap settlement evidence."""
    if taxable_base is None or iva_amount is None:
        raise TransactionValidationError(
            "cash-accounting operations require taxable_base and iva_amount facts",
        )
    return taxable_base, iva_amount


def _require_supplier_regime_direction(
    *,
    treatment: IvaCashAccountingTreatment,
    direction: TransactionDirection,
) -> None:
    """Keep supplier-regime treatment on received/purchase rows only."""
    if treatment is IvaCashAccountingTreatment.SUPPLIER_REGIME and direction is not TransactionDirection.OUTGOING:
        raise TransactionValidationError(
            "supplier-regime cash-accounting treatment is only valid on received/purchase rows",
        )


def _validate_payment_totals(
    *,
    payment_evidence: tuple[IvaCashAccountingPaymentEvidence, ...],
    taxable_base: Decimal,
    iva_amount: Decimal,
    recargo_amount: Decimal | None,
) -> None:
    """Ensure settlement evidence cannot exceed the transaction substrate."""
    total_base = sum((evidence.taxable_base for evidence in payment_evidence), ZERO)
    total_iva = sum((evidence.iva_amount for evidence in payment_evidence), ZERO)
    total_recargo = sum(
        (evidence.recargo_amount for evidence in payment_evidence),
        ZERO,
    )
    recargo = recargo_amount or ZERO
    if total_base > taxable_base or total_iva > iva_amount or total_recargo > recargo:
        raise TransactionValidationError(
            "cash_accounting_payment_evidence totals must not exceed taxable_base, iva_amount, or recargo_amount",
        )


def _validate_payment_dates(
    *,
    payment_evidence: tuple[IvaCashAccountingPaymentEvidence, ...],
    operation_date: date,
) -> None:
    """Reject settlement evidence after the statutory fallback date."""
    fallback_date = date(operation_date.year + 1, 12, 31)
    if any(evidence.payment_date > fallback_date for evidence in payment_evidence):
        raise TransactionValidationError(
            "cash_accounting_payment_evidence cannot fall after the 31 December statutory fallback date",
        )


def validate_cash_accounting_axis(
    *,
    treatment: IvaCashAccountingTreatment,
    operation_date: date | None,
    payment_evidence: tuple[IvaCashAccountingPaymentEvidence, ...],
    taxable_base: Decimal | None,
    iva_amount: Decimal | None,
    recargo_amount: Decimal | None,
    direction: TransactionDirection,
) -> None:
    """Validate timing, direction, substrate, and settlement evidence coupling."""
    if treatment is IvaCashAccountingTreatment.NONE:
        if payment_evidence:
            raise TransactionValidationError(
                "cash_accounting_payment_evidence requires a non-NONE cash_accounting_treatment",
            )
        return
    required_date = _required_operation_date(operation_date)
    _require_payment_evidence(payment_evidence)
    taxable_base, iva_amount = _require_tax_substrate(taxable_base, iva_amount)
    _require_supplier_regime_direction(treatment=treatment, direction=direction)
    _validate_payment_totals(
        payment_evidence=payment_evidence,
        taxable_base=taxable_base,
        iva_amount=iva_amount,
        recargo_amount=recargo_amount,
    )
    _validate_payment_dates(payment_evidence=payment_evidence, operation_date=required_date)
