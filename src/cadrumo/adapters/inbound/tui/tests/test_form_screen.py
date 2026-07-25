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
from textual.widgets import DataTable, Input, SelectionList, Static

from .. import FormApp, FormField, FormFieldKind, FormPage, form_choices, multi_choice_tokens

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

_TERMINAL_SIZE = (140, 60)


def _page(*fields: FormField) -> FormPage:
    return FormPage(title="TITLE", section="SECTION", fields=fields)


def _rows(app: FormApp) -> dict[str, str]:
    table: DataTable[str] = app.query_one("#form-table", DataTable)
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
        app.query_one("#form-table", DataTable).action_select_cursor()
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
        app.query_one("#form-table", DataTable).action_select_cursor()
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
        assert str(app.query_one("#form-refusal", Static).content)
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
        app.query_one("#form-table", DataTable).action_select_cursor()
        await pilot.pause()
        app.screen.query_one("#edit-choices", SelectionList).select_all()
        await pilot.click("#btn-edit-save")
        await pilot.pause()
        assert set(multi_choice_tokens(_rows(app)["scopes"])) == {"READ", "WRITE"}
        app.exit(None)


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
        table: DataTable[str] = app.query_one("#form-table", DataTable)
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
