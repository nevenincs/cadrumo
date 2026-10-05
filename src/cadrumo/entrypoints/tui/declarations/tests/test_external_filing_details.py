"""External completion, local drafts and explicit technical disclosure stay separate."""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.widgets import Button, DataTable, Static

from .....application.modelo.declaration_summary import DeclarationSummary, DeclarationSummaryState
from .....application.modelo.declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from .....application.modelo.work_form_models import ModeloFormResult, ModeloFormResultDirection
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....core.casilla_id import validated_casilla_id
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from ...components.host import ScreenHostApp
from ...navigation import TuiScreenContextV1
from ...tests.frame import geometry_band
from ..controller import DeclarationsWorkspaceController
from ..external_details import ExternalFilingDetailsScreen
from ..models import DeclarationsWorkspaceWiringV1
from ..overview import DeclarationsOverviewScreen
from .portfolio_fixtures import portfolio_projection

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", tuple(OutputLanguage))
@pytest.mark.parametrize("theme", ("cadrumo-dark", "cadrumo-light"))
@pytest.mark.parametrize("size", ((80, 24), (120, 40)))
async def test_external_details_never_borrows_the_local_amount_and_returns_to_the_same_row(
    locale: OutputLanguage, theme: str, size: tuple[int, int]
) -> None:
    workspace, calendar = portfolio_projection()
    private_amount = ModeloFormResult(
        casilla_id=validated_casilla_id("71"),
        box="71",
        value=Decimal("7900"),
        direction=ModeloFormResultDirection.TO_PAY,
    )
    declarations = tuple(
        declaration.model_copy(
            update={
                "summary": DeclarationSummary(
                    state=DeclarationSummaryState.CALCULATED,
                    result=private_amount,
                )
            }
        )
        if declaration.modelo == "303"
        else declaration
        for declaration in workspace.declarations
    )
    workspace = workspace.model_copy(update={"declarations": declarations})
    calls: list[DeclarationsWorkspaceDeclarationRefV1] = []
    with override_settings(cadrumo_output_language=locale.value):
        controller = DeclarationsWorkspaceController(
            TuiScreenContextV1(destination="workbench.declarations"),
            workspace,
            DeclarationsWorkspaceWiringV1(
                work_action=ActionReference(action_id=lookup_action("operator.modelo.work.list").action_id),
                revisions_action=ActionReference(action_id=lookup_action("operator.modelo.work.revisions").action_id),
                filing_action=ActionReference(action_id=lookup_action("operator.modelo.filing_record.list").action_id),
                calendar_projection=calendar,
            ),
        )
        screen = DeclarationsOverviewScreen(controller)
        app = ScreenHostApp(screen)
        async with app.run_test(size=size) as pilot:
            app.theme = theme
            await pilot.pause()
            table = screen.query_one("#declarations-list", DataTable)
            external = next(row for row in screen.rows if row.state == "aeat_unlinked")
            local = next(row for row in screen.rows if row.declaration is not None and row.modelo == "303")
            assert local.key != external.key
            assert local.declaration is not None and local.declaration.summary is not None
            assert local.declaration.summary.result == private_amount
            local_text = "\n".join(str(cell) for cell in table.get_row(local.key))
            assert tr("tui.declarations.list.state.local_draft") in local_text
            table.move_cursor(row=next(i for i, row in enumerate(table.ordered_rows) if row.key.value == external.key))
            table.focus()
            await pilot.press("enter")
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, ExternalFilingDetailsScreen)
            assert app.focused is modal.query_one("#external-filing-close", Button)
            text = "\n".join(str(widget.render()) for widget in modal.query(Static))
            for key in ("confirmed", "no_refile", "unavailable"):
                assert tr("tui.declarations.list.aeat_unlinked.help." + key) in text
            assert "7900" not in text and "7,900" not in text and "7.900" not in text and "7 900" not in text
            assert "2025" in text and "15" in text
            assert external.calendar is not None and external.calendar.aeat_reference_id is not None
            assert external.calendar.aeat_reference_id not in text
            detail = modal.query_one("#external-filing-technical", Static)
            assert not detail.display
            assert "tui." not in text
            assert geometry_band(app, size[0]) == []
            await pilot.press("t")
            assert detail.display
            assert str(detail.render()) == external.calendar.aeat_reference_id
            await pilot.press("t")
            assert not detail.display
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is screen and app.focused is table
            assert table.ordered_rows[table.cursor_row].key.value == external.key
            assert calls == []
