"""Command-bound classification and import interaction tests."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from typing import cast, override

import pytest
from textual.containers import VerticalScroll
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Select, Static

from .....application.ledger.actions_import import LedgerProviderID
from .....application.ledger.models import ManualLedgerTransactionResult
from .....application.ledger.workspace import LedgerWorkspaceArea
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.identity.transaction_ids import TransactionId
from .....domain.transactions.enums import BusinessClassification
from .....domain.transactions.errors import TransactionValidationError
from .....domain.transactions.models import BucketTransactionRef
from ....tui.components.host import ScreenHostApp
from ...tests.frame import geometry_band
from ..classification import LedgerClassificationScreen
from ..controller import LedgerWorkspaceController
from ..import_flow import LedgerImportScreen, import_outcome_lines
from ..models import (
    LedgerClassificationSubmissionV1,
    LedgerFlowState,
    LedgerImportOutcomeV1,
    LedgerImportRequestV1,
    LedgerImportSourceKind,
)
from ..routes import ledger_screen_factory, resolve_ledger_screen
from ..workspace_injection import LedgerWorkspaceInjection
from .test_ledger_workspace import _context, _focused_context, _projection, _review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FLOW_COPY = {
    OutputLanguage.ES: ("Clasificar apunte contable", "Importar apuntes contables"),
    OutputLanguage.EN: ("Classify ledger entry", "Import ledger entries"),
    OutputLanguage.CA: ("Classificar assentament comptable", "Importar assentaments comptables"),
    OutputLanguage.HU: ("Főkönyvi tétel besorolása", "Főkönyvi tételek importálása"),
}


class _ClassificationDoor:
    def __init__(self) -> None:
        self.calls: list[LedgerClassificationSubmissionV1] = []

    async def __call__(self, submission: LedgerClassificationSubmissionV1) -> ManualLedgerTransactionResult:
        self.calls.append(submission)
        return ManualLedgerTransactionResult.model_construct(
            ref=BucketTransactionRef.model_construct(transaction_id=submission.transaction_id),
        )


class _ImportDoor:
    """Records every preview and apply, answering with fixed synthetic counts."""

    def __init__(self) -> None:
        self.previews: list[LedgerImportRequestV1] = []
        self.applied: list[LedgerImportRequestV1] = []

    def _outcome(self, request: LedgerImportRequestV1, *, dry_run: bool) -> LedgerImportOutcomeV1:
        return LedgerImportOutcomeV1(
            source_kind=request.source_kind,
            dry_run=dry_run,
            files=1,
            rows=3,
            imported=2,
            skipped=1,
            likely_duplicates=1,
        )

    async def preview(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        self.previews.append(request)
        return self._outcome(request, dry_run=True)

    async def apply(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        self.applied.append(request)
        return self._outcome(request, dry_run=False)


class _SlowClassificationDoor(_ClassificationDoor):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    @override
    async def __call__(self, submission: LedgerClassificationSubmissionV1) -> ManualLedgerTransactionResult:
        self.calls.append(submission)
        self.started.set()
        await self.release.wait()
        return ManualLedgerTransactionResult.model_construct(
            ref=BucketTransactionRef.model_construct(transaction_id=submission.transaction_id),
        )


class _SlowImportDoor(_ImportDoor):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    @override
    async def apply(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        self.applied.append(request)
        self.started.set()
        await self.release.wait()
        return self._outcome(request, dry_run=False)


class _RefusingImportDoor(_ImportDoor):
    """Refuses to apply with the application's own typed, translated error."""

    @override
    async def apply(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        self.applied.append(request)
        raise TransactionValidationError(
            translated_message="errors.transaction.ledger_import_failed",
            context={"operation": "parse", "path": "statement.csv", "reason": "synthetic-provider refused"},
        )


def _import_controller(door: _ImportDoor | None) -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        _context(),
        _projection(),
        LedgerWorkspaceInjection(review_action=_review_action(), import_door=door),
    )


async def _preview(pilot: Pilot[None], screen: LedgerImportScreen, path: Path) -> None:
    screen.query_one("#ledger-import-path", Input).value = str(path)
    screen.query_one("#ledger-import-preview-button", Button).press()
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def _classify_action() -> ActionReference:
    return ActionReference(action_id=lookup_action("operator.ledger.classify").action_id)


@pytest.mark.asyncio
async def test_classification_is_explicit_confirmable_cancelable_and_catalogue_authorized() -> None:
    projection = _projection()
    door = _ClassificationDoor()
    controller = LedgerWorkspaceController(
        _focused_context(projection.entries[0].transaction_id),
        projection,
        LedgerWorkspaceInjection(
            review_action=_review_action(),
            classify_action=_classify_action(),
            classification_submitter=door,
        ),
    )
    screen = cast(
        "LedgerClassificationScreen",
        resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.CLASSIFICATION)),
    )
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#ledger-classifications", DataTable)
        assert tuple(row.key.value for row in table.ordered_rows) == ("BUSINESS", "PERSONAL", "REVIEWED_EXCLUDED")
        target_copy = str(screen.query_one("#ledger-classification-target", Static).render())
        assert "1" in target_copy and "2" in target_copy and "aaaaaaaaaaaa" in target_copy
        await pilot.press("enter")
        assert screen.flow_state is LedgerFlowState.CONFIRMING
        await pilot.press("escape")
        assert screen.flow_state is LedgerFlowState.CANCELLED
        assert not door.calls
        await pilot.press("enter", "enter", "enter")
        assert not door.calls

    success_door = _ClassificationDoor()
    success_controller = LedgerWorkspaceController(
        _focused_context(projection.entries[0].transaction_id),
        projection,
        LedgerWorkspaceInjection(
            review_action=_review_action(),
            classify_action=_classify_action(),
            classification_submitter=success_door,
        ),
    )
    success_screen = LedgerClassificationScreen(success_controller)
    success_app = ScreenHostApp[None](success_screen)
    async with success_app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("enter", "enter", "enter")
        await pilot.pause()
        assert success_screen.flow_state is LedgerFlowState.SUCCEEDED
        assert len(success_door.calls) == 1
        with pytest.raises(AttributeError):
            success_screen.flow_state = LedgerFlowState.EDITING  # type: ignore[misc]
    assert success_door.calls[0].action == _classify_action()
    assert success_door.calls[0].transaction_id == projection.entries[0].transaction_id
    assert success_door.calls[0].patch.business_classification is BusinessClassification.BUSINESS


@pytest.mark.asyncio
async def test_import_previews_first_then_applies_exactly_the_previewed_request(tmp_path: Path) -> None:
    statement = tmp_path / "statement.csv"
    statement.write_text("date,amount\n", encoding="utf-8")
    door = _ImportDoor()
    controller = _import_controller(door)
    screen = cast(
        "LedgerImportScreen",
        resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.IMPORT)),
    )
    app = ScreenHostApp[None](screen)
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(100, 60)) as pilot:
            await pilot.pause()
            cast("Select[str]", screen.query_one("#ledger-import-provider", Select)).value = LedgerProviderID.CSV.value
            await _preview(pilot, screen, statement)
            assert screen.flow_state is LedgerFlowState.CONFIRMING
            assert door.previews == [
                LedgerImportRequestV1(
                    path=statement,
                    source_kind=LedgerImportSourceKind.BANK_STATEMENT,
                    provider=LedgerProviderID.CSV,
                )
            ]
            assert not door.applied
            preview = str(screen.query_one("#ledger-import-preview", Static).render())
            assert "Would import: 2" in preview
            assert "Possible duplicates: 1" in preview
            # The form is frozen once previewed, so what is applied is what was shown.
            assert screen.query_one("#ledger-import-path", Input).disabled
            screen.query_one("#ledger-import-confirm", Button).press()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert screen.flow_state is LedgerFlowState.SUCCEEDED
            assert door.applied == door.previews
            assert "Imported: 2" in str(screen.query_one("#ledger-import-preview", Static).render())
            screen.query_one("#ledger-import-confirm", Button).press()
            await pilot.pause()
            assert len(door.applied) == 1


@pytest.mark.asyncio
async def test_import_cancel_after_preview_writes_nothing(tmp_path: Path) -> None:
    statement = tmp_path / "statement.csv"
    statement.write_text("date,amount\n", encoding="utf-8")
    door = _ImportDoor()
    screen = LedgerImportScreen(_import_controller(door))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(100, 60)) as pilot:
        await pilot.pause()
        await _preview(pilot, screen, statement)
        assert screen.flow_state is LedgerFlowState.CONFIRMING
        await pilot.press("escape")
        assert screen.flow_state is LedgerFlowState.CANCELLED
        assert not door.applied
        assert screen.query_one("#ledger-import-again", Button).has_class("-open")


@pytest.mark.asyncio
async def test_import_refuses_an_absent_path_and_an_invoice_book_without_country(tmp_path: Path) -> None:
    door = _ImportDoor()
    screen = LedgerImportScreen(_import_controller(door))
    app = ScreenHostApp[None](screen)
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(100, 60)) as pilot:
            await pilot.pause()
            await _preview(pilot, screen, tmp_path / "absent.csv")
            assert screen.flow_state is LedgerFlowState.EDITING
            assert "Nothing exists at" in str(screen.query_one("#ledger-refusal", Static).render())
            book = tmp_path / "received.csv"
            book.write_text("invoice_number\n", encoding="utf-8")
            cast(
                "Select[str]", screen.query_one("#ledger-import-kind", Select)
            ).value = LedgerImportSourceKind.INVOICES_RECEIVED.value
            await pilot.pause()
            assert not screen.query_one("#ledger-import-provider", Select).display
            screen.query_one("#ledger-import-country", Input).value = ""
            await _preview(pilot, screen, book)
            assert "two letters" in str(screen.query_one("#ledger-refusal", Static).render())
            assert not door.previews
            screen.query_one("#ledger-import-country", Input).value = "es"
            await _preview(pilot, screen, book)
            assert door.previews[-1].country == "ES"
            assert door.previews[-1].source_kind is LedgerImportSourceKind.INVOICES_RECEIVED


def test_an_unmeasured_invoice_preview_never_reads_as_zero() -> None:
    outcome = LedgerImportOutcomeV1(
        source_kind=LedgerImportSourceKind.INVOICES_ISSUED,
        dry_run=True,
        files=1,
        rows=4,
        imported=None,
        skipped=None,
        unmapped_columns=("memo",),
    )
    with override_settings(cadrumo_output_language="en"):
        lines = import_outcome_lines(outcome)
    assert not any("Would import" in line for line in lines)
    assert any("only counted when the import is applied" in line for line in lines)
    assert any("memo" in line for line in lines)


@pytest.mark.asyncio
async def test_escape_is_refused_while_classification_submission_is_in_flight() -> None:
    projection = _projection()
    door = _SlowClassificationDoor()
    controller = LedgerWorkspaceController(
        _focused_context(projection.entries[0].transaction_id),
        projection,
        LedgerWorkspaceInjection(
            review_action=_review_action(),
            classify_action=_classify_action(),
            classification_submitter=door,
        ),
    )
    screen = LedgerClassificationScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("enter", "enter")
        await asyncio.wait_for(door.started.wait(), timeout=1)
        assert screen.flow_state is LedgerFlowState.SUBMITTING
        await pilot.press("escape")
        await pilot.pause()
        assert not screen.back_requested
        assert screen.is_mounted
        assert str(screen.query_one("#ledger-flow-status", Static).render())
        door.release.set()
        await app.workers.wait_for_complete()
        assert screen.flow_state is LedgerFlowState.SUCCEEDED
        assert not screen.back_requested


@pytest.mark.asyncio
async def test_escape_is_refused_while_import_submission_is_in_flight(tmp_path: Path) -> None:
    statement = tmp_path / "statement.csv"
    statement.write_text("date,amount\n", encoding="utf-8")
    door = _SlowImportDoor()
    screen = LedgerImportScreen(_import_controller(door))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(100, 60)) as pilot:
        await pilot.pause()
        await _preview(pilot, screen, statement)
        screen.query_one("#ledger-import-confirm", Button).press()
        await asyncio.wait_for(door.started.wait(), timeout=1)
        assert screen.flow_state is LedgerFlowState.SUBMITTING
        await pilot.press("escape")
        await pilot.pause()
        assert not screen.back_requested
        assert screen.is_mounted
        door.release.set()
        await app.workers.wait_for_complete()
        assert screen.flow_state is LedgerFlowState.SUCCEEDED
        assert len(door.applied) == 1


@pytest.mark.asyncio
async def test_import_refusal_is_the_application_message_in_the_operator_language(tmp_path: Path) -> None:
    statement = tmp_path / "statement.csv"
    statement.write_text("date,amount\n", encoding="utf-8")
    door = _RefusingImportDoor()
    with override_settings(cadrumo_output_language="en"):
        screen = LedgerImportScreen(_import_controller(door))
        app = ScreenHostApp[None](screen)
        async with app.run_test(size=(100, 60)) as pilot:
            await pilot.pause()
            await _preview(pilot, screen, statement)
            screen.query_one("#ledger-import-confirm", Button).press()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert screen.flow_state is LedgerFlowState.FAILED
            rendered = "\n".join(str(widget.render()) for widget in screen.query(Static))
            assert "The import could not be completed." in rendered
            assert "synthetic-provider" in str(screen.query_one("#ledger-refusal", Static).render())
            assert "TransactionValidationError" not in rendered
            assert "errors.transaction" not in rendered


def test_import_area_is_refused_without_its_door() -> None:
    refusal = _import_controller(None).refusal_for(LedgerWorkspaceArea.IMPORT)
    assert refusal is not None
    assert refusal.reason_key == "tui.ledger.refusal.submission_unavailable"
    assert _import_controller(_ImportDoor()).refusal_for(LedgerWorkspaceArea.IMPORT) is None


def test_factory_refuses_undeclared_or_drifted_classification_action() -> None:
    with pytest.raises(KeyError, match="unknown operator action ID"):
        ledger_screen_factory(
            _projection(),
            review_action=ActionReference(action_id="operator.ledger.review"),
            classify_action=ActionReference(action_id="operator.ledger.absent"),
        )


def test_controller_refuses_off_projection_classification() -> None:
    projection = _projection()
    door = _ClassificationDoor()
    controller = LedgerWorkspaceController(
        _context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=_review_action(),
            classify_action=_classify_action(),
            classification_submitter=door,
        ),
    )
    # The refusal now guards the selection itself rather than an injected
    # target: an entry the operator cannot see is one they cannot have chosen.
    with pytest.raises(ValueError, match="absent from the visible Ledger projection"):
        controller.with_transaction_focus(cast("TransactionId", "f" * 64))
    assert not door.calls
    with pytest.raises(ValueError, match="canonical command"):
        ledger_screen_factory(
            _projection(),
            review_action=ActionReference(action_id="operator.ledger.review"),
            classify_action=ActionReference(action_id="operator.ledger.review"),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", tuple(OutputLanguage))
async def test_flow_copy_is_localized_while_semantic_choices_are_invariant(locale: OutputLanguage) -> None:
    projection = _projection()
    controller = LedgerWorkspaceController(
        _focused_context(projection.entries[0].transaction_id),
        projection,
        LedgerWorkspaceInjection(
            review_action=_review_action(),
            classify_action=_classify_action(),
            classification_submitter=_ClassificationDoor(),
            import_door=_ImportDoor(),
        ),
    )
    with override_settings(cadrumo_output_language=locale.value):
        classification = LedgerClassificationScreen(controller)
        classification_app = ScreenHostApp[None](classification)
        async with classification_app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            rendered = "\n".join(str(widget.render()) for widget in classification.query(Static))
            assert _FLOW_COPY[locale][0] in rendered
            assert "tui.ledger." not in rendered
            assert tuple(
                row.key.value for row in classification.query_one("#ledger-classifications", DataTable).ordered_rows
            ) == ("BUSINESS", "PERSONAL", "REVIEWED_EXCLUDED")
        import_screen = LedgerImportScreen(controller)
        import_app = ScreenHostApp[None](import_screen)
        async with import_app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            rendered = "\n".join(str(widget.render()) for widget in import_screen.query(Static))
            assert _FLOW_COPY[locale][1] in rendered
            assert "tui.ledger." not in rendered
            kinds = cast("Select[str]", import_screen.query_one("#ledger-import-kind", Select))
            for kind in LedgerImportSourceKind:
                kinds.value = kind.value
                assert kinds.value == kind.value


@pytest.mark.asyncio
async def test_classification_flow_has_exact_focus_and_real_compositor_geometry() -> None:
    projection = _projection()
    controller = LedgerWorkspaceController(
        _focused_context(projection.entries[0].transaction_id),
        projection,
        LedgerWorkspaceInjection(
            review_action=_review_action(),
            classify_action=_classify_action(),
            classification_submitter=_ClassificationDoor(),
        ),
    )
    screen = LedgerClassificationScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table_id = "ledger-classifications"
        assert app.focused is screen.query_one(f"#{table_id}", DataTable)
        assert tuple(widget.id for widget in screen.focus_chain) == (
            "ledger-navigation",
            table_id,
            "ledger-classification-cancel",
        )
        await pilot.press("enter")
        assert app.focused is screen.query_one("#ledger-classification-confirm")
        assert geometry_band(app, 80) == []
        assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
        owners = tuple(
            widget for widget in screen.query(VerticalScroll) if widget.display and widget.show_vertical_scrollbar
        )
        assert len(owners) <= 1
        assert all(isinstance(owner, VerticalScroll) and owner.id == "ledger-page" for owner in owners)


@pytest.mark.asyncio
async def test_import_flow_starts_at_the_path_and_keeps_one_scroll_owner() -> None:
    screen = LedgerImportScreen(_import_controller(_ImportDoor()))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.focused is screen.query_one("#ledger-import-path", Input)
        chain = tuple(widget.id for widget in screen.focus_chain)
        assert chain[0] == "ledger-navigation"
        assert "ledger-import-confirm" not in chain
        assert "ledger-import-tree" not in chain
        assert geometry_band(app, 80) == []
        owners = tuple(
            widget for widget in screen.query(VerticalScroll) if widget.display and widget.show_vertical_scrollbar
        )
        assert all(owner.id == "ledger-page" for owner in owners)


def test_flow_modules_reach_writers_only_through_injected_doors() -> None:
    """The screens take a path from the operator, but only a door reads or writes it."""
    package = Path(__file__).parents[1]
    trees = {
        path.name: ast.parse(path.read_text(encoding="utf-8"))
        for path in (
            package / "classification.py",
            package / "import_flow.py",
            package / "invoice_entry.py",
            package / "evidence.py",
        )
    }
    imports = {
        node.module or "" for tree in trees.values() for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imported_names = {
        alias.name
        for tree in trees.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for tree in trees.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not any("adapters" in name or "entrypoints.cli" in name for name in imports)
    assert (
        not {
            "import_ledger_source",
            "plan_ledger_import_sources",
            "import_invoices_from_rows",
            "build_catalogue_invoice",
            "create_catalogue_invoice",
            "PurchaseInvoiceEvidenceService",
        }
        & imported_names
    )
    assert not {"open", "read", "read_text", "read_bytes", "write_text", "import_ledger_source"} & calls


@pytest.mark.asyncio
async def test_browse_mounts_a_tree_at_the_typed_folder_and_a_choice_fills_the_path(tmp_path: Path) -> None:
    from textual.widgets import DirectoryTree

    statement = tmp_path / "statement.csv"
    statement.write_text("date,amount\n", encoding="utf-8")
    screen = LedgerImportScreen(_import_controller(_ImportDoor()))
    async with ScreenHostApp[None](screen).run_test(size=(100, 60)) as pilot:
        await pilot.pause()
        assert not screen.query("#ledger-import-tree")
        screen.query_one("#ledger-import-path", Input).value = str(tmp_path)
        screen.query_one("#ledger-import-browse", Button).press()
        await pilot.pause()
        tree = screen.query_one("#ledger-import-tree", DirectoryTree)
        assert Path(tree.path) == tmp_path
        screen.post_message(DirectoryTree.FileSelected(tree.root, statement))
        await pilot.pause()
        assert screen.query_one("#ledger-import-path", Input).value == str(statement)


@pytest.mark.asyncio
async def test_refresh_after_a_write_runs_off_the_loop_and_coalesces_repeated_back() -> None:
    import threading

    from ..workspace_injection import LedgerWorkspaceRefreshV1

    projection = _projection()
    release = threading.Event()
    calls: list[int] = []

    def slow_refresh() -> LedgerWorkspaceRefreshV1:
        calls.append(1)
        release.wait(timeout=10)
        return LedgerWorkspaceRefreshV1(projection=projection, evidence_items=None)

    controller = LedgerWorkspaceController(
        _focused_context(projection.entries[0].transaction_id),
        projection,
        LedgerWorkspaceInjection(
            review_action=_review_action(),
            classify_action=_classify_action(),
            classification_submitter=_ClassificationDoor(),
            refresh=slow_refresh,
        ),
    )
    screen = LedgerClassificationScreen(controller)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.press("enter", "enter")
            await pilot.pause()
            assert screen.flow_state is LedgerFlowState.SUCCEEDED
            await pilot.press("escape")
            await pilot.pause()
            assert screen.refreshing
            assert not screen.back_requested
            assert "Updating" in str(screen.query_one("#ledger-flow-status", Static).render())
            # The loop still answers keys while the read is out; a second Back joins the first.
            await pilot.press("escape", "down")
            await pilot.pause()
            assert screen.refreshing
            release.set()
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
            assert not screen.refreshing
            assert screen.back_requested
            assert calls == [1]
            assert len(screen.refresh_seconds) == 1
