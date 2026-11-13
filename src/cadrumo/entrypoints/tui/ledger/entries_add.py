"""Add entry: the ``ledger.add`` form, reviewed before it is written.

Which facts the form asks for, which of them are required and which closed
choices they offer come from the request schema the runtime served for
``ledger.add``. The required facts come first. The optional facts sit in a
second section the operator opens on purpose. The form builds the operation's
own request, so its date, amount and decimal rules refuse a value before
review, and the worker's own validation refusal is shown as it was recorded.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date
from itertools import count
from typing import ClassVar, Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Collapsible, Input, Select, Static

from ....application.ledger.ledger_add_contracts import LedgerAddOperationResult, LedgerAddRequest
from ....application.ledger.list_operation import LedgerListRequest
from ....core.errors.hierarchy import CadrumoError, InternalInvariantError
from ....core.i18n.render import tr
from ..account import AccountSessionExpiredError
from ..components.language import localized
from ..components.theme import tokenised
from ..components.widgets import DisclosureGroup
from ..components.workspace_host import replace_workspace_body
from .controller import LedgerWorkspaceController, review_status_label
from .entries_add_form import LedgerAddFieldV1, LedgerAddFormV1
from .entries_browse import LedgerEntriesBrowseScreen
from .entries_browse_model import BROWSE_PAGE_SIZE, LedgerBrowseStateV1
from .entries_common import classification_label, direction_label, entry_label, joined
from .entries_doors import LedgerEntriesDoorsV1
from .link_picker import LINK_FAMILY_BY_FIELD, LedgerLinkPickers
from .models import LedgerFlowState
from .workspace_presentation import LedgerConfirmationFlowScreen, door_refusal_text, ledger_workspace_page

#: The words of every fact the form can ask for, by the field name the schema serves.
#: The served schema decides which of them the form offers; a served fact with no entry here is not offered.
FIELD_LABEL_LOCALE_KEYS: Final[dict[str, str]] = {
    "booked_date": "tui.ledger.entry_tools.add.field.booked_date",
    "amount": "tui.ledger.entry_tools.add.field.amount",
    "direction": "tui.ledger.entry_tools.add.field.direction",
    "description": "tui.ledger.entry_tools.add.field.description",
    "business_classification": "tui.ledger.entry_tools.add.field.business_classification",
    "value_date": "tui.ledger.entry_tools.add.field.value_date",
    "operation_date": "tui.ledger.entry_tools.add.field.operation_date",
    "accrual_date": "tui.ledger.entry_tools.add.field.accrual_date",
    "currency": "tui.ledger.entry_tools.add.field.currency",
    "counterparty": "tui.ledger.entry_tools.add.field.counterparty",
    "business_pct": "tui.ledger.entry_tools.add.field.business_pct",
    "category_id": "tui.ledger.entry_tools.add.field.category_id",
    "taxable_base": "tui.ledger.entry_tools.add.field.taxable_base",
    "iva_rate": "tui.ledger.entry_tools.add.field.iva_rate",
    "iva_amount": "tui.ledger.entry_tools.add.field.iva_amount",
    "iva_category": "tui.ledger.entry_tools.add.field.iva_category",
    "recargo_amount": "tui.ledger.entry_tools.add.field.recargo_amount",
    "deduction_fact_kind": "tui.ledger.entry_tools.add.field.deduction_fact_kind",
    "investment_asset_id": "tui.ledger.entry_tools.add.field.investment_asset_id",
    "counterparty_country": "tui.ledger.entry_tools.add.field.counterparty_country",
    "counterparty_identification_state": "tui.ledger.entry_tools.add.field.counterparty_identification_state",
    "irpf_category": "tui.ledger.entry_tools.add.field.irpf_category",
    "usage_ratio_id": "tui.ledger.entry_tools.add.field.usage_ratio_id",
    "prorrata_reference": "tui.ledger.entry_tools.add.field.prorrata_reference",
    "art_104_tres_exclusion": "tui.ledger.entry_tools.add.field.art_104_tres_exclusion",
    "input_classification": "tui.ledger.entry_tools.add.field.input_classification",
    "prorrata_sector": "tui.ledger.entry_tools.add.field.prorrata_sector",
    "purchase_invoice_evidence_id": "tui.ledger.entry_tools.add.field.purchase_invoice_evidence_id",
    "source_jurisdiction": "tui.ledger.entry_tools.add.field.source_jurisdiction",
    "own_account_id": "tui.ledger.entry_tools.add.field.own_account_id",
    "notes": "tui.ledger.entry_tools.add.field.notes",
}
#: The facts the door supplies itself: the exact profile the session was admitted for.
SUPPLIED_FIELDS: Final = frozenset({"profile_id"})
#: How a served token of a closed fact is worded; any other closed fact shows its token.
_CHOICE_WORDING: Final[dict[str, Callable[[str], str]]] = {
    "direction": direction_label,
    "business_classification": classification_label,
}
_JURISDICTION_LOCALE_KEYS: Final[dict[str, str]] = {
    "source_jurisdiction_required_irnr": "tui.ledger.entry_tools.add.source_jurisdiction_required_irnr",
    "source_jurisdiction_required_beckham": "tui.ledger.entry_tools.add.source_jurisdiction_required_beckham",
}

#: Starting a flow again replaces its screen while the outgoing one is still
#: being removed, so each instance carries its own identity.
_SCREEN_SERIALS: Final = count()


def _input_id(name: str) -> str:
    return f"entries-add-{name.replace('_', '-')}"


def _word(field: LedgerAddFieldV1, token: str) -> str:
    return _CHOICE_WORDING.get(field.name, str)(token)


def _choice_options(field: LedgerAddFieldV1) -> list[tuple[str, str]]:
    """The tokens the schema closed ``field`` to, each in the operator's words."""
    return [(_word(field, token), token) for token in field.choices]


def _shown_value(field: LedgerAddFieldV1, request: LedgerAddRequest) -> str:
    value = str(getattr(request, field.name))
    if field.is_choice:
        return _word(field, value)
    return f"{value} {request.currency}" if field.name == "amount" else value


def _held_links(request: LedgerAddRequest | None) -> dict[str, str]:
    """The links a request the operator edits again had chosen, by field."""
    if request is None:
        return {}
    return {field: value for field in LINK_FAMILY_BY_FIELD if (value := getattr(request, field)) is not None}


def staged_add_lines(request: LedgerAddRequest, form: LedgerAddFormV1) -> tuple[str, ...]:
    """Name every fact the reviewed request will write, in the operator's language."""
    return tuple(
        f"{tr(FIELD_LABEL_LOCALE_KEYS[field.name])}: {_shown_value(field, request)}"
        for field in form.fields
        if field.name != "currency" and (field.required or getattr(request, field.name) not in (None, ""))
    )


def add_outcome_lines(result: LedgerAddOperationResult) -> tuple[str, ...]:
    """Say what the add recorded, or the refusal the worker recorded instead."""
    if result.outcome == "validation_error" or result.transaction is None:
        code = result.validation_code
        if code is not None and code in _JURISDICTION_LOCALE_KEYS:
            return (tr(_JURISDICTION_LOCALE_KEYS[code]),)
        return (tr("tui.ledger.entry_tools.add.refused"), *result.validation_messages)
    lines = [
        tr(
            "tui.ledger.entry_tools.add.created",
            entry=entry_label(result.transaction),
            status="-" if result.review_status is None else review_status_label(result.review_status.value),
        )
    ]
    if result.advisory_input_classification_inert:
        lines.append(tr("tui.ledger.entry_tools.add.input_classification_inert"))
    if result.advisory_sector_unmatched:
        lines.append(tr("tui.ledger.entry_tools.add.sector_unmatched"))
    return tuple(lines)


class LedgerEntryAddScreen(LedgerConfirmationFlowScreen):
    """Collect the facts ``ledger.add`` takes, then write only the reviewed request."""

    FLOW_NAME = "entry_add"
    CSS: ClassVar[str] = LedgerConfirmationFlowScreen.CSS + tokenised(
        """
        .entries-add-actions { height: auto; width: 100%; }
        .entries-add-actions > * { width: 1fr; min-width: 0; }
        #entries-add-summary { height: auto; }
        #entries-add-again, #entries-add-open { display: none; }
        #entries-add-again.-open, #entries-add-open.-open { display: block; }
        """
    )

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        doors: LedgerEntriesDoorsV1,
        form: LedgerAddFormV1,
        *,
        initial: LedgerAddRequest | None = None,
    ) -> None:
        """Start empty, or with the values of a request the operator wants to edit again.

        ``form`` is what the runtime served for ``ledger.add``: the facts to ask for.
        """
        super().__init__(controller, id=f"ledger-entry-add-screen-{next(_SCREEN_SERIALS)}")
        self.doors = doors
        self.form = form
        self.initial = initial
        self.staged: LedgerAddRequest | None = None
        self.result: LedgerAddOperationResult | None = None

    def _held(self, field: LedgerAddFieldV1) -> str | None:
        """The value of ``field`` in the request being edited again, if there is one."""
        held = None if self.initial is None else getattr(self.initial, field.name)
        return None if held is None else str(held)

    def _field_widgets(self, field: LedgerAddFieldV1) -> Iterator[Widget]:
        """The words of one fact and the control that takes it."""
        key = FIELD_LABEL_LOCALE_KEYS[field.name]
        yield localized(Static(tr(key), markup=False), key)
        held = self._held(field)
        if not field.is_choice:
            yield Input(value="" if held is None else held, id=_input_id(field.name))
            return
        value = held if held is not None else field.default
        yield Select[str](
            _choice_options(field),
            prompt=tr(key),
            allow_blank=field.default is None,
            value=Select.NULL if value is None else value,
            id=_input_id(field.name),
        )

    @override
    def compose(self) -> ComposeResult:
        yield localized(
            Static(tr("tui.ledger.entry_tools.add.title"), classes="cadrumo-banner"), "tui.ledger.entry_tools.add.title"
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(tr("tui.ledger.entry_tools.add.prompt"), markup=False), "tui.ledger.entry_tools.add.prompt"
            )
            for field in self.form.required:
                yield from self._field_widgets(field)
            with DisclosureGroup(title=tr("tui.ledger.entry_tools.add.optional"), id="entries-add-optional"):
                for field in self.form.optional:
                    yield from self._field_widgets(field)
                yield LedgerLinkPickers(
                    "entries-add",
                    self.controller.link_options_door,
                    initial=_held_links(self.initial),
                    id="entries-add-links",
                )
            with Horizontal(classes="entries-add-actions"):
                yield localized(
                    Button(tr("tui.ledger.entry_tools.add.review"), id="entries-add-review", variant="primary"),
                    "tui.ledger.entry_tools.add.review",
                )
            yield Static("", id="entries-add-summary", markup=False)
            yield Static("", id="ledger-flow-status", markup=False)
            with Horizontal(classes="entries-add-actions"):
                yield localized(
                    Button(tr("tui.ledger.entry_tools.confirm"), id="entries-add-confirm", disabled=True),
                    "tui.ledger.entry_tools.confirm",
                )
                yield localized(
                    Button(tr("tui.ledger.entry_tools.cancel"), id="entries-add-cancel"),
                    "tui.ledger.entry_tools.cancel",
                )
            with Horizontal(classes="entries-add-actions"):
                yield Button("", id="entries-add-again")
                yield localized(
                    Button(tr("tui.ledger.entry_tools.add.open_in_browse"), id="entries-add-open"),
                    "tui.ledger.entry_tools.add.open_in_browse",
                )
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Start at the first required field."""
        self.populate_navigation()
        self.query_one(f"#{_input_id(self.form.required[0].name)}").focus()

    @override
    async def refresh_language(self) -> None:
        """Reword choices and the section title in place, keeping every typed value."""
        await super().refresh_language()
        for field in self.form.fields:
            if not field.is_choice:
                continue
            select = cast("Select[str]", self.query_one(f"#{_input_id(field.name)}", Select))
            value = select.value
            select.set_options(_choice_options(field))
            select.value = value
            select.prompt = tr(FIELD_LABEL_LOCALE_KEYS[field.name])
        self.query_one("#entries-add-optional", Collapsible).title = tr("tui.ledger.entry_tools.add.optional")
        self.query_one("#entries-add-again", Button).label = self._again_label()
        if self.staged is not None:
            self.query_one("#entries-add-summary", Static).update(self._staged_text(self.staged))
        if self.result is not None:
            self.query_one("#ledger-flow-status", Static).update(joined(add_outcome_lines(self.result)))

    def _staged_text(self, request: LedgerAddRequest) -> str:
        """The reviewed request's facts, then each chosen link in its served words."""
        links = self.query_one("#entries-add-links", LedgerLinkPickers).chosen_lines()
        return joined((*staged_add_lines(request, self.form), *links))

    def _entered(self, field: LedgerAddFieldV1) -> str:
        """What the operator typed or chose for ``field``; empty when nothing was."""
        if field.is_choice:
            select = cast("Select[str]", self.query_one(f"#{_input_id(field.name)}", Select))
            return "" if select.is_blank() else str(select.value)
        return self.query_one(f"#{_input_id(field.name)}", Input).value.strip()

    def _form_request(self) -> LedgerAddRequest:
        """Build the operation's own request; a fact left blank is not sent."""
        fields: dict[str, object] = {"profile_id": self.doors.profile_id}
        for field in self.form.fields:
            value = self._entered(field)
            if value:
                fields[field.name] = value
        fields.update(self.query_one("#entries-add-links", LedgerLinkPickers).chosen())
        return LedgerAddRequest.model_validate(fields)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route each control through the flow's guarded transitions."""
        notice = self.query_one("#ledger-refusal", Static)
        status = self.query_one("#ledger-flow-status", Static)
        match event.button.id:
            case "entries-add-review" if self.flow_state is LedgerFlowState.EDITING:
                try:
                    self.staged = self._form_request()
                except ValidationError as error:
                    notice.update(door_refusal_text(error))
                    return
                notice.update("")
                self.query_one("#entries-add-summary", Static).update(self._staged_text(self.staged))
                self._lock_form()
                self._transition(LedgerFlowState.CONFIRMING)
                status.update(tr("tui.ledger.entry_tools.add.confirming"))
                confirm = self.query_one("#entries-add-confirm", Button)
                confirm.disabled = False
                confirm.focus()
            case "entries-add-cancel" if self.can_cancel_flow:
                self._cancel_flow()
            case "entries-add-confirm" if self.flow_state is LedgerFlowState.CONFIRMING:
                self._transition(LedgerFlowState.SUBMITTING)
                event.button.disabled = True
                self.query_one("#entries-add-cancel", Button).disabled = True
                status.update(tr("tui.ledger.records.saving"))
                self.run_worker(self._submit(), exclusive=True)
            case "entries-add-again" if self.flow_state.is_settled:
                initial = None if self.flow_state is LedgerFlowState.SUCCEEDED else self.staged
                self.refresh_after_write(lambda: self._start_again(initial))
            case "entries-add-open" if self.flow_state is LedgerFlowState.SUCCEEDED:
                self.refresh_after_write(self._open_in_browse)
            case _:
                return

    def _start_again(self, initial: LedgerAddRequest | None) -> None:
        """Open a fresh form, carrying the reviewed values when the operator edits them again."""
        screen = LedgerEntryAddScreen(self.controller, self.doors, self.form, initial=initial)
        screen.back_area = self.back_area
        replace_workspace_body(self.app, screen)

    def _open_in_browse(self) -> None:
        """Open Browse entries on the month the new entry was booked in, with it chosen."""
        result = self.result
        if result is None or result.transaction is None:
            raise InternalInvariantError("an added entry disappeared before it was opened")
        booked = date.fromisoformat(result.transaction.booked_date)
        request = LedgerListRequest(
            profile_id=self.doors.profile_id,
            filters=(f"period={booked.month:02d}", f"year={booked.year}"),
            limit=BROWSE_PAGE_SIZE,
        )
        screen = LedgerEntriesBrowseScreen(
            self.controller,
            self.doors,
            state=LedgerBrowseStateV1(request=request, selected_id=result.transaction.transaction_id),
        )
        screen.back_area = self.back_area
        replace_workspace_body(self.app, screen)

    def _lock_form(self) -> None:
        for widget in self.query(Input):
            widget.disabled = True
        for widget in self.query(Select):
            widget.disabled = True
        self.query_one("#entries-add-review", Button).disabled = True

    async def _submit(self) -> None:
        """Write exactly the reviewed request."""
        status = self.query_one("#ledger-flow-status", Static)
        notice = self.query_one("#ledger-refusal", Static)
        request = self.staged
        if request is None:
            raise InternalInvariantError("the reviewed entry disappeared before submission")
        try:
            result = await self.doors.add(request)
        except AccountSessionExpiredError as error:
            self._clear_private_form()
            self._transition(LedgerFlowState.FAILED)
            status.update(self.failed_write_status(error, "tui.ledger.records.failed"))
            notice.update(door_refusal_text(error))
        except CadrumoError as error:
            self._transition(LedgerFlowState.FAILED)
            status.update(self.failed_write_status(error, "tui.ledger.records.failed"))
            notice.update(door_refusal_text(error))
        else:
            self.result = result
            if result.outcome == "created":
                self._transition(LedgerFlowState.SUCCEEDED)
                status.update(joined(add_outcome_lines(result)))
                self.query_one("#entries-add-open", Button).add_class("-open")
            else:
                self._transition(LedgerFlowState.FAILED)
                status.update(tr("tui.ledger.records.failed"))
                notice.update(joined(add_outcome_lines(result)))
        self._offer_again()

    def _again_label(self) -> str:
        if self.flow_state is LedgerFlowState.SUCCEEDED:
            return tr("tui.ledger.entry_tools.add.another")
        return tr("tui.ledger.entry_tools.add.edit_again")

    def _offer_again(self) -> None:
        again = self.query_one("#entries-add-again", Button)
        again.label = self._again_label()
        again.add_class("-open")
        again.focus()

    def _clear_private_form(self) -> None:
        """Discard the reviewed entry and every typed value once the session is lost."""
        self.staged = None
        for widget in self.query(Input):
            widget.value = ""
        self.query_one("#entries-add-summary", Static).update("")

    @override
    def _cancel_flow(self) -> None:
        if not self.can_cancel_flow:
            return
        self._transition(LedgerFlowState.CANCELLED)
        self._lock_form()
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.entry_tools.cancelled"))
        self.query_one("#entries-add-confirm", Button).disabled = True
        self.query_one("#entries-add-cancel", Button).disabled = True
        self._offer_again()


__all__ = [
    "FIELD_LABEL_LOCALE_KEYS",
    "SUPPLIED_FIELDS",
    "LedgerEntryAddScreen",
    "add_outcome_lines",
    "staged_add_lines",
]
