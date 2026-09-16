"""Import flow: choose a file or folder, preview what it holds, then confirm the write."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.widgets import Button, DirectoryTree, Input, Select, Static

from ....application.ledger.actions_import import LedgerProviderID
from ....application.ledger.workspace import LedgerWorkspaceArea
from ....core.errors.hierarchy import CadrumoError, InternalInvariantError
from ..components.theme import tokenised
from ..components.widgets import ContentScroll
from .controller import LedgerRouteRequested, LedgerWorkspaceController, ledger_copy
from .models import LedgerFlowState, LedgerImportOutcomeV1, LedgerImportRequestV1, LedgerImportSourceKind
from .workspace_presentation import LedgerConfirmationFlowScreen, door_refusal_text, ledger_workspace_page

#: The readers an operator may pick for a bank statement, automatic first.
IMPORT_PROVIDERS: Final[tuple[LedgerProviderID, ...]] = (
    LedgerProviderID.AUTO,
    LedgerProviderID.CSV,
    LedgerProviderID.OFX,
    LedgerProviderID.XLSX,
    LedgerProviderID.PDF_N26,
)

_SOURCE_KIND_LOCALE_KEYS: Final[dict[LedgerImportSourceKind, str]] = {
    LedgerImportSourceKind.BANK_STATEMENT: "tui.ledger.import.kind.bank_statement",
    LedgerImportSourceKind.INVOICES_RECEIVED: "tui.ledger.import.kind.invoices_received",
    LedgerImportSourceKind.INVOICES_ISSUED: "tui.ledger.import.kind.invoices_issued",
}
_PROVIDER_LOCALE_KEYS: Final[dict[LedgerProviderID, str]] = {
    LedgerProviderID.AUTO: "tui.ledger.import.provider.auto",
    LedgerProviderID.CSV: "tui.ledger.import.provider.csv",
    LedgerProviderID.OFX: "tui.ledger.import.provider.ofx",
    LedgerProviderID.XLSX: "tui.ledger.import.provider.xlsx",
    LedgerProviderID.PDF_N26: "tui.ledger.import.provider.pdf_n26",
}

_EDITABLE_CONTROLS: Final = (
    "#ledger-import-kind",
    "#ledger-import-provider",
    "#ledger-import-country",
    "#ledger-import-path",
    "#ledger-import-browse",
    "#ledger-import-preview-button",
)


def import_outcome_lines(outcome: LedgerImportOutcomeV1) -> tuple[str, ...]:
    """Describe a preview or an applied import, keeping unmeasured counts unmeasured."""
    lines = [
        ledger_copy("tui.ledger.import.outcome.files", count=outcome.files),
        ledger_copy("tui.ledger.import.outcome.rows", count=outcome.rows),
    ]
    if outcome.imported is None or outcome.skipped is None:
        lines.append(ledger_copy("tui.ledger.import.outcome.not_measured"))
    elif outcome.dry_run:
        lines.append(ledger_copy("tui.ledger.import.outcome.would_import", count=outcome.imported))
        lines.append(ledger_copy("tui.ledger.import.outcome.would_skip", count=outcome.skipped))
    else:
        lines.append(ledger_copy("tui.ledger.import.outcome.did_import", count=outcome.imported))
        lines.append(ledger_copy("tui.ledger.import.outcome.did_skip", count=outcome.skipped))
    if outcome.likely_duplicates:
        lines.append(ledger_copy("tui.ledger.import.outcome.likely_duplicates", count=outcome.likely_duplicates))
    lines.extend(ledger_copy("tui.ledger.import.outcome.diagnostic", message=item) for item in outcome.diagnostics)
    lines.extend(
        ledger_copy("tui.ledger.import.outcome.refused_file", file=item.file_name, reason=item.reason)
        for item in outcome.refused_files
    )
    lines.extend(
        ledger_copy(
            "tui.ledger.import.outcome.refused_row",
            row=item.row_number,
            field=item.field,
            reason=item.reason,
        )
        for item in outcome.refused_rows
    )
    if outcome.unmapped_columns:
        lines.append(ledger_copy("tui.ledger.import.outcome.unmapped", columns=", ".join(outcome.unmapped_columns)))
    return tuple(lines)


class LedgerImportScreen(LedgerConfirmationFlowScreen):
    """Read an operator-chosen source, show what it would write, and write it on confirmation."""

    FLOW_NAME = "import"
    CSS: ClassVar[str] = LedgerConfirmationFlowScreen.CSS + tokenised(
        """
        #ledger-import-tree { height: $cadrumo-log-max-height; }
        #ledger-import-again { display: none; }
        #ledger-import-again.-open { display: block; }
        """
    )

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Start editing with nothing previewed."""
        super().__init__(controller, id="ledger-import-screen")
        self.previewed: LedgerImportRequestV1 | None = None
        self.outcome: LedgerImportOutcomeV1 | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.import.title"), classes="cadrumo-banner")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static(ledger_copy("tui.ledger.import.prompt"), markup=False)
            yield Static(ledger_copy("tui.ledger.import.kind_label"), markup=False)
            yield Select[str](
                tuple((ledger_copy(_SOURCE_KIND_LOCALE_KEYS[kind]), kind.value) for kind in LedgerImportSourceKind),
                value=LedgerImportSourceKind.BANK_STATEMENT.value,
                allow_blank=False,
                id="ledger-import-kind",
            )
            yield Static(
                ledger_copy("tui.ledger.import.provider_label"), id="ledger-import-provider-label", markup=False
            )
            yield Select[str](
                tuple((ledger_copy(_PROVIDER_LOCALE_KEYS[provider]), provider.value) for provider in IMPORT_PROVIDERS),
                value=LedgerProviderID.AUTO.value,
                allow_blank=False,
                id="ledger-import-provider",
            )
            yield Static(ledger_copy("tui.ledger.import.country_label"), id="ledger-import-country-label", markup=False)
            yield Input(value="ES", max_length=2, id="ledger-import-country")
            yield Static(ledger_copy("tui.ledger.import.path_label"), markup=False)
            yield Input(placeholder=ledger_copy("tui.ledger.import.path_placeholder"), id="ledger-import-path")
            yield Button(ledger_copy("tui.ledger.import.browse"), id="ledger-import-browse")
            yield Button(ledger_copy("tui.ledger.import.preview"), id="ledger-import-preview-button", variant="primary")
            yield Static("", id="ledger-import-preview", markup=False)
            yield Static("", id="ledger-flow-status", markup=False)
            yield Button(ledger_copy("tui.ledger.import.confirm"), id="ledger-import-confirm", disabled=True)
            yield Button(ledger_copy("tui.ledger.import.cancel"), id="ledger-import-cancel")
            yield Button(ledger_copy("tui.ledger.import.again"), id="ledger-import-again")
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Show only the controls that apply to the default source kind."""
        self.populate_navigation()
        self._show_kind_controls(LedgerImportSourceKind.BANK_STATEMENT)
        self.query_one("#ledger-import-path", Input).focus()

    @property
    def source_kind(self) -> LedgerImportSourceKind:
        """The source kind currently selected."""
        return LedgerImportSourceKind(str(cast("Select[str]", self.query_one("#ledger-import-kind", Select)).value))

    def _show_kind_controls(self, kind: LedgerImportSourceKind) -> None:
        bank = kind is LedgerImportSourceKind.BANK_STATEMENT
        for selector in ("#ledger-import-provider", "#ledger-import-provider-label"):
            self.query_one(selector).display = bank
        for selector in ("#ledger-import-country", "#ledger-import-country-label"):
            self.query_one(selector).display = not bank

    def on_select_changed(self, event: Select.Changed) -> None:
        """Swap the provider and country controls with the source kind."""
        if event.select.id == "ledger-import-kind" and self.flow_state is LedgerFlowState.EDITING:
            self._show_kind_controls(self.source_kind)
            self.query_one("#ledger-import-preview", Static).update("")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Take a browsed file as the source."""
        self._choose_path(event.path)

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Take a browsed folder as the source; every importable file in it is read."""
        self._choose_path(event.path)

    def _choose_path(self, path: Path) -> None:
        if self.flow_state is not LedgerFlowState.EDITING:
            return
        self.query_one("#ledger-import-path", Input).value = str(path)

    def _open_browser(self) -> None:
        """Mount the tree only when asked: it keeps a loader running for as long as it exists."""
        typed = Path(self.query_one("#ledger-import-path", Input).value.strip()).expanduser()
        if typed.is_dir():
            root = typed
        elif str(typed) != "." and typed.parent.is_dir():
            root = typed.parent
        else:
            root = Path.cwd()
        for existing in self.query("#ledger-import-tree"):
            existing.remove()
        tree = DirectoryTree(root, id="ledger-import-tree")
        self.query_one("#ledger-page", ContentScroll).mount(tree, after=self.query_one("#ledger-import-browse", Button))
        tree.focus()

    def _request(self) -> LedgerImportRequestV1 | None:
        """Build the request from the form, or show why it cannot be built."""
        notice = self.query_one("#ledger-refusal", Static)
        raw_path = self.query_one("#ledger-import-path", Input).value.strip()
        if not raw_path:
            notice.update(ledger_copy("tui.ledger.import.path_required"))
            return None
        path = Path(raw_path).expanduser()
        if not path.exists():
            notice.update(ledger_copy("tui.ledger.import.path_missing", path=raw_path))
            return None
        kind = self.source_kind
        country: str | None = None
        if kind is not LedgerImportSourceKind.BANK_STATEMENT:
            country = self.query_one("#ledger-import-country", Input).value.strip().upper() or None
            if country is None or len(country) != 2 or not country.isalpha():
                notice.update(ledger_copy("tui.ledger.import.country_required"))
                return None
        provider = LedgerProviderID(str(cast("Select[str]", self.query_one("#ledger-import-provider", Select)).value))
        notice.update("")
        return LedgerImportRequestV1(path=path, source_kind=kind, provider=provider, country=country)

    def _lock_form(self) -> None:
        for selector in _EDITABLE_CONTROLS:
            self.query_one(selector).disabled = True
        for tree in self.query("#ledger-import-tree"):
            tree.remove()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route each control through the flow's guarded transitions."""
        match event.button.id:
            case "ledger-import-browse" if self.flow_state is LedgerFlowState.EDITING:
                self._open_browser()
            case "ledger-import-preview-button" if self.flow_state is LedgerFlowState.EDITING:
                request = self._request()
                if request is not None:
                    event.button.disabled = True
                    self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.import.previewing"))
                    self.run_worker(self._preview(request), exclusive=True)
            case "ledger-import-cancel" if self.flow_state in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
                self._cancel_flow()
            case "ledger-import-confirm" if self.flow_state is LedgerFlowState.CONFIRMING:
                self._transition(LedgerFlowState.SUBMITTING)
                event.button.disabled = True
                self.query_one("#ledger-import-cancel", Button).disabled = True
                self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.import.progress"))
                self.run_worker(self._submit(), exclusive=True)
            case "ledger-import-again" if self.flow_state in {
                LedgerFlowState.SUCCEEDED,
                LedgerFlowState.FAILED,
                LedgerFlowState.CANCELLED,
            }:
                self._start_again()
            case _:
                return

    async def _preview(self, request: LedgerImportRequestV1) -> None:
        """Read the source without writing, then ask for confirmation."""
        status = self.query_one("#ledger-flow-status", Static)
        try:
            outcome = await self.controller.preview_import(request)
        except (CadrumoError, ValidationError) as error:
            status.update("")
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            self.query_one("#ledger-import-preview-button", Button).disabled = False
            return
        self.previewed = request
        self.query_one("#ledger-import-preview", Static).update("\n".join(import_outcome_lines(outcome)))
        self._lock_form()
        self._transition(LedgerFlowState.CONFIRMING)
        status.update(ledger_copy("tui.ledger.import.confirming"))
        confirm = self.query_one("#ledger-import-confirm", Button)
        confirm.disabled = False
        confirm.focus()

    async def _submit(self) -> None:
        """Apply exactly the request that was previewed."""
        status = self.query_one("#ledger-flow-status", Static)
        request = self.previewed
        if request is None:  # pragma: no cover - guarded before worker creation
            raise InternalInvariantError("previewed import disappeared before submission")
        try:
            outcome = await self.controller.apply_import(request)
        except (CadrumoError, ValidationError) as error:
            self._transition(LedgerFlowState.FAILED)
            status.update(ledger_copy("tui.ledger.import.failure"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        else:
            self.outcome = outcome
            self._transition(LedgerFlowState.SUCCEEDED)
            status.update(ledger_copy("tui.ledger.import.success", imported=outcome.imported, skipped=outcome.skipped))
            self.query_one("#ledger-import-preview", Static).update("\n".join(import_outcome_lines(outcome)))
        self._offer_again()

    def _offer_again(self) -> None:
        again = self.query_one("#ledger-import-again", Button)
        again.add_class("-open")
        again.focus()

    def _start_again(self) -> None:
        """Open a fresh import body over the state this one may have changed."""
        self.refresh_after_write()
        self.post_message(LedgerRouteRequested(self.controller.route_target(LedgerWorkspaceArea.IMPORT)))

    @override
    def _cancel_flow(self) -> None:
        if self.flow_state not in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
            return
        self.previewed = None
        self._transition(LedgerFlowState.CANCELLED)
        self._lock_form()
        self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.import.cancelled"))
        self.query_one("#ledger-import-confirm", Button).disabled = True
        self.query_one("#ledger-import-cancel", Button).disabled = True
        self._offer_again()


__all__ = ["IMPORT_PROVIDERS", "LedgerImportScreen", "import_outcome_lines"]
