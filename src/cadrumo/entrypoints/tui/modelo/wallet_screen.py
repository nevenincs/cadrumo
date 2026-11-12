"""The IVA compensation balance dialog: the balance as served, and the three recordings a filer can make about it.

The dialog reads the balance for a reference year and draws every figure as the
application released it, with the labels the product's catalogue gives them. A
read in flight, a read that failed and a read the application refused are three
different states, and none of them is drawn as a balance of zero. A balance read
before a recording is not shown after one: the dialog reads it again.

A recording states an opening balance, corrects one or replaces the carry by
hand. Whether it is admitted is the application's decision; a refusal is drawn
by the shared refusal slot in the words it was served, and changed nothing. A
recording whose outcome is unknown is never sent again from this dialog: the
filer reads the balance again and decides.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import ClassVar, Final, Literal, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from ....application.modelo.iva_wallet_balance_operation import ModeloIvaWalletBalanceProjection
from ....application.modelo.iva_wallet_correction_operation import ModeloIvaWalletCorrectionProjection
from ....application.modelo.iva_wallet_override_operation import ModeloIvaWalletOverrideProjection
from ....application.modelo.value_presentation import format_casilla_value
from ....application.modelo.work_form_models import ModeloWorkForm
from ....application.modelo.work_form_wording import period_words
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import output_language, tr
from ....core.logging import get_logger
from ..components.language import localized, refresh_localized_widgets
from ..components.theme import tokenised
from ..refusal.panel import RefusalSlot
from .wallet import (
    IvaWalletActionKind,
    IvaWalletEntryV1,
    IvaWalletNotSentError,
    IvaWalletReceiptV1,
    IvaWalletRefusedError,
    ModeloIvaWalletDoorV1,
)
from .workbench.dialog_width import fit_dialog_height, fit_dialog_width
from .workbench.keys import describe_bindings

_PREFIX: Final = "workspace.modelo.iva_wallet"
TITLE_LOCALE_KEY: Final = f"{_PREFIX}.title"
LEAD_LOCALE_KEY: Final = f"{_PREFIX}.lead"
LOADING_LOCALE_KEY: Final = f"{_PREFIX}.loading"
READ_FAILED_LOCALE_KEY: Final = f"{_PREFIX}.read_failed"
RELOAD_LOCALE_KEY: Final = f"{_PREFIX}.reload"
AS_OF_YEAR_LOCALE_KEY: Final = f"{_PREFIX}.as_of_year"
ACTION_LOCALE_KEY: Final = f"{_PREFIX}.action"
AMOUNT_LOCALE_KEY: Final = f"{_PREFIX}.amount"
REASON_LOCALE_KEY: Final = f"{_PREFIX}.reason"
EVIDENCE_LOCALE_KEY: Final = f"{_PREFIX}.evidence_locator"
RECORDED_LOCALE_KEY: Final = f"{_PREFIX}.recorded"
EXPIRY_NOT_REPORTED_LOCALE_KEY: Final = f"{_PREFIX}.expiry_not_reported"
PREVIOUS_AMOUNT_LOCALE_KEY: Final = f"{_PREFIX}.previous_amount"
NOT_REPORTED_LOCALE_KEY: Final = f"{_PREFIX}.receipt.not_reported"
SOURCE_LOCALE_KEY: Final = f"{_PREFIX}.receipt.source"
REGISTER_STATUS_LOCALE_KEY: Final = f"{_PREFIX}.receipt.register_status"
SELECTED_SOURCE_LOCALE_KEY: Final = f"{_PREFIX}.receipt.selected_source"
OUTCOME_LOCALE_KEY: Final = f"{_PREFIX}.receipt.reconciliation_outcome"
PERIOD_LOCALE_KEY: Final = "workspace.declarations.list.column.period"
CLOSE_LOCALE_KEY: Final = "workspace.modelo.key.close"
BACK_LOCALE_KEY: Final = "workspace.modelo.key.back"

#: The dialog's own words, written once for the catalogue; every other sentence on it is served or the product's.
SENDING_LOCALE_KEY: Final = "tui.modelo.wallet.sending"
UNKNOWN_LOCALE_KEY: Final = "tui.modelo.wallet.outcome_unknown"
REFUSED_LOCALE_KEY: Final = "tui.modelo.wallet.refused"
NOT_SENT_LOCALE_KEY: Final = "tui.modelo.wallet.not_sent"
YEAR_LOCALE_KEY: Final = "tui.modelo.wallet.year_label"
CODE_LOCALE_KEY: Final = "tui.modelo.wallet.code_label"
NO_LOTS_LOCALE_KEY: Final = "tui.modelo.wallet.no_lots"

_KEY_DESCRIPTIONS: Final[dict[str, str]] = {"escape": BACK_LOCALE_KEY}
_MODES: Final = (IvaWalletActionKind.SEED, IvaWalletActionKind.CORRECT, IvaWalletActionKind.OVERRIDE)
_MODE_PREFIX: Final = "mode-"
_RECEIPT_WORDS: Final[dict[str, str]] = {
    "operator_seed": f"{_PREFIX}.receipt.provenance.operator_seed",
    "operator_correction": f"{_PREFIX}.receipt.provenance.operator_correction",
    "taxpayer_override": f"{_PREFIX}.receipt.authority.taxpayer_override",
    "override": f"{_PREFIX}.receipt.divergence.override",
}

type BalancePhase = Literal["reading", "ready", "failed", "refused"]


def mode_label_key(kind: IvaWalletActionKind) -> str:
    """The catalogue key naming a recording."""
    return f"{_PREFIX}.mode.{kind.value}"


def mode_help_key(kind: IvaWalletActionKind) -> str:
    """The catalogue key explaining what a recording states."""
    return f"{_PREFIX}.help.{kind.value}"


def written_amount(text: str, language: OutputLanguage) -> str:
    """A served amount written as a box writes money; text that is not a number stays as served."""
    try:
        value = Decimal(text)
    except InvalidOperation:
        return text
    return format_casilla_value(value, data_type="money", language=language)


def balance_lines(balance: ModeloIvaWalletBalanceProjection, language: OutputLanguage) -> tuple[str, ...]:
    """The released balance facts, each with the catalogue's label for it, in the application's field order."""

    def line(name: str, value: str) -> str:
        return f"{tr(f'{_PREFIX}.{name}')}: {value}"

    expiry = tr(EXPIRY_NOT_REPORTED_LOCALE_KEY) if balance.next_expiry_year is None else str(balance.next_expiry_year)
    return (
        line("total_balance", written_amount(balance.total_balance, language)),
        line("active_balance", written_amount(balance.active_balance, language)),
        line("expired_balance", written_amount(balance.expired_balance, language)),
        line("lot_count", str(balance.lot_count)),
        line("next_expiry_year", expiry),
        line("unallocated_applied_amount", written_amount(balance.unallocated_applied_amount, language)),
    )


def receipt_lines(receipt: IvaWalletReceiptV1, language: OutputLanguage) -> tuple[str, ...]:
    """What a recording came back with: period, amounts, reason, evidence, source, outcome, as released."""

    def worded(value: str) -> str:
        key = _RECEIPT_WORDS.get(value)
        return value if key is None else tr(key)

    lines = [
        tr(RECORDED_LOCALE_KEY),
        f"{tr(PERIOD_LOCALE_KEY)}: {period_words(receipt.period.to_period(), language)}",
        f"{tr(AMOUNT_LOCALE_KEY)}: {written_amount(receipt.amount, language)}",
    ]
    if isinstance(receipt, ModeloIvaWalletCorrectionProjection):
        lines.append(f"{tr(PREVIOUS_AMOUNT_LOCALE_KEY)}: {written_amount(receipt.previous_amount, language)}")
    if isinstance(receipt, ModeloIvaWalletCorrectionProjection | ModeloIvaWalletOverrideProjection):
        lines.append(f"{tr(REASON_LOCALE_KEY)}: {receipt.reason}")
    if isinstance(receipt, ModeloIvaWalletOverrideProjection):
        lines.append(f"{tr(EVIDENCE_LOCALE_KEY)}: {receipt.evidence_locator}")
    else:
        lines.append(f"{tr(SOURCE_LOCALE_KEY)}: {worded(receipt.provenance.value)}")
        # The application releases no register status for a local recording.
        lines.append(f"{tr(REGISTER_STATUS_LOCALE_KEY)}: {tr(NOT_REPORTED_LOCALE_KEY)}")
    if isinstance(receipt, ModeloIvaWalletOverrideProjection):
        lines.append(f"{tr(SELECTED_SOURCE_LOCALE_KEY)}: {worded(receipt.selected_authority)}")
        lines.append(f"{tr(OUTCOME_LOCALE_KEY)}: {worded(receipt.divergence)}")
    return tuple(lines)


class ModeloIvaWalletScreen(ModalScreen[str | None]):
    """Read the profile's IVA balance for a year and record what the filer states about it.

    Closing returns the sentence for a recording that was stored or may have
    been, so the workbench can read the declaration again and say it; ``None``
    when nothing was recorded.
    """

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        ModeloIvaWalletScreen #wallet-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        ModeloIvaWalletScreen #wallet-panel {
            width: $cadrumo-modal-width;
            height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        ModeloIvaWalletScreen.-narrow #wallet-panel {
            width: 100%;
        }
        ModeloIvaWalletScreen.-short #wallet-panel {
            height: 100%;
        }
        ModeloIvaWalletScreen #wallet-title {
            text-style: bold;
            color: $foreground;
        }
        ModeloIvaWalletScreen #wallet-lead,
        ModeloIvaWalletScreen #wallet-help {
            height: auto;
            color: $secondary;
        }
        ModeloIvaWalletScreen #wallet-status,
        ModeloIvaWalletScreen #wallet-balance,
        ModeloIvaWalletScreen #wallet-receipt {
            height: auto;
        }
        ModeloIvaWalletScreen #wallet-note {
            height: auto;
            color: $warning;
        }
        ModeloIvaWalletScreen #wallet-modes {
            height: auto;
            max-height: $cadrumo-choice-list-max-height;
        }
        ModeloIvaWalletScreen #wallet-actions {
            height: auto;
            margin-top: $cadrumo-stack;
            align-horizontal: right;
        }
        """
    )

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]

    def __init__(self, door: ModeloIvaWalletDoorV1, *, form: ModeloWorkForm) -> None:
        """Bind the door, and open on the declaration's own year and period."""
        super().__init__()
        self._door = door
        self._year = form.filing_year
        self._code = form.period.registry_token
        self._language = OutputLanguage(output_language())
        self._phase: BalancePhase = "reading"
        self._balance: ModeloIvaWalletBalanceProjection | None = None
        self._mode = IvaWalletActionKind.SEED
        self._receipt: IvaWalletReceiptV1 | None = None
        self._busy = False
        self._held = False
        self._stored = False
        self._said = ""
        self._reads = 0

    @property
    def phase(self) -> BalancePhase:
        """Where the balance read stands."""
        return self._phase

    @override
    def compose(self) -> ComposeResult:
        with Container(id="wallet-backdrop"), Vertical(id="wallet-panel"):
            yield localized(Static(tr(TITLE_LOCALE_KEY), id="wallet-title", markup=False), TITLE_LOCALE_KEY)
            with VerticalScroll(id="wallet-body"):
                yield localized(Static(tr(LEAD_LOCALE_KEY), id="wallet-lead", markup=False), LEAD_LOCALE_KEY)
                yield localized(
                    Static(tr(AS_OF_YEAR_LOCALE_KEY), classes="wallet-label", markup=False), AS_OF_YEAR_LOCALE_KEY
                )
                yield Input(value=str(self._year), type="integer", id="wallet-as-of")
                yield localized(Button(tr(RELOAD_LOCALE_KEY), id="wallet-reload"), RELOAD_LOCALE_KEY)
                yield Static(id="wallet-status", markup=False)
                yield Static(id="wallet-balance", markup=False)
                yield RefusalSlot(id="wallet-read-refusal")
                yield localized(Static(tr(ACTION_LOCALE_KEY), classes="wallet-label", markup=False), ACTION_LOCALE_KEY)
                yield OptionList(
                    *(Option(tr(mode_label_key(mode)), id=f"{_MODE_PREFIX}{mode.value}") for mode in _MODES),
                    id="wallet-modes",
                )
                yield Static(id="wallet-help", markup=False)
                yield localized(Static(tr(YEAR_LOCALE_KEY), classes="wallet-label", markup=False), YEAR_LOCALE_KEY)
                yield Input(value=str(self._year), type="integer", id="wallet-period-year")
                yield localized(Static(tr(CODE_LOCALE_KEY), classes="wallet-label", markup=False), CODE_LOCALE_KEY)
                yield Input(value=self._code, id="wallet-period-code")
                yield localized(Static(tr(AMOUNT_LOCALE_KEY), classes="wallet-label", markup=False), AMOUNT_LOCALE_KEY)
                yield Input(id="wallet-amount")
                yield localized(
                    Static(tr(REASON_LOCALE_KEY), id="wallet-reason-label", markup=False), REASON_LOCALE_KEY
                )
                yield Input(id="wallet-reason")
                yield localized(
                    Static(tr(EVIDENCE_LOCALE_KEY), id="wallet-evidence-label", markup=False), EVIDENCE_LOCALE_KEY
                )
                yield Input(id="wallet-evidence")
                yield Static(id="wallet-note", markup=False)
                yield RefusalSlot(id="wallet-refusal")
                yield Static(id="wallet-receipt", markup=False)
            with Horizontal(id="wallet-actions"):
                yield Button(id="wallet-submit", variant="primary")
                yield localized(Button(tr(CLOSE_LOCALE_KEY), id="wallet-close"), CLOSE_LOCALE_KEY)
        yield Footer(compact=True)

    def on_mount(self) -> None:
        """Draw the dialog, then read the balance for the declaration's year."""
        fit_dialog_width(self, self.app.size.width)
        fit_dialog_height(self, self.app.size.height)
        describe_bindings(self._bindings.key_to_bindings, _KEY_DESCRIPTIONS)
        self.refresh_bindings()
        self.query_one("#wallet-modes", OptionList).highlighted = 0
        self._paint()
        self._read_balance()
        self.query_one("#wallet-as-of", Input).focus()

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal and the whole height on a short one."""
        fit_dialog_width(self, event.size.width)
        fit_dialog_height(self, event.size.height)

    async def refresh_language(self) -> None:
        """Reword the chrome and the released figures; a read is made again so nothing stays in the old language."""
        refresh_localized_widgets(self)
        describe_bindings(self._bindings.key_to_bindings, _KEY_DESCRIPTIONS)
        self._language = OutputLanguage(output_language())
        modes = self.query_one("#wallet-modes", OptionList)
        for mode in _MODES:
            modes.replace_option_prompt(f"{_MODE_PREFIX}{mode.value}", tr(mode_label_key(mode)))
        self._paint()

    # -- reading ---------------------------------------------------------------

    def _as_of_year(self) -> int | None:
        text = self.query_one("#wallet-as-of", Input).value.strip()
        return int(text) if text.lstrip("-").isdigit() else None

    def _read_balance(self) -> None:
        """Read the balance again; an answer is the latest question's only."""
        year = self._as_of_year()
        self._reads += 1
        self.query_one("#wallet-read-refusal", RefusalSlot).show(None)
        self._balance = None
        if year is None:
            self._phase = "failed"
            self._paint()
            return
        self._phase = "reading"
        self._paint()
        self.run_worker(partial(self._read, self._reads, year), group="wallet-read", exclusive=True)

    async def _read(self, ticket: int, year: int) -> None:
        balance: ModeloIvaWalletBalanceProjection | None = None
        refusal = None
        phase: BalancePhase = "failed"
        try:
            balance = await asyncio.to_thread(self._door.read_balance, year)
            phase = "ready"
        except IvaWalletRefusedError as refused:
            refusal, phase = refused.refusal, "refused"
        except Exception as failure:
            get_logger(__name__).warning("the IVA balance could not be read: %s", type(failure).__qualname__)
        if ticket != self._reads:
            return
        self._balance, self._phase = balance, phase
        self.query_one("#wallet-read-refusal", RefusalSlot).show(refusal)
        self._paint()

    # -- drawing ---------------------------------------------------------------

    def _paint(self) -> None:
        status = self.query_one("#wallet-status", Static)
        said = {"reading": tr(LOADING_LOCALE_KEY), "failed": tr(READ_FAILED_LOCALE_KEY)}.get(self._phase, "")
        status.update(said)
        status.display = bool(said)
        lines: tuple[str, ...] = ()
        if self._phase == "ready" and self._balance is not None:
            lines = balance_lines(self._balance, self._language)
            if self._balance.lot_count == 0:
                lines = (*lines, tr(NO_LOTS_LOCALE_KEY))
        balance = self.query_one("#wallet-balance", Static)
        balance.update("\n".join(lines))
        balance.display = bool(lines)
        self.query_one("#wallet-help", Static).update(tr(mode_help_key(self._mode)))
        self.query_one("#wallet-reason-label").display = self._mode is not IvaWalletActionKind.SEED
        self.query_one("#wallet-reason").display = self._mode is not IvaWalletActionKind.SEED
        self.query_one("#wallet-evidence-label").display = self._mode is IvaWalletActionKind.OVERRIDE
        self.query_one("#wallet-evidence").display = self._mode is IvaWalletActionKind.OVERRIDE
        note = self.query_one("#wallet-note", Static)
        note.update(tr(SENDING_LOCALE_KEY) if self._busy else tr(UNKNOWN_LOCALE_KEY) if self._held else self._said)
        receipt = self.query_one("#wallet-receipt", Static)
        receipt_text = "" if self._receipt is None else "\n".join(receipt_lines(self._receipt, self._language))
        receipt.update(receipt_text)
        receipt.display = bool(receipt_text)
        submit = self.query_one("#wallet-submit", Button)
        submit.label = tr(mode_label_key(self._mode))
        submit.disabled = not self._may_send()
        self.query_one("#wallet-reload", Button).disabled = self._phase == "reading"
        self.refresh_bindings()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Choose the recording under the cursor; a receipt of another recording no longer stands."""
        option_id = event.option.id or ""
        kind = next((mode for mode in _MODES if option_id == f"{_MODE_PREFIX}{mode.value}"), None)
        if kind is None or kind is self._mode:
            return
        self._mode, self._receipt, self._said = kind, None, ""
        self._paint()

    # -- recording -------------------------------------------------------------

    def _complete(self) -> bool:
        def given(selector: str) -> bool:
            return bool(self.query_one(selector, Input).value.strip())

        return (
            given("#wallet-period-year")
            and given("#wallet-period-code")
            and given("#wallet-amount")
            and (self._mode is IvaWalletActionKind.SEED or given("#wallet-reason"))
            and (self._mode is not IvaWalletActionKind.OVERRIDE or given("#wallet-evidence"))
        )

    def _may_send(self) -> bool:
        return not (self._busy or self._held or self._receipt is not None) and self._complete()

    def on_input_changed(self, event: Input.Changed) -> None:
        """A changed entry is a new recording: the last receipt no longer describes it."""
        if event.input.id == "wallet-as-of":
            return
        self._receipt, self._said = None, ""
        self._paint()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Read on Enter in the year box; record on Enter in any other."""
        event.stop()
        if event.input.id == "wallet-as-of":
            self._read_balance()
        else:
            self._send()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route the dialog's three buttons."""
        event.stop()
        if event.button.id == "wallet-reload":
            self._read_balance()
        elif event.button.id == "wallet-submit":
            self._send()
        else:
            self.action_close()

    def _entry(self) -> IvaWalletEntryV1 | None:
        year = self.query_one("#wallet-period-year", Input).value.strip()
        if not year.lstrip("-").isdigit():
            return None
        return IvaWalletEntryV1(
            kind=self._mode,
            filing_year=int(year),
            period_code=self.query_one("#wallet-period-code", Input).value.strip(),
            amount=self.query_one("#wallet-amount", Input).value.strip(),
            reason=self.query_one("#wallet-reason", Input).value.strip() if self._mode is not _MODES[0] else "",
            evidence_locator=(
                self.query_one("#wallet-evidence", Input).value.strip() if self._mode is _MODES[2] else ""
            ),
        )

    def _send(self) -> None:
        if not self._may_send():
            return
        entry = self._entry()
        self._said = ""
        self.query_one("#wallet-refusal", RefusalSlot).show(None)
        if entry is None:
            self._said = tr(NOT_SENT_LOCALE_KEY)
            self._paint()
            return
        self._busy = True
        self._paint()
        self.run_worker(partial(self._record, entry), group="wallet-send")

    async def _record(self, entry: IvaWalletEntryV1) -> None:
        slot = self.query_one("#wallet-refusal", RefusalSlot)
        try:
            receipt = await asyncio.to_thread(self._door.record, entry)
        except IvaWalletNotSentError:
            self._busy, self._said = False, tr(NOT_SENT_LOCALE_KEY)
            self._paint()
            return
        except IvaWalletRefusedError as refused:
            self._busy = False
            if refused.refusal is None:
                self._said = tr(REFUSED_LOCALE_KEY)
            else:
                slot.show(refused.refusal)
            self._paint()
            return
        except Exception as failure:
            # The recording may have been stored: say so, send nothing more from here, and show what is stored.
            get_logger(__name__).warning(
                "an IVA balance recording's outcome is unknown: %s", type(failure).__qualname__
            )
            self._busy, self._held = False, True
            self._read_balance()
            return
        self._busy, self._stored, self._receipt = False, True, receipt
        # The balance read before the recording is stale now.
        self._read_balance()

    # -- leaving ---------------------------------------------------------------

    def action_close(self) -> None:
        """Close, saying the recording was stored or may have been; never while one is being sent."""
        if self._busy:
            return
        if self._held:
            self.dismiss(tr(UNKNOWN_LOCALE_KEY))
        elif self._stored:
            self.dismiss(tr(RECORDED_LOCALE_KEY))
        else:
            self.dismiss(None)


__all__ = [
    "ModeloIvaWalletScreen",
    "balance_lines",
    "mode_help_key",
    "mode_label_key",
    "receipt_lines",
    "written_amount",
]
