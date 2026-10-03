"""Ask the filer where and how to export the verified declaration.

The dialog offers only the artefacts this installation can publish, so the
filer never picks an export the installation would refuse. A Modelo 303 asks the
three declaration-shaping elections -- refund, payment and prior direct debit --
each pre-set to its neutral default and never blank; other modelos submit those
defaults without asking. Nothing is exported here: the dialog returns the typed
request and the workbench runs it through the supervised operation.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import ClassVar, Final, cast, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Select, Static

from .....core.i18n.render import tr
from .....core.modelo_export_artefact import ModeloExportArtefact
from .....core.optional_extras import PDF_EXTRA, OptionalExtra, optional_extra_available
from .....core.payment_election import PaymentElection
from .....core.prior_domiciliation_election import PriorDomiciliationElection
from .....core.refund_election import RefundElection
from ...components.theme import tokenised
from ..export_result import EXPORT_ARTEFACT_LOCALE_KEYS
from .dialog_width import fit_dialog_width
from .ports import WorkbenchExportOffer, WorkbenchExportRequest

REFUND_ELECTION_LOCALE_KEYS: Final[Mapping[RefundElection, str]] = MappingProxyType(
    {
        RefundElection.COMPENSAR: "tui.modelo.export.refund_election.compensar",
        RefundElection.DEVOLVER: "tui.modelo.export.refund_election.devolver",
    }
)
PAYMENT_ELECTION_LOCALE_KEYS: Final[Mapping[PaymentElection, str]] = MappingProxyType(
    {
        PaymentElection.INGRESO: "tui.modelo.export.payment_election.ingreso",
        PaymentElection.DOMICILIACION: "tui.modelo.export.payment_election.domiciliacion",
        PaymentElection.CUENTA_CORRIENTE: "tui.modelo.export.payment_election.cuenta_corriente",
    }
)
PRIOR_DOMICILIATION_ELECTION_LOCALE_KEYS: Final[Mapping[PriorDomiciliationElection, str]] = MappingProxyType(
    {
        PriorDomiciliationElection.KEEP: "tui.modelo.export.prior_domiciliation_election.keep",
        PriorDomiciliationElection.CANCEL_OR_MODIFY: "tui.modelo.export.prior_domiciliation_election.cancel_or_modify",
    }
)

#: An artefact that needs an optional extra is offered only when the extra is
#: installed, so the operator never picks an export the installation would
#: refuse and no other artefact is ever published in its place.
_EXPORT_ARTEFACT_EXTRAS: Final[Mapping[ModeloExportArtefact, OptionalExtra]] = MappingProxyType(
    {ModeloExportArtefact.CALCULATION_REPORT_PDF: PDF_EXTRA},
)


def offered_export_artefacts() -> tuple[ModeloExportArtefact, ...]:
    """Return the artefacts this installation can publish, in the order the dialog lists them.

    Probed each time, through the same spec-only probe the export service's own
    refusal rests on.
    """
    return tuple(
        artefact
        for artefact in EXPORT_ARTEFACT_LOCALE_KEYS
        if (extra := _EXPORT_ARTEFACT_EXTRAS.get(artefact)) is None or optional_extra_available(extra)
    )


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
        with Container(id="export-backdrop"), Vertical(id="export-panel"):
            yield Static(tr("tui.modelo.workbench.export.title"), id="export-title", markup=False)
            yield Input(placeholder=tr("application.modelo.lifecycle.export_destination_placeholder"), id="export-path")
            yield Static(tr("tui.modelo.export.artefact.label"), markup=False)
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
            yield Checkbox(tr("tui.modelo.export.replace_existing.label"), id="export-replace")
            yield Static("", id="export-notice", markup=False)
            with Horizontal(id="export-actions"):
                yield Button(tr("tui.modelo.workbench.editor.cancel"), id="export-cancel")
                yield Button(tr("application.modelo.lifecycle.export"), id="export-submit", variant="primary")

    def _compose_elections(self) -> ComposeResult:
        for control_id, label_key, keys, default in (
            (
                "export-refund-election",
                "tui.modelo.export.refund_election.label",
                REFUND_ELECTION_LOCALE_KEYS,
                RefundElection.COMPENSAR.value,
            ),
            (
                "export-payment-election",
                "tui.modelo.export.payment_election.label",
                PAYMENT_ELECTION_LOCALE_KEYS,
                PaymentElection.INGRESO.value,
            ),
            (
                "export-prior-domiciliation-election",
                "tui.modelo.export.prior_domiciliation_election.label",
                PRIOR_DOMICILIATION_ELECTION_LOCALE_KEYS,
                PriorDomiciliationElection.KEEP.value,
            ),
        ):
            yield Static(tr(label_key), markup=False)
            yield Select[str](
                tuple((tr(key), member.value) for member, key in keys.items()),
                value=default,
                allow_blank=False,
                id=control_id,
            )

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)

    def on_mount(self) -> None:
        """Start in the destination field."""
        fit_dialog_width(self, self.app.size.width)
        self.query_one("#export-path", Input).focus()

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
        asks = self._offer.asks_elections
        return WorkbenchExportRequest(
            output_path=path,
            artefact=ModeloExportArtefact(self._election("export-artefact")),
            refund_election=RefundElection(self._election("export-refund-election"))
            if asks
            else RefundElection.COMPENSAR,
            payment_election=PaymentElection(self._election("export-payment-election"))
            if asks
            else PaymentElection.INGRESO,
            prior_domiciliation_election=PriorDomiciliationElection(
                self._election("export-prior-domiciliation-election")
            )
            if asks
            else PriorDomiciliationElection.KEEP,
            replace_existing=self.query_one("#export-replace", Checkbox).value,
        )

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


__all__ = [
    "PAYMENT_ELECTION_LOCALE_KEYS",
    "PRIOR_DOMICILIATION_ELECTION_LOCALE_KEYS",
    "REFUND_ELECTION_LOCALE_KEYS",
    "WorkbenchExportScreen",
    "offered_export_artefacts",
]
