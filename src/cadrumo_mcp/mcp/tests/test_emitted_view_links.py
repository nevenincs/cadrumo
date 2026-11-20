"""Every view link Cadrumo can hand the agent opens on the window, or the gate fails."""

from __future__ import annotations

from typing import Any

import pytest

from cadrumo.application.auth.setup_handoff import auth_setup_handoff
from cadrumo.application.auth.sync_readiness import AuthSyncReadiness
from cadrumo.application.operations.contract_manifest import load_operation_contract_manifest
from cadrumo.application.operations.operation_pages import operation_destination
from cadrumo_client.contracts.navigation import (
    NavigationSurface,
    ViewLinkRefused,
    ViewOpened,
    load_navigation_register,
    parse_view_link,
    resolve_view,
    view_link,
)

from ..record_links import RECORD_VIEWS, record_link
from ..view_register import VIEW_PAGE_MAX, view_register_query

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ID = "0123456789abcdef" * 4


def _opens_on_the_window(link: str) -> bool:
    """Whether the link parses and the declared implementation opens exactly the element it names."""
    parsed = parse_view_link(link)
    if isinstance(parsed, ViewLinkRefused):
        return False
    outcome = resolve_view(parsed)
    return isinstance(outcome, ViewOpened) and outcome.surface is NavigationSurface.GUI and outcome.fallback == "none"


def _operation_links() -> dict[str, str]:
    """The link ``execute`` attaches for each registered operation, keyed by definition id."""
    links: dict[str, str] = {}
    for entry in load_operation_contract_manifest().operations:
        definition_id = entry.contract.definition_id
        page = operation_destination(definition_id)
        if page is not None:
            links[definition_id] = view_link(page)
    return links


def _record_document(path: tuple[str, ...]) -> dict[str, Any]:
    projection: Any = _ID
    for key in reversed(path):
        projection = {key: projection}
    return {"outcome": "success", "projection": projection}


def _register_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query in ({}, *({"query": element.id} for element in load_navigation_register().elements)):
        answer = view_register_query({**query, "limit": VIEW_PAGE_MAX}, "en")
        rows.extend(answer.get("views", []))
    return rows


def test_there_are_operations_to_gate() -> None:
    assert len(load_operation_contract_manifest().operations) > 50
    assert _operation_links()


def test_every_operation_page_link_opens_on_the_window() -> None:
    unopened = {
        definition_id: link for definition_id, link in _operation_links().items() if not _opens_on_the_window(link)
    }
    assert unopened == {}


def test_every_record_link_opens_on_the_window() -> None:
    assert RECORD_VIEWS
    for result_schema_id, record in RECORD_VIEWS.items():
        emitted = record_link(result_schema_id, _record_document(record.path))
        assert emitted is not None, result_schema_id
        assert _opens_on_the_window(emitted["link"]), result_schema_id


def test_every_row_link_the_views_tool_returns_opens_on_the_window() -> None:
    rows = _register_rows()
    assert {row["id"] for row in rows} == load_navigation_register().ids_for(NavigationSurface.GUI)
    assert [row["link"] for row in rows if not _opens_on_the_window(row["link"])] == []


def test_the_aeat_setup_handoff_link_opens_on_the_window() -> None:
    assert _opens_on_the_window(auth_setup_handoff(AuthSyncReadiness()).url)


@pytest.mark.parametrize("view_id", ["home", "withholding", "operations", "installation", "reference"])
def test_the_gate_detects_a_link_to_an_element_no_surface_implements(view_id: str) -> None:
    link = f"cadrumo://view/{view_id}"
    assert not _opens_on_the_window(link)
    assert view_link(view_id) == link
    assert link not in {row["link"] for row in _register_rows()}
