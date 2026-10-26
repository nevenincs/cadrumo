"""View links spell, parse and resolve exactly as the shared conformance vectors say.

The vectors file is read by the window's implementation of the same grammar
too, so a case here is a case both implementations must agree on.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ..navigation import (
    MAX_VIEW_LINK_LENGTH,
    NavigationSurface,
    SurfaceImplementation,
    ViewLink,
    ViewLinkRefused,
    ViewOpened,
    ViewRefused,
    load_navigation_register,
    parse_view_link,
    resolve_view,
    view_link,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_VECTORS: dict[str, Any] = json.loads((Path(__file__).parent / "navigation_vectors.json").read_text(encoding="utf-8"))
_INVOICE = "fedcba9876543210" * 4


def _surface(value: str | None) -> NavigationSurface | None:
    return None if value is None else NavigationSurface(value)


def _pairs(params: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(params.items()))


def _request(case: dict[str, Any]) -> ViewLink:
    return ViewLink(view_id=case["view_id"], params=_pairs(case["params"]), prefer=_surface(case["prefer"]))


def _implemented(value: dict[str, Any] | None) -> dict[NavigationSurface, SurfaceImplementation] | None:
    if value is None:
        return None
    return {
        NavigationSurface(surface): SurfaceImplementation(
            views=frozenset(entry["views"]),
            params={view: frozenset(names) for view, names in entry["params"].items()},
        )
        for surface, entry in value.items()
    }


def test_vectors_cover_every_refusal_and_fallback() -> None:
    refusals = {case["expect"]["refused"] for case in _VECTORS["parse"] if "refused" in case["expect"]}
    assert refusals == {
        "too_long",
        "malformed",
        "uppercase",
        "not_a_view_link",
        "credentials",
        "percent_encoding",
        "fragment",
        "query",
        "too_many_segments",
        "unknown_view",
        "unknown_param",
        "param_not_accepted",
        "param_malformed",
    }
    outcomes = {case["expect"].get("fallback", case["expect"].get("refused")) for case in _VECTORS["resolve"]}
    assert outcomes == {
        "none",
        "other_surface",
        "ancestor",
        "not_implemented",
        "unknown_view",
        "unknown_param",
        "param_not_accepted",
        "param_malformed",
    }


@pytest.mark.parametrize("case", _VECTORS["format"], ids=lambda case: case["link"][:60])
def test_format_vector(case: dict[str, Any]) -> None:
    request = _request(case)
    assert view_link(request.view_id, dict(request.params), request.prefer) == case["link"]
    assert parse_view_link(case["link"]) == request


@pytest.mark.parametrize("case", _VECTORS["parse"], ids=lambda case: repr(case["link"][:60]))
def test_parse_vector(case: dict[str, Any]) -> None:
    expect = case["expect"]
    parsed = parse_view_link(case["link"])
    if "refused" in expect:
        assert isinstance(parsed, ViewLinkRefused)
        assert parsed.reason.value == expect["refused"]
    else:
        assert parsed == _request(expect)


@pytest.mark.parametrize("case", _VECTORS["resolve"], ids=lambda case: json.dumps(case["link"])[:80])
def test_resolve_vector(case: dict[str, Any]) -> None:
    expect = case["expect"]
    outcome = resolve_view(_request(case["link"]), _implemented(case["implemented"]))
    if "refused" in expect:
        assert isinstance(outcome, ViewRefused)
        assert outcome.reason == expect["refused"]
        return
    assert isinstance(outcome, ViewOpened)
    assert (outcome.opened, outcome.surface.value, outcome.fallback, outcome.params, outcome.notice_due) == (
        expect["opened"],
        expect["surface"],
        expect["fallback"],
        _pairs(expect["params"]),
        expect["notice"],
    )


def test_every_registered_view_round_trips_on_both_preferences() -> None:
    register = load_navigation_register()
    for element in register.elements:
        for prefer in (None, *NavigationSurface):
            link = view_link(element.id, prefer=prefer)
            assert len(link) <= MAX_VIEW_LINK_LENGTH
            assert parse_view_link(link) == ViewLink(view_id=element.id, prefer=prefer)


def test_the_formatter_refuses_what_the_parser_would() -> None:
    with pytest.raises(ValueError, match="unknown_view"):
        view_link("nowhere")
    with pytest.raises(ValueError, match="param_not_accepted"):
        view_link("calendar", {"select": _INVOICE})
    with pytest.raises(ValueError, match="unknown_param"):
        view_link("ledger/invoices", {"focus": _INVOICE})
    with pytest.raises(ValueError, match="param_malformed"):
        view_link("ledger/invoices", {"select": "F-0001-2026"})


def test_a_hand_built_request_breaking_the_register_is_refused() -> None:
    request = ViewLink(view_id="profile", params=(("select", _INVOICE),))
    assert resolve_view(request) == ViewRefused(requested=request, reason="param_not_accepted")
