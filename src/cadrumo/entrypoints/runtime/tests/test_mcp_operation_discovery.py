"""Finding and describing operations through MCP: under a session the runtime answers, and without one nothing does.

The adapter, the installed client it opens, the native transport, the runtime,
the session authority, the profile worker and the stored sign-in are real. The
native login the runtime observes, the keychain holding the proof and the
runtime's wall clock are ports held by the test. What every answer is held to
is the production registry's own description of the operation, which is what
the runtime serves a session. An agent works only inside the profile the person
signed in to, so with nobody signed in discovery is refused like every call but
status, with the remedy that sends the agent to the person.
"""

from __future__ import annotations

import json
import sys
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.operations.person_acts import operation_is_persons_act
from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1, OperationRegistry
from cadrumo.application.user_profile.access_contracts import ProfileAccessStatus
from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_PATCH_OPERATION_DEFINITION_ID
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo_harness.mcp.protocol_contract import SIGN_IN_REMEDY
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter

from ...operation_composition import build_production_operation_registry
from .stored_sign_in_runtime import stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_READ = AUTH_READ_OPERATION_DEFINITION_ID
_PATCH = PROFILE_PATCH_OPERATION_DEFINITION_ID
_UNREGISTERED = "auth.synthetic-unregistered"


@cache
def _registry() -> OperationRegistry:
    return build_production_operation_registry()


def _adapter() -> RuntimeMcpAdapter:
    """An adapter started with no credential reference and no profile named."""
    return RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)


def _described(reply: dict[str, Any]) -> OperationPublicDefinitionDescriptionV1:
    """Read a ``describe`` reply's description as the typed description it is the public value of."""
    assert reply["outcome"] == "described", reply
    return OperationPublicDefinitionDescriptionV1.model_validate_json(json.dumps(reply["description"]))


def _persons_act(definition_id: str) -> bool:
    contract = _registry().describe_public_definition(definition_id).contract
    return operation_is_persons_act(definition_id, ephemeral_secret_required=contract.ephemeral_secret_required)


async def _ranked(adapter: RuntimeMcpAdapter, args: dict[str, Any]) -> dict[str, Any]:
    """Search by query as an agent does: a search that ran out of time resumes from the contracts it read."""
    for _attempt in range(10):
        reply = await adapter.call("search", args)
        if reply.get("code") != "runtime_deadline_exceeded":
            return reply
    return reply


async def _discover(adapter: RuntimeMcpAdapter) -> dict[str, dict[str, Any]]:
    """Make the same discovery calls, whatever session the adapter holds."""
    return {
        "ranked": await _ranked(adapter, {"query": _READ, "limit": 3}),
        "family": await adapter.call("search", {"family": "auth", "limit": 200}),
        "read": await adapter.call("describe", {"definition_id": _READ}),
        "patch": await adapter.call("describe", {"definition_id": _PATCH}),
        "unregistered": await adapter.call("describe", {"definition_id": _UNREGISTERED}),
    }


@pytest.mark.anyio
async def test_with_nobody_signed_in_discovery_is_refused_and_the_runtime_admits_nobody(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=False) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            status = await adapter.call("status", {})
            answers = await _discover(adapter)
        finally:
            await adapter.close()

        assert (status["session"], status["denial"]) == ("none", "authentication_required")
        assert status["remedy"] == SIGN_IN_REMEDY
        for name, answer in answers.items():
            assert answer == {
                "outcome": "refused",
                "code": "authentication_required",
                "sign_in_reason": "absent",
                "remedy": SIGN_IN_REMEDY,
            }, name
        # Nothing was presented and no lease was given.
        assert runtime.profiles.logins == [] and runtime.leases() == ()
        assert adapter.client is None


@pytest.mark.anyio
async def test_under_a_session_the_runtime_answers_with_the_registrys_descriptions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            status = await adapter.call("status", {})
            under = await _discover(adapter)
        finally:
            await adapter.close()

    assert status["session"] == "sign_in"
    scope = ProfileAccessStatus.model_validate_json(canonical_json_bytes(status["status"])).effective_scope
    assert all("session" not in answer for answer in under.values())
    assert set(under["read"]) == {"outcome", "description"}
    assert set(under["patch"]) == {"outcome", "description", "payload_vocabulary"}
    assert under["ranked"]["operations"][0]["definition_id"] == _READ
    listed = [row["definition_id"] for row in under["family"]["operations"]]
    # Every operation of the family in scope, except the person's own acts, which no agent is offered.
    assert listed == sorted(item for item in scope.operations if item.startswith("auth.") and not _persons_act(item))
    assert len(listed) < len([item for item in scope.operations if item.startswith("auth.")])
    for name, definition_id in (("read", _READ), ("patch", _PATCH)):
        assert _described(under[name]) == _registry().describe_public_definition(definition_id)
    assert under["patch"]["payload_vocabulary"]["questions"]
    assert under["unregistered"] == {"outcome": "refused", "code": "operation_denied"}
