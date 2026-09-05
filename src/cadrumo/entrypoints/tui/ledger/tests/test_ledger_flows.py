"""Command-bound classification and prepared-import interaction tests."""

from __future__ import annotations

import ast
import asyncio
import pickle
from pathlib import Path
from types import SimpleNamespace
from typing import cast, override

import pytest
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Input, Static

from .....application.ledger.models import (
    LedgerSourceImportCommand,
    LedgerSourceImportResult,
    ManualLedgerTransactionResult,
)
from .....application.ledger.workspace import LedgerWorkspaceArea
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.identity import TransactionId
from .....domain.transactions.enums import BusinessClassification
from ....tui.components.host import ScreenHostApp
from ....tui.devtools.frame import geometry_band
from ..classification import LedgerClassificationScreen
from ..controller import LedgerEntrySelected, LedgerWorkspaceController, ledger_copy
from ..entries import LedgerEntriesScreen
from ..import_flow import LedgerImportScreen
from ..models import LedgerClassificationSubmissionV1, LedgerFlowState, LedgerPreparedImportV1
from ..overview import LedgerOverviewScreen
from ..routes import ledger_screen_factory, resolve_ledger_screen
from ..workspace_injection import LedgerWorkspaceInjection
from .test_ledger_workspace import _context, _projection, _review_action

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
        return cast(
            "ManualLedgerTransactionResult",
            SimpleNamespace(ref=SimpleNamespace(transaction_id=submission.transaction_id)),
        )


class _ImportDoor:
    def __init__(self) -> None:
        self.calls: list[LedgerSourceImportCommand] = []

    async def __call__(self, command: LedgerSourceImportCommand) -> LedgerSourceImportResult:
        self.calls.append(command)
        return LedgerSourceImportResult(
            rows=3,
            imported=2,
            skipped=1,
            dry_run=False,
            verify=False,
            validations=(),
            sources=(),
        )


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
        return cast(
            "ManualLedgerTransactionResult",
            SimpleNamespace(ref=SimpleNamespace(transaction_id=submission.transaction_id)),
        )


class _SlowImportDoor(_ImportDoor):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    @override
    async def __call__(self, command: LedgerSourceImportCommand) -> LedgerSourceImportResult:
        self.calls.append(command)
        self.started.set()
        await self.release.wait()
        return LedgerSourceImportResult(
            rows=1,
            imported=1,
            skipped=0,
            dry_run=False,
            verify=False,
            validations=(),
            sources=(),
        )


class _FailingImportDoor:
    async def __call__(self, command: LedgerSourceImportCommand) -> LedgerSourceImportResult:
        del command
        raise RuntimeError("private-provider C:/private/customer-sensitive-statement.csv")


def _classify_action() -> ActionReference:
    return ActionReference(action_id=lookup_action("operator.ledger.classify").action_id)


@pytest.mark.asyncio
async def test_classification_is_explicit_confirmable_cancelable_and_catalogue_authorized() -> None:
    projection = _projection()
    door = _ClassificationDoor()
    controller = LedgerWorkspaceController(
        _context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=_review_action(),
            classify_action=_classify_action(),
            classification_target=projection.entries[0].transaction_id,
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
        _context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=_review_action(),
            classify_action=_classify_action(),
            classification_target=projection.entries[0].transaction_id,
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
async def test_import_only_submits_injected_opaque_prepared_command_and_redacts_path() -> None:
    protected_label = "customer-sensitive-statement.csv"
    command = LedgerSourceImportCommand(path=Path("C:/private") / protected_label, provider="private-provider")
    prepared = LedgerPreparedImportV1(
        choice_id="prepared-bank",
        provider_label_key="tui.ledger.import.provider.bank",
        source_label_key="tui.ledger.import.source.prepared",
        command=command,
    )
    assert protected_label not in repr(prepared)
    assert "private-provider" not in repr(prepared)
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(prepared)
    with pytest.raises(AttributeError, match="immutable"):
        LedgerPreparedImportV1.__setattr__(prepared, "choice_id", "swapped")
    door = _ImportDoor()
    controller = LedgerWorkspaceController(
        _context(),
        _projection(),
        LedgerWorkspaceInjection(review_action=_review_action(), prepared_imports=(prepared,), import_submitter=door),
    )
    screen = cast(
        "LedgerImportScreen",
        resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.IMPORT)),
    )
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert not door.calls
        rendered = "\n".join(str(widget.render()) for widget in screen.query(Static))
        assert protected_label not in rendered
        assert "private-provider" not in rendered
        await pilot.press("enter", "enter")
        await pilot.pause()
        assert screen.flow_state is LedgerFlowState.SUCCEEDED
        assert door.calls == [command]
        await pilot.press("enter", "escape")
        assert len(door.calls) == 1
        assert screen.flow_state is LedgerFlowState.SUCCEEDED


@pytest.mark.asyncio
async def test_escape_is_refused_while_classification_submission_is_in_flight() -> None:
    projection = _projection()
    door = _SlowClassificationDoor()
    controller = LedgerWorkspaceController(
        _context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=_review_action(),
            classify_action=_classify_action(),
            classification_target=projection.entries[0].transaction_id,
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
async def test_escape_is_refused_while_import_submission_is_in_flight() -> None:
    command = LedgerSourceImportCommand(path=Path("C:/synthetic/input.csv"), provider="bank")
    prepared = LedgerPreparedImportV1(
        choice_id="prepared-bank",
        provider_label_key="tui.ledger.import.provider.bank",
        source_label_key="tui.ledger.import.source.prepared",
        command=command,
    )
    door = _SlowImportDoor()
    controller = LedgerWorkspaceController(
        _context(),
        _projection(),
        LedgerWorkspaceInjection(review_action=_review_action(), prepared_imports=(prepared,), import_submitter=door),
    )
    screen = LedgerImportScreen(controller)
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
        door.release.set()
        await app.workers.wait_for_complete()
        assert screen.flow_state is LedgerFlowState.SUCCEEDED
        assert len(door.calls) == 1


@pytest.mark.asyncio
async def test_import_failure_is_localized_and_never_leaks_exception_path_or_provider() -> None:
    protected_path = "C:/private/customer-sensitive-statement.csv"
    protected_provider = "private-provider"
    prepared = LedgerPreparedImportV1(
        choice_id="prepared-bank",
        provider_label_key="tui.ledger.import.provider.bank",
        source_label_key="tui.ledger.import.source.prepared",
        command=LedgerSourceImportCommand(path=Path(protected_path), provider=protected_provider),
    )
    controller = LedgerWorkspaceController(
        _context(),
        _projection(),
        LedgerWorkspaceInjection(
            review_action=_review_action(), prepared_imports=(prepared,), import_submitter=_FailingImportDoor()
        ),
    )
    with override_settings(cadrumo_output_language="en"):
        screen = LedgerImportScreen(controller)
        app = ScreenHostApp[None](screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.press("enter", "enter")
            await app.workers.wait_for_complete()
            assert screen.flow_state is LedgerFlowState.FAILED
            rendered = "\n".join(str(widget.render()) for widget in screen.query(Static))
            assert "The import could not be completed." in rendered
            assert protected_path not in rendered
            assert protected_provider not in rendered
            assert "RuntimeError" not in rendered


def test_factory_refuses_undeclared_or_drifted_classification_action() -> None:
    with pytest.raises(KeyError, match="unknown operator action ID"):
        ledger_screen_factory(
            _projection(),
            review_action=ActionReference(action_id="operator.ledger.review"),
            classify_action=ActionReference(action_id="operator.ledger.absent"),
        )


def test_controller_refuses_off_projection_classification_and_unsafe_or_duplicate_import_choices() -> None:
    projection = _projection()
    door = _ClassificationDoor()
    with pytest.raises(ValueError, match="absent from the visible Ledger projection"):
        LedgerWorkspaceController(
            _context(),
            projection,
            LedgerWorkspaceInjection(
                review_action=_review_action(),
                classify_action=_classify_action(),
                classification_target=cast("TransactionId", "f" * 64),
                classification_submitter=door,
            ),
        )
    assert not door.calls
    command = LedgerSourceImportCommand(path=Path("C:/private/statement.csv"), provider="bank")
    with pytest.raises(ValueError, match="safe Ledger catalogue identities"):
        LedgerPreparedImportV1(
            choice_id="../unsafe",
            provider_label_key="tui.ledger.import.provider.bank",
            source_label_key="tui.ledger.import.source.prepared",
            command=command,
        )
    prepared = LedgerPreparedImportV1(
        choice_id="duplicate",
        provider_label_key="tui.ledger.import.provider.bank",
        source_label_key="tui.ledger.import.source.prepared",
        command=command,
    )
    with pytest.raises(ValueError, match="must be unique"):
        LedgerWorkspaceController(
            _context(),
            projection,
            LedgerWorkspaceInjection(
                review_action=_review_action(), prepared_imports=(prepared, prepared), import_submitter=_ImportDoor()
            ),
        )
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
    command = LedgerSourceImportCommand(path=Path("C:/synthetic/input.csv"), provider="bank")
    prepared = LedgerPreparedImportV1(
        choice_id="prepared-bank",
        provider_label_key="tui.ledger.import.provider.bank",
        source_label_key="tui.ledger.import.source.prepared",
        command=command,
    )
    controller = LedgerWorkspaceController(
        _context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=_review_action(),
            classify_action=_classify_action(),
            classification_target=projection.entries[0].transaction_id,
            classification_submitter=_ClassificationDoor(),
            prepared_imports=(prepared,),
            import_submitter=_ImportDoor(),
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
            assert tuple(
                row.key.value for row in import_screen.query_one("#ledger-import-choices", DataTable).ordered_rows
            ) == ("prepared-bank",)


@pytest.mark.asyncio
@pytest.mark.parametrize("screen_kind", ("classification", "import"))
async def test_new_flows_have_exact_focus_and_real_compositor_geometry(screen_kind: str) -> None:
    projection = _projection()
    command = LedgerSourceImportCommand(path=Path("C:/synthetic/input.csv"), provider="bank")
    prepared = LedgerPreparedImportV1(
        choice_id="prepared-bank",
        provider_label_key="tui.ledger.import.provider.bank",
        source_label_key="tui.ledger.import.source.prepared",
        command=command,
    )
    controller = LedgerWorkspaceController(
        _context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=_review_action(),
            classify_action=_classify_action(),
            classification_target=projection.entries[0].transaction_id,
            classification_submitter=_ClassificationDoor(),
            prepared_imports=(prepared,),
            import_submitter=_ImportDoor(),
        ),
    )
    screen = (
        LedgerClassificationScreen(controller) if screen_kind == "classification" else LedgerImportScreen(controller)
    )
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table_id = "ledger-classifications" if screen_kind == "classification" else "ledger-import-choices"
        assert app.focused is screen.query_one(f"#{table_id}", DataTable)
        assert tuple(widget.id for widget in screen.focus_chain) == (
            "ledger-navigation",
            table_id,
            f"ledger-{screen_kind}-cancel",
        )
        await pilot.press("enter")
        assert app.focused is screen.query_one(f"#ledger-{screen_kind}-confirm")
        assert tuple(widget.id for widget in screen.focus_chain) == (
            "ledger-navigation",
            table_id,
            f"ledger-{screen_kind}-confirm",
            f"ledger-{screen_kind}-cancel",
        )
        assert geometry_band(app, 80) == []
        assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
        owners = tuple(
            widget for widget in screen.query(VerticalScroll) if widget.display and widget.show_vertical_scrollbar
        )
        assert len(owners) <= 1
        assert all(isinstance(owner, VerticalScroll) and owner.id == "ledger-page" for owner in owners)


def test_flow_modules_cannot_read_files_detect_providers_or_import_mutators() -> None:
    package = Path(__file__).parents[1]
    trees = {
        path.name: ast.parse(path.read_text(encoding="utf-8"))
        for path in (package / "classification.py", package / "import_flow.py")
    }
    imports = {
        node.module or "" for tree in trees.values() for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for tree in trees.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not any("actions_import" in name or "adapters" in name or "entrypoints.cli" in name for name in imports)
    assert not {"Path", "open", "read", "read_text", "import_ledger_source"} & calls


@pytest.mark.asyncio
async def test_selecting_an_entry_makes_the_classification_area_reachable() -> None:
    """A destination the session can never open should not be offered at all.

    Classification is entered WITH a chosen row, and the target used to be
    fixed when the workspace was composed -- before the operator had chosen
    anything. Every other test here binds `classification_target` up front,
    which is precisely the workaround that hid this: in a real session nothing
    set it, so the area was permanently refused while the navigation table went
    on listing it, and the selection made on the entries screen went nowhere.

    The doors ARE bound here, so the selection is the only variable. The
    refusal is asserted before and its absence after, because either half alone
    proves nothing: a screen that always admits classification passes the
    second, and one that never does passes the first.
    """
    projection = _projection()
    controller = LedgerWorkspaceController(
        _context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=_review_action(),
            classify_action=_classify_action(),
            classification_submitter=_ClassificationDoor(),
        ),
    )
    screen = LedgerEntriesScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert controller.refusal_for(LedgerWorkspaceArea.CLASSIFICATION) is not None, (
            "classification was already reachable, so this cannot show a selection changed anything"
        )

        chosen = projection.entries[0].transaction_id
        screen.post_message(LedgerEntrySelected(chosen))
        await pilot.pause()

        assert controller.classification_target == chosen
        assert controller.refusal_for(LedgerWorkspaceArea.CLASSIFICATION) is None, (
            "the operator chose an entry and classification is still refused, so the selection carried nowhere"
        )
        app.exit(None)


def test_a_classification_target_outside_the_visible_projection_is_refused() -> None:
    """A target the snapshot does not contain would open on an invisible row."""
    controller = LedgerWorkspaceController(
        _context(), _projection(), LedgerWorkspaceInjection(review_action=_review_action())
    )
    with pytest.raises(ValueError, match="absent from the visible Ledger projection"):
        controller.select_classification_target("f" * 64)

@pytest.mark.asyncio
async def test_preparing_an_import_from_a_path_makes_the_import_area_reachable(tmp_path: Path) -> None:
    """The import area is entered WITH a prepared command, and nothing made one.

    `LedgerPreparedImportV1` was constructed only in tests, so in a live
    session the area was permanently refused while the navigation table listed
    it as a destination. The entry lives on the OVERVIEW screen because the
    import screen itself refuses without a prepared import -- an entry inside
    it could never be reached.

    The refusal is asserted before and its absence after: a screen that always
    admits import passes the second, one that never does passes the first.
    """
    source = tmp_path / "statement.csv"
    source.write_text("date,amount\n2026-01-01,10.00\n", encoding="utf-8")

    async def submitter(command: object) -> object:
        del command
        raise AssertionError("this test prepares an import; it does not submit one")

    controller = LedgerWorkspaceController(
        _context(),
        _projection(),
        LedgerWorkspaceInjection(review_action=_review_action(), import_submitter=submitter),
    )
    screen = LedgerOverviewScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert controller.refusal_for(LedgerWorkspaceArea.IMPORT) is not None, (
            "import was already reachable, so this cannot show a preparation changed anything"
        )

        entry = screen.query_one("#ledger-import-path", Input)
        entry.value = str(source)
        await entry.action_submit()
        await pilot.pause()

        assert controller.refusal_for(LedgerWorkspaceArea.IMPORT) is None, (
            "the operator prepared an import and the area is still refused"
        )
        status = str(screen.query_one("#ledger-import-status", Static).render())
        assert status == ledger_copy("tui.ledger.overview.import_prepared")
        app.exit(None)


@pytest.mark.asyncio
async def test_an_unusable_import_path_is_refused_without_naming_it(tmp_path: Path) -> None:
    """A refusal must not print the path the operator typed.

    The whole point of sealing the command is that a filesystem path never
    reaches a rendered frame; a status line that echoes it back would undo
    that at the first mistake, which is exactly when an operator is most
    likely to be sharing their screen or a screenshot.
    """
    controller = LedgerWorkspaceController(
        _context(), _projection(), LedgerWorkspaceInjection(review_action=_review_action())
    )
    screen = LedgerOverviewScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        missing = tmp_path / "absent.csv"
        entry = screen.query_one("#ledger-import-path", Input)
        entry.value = str(missing)
        await entry.action_submit()
        await pilot.pause()

        status = str(screen.query_one("#ledger-import-status", Static).render())
        assert status == ledger_copy("tui.ledger.overview.import_refused")
        assert str(missing) not in status
        assert str(tmp_path) not in status
        assert controller.refusal_for(LedgerWorkspaceArea.IMPORT) is not None
        app.exit(None)
