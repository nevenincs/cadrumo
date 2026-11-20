"""No reference answer a model reads is large: each list is a page, each long text a window.

A reply stays in the model's context and is read again on every later model
call of the turn. These tests run the real queries against the published
authority and hold every default reply to the bound, then follow the cursors
and hold the pages to the catalogue the command line prints: every row exactly
once, in order, with the total the first page stated.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from mcp.types import TextContent

from cadrumo.application import reference_catalogue as catalogue
from cadrumo.application.reference_catalogue import read_pinned_reference
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.portals.registry import PORTAL_REGISTRY

from ..authority_query import authority_query
from ..bounded_pages import REPLY_BYTES, ROWS_MAX, encoded_size
from ..protocol_contract import MCP_TOOL_CATALOGUE, validate_tool_arguments
from ..server import build_server
from .admitted_lease import admitted_adapter
from .session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def _pages(first: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield every page of ``first``'s answer by following each reply's own ``next_call``."""
    reply = authority_query(first)
    while True:
        assert reply["outcome"] == "published", reply
        assert encoded_size(reply) <= REPLY_BYTES
        yield reply
        paging = reply["paging"]
        if paging["next_cursor"] is None:
            return
        assert paging["next_call"]["tool"] == "authority"
        assert paging["next_call"]["arguments"]["cursor"] == paging["next_cursor"] > paging["offset"]
        reply = authority_query(paging["next_call"]["arguments"])


def _rows(first: dict[str, Any], member: str) -> list[Any]:
    pages = list(_pages(first))
    rows = [row for page in pages for row in page["report"][member]]
    assert len(rows) == pages[0]["paging"]["total"]
    assert sum(page["paging"]["returned"] for page in pages) == len(rows)
    return rows


def _only(row: dict[str, Any], members: tuple[str, ...]) -> dict[str, Any]:
    return {member: row[member] for member in members}


def _modelo_codes() -> list[str]:
    return [row["code"] for row in _rows({"query": "modelos"}, "modelos")]


_ONE_OF_EACH: tuple[dict[str, Any], ...] = (
    {"query": "modelos"},
    {"query": "support"},
    {"query": "describe", "modelo": "303", "period": "3T"},
    {"query": "casillas", "modelo": "303", "period": "3T"},
    {"query": "casilla", "modelo": "303", "period": "3T", "casilla": "01"},
    {"query": "formulas", "modelo": "303", "period": "3T"},
    {"query": "bindings", "modelo": "303", "filing_year": 2025},
    {"query": "categories"},
    {"query": "portals"},
    {"query": "portal", "portal": next(iter(PORTAL_REGISTRY))},
    {"query": "auth_providers"},
    {"query": "apoderado_scopes"},
)


@pytest.mark.parametrize("arguments", _ONE_OF_EACH, ids=[arguments["query"] for arguments in _ONE_OF_EACH])
def test_every_authority_query_answers_within_the_bound_by_default(arguments: dict[str, Any]) -> None:
    reply = authority_query(arguments)

    assert reply["outcome"] == "published", reply
    assert encoded_size(reply) <= REPLY_BYTES
    # The wire's text block is the same document, compact and unescaped.
    assert len(json.dumps(reply, ensure_ascii=False, separators=(",", ":")).encode()) <= REPLY_BYTES


def test_no_modelo_answers_a_scoped_query_past_the_bound() -> None:
    codes = _modelo_codes()
    assert len(codes) > 10
    widest: dict[str, int] = {}
    for code in codes:
        for query in ("support", "describe", "casillas", "formulas", "bindings"):
            arguments: dict[str, Any] = {"query": query, "modelo": code}
            if query == "bindings":
                arguments["filing_year"] = 2025
            try:
                reply = authority_query(arguments)
            except RegistryError:
                # A year that selects two revisions of one modelo is refused by the catalogue, whole or paged.
                assert query == "bindings"
                continue
            assert reply["outcome"] == "published", reply
            widest[query] = max(widest.get(query, 0), encoded_size(reply))
    assert set(widest) == {"support", "describe", "casillas", "formulas", "bindings"}
    assert max(widest.values()) <= REPLY_BYTES


def test_a_page_says_its_total_and_how_to_reach_the_next_and_the_detail() -> None:
    first = authority_query({"query": "casillas", "modelo": "303", "period": "3T"})

    paging = first["paging"]
    assert paging["offset"] == 0 and paging["returned"] == len(first["report"]["rows"]) < paging["total"]
    assert paging["next_cursor"] == paging["returned"]
    assert paging["next_call"] == {
        "tool": "authority",
        "arguments": {"query": "casillas", "modelo": "303", "period": "3T", "cursor": paging["returned"]},
    }
    assert "query=casilla" in paging["detail"]
    assert first["report"]["casilla_count"] == paging["total"]


def test_paging_casillas_visits_every_row_once_and_the_total_matches_the_catalogue() -> None:
    arguments = {"query": "casillas", "modelo": "303", "period": "3T"}
    with_pin = read_pinned_reference(lambda operation: catalogue.list_casillas("303", period="3T", operation=operation))
    expected = [row.model_dump(mode="json") for row in with_pin.report.rows]

    pages = list(_pages(arguments))
    served = [row for page in pages for row in page["report"]["rows"]]

    assert len(pages) > 1
    assert all(page["logical_generation"] == with_pin.generation.logical_generation for page in pages)
    assert [page["paging"]["offset"] for page in pages] == [
        sum(len(earlier["report"]["rows"]) for earlier in pages[:index]) for index in range(len(pages))
    ]
    assert pages[0]["paging"]["total"] == len(expected) == with_pin.report.casilla_count
    assert [row["casilla_id"] for row in served] == [row["casilla_id"] for row in expected]
    summary = (
        "casilla_id",
        "number",
        "label",
        "input_kind",
        "required",
        "data_type",
        "binding",
        "formula",
        "form_number",
    )
    assert served == [_only(row, summary) for row in expected]
    assert all("help_text" not in row and "legal_refs" not in row for row in served)


def test_a_casilla_read_gives_the_detail_a_summary_row_leaves_out() -> None:
    arguments = {"query": "casillas", "modelo": "303", "period": "3T", "casilla_number": "28"}
    (summary,) = _rows(arguments, "rows")

    detail = authority_query({"query": "casilla", "modelo": "303", "period": "3T", "casilla": summary["casilla_id"]})
    expected = read_pinned_reference(
        lambda operation: catalogue.describe_casilla("303", summary["casilla_id"], period="3T", operation=operation)
    ).report.model_dump(mode="json")

    assert "paging" not in detail
    assert detail["report"] == expected
    assert detail["report"]["help_text"] and detail["report"]["legal_refs"]


def test_formulas_page_as_summaries_whose_expression_is_read_through_their_target_casilla() -> None:
    rows = _rows({"query": "formulas", "modelo": "303", "period": "3T"}, "rows")
    full = read_pinned_reference(
        lambda operation: catalogue.list_formulas("303", period="3T", operation=operation)
    ).report

    expected = [formula.model_dump(mode="json") for formula in full.rows]
    summary = (
        "formula_id",
        "target_casilla_id",
        "input_casilla_ids",
        "input_bindings",
        "input_parameters",
        "input_relations",
    )
    assert rows == [_only(formula, summary) for formula in expected]
    assert all("expression" not in row and "legal_refs" not in row for row in rows)
    for row, formula in zip(rows, expected, strict=True):
        detail = authority_query(
            {"query": "casilla", "modelo": "303", "period": "3T", "casilla": row["target_casilla_id"]}
        )
        assert detail["report"]["formula_id"] == formula["formula_id"]
        assert detail["report"]["formula_expression"] == formula["expression"]


def test_limit_shortens_a_page_and_the_cursors_still_cover_every_row() -> None:
    whole = _rows({"query": "modelos"}, "modelos")

    small = list(_pages({"query": "modelos", "limit": 7}))

    assert all(page["paging"]["returned"] <= 7 for page in small)
    assert [row for page in small for row in page["report"]["modelos"]] == whole
    assert len(small) == -(-len(whole) // 7)


@pytest.mark.parametrize(
    ("arguments", "member"),
    (
        ({"query": "modelos"}, "modelos"),
        ({"query": "modelos", "domain": "iva"}, "modelos"),
        ({"query": "portals"}, "rows"),
        ({"query": "portals", "category": "filing"}, "rows"),
        ({"query": "bindings", "modelo": "303", "filing_year": 2025}, "rows"),
    ),
    ids=("modelos", "modelos-domain", "portals", "portals-category", "bindings"),
)
def test_every_other_list_pages_to_the_rows_the_catalogue_holds(arguments: dict[str, Any], member: str) -> None:
    rows = _rows(arguments, member)
    first = authority_query(arguments)["report"]

    assert rows
    if member == "modelos":
        assert first["modelo_count"] == len(rows)
    elif arguments["query"] == "portals":
        assert first["count"] == len(rows) == len({row["portal"] for row in rows})
    else:
        assert len({row["binding_id"] for row in rows}) == len(rows)


def test_support_unnarrowed_pages_one_summary_per_modelo_with_its_renames_counted() -> None:
    full = read_pinned_reference(lambda operation: catalogue.read_support_matrix(operation=operation)).report

    entries = _rows({"query": "support"}, "entries")

    assert [entry["modelo_id"] for entry in entries] == [entry.modelo_id for entry in full.entries]
    assert [entry["rename_count"] for entry in entries] == [len(entry.renames) for entry in full.entries]
    assert all("renames" not in entry for entry in entries)
    assert "pass modelo" in authority_query({"query": "support"})["paging"]["detail"]


def test_support_narrowed_by_modelo_pages_that_modelos_renames() -> None:
    full = read_pinned_reference(lambda operation: catalogue.read_support_matrix(operation=operation)).report
    widest = max(full.entries, key=lambda entry: len(entry.renames))
    assert encoded_size(widest.model_dump(mode="json")) > REPLY_BYTES, "no modelo's renames exceed one reply"

    arguments = {"query": "support", "modelo": widest.modelo_id}
    pages = list(_pages(arguments))

    assert len(pages) > 1
    for page in pages:
        (entry,) = page["report"]["entries"]
        assert entry["modelo_id"] == widest.modelo_id and entry["rename_count"] == len(widest.renames)
        assert "renames" not in entry
    served = [rename for page in pages for rename in page["report"]["renames"]]
    assert served == [rename.model_dump(mode="json") for rename in widest.renames]

    small = authority_query({"query": "support", "modelo": " 303 "})
    assert [entry["modelo_id"] for entry in small["report"]["entries"]] == ["303"]
    assert small["paging"]["next_cursor"] is None


def test_support_for_a_modelo_the_matrix_lacks_is_refused_with_the_reason() -> None:
    refused = authority_query({"query": "support", "modelo": "NOT-A-MODELO"})

    assert refused["outcome"] == "refused" and refused["code"] == "invalid_request"
    assert "NOT-A-MODELO" in refused["message"]


@pytest.mark.parametrize(
    "arguments",
    (
        {"query": "casillas", "modelo": "303", "period": "3T", "cursor": 10_000},
        {"query": "modelos", "cursor": 10_000},
        {"query": "casilla", "modelo": "303", "period": "3T", "casilla": "01", "cursor": 1},
    ),
    ids=("past-the-last-row", "modelos-past-the-last-row", "a-casilla-that-fits-takes-no-cursor"),
)
def test_a_cursor_that_names_nothing_is_refused_not_answered_empty(arguments: dict[str, Any]) -> None:
    refused = authority_query(arguments)

    assert refused["outcome"] == "refused" and refused["code"] == "invalid_request"
    assert "cursor" in refused["message"]


def test_an_empty_list_is_one_empty_page_without_a_next() -> None:
    reply = authority_query({"query": "casillas", "modelo": "303", "period": "3T", "casilla_number": "NO-SUCH"})

    assert reply["report"]["rows"] == [] and reply["report"]["casilla_count"] == 0
    assert reply["paging"]["total"] == reply["paging"]["returned"] == 0
    assert reply["paging"]["next_cursor"] is None and "next_call" not in reply["paging"]


def test_a_formula_expression_too_long_for_one_reply_is_served_in_windows_that_join_to_it() -> None:
    full = read_pinned_reference(lambda operation: catalogue.list_formulas("100", operation=operation)).report
    formulas = [formula.model_dump(mode="json") for formula in full.rows]
    longest = max(formulas, key=lambda formula: encoded_size(formula["expression"]))
    assert encoded_size(longest["expression"]) > 3 * REPLY_BYTES, "no formula expression is long"
    arguments = {"query": "casilla", "modelo": "100", "casilla": longest["target_casilla_id"]}

    pages = list(_pages(arguments))

    assert len(pages) > 3
    joined = "".join(page["report"]["formula_expression_json"] for page in pages)
    assert joined == canonical_json_bytes(longest["expression"]).decode()
    assert json.loads(joined) == longest["expression"]
    assert all("formula_expression" not in page["report"] for page in pages)
    assert {page["report"]["formula_id"] for page in pages} == {longest["formula_id"]}
    assert pages[0]["paging"]["total"] == len(joined)
    assert [page["paging"]["offset"] for page in pages] == [
        sum(page["paging"]["returned"] for page in pages[:index]) for index in range(len(pages))
    ]


def test_the_tool_declares_how_to_page_and_its_schema_bounds_the_arguments() -> None:
    tools = {name: (description, schema) for name, description, schema in MCP_TOOL_CATALOGUE}
    description, schema = tools["authority"]

    assert schema["properties"]["limit"] == {"type": "integer", "minimum": 1, "maximum": ROWS_MAX}
    assert schema["properties"]["cursor"] == {"type": "integer", "minimum": 0}
    assert "next_cursor" in description and "casilla" in description and "windows" in description
    corpus_description, corpus_schema = tools["corpus_search"]
    assert corpus_schema["properties"]["cursor"] == {"type": "integer", "minimum": 0}
    assert "next_cursor" in corpus_description
    validate_tool_arguments("authority", {"query": "modelos", "limit": ROWS_MAX, "cursor": 3})
    refusals: tuple[dict[str, object], ...] = (
        {"query": "modelos", "limit": 0},
        {"query": "modelos", "limit": ROWS_MAX + 1},
        {"query": "modelos", "cursor": -1},
    )
    for refused in refusals:
        with pytest.raises(ValueError, match="invalid tool field"):
            validate_tool_arguments("authority", refused)


@pytest.mark.parametrize(
    "arguments",
    (
        {"query": "describe", "modelo": "303", "limit": 5},
        {"query": "categories", "cursor": 1},
        {"query": "casilla", "modelo": "303", "casilla": "01", "limit": 5},
        {"query": "portal", "portal": "x", "cursor": 1},
    ),
    ids=("describe", "categories", "casilla", "portal"),
)
def test_a_query_that_is_not_a_list_takes_no_limit_and_a_whole_answer_takes_no_cursor(
    arguments: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match="invalid authority query coordinates"):
        authority_query(arguments)


@pytest.mark.anyio
async def test_the_wire_serves_a_page_whose_text_block_is_within_the_bound() -> None:
    adapter = admitted_adapter()
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            first = await client.call_tool("authority", {"query": "casillas", "modelo": "303", "period": "3T"})
            assert first.structured_content is not None
            paging = first.structured_content["paging"]
            second = await client.call_tool("authority", paging["next_call"]["arguments"])
            refused = await client.call_tool("authority", {"query": "modelos", "limit": ROWS_MAX + 1})
    finally:
        await adapter.close()

    assert first.is_error is False and second.is_error is False
    for result in (first, second):
        (block,) = result.content
        assert isinstance(block, TextContent) and len(block.text.encode()) <= REPLY_BYTES
    assert second.structured_content is not None and second.structured_content["paging"]["offset"] == paging["returned"]
    assert refused.is_error is True and refused.structured_content == {"outcome": "refused", "code": "invalid_request"}
