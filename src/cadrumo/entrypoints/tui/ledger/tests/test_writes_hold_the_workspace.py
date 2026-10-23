"""A Records write in flight keeps its body, and a write whose outcome is unknown is said to be unknown.

Each write flow submits through a door held mid-flight. While it is held, an
area change, a tool choice and Back are refused on screen, because leaving
would cancel the awaited door after submission and lose its outcome. Once the
door settles, the outcome renders on the same body and the body can be left.
A door that settles with an unknown outcome is reported as unknown, never as
refused, together with the instruction to read the records again.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast, override
from uuid import UUID

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Static

from .....application.bienes_inversion.registered_requests import BienesInversionDeclareRequest
from .....application.bienes_inversion.registered_result_contracts import BienesInversionDeclareProjection
from .....application.invoices.catalogue_intake_contracts import (
    InvoiceImportProjection,
    InvoiceImportRequest,
    InvoiceWizardOutcome,
    InvoiceWizardRequest,
)
from .....application.invoices.catalogue_lifecycle import CatalogueInvoicePatch
from .....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from .....application.ledger.evidence_mutation_operation import (
    LedgerEvidenceUpdateProjection,
    LedgerEvidenceUpdateRequest,
)
from .....application.ledger.export_operation import LedgerExportRequest
from .....application.ledger.ledger_add_contracts import LedgerAddRequest
from .....application.ledger.llm_review_contracts import LedgerLlmReviewRequest
from .....application.ledger.models import ManualLedgerTransactionResult
from .....application.ledger.remove_operation import LedgerRemoveRequest
from .....application.ledger.reset_operation import LedgerResetRequest
from .....application.ledger.review_operation import LedgerReviewProjection, LedgerReviewRequest
from .....application.ledger.transaction_projection import LedgerTransactionProjection
from .....application.ledger.update_contracts import LedgerUpdatePatch, LedgerUpdatePatchField
from .....application.ledger.workspace import LedgerWorkspaceArea
from .....application.operations.frontend_projection import OperationPublicProjectionV1
from .....core.config import override_settings
from .....core.errors.error_codes import resolve_error_message
from .....core.i18n.render import tr
from .....core.operations import OperationEffect, OperationTerminalCondition
from .....domain.transactions.enums import BusinessClassification
from ...components.dialogs import ConfirmScreen
from ...navigation import TuiFocusIdentityV1, TuiScreenContextV1
from ...operations.outcome import OperationOutcomeUnknownError
from ...tests.settling import settle
from ..categorisation_doors import LedgerRuleAddDoorV1, LedgerRuleApplyDoorV1, LedgerRuleListDoorV1
from ..categorisation_review import LedgerSuggestionReviewScreen
from ..categorisation_rules import LedgerRulesScreen
from ..classification import LedgerClassificationScreen
from ..controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from ..entries_add import LedgerEntryAddScreen
from ..entries_browse import LedgerEntriesBrowseScreen
from ..entries_doors import LedgerAddDoorV1, LedgerExportDoorV1, LedgerRemoveDoorV1, LedgerResetDoorV1
from ..entries_export import LedgerEntriesExportScreen
from ..entries_reset import LedgerResetScreen
from ..evidence import LedgerEvidenceScreen
from ..evidence_files_doors import LedgerEvidenceFilesDoorV1
from ..evidence_files_records import LedgerEvidenceFilesRecordsScreen
from ..evidence_files_write import LedgerEvidenceFilesWriteScreen
from ..import_flow import LedgerImportScreen
from ..invoice_entry import LedgerInvoiceEntryScreen
from ..invoices_import import LedgerInvoiceImportScreen
from ..invoices_wizard import LedgerInvoiceWizardScreen
from ..models import (
    LedgerClassificationSubmissionV1,
    LedgerEvidenceRecordRowV1,
    LedgerExclusionSubmissionV1,
    LedgerFlowState,
    LedgerImportOutcomeV1,
    LedgerImportRequestV1,
    LedgerInvoiceAddResultV1,
    LedgerInvoiceEntryV1,
    LedgerLinkResultV1,
    LedgerLinkSubmissionV1,
    LedgerRecordDoorsV1,
)
from ..own_accounts import LedgerOwnAccountDoorV1, LedgerOwnAccountsScreen
from ..reconciliation import LedgerReconciliationScreen
from ..record_views import LedgerInvoiceDetailScreen
from ..registers_capital_goods import LedgerCapitalGoodsDoorV1, LedgerCapitalGoodsScreen
from ..review import LedgerReviewDoorV1, LedgerReviewScreen
from ..tools import LedgerToolV1
from ..transaction_views import LedgerTransactionDetailScreen
from ..workspace_injection import LedgerWorkspaceInjection, LedgerWorkspaceRefreshV1
from .categorisation_fixtures import MemoryDoor, MemoryRuleBook, synthetic_id
from .categorisation_memory_doors import MemoryCategorisationProfile, categorisation_controller
from .categorisation_review_fixtures import MemoryReviewController, MemoryReviewDoor
from .entries_door_fixtures import MemoryEntriesLedger, entries_controller, entry_id
from .evidence_files_fixtures import MemoryEvidenceFilesStore
from .invoices_fixtures import (
    MemoryInvoiceImportDoor,
    MemoryInvoiceWizardDoor,
    MemoryRecordDoors,
    ReplacingHostApp,
    invoice_snapshot,
)
from .invoices_fixtures import transaction_projection as synthetic_transaction
from .own_account_fixtures import SYNTHETIC_ES_IBAN, MemoryOwnAccountDoor
from .registers_fixtures import MemoryCapitalGoodsDoor
from .test_categorisation_review import _ask as ask_for_review
from .test_categorisation_review import _decide as decide_review
from .test_invoices_import import _review as review_invoice_import
from .test_invoices_wizard import _fill_and_review as review_invoice_wizard
from .test_ledger_flows import _ImportDoor, _preview
from .test_ledger_ingestion_surfaces import _EvidenceDoor, _ExclusionDoor, _InvoiceDoor
from .test_ledger_slice3 import _TX, _link_action, _LinkDoor
from .test_ledger_tools import _tool
from .workspace_fixtures import (
    ClassificationDoor,
    ledger_classify_action,
    ledger_context,
    ledger_evidence_action,
    ledger_focused_context,
    ledger_projection,
    ledger_reconciled_projection,
    ledger_review_action,
    ledger_review_door,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_OVERVIEW_ROW = tuple(LedgerWorkspaceArea).index(LedgerWorkspaceArea.OVERVIEW)
_UNKNOWN = OperationOutcomeUnknownError(operation_id="f" * 64, effect=OperationEffect.UNKNOWN)
_EVIDENCE_PATH = "C:/synthetic/invoice_A-0003.pdf"


class _Gate:
    """Holds every door call that reaches it until released, then answers or raises the configured error."""

    def __init__(self, error: OperationOutcomeUnknownError | None) -> None:
        self.error = error
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def wait(self) -> None:
        self.started.set()
        await self.release.wait()
        if self.error is not None:
            raise self.error


class _ProfileDoor[RequestT, ResultT](Protocol):
    @property
    def profile_id(self) -> UUID: ...

    async def __call__(self, request: RequestT, /) -> ResultT: ...


class _HeldDoor[RequestT, ResultT]:
    """One profile-bound door whose chosen requests wait at the gate before they are answered."""

    def __init__(
        self,
        door: _ProfileDoor[RequestT, ResultT],
        gate: _Gate,
        *,
        hold: Callable[[RequestT], bool] = lambda _request: True,
    ) -> None:
        self._door = door
        self._gate = gate
        self._hold = hold

    @property
    def profile_id(self) -> UUID:
        return self._door.profile_id

    async def __call__(self, request: RequestT, /) -> ResultT:
        if self._hold(request):
            await self._gate.wait()
        return await self._door(request)


@dataclass(frozen=True)
class _Flow:
    """One write flow: the body it opens on, how its write is submitted, and what a saved write shows."""

    body: LedgerWorkspaceScreen
    submit: Callable[[Pilot[None]], Awaitable[LedgerWorkspaceScreen]]
    """Drive the screen until its write is out; answer the body that awaits it."""
    saved: Callable[[Pilot[None], LedgerWorkspaceScreen], None]
    unknown_line: Callable[[], str] = lambda: tr("tui.ledger.flow.outcome_unknown")
    leaves_after_saving: bool = True
    """Whether the body is still shown once the write is saved, so leaving it can be tried."""


async def _press(pilot: Pilot[None], body: LedgerWorkspaceScreen, button_id: str) -> None:
    """Press a button whose work is not held, and wait for it to finish."""
    body.query_one(f"#{button_id}", Button).press()
    await settle(pilot)


async def _click(pilot: Pilot[None], body: LedgerWorkspaceScreen, button_id: str) -> None:
    """Press a button and wait for the messages it posts, without waiting for the workers it starts."""
    body.query_one(f"#{button_id}", Button).press()
    await settle(pilot, workers=False)


async def _accept(pilot: Pilot[None]) -> None:
    dialog = pilot.app.screen
    assert isinstance(dialog, ConfirmScreen)
    dialog.query_one("#btn-confirm-accept", Button).press()
    await settle(pilot, workers=False)


def _text(body: LedgerWorkspaceScreen, selector: str) -> str:
    return str(body.query_one(selector, Static).render())


def _rendered(body: LedgerWorkspaceScreen) -> str:
    return "\n".join(str(widget.render()) for widget in body.query(Static))


def _status(body: LedgerWorkspaceScreen) -> str:
    found = body.query("#ledger-flow-status")
    return str(cast(Static, found.first()).render()) if found else _text(body, "#ledger-refusal")


async def _choose_overview(pilot: Pilot[None], body: LedgerWorkspaceScreen) -> None:
    navigation = body.query_one("#ledger-navigation", DataTable)
    navigation.focus()
    navigation.move_cursor(row=_OVERVIEW_ROW)
    await pilot.press("enter")
    await settle(pilot, workers=False)


async def _cannot_leave(pilot: Pilot[None], body: LedgerWorkspaceScreen) -> None:
    """Try an area, a tool where the body lists one, and Back; each is refused on screen."""
    refusal = tr("tui.ledger.flow.in_flight_refusal")
    await _choose_overview(pilot, body)
    assert pilot.app.screen is body
    assert body.requested_target is None
    assert _status(body) == refusal
    if body.query("#ledger-tools"):
        _status_line(body).update("")
        tools = body.query_one("#ledger-tools", DataTable)
        assert tools.row_count
        tools.focus()
        tools.move_cursor(row=0)
        await pilot.press("enter")
        await settle(pilot, workers=False)
        assert pilot.app.screen is body
        assert _status(body) == refusal
    _status_line(body).update("")
    await pilot.press("escape")
    await settle(pilot, workers=False)
    assert pilot.app.screen is body
    assert not body.back_requested
    assert _status(body) == refusal


def _status_line(body: LedgerWorkspaceScreen) -> Static:
    found = body.query("#ledger-flow-status")
    return cast(Static, found.first()) if found else body.query_one("#ledger-refusal", Static)


def _tools(area: LedgerWorkspaceArea) -> tuple[LedgerToolV1, ...]:
    return (_tool(area, "held"),)


# -- Area bodies -----------------------------------------------------------------


class _HeldClassificationDoor(ClassificationDoor):
    def __init__(self, gate: _Gate) -> None:
        super().__init__()
        self._gate = gate

    @override
    async def __call__(self, submission: LedgerClassificationSubmissionV1) -> ManualLedgerTransactionResult:
        await self._gate.wait()
        return await super().__call__(submission)


def _classification(gate: _Gate, _tmp_path: Path) -> _Flow:
    projection = ledger_projection()
    door = _HeldClassificationDoor(gate)
    controller = LedgerWorkspaceController(
        ledger_focused_context(projection.entries[0].transaction_id),
        projection,
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            classify_action=ledger_classify_action(),
            classification_submitter=door,
            tools=_tools(LedgerWorkspaceArea.CLASSIFICATION),
        ),
    )
    body = LedgerClassificationScreen(controller)

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        body.query_one("#ledger-classifications", DataTable).focus()
        await pilot.press("enter")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot, workers=False)
        return body

    def saved(_pilot: Pilot[None], shown: LedgerWorkspaceScreen) -> None:
        assert body.flow_state is LedgerFlowState.SUCCEEDED
        assert _status(shown) == tr("tui.ledger.classification.success")
        assert len(door.calls) == 1

    return _Flow(body, submit, saved)


class _HeldImportDoor(_ImportDoor):
    def __init__(self, gate: _Gate) -> None:
        super().__init__()
        self._gate = gate

    @override
    async def apply(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        await self._gate.wait()
        return await super().apply(request)


def _bank_import(gate: _Gate, tmp_path: Path) -> _Flow:
    statement = tmp_path / "statement.csv"
    statement.write_text("date,amount\n", encoding="utf-8")
    door = _HeldImportDoor(gate)
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(), import_door=door, tools=_tools(LedgerWorkspaceArea.IMPORT)
        ),
    )
    body = LedgerImportScreen(controller)

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        await _preview(pilot, body, statement)
        await _click(pilot, body, "ledger-import-confirm")
        return body

    def saved(_pilot: Pilot[None], _shown: LedgerWorkspaceScreen) -> None:
        assert body.flow_state is LedgerFlowState.SUCCEEDED
        assert len(door.applied) == 1

    return _Flow(body, submit, saved)


class _HeldLinkDoor(_LinkDoor):
    def __init__(self, gate: _Gate) -> None:
        super().__init__()
        self._gate = gate

    @override
    async def __call__(self, submission: LedgerLinkSubmissionV1) -> LedgerLinkResultV1:
        await self._gate.wait()
        return await super().__call__(submission)


def _reconciliation(gate: _Gate, _tmp_path: Path) -> _Flow:
    door = _HeldLinkDoor(gate)
    context = TuiScreenContextV1(
        destination="workbench.ledger",
        focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.transaction", restore_token=_TX),
    )
    controller = LedgerWorkspaceController(
        context,
        ledger_reconciled_projection(),
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            link_action=_link_action(),
            link_submitter=door,
            tools=_tools(LedgerWorkspaceArea.RECONCILIATION),
        ),
    )
    body = LedgerReconciliationScreen(controller)

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        body.query_one("#ledger-suggestions", DataTable).focus()
        await pilot.press("enter")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot, workers=False)
        return body

    def saved(_pilot: Pilot[None], shown: LedgerWorkspaceScreen) -> None:
        assert body.flow_state is LedgerFlowState.SUCCEEDED
        assert _status(shown) == tr("tui.ledger.reconciliation.success")
        assert len(door.calls) == 1

    return _Flow(body, submit, saved)


class _HeldExclusionDoor(_ExclusionDoor):
    def __init__(self, gate: _Gate) -> None:
        super().__init__()
        self._gate = gate

    @override
    async def __call__(self, submission: LedgerExclusionSubmissionV1) -> ManualLedgerTransactionResult:
        await self._gate.wait()
        return await super().__call__(submission)


def _review_exclusion(gate: _Gate, _tmp_path: Path) -> _Flow:
    door = _HeldExclusionDoor(gate)
    projection = ledger_projection()
    controller = LedgerWorkspaceController(
        ledger_context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            review_door=ledger_review_door(projection),
            classify_action=ledger_classify_action(),
            classification_submitter=ClassificationDoor(),
            exclusion_submitter=door,
            tools=_tools(LedgerWorkspaceArea.REVIEW),
        ),
    )
    body = LedgerReviewScreen(controller)

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        review = body.query_one("#ledger-review", DataTable)
        review.focus()
        review.move_cursor(row=0)
        await pilot.press("x")
        await settle(pilot)
        await _click(pilot, body, "ledger-exclusion-confirm")
        return body

    def saved(pilot: Pilot[None], _shown: LedgerWorkspaceScreen) -> None:
        assert len(door.calls) == 1
        # A saved exclusion reopens the review list over the re-read workspace.
        assert isinstance(pilot.app.screen, LedgerReviewScreen)
        assert pilot.app.screen is not body

    return _Flow(body, submit, saved, leaves_after_saving=False)


class _HeldEvidenceDoor(_EvidenceDoor):
    def __init__(self, gate: _Gate) -> None:
        super().__init__(ready=False)
        self._gate = gate

    @override
    async def add(self, source_path: str) -> LedgerEvidenceRecordRowV1:
        await self._gate.wait()
        return await super().add(source_path)


def _evidence_add(gate: _Gate, _tmp_path: Path) -> _Flow:
    door = _HeldEvidenceDoor(gate)
    projection = ledger_projection()
    controller = LedgerWorkspaceController(
        ledger_context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            evidence_action=ledger_evidence_action(),
            evidence_items=(),
            evidence_door=door,
            refresh=lambda: LedgerWorkspaceRefreshV1(projection=projection, evidence_items=()),
            tools=_tools(LedgerWorkspaceArea.EVIDENCE),
        ),
    )
    body = LedgerEvidenceScreen(controller)

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        body.query_one("#ledger-evidence-path", Input).value = _EVIDENCE_PATH
        await _click(pilot, body, "ledger-evidence-add")
        return body

    def saved(_pilot: Pilot[None], shown: LedgerWorkspaceScreen) -> None:
        assert door.added == [_EVIDENCE_PATH]
        assert _status(shown) == tr("tui.ledger.evidence.added", file="invoice_A-0003.pdf")

    return _Flow(body, submit, saved)


# -- Entry tools -----------------------------------------------------------------


def _entry_add(gate: _Gate, _tmp_path: Path) -> _Flow:
    ledger = MemoryEntriesLedger.with_entries(2)
    doors = ledger.doors()
    held = replace(doors, add=cast(LedgerAddDoorV1, _HeldDoor[LedgerAddRequest, object](doors.add, gate)))
    body = LedgerEntryAddScreen(entries_controller(), held)

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        body.query_one("#entries-add-booked-date", Input).value = "2026-03-14"
        body.query_one("#entries-add-amount", Input).value = "120.50"
        body.query_one("#entries-add-description", Input).value = "Material de oficina"
        await _press(pilot, body, "entries-add-review")
        await _click(pilot, body, "entries-add-confirm")
        return body

    def saved(_pilot: Pilot[None], _shown: LedgerWorkspaceScreen) -> None:
        assert body.flow_state is LedgerFlowState.SUCCEEDED
        assert len(ledger.entries) == 3

    return _Flow(body, submit, saved)


def _entry_export(gate: _Gate, tmp_path: Path) -> _Flow:
    ledger = MemoryEntriesLedger.with_entries(2)
    doors = ledger.doors()
    held = replace(doors, export=cast(LedgerExportDoorV1, _HeldDoor[LedgerExportRequest, object](doors.export, gate)))
    body = LedgerEntriesExportScreen(entries_controller(), held)
    path = str(tmp_path / "ledger.csv")

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        body.query_one("#entries-export-path", Input).value = path
        await _press(pilot, body, "entries-export-review")
        await _click(pilot, body, "entries-export-confirm")
        return body

    def saved(_pilot: Pilot[None], shown: LedgerWorkspaceScreen) -> None:
        assert body.flow_state is LedgerFlowState.SUCCEEDED
        assert tr("tui.ledger.entry_tools.export.written", path=path) in _status(shown)

    return _Flow(
        body,
        submit,
        saved,
        lambda: tr("tui.ledger.entry_tools.export.unknown", path=path),
    )


def _entry_reset(gate: _Gate, _tmp_path: Path) -> _Flow:
    ledger = MemoryEntriesLedger.with_entries(4)
    doors = ledger.doors()
    held_reset = _HeldDoor[LedgerResetRequest, object](doors.reset, gate, hold=lambda request: not request.dry_run)
    body = LedgerResetScreen(entries_controller(), replace(doors, reset=cast(LedgerResetDoorV1, held_reset)))

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        body.query_one("#entries-reset-reason", Input).value = "start over with a clean import"
        await _press(pilot, body, "entries-reset-preview-button")
        await _click(pilot, body, "entries-reset-run")
        await _accept(pilot)
        return body

    def saved(_pilot: Pilot[None], shown: LedgerWorkspaceScreen) -> None:
        assert body.flow_state is LedgerFlowState.SUCCEEDED
        assert _status(shown) == tr("tui.ledger.entry_tools.reset.done", count=4)

    return _Flow(body, submit, saved)


def _entry_removal(gate: _Gate, _tmp_path: Path) -> _Flow:
    ledger = MemoryEntriesLedger.with_entries(3)
    doors = ledger.doors()
    held_remove = _HeldDoor[LedgerRemoveRequest, object](doors.remove, gate, hold=lambda request: not request.dry_run)
    body = LedgerEntriesBrowseScreen(entries_controller(), replace(doors, remove=cast(LedgerRemoveDoorV1, held_remove)))

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        table = body.query_one("#entries-browse", DataTable)
        table.focus()
        table.move_cursor(row=2)
        await pilot.press("enter")
        await settle(pilot)
        await _click(pilot, body, "entries-browse-remove")
        await settle(pilot)
        await _accept(pilot)
        return body

    def saved(_pilot: Pilot[None], _shown: LedgerWorkspaceScreen) -> None:
        assert body.page is not None
        assert entry_id(2) not in {row.transaction.transaction_id for row in body.page.rows}

    return _Flow(body, submit, saved)


# -- Records, registers and accounts ------------------------------------------------


def _own_account(gate: _Gate, _tmp_path: Path) -> _Flow:
    door = _HeldDoor(MemoryOwnAccountDoor(), gate, hold=lambda request: request.action != "list")
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(), own_account_door=cast(LedgerOwnAccountDoorV1, door)
        ),
    )
    body = LedgerOwnAccountsScreen(controller, cast(LedgerOwnAccountDoorV1, door))

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        await _press(pilot, body, "own-account-new")
        body.query_one("#own-account-label", Input).value = "main"
        body.query_one("#own-account-iban", Input).value = SYNTHETIC_ES_IBAN
        await _press(pilot, body, "own-account-review")
        assert body.staged is not None, _text(body, "#ledger-refusal")
        await _click(pilot, body, "own-account-confirm")
        return body

    def saved(_pilot: Pilot[None], shown: LedgerWorkspaceScreen) -> None:
        assert _status(shown) == tr("tui.ledger.records.saved")
        assert len(body.accounts) == 1

    return _Flow(body, submit, saved)


class _HeldRecordDoors(MemoryRecordDoors):
    def __init__(
        self,
        gate: _Gate,
        invoices: tuple[CatalogueInvoiceSnapshot, ...] = (),
        transactions: tuple[LedgerTransactionProjection, ...] = (),
    ) -> None:
        super().__init__(invoices, transactions)
        self._gate = gate

    @override
    async def update_invoice(
        self, baseline: CatalogueInvoiceSnapshot, patch: CatalogueInvoicePatch
    ) -> CatalogueInvoiceSnapshot:
        await self._gate.wait()
        return await super().update_invoice(baseline, patch)

    @override
    async def update_transaction(
        self,
        baseline: LedgerTransactionProjection,
        patch: LedgerUpdatePatch,
        fields: tuple[LedgerUpdatePatchField, ...],
    ) -> LedgerTransactionProjection:
        await self._gate.wait()
        return await super().update_transaction(baseline, patch, fields)


def _record_controller(doors: MemoryRecordDoors) -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), record_doors=cast(LedgerRecordDoorsV1, doors)),
    )


def _invoice_correction(gate: _Gate, _tmp_path: Path) -> _Flow:
    invoice = invoice_snapshot()
    doors = _HeldRecordDoors(gate, invoices=(invoice,))
    body = LedgerInvoiceDetailScreen(_record_controller(doors), cast(LedgerRecordDoorsV1, doors), invoice.invoice_id)

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        body.query_one("#ledger-invoice-notes", Input).value = "after"
        await _press(pilot, body, "ledger-invoice-edit-review")
        await _click(pilot, body, "ledger-invoice-edit-save")
        return body

    def saved(_pilot: Pilot[None], shown: LedgerWorkspaceScreen) -> None:
        assert _status(shown) == tr("tui.ledger.records.saved")
        assert doors.catalogue[invoice.invoice_id].notes == "after"

    return _Flow(body, submit, saved)


def _transaction_correction(gate: _Gate, _tmp_path: Path) -> _Flow:
    transaction = synthetic_transaction()
    doors = _HeldRecordDoors(gate, transactions=(transaction,))
    body = LedgerTransactionDetailScreen(
        _record_controller(doors), cast(LedgerRecordDoorsV1, doors), transaction.transaction_id
    )

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        body.query_one("#ledger-transaction-description", Input).value = "changed description"
        await _press(pilot, body, "ledger-transaction-edit-review")
        await _click(pilot, body, "ledger-transaction-edit-save")
        return body

    def saved(_pilot: Pilot[None], shown: LedgerWorkspaceScreen) -> None:
        assert _status(shown) == tr("tui.ledger.records.saved")
        assert doors.transactions[transaction.transaction_id].description == "changed description"

    return _Flow(body, submit, saved)


class _HeldCapitalGoodsDoor(MemoryCapitalGoodsDoor):
    def __init__(self, gate: _Gate) -> None:
        super().__init__()
        self._gate = gate

    @override
    async def declare(self, request: BienesInversionDeclareRequest) -> BienesInversionDeclareProjection:
        await self._gate.wait()
        return await super().declare(request)


def _capital_good(gate: _Gate, _tmp_path: Path) -> _Flow:
    door = _HeldCapitalGoodsDoor(gate)
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    body = LedgerCapitalGoodsScreen(controller, cast(LedgerCapitalGoodsDoorV1, door))

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        for selector, value in (
            ("#capital-identifier", "BI-02"),
            ("#capital-description", "Synthetic delivery van"),
            ("#capital-year", "2025"),
            ("#capital-ledger-id", "tx-synthetic-02"),
            ("#capital-cuota", "4200.00"),
            ("#capital-prorrata", "80"),
            ("#capital-kind", "synthetic_kind"),
        ):
            body.query_one(selector, Input).value = value
        await _press(pilot, body, "register-review")
        assert body.staged is not None, _text(body, "#ledger-refusal")
        await _click(pilot, body, "register-confirm")
        return body

    def saved(_pilot: Pilot[None], shown: LedgerWorkspaceScreen) -> None:
        assert tr("tui.ledger.registers.capital_goods.declared", count=1) in _text(shown, "#register-result")
        assert _status(shown) == tr("tui.ledger.records.saved")

    return _Flow(body, submit, saved)


# -- Invoices ------------------------------------------------------------------------


class _HeldInvoiceImportDoor(MemoryInvoiceImportDoor):
    def __init__(self, gate: _Gate) -> None:
        super().__init__()
        self._gate = gate

    @override
    async def apply(self, request: InvoiceImportRequest) -> InvoiceImportProjection:
        await self._gate.wait()
        return await super().apply(request)


def _invoice_import(gate: _Gate, _tmp_path: Path) -> _Flow:
    door = _HeldInvoiceImportDoor(gate)
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    body = LedgerInvoiceImportScreen(controller, door)

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        await review_invoice_import(pilot, body)
        await _click(pilot, body, "ledger-invoices-import-confirm")
        return body

    def saved(_pilot: Pilot[None], _shown: LedgerWorkspaceScreen) -> None:
        assert body.flow_state is LedgerFlowState.SUCCEEDED
        assert len(door.requests) == 1

    return _Flow(body, submit, saved)


class _HeldInvoiceWizardDoor(MemoryInvoiceWizardDoor):
    def __init__(self, gate: _Gate) -> None:
        super().__init__()
        self._gate = gate

    @override
    async def __call__(self, request: InvoiceWizardRequest) -> InvoiceWizardOutcome:
        await self._gate.wait()
        return await super().__call__(request)


def _invoice_wizard(gate: _Gate, _tmp_path: Path) -> _Flow:
    door = _HeldInvoiceWizardDoor(gate)
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    body = LedgerInvoiceWizardScreen(controller, door)

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        await review_invoice_wizard(pilot, body)
        await _click(pilot, body, "ledger-invoices-wizard-confirm")
        return body

    def saved(_pilot: Pilot[None], _shown: LedgerWorkspaceScreen) -> None:
        assert body.flow_state is LedgerFlowState.SUCCEEDED
        assert len(door.requests) == 1

    return _Flow(body, submit, saved)


class _HeldInvoiceDoor(_InvoiceDoor):
    def __init__(self, gate: _Gate) -> None:
        super().__init__()
        self._gate = gate

    @override
    async def __call__(self, entry: LedgerInvoiceEntryV1) -> LedgerInvoiceAddResultV1:
        await self._gate.wait()
        return await super().__call__(entry)


def _invoice_entry(gate: _Gate, _tmp_path: Path) -> _Flow:
    door = _HeldInvoiceDoor(gate)
    body = LedgerInvoiceEntryScreen(
        LedgerWorkspaceController(
            ledger_context(),
            ledger_projection(),
            LedgerWorkspaceInjection(review_action=ledger_review_action(), invoice_add_door=door),
        )
    )

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        for name, value in (
            ("counterparty-name", "Hardware Profesional Sur SL"),
            ("counterparty-nif", "B92000090"),
            ("invoice-number", "A-0003"),
            ("invoice-date", "2026-03-27"),
            ("taxable-base", "1200.00"),
            ("iva-rate", "21"),
        ):
            body.query_one(f"#ledger-invoice-{name}", Input).value = value
        await _press(pilot, body, "ledger-invoice-review")
        await _click(pilot, body, "ledger-invoice-confirm")
        return body

    def saved(_pilot: Pilot[None], _shown: LedgerWorkspaceScreen) -> None:
        assert body.flow_state is LedgerFlowState.SUCCEEDED
        assert [entry.taxable_base for entry in door.entries] == [Decimal("1200.00")]

    return _Flow(body, submit, saved)


# -- Categorisation and evidence files -------------------------------------------------


def _classification_rule(gate: _Gate, _tmp_path: Path) -> _Flow:
    book = MemoryRuleBook(
        entries={synthetic_id(1): ("Papelería Norte factura 12", BusinessClassification.NOT_YET_PROCESSED)}
    )
    add_door = MemoryDoor(book.add_rule)
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    body = LedgerRulesScreen(
        controller,
        list_door=cast(LedgerRuleListDoorV1, MemoryDoor(book.list_rules)),
        add_door=cast(LedgerRuleAddDoorV1, _HeldDoor(add_door, gate)),
        apply_door=cast(LedgerRuleApplyDoorV1, MemoryDoor(book.apply_rules)),
    )

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        body.query_one("#categorisation-rule-pattern", Input).value = "papelería"
        await _press(pilot, body, "categorisation-rule-review-add")
        assert body.staged is not None
        await _click(pilot, body, "categorisation-confirm")
        return body

    def saved(_pilot: Pilot[None], shown: LedgerWorkspaceScreen) -> None:
        assert len(book.rules) == 1
        assert body.staged is None
        assert _status(shown) == tr("tui.ledger.categorisation.saved")

    return _Flow(body, submit, saved)


def _evidence_record_correction(gate: _Gate, _tmp_path: Path) -> _Flow:
    store = MemoryEvidenceFilesStore()
    store.seed_records(3)
    doors = store.doors()
    held_update = cast(
        LedgerEvidenceFilesDoorV1[LedgerEvidenceUpdateRequest, LedgerEvidenceUpdateProjection],
        _HeldDoor(doors.update, gate),
    )
    held = replace(doors, update=held_update)
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    body = LedgerEvidenceFilesRecordsScreen(controller, held)

    async def submit(pilot: Pilot[None]) -> LedgerWorkspaceScreen:
        table = body.query_one("#evidence-files-records", DataTable)
        table.focus()
        table.move_cursor(row=1)
        await pilot.press("enter")
        await settle(pilot)
        body.query_one("#evidence-files-field-supplier", Input).value = "Suministros Gamma SL"
        await _press(pilot, body, "evidence-files-review-update")
        write = pilot.app.screen
        assert isinstance(write, LedgerEvidenceFilesWriteScreen)
        await _click(pilot, write, "evidence-files-confirm")
        return write

    def saved(_pilot: Pilot[None], shown: LedgerWorkspaceScreen) -> None:
        assert isinstance(shown, LedgerEvidenceFilesWriteScreen)
        assert shown.flow_state is LedgerFlowState.SUCCEEDED
        assert _status(shown) == tr("tui.ledger.evidence_files.write.saved")

    return _Flow(body, submit, saved)


_FLOWS: dict[str, Callable[[_Gate, Path], _Flow]] = {
    "bank-import": _bank_import,
    "capital-good": _capital_good,
    "classification": _classification,
    "classification-rule": _classification_rule,
    "entry-add": _entry_add,
    "entry-export": _entry_export,
    "entry-removal": _entry_removal,
    "entry-reset": _entry_reset,
    "evidence-add": _evidence_add,
    "evidence-record-correction": _evidence_record_correction,
    "invoice-correction": _invoice_correction,
    "invoice-entry": _invoice_entry,
    "invoice-import": _invoice_import,
    "invoice-wizard": _invoice_wizard,
    "own-account": _own_account,
    "reconciliation": _reconciliation,
    "review-exclusion": _review_exclusion,
    "transaction-correction": _transaction_correction,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("name", sorted(_FLOWS))
async def test_a_write_in_flight_keeps_its_body_until_its_outcome_renders(name: str, tmp_path: Path) -> None:
    gate = _Gate(error=None)
    with override_settings(cadrumo_output_language="en"):
        flow = _FLOWS[name](gate, tmp_path)
        async with ReplacingHostApp(flow.body).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            body = await flow.submit(pilot)
            await asyncio.wait_for(gate.started.wait(), timeout=10)
            assert body.in_flight
            await _cannot_leave(pilot, body)

            gate.release.set()
            await settle(pilot)
            assert not body.in_flight
            flow.saved(pilot, body)
            if flow.leaves_after_saving:
                # The same Back that was refused while the write was out now leaves the body.
                await pilot.press("escape")
                await settle(pilot)
                assert pilot.app.screen is not body


@pytest.mark.asyncio
@pytest.mark.parametrize("name", sorted(_FLOWS))
async def test_a_write_whose_outcome_is_unknown_is_said_to_be_unknown(name: str, tmp_path: Path) -> None:
    gate = _Gate(error=_UNKNOWN)
    gate.release.set()
    with override_settings(cadrumo_output_language="en"):
        flow = _FLOWS[name](gate, tmp_path)
        async with ReplacingHostApp(flow.body).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            body = await flow.submit(pilot)
            await settle(pilot)
            assert pilot.app.screen is body
            assert not body.in_flight
            rendered = _rendered(body)
            assert flow.unknown_line() in rendered
            assert resolve_error_message(_UNKNOWN) in rendered
            assert body.write_outcome_unknown
            # Saying "refused" or "not saved" would invite a retry that could apply the change twice.
            assert tr("tui.ledger.records.failed") not in rendered
            assert tr("tui.ledger.categorisation.failed") not in rendered


class _UnknownReviewController(MemoryReviewController):
    """A review whose decision settles as failed after it may have written."""

    @override
    def projection(self) -> OperationPublicProjectionV1:
        settled = super().projection()
        if self.decision is None:
            return settled
        return OperationPublicProjectionV1.model_validate(
            {
                **settled.model_dump(),
                "terminal_condition": OperationTerminalCondition.FAILED,
                "effect": OperationEffect.UNKNOWN,
                "result_ref": None,
            }
        )


class _UnknownReviewDoor(MemoryReviewDoor):
    @override
    async def submit(self, request: LedgerLlmReviewRequest) -> MemoryReviewController:
        transaction_id = next(key for key in self.ledger.entries if key.startswith(request.transaction_id))
        controller = _UnknownReviewController(request, self.definition_id, transaction_id)
        self.controllers.append(controller)
        return controller


@pytest.mark.asyncio
async def test_a_review_that_settles_failed_with_an_effect_is_said_to_be_unknown() -> None:
    profile = MemoryCategorisationProfile()
    door = _UnknownReviewDoor(profile.ledger)
    screen = LedgerSuggestionReviewScreen(categorisation_controller(), door=door)
    with override_settings(cadrumo_output_language="en"):
        async with ReplacingHostApp(screen).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            await ask_for_review(pilot, screen, "categorisation-review-ask")
            await decide_review(pilot, "btn-operation-apply")
            assert _status(screen) == tr("tui.ledger.flow.outcome_unknown")
            unknown = OperationOutcomeUnknownError(operation_id=door.controllers[0].operation_id, effect=None)
            assert resolve_error_message(unknown) in _text(screen, "#ledger-refusal")
            assert tr("tui.ledger.categorisation.not_done") not in _text(screen, "#ledger-refusal")
            assert screen.write_outcome_unknown
            assert door.results == []


class _CountingGate(_Gate):
    """A gate that also counts the door calls that reached it."""

    def __init__(self, error: OperationOutcomeUnknownError | None) -> None:
        super().__init__(error)
        self.calls = 0

    @override
    async def wait(self) -> None:
        self.calls += 1
        await super().wait()


class _HeldRereadDoor:
    """The review queue door: the first read opens the area, and every later re-read waits at the gate."""

    def __init__(self, door: LedgerReviewDoorV1, gate: _Gate) -> None:
        self._door = door
        self._gate = gate
        self._reads = 0

    @property
    def profile_id(self) -> UUID:
        return self._door.profile_id

    async def __call__(self, request: LedgerReviewRequest) -> LedgerReviewProjection:
        self._reads += 1
        if self._reads > 1:
            await self._gate.wait()
        return await self._door(request)


@pytest.mark.asyncio
async def test_an_exclusion_whose_outcome_is_unknown_is_offered_again_only_over_a_reread_queue() -> None:
    write = _CountingGate(error=_UNKNOWN)
    write.release.set()
    reread = _Gate(error=None)
    projection = ledger_projection()
    queue = ledger_review_door(projection)
    held_queue = _HeldRereadDoor(queue, reread)
    controller = LedgerWorkspaceController(
        ledger_context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            review_door=held_queue,
            classify_action=ledger_classify_action(),
            classification_submitter=ClassificationDoor(),
            exclusion_submitter=_HeldExclusionDoor(write),
            tools=_tools(LedgerWorkspaceArea.REVIEW),
        ),
    )
    body = LedgerReviewScreen(controller)
    with override_settings(cadrumo_output_language="en"):
        async with ReplacingHostApp(body).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            listed = body.rows
            assert listed
            review = body.query_one("#ledger-review", DataTable)
            review.focus()
            review.move_cursor(row=0)
            await pilot.press("x")
            await settle(pilot)
            await _click(pilot, body, "ledger-exclusion-confirm")
            await asyncio.wait_for(reread.started.wait(), timeout=10)

            # The entry may already be excluded: until the queue is read again, nothing is offered to exclude.
            assert body.rows == ()
            assert body.pending_exclusion is None
            await pilot.press("x")
            await settle(pilot, workers=False)
            assert body.pending_exclusion is None
            assert write.calls == 1

            reread.release.set()
            await settle(pilot)
            assert len(queue.requests) == 2
            assert body.rows == listed
            assert _status(body) == tr("tui.ledger.flow.outcome_unknown")
            assert resolve_error_message(_UNKNOWN) in _text(body, "#ledger-refusal")
            assert pilot.app.screen is body


@pytest.mark.asyncio
async def test_an_evidence_addition_whose_outcome_is_unknown_is_offered_again_only_over_reread_records() -> None:
    write = _CountingGate(error=_UNKNOWN)
    write.release.set()
    door = _HeldEvidenceDoor(write)
    projection = ledger_projection()
    refreshing = threading.Event()
    refreshed = threading.Event()
    refreshes: list[int] = []

    def refresh() -> LedgerWorkspaceRefreshV1:
        refreshes.append(1)
        refreshing.set()
        refreshed.wait(timeout=10)
        return LedgerWorkspaceRefreshV1(projection=projection, evidence_items=())

    controller = LedgerWorkspaceController(
        ledger_context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            evidence_action=ledger_evidence_action(),
            evidence_items=(),
            evidence_door=door,
            refresh=refresh,
            tools=_tools(LedgerWorkspaceArea.EVIDENCE),
        ),
    )
    body = LedgerEvidenceScreen(controller)
    with override_settings(cadrumo_output_language="en"):
        async with ReplacingHostApp(body).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            body.query_one("#ledger-evidence-path", Input).value = _EVIDENCE_PATH
            await _click(pilot, body, "ledger-evidence-add")
            assert await asyncio.to_thread(refreshing.wait, 10)
            await settle(pilot, workers=False)

            # The document may already be added: until the records are read again, the addition is not offered.
            add = body.query_one("#ledger-evidence-add", Button)
            assert add.disabled
            await _click(pilot, body, "ledger-evidence-add")
            assert write.calls == 1

            refreshed.set()
            await settle(pilot)
            assert refreshes == [1]
            assert not add.disabled
            assert _status(body) == tr("tui.ledger.flow.outcome_unknown")
            assert resolve_error_message(_UNKNOWN) in _text(body, "#ledger-refusal")
