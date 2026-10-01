"""Immutable synthetic portfolio states for reviewing the shipped filing UI.

These are visual fixtures, not proof of calculation or installed persistence.
They hand the production screens typed application projections; the installed
creation and AEAT-reader tests own that evidence. No fixture writes tax data.
"""

from __future__ import annotations

from textual.app import App

from cadrumo.application.modelo.declaration_targets import DeclarationTarget, declaration_targets
from cadrumo.application.modelo.declarations_list import declaration_list_rows
from cadrumo.application.operator_actions.catalogue import lookup_action
from cadrumo.application.operator_actions.models import ActionReference
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.declarations.controller import DeclarationsWorkspaceController
from cadrumo.entrypoints.tui.declarations.external_details import ExternalFilingDetailsScreen
from cadrumo.entrypoints.tui.declarations.models import ModeloWorkCreateResultV1
from cadrumo.entrypoints.tui.declarations.overview import DeclarationsOverviewScreen
from cadrumo.entrypoints.tui.declarations.picker import NewDeclarationPicker
from cadrumo.entrypoints.tui.declarations.tests.portfolio_fixtures import portfolio_projection
from cadrumo.entrypoints.tui.modelo.lifecycle import ModeloLifecycleActionUnavailableError
from cadrumo.entrypoints.tui.navigation import TuiScreenContextV1

_PERIOD = Period.from_year_and_code(2025, "1T")


def _refuse_fixture_write(modelo: str, year: int, period: Period) -> ModeloWorkCreateResultV1:
    raise ModeloLifecycleActionUnavailableError(
        translated_message="tui.declarations.refusal.handoff",
        context={"modelo": modelo, "year": year, "period": period.registry_token},
    )


def build_grouped() -> App[None]:
    """Review the real grouped list over synthetic, explicitly separated facts."""
    workspace, calendar = portfolio_projection()
    with bundled_indexed_authority().operation() as operation:
        targets = declaration_targets(operation)
    controller = DeclarationsWorkspaceController(
        TuiScreenContextV1(destination="workbench.declarations"),
        workspace,
        work_action=ActionReference(action_id=lookup_action("operator.modelo.work.list").action_id),
        revisions_action=ActionReference(action_id=lookup_action("operator.modelo.work.revisions").action_id),
        filing_action=ActionReference(action_id=lookup_action("operator.modelo.filing_record.list").action_id),
        calendar_projection=calendar,
        creation_targets=targets,
        work_create_handoff=_refuse_fixture_write,
    )
    return ScreenHostApp[None](DeclarationsOverviewScreen(controller))


def build_picker_modelo() -> App[DeclarationTarget | None]:
    """Review supported modelo names with the profile applicability shortcut."""
    with bundled_indexed_authority().operation() as operation:
        targets = declaration_targets(operation)
    return ScreenHostApp(NewDeclarationPicker(targets, frozenset({"130", "303", "349"})))


def build_picker_period() -> App[DeclarationTarget | None]:
    """Review the period step using only the published registry choices."""
    with bundled_indexed_authority().operation() as operation:
        targets = declaration_targets(operation)
    picker = NewDeclarationPicker(targets, frozenset({"130"}), preferred=DeclarationTarget("130", _PERIOD))
    # A capture opens the production second step without pretending a choice
    # has been confirmed or submitting a write to storage.
    picker.modelo = "130"
    return ScreenHostApp(picker)


def build_external_details() -> App[None]:
    """Review independent external completion before revealing its reference."""
    workspace, calendar = portfolio_projection()
    row = next(row for row in declaration_list_rows(workspace, calendar) if row.state == "aeat_unlinked")
    return ScreenHostApp[None](ExternalFilingDetailsScreen(row))


__all__ = [
    "build_external_details",
    "build_grouped",
    "build_picker_modelo",
    "build_picker_period",
    "portfolio_projection",
]
