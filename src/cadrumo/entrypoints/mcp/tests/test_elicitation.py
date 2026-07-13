"""Tests for the elicitation-backed CONFIRM tier and its degradation matrix.

Pure SDK-independent logic over ``_elicitation.py``: the (policy, handoff, client)
degradation matrix, the fail-closed decision mapping, and the argument-free,
localized request payload. User-facing strings flow through ``tr()`` (default
locale), so the assertions check command interpolation and payload structure, not
hardcoded prose.
"""

from __future__ import annotations

from collections.abc import Mapping

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


def test_no_channel_refusal_names_the_canonical_product_cli() -> None:
    no_channel = refusal_message(ConfirmRoute.REFUSE_NO_CHANNEL, command_key=_HANDOFF)

    assert "Cadrumo CLI" in no_channel
    assert "aeat CLI" not in no_channel


# --- H8: no secret ever rides an MCP elicitation channel -------------------
#
# The policy records the decided stance: secrets
# (certificate passphrases, tokens, API keys, PINs) are entered ONLY through the
# local CLI (`aeat config auth certificate secret set`) into encrypted storage;
# no secret ever rides any MCP channel, form or URL. The console's sole
# elicitation payload is ``confirmation_request``, which asks exactly one boolean
# ``confirm`` field. This gate asserts that stance and locks it: a secret-like
# field in an elicitation schema would fail here.

# Field-name fragments that name a secret. ``token``/``pin`` are matched as whole
# underscore-delimited segments to avoid substring false positives (e.g. "pin"
# inside "mapping"); the rest are unambiguous enough to substring-match.
_SECRET_SUBSTRINGS = (
    "password",
    "passphrase",
    "secret",
    "api_key",
    "apikey",
    "private_key",
    "privatekey",
    "credential",
    "certificate",
)
_SECRET_SEGMENTS = frozenset({"token", "pin", "pwd", "cert", "otp", "key"})


def _name_requests_secret(name: str) -> bool:
    """True when a field name names a secret the MCP channel must never collect."""
    lowered = name.lower()
    if any(fragment in lowered for fragment in _SECRET_SUBSTRINGS):
        return True
    segments = {segment for segment in lowered.replace("-", "_").split("_") if segment}
    return bool(segments & _SECRET_SEGMENTS)


def _schema_field_names(schema: Mapping[str, object]) -> set[str]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return set()
    return {str(name) for name in properties}


def _schema_requests_secret(schema: Mapping[str, object]) -> bool:
    return any(_name_requests_secret(name) for name in _schema_field_names(schema))


def test_confirmation_schema_asks_only_a_boolean_and_no_secret() -> None:
    # The one elicitation schema the console can emit asks a single boolean
    # confirm field — never a password, passphrase, token, API key, or PIN.
    for command_key in (_HANDOFF, _NON_HANDOFF_DESTRUCTIVE, "ledger.add"):
        schema = confirmation_request(command_key=command_key).requested_schema
        assert _schema_field_names(schema) == {"confirm"}
        properties = schema.get("properties")
        assert isinstance(properties, dict)
        confirm_field = properties.get("confirm")
        assert isinstance(confirm_field, dict)
        assert confirm_field.get("type") == "boolean"
        assert not _schema_requests_secret(schema), f"{command_key} elicitation schema requests a secret-like field"


def test_secret_detector_flags_credential_fields() -> None:
    # Anti-tautology negative control: the detector DOES fire on secret-like
    # fields, so the assertion above would fail the moment an elicitation schema
    # tried to collect one. Proves the H8 gate has teeth.
    for secret_name in (
        "password",
        "passphrase",
        "api_key",
        "apikey",
        "auth_token",
        "certificate_pin",
        "card_pin",
        "otp",
        "cert_password",
    ):
        assert _name_requests_secret(secret_name), f"detector missed secret field {secret_name!r}"
    # And it does not false-fire on the real, innocuous confirm field or on plain
    # non-secret field names.
    for benign_name in ("confirm", "mapping", "period", "modelo", "amount"):
        assert not _name_requests_secret(benign_name), f"detector false-flagged {benign_name!r}"

    secret_schema = {
        "type": "object",
        "properties": {"passphrase": {"type": "string"}},
        "required": ["passphrase"],
    }
    assert _schema_requests_secret(secret_schema)
