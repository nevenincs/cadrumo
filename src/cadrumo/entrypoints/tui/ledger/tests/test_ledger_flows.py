"""Command-bound classification and prepared-import interaction tests."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from textual.widgets import DataTable, Static

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
from .....domain.transactions.enums import BusinessClassification
from ....tui.components.host import ScreenHostApp
from ..classification import LedgerClassificationScreen
from ..import_flow import LedgerImportScreen
from ..models import LedgerClassificationSubmissionV1, LedgerFlowState, LedgerPreparedImportV1
from ..routes import ledger_screen_factory, resolve_ledger_screen
from .test_ledger_workspace import _controller, _projection

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


def _classify_action() -> ActionReference:
    return ActionReference(action_id=lookup_action("operator.ledger.classify").action_id)


@pytest.mark.asyncio
async def test_classification_is_explicit_confirmable_cancelable_and_catalogue_authorized() -> None:
    projection = _projection()
    door = _ClassificationDoor()
    controller = _controller(projection)
    controller.classify_action = _classify_action()
    controller.classification_target = projection.entries[0].transaction_id
    controller.classification_submitter = door
    screen = cast(
        "LedgerClassificationScreen",
        resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.CLASSIFICATION)),
    )
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#ledger-classifications", DataTable)
        assert tuple(row.key.value for row in table.ordered_rows) == ("BUSINESS", "PERSONAL", "REVIEWED_EXCLUDED")
        await pilot.press("enter")
        assert screen.flow_state is LedgerFlowState.CONFIRMING
        await pilot.press("escape")
        assert screen.flow_state is LedgerFlowState.CANCELLED
        assert not door.calls
        await pilot.press("enter", "enter")
        await pilot.pause()
        assert screen.flow_state is LedgerFlowState.SUCCEEDED
    assert door.calls[0].action == _classify_action()
    assert door.calls[0].transaction_id == projection.entries[0].transaction_id
    assert door.calls[0].patch.business_classification is BusinessClassification.BUSINESS


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
    door = _ImportDoor()
    controller = _controller(_projection())
    controller.prepared_imports = (prepared,)
    controller.import_submitter = door
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


def test_factory_refuses_undeclared_or_drifted_classification_action() -> None:
    with pytest.raises(KeyError, match="unknown operator action ID"):
        ledger_screen_factory(
            _projection(),
            review_action=ActionReference(action_id="operator.ledger.review"),
            classify_action=ActionReference(action_id="operator.ledger.absent"),
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
    controller = _controller(_projection())
    controller.classify_action = _classify_action()
    controller.classification_target = controller.projection.entries[0].transaction_id
    controller.classification_submitter = _ClassificationDoor()
    command = LedgerSourceImportCommand(path=Path("C:/synthetic/input.csv"), provider="bank")
    controller.prepared_imports = (
        LedgerPreparedImportV1(
            choice_id="prepared-bank",
            provider_label_key="tui.ledger.import.provider.bank",
            source_label_key="tui.ledger.import.source.prepared",
            command=command,
        ),
    )
    controller.import_submitter = _ImportDoor()
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
            assert tuple(row.key.value for row in import_screen.query_one("#ledger-import-choices", DataTable).ordered_rows) == (
                "prepared-bank",
            )
def test_flow_modules_cannot_read_files_detect_providers_or_import_mutators() -> None:
    package = Path(__file__).parents[1]
    trees = {
        path.name: ast.parse(path.read_text(encoding="utf-8"))
        for path in (package / "classification.py", package / "import_flow.py")
    }
    imports = {
        node.module or ""
        for tree in trees.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for tree in trees.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not any("actions_import" in name or "adapters" in name or "entrypoints.cli" in name for name in imports)
    assert not {"Path", "open", "read", "read_text", "import_ledger_source"} & calls
