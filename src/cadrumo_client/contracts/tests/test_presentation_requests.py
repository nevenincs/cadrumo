"""A TUI view request names a register view some TUI implements, with only the parameters that element declares."""

from __future__ import annotations

from uuid import uuid4

import pytest

from ..navigation import NavigationSurface, load_navigation_register
from ..presentation import PresentationRequest, presentation_refusal
from ..session_events import PresentationRequested

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TRANSACTION = "a" * 64


def test_every_tui_view_of_the_register_may_be_asked_for() -> None:
    register = load_navigation_register()
    tui_views = register.ids_for(NavigationSurface.TUI)
    assert {"profile/aeat-access", "aeat-sync", "ledger"} <= tui_views
    for view_id in tui_views:
        assert presentation_refusal(view_id, {}) is None, view_id


def test_a_declared_parameter_with_a_value_of_its_kind_may_be_asked_for() -> None:
    assert presentation_refusal("ledger", {"select": _TRANSACTION}) is None


@pytest.mark.parametrize(
    ("destination", "params", "reason"),
    [
        ("ledger/invoices", {}, "not_a_tui_view"),
        ("calendar", {}, "not_a_tui_view"),
        ("nowhere", {}, "not_a_tui_view"),
        ("aeat_sync", {}, "not_a_tui_view"),
        ("workbench.ledger", {}, "not_a_tui_view"),
        ("ledger", {"focus": _TRANSACTION}, "unknown_param"),
        ("profile", {"select": _TRANSACTION}, "param_not_accepted"),
        ("ledger", {"select": "A" * 64}, "param_malformed"),
        ("ledger", {"select": "a" * 63}, "param_malformed"),
    ],
)
def test_a_view_no_tui_implements_or_a_parameter_the_element_refuses_is_named(
    destination: str, params: dict[str, str], reason: str
) -> None:
    assert presentation_refusal(destination, params) == reason


@pytest.mark.parametrize(
    "fields",
    [
        {"destination": "ledger/movements"},
        {"destination": "aeat_auth"},
        {"destination": "ledger", "params": {"select": "not-a-transaction"}},
        {"destination": "home", "params": {"select": _TRANSACTION}},
    ],
)
def test_neither_the_request_nor_the_relayed_event_decodes_a_refused_view(fields: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="TUI view request"):
        PresentationRequest.model_validate(
            {"request_id": uuid4(), "profile_id": uuid4(), "session_id": uuid4(), **fields}
        )
    with pytest.raises(ValueError, match="TUI view request"):
        PresentationRequested.model_validate(
            {
                "runtime_boot_id": uuid4(),
                "connection_id": uuid4(),
                "profile_id": uuid4(),
                "session_id": uuid4(),
                **fields,
            }
        )


def test_the_wire_names_the_view_and_its_parameters() -> None:
    request = PresentationRequest(
        request_id=uuid4(),
        profile_id=uuid4(),
        session_id=uuid4(),
        destination="ledger",
        params={"select": _TRANSACTION},
    )
    wire = request.model_dump(mode="json")
    assert (wire["action"], wire["destination"], wire["params"]) == (
        "present_destination",
        "ledger",
        {"select": _TRANSACTION},
    )
    bare = PresentationRequest.model_validate_json(
        f'{{"request_id":"{uuid4()}","profile_id":"{uuid4()}","session_id":"{uuid4()}",'
        '"destination":"profile/aeat-access"}'
    )
    assert bare.params == {}
