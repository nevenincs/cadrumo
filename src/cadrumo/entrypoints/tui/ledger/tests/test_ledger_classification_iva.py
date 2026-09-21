"""Focused IVA facts tests for the command-backed classification screen."""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Static

from .....application.ledger import models as ledger_models
from .....application.ledger.models import ManualLedgerTransactionResult
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....core.iva_deduction_fact import IvaDeductionFactKind
from .....domain.iva.schema import IvaCategory
from .....domain.transactions.enums import BusinessClassification
from .....domain.transactions.models import BucketTransactionRef
from ....tui.components.host import ScreenHostApp
from .. import classification as classification_ui
from ..classification import LedgerClassificationScreen
from ..controller import LedgerWorkspaceController
from ..models import LedgerClassificationSubmissionV1, LedgerFlowState
from ..workspace_injection import LedgerWorkspaceInjection
from .workspace_fixtures import ledger_focused_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _ClassificationDoor:
    def __init__(self) -> None:
        self.calls: list[LedgerClassificationSubmissionV1] = []

    async def __call__(self, submission: LedgerClassificationSubmissionV1) -> ManualLedgerTransactionResult:
        self.calls.append(submission)
        return ManualLedgerTransactionResult.model_construct(
            ref=BucketTransactionRef.model_construct(transaction_id=submission.transaction_id),
        )


def _action_controller(door: _ClassificationDoor) -> LedgerWorkspaceController:
    projection = ledger_projection()
    return LedgerWorkspaceController(
        ledger_focused_context(projection.entries[0].transaction_id),
        projection,
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            classify_action=ActionReference(action_id=lookup_action("operator.ledger.classify").action_id),
            classification_submitter=door,
        ),
    )


def _set_input(screen: LedgerClassificationScreen, field_name: str, value: str) -> None:
    screen.query_one(f"#ledger-classification-{field_name.replace('_', '-')}", Input).value = value


async def _choose_and_confirm(
    pilot: Pilot[None],
    screen: LedgerClassificationScreen,
    *,
    row: int,
) -> None:
    table = screen.query_one("#ledger-classifications", DataTable)
    table.move_cursor(row=row)
    table.focus()
    await pilot.press("enter")
    assert screen.flow_state is LedgerFlowState.CONFIRMING
    screen.query_one("#ledger-classification-confirm", Button).press()
    await screen.app.workers.wait_for_complete()
    await pilot.pause()


@pytest.mark.asyncio
async def test_iva_and_allocation_fields_reach_the_shared_submitter_as_typed_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ledger_models,
        "require_iva_deduction_fact_kind",
        lambda value: IvaDeductionFactKind.from_registry(str(value)),
    )
    door = _ClassificationDoor()
    screen = LedgerClassificationScreen(_action_controller(door))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 60)) as pilot:
        await pilot.pause()
        _set_input(screen, "taxable_base", "100.00")
        _set_input(screen, "iva_rate", "0.21")
        _set_input(screen, "iva_amount", "0")
        _set_input(screen, "iva_category", "domestic_general")
        _set_input(screen, "deduction_fact_kind", "domestic_current")
        _set_input(screen, "business_pct", "0.60")
        _set_input(screen, "usage_ratio_id", "ratio-office")
        _set_input(screen, "prorrata_reference", "prorrata-2026")
        await _choose_and_confirm(pilot, screen, row=2)  # MIXED

    assert screen.flow_state is LedgerFlowState.SUCCEEDED
    assert len(door.calls) == 1
    patch = door.calls[0].patch
    assert patch.model_fields_set == {
        "business_classification",
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "iva_category",
        "deduction_fact_kind",
        "business_pct",
        "usage_ratio_id",
        "prorrata_reference",
    }
    assert patch.business_classification is BusinessClassification.MIXED
    assert patch.taxable_base == 100
    assert patch.iva_rate == Decimal("0.21")
    assert patch.iva_amount == 0
    assert patch.iva_category == IvaCategory("domestic_general")
    assert patch.deduction_fact_kind == IvaDeductionFactKind.from_registry("domestic_current")
    assert patch.business_pct == Decimal("0.60")
    assert patch.usage_ratio_id == "ratio-office"
    assert patch.prorrata_reference == "prorrata-2026"


@pytest.mark.asyncio
async def test_blank_iva_and_prorrata_inputs_remain_unset() -> None:
    door = _ClassificationDoor()
    screen = LedgerClassificationScreen(_action_controller(door))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 60)) as pilot:
        await pilot.pause()
        await _choose_and_confirm(pilot, screen, row=0)  # BUSINESS

    assert screen.flow_state is LedgerFlowState.SUCCEEDED
    patch = door.calls[0].patch
    assert patch.model_fields_set == {"business_classification"}
    assert patch.taxable_base is None
    assert patch.iva_rate is None
    assert patch.iva_amount is None
    assert patch.iva_category is None
    assert patch.deduction_fact_kind is None
    assert patch.business_pct is None
    assert patch.usage_ratio_id is None
    assert patch.prorrata_reference is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field_name", "value", "row", "message"),
    (
        ("iva_rate", "21", 0, "decimal fraction"),
        ("business_pct", "1.01", 2, "business_pct must be within"),
    ),
)
async def test_invalid_rate_or_percentage_refuses_before_submit(
    field_name: str,
    value: str,
    row: int,
    message: str,
) -> None:
    door = _ClassificationDoor()
    screen = LedgerClassificationScreen(_action_controller(door))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 60)) as pilot:
        await pilot.pause()
        _set_input(screen, field_name, value)
        await pilot.press("enter") if row == 0 else await _choose_and_confirm(pilot, screen, row=row)
        if row == 0:
            screen.query_one("#ledger-classification-confirm", Button).press()
            await pilot.pause()
        assert screen.flow_state is LedgerFlowState.CONFIRMING
        assert not door.calls
        assert message in str(screen.query_one("#ledger-refusal", Static).render())


@pytest.mark.asyncio
async def test_invalid_deduction_kind_refuses_before_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse_deduction_kind(value: object) -> IvaDeductionFactKind:
        raise ValueError(f"deduction kind {value!r} is not declared by the facts registry")

    monkeypatch.setattr(ledger_models, "require_iva_deduction_fact_kind", refuse_deduction_kind)
    door = _ClassificationDoor()
    screen = LedgerClassificationScreen(_action_controller(door))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 60)) as pilot:
        await pilot.pause()
        _set_input(screen, "deduction_fact_kind", "not-a-deduction-kind")
        await _choose_and_confirm(pilot, screen, row=0)
        assert screen.flow_state is LedgerFlowState.CONFIRMING
        assert not door.calls
        assert "not declared" in str(screen.query_one("#ledger-refusal", Static).render())


def test_classification_has_no_cli_or_alternate_writer_dependency() -> None:
    source_path = classification_ui.__file__
    assert source_path is not None
    source = Path(source_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}
    assert not any(name.startswith("entrypoints.cli") for name in imported)
    assert "update_manual_transaction_fields" not in source
    assert "LedgerClassificationSubmissionV1" not in source
