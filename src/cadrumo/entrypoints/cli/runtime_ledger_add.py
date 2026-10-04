"""CLI transport bridge for exact-profile manual ledger transaction creation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from uuid import UUID

import typer

from ...application.ledger.ledger_add_contracts import (
    LEDGER_ADD_OPERATION_DEFINITION_ID,
    LEDGER_ADD_VALIDATION_REFUSAL_CODE,
    LedgerAddOperationResult,
    LedgerAddRequest,
)
from ...application.ledger.transaction_projection import LedgerTransactionProjection
from ...core.i18n.render import tr
from ...core.iva_deduction_fact import IvaDeductionFactKind
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.parsing.codes import normalise_iso_4217_currency
from ...core.prorrata_exclusions import Art104TresExclusion
from ...domain.iva.schema import EUMemberState, IvaCategory
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from .common import bad
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def handle_add_validation_refusal(
    completed: RegisteredOperationCompletion[LedgerAddOperationResult], profile_id: UUID
) -> None:
    """Handle add validation refusal."""
    projection = completed.projection
    if projection.outcome == "validation_error":
        invalid_refusal = (
            invalid_add_refusal_receipt(completed, profile_id)
            or invalid_add_refusal_shape(projection)
            or invalid_add_refusal_advisories(projection)
        )
        if invalid_refusal:
            raise invalid_completion_error(completed)
        if projection.validation_code == "source_jurisdiction_required_irnr":
            raise bad(tr("cli.ledger.add.source_jurisdiction_required_irnr"))
        if projection.validation_code == "source_jurisdiction_required_beckham":
            raise bad(tr("cli.ledger.add.source_jurisdiction_required_beckham"))
        detail = "; ".join(projection.validation_messages)
        raise bad(tr("cli.ledger.errors.command_input_invalid", details=detail))


def require_add_success_correlation(
    completed: RegisteredOperationCompletion[LedgerAddOperationResult],
    profile_id: UUID,
    transaction: LedgerTransactionProjection,
    booked_date: str,
    value_date: str | None,
    currency: str,
    amount: str,
    direction: TransactionDirection,
    description: str,
    counterparty: str | None,
    business_classification: BusinessClassification,
    input_classification: str | None,
    prorrata_sector: str | None,
    business_pct: str | None,
) -> None:
    """Require add success correlation."""
    projection = completed.projection
    expected_effect = OperationEffect.UPDATED if projection.bucket_event_ids else OperationEffect.NONE
    try:
        expected_booked_date = date.fromisoformat(booked_date.strip()).isoformat()
        expected_date = date.fromisoformat((value_date or booked_date).strip()).isoformat()
        expected_currency = normalise_iso_4217_currency(currency)
        expected_amount = Decimal(amount.strip())
    except (ValueError, ArithmeticError):
        expected_booked_date = ""
        expected_date = ""
        expected_currency = ""
        expected_amount = Decimal("NaN")
    invalid = (
        invalid_add_success_receipt(completed, profile_id, expected_effect)
        or invalid_added_transaction_amount(
            transaction, expected_booked_date, expected_date, expected_amount, expected_currency
        )
        or invalid_added_transaction_identity(
            transaction, direction, description, counterparty, business_classification
        )
        or invalid_add_success_advisories(projection, input_classification, prorrata_sector)
        or invalid_added_business_fraction(business_pct, business_classification, transaction)
        or (len(projection.bucket_event_ids) > 1)
    )
    if invalid:
        raise invalid_completion_error(completed)


def run_ledger_add(
    ctx: typer.Context,
    *,
    booked_date: str,
    amount: str,
    direction: TransactionDirection,
    description: str,
    value_date: str | None,
    currency: str,
    counterparty: str | None,
    business_classification: BusinessClassification,
    business_pct: str | None,
    category_id: str | None,
    taxable_base: str | None,
    iva_rate: str | None,
    iva_amount: str | None,
    iva_category: IvaCategory | None,
    deduction_fact_kind: IvaDeductionFactKind | None,
    investment_asset_id: str | None,
    counterparty_country: str | None,
    counterparty_identification_state: EUMemberState | None,
    recargo_amount: str | None,
    irpf_category: str | None,
    usage_ratio_id: str | None,
    prorrata_reference: str | None,
    art_104_tres_exclusion: Art104TresExclusion | None,
    input_classification: str | None,
    prorrata_sector: str | None,
    purchase_invoice_evidence_id: str | None,
    attachment_ids: Sequence[str],
    notes: str,
    actor: str | None,
    idempotency_key: str | None,
    source_jurisdiction: str | None,
    own_account_id: str | None = None,
) -> LedgerAddOperationResult:
    """Submit one bounded add request and strictly correlate its terminal receipt."""
    client = bound_profile_client(ctx)
    request = LedgerAddRequest(
        profile_id=client.profile_id,
        booked_date=booked_date,
        amount=amount,
        direction=direction.value,
        description=description,
        value_date=value_date,
        currency=currency,
        counterparty=counterparty,
        business_classification=business_classification.value,
        business_pct=business_pct,
        category_id=category_id,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        iva_category=_wire_token(iva_category),
        deduction_fact_kind=_wire_token(deduction_fact_kind),
        investment_asset_id=investment_asset_id,
        counterparty_country=counterparty_country,
        counterparty_identification_state=_wire_token(counterparty_identification_state),
        recargo_amount=recargo_amount,
        irpf_category=irpf_category,
        usage_ratio_id=usage_ratio_id,
        prorrata_reference=prorrata_reference,
        art_104_tres_exclusion=_wire_token(art_104_tres_exclusion),
        input_classification=input_classification,
        prorrata_sector=prorrata_sector,
        purchase_invoice_evidence_id=purchase_invoice_evidence_id,
        attachment_ids=tuple(attachment_ids),
        notes=notes,
        actor=actor if actor else None,
        idempotency_key=idempotency_key,
        source_jurisdiction=source_jurisdiction,
        own_account_id=own_account_id,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_ADD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerAddOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    handle_add_validation_refusal(completed, client.profile_id)

    transaction = projection.transaction
    if transaction is None or projection.review_status is None:
        raise invalid_completion_error(completed)
    require_add_success_correlation(
        completed,
        client.profile_id,
        transaction,
        booked_date,
        value_date,
        currency,
        amount,
        direction,
        description,
        counterparty,
        business_classification,
        input_classification,
        prorrata_sector,
        business_pct,
    )
    return projection


def _wire_token(value: object | None) -> str | None:
    """Render a CLI-owned token as its bounded wire spelling."""
    return None if value is None else str(value)


def _decimal_projection(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(value)
    except ArithmeticError:
        return None
    return parsed if parsed.is_finite() else None


__all__ = ["run_ledger_add"]


def invalid_add_refusal_receipt(
    completed: RegisteredOperationCompletion[LedgerAddOperationResult], profile_id: UUID
) -> bool:
    """Invalid add refusal receipt."""
    projection = completed.projection
    return (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.refusal_code != LEDGER_ADD_VALIDATION_REFUSAL_CODE
        or completed.effect is not OperationEffect.NONE
        or (projection.profile_id != profile_id)
    )


def invalid_add_refusal_shape(projection: LedgerAddOperationResult) -> bool:
    """Invalid add refusal shape."""
    return bool(
        projection.transaction is not None
        or projection.bucket_event_ids
        or projection.validation_code is None
        or (not projection.validation_messages)
    )


def invalid_add_refusal_advisories(projection: LedgerAddOperationResult) -> bool:
    """Invalid add refusal advisories."""
    return (
        projection.advisory_input_classification is not None
        or projection.advisory_input_classification_inert
        or projection.advisory_sector_id is not None
        or projection.advisory_sector_unmatched
    )


def invalid_add_success_receipt(
    completed: RegisteredOperationCompletion[LedgerAddOperationResult],
    profile_id: UUID,
    expected_effect: OperationEffect,
) -> bool:
    """Invalid add success receipt."""
    projection = completed.projection
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or (projection.profile_id != profile_id)
    )


def invalid_added_transaction_amount(
    transaction: LedgerTransactionProjection,
    expected_booked_date: str,
    expected_date: str,
    expected_amount: Decimal,
    expected_currency: str,
) -> bool:
    """Invalid added transaction amount."""
    return (
        transaction.booked_date != expected_booked_date
        or transaction.date != expected_date
        or _decimal_projection(transaction.amount) != expected_amount
        or (transaction.currency != expected_currency)
    )


def invalid_added_transaction_identity(
    transaction: LedgerTransactionProjection,
    direction: TransactionDirection,
    description: str,
    counterparty: str | None,
    business_classification: BusinessClassification,
) -> bool:
    """Invalid added transaction identity."""
    return (
        transaction.direction != direction.value
        or transaction.description != description.strip()
        or transaction.counterparty != (counterparty or "").strip()
        or (transaction.business_classification != business_classification.value)
    )


def invalid_add_success_advisories(
    projection: LedgerAddOperationResult, input_classification: str | None, prorrata_sector: str | None
) -> bool:
    """Invalid add success advisories."""
    return (
        projection.advisory_input_classification != input_classification
        or projection.advisory_sector_id != prorrata_sector
        or (projection.advisory_input_classification_inert and input_classification is None)
        or (projection.advisory_sector_unmatched and prorrata_sector is None)
    )


def invalid_added_business_fraction(
    business_pct: str | None, business_classification: BusinessClassification, transaction: LedgerTransactionProjection
) -> bool:
    """Invalid added business fraction."""
    return (
        business_pct is not None
        and business_classification is BusinessClassification.MIXED
        and (_decimal_projection(transaction.business_pct) != Decimal(business_pct.strip()))
    )
