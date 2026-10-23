"""Canonical transaction detail screen for Ledger.

The screen reads one transaction through the registered view operation and
corrects it through the registered update operation against the projection
the operator saw. A correction is staged and shown field by field before it is
saved; only the staged fields are sent.
"""

from __future__ import annotations

from typing import Final, cast, get_args, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Select, Static

from ....application.ledger.actions_common import display_decimal
from ....application.ledger.transaction_projection import LedgerTransactionProjection
from ....application.ledger.update_contracts import LedgerUpdatePatch, LedgerUpdatePatchField
from ....core.decimal.grammar import try_parse_canonical_decimal
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....domain.transactions.enums import TransactionDirection
from ..components.language import localized
from ..components.theme import tokenised
from ..operations.outcome import OperationOutcomeUnknownError
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from .models import LedgerRecordDoorsV1
from .workspace_presentation import door_refusal_text, ledger_workspace_page

_TEXT_FIELDS: Final[tuple[LedgerUpdatePatchField, ...]] = (
    "description",
    "counterparty",
    "booked_date",
    "value_date",
    "amount",
    "currency",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "notes",
)
"""Correctable text fields the projection carries, in the order the form shows them."""
_OPTIONAL_FIELDS: Final = frozenset({"counterparty", "value_date", "taxable_base", "iva_rate", "iva_amount"})
"""Fields a blank entry clears; the rest are facts every transaction keeps."""
_DECIMAL_FIELDS: Final = frozenset({"amount", "taxable_base", "iva_rate", "iva_amount"})
"""Fields the update carries as canonical decimal text, which drops trailing zeros."""
_EDIT_CONTROLS: Final = (
    *(f"#ledger-transaction-{name.replace('_', '-')}" for name in _TEXT_FIELDS),
    "#ledger-transaction-direction",
)


def _field_label(name: str) -> str:
    return tr(f"tui.ledger.records.transaction_field.{name}")


def _direction_label(direction: str) -> str:
    return tr(f"tui.ledger.records.direction.{direction.lower()}")


def _current(transaction: LedgerTransactionProjection, name: str) -> str:
    value = getattr(transaction, name)
    return "" if value is None else str(value)


class LedgerTransactionDetailScreen(LedgerWorkspaceScreen):
    """Read and correct one transaction through the registered view and update operations."""

    DEFAULT_CSS = tokenised(
        """
        .ledger-transaction-actions { height: auto; margin-bottom: $cadrumo-stack; }
        .ledger-transaction-actions Button { margin-right: $cadrumo-space-1; }
        #ledger-transaction-staged { height: auto; text-style: bold; }
        """
    )

    def __init__(self, controller: LedgerWorkspaceController, doors: LedgerRecordDoorsV1, transaction_id: str) -> None:
        """Capture the selected transaction identity and bound doors."""
        super().__init__(controller, id="ledger-transaction-detail-screen")
        self.doors = doors
        self.transaction_id = transaction_id
        self.baseline: LedgerTransactionProjection | None = None
        self.staged: tuple[LedgerUpdatePatch, tuple[LedgerUpdatePatchField, ...]] | None = None
        self._busy = False

    @property
    @override
    def in_flight(self) -> bool:
        """The transaction read or its correction is out through a door."""
        return self._busy

    @override
    def compose(self) -> ComposeResult:
        yield localized(
            Static(tr("tui.ledger.records.transaction_detail"), classes="cadrumo-banner"),
            "tui.ledger.records.transaction_detail",
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static("", id="ledger-record-detail", markup=False)
            yield Static("", id="ledger-transaction-staged", markup=False)
            with Horizontal(id="ledger-transaction-decision", classes="ledger-transaction-actions"):
                yield localized(
                    Button(tr("tui.ledger.records.save"), id="ledger-transaction-edit-save", variant="primary"),
                    "tui.ledger.records.save",
                )
                yield localized(
                    Button(tr("tui.ledger.records.cancel"), id="ledger-transaction-edit-cancel"),
                    "tui.ledger.records.cancel",
                )
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
            yield localized(
                Static(tr("tui.ledger.records.correct_heading"), classes="cadrumo-heading", markup=False),
                "tui.ledger.records.correct_heading",
            )
            for name in _TEXT_FIELDS:
                key = f"tui.ledger.records.transaction_field.{name}"
                yield localized(Static(tr(key), markup=False), key)
                yield Input(id=f"ledger-transaction-{name.replace('_', '-')}", disabled=True)
            yield localized(
                Static(_field_label("direction"), markup=False), "tui.ledger.records.transaction_field.direction"
            )
            yield Select[str](
                tuple((_direction_label(item.value), item.value) for item in TransactionDirection),
                allow_blank=False,
                value=TransactionDirection.OUTGOING.value,
                id="ledger-transaction-direction",
                disabled=True,
            )
            with Horizontal(classes="ledger-transaction-actions"):
                yield localized(
                    Button(tr("tui.ledger.invoice.review"), id="ledger-transaction-edit-review", disabled=True),
                    "tui.ledger.invoice.review",
                )

    def on_mount(self) -> None:
        """Read the transaction before enabling its correction form."""
        self.populate_navigation()
        self.query_one("#ledger-transaction-decision", Horizontal).display = False
        self._busy = True
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        status.update(tr("tui.ledger.records.loading"))
        try:
            transaction = await self.doors.transaction(self.transaction_id)
        except CadrumoError as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            status.update(tr("tui.ledger.records.failed"))
        else:
            self._show_transaction(transaction)
            status.update("")
        finally:
            self._busy = False

    def _entered(self, name: str) -> str:
        value = self.query_one(f"#ledger-transaction-{name.replace('_', '-')}", Input).value
        if name == "notes":
            return value
        value = value.strip()
        if name in _DECIMAL_FIELDS and value:
            # 100.00 is the canonical 100; text that is no number is left for the update to refuse.
            parsed = try_parse_canonical_decimal(value, signed=name != "amount")
            if parsed is not None:
                return display_decimal(parsed)
        return value

    def _stage(self, baseline: LedgerTransactionProjection) -> None:
        refusal = self.query_one("#ledger-refusal", Static)
        refusal.update("")
        changes: dict[str, str | None] = {}
        for name in _TEXT_FIELDS:
            entered = self._entered(name)
            if entered != _current(baseline, name):
                changes[name] = None if not entered and name in _OPTIONAL_FIELDS else entered
        direction = str(cast("Select[str]", self.query_one("#ledger-transaction-direction", Select)).value)
        if direction != baseline.direction:
            changes["direction"] = direction
        if not changes:
            refusal.update(tr("tui.ledger.records.no_change"))
            return
        fields = tuple(name for name in get_args(LedgerUpdatePatchField) if name in changes)
        try:
            patch = LedgerUpdatePatch.model_validate(changes)
        except ValidationError as error:
            refusal.update(door_refusal_text(error))
            return
        self.staged = (patch, fields)
        lines = [
            tr(
                "tui.ledger.records.change",
                field=_field_label(name),
                before=(
                    _direction_label(baseline.direction) if name == "direction" else _current(baseline, name) or "-"
                ),
                after=_direction_label(direction) if name == "direction" else changes[name] or "-",
            )
            for name in fields
        ]
        self.query_one("#ledger-transaction-staged", Static).update(
            "\n".join((tr("tui.ledger.records.staged_heading"), *lines))
        )
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.reviewed"))
        self._set_staged_controls(staged=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Stage a correction, then save exactly the staged fields once."""
        if self._busy:
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.flow.in_flight_refusal"))
            return
        if self.baseline is None:
            return
        if event.button.id == "ledger-transaction-edit-review":
            self._stage(self.baseline)
        elif event.button.id == "ledger-transaction-edit-cancel":
            self._unstage()
        elif event.button.id == "ledger-transaction-edit-save" and self.staged is not None:
            self._busy = True
            self.query_one("#ledger-transaction-edit-save", Button).disabled = True
            self.query_one("#ledger-transaction-edit-cancel", Button).disabled = True
            patch, fields = self.staged
            self.run_worker(self._save(self.baseline, patch, fields), exclusive=True)

    async def _save(
        self,
        baseline: LedgerTransactionProjection,
        patch: LedgerUpdatePatch,
        fields: tuple[LedgerUpdatePatchField, ...],
    ) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        status.update(tr("tui.ledger.records.saving"))
        try:
            updated = await self.doors.update_transaction(baseline, patch, fields)
        except CadrumoError as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            status.update(self.failed_write_status(error, "tui.ledger.records.failed"))
            self._busy = False
            if isinstance(error, OperationOutcomeUnknownError):
                # The correction may be saved; offering it again could apply it twice.
                self._unstage()
                return
            self.query_one("#ledger-transaction-edit-save", Button).disabled = False
            self.query_one("#ledger-transaction-edit-cancel", Button).disabled = False
            return
        self._busy = False
        self._unstage()
        self._show_transaction(updated)
        status.update(tr("tui.ledger.records.saved"))

    def _show_transaction(self, transaction: LedgerTransactionProjection) -> None:
        """Render one projection and prefill the form with its current values."""
        self.baseline = transaction
        self.transaction_id = transaction.transaction_id
        self.query_one("#ledger-record-detail", Static).update(
            "\n".join(
                (
                    f"{transaction.booked_date} · {transaction.description}",
                    f"{_direction_label(transaction.direction)} · {transaction.amount} {transaction.currency}",
                    f"{_field_label('counterparty')}: {transaction.counterparty or '-'}",
                    f"{tr('tui.ledger.records.links')}: {transaction.invoice_id or '-'}",
                    f"{tr('tui.ledger.records.identity')}: {transaction.transaction_id}",
                )
            )
        )
        for name in _TEXT_FIELDS:
            self.query_one(f"#ledger-transaction-{name.replace('_', '-')}", Input).value = _current(transaction, name)
        cast("Select[str]", self.query_one("#ledger-transaction-direction", Select)).value = transaction.direction
        self._set_staged_controls(staged=False)

    def _set_staged_controls(self, *, staged: bool) -> None:
        """Freeze the form while a correction is staged, so only the reviewed fields are saved."""
        for selector in _EDIT_CONTROLS:
            self.query_one(selector).disabled = staged
        self.query_one("#ledger-transaction-edit-review", Button).disabled = staged
        self.query_one("#ledger-transaction-edit-save", Button).disabled = not staged
        self.query_one("#ledger-transaction-edit-cancel", Button).disabled = not staged
        self.query_one("#ledger-transaction-decision", Horizontal).display = staged

    def _unstage(self) -> None:
        self.staged = None
        self.query_one("#ledger-transaction-staged", Static).update("")
        self._set_staged_controls(staged=False)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Answer the area navigation, which keeps a pending write on this screen."""
        self.handle_navigation_selection(event)


__all__ = ["LedgerTransactionDetailScreen"]
