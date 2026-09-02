"""Scratch conversion helper for the production-assert retirement batch."""

from __future__ import annotations

import pathlib

WALLET = "src/cadrumo/entrypoints/cli/_modelo_iva_wallet_cli.py"


def sub(name: str, old: str, new: str, count: int = 1) -> None:
    path = pathlib.Path(name)
    text = path.read_text(encoding="utf-8")
    if text.count(old) != count:
        raise SystemExit(f"{name}: {text.count(old)} matches (want {count}) for {old[:70]!r}")
    path.write_text(text.replace(old, new, count), encoding="utf-8")


# The three refusals below all carry their own translation key and every
# interpolation value the CLI used to pass by hand, so the canonical resolver
# renders the same sentence from one home.
sub(
    WALLET,
    """    except ModeloIvaWalletSeedNegativeAmountError as exc:
        assert exc.translated_message is not None
        raise typer.BadParameter(tr(exc.translated_message, default="Amount must be non-negative.")) from exc
""",
    """    except ModeloIvaWalletSeedNegativeAmountError as exc:
        raise typer.BadParameter(resolve_error_message(exc)) from exc
""",
    count=3,
)

sub(
    WALLET,
    """    except ModeloIvaWalletCorrectionNoRecordError as exc:
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
""",
    """    except ModeloIvaWalletCorrectionNoRecordError as exc:
        raise typer.BadParameter(resolve_error_message(exc)) from exc
    except ModeloIvaWalletCorrectionSealedError as exc:
        raise typer.BadParameter(resolve_error_message(exc)) from exc
""",
)

sub(
    WALLET,
    """    assert state.taxpayer_nif is not None, "seeded IVA wallet state must retain its taxpayer NIF"
""",
    """    if state.taxpayer_nif is None:
        raise ModeloError(
            f"seeded IVA wallet state for {state.filing_year}/{state.period} retains no taxpayer NIF",
        )
""",
)

sub(
    WALLET,
    """    assert state.taxpayer_nif is not None, "corrected IVA wallet state must retain its taxpayer NIF"
""",
    """    if state.taxpayer_nif is None:
        raise ModeloError(
            f"corrected IVA wallet state for {state.filing_year}/{state.period} retains no taxpayer NIF",
        )
""",
)

sub(
    WALLET,
    """from ...core.i18n.render import tr""",
    """from ...core.errors.error_codes import resolve_error_message
from ...core.i18n.render import tr""",
)

sub(
    WALLET,
    """from ...domain.iva_compensation.errors import IvaCompensationSeedConflictError""",
    """from ...domain.iva_compensation.errors import IvaCompensationSeedConflictError
from ...domain.modelos.errors import ModeloError""",
)

print("ok")
