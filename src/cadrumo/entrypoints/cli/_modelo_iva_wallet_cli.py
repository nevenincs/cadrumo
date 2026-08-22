"""Typer registrations for modelo IVA wallet commands."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Annotated

import typer

from ...application.calculations import query_iva_wallet_balance
from ...application.modelo import (
    ModeloIvaWalletCorrectionNoRecordError,
    ModeloIvaWalletCorrectionSealedError,
    ModeloIvaWalletSeedNegativeAmountError,
    ModeloIvaWalletSeedNoTaxpayerError,
    correct_iva_compensation_period_for_bucket,
    record_iva_compensation_override_for_bucket,
    seed_iva_compensation_period_for_bucket,
)
from ...core import Period
from ...core.decimal import try_parse_canonical_decimal
from ...core.i18n import tr
from ...domain.iva_compensation import IvaCompensationSeedConflictError
from ._command_policy import command_execution_policy
from ._common import _emit_envelope
from ._modelo_execution_policies import MODEL_READ, MODEL_WRITE, declare_metadata_group
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
            ),
        )
    return parsed


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
    declare_metadata_group(iva_wallet_app)
    app.add_typer(iva_wallet_app, name="iva-wallet")
    _register_iva_wallet_balance_command(iva_wallet_app)
    _register_iva_wallet_seed_command(iva_wallet_app, active_bucket_id=active_bucket_id)
    _register_iva_wallet_correct_command(iva_wallet_app, active_bucket_id=active_bucket_id)
    _register_iva_wallet_override_command(iva_wallet_app, active_bucket_id=active_bucket_id)


def _register_iva_wallet_balance_command(iva_wallet_app: typer.Typer) -> None:
    @iva_wallet_app.command(
        "balance",
        help=tr(
            "cli.app.modelo.iva_wallet.balance_help",
            default=(
                "Show aggregated IVA compensation carry-forward balance computed from local "
                "Modelo 303 history. Reports total_balance, active_balance, expired_balance, "
                "lot_count, and next_expiry_year (source_filing_year + 4 for the earliest "
                "non-expired lot with remaining balance)."
            ),
        ),
    )
    @command_execution_policy(MODEL_READ)
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
    @command_execution_policy(MODEL_WRITE)
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
                ),
            )

        seed_amount = _wallet_amount(amount)

        try:
            filing_period = Period.from_year_and_code(filing_year, period)
            state = seed_iva_compensation_period_for_bucket(
                bucket_id=active_bucket_id(),
                period=filing_period,
                amount=seed_amount,
            )
        except ModeloIvaWalletSeedNegativeAmountError as exc:
            assert exc.translated_message is not None
            raise typer.BadParameter(
                tr(
                    exc.translated_message,
                    default="Amount must be non-negative.",
                ),
            ) from exc
        except ModeloIvaWalletSeedNoTaxpayerError as exc:
            assert exc.translated_message is not None
            raise typer.BadParameter(
                tr(
                    exc.translated_message,
                    default="Active profile has no identity.tax_id configured. Set it via config profile.",
                ),
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
                ),
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
        _emit_envelope(ctx, command="modelo.iva_wallet.seed", result=seed_result, lines=lines)


def _register_iva_wallet_correct_command(iva_wallet_app: typer.Typer, *, active_bucket_id: Callable[[], str]) -> None:
    @iva_wallet_app.command(
        "correct",
        help=tr(
            "cli.app.modelo.iva_wallet.correct_help",
            default=(
                "Correct a wrong opening Modelo 303 carry-forward balance previously seeded for a "
                "pre-history period. Overwrites the existing seeded amount; refuses when no record "
                "exists for the period (seed first) and when an already-filed Modelo 303 has "
                "consumed the seeded basis (correcting it would change a filed return). Records "
                "--reason into an audit event. Requires --confirm."
            ),
        ),
    )
    @command_execution_policy(MODEL_WRITE)
    def iva_wallet_correct_cmd(
        ctx: typer.Context,
        filing_year: Annotated[
            int,
            typer.Option(
                "--filing-year",
                min=2000,
                max=2099,
                help=tr(
                    "cli.app.modelo.iva_wallet.correct_filing_year_help",
                    default="Filing year of the seeded Modelo 303 period to correct.",
                ),
            ),
        ],
        period: Annotated[
            str,
            typer.Option(
                "--period",
                help=tr(
                    "cli.app.modelo.iva_wallet.correct_period_help",
                    default="Period of the seeded Modelo 303 record to correct (e.g. 4T, 3T).",
                ),
            ),
        ],
        amount: Annotated[
            str,
            typer.Option(
                "--amount",
                help=tr(
                    "cli.app.modelo.iva_wallet.correct_amount_help",
                    default="Corrected carry-forward balance amount in EUR (decimal, e.g. 1200.50).",
                ),
            ),
        ],
        reason: Annotated[
            str,
            typer.Option(
                "--reason",
                help=tr(
                    "cli.app.modelo.iva_wallet.correct_reason_help",
                    default="Reason for the correction, recorded into the audit event.",
                ),
            ),
        ],
        confirm: Annotated[
            bool,
            typer.Option(
                "--confirm",
                "--yes",
                help=tr(
                    "cli.app.modelo.iva_wallet.correct_confirm_help",
                    default=(
                        "Required confirmation flag. Acknowledge that this overwrites a previously "
                        "seeded carry-forward balance and filing accuracy depends on the new value."
                    ),
                ),
            ),
        ] = False,
    ) -> None:
        """Correct a wrong seeded Modelo 303 carry-forward balance, guarded and audited."""
        if not confirm:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.iva_wallet.correct_confirm_required",
                    default=(
                        "Pass --confirm to acknowledge: this overwrites the previously seeded M303 "
                        "carry-forward balance for the specified period."
                    ),
                ),
            )

        clean_reason = reason.strip()
        if not clean_reason:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.iva_wallet.correct_reason_required",
                    default="--reason must not be blank; record why the opening balance is being corrected.",
                ),
            )

        correct_amount = _wallet_amount(amount)

        filing_period = Period.from_year_and_code(filing_year, period)
        previous_state = _load_existing_seeded_period(active_bucket_id(), filing_period)

        try:
            state = correct_iva_compensation_period_for_bucket(
                bucket_id=active_bucket_id(),
                period=filing_period,
                amount=correct_amount,
                reason=clean_reason,
            )
        except ModeloIvaWalletSeedNegativeAmountError as exc:
            assert exc.translated_message is not None
            raise typer.BadParameter(tr(exc.translated_message, default="Amount must be non-negative.")) from exc
        except ModeloIvaWalletSeedNoTaxpayerError as exc:
            assert exc.translated_message is not None
            raise typer.BadParameter(
                tr(
                    exc.translated_message,
                    default="Active profile has no identity.tax_id configured. Set it via config profile.",
                ),
            ) from exc
        except ModeloIvaWalletCorrectionNoRecordError as exc:
            assert exc.translated_message is not None
            raise typer.BadParameter(
                tr(
                    exc.translated_message,
                    filing_year=filing_year,
                    period=period,
                    default=(
                        f"No seeded compensation record exists for {filing_year}/{period}. "
                        "Run 'aeat app modelo iva-wallet seed' first; correction overwrites an existing seed."
                    ),
                ),
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
                    default=(
                        f"Correction refused: an already-filed Modelo 303 "
                        f"({context.get('blocking_filing_year', '?')}/{context.get('blocking_period', '?')}) "
                        "has consumed this seeded compensation basis. Changing it would alter a filed return."
                    ),
                ),
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
            f"previous_amount\t{previous_state.available_end_amount if previous_state is not None else ''}",
            f"amount\t{state.available_end_amount}",
            f"provenance\t{state.provenance.value}",
            f"register_status\t{state.status or ''}",
            f"reason\t{clean_reason}",
        ]
        _emit_envelope(ctx, command="modelo.iva_wallet.correct", result=correct_result, lines=lines)


def _register_iva_wallet_override_command(iva_wallet_app: typer.Typer, *, active_bucket_id: Callable[[], str]) -> None:
    @iva_wallet_app.command(
        "override",
        help=tr(
            "cli.app.modelo.iva_wallet.override_help",
            default=(
                "Record an explicit taxpayer override for the Modelo 303 prior-period "
                "compensación carry (`iva.compensacion-pendiente-periodos-anteriores`, AEAT box 110). "
                "The reconciliation refuses to auto-apply a "
                "seeded/local carry without live AEAT wallet evidence; this verb records the "
                "operator-asserted amount with mandatory --reason and --evidence-locator "
                "provenance, persisting a non-blocking taxpayer_override decision so the next "
                "'work calculate' applies it to `iva.compensacion-pendiente-periodos-anteriores`. "
                "It unblocks the carry CALCULATION "
                "only — it does NOT satisfy the dependent period's official-evidence verify gate, "
                "and contacts AEAT zero times. Requires --confirm."
            ),
        ),
    )
    @command_execution_policy(MODEL_WRITE)
    def iva_wallet_override_cmd(
        ctx: typer.Context,
        filing_year: Annotated[
            int,
            typer.Option(
                "--filing-year",
                min=2000,
                max=2099,
                help=tr(
                    "cli.app.modelo.iva_wallet.override_filing_year_help",
                    default="Filing year of the Modelo 303 period whose prior-compensation carry is overridden.",
                ),
            ),
        ],
        period: Annotated[
            str,
            typer.Option(
                "--period",
                help=tr(
                    "cli.app.modelo.iva_wallet.override_period_help",
                    default="Period of the dependent Modelo 303 filing receiving the carry (e.g. 2T, 3T).",
                ),
            ),
        ],
        amount: Annotated[
            str,
            typer.Option(
                "--amount",
                help=tr(
                    "cli.app.modelo.iva_wallet.override_amount_help",
                    default=(
                        "Overridden prior-compensación amount in EUR applied to "
                        "`iva.compensacion-pendiente-periodos-anteriores` "
                        "(AEAT box 110; decimal, e.g. 420.00)."
                    ),
                ),
            ),
        ],
        reason: Annotated[
            str,
            typer.Option(
                "--reason",
                help=tr(
                    "cli.app.modelo.iva_wallet.override_reason_help",
                    default="Required basis for the override, recorded as auditable provenance.",
                ),
            ),
        ],
        evidence_locator: Annotated[
            str,
            typer.Option(
                "--evidence-locator",
                help=tr(
                    "cli.app.modelo.iva_wallet.override_evidence_locator_help",
                    default=(
                        "Required locator of the evidence supporting the override (e.g. prior justificante reference)."
                    ),
                ),
            ),
        ],
        confirm: Annotated[
            bool,
            typer.Option(
                "--confirm",
                "--yes",
                help=tr(
                    "cli.app.modelo.iva_wallet.override_confirm_help",
                    default=(
                        "Required confirmation flag. Acknowledge that this override changes the filed "
                        "`iva.compensacion-pendiente-periodos-anteriores` figure and filing accuracy depends "
                        "on the value supplied."
                    ),
                ),
            ),
        ] = False,
    ) -> None:
        """Record an explicit taxpayer override releasing the M303 prior-compensación carry."""
        if not confirm:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.iva_wallet.override_confirm_required",
                    default=(
                        "Pass --confirm to acknowledge: this records a taxpayer override of the M303 "
                        "prior-compensación carry. Filing accuracy depends on the value supplied."
                    ),
                ),
            )

        clean_reason = reason.strip()
        if not clean_reason:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.iva_wallet.override_reason_required",
                    default="--reason must not be blank; record the basis for the override.",
                ),
            )
        clean_locator = evidence_locator.strip()
        if not clean_locator:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.iva_wallet.override_evidence_locator_required",
                    default="--evidence-locator must not be blank; record where the override's evidence lives.",
                ),
            )

        override_amount = _wallet_amount(amount)

        filing_period = Period.from_year_and_code(filing_year, period)
        try:
            decision = record_iva_compensation_override_for_bucket(
                bucket_id=active_bucket_id(),
                period=filing_period,
                amount=override_amount,
                reason=clean_reason,
                evidence_locator=clean_locator,
            )
        except ModeloIvaWalletSeedNegativeAmountError as exc:
            assert exc.translated_message is not None
            raise typer.BadParameter(tr(exc.translated_message, default="Amount must be non-negative.")) from exc
        except ModeloIvaWalletSeedNoTaxpayerError as exc:
            assert exc.translated_message is not None
            raise typer.BadParameter(
                tr(
                    exc.translated_message,
                    default="Active profile has no identity.tax_id configured. Set it via config profile.",
                ),
            ) from exc

        selected_amount = getattr(decision, "selected_amount", None)
        override_result = IvaWalletOverrideResult(
            filing_year=filing_year,
            period=filing_period,
            taxpayer_nif=str(getattr(decision, "taxpayer_nif", "")),
            amount=str(selected_amount if selected_amount is not None else override_amount),
            reason=clean_reason,
            evidence_locator=clean_locator,
            selected_authority=str(getattr(decision, "selected_authority", "taxpayer_override")),
            divergence=str(getattr(decision, "divergence", "override")),
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
        _emit_envelope(ctx, command="modelo.iva_wallet.override", result=override_result, lines=lines)


def _load_existing_seeded_period(bucket_id: str, period: Period):
    """Return the stored period state before correction, or ``None`` when absent."""
    from ...application.calculations import IvaCompensationHistoryRepository

    del bucket_id  # repository is profile-active scoped; bucket binding is implicit
    return IvaCompensationHistoryRepository().load_period(period)


__all__ = ["register_iva_wallet_commands"]
