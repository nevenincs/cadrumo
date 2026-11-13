"""The Add entry form is read from the served ``ledger.add`` request schema, never composed in the frontend."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import cast

import pytest
from textual.widgets import Button, Collapsible, Input, Select, Static
from textual.widgets._select import InvalidSelectValueError

from .....application.ledger.tests.add_request_description_support import ledger_add_description
from .....core.config import override_settings
from .....domain.transactions.enums import BusinessClassification, TransactionDirection
from ...tests.settling import settle
from ..entries_add import FIELD_LABEL_LOCALE_KEYS, SUPPLIED_FIELDS, LedgerEntryAddScreen
from ..entries_add_form import LedgerAddFormUnavailableError, LedgerAddFormV1, read_served_form
from ..models import LedgerFlowState
from .entries_door_fixtures import MemoryEntriesLedger, entries_controller, served_add_form
from .workspace_fixtures import WorkspaceHostApp

_BOOKED_DATE = date.today().isoformat()

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: Written out here, not derived from the schema under test.
_REQUIRED = ["booked_date", "amount", "direction", "description"]
_SERVED_CLASSIFICATIONS = ["BUSINESS", "PERSONAL", "MIXED", "NOT_YET_PROCESSED"]


def _served_schema() -> dict[str, object]:
    return deepcopy(dict(ledger_add_description().request_json_schema))


def _read(schema: dict[str, object]) -> LedgerAddFormV1:
    return read_served_form(schema, offered=FIELD_LABEL_LOCALE_KEYS, supplied=SUPPLIED_FIELDS)


def _properties(schema: dict[str, object]) -> dict[str, dict[str, object]]:
    return cast("dict[str, dict[str, object]]", schema["properties"])


def test_the_required_and_optional_facts_are_the_served_ones() -> None:
    form = served_add_form()

    assert [field.name for field in form.required] == _REQUIRED
    optional = [field.name for field in form.optional]
    assert "business_classification" in optional
    assert "profile_id" not in optional
    assert "attachment_ids" not in optional
    assert all(field.name in FIELD_LABEL_LOCALE_KEYS for field in form.fields)


def test_the_choices_are_the_tokens_the_schema_lists() -> None:
    form = served_add_form()

    assert form.field("direction").choices == ("INCOMING", "OUTGOING", "INTERNAL_TRANSFER")
    assert form.field("business_classification").choices == tuple(_SERVED_CLASSIFICATIONS)
    assert form.field("business_classification").default == "NOT_YET_PROCESSED"
    assert form.field("direction").default is None
    assert not form.field("amount").is_choice


def test_a_fact_the_schema_makes_required_is_required_here_and_a_narrowed_choice_list_is_narrowed() -> None:
    schema = _served_schema()
    cast("list[str]", schema["required"]).append("counterparty")
    _properties(schema)["business_classification"]["enum"] = ["BUSINESS", "PERSONAL"]
    _properties(schema)["counterparty"] = {"type": "string"}

    form = _read(schema)

    assert "counterparty" in [field.name for field in form.required]
    assert form.field("business_classification").choices == ("BUSINESS", "PERSONAL")


def test_a_fact_the_schema_stops_serving_is_not_offered() -> None:
    schema = _served_schema()
    del _properties(schema)["notes"]

    assert "notes" not in [field.name for field in _read(schema).fields]


def test_a_required_fact_the_form_has_no_words_for_refuses_the_form() -> None:
    schema = _served_schema()
    cast("list[str]", schema["required"]).append("a_fact_added_later")
    _properties(schema)["a_fact_added_later"] = {"type": "string"}

    with pytest.raises(LedgerAddFormUnavailableError, match="a_fact_added_later"):
        _read(schema)


def test_a_required_fact_that_is_not_text_refuses_the_form() -> None:
    schema = _served_schema()
    _properties(schema)["amount"] = {"type": "array", "items": {"type": "string"}}

    with pytest.raises(LedgerAddFormUnavailableError, match="amount"):
        _read(schema)


def test_a_schema_without_facts_refuses_the_form() -> None:
    with pytest.raises(LedgerAddFormUnavailableError):
        _read({"type": "object"})


@pytest.mark.asyncio
async def test_the_screen_asks_for_the_required_facts_openly_and_offers_only_the_served_classifications() -> None:
    ledger = MemoryEntriesLedger()
    screen = LedgerEntryAddScreen(entries_controller(), ledger.doors(), served_add_form())
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            optional = screen.query_one("#entries-add-optional", Collapsible)
            inside = {widget.id for widget in optional.query(Input)} | {widget.id for widget in optional.query(Select)}
            for name in _REQUIRED:
                widget_id = f"entries-add-{name.replace('_', '-')}"
                assert screen.query_one(f"#{widget_id}").id not in inside
            assert "entries-add-business-classification" in inside
            classification = cast("Select[str]", screen.query_one("#entries-add-business-classification", Select))
            assert classification.value == "NOT_YET_PROCESSED"
            assert _selectable(classification, [member.value for member in BusinessClassification]) == (
                _SERVED_CLASSIFICATIONS
            )
            direction = cast("Select[str]", screen.query_one("#entries-add-direction", Select))
            assert direction.is_blank()
            assert _selectable(direction, [member.value for member in TransactionDirection]) == [
                "INCOMING",
                "OUTGOING",
                "INTERNAL_TRANSFER",
            ]


@pytest.mark.asyncio
async def test_a_review_without_a_required_choice_is_refused_by_the_request_and_writes_nothing() -> None:
    ledger = MemoryEntriesLedger()
    screen = LedgerEntryAddScreen(entries_controller(), ledger.doors(), served_add_form())
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            screen.query_one("#entries-add-booked-date", Input).value = _BOOKED_DATE
            screen.query_one("#entries-add-amount", Input).value = "10.00"
            screen.query_one("#entries-add-description", Input).value = "Synthetic"
            screen.query_one("#entries-add-review", Button).press()
            await settle(pilot)
            assert screen.flow_state is LedgerFlowState.EDITING
            assert "required" in str(screen.query_one("#ledger-refusal", Static).render()).lower()
    assert ledger.requests == []


def _selectable(select: Select[str], tokens: list[str]) -> list[str]:
    """The tokens ``select`` takes as its value, in the order given; it refuses any other."""
    taken: list[str] = []
    for token in tokens:
        try:
            select.value = token
        except InvalidSelectValueError:
            continue
        taken.append(token)
    return taken
