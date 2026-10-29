"""Shared actual CLI-adjacent TUI, MCP and native protected-read probes."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import suppress
from typing import Any, cast
from uuid import uuid4

from mcp import ClientSession

from cadrumo.application.auth.auth_read_contracts import AuthReadProjection
from cadrumo.application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicTerminalEventV1,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    ProfileMutationOperationProjection,
)
from cadrumo.application.user_profile.view_operation import (
    PROFILE_VIEW_OPERATION_DEFINITION_ID,
    ProfileViewFactItem,
    ProfileViewOperationProjection,
    ProfileViewPageKind,
)
from cadrumo.core.operations import profile_operation_subject

from .harness import LifecycleHarness, Profile
from .proof_support import ProcessIdentity, verified_relay
from .session_holder import AsyncRuntimeSessionHolder


async def call_mcp(
    client: ClientSession, name: str, arguments: dict[str, Any], *, admitted: bool = True
) -> dict[str, Any]:
    """Call one MCP tool and check the expected admission outcome."""
    reply = await client.call_tool(name, arguments)
    if not (isinstance(reply.structured_content, dict)):
        raise AssertionError("Protected application probe failed")
    document = cast(dict[str, Any], reply.structured_content)
    if not (reply.is_error is not admitted):
        raise AssertionError(
            f"MCP {name} admission differed: {document.get('outcome', 'unreported')} "
            f"{document.get('code', 'unreported')}"
        )
    if not admitted and not (document["outcome"] == "refused" and isinstance(document["code"], str)):
        raise AssertionError("Protected application probe failed")
    return document


async def _mcp_settle(
    client: ClientSession,
    profile: Profile,
    definition_id: str,
    payload: dict[str, Any],
    *,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Run one operation over MCP to a successful terminal and return its released projection."""
    described = await call_mcp(client, "describe", {"definition_id": definition_id})
    contract = described["description"]["contract"]
    request: dict[str, Any] = {
        "definition_id": definition_id,
        "subject_ref": profile_operation_subject(str(profile.profile_id)),
        "payload": payload,
    }
    if idempotency_key is not None:
        request["idempotency_key"] = idempotency_key
    submitted = await call_mcp(client, "execute", request)
    operation_id = submitted["receipt"]["operation_id"]
    deadline = time.monotonic() + 60
    while True:
        observed = await call_mcp(
            client, "observe", {"observation": {"operation_id": operation_id, "after_cursor": 0, "page_limit": 32}}
        )
        observation = OperationObservationSuccessV1.model_validate_json(json.dumps(observed["reply"]["observation"]))
        projection = observation.projection
        if projection.lifecycle.value == "terminal":
            break
        if not (time.monotonic() < deadline):
            raise AssertionError("Protected application probe failed")
        await asyncio.sleep(0.05)
    terminal = projection.terminal_condition
    failure_codes = tuple(
        event.failure_error_code
        for event in observation.event_page.events
        if isinstance(event, OperationPublicTerminalEventV1) and event.failure_error_code is not None
    )
    if not (terminal is not None and terminal.value == "succeeded"):
        raise AssertionError(f"MCP {definition_id} terminal={terminal}; failure_codes={failure_codes}")
    result = await call_mcp(
        client,
        "result",
        {
            "result": {
                "operation_id": operation_id,
                "terminal_revision": projection.revision,
                "definition_contract_digest": contract["definition_contract_digest"],
                "result_schema": contract["result_schema"],
            }
        },
    )
    return result["document"]["projection"]


async def attend_mcp(
    holder: AsyncRuntimeSessionHolder,
    client: ClientSession,
    *,
    harness: LifecycleHarness,
    invocation: ProcessIdentity,
) -> None:
    """Review only this retained packaged relay's ask through the held person session."""
    asking = asyncio.create_task(call_mcp(client, "describe", {"definition_id": "auth.local-read"}))
    deadline = time.monotonic() + 90
    try:
        while True:
            inventory = await holder.command("attendance_inventory")
            candidates = inventory.get("candidates")
            if not isinstance(candidates, list):
                raise AssertionError("Held runtime returned no attendance inventory")
            attendance_id = _owned_attendance_id(cast(list[object], candidates), harness, invocation)
            if attendance_id is not None:
                decided = await holder.command("attendance_decision", attendance_id=attendance_id, approve=True)
                if decided.get("kind") != "attendance_decided" or decided.get("approved") is not True:
                    raise AssertionError("Runtime did not approve the reviewed relay")
                await asking
                return
            if asking.done():
                await asking
                raise AssertionError("Relay answered without the person's attendance review")
            if time.monotonic() >= deadline:
                raise AssertionError("Runtime recorded no ask from the owned relay")
            await asyncio.sleep(0.05)
    finally:
        if not asking.done():
            asking.cancel()
            with suppress(asyncio.CancelledError):
                await asking


def _owned_attendance_id(
    candidates: list[object], harness: LifecycleHarness, invocation: ProcessIdentity
) -> str | None:
    """Select exactly one ask from the retained packaged relay."""
    matching = [
        cast(dict[str, object], item)
        for item in candidates
        if isinstance(item, dict)
        and verified_relay(
            cast(dict[str, object], item).get("process_id"), harness.package / "bin/cadrumo-mcp.exe", invocation
        )
    ]
    if len(matching) > 1:
        raise AssertionError("Multiple asks came from the owned relay")
    if not matching:
        return None
    attendance_id = matching[0].get("attendance_id")
    if not isinstance(attendance_id, str):
        raise AssertionError("Owned relay ask has no identity")
    return attendance_id


async def mcp_read(client: ClientSession, profile: Profile) -> None:
    """Require a protected profile read through MCP."""
    document = await _mcp_settle(
        client, profile, "auth.local-read", {"profile_id": str(profile.profile_id), "kind": "status"}
    )
    body = AuthReadProjection.model_validate_json(json.dumps(document))
    if not (body.profile_id == profile.profile_id and body.status is not None):
        raise AssertionError("Protected application probe failed")


async def _mcp_profile_facts(client: ClientSession, profile: Profile) -> ProfileViewOperationProjection:
    """Read every stored fact of the profile over MCP, pinned to one revision."""
    payload: dict[str, Any] = {"profile_id": str(profile.profile_id), "page_kind": ProfileViewPageKind.FACTS.value}
    first = ProfileViewOperationProjection.model_validate_json(
        json.dumps(await _mcp_settle(client, profile, PROFILE_VIEW_OPERATION_DEFINITION_ID, payload))
    )
    if not (first.profile_id == profile.profile_id and first.outcome == "page"):
        raise AssertionError("MCP profile view was not released")
    items = list(first.items)
    cursor = first.next_cursor
    while cursor is not None:
        page = ProfileViewOperationProjection.model_validate_json(
            json.dumps(
                await _mcp_settle(
                    client,
                    profile,
                    PROFILE_VIEW_OPERATION_DEFINITION_ID,
                    payload
                    | {
                        "cursor": cursor,
                        "expected_revision": first.record_revision,
                        "expected_content_digest": str(first.content_digest),
                    },
                )
            )
        )
        if not (page.outcome == "page" and page.record_revision == first.record_revision):
            raise AssertionError("MCP profile view changed revision while paging")
        items.extend(page.items)
        cursor = page.next_cursor
    return first.model_copy(update={"items": tuple(items), "next_cursor": None})


def _fact(view: ProfileViewOperationProjection, path: str) -> str | None:
    return next(
        (item.value for item in view.items if isinstance(item, ProfileViewFactItem) and item.path == path), None
    )


async def mcp_edit_profile(
    client: ClientSession, profile: Profile, *, path: str, previous: str | None, value: str
) -> None:
    """Read the profile, change one fact and read it back, all as the agent."""
    before = await _mcp_profile_facts(client, profile)
    if _fact(before, path) != previous:
        raise AssertionError("The agent did not read the profile value it expected before editing")
    mutation = ProfileMutationOperationProjection.model_validate_json(
        json.dumps(
            await _mcp_settle(
                client,
                profile,
                PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
                {
                    "profile_id": str(profile.profile_id),
                    "expected_revision": before.record_revision,
                    "expected_content_digest": str(before.content_digest),
                    "path": path,
                    "value": value,
                },
                idempotency_key=str(uuid4()),
            )
        )
    )
    after = await _mcp_profile_facts(client, profile)
    if not (after.record_revision > before.record_revision and after.record_revision == mutation.record_revision):
        raise AssertionError("The agent's profile edit did not publish a new revision")
    if _fact(after, path) != value:
        raise AssertionError("The agent did not read back the profile value it wrote")


async def mcp_refuse_profile(client: ClientSession, profile: Profile) -> None:
    """Require a cross-profile read to be refused."""
    crossed = await call_mcp(
        client,
        "execute",
        {
            "definition_id": "auth.local-read",
            "subject_ref": profile_operation_subject(str(profile.profile_id)),
            "payload": {"profile_id": str(profile.profile_id), "kind": "status"},
        },
        admitted=False,
    )
    if crossed["code"] not in {"profile_mismatch", "operation_denied", "invalid_request"}:
        raise AssertionError("MCP cross-profile probe returned an unexpected refusal")
