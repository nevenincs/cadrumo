"""Behavior handlers for modelo IVA wallet commands."""

from __future__ import annotations

from decimal import Decimal

import typer

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.i18n.render import tr
from ...core.period import Period
from ._modelo_iva_wallet_payloads import IvaWalletBalanceResult, IvaWalletOverrideResult, IvaWalletSeedResult
from ._modelo_payloads_m036 import IvaWalletCorrectResult
from .common import emit_envelope
from .runtime_modelo_iva_wallet_balance import read_modelo_iva_wallet_balance_for_cli
from .runtime_modelo_iva_wallet_correction import read_modelo_iva_wallet_correction_for_cli
from .runtime_modelo_iva_wallet_override import read_modelo_iva_wallet_override_for_cli
from .runtime_modelo_iva_wallet_seed import read_modelo_iva_wallet_seed_for_cli


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
            )
        )
    return parsed


__all__ = ["iva_wallet_balance_cmd", "iva_wallet_correct_cmd", "iva_wallet_override_cmd", "iva_wallet_seed_cmd"]


def iva_wallet_balance_cmd(ctx: typer.Context, as_of_year: int) -> None:
    """Report the aggregated IVA wallet balance without contacting AEAT."""
    read = read_modelo_iva_wallet_balance_for_cli(ctx, as_of_year=as_of_year)
    projection = read.projection
    balance_result = IvaWalletBalanceResult(
        as_of_year=projection.as_of_year,
        total_balance=projection.total_balance,
        active_balance=projection.active_balance,
        expired_balance=projection.expired_balance,
        lot_count=projection.lot_count,
        next_expiry_year=projection.next_expiry_year,
        unallocated_applied_amount=projection.unallocated_applied_amount,
    )
    lines = [
        "operation\tmodelo.iva-wallet.balance",
        f"as_of_year\t{projection.as_of_year}",
        f"total_balance\t{projection.total_balance}",
        f"active_balance\t{projection.active_balance}",
        f"expired_balance\t{projection.expired_balance}",
        f"lot_count\t{projection.lot_count}",
        f"next_expiry_year\t{projection.next_expiry_year}",
        f"unallocated_applied_amount\t{projection.unallocated_applied_amount}",
    ]
    emit_envelope(ctx, command="modelo.iva_wallet.balance", result=balance_result, lines=lines)


def iva_wallet_seed_cmd(ctx: typer.Context, filing_year: int, period: str, amount: str, confirm: bool = False) -> None:
    """Declare a Modelo 303 carry-forward balance for bootstrapping local history."""
    if not confirm:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.seed_confirm_required",
            )
        )
    seed_amount = _wallet_amount(amount)
    filing_period = Period.from_year_and_code(filing_year, period)
    read = read_modelo_iva_wallet_seed_for_cli(
        ctx,
        period=filing_period,
        amount=str(seed_amount),
    )
    projection = read.projection
    seed_result = IvaWalletSeedResult(
        filing_year=projection.period.filing_year,
        period=filing_period,
        taxpayer_nif=projection.taxpayer_nif,
        amount=projection.amount,
        provenance=projection.provenance,
        register_status=projection.register_status,
    )
    lines = [
        "operation\tmodelo.iva-wallet.seed",
        f"filing_year\t{projection.period.filing_year}",
        f"period\t{filing_period.registry_token}",
        f"taxpayer_nif\t{projection.taxpayer_nif}",
        f"amount\t{projection.amount}",
        f"provenance\t{projection.provenance.value}",
        f"register_status\t{projection.register_status or ''}",
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
            )
        )
    clean_reason = reason.strip()
    if not clean_reason:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.correct_reason_required",
            )
        )
    correct_amount = _wallet_amount(amount)
    filing_period = Period.from_year_and_code(filing_year, period)
    read = read_modelo_iva_wallet_correction_for_cli(
        ctx,
        period=filing_period,
        amount=str(correct_amount),
        reason=clean_reason,
    )
    projection = read.projection
    correct_result = IvaWalletCorrectResult(
        filing_year=projection.period.filing_year,
        period=filing_period,
        taxpayer_nif=projection.taxpayer_nif,
        previous_amount=projection.previous_amount,
        amount=projection.amount,
        provenance=projection.provenance,
        register_status=projection.register_status,
        reason=projection.reason,
    )
    lines = [
        "operation\tmodelo.iva-wallet.correct",
        f"filing_year\t{projection.period.filing_year}",
        f"period\t{filing_period.registry_token}",
        f"taxpayer_nif\t{projection.taxpayer_nif}",
        f"previous_amount\t{projection.previous_amount}",
        f"amount\t{projection.amount}",
        f"provenance\t{projection.provenance.value}",
        f"register_status\t{projection.register_status or ''}",
        f"reason\t{projection.reason}",
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
            )
        )
    clean_reason = reason.strip()
    if not clean_reason:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.override_reason_required",
            )
        )
    clean_locator = evidence_locator.strip()
    if not clean_locator:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.override_evidence_locator_required",
            )
        )
    override_amount = _wallet_amount(amount)
    filing_period = Period.from_year_and_code(filing_year, period)
    read = read_modelo_iva_wallet_override_for_cli(
        ctx,
        period=filing_period,
        amount=str(override_amount),
        reason=clean_reason,
        evidence_locator=clean_locator,
    )
    projection = read.projection
    override_result = IvaWalletOverrideResult(
        filing_year=filing_year,
        period=filing_period,
        taxpayer_nif=projection.taxpayer_nif,
        amount=projection.amount,
        reason=clean_reason,
        evidence_locator=clean_locator,
        selected_authority=str(projection.selected_authority),
        divergence=str(projection.divergence),
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
