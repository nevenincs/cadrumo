# ruff: noqa: E501 - localized guidance and tabular wire lines are atomic
"""Behavior handlers for modelo IVA wallet commands."""

from __future__ import annotations

from decimal import Decimal

import typer

from ...application.calculations import query_iva_wallet_balance
from ...application.modelo import (
    ModeloIvaWalletCorrectionNoRecordError,
    ModeloIvaWalletCorrectionSealedError,
    ModeloIvaWalletSeedNegativeAmountError,
    correct_iva_compensation_period_for_bucket,
    record_iva_compensation_override_for_bucket,
    seed_iva_compensation_period_for_bucket,
)
from ...core import Period
from ...core.decimal import try_parse_canonical_decimal
from ...core.i18n import tr
from ...domain.iva_compensation import IvaCompensationSeedConflictError
from ._common import active_bucket_id_or_refuse, emit_envelope
from ._modelo_payloads import IvaWalletBalanceResult, IvaWalletOverrideResult, IvaWalletSeedResult
from ._modelo_payloads_m036 import IvaWalletCorrectResult


def _wallet_amount(amount: str) -> Decimal:
    """Validate a hand-typed M303 carry-forward balance against the canonical grammar.

    All three mutating wallet verbs (``seed``, ``correct``, ``override``) declare
    the same euro figure and refuse with the same catalogue message, so the
    grammar is enforced once here. The two-fractional-digit cap is what makes the
    Spanish thousands shape ``1.000`` refuse instead of silently becoming
    ``Decimal("1.0")``; the grammar also refuses scientific notation, a leading
    ``+``, a comma decimal separator, and ``NaN``/``Infinity``, all of which the
    previous bare :class:`~decimal.Decimal` call accepted. A leading ``-`` still
    conforms so the domain's own non-negative refusal stays the surface that
    reports a negative balance.
    """
    parsed = try_parse_canonical_decimal(amount, max_fraction_digits=2)
    if parsed is None:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.seed_invalid_amount",
                amount=amount,
                default=f"Amount {amount!r} is not a valid decimal.",
            )
        )
    return parsed


def _load_existing_seeded_period(bucket_id: str, period: Period):
    """Return the stored period state before correction, or ``None`` when absent."""
    from ...application.calculations import IvaCompensationHistoryRepository

    del bucket_id
    return IvaCompensationHistoryRepository().load_period(period)


__all__ = ["iva_wallet_balance_cmd", "iva_wallet_correct_cmd", "iva_wallet_override_cmd", "iva_wallet_seed_cmd"]


def iva_wallet_balance_cmd(ctx: typer.Context, as_of_year: int) -> None:
    """Report the aggregated IVA wallet balance without contacting AEAT."""
    report = query_iva_wallet_balance(as_of_year=as_of_year)
    balance_result = IvaWalletBalanceResult(
        as_of_year=report.as_of_year,
        total_balance=str(report.total_balance),
        active_balance=str(report.active_balance),
        expired_balance=str(report.expired_balance),
        lot_count=report.lot_count,
        next_expiry_year=report.next_expiry_year,
        unallocated_applied_amount=str(report.unallocated_applied_amount),
    )
    lines = [
        "operation\tmodelo.iva-wallet.balance",
        f"as_of_year\t{report.as_of_year}",
        f"total_balance\t{report.total_balance}",
        f"active_balance\t{report.active_balance}",
        f"expired_balance\t{report.expired_balance}",
        f"lot_count\t{report.lot_count}",
        f"next_expiry_year\t{report.next_expiry_year}",
        f"unallocated_applied_amount\t{report.unallocated_applied_amount}",
    ]
    emit_envelope(ctx, command="modelo.iva_wallet.balance", result=balance_result, lines=lines)


def iva_wallet_seed_cmd(ctx: typer.Context, filing_year: int, period: str, amount: str, confirm: bool = False) -> None:
    """Declare a Modelo 303 carry-forward balance for bootstrapping local history."""
    if not confirm:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.seed_confirm_required",
                default="Pass --confirm to acknowledge: this declares the M303 carry-forward balance for the specified period. Filing accuracy depends on correct seeding.",
            )
        )
    seed_amount = _wallet_amount(amount)
    try:
        filing_period = Period.from_year_and_code(filing_year, period)
        state = seed_iva_compensation_period_for_bucket(
            bucket_id=active_bucket_id_or_refuse(), period=filing_period, amount=seed_amount
        )
    except ModeloIvaWalletSeedNegativeAmountError as exc:
        assert exc.translated_message is not None
        raise typer.BadParameter(tr(exc.translated_message, default="Amount must be non-negative.")) from exc
    except IvaCompensationSeedConflictError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.seed_conflict",
                filing_year=filing_year,
                period=period,
                default=f"A compensation state for {filing_year}/{period} already exists. Seeding is refused to prevent overwriting.",
            )
        ) from exc
    assert state.taxpayer_nif is not None, "seeded IVA wallet state must retain its taxpayer NIF"
    seed_result = IvaWalletSeedResult(
        filing_year=state.filing_year,
        period=state.period,
        taxpayer_nif=state.taxpayer_nif,
        amount=str(state.available_end_amount),
        provenance=state.provenance,
        register_status=state.status,
    )
    lines = [
        "operation\tmodelo.iva-wallet.seed",
        f"filing_year\t{state.filing_year}",
        f"period\t{state.period.registry_token}",
        f"taxpayer_nif\t{state.taxpayer_nif}",
        f"amount\t{state.available_end_amount}",
        f"provenance\t{state.provenance.value}",
        f"register_status\t{state.status or ''}",
    ]
    emit_envelope(ctx, command="modelo.iva_wallet.seed", result=seed_result, lines=lines)


def iva_wallet_correct_cmd(
    ctx: typer.Context, filing_year: int, period: str, amount: str, reason: str, confirm: bool = False
) -> None:
    """Correct a wrong seeded Modelo 303 carry-forward balance, guarded and audited."""
    if not confirm:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.correct_confirm_required",
                default="Pass --confirm to acknowledge: this overwrites the previously seeded M303 carry-forward balance for the specified period.",
            )
        )
    clean_reason = reason.strip()
    if not clean_reason:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.correct_reason_required",
                default="--reason must not be blank; record why the opening balance is being corrected.",
            )
        )
    correct_amount = _wallet_amount(amount)
    filing_period = Period.from_year_and_code(filing_year, period)
    previous_state = _load_existing_seeded_period(active_bucket_id_or_refuse(), filing_period)
    try:
        state = correct_iva_compensation_period_for_bucket(
            bucket_id=active_bucket_id_or_refuse(), period=filing_period, amount=correct_amount, reason=clean_reason
        )
    except ModeloIvaWalletSeedNegativeAmountError as exc:
        assert exc.translated_message is not None
        raise typer.BadParameter(tr(exc.translated_message, default="Amount must be non-negative.")) from exc
    except ModeloIvaWalletCorrectionNoRecordError as exc:
        assert exc.translated_message is not None
        raise typer.BadParameter(
            tr(
                exc.translated_message,
                filing_year=filing_year,
                period=period,
                default=f"No seeded compensation record exists for {filing_year}/{period}; correction overwrites an existing seed.",
            )
        ) from exc
    except ModeloIvaWalletCorrectionSealedError as exc:
        assert exc.translated_message is not None
        context = exc.context or {}
        raise typer.BadParameter(
            tr(
                exc.translated_message,
                filing_year=filing_year,
                period=period,
                blocking_period=context.get("blocking_period", ""),
                blocking_filing_year=context.get("blocking_filing_year", ""),
                default=f"Correction refused: an already-filed Modelo 303 ({context.get('blocking_filing_year', '?')}/{context.get('blocking_period', '?')}) has consumed this seeded compensation basis. Changing it would alter a filed return.",
            )
        ) from exc
    assert state.taxpayer_nif is not None, "corrected IVA wallet state must retain its taxpayer NIF"
    correct_result = IvaWalletCorrectResult(
        filing_year=state.filing_year,
        period=state.period,
        taxpayer_nif=state.taxpayer_nif,
        previous_amount=str(previous_state.available_end_amount) if previous_state is not None else "",
        amount=str(state.available_end_amount),
        provenance=state.provenance,
        register_status=state.status,
        reason=clean_reason,
    )
    lines = [
        "operation\tmodelo.iva-wallet.correct",
        f"filing_year\t{state.filing_year}",
        f"period\t{state.period.registry_token}",
        f"taxpayer_nif\t{state.taxpayer_nif}",
        f"previous_amount\t{(previous_state.available_end_amount if previous_state is not None else '')}",
        f"amount\t{state.available_end_amount}",
        f"provenance\t{state.provenance.value}",
        f"register_status\t{state.status or ''}",
        f"reason\t{clean_reason}",
    ]
    emit_envelope(ctx, command="modelo.iva_wallet.correct", result=correct_result, lines=lines)


def iva_wallet_override_cmd(
    ctx: typer.Context,
    filing_year: int,
    period: str,
    amount: str,
    reason: str,
    evidence_locator: str,
    confirm: bool = False,
) -> None:
    """Record an explicit taxpayer override releasing the M303 prior-compensación carry."""
    if not confirm:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.override_confirm_required",
                default="Pass --confirm to acknowledge: this records a taxpayer override of the M303 prior-compensación carry. Filing accuracy depends on the value supplied.",
            )
        )
    clean_reason = reason.strip()
    if not clean_reason:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.override_reason_required",
                default="--reason must not be blank; record the basis for the override.",
            )
        )
    clean_locator = evidence_locator.strip()
    if not clean_locator:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.override_evidence_locator_required",
                default="--evidence-locator must not be blank; record where the override's evidence lives.",
            )
        )
    override_amount = _wallet_amount(amount)
    filing_period = Period.from_year_and_code(filing_year, period)
    try:
        decision = record_iva_compensation_override_for_bucket(
            bucket_id=active_bucket_id_or_refuse(),
            period=filing_period,
            amount=override_amount,
            reason=clean_reason,
            evidence_locator=clean_locator,
        )
    except ModeloIvaWalletSeedNegativeAmountError as exc:
        assert exc.translated_message is not None
        raise typer.BadParameter(tr(exc.translated_message, default="Amount must be non-negative.")) from exc
    selected_amount = decision.selected_amount
    override_result = IvaWalletOverrideResult(
        filing_year=filing_year,
        period=filing_period,
        taxpayer_nif=str(decision.taxpayer_nif),
        amount=str(selected_amount if selected_amount is not None else override_amount),
        reason=clean_reason,
        evidence_locator=clean_locator,
        selected_authority=str(decision.selected_authority),
        divergence=str(decision.divergence),
    )
    lines = [
        "operation\tmodelo.iva-wallet.override",
        f"filing_year\t{filing_year}",
        f"period\t{filing_period.registry_token}",
        f"amount\t{override_result.amount}",
        f"selected_authority\t{override_result.selected_authority}",
        f"divergence\t{override_result.divergence}",
        f"reason\t{clean_reason}",
        f"evidence_locator\t{clean_locator}",
    ]
    emit_envelope(ctx, command="modelo.iva_wallet.override", result=override_result, lines=lines)
