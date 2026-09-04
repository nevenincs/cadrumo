"""Evidence and local-reconciliation contract and interaction tests."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from typing import override

import pytest
from textual.containers import VerticalScroll
from textual.widgets import Button, DataTable, Static

from .....application.ledger.attachment_review import AttachmentReviewItem
from .....application.ledger.models import LedgerSourceImportCommand
from .....application.ledger.workspace import (
    LedgerAffectedDeclarationRefV1,
    LedgerInvoiceReconciliationRefV1,
    LedgerLinkInconsistencyRefV1,
    LedgerWorkspaceArea,
)
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....core.config import override_settings
from .....core.period import Period
from .....domain.attachments.enums import AttachmentSource
from ....tui.components.host import ScreenHostApp
from ....tui.devtools.frame import geometry_band
from ....tui.navigation import TuiFocusIdentityV1, TuiScreenContextV1
from ..controller import LedgerWorkspaceController
from ..evidence import LedgerEvidenceScreen
from ..models import LedgerFlowState, LedgerLinkResultV1, LedgerLinkSubmissionV1, LedgerPreparedImportV1
from ..reconciliation import LedgerReconciliationScreen
from ..routes import LedgerUnavailableScreen, resolve_ledger_screen
from ..workspace_injection import LedgerWorkspaceInjection
from .test_ledger_flows import _ClassificationDoor, _classify_action, _ImportDoor
from .test_ledger_workspace import _projection, _review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TX = "a" * 64
_TX_B = "b" * 64
_INVOICE = "c" * 64
_INVOICE_D = "d" * 64
_EVIDENCE = "e" * 64


def _evidence_action() -> ActionReference:
    return ActionReference(action_id=lookup_action("operator.ledger.evidence.review.list").action_id)


def _link_action() -> ActionReference:
    return ActionReference(action_id=lookup_action("operator.ledger.link").action_id)


def _evidence_item() -> AttachmentReviewItem:
    return AttachmentReviewItem(
        attachment_id=_EVIDENCE,
        sha256="d" * 64,
        mime_type="application/pdf",
        bytes_size=512,
        source=AttachmentSource.GOOGLE_DRIVE,
        provider_locator="protected-provider-locator",
        captured_at="2026-09-03T09:00:00+00:00",
        linked_invoice_ids=(),
        pending_review=True,
    )


def _reconciled_projection():
    projection = _projection()
    return projection.model_copy(
        update={
            "invoice_reconciliations": (
                LedgerInvoiceReconciliationRefV1(
                    invoice_id=_INVOICE,
                    transaction_id=_TX,
                    amount_match=True,
                    counterparty_match=True,
                    score="1.0",
                    invoice_total="1250.00",
                    transaction_amount="1250.00",
                    invoice_counterparty="Suministros Delta SL",
                    transaction_counterparty="Suministros Delta SL",
                ),
            ),
            "link_inconsistencies": (
                LedgerLinkInconsistencyRefV1(invoice_id="f" * 64, transaction_id=_TX, direction="invoice-only"),
            ),
            "affected_declarations": (
                LedgerAffectedDeclarationRefV1(
                    modelo="303",
                    filing_year=2026,
                    period=Period.from_year_and_code(2026, "2T"),
                    calculation_revision_id="b" * 64,
                    changed_count=2,
                    removed_count=1,
                ),
            ),
        }
    )


def _two_suggestion_projection():
    projection = _reconciled_projection()
    second = LedgerInvoiceReconciliationRefV1(
        invoice_id=_INVOICE_D,
        transaction_id=_TX_B,
        amount_match=True,
        counterparty_match=False,
        score="0.5",
        invoice_total="480.50",
        transaction_amount="480.50",
        invoice_counterparty="Cliente Omega SA",
        transaction_counterparty="Omega SA",
    )
    return projection.model_copy(update={"invoice_reconciliations": (*projection.invoice_reconciliations, second)})


def _render_all(screen: LedgerReconciliationScreen) -> str:
    values = [str(widget.render()) for widget in screen.query(Static)]
    values.extend(
        str(cell)
        for table in screen.query(DataTable)
        for row_index in range(table.row_count)
        for cell in table.get_row_at(row_index)
    )
    return "\n".join(values)


class _LinkDoor:
    def __init__(self) -> None:
        self.calls: list[LedgerLinkSubmissionV1] = []

    async def __call__(self, submission: LedgerLinkSubmissionV1) -> LedgerLinkResultV1:
        self.calls.append(submission)
        return LedgerLinkResultV1(transaction_id=submission.transaction_id, invoice_id=submission.invoice_id)


class _SlowLinkDoor(_LinkDoor):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    @override
    async def __call__(self, submission: LedgerLinkSubmissionV1) -> LedgerLinkResultV1:
        self.calls.append(submission)
        self.started.set()
        await self.release.wait()
        return LedgerLinkResultV1(transaction_id=submission.transaction_id, invoice_id=submission.invoice_id)


class _FailingLinkDoor:
    async def __call__(self, submission: LedgerLinkSubmissionV1) -> LedgerLinkResultV1:
        del submission
        raise RuntimeError("taxpayer-name invoice-private-path.pdf")


@pytest.mark.asyncio
async def test_evidence_renders_only_safe_metadata_and_restores_semantic_focus() -> None:
    context = TuiScreenContextV1(
        destination="workbench.ledger",
        focus=TuiFocusIdentityV1(
            destination="workbench.ledger", semantic_key="ledger.evidence", restore_token=_EVIDENCE
        ),
    )
    controller = LedgerWorkspaceController(
        context,
        _projection(),
        LedgerWorkspaceInjection(
            review_action=_review_action(), evidence_action=_evidence_action(), evidence_items=(_evidence_item(),)
        ),
    )
    screen = LedgerEvidenceScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#ledger-evidence", DataTable)
        assert app.focused is table
        assert table.ordered_rows[table.cursor_row].key.value == _EVIDENCE
        await pilot.press("enter")
        assert screen.requested_review is not None
        assert screen.requested_review.attachment_id == _EVIDENCE
        assert screen.requested_review.action == _evidence_action()
        rendered = "\n".join(str(widget.render()) for widget in screen.query(Static))
        assert "512" in rendered
        assert "protected-provider-locator" not in rendered
        assert "d" * 64 not in rendered
        assert _EVIDENCE not in rendered


@pytest.mark.asyncio
async def test_local_reconciliation_renders_distinct_source_and_submits_exact_visible_pair_once() -> None:
    door = _LinkDoor()
    controller = LedgerWorkspaceController(
        TuiScreenContextV1(destination="workbench.ledger"),
        _reconciled_projection(),
        LedgerWorkspaceInjection(review_action=_review_action(), link_action=_link_action(), link_submitter=door),
    )
    screen = LedgerReconciliationScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        rendered = "\n".join(str(widget.render()) for widget in screen.query(Static))
        assert "AEAT" in rendered
        await pilot.press("enter", "enter")
        await app.workers.wait_for_complete()
        assert screen.flow_state is LedgerFlowState.SUCCEEDED
        assert len(door.calls) == 1
        assert door.calls[0].transaction_id == _TX
        assert door.calls[0].invoice_id == _INVOICE
        assert door.calls[0].action == _link_action()
        await pilot.press("enter")
        assert len(door.calls) == 1
        affected = screen.query_one("#ledger-affected", DataTable)
        assert tuple(str(value) for value in affected.get_row_at(0)) == ("303", "2026 2T", "2/1")


@pytest.mark.asyncio
async def test_reordered_table_selection_resolves_exact_semantic_pair_not_cursor_position() -> None:
    door = _LinkDoor()
    controller = LedgerWorkspaceController(
        TuiScreenContextV1(destination="workbench.ledger"),
        _two_suggestion_projection(),
        LedgerWorkspaceInjection(review_action=_review_action(), link_action=_link_action(), link_submitter=door),
    )
    screen = LedgerReconciliationScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#ledger-suggestions", DataTable)
        table.sort("invoice", reverse=True)
        await pilot.pause()
        assert table.ordered_rows[0].key.value == f"{_TX_B}:{_INVOICE_D}"
        table.move_cursor(row=0)
        await pilot.press("enter", "enter")
        await app.workers.wait_for_complete()
        assert screen.selected_pair == (_TX_B, _INVOICE_D)
        assert len(door.calls) == 1
        assert door.calls[0].transaction_id == _TX_B
        assert door.calls[0].invoice_id == _INVOICE_D


@pytest.mark.asyncio
async def test_reconciliation_restores_semantic_transaction_and_refuses_escape_in_flight() -> None:
    door = _SlowLinkDoor()
    context = TuiScreenContextV1(
        destination="workbench.ledger",
        focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.transaction", restore_token=_TX),
    )
    controller = LedgerWorkspaceController(
        context,
        _reconciled_projection(),
        LedgerWorkspaceInjection(review_action=_review_action(), link_action=_link_action(), link_submitter=door),
    )
    screen = LedgerReconciliationScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        suggestions = screen.query_one("#ledger-suggestions", DataTable)
        assert app.focused is suggestions
        assert suggestions.ordered_rows[suggestions.cursor_row].key.value == f"{_TX}:{_INVOICE}"
        await pilot.press("enter", "enter")
        await asyncio.wait_for(door.started.wait(), timeout=1)
        await pilot.press("escape")
        assert screen.flow_state is LedgerFlowState.SUBMITTING
        assert not screen.back_requested
        assert screen.is_mounted
        door.release.set()
        await app.workers.wait_for_complete()
        assert screen.flow_state is LedgerFlowState.SUCCEEDED
        assert len(door.calls) == 1


@pytest.mark.asyncio
async def test_reconciliation_failure_copy_is_generic_and_sensitive_exception_is_not_rendered() -> None:
    controller = LedgerWorkspaceController(
        TuiScreenContextV1(destination="workbench.ledger"),
        _reconciled_projection(),
        LedgerWorkspaceInjection(
            review_action=_review_action(), link_action=_link_action(), link_submitter=_FailingLinkDoor()
        ),
    )
    with override_settings(cadrumo_output_language="en"):
        screen = LedgerReconciliationScreen(controller)
        app = ScreenHostApp[None](screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.press("enter", "enter")
            await app.workers.wait_for_complete()
            rendered = "\n".join(str(widget.render()) for widget in screen.query(Static))
            assert screen.flow_state is LedgerFlowState.FAILED
            assert "The link could not be saved." in rendered
            assert "taxpayer-name" not in rendered
            assert "invoice-private-path.pdf" not in rendered
            assert "RuntimeError" not in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize("screen_kind", ("evidence", "reconciliation"))
async def test_slice3_compositor_has_one_scroll_owner_and_no_80_column_overflow(screen_kind: str) -> None:
    projection = _projection() if screen_kind == "evidence" else _reconciled_projection()
    if screen_kind == "evidence":
        controller = LedgerWorkspaceController(
            TuiScreenContextV1(destination="workbench.ledger"),
            projection,
            LedgerWorkspaceInjection(
                review_action=_review_action(), evidence_action=_evidence_action(), evidence_items=(_evidence_item(),)
            ),
        )
    else:
        controller = LedgerWorkspaceController(
            TuiScreenContextV1(destination="workbench.ledger"),
            projection,
            LedgerWorkspaceInjection(
                review_action=_review_action(), link_action=_link_action(), link_submitter=_LinkDoor()
            ),
        )
    screen = LedgerEvidenceScreen(controller) if screen_kind == "evidence" else LedgerReconciliationScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert geometry_band(app, 80) == []
        assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
        owners = tuple(
            widget for widget in screen.query(VerticalScroll) if widget.display and widget.show_vertical_scrollbar
        )
        assert len(owners) <= 1
        assert all(owner.id == "ledger-page" for owner in owners)


def test_slice3_routes_and_actions_fail_closed_without_declared_dependencies() -> None:
    controller = LedgerWorkspaceController(
        TuiScreenContextV1(destination="workbench.ledger"),
        _projection(),
        LedgerWorkspaceInjection(review_action=_review_action()),
    )
    assert isinstance(
        resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.EVIDENCE)),
        LedgerUnavailableScreen,
    )
    assert isinstance(
        resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.RECONCILIATION)),
        LedgerReconciliationScreen,
    )
    with pytest.raises(ValueError, match="canonical review query"):
        LedgerWorkspaceController(
            TuiScreenContextV1(destination="workbench.ledger"),
            _projection(),
            LedgerWorkspaceInjection(review_action=_review_action(), evidence_action=_link_action(), evidence_items=()),
        )
    with pytest.raises(ValueError, match="canonical command"):
        LedgerWorkspaceController(
            TuiScreenContextV1(destination="workbench.ledger"),
            _projection(),
            LedgerWorkspaceInjection(
                review_action=_review_action(), link_action=_evidence_action(), link_submitter=_LinkDoor()
            ),
        )


@pytest.mark.asyncio
async def test_reconciliation_without_mutation_door_preserves_read_only_drift_and_hides_controls() -> None:
    with override_settings(cadrumo_output_language="en"):
        controller = LedgerWorkspaceController(
            TuiScreenContextV1(destination="workbench.ledger"),
            _reconciled_projection(),
            LedgerWorkspaceInjection(review_action=_review_action()),
        )
        screen = LedgerReconciliationScreen(controller)
        app = ScreenHostApp[None](screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert screen.query_one("#ledger-suggestions", DataTable).row_count == 1
            assert screen.query_one("#ledger-inconsistencies", DataTable).row_count == 1
            assert screen.query_one("#ledger-affected", DataTable).row_count == 1
            assert not screen.query_one("#ledger-reconciliation-confirm", Button).display
            assert not screen.query_one("#ledger-reconciliation-cancel", Button).display
            assert screen.flow_state is LedgerFlowState.EDITING
            await pilot.press("enter")
            assert screen.flow_state is LedgerFlowState.EDITING
            assert screen.selected_pair is None
            assert str(screen.query_one("#ledger-flow-status", Static).render()) == (
                "This task is unavailable until a prepared operation is supplied."
            )


def _all_routes_controller() -> LedgerWorkspaceController:
    command = LedgerSourceImportCommand(path=Path("C:/synthetic/input.csv"), provider="bank")
    prepared = LedgerPreparedImportV1(
        choice_id="synthetic-bank",
        provider_label_key="tui.ledger.import.provider.bank",
        source_label_key="tui.ledger.import.source.prepared",
        command=command,
    )
    projection = _reconciled_projection()
    return LedgerWorkspaceController(
        TuiScreenContextV1(destination="workbench.ledger"),
        projection,
        LedgerWorkspaceInjection(
            review_action=_review_action(),
            classify_action=_classify_action(),
            classification_target=projection.entries[0].transaction_id,
            classification_submitter=_ClassificationDoor(),
            prepared_imports=(prepared,),
            import_submitter=_ImportDoor(),
            evidence_action=_evidence_action(),
            evidence_items=(_evidence_item(),),
            link_action=_link_action(),
            link_submitter=_LinkDoor(),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("size", ((80, 24), (100, 30), (120, 40), (200, 50)))
@pytest.mark.parametrize("area", tuple(LedgerWorkspaceArea))
async def test_all_seven_routes_are_focus_reachable_with_one_scroll_owner_and_no_overflow(
    area: LedgerWorkspaceArea,
    size: tuple[int, int],
) -> None:
    controller = _all_routes_controller()
    screen = resolve_ledger_screen(controller, controller.route_target(area))
    assert not isinstance(screen, LedgerUnavailableScreen)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        assert geometry_band(app, size[0]) == []
        assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
        owners = tuple(
            widget for widget in screen.query(VerticalScroll) if widget.display and widget.show_vertical_scrollbar
        )
        assert len(owners) <= 1
        assert all(owner.id == "ledger-page" for owner in owners)
        focus_chain = tuple(screen.focus_chain)
        assert focus_chain
        reached = {app.focused}
        for _ in range(len(focus_chain) * 2):
            await pilot.press("tab")
            reached.add(app.focused)
        assert set(focus_chain) <= reached


@pytest.mark.asyncio
async def test_link_door_is_not_called_for_a_pair_absent_from_visible_projection() -> None:
    door = _LinkDoor()
    controller = LedgerWorkspaceController(
        TuiScreenContextV1(destination="workbench.ledger"),
        _reconciled_projection(),
        LedgerWorkspaceInjection(review_action=_review_action(), link_action=_link_action(), link_submitter=door),
    )
    with pytest.raises(ValueError, match="absent from the visible reconciliation projection"):
        await controller.submit_link(_TX, "f" * 64)
    assert not door.calls


@pytest.mark.asyncio
async def test_slice3_copy_is_real_across_locales_without_semantic_drift() -> None:
    titles = []
    for locale in ("es", "en", "ca", "hu"):
        with override_settings(cadrumo_output_language=locale):
            controller = LedgerWorkspaceController(
                TuiScreenContextV1(destination="workbench.ledger"),
                _projection(),
                LedgerWorkspaceInjection(
                    review_action=_review_action(),
                    evidence_action=_evidence_action(),
                    evidence_items=(_evidence_item(),),
                ),
            )
            screen = LedgerEvidenceScreen(controller)
            app = ScreenHostApp[None](screen)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                titles.append(str(next(iter(screen.query(".cadrumo-banner"))).render()))
                assert screen.query_one("#ledger-evidence", DataTable).ordered_rows[0].key.value == _EVIDENCE
    assert len(set(titles)) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("locale", "expected"),
    (
        (
            "en",
            (
                "Local Ledger evidence only. AEAT Sync is a separate workspace.",
                "Canonical score: 1.0",
                "Amount matches: Yes",
                "Counterparty matches: Yes",
                "Invoice cites entry only",
            ),
        ),
        (
            "es",
            (
                "Solo datos locales del libro. Sincronización AEAT es un espacio distinto.",
                "Puntuación canónica: 1.0",
                "Coincide el importe: Sí",
                "Coincide la contraparte: Sí",
                "Solo la factura cita el apunte",
            ),
        ),
        (
            "ca",
            (
                "Només dades locals del llibre. Sincronització AEAT és un espai diferent.",
                "Puntuació canònica: 1.0",
                "Coincideix l'import: Sí",
                "Coincideix la contrapart: Sí",
                "Només la factura cita l'assentament",
            ),
        ),
        (
            "hu",
            (
                "Csak helyi főkönyvi adatok. Az AEAT-szinkron külön munkaterület.",
                "Kanonikus pontszám: 1.0",
                "Összeg egyezik: Igen",
                "Partner egyezik: Igen",
                "Csak a számla hivatkozik a tételre",
            ),
        ),
    ),
)
async def test_reconciliation_copy_pins_local_source_and_canonical_semantics(
    locale: str, expected: tuple[str, ...]
) -> None:
    with override_settings(cadrumo_output_language=locale):
        controller = LedgerWorkspaceController(
            TuiScreenContextV1(destination="workbench.ledger"),
            _reconciled_projection(),
            LedgerWorkspaceInjection(
                review_action=_review_action(), link_action=_link_action(), link_submitter=_LinkDoor()
            ),
        )
        screen = LedgerReconciliationScreen(controller)
        app = ScreenHostApp[None](screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            rendered = _render_all(screen)
            assert all(text in rendered for text in expected)
            suggestion = screen.query_one("#ledger-suggestions", DataTable)
            assert suggestion.ordered_rows[0].key.value == f"{_TX}:{_INVOICE}"


def test_slice3_modules_have_no_io_cli_adapter_or_sensitive_content_access() -> None:
    package = Path(__file__).parents[1]
    trees = [ast.parse((package / name).read_text(encoding="utf-8")) for name in ("evidence.py", "reconciliation.py")]
    imports = {node.module or "" for tree in trees for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not any("entrypoints.cli" in item or "adapters" in item for item in imports)
    assert not {"open", "read", "read_text", "Path", "load_manifest", "verify_blob"} & calls


@pytest.mark.asyncio
async def test_a_suggested_link_shows_the_values_it_was_suggested_on() -> None:
    """A match verdict the operator cannot check is not evidence.

    The suggestion table reported `amount_match: yes` and
    `counterparty_match: no` and stopped there. The first asks the operator to
    confirm a link while hiding the two amounts that supposedly agree; the
    second reports a disagreement without saying between what and what. Both
    values are local records this session is already authenticated for, and
    both were in scope where the suggestion is built -- they were discarded,
    not protected.

    The second fixture row is the one that matters: its counterparties differ
    ("Cliente Omega SA" against "Omega SA"), which is precisely the case where
    a bare "no" leaves the operator unable to tell a real mismatch from a
    formatting difference they would accept at a glance.
    """
    controller = LedgerWorkspaceController(
        TuiScreenContextV1(destination="workbench.ledger"),
        _two_suggestion_projection(),
        LedgerWorkspaceInjection(
            review_action=_review_action(), link_action=_link_action(), link_submitter=_LinkDoor()
        ),
    )
    screen = LedgerReconciliationScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        rendered = _render_all(screen)
        app.exit(None)

    for value in ("1250.00", "Suministros Delta SL", "480.50", "Cliente Omega SA", "Omega SA"):
        assert value in rendered, f"the suggestion hides {value!r}, so its verdict cannot be checked"
