"""Tests for the elicitation-backed CONFIRM tier and its degradation matrix.

Pure SDK-independent logic over ``_elicitation.py``: the (policy, handoff, client)
degradation matrix, the fail-closed decision mapping, and the argument-free,
localized request payload. User-facing strings flow through ``tr()`` (default
locale), so the assertions check command interpolation and payload structure, not
hardcoded prose.
"""

from __future__ import annotations

import pytest

from .._elicitation import (
    ConfirmDecision,
    ConfirmRoute,
    confirmation_request,
    decision_from_elicitation,
    refusal_message,
    resolve_confirm_route,
)
from .._hitl import ConfirmationPolicy

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_HANDOFF = "modelo.export"
_NON_HANDOFF_DESTRUCTIVE = "ledger.remove"


def test_block_always_refuses_regardless_of_client() -> None:
    for supports in (True, False):
        route = resolve_confirm_route(
            policy=ConfirmationPolicy.BLOCK,
            command_key="modelo.work.submit",
            client_supports_elicitation=supports,
        )
        assert route is ConfirmRoute.REFUSE_BLOCKED


def test_auto_approve_passes() -> None:
    route = resolve_confirm_route(
        policy=ConfirmationPolicy.AUTO_APPROVE,
        command_key="overview.status",
        client_supports_elicitation=False,
    )
    assert route is ConfirmRoute.AUTO


def test_confirm_with_elicitation_elicits() -> None:
    for command_key in (_HANDOFF, _NON_HANDOFF_DESTRUCTIVE):
        route = resolve_confirm_route(
            policy=ConfirmationPolicy.CONFIRM,
            command_key=command_key,
            client_supports_elicitation=True,
        )
        assert route is ConfirmRoute.ELICIT


def test_confirm_without_elicitation_refuses_handoff_but_hints_otherwise() -> None:
    # Fail-closed at the irreversible boundary; degrade to the client's own
    # destructiveHint UI everywhere else.
    handoff = resolve_confirm_route(
        policy=ConfirmationPolicy.CONFIRM,
        command_key=_HANDOFF,
        client_supports_elicitation=False,
    )
    assert handoff is ConfirmRoute.REFUSE_NO_CHANNEL
    non_handoff = resolve_confirm_route(
        policy=ConfirmationPolicy.CONFIRM,
        command_key=_NON_HANDOFF_DESTRUCTIVE,
        client_supports_elicitation=False,
    )
    assert non_handoff is ConfirmRoute.CLIENT_HINT


def test_decision_maps_fail_closed_on_every_non_accepted_yes() -> None:
    assert decision_from_elicitation(action="accept", content={"confirm": True}) is ConfirmDecision.PROCEED
    # Accepted the form but answered no.
    assert (
        decision_from_elicitation(action="accept", content={"confirm": False}) is ConfirmDecision.REFUSED_NOT_CONFIRMED
    )
    # Malformed accept: missing field, or no content at all.
    assert decision_from_elicitation(action="accept", content={}) is ConfirmDecision.REFUSED_NOT_CONFIRMED
    assert decision_from_elicitation(action="accept", content=None) is ConfirmDecision.REFUSED_NOT_CONFIRMED
    # A non-boolean-true value never proceeds.
    assert (
        decision_from_elicitation(action="accept", content={"confirm": "true"}) is ConfirmDecision.REFUSED_NOT_CONFIRMED
    )
    assert decision_from_elicitation(action="decline", content=None) is ConfirmDecision.REFUSED_DECLINED
    assert decision_from_elicitation(action="cancel", content=None) is ConfirmDecision.REFUSED_CANCELLED
    # An unknown action fails closed to a decline, never a proceed.
    assert decision_from_elicitation(action="something-else", content=None) is ConfirmDecision.REFUSED_DECLINED


def test_request_payload_is_argument_free_and_interpolates_the_command() -> None:
    request = confirmation_request(command_key=_HANDOFF)
    # The requested schema is exactly one boolean confirm field - no argument
    # values, figures, or taxpayer data (the MCP-spec sensitive-data constraint).
    properties = request.requested_schema["properties"]
    assert isinstance(properties, dict)
    typed_properties: dict[str, object] = {str(key): value for key, value in properties.items()}
    assert set(typed_properties) == {"confirm"}
    confirm_property = typed_properties["confirm"]
    assert isinstance(confirm_property, dict)
    typed_confirm_property: dict[str, object] = {str(key): value for key, value in confirm_property.items()}
    assert typed_confirm_property["type"] == "boolean"
    assert request.requested_schema["required"] == ["confirm"]
    # The command is interpolated into the localized message (not hardcoded prose).
    assert _HANDOFF in request.message


def test_request_consequence_differs_between_handoff_and_local_verbs() -> None:
    handoff = confirmation_request(command_key=_HANDOFF)
    local = confirmation_request(command_key="ledger.add")
    assert handoff.message != local.message
    assert _HANDOFF in handoff.message
    assert "ledger.add" in local.message


def test_refusal_messages_interpolate_the_command() -> None:
    blocked = refusal_message(ConfirmRoute.REFUSE_BLOCKED, command_key="modelo.work.submit")
    no_channel = refusal_message(ConfirmRoute.REFUSE_NO_CHANNEL, command_key=_HANDOFF)
    assert "modelo.work.submit" in blocked
    assert _HANDOFF in no_channel
    assert blocked != no_channel
