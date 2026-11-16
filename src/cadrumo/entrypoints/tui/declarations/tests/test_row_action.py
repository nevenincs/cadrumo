"""One row action decides both the Enter hint and what Enter does on a declarations row."""

from __future__ import annotations

from typing import cast

import pytest
from textual.screen import Screen

from .....application.modelo.declarations_list import declaration_list_rows
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from ...navigation import TuiScreenContextV1
from ..controller import DeclarationsWorkspaceController
from ..models import (
    DeclarationsWorkspaceWiringV1,
    ModeloWorkCreateHandoffV1,
    ModeloWorkspaceScreenFactoryV1,
)
from ..portfolio_rendering import RowAction, row_action, row_enter_action
from .portfolio_fixtures import portfolio_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _action(action_id: str) -> ActionReference:
    return ActionReference(action_id=lookup_action(action_id).action_id)


def _factory(_declaration: object) -> Screen[None]:
    raise AssertionError("the row action is decided without opening anything")


def _controller(*, factory: bool, create: bool) -> DeclarationsWorkspaceController:
    projection, calendar = portfolio_projection()
    return DeclarationsWorkspaceController(
        TuiScreenContextV1(destination="workbench.declarations"),
        projection,
        DeclarationsWorkspaceWiringV1(
            work_action=_action("operator.modelo.work.list"),
            revisions_action=_action("operator.modelo.work.revisions"),
            filing_action=_action("operator.modelo.filing_record.list"),
            modelo_workspace_factory=cast(ModeloWorkspaceScreenFactoryV1, _factory) if factory else None,
            work_create_handoff=cast(ModeloWorkCreateHandoffV1, object()) if create else None,
            calendar_projection=calendar,
        ),
    )


@pytest.mark.parametrize("factory", [True, False])
@pytest.mark.parametrize("create", [True, False])
def test_the_enter_hint_is_said_exactly_for_the_rows_enter_acts_on(*, factory: bool, create: bool) -> None:
    controller = _controller(factory=factory, create=create)
    rows = declaration_list_rows(controller.projection, controller.calendar_projection)
    assert rows
    for row in rows:
        action = row_action(row, controller)
        assert (action is not None) == bool(row_enter_action(row, controller)), row.key


def test_a_readable_declaration_opens_only_where_a_workspace_is_bound() -> None:
    bound = _controller(factory=True, create=False)
    unbound = _controller(factory=False, create=False)
    rows = [
        row
        for row in declaration_list_rows(bound.projection, bound.calendar_projection)
        if row.declaration is not None and row.state != "unreadable"
    ]
    assert rows
    for row in rows:
        assert row_action(row, bound) in {RowAction.OPEN, RowAction.OPEN_LOCAL_DRAFT}
        assert row_action(row, unbound) is None


def test_starting_a_due_return_needs_the_creation_handoff() -> None:
    with_create = _controller(factory=False, create=True)
    without = _controller(factory=False, create=False)
    due = [
        row
        for row in declaration_list_rows(with_create.projection, with_create.calendar_projection)
        if row.state == "not_started" and row.period is not None
    ]
    assert due
    for row in due:
        assert row_action(row, with_create) is RowAction.START
        assert row_action(row, without) is None
