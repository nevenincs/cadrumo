"""Typer registrations for modelo IVA wallet commands."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Annotated

import typer

from ...application.calculations import query_iva_wallet_balance
from ...application.modelo import (
    ModeloIvaWalletSeedNegativeAmountError,
    ModeloIvaWalletSeedNoTaxpayerError,
    seed_iva_compensation_period_for_bucket,
)
from ...core.i18n import tr
from ...domain.iva_compensation._errors import IvaCompensationSeedConflictError
from ._common import _emit_envelope
from ._modelo_payloads import IvaWalletBalanceResult, IvaWalletSeedResult


def register_iva_wallet_commands(
    app: typer.Typer,
    *,
    active_bucket_id: Callable[[], str],
) -> None:
    """Register IVA wallet commands against the root modelo Typer app."""
    iva_wallet_app = typer.Typer(
        name="iva-wallet",
        help=tr(
            "cli.app.modelo.iva_wallet.group_help",
            default="Local IVA compensation wallet balance commands.",
        ),
        no_args_is_help=True,
        add_completion=False,
    )
    app.add_typer(iva_wallet_app, name="iva-wallet")
    _register_iva_wallet_balance_command(iva_wallet_app)
    _register_iva_wallet_seed_command(iva_wallet_app, active_bucket_id=active_bucket_id)


def _register_iva_wallet_balance_command(iva_wallet_app: typer.Typer) -> None:
    @iva_wallet_app.command(
        "balance",
        help=tr(
            "cli.app.modelo.iva_wallet.balance_help",
            default=(
                "Show aggregated IVA compensation carry-forward balance computed from local "
                "Modelo 303 history. Reports total_balance, lot_count, and next_expiry_year "
                "(source_filing_year + 4 for the earliest ACTIVE lot with remaining balance)."
            ),
        ),
    )
    def iva_wallet_balance_cmd(
        ctx: typer.Context,
        as_of_year: Annotated[
            int,
            typer.Option(
                "--as-of-year",
                min=2000,
                max=2099,
                help=tr(
                    "cli.app.modelo.iva_wallet.as_of_year_help",
                    default="Reference year for carry-forward age and expiry calculations.",
                ),
            ),
        ],
    ) -> None:
        """Report the aggregated IVA wallet balance without contacting AEAT."""
        report = query_iva_wallet_balance(as_of_year=as_of_year)
        balance_result = IvaWalletBalanceResult(
            as_of_year=report.as_of_year,
            total_balance=str(report.total_balance),
            lot_count=report.lot_count,
            next_expiry_year=report.next_expiry_year,
            unallocated_applied_amount=str(report.unallocated_applied_amount),
        )
        lines = [
            "operation\tmodelo.iva-wallet.balance",
            f"as_of_year\t{report.as_of_year}",
            f"total_balance\t{report.total_balance}",
            f"lot_count\t{report.lot_count}",
            f"next_expiry_year\t{report.next_expiry_year}",
            f"unallocated_applied_amount\t{report.unallocated_applied_amount}",
        ]
        _emit_envelope(ctx, command="modelo.iva_wallet.balance", result=balance_result, lines=lines)


def _register_iva_wallet_seed_command(iva_wallet_app: typer.Typer, *, active_bucket_id: Callable[[], str]) -> None:
    @iva_wallet_app.command(
        "seed",
        help=tr(
            "cli.app.modelo.iva_wallet.seed_help",
            default=(
                "Declare a Modelo 303 carry-forward balance for a period that pre-dates "
                "local history. Use this once to seed the first period so subsequent "
                "M303 prefill resolves modelo-303-compensacion-pendiente-anteriores correctly. "
                "Refuses if a record already exists for the period."
            ),
        ),
    )
    def iva_wallet_seed_cmd(
        ctx: typer.Context,
        filing_year: Annotated[
            int,
            typer.Option(
                "--filing-year",
                min=2000,
                max=2099,
                help=tr(
                    "cli.app.modelo.iva_wallet.seed_filing_year_help",
                    default="Filing year of the Modelo 303 period to seed.",
                ),
            ),
        ],
        period: Annotated[
            str,
            typer.Option(
                "--period",
                help=tr(
                    "cli.app.modelo.iva_wallet.seed_period_help",
                    default="Period of the Modelo 303 filing (e.g. 4T, 3T).",
                ),
            ),
        ],
        amount: Annotated[
            str,
            typer.Option(
                "--amount",
                help=tr(
                    "cli.app.modelo.iva_wallet.seed_amount_help",
                    default=(
                        "Carry-forward balance amount in EUR (decimal, e.g. 1200.50). "
                        "This is the compensación pendiente de periodos anteriores for the "
                        "NEXT period after the seeded one."
                    ),
                ),
            ),
        ],
        confirm: Annotated[
            bool,
            typer.Option(
                "--confirm",
                help=tr(
                    "cli.app.modelo.iva_wallet.seed_confirm_help",
                    default=(
                        "Required confirmation flag. Acknowledge that seeding declares a "
                        "carry-forward balance and filing accuracy depends on the value supplied."
                    ),
                ),
            ),
        ] = False,
    ) -> None:
        """Declare a Modelo 303 carry-forward balance for bootstrapping local history."""
        if not confirm:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.iva_wallet.seed_confirm_required",
                    default=(
                        "Pass --confirm to acknowledge: this declares the M303 carry-forward "
                        "balance for the specified period. Filing accuracy depends on correct seeding."
                    ),
                )
            )

        try:
            seed_amount = Decimal(amount)
        except InvalidOperation as exc:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.iva_wallet.seed_invalid_amount",
                    amount=amount,
                    default=f"Amount {amount!r} is not a valid decimal.",
                )
            ) from exc

        try:
            state = seed_iva_compensation_period_for_bucket(
                bucket_id=active_bucket_id(),
                filing_year=filing_year,
                period=period,
                amount=seed_amount,
            )
        except ModeloIvaWalletSeedNegativeAmountError as exc:
            assert exc.translated_message is not None
            raise typer.BadParameter(
                tr(
                    exc.translated_message,
                    default="Amount must be non-negative.",
                )
            ) from exc
        except ModeloIvaWalletSeedNoTaxpayerError as exc:
            assert exc.translated_message is not None
            raise typer.BadParameter(
                tr(
                    exc.translated_message,
                    default="Active profile has no identity.tax_id configured. Set it via config profile.",
                )
            ) from exc
        except IvaCompensationSeedConflictError as exc:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.iva_wallet.seed_conflict",
                    filing_year=filing_year,
                    period=period,
                    default=(
                        f"A compensation state for {filing_year}/{period} already exists. "
                        "Seeding is refused to prevent overwriting."
                    ),
                )
            ) from exc

        seed_result = IvaWalletSeedResult(
            filing_year=state.filing_year,
            period=state.period,
            taxpayer_nif=state.taxpayer_nif,
            amount=str(state.available_end_amount),
            status=str(state.status),
        )
        lines = [
            "operation\tmodelo.iva-wallet.seed",
            f"filing_year\t{state.filing_year}",
            f"period\t{state.period}",
            f"taxpayer_nif\t{state.taxpayer_nif}",
            f"amount\t{state.available_end_amount}",
            f"status\t{state.status}",
        ]
        _emit_envelope(ctx, command="modelo.iva_wallet.seed", result=seed_result, lines=lines)


__all__ = ["register_iva_wallet_commands"]
