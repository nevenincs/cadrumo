"""MCP serves the navigation register as searchable data and checks a view link before an agent writes one."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from cadrumo.application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from cadrumo_client.contracts import navigation
from cadrumo_client.contracts.navigation import (
    NavigationRegister,
    NavigationSurface,
    load_navigation_register,
    view_link,
)
from cadrumo_client.transport.frontend_client import FrontendClient

from .. import view_register
from ..runtime_adapter import RuntimeMcpAdapter
from ..server import build_server
from ..surfaces import MCP_SURFACES, McpSurfaceName
from .admitted_lease import AdmittedLease
from .session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_INVOICE = "0123456789abcdef" * 4
_RETIRED = "statements"


class _SpeakingLease(AdmittedLease):
    """An admitted lease whose profile stores one output language, read as the profile view reads it."""

    def __init__(self, language: str | None) -> None:
        super().__init__(uuid4())
        self.language = language
        self.views_read = 0

    def read_profile_view(self, page_kinds: tuple[ProfileViewPageKind, ...]) -> SimpleNamespace:
        assert page_kinds == (ProfileViewPageKind.PREFERENCES,)
        self.views_read += 1
        items = (
            ()
            if self.language is None
            else (ProfileViewFactItem(path=PROFILE_OUTPUT_LANGUAGE_PATH, value=self.language),)
        )
        return SimpleNamespace(items=lambda _kind: items, record_revision=1, content_digest="0" * 64)


async def _call(
    arguments: dict[str, Any], *, language: str | None = "ca", surface: McpSurfaceName = McpSurfaceName.FULL
) -> dict[str, Any]:
    lease = _SpeakingLease(language)
    adapter = RuntimeMcpAdapter(
        profile_id=lease.profile_id, client=cast(FrontendClient, lease), surface=MCP_SURFACES[surface]
    )
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            result = await sdk.call_tool("views", arguments)
    finally:
        await adapter.close()
    document = result.structured_content
    assert isinstance(document, dict), result
    assert result.is_error is (document.get("outcome") == "refused")
    return document


@pytest.mark.anyio
@pytest.mark.parametrize("surface", list(MCP_SURFACES.values()), ids=lambda surface: surface.name.value)
async def test_every_surface_advertises_views_as_a_local_read(surface: Any) -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None, surface=surface)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            tools = {tool.name: tool for tool in (await sdk.list_tools()).tools}
    finally:
        await adapter.close()
    views = tools["views"]
    assert views.annotations is not None
    assert views.annotations.read_only_hint is True
    assert views.annotations.open_world_hint is False
    assert views.annotations.destructive_hint is False
    assert views.input_schema["required"] == []
    assert set(views.input_schema["properties"]) == {"query", "id", "link", "limit"}


@pytest.mark.anyio
async def test_an_exact_id_answers_every_fact_of_the_view_with_its_label_in_the_profiles_language() -> None:
    found = await _call({"id": "ledger/invoices"}, language="ca")

    assert found["outcome"] == "found"
    assert found["language"] == "ca"
    assert found["views"] == [
        {
            "id": "ledger/invoices",
            "parent": "ledger",
            "surfaces": ["gui"],
            "params": {"select": {"kind": "invoice", "alphabet": "0123456789abcdef", "length": 64}},
            "keywords": ["invoices", "bills", "facturas"],
            "label": lookup_translation("navigation.view.ledger.invoices.label", locale="ca"),
            "label_key": "navigation.view.ledger.invoices.label",
            "link": "cadrumo://view/ledger/invoices",
        }
    ]
    assert found["views"][0]["label"] not in {None, "", "navigation.view.ledger.invoices.label"}


@pytest.mark.anyio
async def test_a_profile_with_no_language_is_answered_in_the_default_language() -> None:
    found = await _call({"id": "profile/aeat-access"}, language=None)
    assert found["language"] == "es"
    assert found["views"][0]["label"] == lookup_translation("navigation.view.profile.aeat_access.label", locale="es")
    assert found["views"][0]["surfaces"] == ["gui"]


@pytest.mark.anyio
async def test_a_search_matches_labels_keywords_and_ids_best_first() -> None:
    by_keyword = await _call({"query": "facturas"}, language="en")
    assert by_keyword["views"][0]["id"] == "ledger/invoices"

    by_id = await _call({"query": "calendar"}, language="en")
    assert by_id["views"][0]["id"] == "calendar"

    # Accents fold, and a word must match for a view to be answered at all.
    folded = await _call({"query": "plázos"}, language="es")
    assert [row["id"] for row in folded["views"]] == ["calendar"]
    assert (await _call({"query": "zzzz"}))["views"] == []


@pytest.mark.anyio
async def test_listing_answers_every_view_once_in_register_order_within_the_limit() -> None:
    register = load_navigation_register()
    everything = await _call({"limit": 50})
    assert [row["id"] for row in everything["views"]] == [element.id for element in register.elements]
    assert everything["total"] == len(register.elements)
    page = await _call({"limit": 2})
    assert len(page["views"]) == 2 and page["total"] == len(register.elements)


@pytest.mark.anyio
async def test_a_valid_link_is_answered_with_its_parsed_parts() -> None:
    link = f"cadrumo://view/ledger/invoices?prefer=gui&select={_INVOICE}"
    checked = await _call({"link": link})

    assert checked["outcome"] == "valid"
    assert checked["view"]["id"] == "ledger/invoices"
    assert checked["params"] == {"select": _INVOICE}
    assert checked["prefer"] == "gui"
    # The canonical spelling writes parameters in name order and prefer last.
    assert checked["link"] == f"cadrumo://view/ledger/invoices?select={_INVOICE}&prefer=gui"
    assert checked["link"] == view_link("ledger/invoices", {"select": _INVOICE}, NavigationSurface.GUI)
    assert checked["opens"] == {
        "surface": "gui",
        "view": "ledger/invoices",
        "fallback": "none",
        "params_kept": True,
        "notice_due": False,
    }


@pytest.mark.anyio
async def test_a_link_naming_a_surface_the_register_does_not_declare_is_invalid() -> None:
    assert await _call({"link": f"cadrumo://view/ledger/invoices?select={_INVOICE}&prefer=tui"}) == {
        "outcome": "invalid",
        "reason": "query",
    }


@pytest.mark.anyio
async def test_a_valid_link_without_a_preference_opens_on_the_window() -> None:
    window_first = await _call({"link": "cadrumo://view/profile/aeat-access"})
    assert window_first["opens"] == {
        "surface": "gui",
        "view": "profile/aeat-access",
        "fallback": "none",
        "params_kept": True,
        "notice_due": False,
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("link", "reason"),
    [
        ("cadrumo://profiles/5aa00000-0000-4000-8000-0000000000aa/ledger", "not_a_view_link"),
        ("cadrumo://view/Ledger", "uppercase"),
        ("cadrumo://view/ledger#entries", "fragment"),
        ("cadrumo://view/nowhere", "unknown_view"),
        ("cadrumo://view/ledger/invoices?select=0042", "param_malformed"),
        (f"cadrumo://view/calendar?select={_INVOICE}", "param_not_accepted"),
        ("cadrumo://view/ledger?select=a&select=b", "query"),
    ],
)
async def test_a_refused_link_is_answered_with_the_parsers_reason(link: str, reason: str) -> None:
    assert await _call({"link": link}) == {"outcome": "invalid", "reason": reason}


@pytest.mark.anyio
async def test_naming_more_than_one_selector_is_refused() -> None:
    refused = await _call({"id": "ledger", "query": "ledger"})
    assert refused["outcome"] == "refused"
    assert refused["code"] == "invalid_request"


@pytest.fixture
def register_with_a_retired_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[NavigationRegister]:
    """The shipped register with one more id retired, served to the tool as the packaged one."""
    source = Path(navigation.__file__).with_name("navigation.toml").read_text(encoding="utf-8")
    declared = next(line for line in source.splitlines() if line.startswith("retired = "))
    fixture = tmp_path / "navigation.toml"
    fixture.write_text(source.replace(declared, f'retired = ["{_RETIRED}"]'), encoding="utf-8")
    register = load_navigation_register(fixture)
    assert _RETIRED in register.retired and register.element(_RETIRED) is None
    monkeypatch.setattr(view_register, "load_navigation_register", lambda: register)
    yield register


@pytest.mark.anyio
async def test_a_retired_id_is_never_answered_as_a_view(register_with_a_retired_id: NavigationRegister) -> None:
    assert await _call({"id": _RETIRED}) == {"outcome": "not_found", "id": _RETIRED, "language": "ca"}
    assert _RETIRED not in {row["id"] for row in (await _call({"query": _RETIRED}))["views"]}
    assert _RETIRED not in {row["id"] for row in (await _call({"limit": 50}))["views"]}
    assert await _call({"link": f"cadrumo://view/{_RETIRED}"}) == {"outcome": "invalid", "reason": "unknown_view"}


@pytest.mark.anyio
async def test_without_a_session_the_tool_sends_the_agent_to_the_person() -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            result = await sdk.call_tool("views", {"id": "ledger"})
    finally:
        await adapter.close()
    assert result.is_error is True
    assert result.structured_content is not None
    assert result.structured_content["outcome"] == "refused"
    assert "remedy" in result.structured_content
