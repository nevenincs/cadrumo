"""Finding and describing operations through MCP, with a session and without one, against the real runtime.

The adapter, the installed client it opens, the native transport, the runtime,
the session authority, the profile worker and the stored sign-in are real. The
native login the runtime observes, the keychain holding the proof and the
runtime's wall clock are ports held by the test. What every answer is held to
is the production registry's own description of the operation, which is what
the runtime serves a session and what the shipped contracts are rendered from.
"""

from __future__ import annotations

import json
import sys
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1, OperationRegistry
from cadrumo.application.user_profile.access_contracts import ProfileAccessStatus
from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_PATCH_OPERATION_DEFINITION_ID
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import canonical_json_bytes
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


async def _discover(adapter: RuntimeMcpAdapter) -> dict[str, dict[str, Any]]:
    """Make the same discovery calls, whatever session the adapter holds."""
    return {
        "ranked": await adapter.call("search", {"query": _READ, "limit": 3}),
        "family": await adapter.call("search", {"family": "auth", "limit": 200}),
        "read": await adapter.call("describe", {"definition_id": _READ}),
        "patch": await adapter.call("describe", {"definition_id": _PATCH}),
        "unregistered": await adapter.call("describe", {"definition_id": _UNREGISTERED}),
    }


@pytest.mark.anyio
async def test_with_nobody_signed_in_operations_are_found_and_described_and_the_runtime_admits_nobody(
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
            private = await adapter.call("execute", {"definition_id": _READ, "payload": {}})
        finally:
            await adapter.close()

        assert (status["session"], status["denial"]) == ("none", "authentication_required")
        assert all(answers[name]["session"] == "none" for name in ("ranked", "family", "read", "patch"))
        assert answers["ranked"]["operations"][0]["definition_id"] == _READ
        registered = sorted(
            contract.definition_id
            for contract in _registry().public_contract_set.definitions
            if contract.definition_id.startswith("auth.")
        )
        assert len(registered) > 1
        # Every registered operation of the family, where a session would see those in its scope.
        assert [row["definition_id"] for row in answers["family"]["operations"]] == registered
        assert _described(answers["read"]) == _registry().describe_public_definition(_READ)
        assert _described(answers["patch"]) == _registry().describe_public_definition(_PATCH)
        assert answers["patch"]["payload_vocabulary"]["questions"]
        assert answers["unregistered"] == {"outcome": "refused", "code": "operation_denied"}
        assert private == {"outcome": "refused", "code": "authentication_required"}
        # Reading what exists presented no proof and was given no lease.
        assert runtime.profiles.logins == [] and runtime.leases() == ()
        assert adapter.client is None


@pytest.mark.anyio
async def test_under_a_session_the_runtime_answers_and_the_descriptions_are_the_ones_read_without_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        # A connection started for a key it was never given resumes no sign-in, so it holds no session.
        unadmitted = RuntimeMcpAdapter(profile_id=runtime.profile_id, client=None)
        try:
            before = await _discover(unadmitted)
        finally:
            await unadmitted.close()
        assert runtime.profiles.logins == [] and unadmitted.client is None
        adapter = _adapter()
        try:
            status = await adapter.call("status", {})
            under = await _discover(adapter)
        finally:
            await adapter.close()

    assert status["session"] == "sign_in"
    scope = ProfileAccessStatus.model_validate_json(canonical_json_bytes(status["status"])).effective_scope
    # A session's reply is the runtime's and says nothing of a session: it has one.
    assert all("session" not in answer for answer in under.values())
    assert set(under["read"]) == {"outcome", "description"}
    assert set(under["patch"]) == {"outcome", "description", "payload_vocabulary"}
    assert under["ranked"]["operations"][0]["definition_id"] == _READ
    listed = [row["definition_id"] for row in under["family"]["operations"]]
    assert listed == sorted(item for item in scope.operations if item.startswith("auth."))
    assert set(listed) <= {row["definition_id"] for row in before["family"]["operations"]}
    for name, definition_id in (("read", _READ), ("patch", _PATCH)):
        assert _described(under[name]) == _registry().describe_public_definition(definition_id)
        assert _described(before[name]) == _described(under[name])
    assert before["patch"]["payload_vocabulary"] == under["patch"]["payload_vocabulary"]
    assert under["unregistered"] == before["unregistered"] == {"outcome": "refused", "code": "operation_denied"}
