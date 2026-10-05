"""Own bank account setup in the Ledger workspace.

The screen lists the taxpayer's own accounts masked, shows one in detail, stages
an add, edit, close, removal or role designation for review, and submits only the reviewed request
through the injected own-account door. Account numbers are typed into secret
inputs and cleared once a request settles; nothing on the screen ever shows
more than the country code and last four characters.
"""

from __future__ import annotations

from typing import Protocol, cast, override
from uuid import UUID

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Select, Static

from ....application.ledger.own_account_operation import (
    LedgerOwnAccountRequest,
    LedgerOwnAccountResult,
    OwnAccountDesignationProjection,
    OwnAccountProjection,
)
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.iban import mask_iban
from ....core.parsing.dates import require_iso8601_date, require_iso8601_date_unless_blank
from ....domain.transactions.own_accounts import OwnAccountHolding, OwnAccountRole, OwnBankAccountDetails
from ..account import AccountSessionExpiredError
from ..components.theme import tokenised
from ..components.widgets import ContentDataTable
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from .workspace_presentation import door_refusal_text, ledger_workspace_page

_SECRET_INPUTS = ("#own-account-iban", "#own-account-bic")
_TEXT_INPUTS = (
    "#own-account-label",
    *_SECRET_INPUTS,
    "#own-account-bank-name",
    "#own-account-bank-address",
    "#own-account-bank-city",
    "#own-account-bank-country",
    "#own-account-currency",
    "#own-account-opened-on",
    "#own-account-closed-on",
    "#own-account-modelo",
)
_STAGE_BUTTONS = (
    "own-account-review",
    "own-account-review-close",
    "own-account-review-designate",
    "own-account-review-undesignate",
    "own-account-review-remove",
)


class LedgerOwnAccountDoorV1(Protocol):
    """Injected door to the registered own-account operation of one admitted profile."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door must name."""
        ...

    async def __call__(self, request: LedgerOwnAccountRequest) -> LedgerOwnAccountResult:
        """Submit one request and return its masked, receipt-correlated result."""
        ...


def _blank_to_none(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None


def _role_label(role: OwnAccountRole) -> str:
    return tr(f"tui.ledger.own_accounts.role.{role.value}")


def _scope_label(modelo: str | None) -> str:
    if modelo is None:
        return tr("tui.ledger.own_accounts.scope.all")
    return tr("tui.ledger.own_accounts.scope.modelo", modelo=modelo)


def _designation_label(designation: OwnAccountDesignationProjection) -> str:
    return f"{_role_label(designation.role)} · {_scope_label(designation.modelo)}"


def _change_label(name: str, value: object) -> str:
    """Name one staged change: its new value when it is shown anyway, the field alone when it is account material."""
    field = tr(f"tui.ledger.own_accounts.field_name.{name}")
    if name == "iban":
        return f"{field}: {mask_iban(str(value))}"
    if name in {"swift_bic", "bank_name", "bank_address", "bank_city", "bank_country_code"}:
        return field
    if isinstance(value, OwnAccountHolding):
        return f"{field}: {tr(f'tui.ledger.own_accounts.holding.{value.value}')}"
    return f"{field}: {value}"


def _state_label(account: OwnAccountProjection) -> str:
    if account.closed_on is None:
        return tr("tui.ledger.own_accounts.state.open")
    return tr("tui.ledger.own_accounts.state.closed", date=account.closed_on.isoformat())


class LedgerOwnAccountsScreen(LedgerWorkspaceScreen):
    """List, add, edit, close and designate the taxpayer's own bank accounts."""

    def __init__(self, controller: LedgerWorkspaceController, door: LedgerOwnAccountDoorV1) -> None:
        """Keep the injected profile-bound door for every request this screen submits."""
        super().__init__(controller, id="ledger-own-accounts-screen")
        self.door = door
        self.accounts: tuple[OwnAccountProjection, ...] = ()
        self.designations: tuple[OwnAccountDesignationProjection, ...] = ()
        self.selected_id: str | None = None
        self.staged: LedgerOwnAccountRequest | None = None
        self._busy = False

    DEFAULT_CSS = tokenised(
        """
        .own-account-actions { height: auto; margin-bottom: $cadrumo-stack; }
        .own-account-actions Button { margin-right: $cadrumo-space-1; }
        #own-account-staged { height: auto; text-style: bold; }
        """
    )

    @override
    def compose(self) -> ComposeResult:
        yield Static(tr("tui.ledger.own_accounts.title"), classes="cadrumo-banner")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static(tr("tui.ledger.own_accounts.prompt"), markup=False)
            yield ContentDataTable[str](id="ledger-own-accounts", cursor_type="row", zebra_stripes=True)
            yield Static("", id="own-account-detail", markup=False)
            # The reviewed request, its decision and its outcome sit above the
            # form, so the operator never has to scroll to see what will be sent.
            yield Static("", id="own-account-staged", markup=False)
            with Horizontal(id="own-account-decision", classes="own-account-actions"):
                yield Button(
                    tr("tui.ledger.own_accounts.confirm"), id="own-account-confirm", variant="primary", disabled=True
                )
                yield Button(tr("tui.ledger.own_accounts.cancel"), id="own-account-cancel", disabled=True)
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
            yield Static("", id="own-account-mode", classes="cadrumo-heading", markup=False)
            yield Button(tr("tui.ledger.own_accounts.new"), id="own-account-new")
            yield Static(tr("tui.ledger.own_accounts.field.label"), markup=False)
            yield Input(id="own-account-label")
            yield Static(tr("tui.ledger.own_accounts.field.holding"), markup=False)
            yield Select[str](
                tuple((tr(f"tui.ledger.own_accounts.holding.{item.value}"), item.value) for item in OwnAccountHolding),
                value=OwnAccountHolding.TITULAR.value,
                allow_blank=False,
                id="own-account-holding",
            )
            yield Static(tr("tui.ledger.own_accounts.field.iban"), markup=False)
            yield Input(password=True, id="own-account-iban")
            yield Static(tr("tui.ledger.own_accounts.field.swift_bic"), markup=False)
            yield Input(password=True, id="own-account-bic")
            yield Static(tr("tui.ledger.own_accounts.field.bank_block"), markup=False)
            yield Input(placeholder=tr("tui.ledger.own_accounts.field.bank_name"), id="own-account-bank-name")
            yield Input(placeholder=tr("tui.ledger.own_accounts.field.bank_address"), id="own-account-bank-address")
            yield Input(placeholder=tr("tui.ledger.own_accounts.field.bank_city"), id="own-account-bank-city")
            yield Input(
                placeholder=tr("tui.ledger.own_accounts.field.bank_country"),
                max_length=2,
                id="own-account-bank-country",
            )
            yield Static(tr("tui.ledger.own_accounts.field.currency"), markup=False)
            yield Input(placeholder="EUR", max_length=3, id="own-account-currency")
            yield Static(tr("tui.ledger.own_accounts.field.opened_on"), markup=False)
            yield Input(placeholder=tr("tui.ledger.own_accounts.field.date_placeholder"), id="own-account-opened-on")
            with Horizontal(classes="own-account-actions"):
                yield Button(tr("tui.ledger.own_accounts.review"), id="own-account-review")
            yield Static(tr("tui.ledger.own_accounts.field.closed_on"), markup=False)
            yield Input(placeholder=tr("tui.ledger.own_accounts.field.date_placeholder"), id="own-account-closed-on")
            with Horizontal(classes="own-account-actions"):
                yield Button(tr("tui.ledger.own_accounts.review_close"), id="own-account-review-close")
                yield Button(tr("tui.ledger.own_accounts.review_remove"), id="own-account-review-remove")
            yield Static(tr("tui.ledger.own_accounts.field.role"), markup=False)
            yield Select[str](
                tuple((_role_label(role), role.value) for role in OwnAccountRole),
                value=OwnAccountRole.CHARGE.value,
                allow_blank=False,
                id="own-account-role",
            )
            yield Input(placeholder=tr("tui.ledger.own_accounts.field.modelo"), max_length=3, id="own-account-modelo")
            with Horizontal(classes="own-account-actions"):
                yield Button(tr("tui.ledger.own_accounts.review_designate"), id="own-account-review-designate")
                yield Button(tr("tui.ledger.own_accounts.review_undesignate"), id="own-account-review-undesignate")

    def on_mount(self) -> None:
        """Show headings, then read the register without blocking the UI."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-own-accounts", DataTable))
        table.add_columns(
            tr("tui.ledger.own_accounts.column.id"),
            tr("tui.ledger.own_accounts.column.label"),
            tr("tui.ledger.own_accounts.column.account"),
            tr("tui.ledger.own_accounts.column.holding"),
            tr("tui.ledger.own_accounts.column.roles"),
            tr("tui.ledger.own_accounts.column.state"),
        )
        self._show_mode()
        self._set_staged_controls(staged=False)
        self._busy = True
        self.run_worker(self._submit(self._request(action="list")), exclusive=True)

    def _request(self, **fields: object) -> LedgerOwnAccountRequest:
        """Build the operation's own request, validated before anything is staged."""
        return LedgerOwnAccountRequest.model_validate({"profile_id": self.door.profile_id, **fields})

    def _value(self, selector: str) -> str:
        return self.query_one(selector, Input).value

    def _select(self, selector: str) -> str:
        return str(cast("Select[str]", self.query_one(selector, Select)).value)

    def _selected(self) -> OwnAccountProjection:
        account = next((item for item in self.accounts if item.own_account_id == self.selected_id), None)
        if account is None:
            raise ValueError(tr("tui.ledger.own_accounts.choose_account"))
        return account

    def _detail_fields(self) -> dict[str, object]:
        """Collect the entered details; a blank field is not part of the request."""
        fields: dict[str, object] = {
            "label": _blank_to_none(self._value("#own-account-label")),
            "holding": OwnAccountHolding(self._select("#own-account-holding")),
            "iban": _blank_to_none(self._value("#own-account-iban")),
            "swift_bic": _blank_to_none(self._value("#own-account-bic")),
            "bank_name": _blank_to_none(self._value("#own-account-bank-name")),
            "bank_address": _blank_to_none(self._value("#own-account-bank-address")),
            "bank_city": _blank_to_none(self._value("#own-account-bank-city")),
            "bank_country_code": _blank_to_none(self._value("#own-account-bank-country")),
            "currency": _blank_to_none(self._value("#own-account-currency")),
            "opened_on": require_iso8601_date_unless_blank(self._value("#own-account-opened-on")),
        }
        return {name: value for name, value in fields.items() if value is not None}

    def _stage_details(self) -> tuple[LedgerOwnAccountRequest, str]:
        fields = self._detail_fields()
        if self.selected_id is None:
            # The register's own validator previews the IBAN, BIC and bank-block rules before review.
            OwnBankAccountDetails.model_validate(fields)
            request = self._request(action="add", **fields)
            mask = mask_iban(request.iban or "")
            holding = tr(f"tui.ledger.own_accounts.holding.{fields['holding']}")
            return request, tr("tui.ledger.own_accounts.stage.add", label=request.label, account=mask, holding=holding)
        current = self._selected()
        unchanged = {
            "label": current.label,
            "holding": current.holding,
            "currency": current.currency,
            "opened_on": current.opened_on,
        }
        changes = {name: value for name, value in fields.items() if unchanged.get(name) != value}
        if not changes:
            raise ValueError(tr("tui.ledger.records.no_change"))
        request = self._request(action="update", own_account_id=current.own_account_id, **changes)
        named = ", ".join(_change_label(name, value) for name, value in changes.items())
        return request, tr("tui.ledger.own_accounts.stage.update", account=current.masked_iban, fields=named)

    def _stage(self, button_id: str) -> tuple[LedgerOwnAccountRequest, str]:
        """Build the request one review button asks for and its masked summary."""
        if button_id == "own-account-review":
            return self._stage_details()
        role = OwnAccountRole(self._select("#own-account-role"))
        modelo = _blank_to_none(self._value("#own-account-modelo"))
        if button_id == "own-account-review-undesignate":
            request = self._request(action="undesignate", role=role, modelo=modelo)
            return request, tr(
                "tui.ledger.own_accounts.stage.undesignate", role=_role_label(role), scope=_scope_label(modelo)
            )
        current = self._selected()
        if button_id == "own-account-review-remove":
            request = self._request(action="remove", own_account_id=current.own_account_id)
            return request, tr("tui.ledger.own_accounts.stage.remove", account=current.masked_iban, label=current.label)
        if button_id == "own-account-review-close":
            closed_on = require_iso8601_date(self._value("#own-account-closed-on").strip())
            request = self._request(action="close", own_account_id=current.own_account_id, closed_on=closed_on)
            return request, tr(
                "tui.ledger.own_accounts.stage.close", account=current.masked_iban, date=closed_on.isoformat()
            )
        request = self._request(
            action="designate",
            own_account_id=current.own_account_id,
            role=role,
            modelo=modelo,
        )
        return request, tr(
            "tui.ledger.own_accounts.stage.designate",
            account=current.masked_iban,
            role=_role_label(role),
            scope=_scope_label(modelo),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Stage a reviewed request, then submit exactly the reviewed request."""
        if self._busy:
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.flow.in_flight_refusal"))
            return
        button_id = event.button.id or ""
        refusal = self.query_one("#ledger-refusal", Static)
        if button_id == "own-account-new":
            self.selected_id = None
            self.query_one("#own-account-detail", Static).update("")
            self._unstage()
            self._clear_form()
            self._show_mode()
        elif button_id in _STAGE_BUTTONS:
            refusal.update("")
            try:
                self.staged, summary = self._stage(button_id)
            except (CadrumoError, ValidationError) as error:
                refusal.update(door_refusal_text(error))
                return
            except ValueError as error:
                refusal.update(str(error))
                return
            self.query_one("#own-account-staged", Static).update(summary)
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.reviewed"))
            self._set_staged_controls(staged=True)
        elif button_id == "own-account-cancel":
            self._unstage()
        elif button_id == "own-account-confirm" and self.staged is not None:
            self._busy = True
            self.query_one("#own-account-confirm", Button).disabled = True
            self.run_worker(self._submit(self.staged), exclusive=True)

    async def _submit(self, request: LedgerOwnAccountRequest) -> None:
        """Run one request through the door, then re-read the register after a change."""
        status = self.query_one("#ledger-flow-status", Static)
        refusal = self.query_one("#ledger-refusal", Static)
        reading = request.action == "list"
        status.update(tr("tui.ledger.records.loading" if reading else "tui.ledger.records.saving"))
        try:
            result = await self.door(request)
            if not reading:
                self._clear_secrets()
                result = await self.door(self._request(action="list"))
        except AccountSessionExpiredError as error:
            self._clear_private_view()
            refusal.update(door_refusal_text(error))
            status.update(tr("tui.ledger.records.failed"))
            return
        except CadrumoError as error:
            refusal.update(door_refusal_text(error))
            status.update(tr("tui.ledger.records.failed"))
            self._set_staged_controls(staged=self.staged is not None)
            return
        finally:
            self._busy = False
        self._show_register(result)
        if not reading:
            self._unstage()
            status.update(tr("tui.ledger.records.saved"))
            if self.selected_id is not None:
                await self._show_detail(self.selected_id)
        else:
            status.update("" if self.accounts else tr("tui.ledger.own_accounts.empty"))

    def _show_register(self, result: LedgerOwnAccountResult) -> None:
        """Render the masked register projection the operation returned."""
        self.accounts = result.accounts
        self.designations = result.designations
        if self.selected_id is not None and all(item.own_account_id != self.selected_id for item in self.accounts):
            self.selected_id = None
            self.query_one("#own-account-detail", Static).update("")
        table = cast("DataTable[str]", self.query_one("#ledger-own-accounts", DataTable))
        table.clear()
        for account in self.accounts:
            roles = [
                _designation_label(item) for item in self.designations if item.own_account_id == account.own_account_id
            ]
            table.add_row(
                account.own_account_id,
                account.label,
                account.masked_iban,
                tr(f"tui.ledger.own_accounts.holding.{account.holding.value}"),
                ", ".join(roles) or "-",
                _state_label(account),
                key=account.own_account_id,
            )
        self._show_mode()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Edit the chosen account: its non-secret details fill the form, secrets stay blank."""
        if self.handle_navigation_selection(event):
            return
        if self._busy or event.data_table.id != "ledger-own-accounts" or event.row_key.value is None:
            return
        self.selected_id = str(event.row_key.value)
        account = self._selected()
        self._busy = True
        self.run_worker(self._show_detail(account.own_account_id), exclusive=True)
        self._unstage()
        self._clear_form()
        self.query_one("#own-account-label", Input).value = account.label
        cast("Select[str]", self.query_one("#own-account-holding", Select)).value = account.holding.value
        self.query_one("#own-account-currency", Input).value = account.currency
        self.query_one("#own-account-opened-on", Input).value = (
            "" if account.opened_on is None else account.opened_on.isoformat()
        )
        self._show_mode()

    async def _show_detail(self, own_account_id: str) -> None:
        """Read one account through the operation's own detail action and render it masked."""
        refusal = self.query_one("#ledger-refusal", Static)
        try:
            result = await self.door(self._request(action="show", own_account_id=own_account_id))
        except AccountSessionExpiredError as error:
            self._clear_private_view()
            refusal.update(door_refusal_text(error))
            return
        except CadrumoError as error:
            refusal.update(door_refusal_text(error))
            return
        finally:
            self._busy = False
        account = result.accounts[0]
        roles = ", ".join(_designation_label(item) for item in result.designations) or "-"
        self.query_one("#own-account-detail", Static).update(
            "\n".join(
                (
                    tr(
                        "tui.ledger.own_accounts.detail.account",
                        id=account.own_account_id,
                        label=account.label,
                        account=account.masked_iban,
                    ),
                    tr(
                        "tui.ledger.own_accounts.detail.holding",
                        holding=tr(f"tui.ledger.own_accounts.holding.{account.holding.value}"),
                        country=account.country_code,
                        currency=account.currency,
                    ),
                    tr(
                        "tui.ledger.own_accounts.detail.bank",
                        bic=tr(f"tui.ledger.own_accounts.detail.{'present' if account.has_swift_bic else 'absent'}"),
                        block=tr(f"tui.ledger.own_accounts.detail.{'present' if account.has_bank_block else 'absent'}"),
                    ),
                    tr(
                        "tui.ledger.own_accounts.detail.dates",
                        opened="-" if account.opened_on is None else account.opened_on.isoformat(),
                        state=_state_label(account),
                    ),
                    tr("tui.ledger.own_accounts.detail.roles", roles=roles),
                )
            )
        )

    def _show_mode(self) -> None:
        mode = self.query_one("#own-account-mode", Static)
        if self.selected_id is None:
            mode.update(tr("tui.ledger.own_accounts.mode.add"))
            return
        account = self._selected()
        mode.update(tr("tui.ledger.own_accounts.mode.edit", account=account.masked_iban, label=account.label))

    def _set_staged_controls(self, *, staged: bool) -> None:
        """Freeze the form while a request is staged, so only the reviewed request is sent."""
        for selector in (*_TEXT_INPUTS, "#own-account-holding", "#own-account-role"):
            self.query_one(selector).disabled = staged
        for button_id in (*_STAGE_BUTTONS, "own-account-new"):
            self.query_one(f"#{button_id}", Button).disabled = staged
        self.query_one("#own-account-confirm", Button).disabled = not staged
        self.query_one("#own-account-cancel", Button).disabled = not staged
        # The decision row exists only while there is a reviewed request to decide on.
        self.query_one("#own-account-decision", Horizontal).display = staged

    def _unstage(self) -> None:
        self.staged = None
        self.query_one("#own-account-staged", Static).update("")
        self._set_staged_controls(staged=False)

    def _clear_secrets(self) -> None:
        for selector in _SECRET_INPUTS:
            self.query_one(selector, Input).value = ""

    def _clear_form(self) -> None:
        for selector in _TEXT_INPUTS:
            self.query_one(selector, Input).value = ""
        self.query_one("#ledger-refusal", Static).update("")

    def _clear_private_view(self) -> None:
        """Discard every account fact the screen holds once the admitted session is lost."""
        self.staged = None
        self.accounts = ()
        self.designations = ()
        self.selected_id = None
        self._clear_form()
        self.query_one("#own-account-staged", Static).update("")
        self.query_one("#own-account-detail", Static).update("")
        cast("DataTable[str]", self.query_one("#ledger-own-accounts", DataTable)).clear()
        self._set_staged_controls(staged=False)

    @override
    def action_back(self) -> None:
        if self._busy:
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.flow.in_flight_refusal"))
            return
        super().action_back()


__all__ = ["LedgerOwnAccountDoorV1", "LedgerOwnAccountsScreen"]
