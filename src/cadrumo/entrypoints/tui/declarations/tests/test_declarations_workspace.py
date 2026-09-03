"""Contract, interaction, locale, geometry, and security tests."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path
from typing import cast, override

import pytest
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Static

from .....application.modelo.declarations_workspace import (
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceCalculationRevisionRefV1,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceFilingRefV1,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceSource,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneStateV1,
)
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....core.external_constants import OutputLanguage
from .....core.identity import CalculationRevisionId, FilingRecordId, WorkUnitId
from .....core.period import Period
from .....domain.modelos.calculation_revision import CalculationRevisionState
from .....domain.modelos.filing_record import ExternalEvidenceKind, ModeloRecordStatus
from .....domain.modelos.work_unit import WorkUnitState
from ...components.host import ScreenHostApp
from ...devtools.frame import geometry_band
from ...navigation import TuiFocusIdentityV1, TuiScreenContextV1
from ..controller import DeclarationsWorkspaceController, declarations_copy
from ..filing_history import DeclarationsFilingHistoryScreen
from ..models import DeclarationHandoffV1, FilingHandoffV1, RevisionHandoffV1
from ..overview import DeclarationsOverviewScreen
from ..revisions import DeclarationsRevisionsScreen
from ..routes import (
    DECLARATIONS_ROUTES,
    DeclarationsUnavailableScreen,
    declarations_screen_factory,
    resolve_declarations_screen,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORK = cast("WorkUnitId", "a" * 64)
_REVISION = cast("CalculationRevisionId", "b" * 64)
_FILING = cast("FilingRecordId", "c" * 64)
_NOW = datetime(2026, 9, 3, 10, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2026, "1T")
_EXPECTED = {
    OutputLanguage.ES: ("Resumen de declaraciones", "Revisiones de cálculo", "Historial de presentaciones"),
    OutputLanguage.EN: ("Declarations overview", "Calculation revisions", "Filing history"),
    OutputLanguage.CA: ("Resum de declaracions", "Revisions de càlcul", "Historial de presentacions"),
    OutputLanguage.HU: ("Bevallások áttekintése", "Számítási változatok", "Benyújtási előzmények"),
}


def _projection(
    *, unavailable: DeclarationsWorkspaceZone | None = None, empty: bool = False
) -> DeclarationsWorkspaceProjectionV1:
    zones = tuple(
        DeclarationsWorkspaceZoneStateV1(
            zone=zone,
            sources=(DeclarationsWorkspaceSource.LOCAL_DECLARATIONS,),
            availability=(
                DeclarationsWorkspaceAvailability.NEVER_CAPTURED
                if zone is unavailable
                else DeclarationsWorkspaceAvailability.AVAILABLE
            ),
            observed_at=None if zone is unavailable else _NOW,
            reason_code="declarations.source.missing" if zone is unavailable else None,
            item_count=None if zone is unavailable else (0 if empty else 1),
        )
        for zone in DeclarationsWorkspaceZone
    )
    declaration = DeclarationsWorkspaceDeclarationRefV1(
        work_unit_id=_WORK,
        modelo="130",
        filing_year=2026,
        period=_PERIOD,
        state=WorkUnitState.BORRADOR,
        has_current_calculation=True,
        has_current_filing=False,
    )
    revision = DeclarationsWorkspaceCalculationRevisionRefV1(
        calculation_revision_id=_REVISION,
        work_unit_id=_WORK,
        modelo="130",
        filing_year=2026,
        period=_PERIOD,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=_NOW,
        updated_at=_NOW,
        is_current=True,
        is_filed=False,
    )
    filing = DeclarationsWorkspaceFilingRefV1(
        filing_record_id=_FILING,
        work_unit_id=_WORK,
        calculation_revision_id=_REVISION,
        modelo="130",
        filing_year=2026,
        period=_PERIOD,
        filed_at=_NOW,
        local_status=ModeloRecordStatus.VIGENTE,
        aeat_accepted=True,
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
    )
    return DeclarationsWorkspaceProjectionV1(
        bucket_id="11111111-1111-4111-8111-111111111111",
        zones=zones,
        declarations=() if empty else (declaration,),
        calculation_revisions=() if empty else (revision,),
        filings=() if empty else (filing,),
        lifecycle=(),
    )


def _action(action_id: str) -> ActionReference:
    return ActionReference(action_id=lookup_action(action_id).action_id)


def _controller(
    projection: DeclarationsWorkspaceProjectionV1,
    context: TuiScreenContextV1 | None = None,
    *,
    declaration_handoff: DeclarationHandoffV1 | None = None,
    revision_handoff: RevisionHandoffV1 | None = None,
    filing_handoff: FilingHandoffV1 | None = None,
) -> DeclarationsWorkspaceController:
    return DeclarationsWorkspaceController(
        context or TuiScreenContextV1(destination="workbench.declarations"),
        projection,
        work_action=_action("operator.modelo.work.list"),
        revisions_action=_action("operator.modelo.work.revisions"),
        filing_action=_action("operator.modelo.filing_record.list"),
        declaration_handoff=declaration_handoff,
        revision_handoff=revision_handoff,
        filing_handoff=filing_handoff,
    )


def _copy(screen: Screen[None]) -> str:
    values = [str(widget.render()) for widget in screen.query(Static)]
    values.extend(
        str(cell)
        for table in screen.query(DataTable)
        for row in range(table.row_count)
        for cell in table.get_row_at(row)
    )
    return "\n".join(values)


def test_closed_routes_and_factory_require_exact_catalogue_actions() -> None:
    assert tuple(route.destination for route in DECLARATIONS_ROUTES) == (
        "declarations.overview",
        "declarations.revisions",
        "declarations.filing_history",
        "declarations.modelo_workspace",
    )
    factory = declarations_screen_factory(
        _projection(),
        work_action=_action("operator.modelo.work.list"),
        revisions_action=_action("operator.modelo.work.revisions"),
        filing_action=_action("operator.modelo.filing_record.list"),
    )
    assert isinstance(factory(TuiScreenContextV1(destination="workbench.declarations")), DeclarationsOverviewScreen)
    with pytest.raises(ValueError, match="another application door"):
        declarations_screen_factory(
            _projection(),
            work_action=_action("operator.modelo.work.revisions"),
            revisions_action=_action("operator.modelo.work.revisions"),
            filing_action=_action("operator.modelo.filing_record.list"),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "screen_type",
    (DeclarationsOverviewScreen, DeclarationsRevisionsScreen, DeclarationsFilingHistoryScreen),
)
async def test_each_screen_has_four_targets_one_outer_scroll_and_no_overflow(screen_type: type) -> None:
    screen = screen_type(_controller(_projection()))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert screen.query_one("#declarations-navigation", DataTable).row_count == 4
        assert geometry_band(app, 80) == []
        assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
        owners = tuple(widget for widget in screen.walk_children() if widget.display and widget.show_vertical_scrollbar)
        assert len(owners) <= 1
        assert all(isinstance(owner, VerticalScroll) and owner.id == "declarations-page" for owner in owners)


@pytest.mark.asyncio
async def test_semantic_selection_uses_exact_projected_identity_and_typed_callbacks() -> None:
    selected: list[object] = []
    screen = DeclarationsRevisionsScreen(
        _controller(_projection(), revision_handoff=selected.append)
    )
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#declarations-revisions", DataTable)
        table.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert len(selected) == 1
        assert selected[0] is screen.controller.projection.calculation_revisions[0]
        assert screen.selected_calculation_revision_id == _REVISION
        rendered = _copy(screen)
        assert _WORK not in rendered and _REVISION not in rendered and _FILING not in rendered
        assert "Modelo 130" in rendered


@pytest.mark.asyncio
async def test_focus_restores_by_calculation_revision_identity_not_registry_revision_or_position() -> None:
    context = TuiScreenContextV1(
        destination="workbench.declarations",
        focus=TuiFocusIdentityV1(
            destination="workbench.declarations",
            semantic_key="declarations.calculation_revision",
            restore_token=_REVISION,
        ),
    )
    screen = DeclarationsRevisionsScreen(_controller(_projection(), context))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#declarations-revisions", DataTable)
        assert app.focused is table
        assert table.ordered_rows[table.cursor_row].key.value == _REVISION


@pytest.mark.asyncio
async def test_unavailable_is_refusal_empty_is_measured_and_missing_handoff_refuses() -> None:
    controller = _controller(_projection(unavailable=DeclarationsWorkspaceZone.CALCULATION_REVISIONS))
    unavailable = resolve_declarations_screen(controller, controller.target("declarations.revisions"))
    assert isinstance(unavailable, DeclarationsUnavailableScreen)
    empty = DeclarationsOverviewScreen(_controller(_projection(empty=True)))
    app = ScreenHostApp[None](empty)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert declarations_copy("tui.declarations.empty") in _copy(empty)
    screen = DeclarationsOverviewScreen(_controller(_projection()))
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = screen.query_one("#declarations-list", DataTable)
        table.focus()
        await pilot.press("enter")
        assert declarations_copy("tui.declarations.refusal.handoff") in _copy(screen)


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", tuple(OutputLanguage))
async def test_real_locales_change_copy_without_changing_semantic_rows(locale: OutputLanguage) -> None:
    from .....core.config import override_settings

    with override_settings(cadrumo_output_language=locale.value):
        screens = (
            DeclarationsOverviewScreen(_controller(_projection())),
            DeclarationsRevisionsScreen(_controller(_projection())),
            DeclarationsFilingHistoryScreen(_controller(_projection())),
        )
        for screen, expected in zip(screens, _EXPECTED[locale], strict=True):
            app = ScreenHostApp[None](screen)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                rendered = _copy(screen)
                assert expected in rendered
                assert "tui.declarations." not in rendered
                assert "work_unit" not in rendered.lower()
                assert tuple(row.key.value for row in screen.query_one("#declarations-navigation", DataTable).ordered_rows) == tuple(
                    route.destination for route in DECLARATIONS_ROUTES
                )


class _Root(App[None]):
    @override
    def compose(self) -> ComposeResult:
        yield Static("root", id="root")


@pytest.mark.asyncio
async def test_escape_dismisses_only_child_and_returns_to_generic_root() -> None:
    root = _Root()
    screen = DeclarationsOverviewScreen(_controller(_projection()))
    async with root.run_test(size=(80, 24)) as pilot:
        await root.push_screen(screen)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert root.is_running
        assert root.query_one("#root", Static).display


def test_declarations_tui_has_no_io_adapter_cli_reader_or_raw_payload_surface() -> None:
    package = Path(__file__).parents[1]
    production = tuple(path for path in package.glob("*.py") if path.name != "__init__.py")
    trees = tuple(ast.parse(path.read_text(encoding="utf-8")) for path in production)
    imports = {
        node.module or ""
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not any("entrypoints.cli" in name or "adapters" in name or "repositories" in name for name in imports)
    assert not {"open", "read", "write", "read_text", "write_text", "print"} & calls
    for path in production:
        text = path.read_text(encoding="utf-8")
        assert "member_nif" not in text
        assert "source_transaction_ids" not in text
        assert "input_values_by_casilla_id" not in text
