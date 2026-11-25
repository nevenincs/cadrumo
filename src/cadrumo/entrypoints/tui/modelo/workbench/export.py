"""Ask the filer where and how to export the verified declaration.

The dialog offers the artefacts the declaration's read says this installation
can publish, so the filer never picks an export the installation would refuse.
Where the read says the export asks them, it asks the settlement questions the
read served -- refund, payment, prior direct debit and instalments -- in the
words the read served: an answerable question with its choices, pre-set to the
default it served, with the conditions and amounts it states, an advisory
amount marked and told why; a question that applies but cannot be answered
says why, and one the result makes meaningless is not asked. A question not
asked is submitted at its neutral default. Beside them it offers the own bank
account AEAT debits and the one it pays a refund into, each prefilled from the
Ledger designation for this modelo and shown masked. Nothing is exported here: the
dialog returns the typed request and the workbench runs it through the
supervised operation.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import ClassVar, Final, cast, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Select, Static

from .....application.ledger.own_account_operation import (
    LedgerOwnAccountRequest,
    LedgerOwnAccountResult,
    OwnAccountProjection,
)
from .....application.modelo.work_form_export_offer import (
    EXPORT_ARTEFACT_LOCALE_KEYS,
    ModeloFormElection,
    ModeloFormElectionQuestion,
    ModeloFormElectionState,
)
from .....core.errors.hierarchy import CadrumoError
from .....core.i18n.render import tr
from .....core.modelo_export_artefact import ModeloExportArtefact
from .....core.payment_election import PaymentElection
from .....core.payment_instalment_election import PaymentInstalmentElection
from .....core.prior_domiciliation_election import PriorDomiciliationElection
from .....core.refund_election import RefundElection
from .....domain.transactions.own_accounts import OwnAccountRole
from ...components.language import localized, refresh_localized_widgets
from ...components.theme import tokenised
from ...ledger.own_accounts import LedgerOwnAccountDoorV1
from ...ledger.workspace_presentation import door_refusal_text
from .dialog_width import fit_dialog_width
from .ports import WorkbenchExportOffer, WorkbenchExportRequest

#: The account choice that leaves the export to resolve the Ledger designations.
DESIGNATED_ACCOUNT: Final = "-"
_ACCOUNT_CONTROLS: Final[Mapping[OwnAccountRole, str]] = MappingProxyType(
    {OwnAccountRole.CHARGE: "export-charge-account", OwnAccountRole.REFUND: "export-refund-account"}
)
_ELECTION_CONTROLS: Final[Mapping[ModeloFormElection, str]] = MappingProxyType(
    {
        ModeloFormElection.REFUND: "export-refund-election",
        ModeloFormElection.PAYMENT: "export-payment-election",
        ModeloFormElection.PRIOR_DOMICILIATION: "export-prior-domiciliation-election",
        ModeloFormElection.INSTALMENT: "export-instalment-election",
    }
)
"""The control each answerable settlement question is drawn as."""
_ACCOUNT_ELECTIONS: Final[Mapping[ModeloFormElection, OwnAccountRole]] = MappingProxyType(
    {ModeloFormElection.CHARGE_ACCOUNT: OwnAccountRole.CHARGE, ModeloFormElection.REFUND_ACCOUNT: OwnAccountRole.REFUND}
)
"""The elections the own-account controls answer, drawn from the Ledger designations rather than from choices."""
SETTLEMENT_TITLE_LOCALE_KEY: Final = "desktop.modelo.settlement.title"
ADVISORY_LOCALE_KEY: Final = "desktop.modelo.settlement.advisory"


def designated_account_id(result: LedgerOwnAccountResult, role: OwnAccountRole, modelo: str) -> str | None:
    """The account the register designates for ``role`` on ``modelo``: its own scope first, then every modelo."""
    scoped = {(item.role, item.modelo): item.own_account_id for item in result.designations}
    return scoped.get((role, modelo)) or scoped.get((role, None))


class WorkbenchExportScreen(ModalScreen[WorkbenchExportRequest | None]):
    """Collect one export's destination, artefact and elections."""

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        WorkbenchExportScreen #export-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        WorkbenchExportScreen #export-panel {
            width: $cadrumo-modal-width;
            height: auto;
            max-height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        WorkbenchExportScreen.-narrow #export-panel {
            width: 100%;
        }
        WorkbenchExportScreen #export-title {
            text-style: bold;
            color: $primary;
            margin-bottom: $cadrumo-stack;
        }
        WorkbenchExportScreen #export-notice {
            color: $warning;
            height: auto;
        }
        WorkbenchExportScreen #export-settlement-title {
            text-style: bold;
            margin-top: $cadrumo-stack;
        }
        WorkbenchExportScreen .export-question {
            margin-top: $cadrumo-tight;
        }
        WorkbenchExportScreen .export-help,
        WorkbenchExportScreen .export-figure-why {
            color: $text-muted;
            height: auto;
        }
        WorkbenchExportScreen .export-figure {
            height: auto;
        }
        WorkbenchExportScreen .export-state {
            height: auto;
            color: $warning;
        }
        WorkbenchExportScreen #export-actions {
            height: auto;
            align-horizontal: right;
            margin-top: $cadrumo-stack;
        }
        WorkbenchExportScreen #export-actions Button {
            margin-left: $cadrumo-control-gap;
        }
        """
    )

    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, offer: WorkbenchExportOffer) -> None:
        """Hold what this declaration may export and whether it asks elections."""
        super().__init__()
        self._offer = offer

    @override
    def compose(self) -> ComposeResult:
        with Container(id="export-backdrop"), VerticalScroll(id="export-panel"):
            yield localized(
                Static(tr("workspace.modelo.export.title"), id="export-title", markup=False),
                "workspace.modelo.export.title",
            )
            yield localized(
                Input(placeholder=tr("application.modelo.lifecycle.export_destination_placeholder"), id="export-path"),
                "application.modelo.lifecycle.export_destination_placeholder",
            )
            yield localized(
                Static(tr("tui.modelo.export.artefact.label"), markup=False), "tui.modelo.export.artefact.label"
            )
            yield Select[str](
                tuple(
                    (tr(EXPORT_ARTEFACT_LOCALE_KEYS[artefact]), artefact.value) for artefact in self._offer.artefacts
                ),
                value=self._offer.artefacts[0].value,
                allow_blank=False,
                id="export-artefact",
            )
            if self._offer.asks_elections:
                yield from self._compose_elections()
                if self._offer.own_accounts is not None:
                    yield from self._compose_accounts()
            yield Checkbox(tr("tui.modelo.export.replace_existing.label"), id="export-replace")
            yield Static("", id="export-notice", markup=False)
            with Horizontal(id="export-actions"):
                yield localized(
                    Button(tr("workspace.modelo.editor.cancel"), id="export-cancel"),
                    "workspace.modelo.editor.cancel",
                )
                yield localized(
                    Button(tr("application.modelo.lifecycle.export"), id="export-submit", variant="primary"),
                    "application.modelo.lifecycle.export",
                )

    def _asked(self) -> tuple[ModeloFormElectionQuestion, ...]:
        """The served questions the dialog asks or explains: those the result does not make meaningless."""
        return tuple(
            question
            for question in self._offer.elections
            if question.state is not ModeloFormElectionState.NOT_APPLICABLE
        )

    def _unasked_roles(self) -> frozenset[OwnAccountRole]:
        """The account roles whose served question is not answerable: unavailable, or meaningless for the result."""
        return frozenset(
            _ACCOUNT_ELECTIONS[question.election]
            for question in self._offer.elections
            if question.election in _ACCOUNT_ELECTIONS and question.state is not ModeloFormElectionState.AVAILABLE
        )

    def _compose_elections(self) -> ComposeResult:
        asked = self._asked()
        if not asked:
            return
        yield localized(
            Static(tr(SETTLEMENT_TITLE_LOCALE_KEY), id="export-settlement-title", markup=False),
            SETTLEMENT_TITLE_LOCALE_KEY,
        )
        for question in asked:
            if question.state is ModeloFormElectionState.AVAILABLE and question.election in _ACCOUNT_ELECTIONS:
                continue
            yield Static(question.words, classes="export-question", markup=False)
            if question.state is ModeloFormElectionState.UNAVAILABLE:
                yield Static(
                    question.state_words or "",
                    id=f"export-state-{question.election.value}",
                    classes="export-state",
                    markup=False,
                )
                continue
            yield Select[str](
                tuple((choice.words, choice.value) for choice in question.choices),
                value=Select.NULL if question.default is None else question.default,
                allow_blank=question.default is None,
                id=_ELECTION_CONTROLS[question.election],
            )
            if question.help is not None:
                yield Static(question.help, classes="export-help", markup=False)
            for figure in question.figures:
                line = figure.words
                if figure.advisory:
                    line = f"{line} [{tr(ADVISORY_LOCALE_KEY)}]"
                yield Static(
                    line,
                    id=f"export-figure-{question.election.value}-{figure.instalment.value}",
                    classes="export-figure",
                    markup=False,
                )
                if figure.advisory_words is not None:
                    yield Static(figure.advisory_words, classes="export-figure-why", markup=False)

    def _compose_accounts(self) -> ComposeResult:
        for role, control_id in _ACCOUNT_CONTROLS.items():
            if role in self._unasked_roles():
                continue
            yield localized(
                Static(tr(f"tui.modelo.export.account.{role.value}_label"), markup=False),
                f"tui.modelo.export.account.{role.value}_label",
            )
            yield Select[str](
                ((tr("tui.modelo.export.account.designated"), DESIGNATED_ACCOUNT),),
                value=DESIGNATED_ACCOUNT,
                allow_blank=False,
                id=control_id,
            )

    async def _load_accounts(self, door: LedgerOwnAccountDoorV1) -> None:
        """Offer the open own accounts, masked, each role prefilled from its designation for this modelo."""
        try:
            result = await door(LedgerOwnAccountRequest(profile_id=door.profile_id, action="list"))
        except CadrumoError as error:
            self.query_one("#export-notice", Static).update(door_refusal_text(error))
            return
        open_accounts = tuple(item for item in result.accounts if item.closed_on is None)
        for role, control_id in _ACCOUNT_CONTROLS.items():
            if role in self._unasked_roles():
                continue
            designated = designated_account_id(result, role, self._offer.modelo)
            options = [(tr("tui.modelo.export.account.designated"), DESIGNATED_ACCOUNT)]
            options.extend((self._account_label(item, designated), item.own_account_id) for item in open_accounts)
            select = cast("Select[str]", self.query_one(f"#{control_id}", Select))
            select.set_options(options)
            known = any(item.own_account_id == designated for item in open_accounts)
            select.value = designated if designated is not None and known else DESIGNATED_ACCOUNT

    @staticmethod
    def _account_label(account: OwnAccountProjection, designated: str | None) -> str:
        label = f"{account.own_account_id} · {account.label} · {account.masked_iban}"
        if account.own_account_id == designated:
            return tr("tui.modelo.export.account.designated_option", account=label)
        return label

    def _account(self, role: OwnAccountRole) -> str | None:
        if not self._offer.asks_elections or self._offer.own_accounts is None:
            return None
        if role in self._unasked_roles():
            return None
        value = self._election(_ACCOUNT_CONTROLS[role])
        return None if value == DESIGNATED_ACCOUNT else value

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)

    def on_mount(self) -> None:
        """Start in the destination field."""
        fit_dialog_width(self, self.app.size.width)
        self.query_one("#export-path", Input).focus()
        door = self._offer.own_accounts
        if self._offer.asks_elections and door is not None:
            self.run_worker(self._load_accounts(door), group="export-accounts")

    def _election(self, control_id: str) -> str:
        """Return the selected election, refusing rather than stringifying a blank selection."""
        value = cast("Select[str]", self.query_one(f"#{control_id}", Select)).value
        if not isinstance(value, str):
            raise ValueError("required Modelo export election has no selected value")
        return value

    def _request(self) -> WorkbenchExportRequest | None:
        path = self.query_one("#export-path", Input).value.strip()
        if not path:
            self.query_one("#export-notice", Static).update(
                tr("application.modelo.lifecycle.refusal.export_destination_required")
            )
            return None
        refund = self._answered(ModeloFormElection.REFUND)
        payment = self._answered(ModeloFormElection.PAYMENT)
        prior = self._answered(ModeloFormElection.PRIOR_DOMICILIATION)
        instalment = self._answered(ModeloFormElection.INSTALMENT)
        return WorkbenchExportRequest(
            output_path=path,
            artefact=ModeloExportArtefact(self._election("export-artefact")),
            refund_election=RefundElection.COMPENSAR if refund is None else RefundElection(refund),
            payment_election=PaymentElection.INGRESO if payment is None else PaymentElection(payment),
            prior_domiciliation_election=(
                PriorDomiciliationElection.KEEP if prior is None else PriorDomiciliationElection(prior)
            ),
            replace_existing=self.query_one("#export-replace", Checkbox).value,
            charge_account_id=self._account(OwnAccountRole.CHARGE),
            refund_account_id=self._account(OwnAccountRole.REFUND),
            instalment_election=(
                PaymentInstalmentElection.SINGLE if instalment is None else PaymentInstalmentElection(instalment)
            ),
        )

    def _answered(self, election: ModeloFormElection) -> str | None:
        """The answer chosen for one served question, or ``None`` when it was not asked and keeps its default."""
        nodes = self.query(f"#{_ELECTION_CONTROLS[election]}")
        return self._election(_ELECTION_CONTROLS[election]) if nodes else None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Export, or leave without exporting."""
        event.stop()
        if event.button.id == "export-cancel":
            self.dismiss(None)
            return
        request = self._request()
        if request is not None:
            self.dismiss(request)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Export from the destination field once it is filled."""
        event.stop()
        request = self._request()
        if request is not None:
            self.dismiss(request)

    def action_cancel(self) -> None:
        """Leave without exporting."""
        self.dismiss(None)

    async def refresh_language(self) -> None:
        """Reword the open dialog without changing its inputs or decision."""
        refresh_localized_widgets(self)


__all__ = [
    "DESIGNATED_ACCOUNT",
    "WorkbenchExportScreen",
    "designated_account_id",
]
