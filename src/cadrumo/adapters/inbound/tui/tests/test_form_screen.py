"""Pilot-driven proofs for the reusable field page.

The page replaces a paged flow, so the tests pin the properties that made
the replacement worth doing: every field is reachable in any order on one
screen, a field the operator never opened is still checked before commit,
and a page whose shape depends on its own answers regenerates without
carrying stale values forward.

Assertions are against widget ids, returned values and CSS classes — never
rendered prose, which is locale data and would make them tautological.
"""

from __future__ import annotations

import pytest
from textual.app import App
from textual.containers import ScrollableContainer
from textual.widgets import Button, DataTable, Input, SelectionList, Static

from cadrumo.entrypoints.tui.components.forms import (
    FormField,
    FormFieldKind,
    FormPage,
    form_choices,
    multi_choice_tokens,
)
from cadrumo.entrypoints.tui.components.widgets import ContentScroll

from .. import FormApp, FormScreen

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

_TERMINAL_SIZE = (140, 60)


def _page(*fields: FormField) -> FormPage:
    return FormPage(title="TITLE", section="SECTION", fields=fields)


def _form[AppResult](app: App[AppResult]) -> FormScreen:
    """The form page, wherever it currently sits in the screen stack.

    The page is a screen the host pushes rather than the host's own body,
    so it is addressed directly here for two reasons: an open edit dialog
    sits above it, which rules out ``app.screen``, and ``App.query_one``
    resolves against the default screen, which the page is not.
    """
    return next(screen for screen in reversed(app.screen_stack) if isinstance(screen, FormScreen))


def _rows[AppResult](app: App[AppResult]) -> dict[str, str]:
    table: DataTable[str] = _form(app).query_one("#form-table", DataTable)
    return {str(row_key.value): str(table.get_row(row_key)[1]) for row_key in table.rows}


@pytest.mark.asyncio
async def test_every_field_is_on_one_page_in_declaration_order() -> None:
    """The paradigm difference: no next, no back, everything visible."""
    app = FormApp(_page(FormField(key="a", label="A"), FormField(key="b", label="B", value="set")))
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        assert list(_rows(app)) == ["a", "b"]
        assert _rows(app)["b"] == "set"
        app.exit(None)


@pytest.mark.asyncio
async def test_editing_a_row_writes_the_typed_value_back_to_the_page() -> None:
    app = FormApp(_page(FormField(key="a", label="A")))
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        _form(app).query_one("#form-table", DataTable).action_select_cursor()
        await pilot.pause()
        app.screen.query_one("#edit-input", Input).value = "typed"
        await pilot.click("#btn-edit-save")
        await pilot.pause()
        assert _rows(app)["a"] == "typed"
        app.exit(None)


@pytest.mark.asyncio
async def test_a_refused_value_holds_the_dialog_open_and_never_reaches_the_page() -> None:
    """Validation runs where the value was typed, not at submit.

    A refusal that only surfaced at commit would make the operator hunt
    for which of several fields it came from.
    """
    app = FormApp(_page(FormField(key="a", label="A", validate=lambda value: "NO" if value == "bad" else None)))
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        _form(app).query_one("#form-table", DataTable).action_select_cursor()
        await pilot.pause()
        app.screen.query_one("#edit-input", Input).value = "bad"
        await pilot.click("#btn-edit-save")
        await pilot.pause()
        assert str(app.screen.query_one("#edit-refusal", Static).content), "the refusal must be shown"
        assert _rows(app)["a"] == "", "a refused value must not reach the page"
        app.exit(None)


@pytest.mark.asyncio
async def test_commit_rechecks_a_field_the_operator_never_opened() -> None:
    """A required field left untouched has never been validated once."""
    app = FormApp(_page(FormField(key="a", label="A", validate=lambda value: None if value else "REQUIRED")))
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        await pilot.click("#btn-form-save")
        await pilot.pause()
        assert app.collected is None, "commit must refuse while a field is invalid"
        assert str(_form(app).query_one("#form-refusal", Static).content)
        app.exit(None)


@pytest.mark.asyncio
async def test_committing_returns_every_value_and_abandoning_returns_nothing() -> None:
    app = FormApp(_page(FormField(key="a", label="A", value="one"), FormField(key="b", label="B", value="two")))
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        await pilot.click("#btn-form-save")
        await pilot.pause()
    assert app.collected == {"a": "one", "b": "two"}

    abandoned = FormApp(_page(FormField(key="a", label="A", value="one")))
    async with abandoned.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        await pilot.click("#btn-form-cancel")
        await pilot.pause()
    assert abandoned.collected is None


@pytest.mark.asyncio
async def test_a_multi_choice_field_stores_the_tokens_it_was_given() -> None:
    field = FormField(
        key="scopes",
        label="Scopes",
        kind=FormFieldKind.MULTI_CHOICE,
        choices=form_choices([("READ", "Read"), ("WRITE", "Write")]),
    )
    app = FormApp(_page(field))
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        _form(app).query_one("#form-table", DataTable).action_select_cursor()
        await pilot.pause()
        app.screen.query_one("#edit-choices", SelectionList).select_all()
        await pilot.click("#btn-edit-save")
        await pilot.pause()
        assert _rows(app)["scopes"] == "Read, Write"
        await pilot.click("#btn-form-save")
        await pilot.pause()
    assert app.collected is not None
    assert set(multi_choice_tokens(app.collected["scopes"])) == {"READ", "WRITE"}


@pytest.mark.asyncio
async def test_choice_rows_render_labels_and_never_storage_tokens() -> None:
    """The page may store a schema token but must speak in operator labels."""
    field = FormField(
        key="route",
        label="Cl@ve Móvil route",
        value="app_request",
        kind=FormFieldKind.SINGLE_CHOICE,
        choices=form_choices([("qr", "QR code"), ("app_request", "Request in app")]),
    )
    app = FormApp(_page(field))

    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        rendered = _rows(app)["route"]
        assert rendered == "Request in app"
        assert "app_request" not in rendered
        app.exit(None)


@pytest.mark.asyncio
async def test_the_page_works_in_a_host_that_is_not_its_own_application() -> None:
    """The page is reachable from an application that is already running.

    This is the property the page was separated from its application to
    obtain, and it cannot be observed through :class:`FormApp`, which
    always starts a fresh application. A host that is already running one
    cannot start a second — so if the page only worked as an application,
    every door reached from inside a running screen would be shut.

    The host here is a plain application standing in for any such caller,
    deliberately not the profile manager: what is being pinned is that the
    page needs nothing from a particular host, only somewhere to be
    pushed.
    """

    class _Host(App[None]):
        pass

    host = _Host()
    async with host.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        collected: list[object] = []
        host.push_screen(
            FormScreen(_page(FormField(key="a", label="A", value="carried"))),
            collected.append,
        )
        await pilot.pause()

        assert _rows(host)["a"] == "carried", "the page must render inside the borrowed host"

        await pilot.click("#btn-form-save")
        await pilot.pause()
        assert collected == [{"a": "carried"}], "committing must hand the values back to the host"
        host.exit(None)


@pytest.mark.asyncio
async def test_a_shrinking_page_drops_the_values_it_no_longer_asks_for() -> None:
    """A count that falls must not commit the children it stopped asking about.

    This is the repeating-group case the paged flow used to own: without
    the drop, lowering the count would silently persist a stale child the
    operator can no longer see.
    """

    def rebuild(values):
        count = int(values["count"]) if values["count"].isdigit() else 0
        return _page(
            FormField(key="count", label="Count", value=values["count"]),
            *[FormField(key=f"child-{index}", label=f"Child {index}") for index in range(count)],
        )

    app = FormApp(_page(FormField(key="count", label="Count", value="2")), rebuild=rebuild)
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        table: DataTable[str] = _form(app).query_one("#form-table", DataTable)
        table.action_select_cursor()
        await pilot.pause()
        app.screen.query_one("#edit-input", Input).value = "2"
        await pilot.click("#btn-edit-save")
        await pilot.pause()
        assert list(_rows(app)) == ["count", "child-0", "child-1"]

        table.action_select_cursor()
        await pilot.pause()
        app.screen.query_one("#edit-input", Input).value = "1"
        await pilot.click("#btn-edit-save")
        await pilot.pause()
        assert list(_rows(app)) == ["count", "child-0"]

        await pilot.click("#btn-form-save")
        await pilot.pause()
    assert app.collected is not None
    assert "child-1" not in app.collected


@pytest.mark.asyncio
async def test_an_overflowing_form_has_exactly_one_visible_vertical_scrollbar() -> None:
    """The outer page, not its auto-height table, owns vertical scrolling.

    Twenty real rows are a positive control: at this terminal height the
    page cannot fit, so a test that merely observed no table scrollbar would
    be vacuous. The mounted widget geometry proves both the overflow and the
    single-owner result that prevents adjacent right-side tracks.
    """
    app = FormApp(
        _page(
            *[FormField(key=f"field-{index}", label=f"Field {index}", value=str(index)) for index in range(20)],
        ),
    )
    async with app.run_test(size=(80, 16)) as pilot:
        await pilot.pause()
        form = _form(app)
        outer = form.query_one(ContentScroll)
        table = form.query_one("#form-table", DataTable)

        assert outer.virtual_size.height > outer.container_size.height
        assert outer.show_vertical_scrollbar
        assert not table.show_vertical_scrollbar
        assert table.virtual_size.height == table.container_size.height
        assert table.max_scroll_y == 0

        visible_owners = [
            widget
            for widget in app.screen.walk_children()
            if isinstance(widget, ScrollableContainer) and widget.display and widget.show_vertical_scrollbar
        ]
        assert visible_owners == [outer]

        await pilot.press("tab")
        await pilot.pause()
        cancel = form.query_one("#btn-form-cancel", Button)
        assert cancel.has_focus
        assert outer.region.contains_region(cancel.region)
        app.exit(None)
