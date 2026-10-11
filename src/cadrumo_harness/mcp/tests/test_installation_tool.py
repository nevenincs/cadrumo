"""The ``installation`` tool is read from the runtime's act table, narrowed by the surface, and needs no session.

The acts themselves are exercised against a real runtime beside the runtime's
own tests. Here the tool's contract is held to the table and the request
models, the surface decision is taken on real requests, and a call with no
runtime running answers as every other tool does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NoReturn, cast
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation_client import RuntimeInstallationClient
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.operations.mcp_surfaces import MCP_SURFACES, McpSurface, McpSurfaceName
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    InstallationAct,
    RuntimeRepairProfileRequest,
    RuntimeStorageReclaimRequest,
    installation_request_facts,
)
from cadrumo.core.config import override_settings
from cadrumo_harness.mcp.installation_acts import (
    installation_acts_on,
    perform_installation_act,
    prepare_installation_act,
)
from cadrumo_harness.mcp.protocol_contract import (
    MCP_TOOL_CATALOGUE,
    installation_act_arguments,
    tool_catalogue,
    validate_tool_arguments,
)
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.session_acts import SessionSecrets
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_FULL = MCP_SURFACES[McpSurfaceName.FULL]
_READ_ONLY_LOCAL = MCP_SURFACES[McpSurfaceName.READ_ONLY_LOCAL]
_SERVER_SUPPLIED = {"request_id", "frontend", "action"}
_PROFILE_INPUT = "synthetic-profile-input"
_SAMPLE_ARGUMENTS: dict[str, object] = {
    "area": "cache",
    "confirm": True,
    "acknowledge_retention_override": True,
    "retention_override_reason": "synthetic reason",
    "operation_id": "0f" * 32,
    "path": "/synthetic/archive.cadrumo",
    "label": "Synthetic",
    "source_digest": "ab" * 32,
    "profile_id": "6f1c1a52-3b55-4d0b-9c0e-0d6b7c4c8f11",
    "lines": 40,
    "profile": "Synthetic",
    "clear_active": True,
    "package": "/synthetic/package.zip",
    "signature": "/synthetic/package.sig",
    "public_key": "ab" * 32,
    "receipt": "/synthetic/package.receipt",
    "operator_public_key": "ab" * 32,
    "counter_signer_public_key": "cd" * 32,
    "trusted_key": "ab" * 32,
}
"""One valid value for every argument an act takes today; an act that gains an argument needs one here."""


def _installation_schema(surface: McpSurface = _FULL) -> dict[str, Any]:
    (schema,) = [
        schema for name, _text, schema in tool_catalogue(installation_acts_on(surface)) if name == "installation"
    ]
    return dict(schema)


def _call_arguments(act: InstallationAct, *, every: bool) -> dict[str, object]:
    """Build one call for ``act`` from the sample values: its required arguments, or all of them."""
    contract = INSTALLATION_ACT_CONTRACTS[act]
    arguments: dict[str, object] = {"action": act.value}
    for name, (_declaration, required) in installation_act_arguments(contract).items():
        if required or every:
            arguments[name] = _SAMPLE_ARGUMENTS[name]
    if contract.takes_secret:
        arguments["secret"] = _PROFILE_INPUT
    return arguments


def test_the_tools_actions_are_exactly_the_act_table_in_its_order() -> None:
    actions = _installation_schema()["properties"]["action"]["enum"]

    assert actions == [act.value for act in INSTALLATION_ACT_CONTRACTS]
    assert actions == [act.value for act in InstallationAct]
    assert _installation_schema()["required"] == ["action"]


@pytest.mark.parametrize("act", list(InstallationAct), ids=lambda act: act.value)
def test_an_acts_arguments_are_the_members_of_its_request(act: InstallationAct) -> None:
    contract = INSTALLATION_ACT_CONTRACTS[act]
    members = {name: info for name, info in contract.request.model_fields.items() if name not in _SERVER_SUPPLIED}
    arguments = installation_act_arguments(contract)

    # The request's confirmation is the tool's confirm, as on the session tool; every other member keeps its name.
    assert set(arguments) == {"confirm" if name == "confirmed" else name for name in members}
    for name, info in members.items():
        _declaration, required = arguments["confirm" if name == "confirmed" else name]
        assert required is info.is_required(), name
    properties = _installation_schema()["properties"]
    for name, (declaration, _required) in arguments.items():
        assert properties[name] == declaration


def test_the_tool_declares_nothing_but_the_acts_arguments_and_its_own() -> None:
    properties = _installation_schema()["properties"]
    derived = {
        name for contract in INSTALLATION_ACT_CONTRACTS.values() for name in installation_act_arguments(contract)
    }

    assert set(properties) == derived | {"action", "secret", "secret_reference"}
    assert properties["secret"] == {"type": "string", "format": "password", "writeOnly": True}
    # The reference names a secret and is none itself, so it is plain text a client may show.
    assert properties["secret_reference"] == {"type": "string", "format": "uuid"}
    assert set(_SAMPLE_ARGUMENTS) == derived


def test_declarations_carry_the_request_models_types_and_bounds() -> None:
    """Expected values written from the request models' own definitions, not from the derivation."""
    reclaim = installation_act_arguments(INSTALLATION_ACT_CONTRACTS[InstallationAct.STORAGE_RECLAIM])
    logs = installation_act_arguments(INSTALLATION_ACT_CONTRACTS[InstallationAct.REPAIR_LOGS])
    enrol = installation_act_arguments(INSTALLATION_ACT_CONTRACTS[InstallationAct.RECOVERY_ENROLL])
    status = installation_act_arguments(INSTALLATION_ACT_CONTRACTS[InstallationAct.RESET_STATUS])
    inspect = installation_act_arguments(INSTALLATION_ACT_CONTRACTS[InstallationAct.ARCHIVE_INSPECT])

    assert reclaim == {
        "area": ({"type": "string", "enum": ["state", "logs", "cache", "exports"]}, True),
        "confirm": ({"type": "boolean"}, False),
    }
    assert logs == {"lines": ({"type": "integer", "minimum": 0, "maximum": 5000}, False)}
    # Enrolment names a profile only when it is not the selected one.
    assert enrol == {"profile_id": ({"type": "string", "format": "uuid"}, False)}
    assert status == {
        "operation_id": ({"type": "string", "minLength": 64, "maxLength": 64, "pattern": "^[0-9a-f]{64}$"}, False)
    }
    assert inspect == {"path": ({"type": "string", "minLength": 1, "maxLength": 4096}, True)}


@pytest.mark.parametrize("act", list(InstallationAct), ids=lambda act: act.value)
@pytest.mark.parametrize("every", [False, True], ids=["required-only", "every-argument"])
def test_a_call_the_schema_admits_builds_the_acts_own_request(act: InstallationAct, every: bool) -> None:
    contract = INSTALLATION_ACT_CONTRACTS[act]
    arguments = _call_arguments(act, every=every)
    validate_tool_arguments("installation", arguments)
    secrets = SessionSecrets(arguments)
    try:
        prepared = prepare_installation_act(arguments, secrets, _FULL)
        request = prepared.request

        assert type(request) is contract.request
        assert request.frontend is OperationFrontendProjection.MCP
        assert (prepared.passphrase is not None) is contract.takes_secret
        sent = request.model_dump(mode="json", exclude=_SERVER_SUPPLIED, exclude_unset=True)
        expected = {("confirmed" if name == "confirm" else name): value for name, value in arguments.items()}
        del expected["action"]
        assert sent == expected
        # The secret left the arguments as a buffer, so nothing built from them can repeat it.
        assert "secret" not in arguments
    finally:
        secrets.wipe()
    assert prepared.passphrase is None or not any(prepared.passphrase)


def test_an_argument_of_another_act_and_an_unknown_action_are_refused_before_anything_is_sent() -> None:
    with pytest.raises(ValueError, match="invalid tool field"):
        validate_tool_arguments("installation", {"action": "storage_format"})
    with pytest.raises(ValueError, match="unknown or missing tool field"):
        validate_tool_arguments("installation", {"action": "storage_check", "confirmed": True})
    stray: dict[str, object] = {"action": "storage_check", "lines": 5}
    validate_tool_arguments("installation", stray)
    with pytest.raises(ValueError):
        prepare_installation_act(stray, SessionSecrets(stray), _FULL)
    relative: dict[str, object] = {"action": "archive_inspect", "path": "relative/archive.cadrumo"}
    with pytest.raises(ValueError):
        prepare_installation_act(relative, SessionSecrets(relative), _FULL)


def test_the_narrowed_surface_offers_reads_and_unconfirmed_reports_and_nothing_that_changes_records() -> None:
    reads = {act for act, contract in INSTALLATION_ACT_CONTRACTS.items() if not contract.facts.changes_records}
    reports = {
        InstallationAct.STORAGE_RECLAIM,
        InstallationAct.RESET_START,
        InstallationAct.RESET_RESUME,
        InstallationAct.REPAIR_PROFILE,
    }

    assert installation_acts_on(_FULL) == tuple(INSTALLATION_ACT_CONTRACTS)
    assert set(installation_acts_on(_READ_ONLY_LOCAL)) == reads | reports
    withheld = set(InstallationAct) - set(installation_acts_on(_READ_ONLY_LOCAL))
    assert withheld == {InstallationAct.STORAGE_INIT, InstallationAct.ARCHIVE_IMPORT, InstallationAct.RECOVERY_ENROLL}
    # No act left on the surface takes a secret, so the narrowed tool declares neither form of one.
    narrowed = _installation_schema(_READ_ONLY_LOCAL)
    assert narrowed["properties"]["action"]["enum"] == [act.value for act in installation_acts_on(_READ_ONLY_LOCAL)]
    assert not {"secret", "secret_reference", "profile_id"} & set(narrowed["properties"])


@pytest.mark.parametrize("surface", list(MCP_SURFACES.values()), ids=lambda surface: surface.name.value)
def test_a_surface_lists_the_tool_exactly_when_it_allows_at_least_one_act(surface: McpSurface) -> None:
    assert ("installation" in surface.tools) is bool(installation_acts_on(surface))


@pytest.mark.parametrize("act", list(InstallationAct), ids=lambda act: act.value)
def test_the_narrowed_surface_decides_on_the_facts_of_the_exact_request(act: InstallationAct) -> None:
    """Every form of every act is allowed exactly when its own facts change no record and reach no network."""
    for every in (False, True):
        arguments = _call_arguments(act, every=every)
        on_full = dict(arguments)
        request = prepare_installation_act(on_full, SessionSecrets(on_full), _FULL).request
        facts = installation_request_facts(request)
        allowed = not facts.changes_records and not facts.reaches_network
        secrets = SessionSecrets(arguments)
        if allowed:
            assert type(prepare_installation_act(arguments, secrets, _READ_ONLY_LOCAL).request) is type(request)
        else:
            with pytest.raises(RuntimeFrontendRefusedError) as refused:
                prepare_installation_act(arguments, secrets, _READ_ONLY_LOCAL)
            assert refused.value.reason == "frontend_denied"


def test_confirmation_is_what_turns_a_report_into_a_change_on_the_narrowed_surface() -> None:
    unconfirmed = {"action": "storage_reclaim", "area": "logs"}
    confirmed = {"action": "storage_reclaim", "area": "logs", "confirm": True}
    inspection = {"action": "repair_profile", "profile": "Synthetic", "confirm": True}
    clearing = {"action": "repair_profile", "clear_active": True, "confirm": True}

    reported = prepare_installation_act(unconfirmed, SessionSecrets(unconfirmed), _READ_ONLY_LOCAL).request
    inspected = prepare_installation_act(inspection, SessionSecrets(inspection), _READ_ONLY_LOCAL).request
    assert isinstance(reported, RuntimeStorageReclaimRequest) and not reported.confirmed
    assert isinstance(inspected, RuntimeRepairProfileRequest) and not inspected.clear_active
    for changing in (confirmed, clearing):
        with pytest.raises(RuntimeFrontendRefusedError):
            prepare_installation_act(changing, SessionSecrets(changing), _READ_ONLY_LOCAL)


@pytest.mark.anyio
@pytest.mark.parametrize("surface", list(MCP_SURFACES.values()), ids=lambda surface: surface.name.value)
async def test_the_server_advertises_the_installation_acts_its_surface_allows(surface: McpSurface) -> None:
    adapter = RuntimeMcpAdapter(profile_id=uuid4(), client=None, surface=surface)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    finally:
        await adapter.close()

    advertised = tools["installation"]
    assert advertised.input_schema == _installation_schema(surface)
    offered = [act.value for act in installation_acts_on(surface)]
    assert advertised.input_schema["properties"]["action"]["enum"] == offered
    # Each offered action is described, and one the surface withholds is not named as an action.
    described = advertised.description or ""
    for act in InstallationAct:
        assert (f" {act.value}(" in described) is (act.value in offered)
    if surface is _FULL:
        assert [(tool.name, tool.description, tool.input_schema) for tool in tools.values()] == [
            (name, text, schema) for name, text, schema in MCP_TOOL_CATALOGUE
        ]


class _LostConnection:
    """A connection whose wait runs out after the act was sent, as a long act on a slow disk can."""

    def perform(self, *_request: object, **_exchange: object) -> NoReturn:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)


def _no_held_secret() -> NoReturn:
    raise AssertionError("no secret is handed over on a connection that sends nothing back")


def test_a_changing_act_whose_outcome_was_lost_is_unresolved_and_names_the_act_that_reads_it() -> None:
    lost = cast("RuntimeInstallationClient", _LostConnection())
    reset: dict[str, object] = {"action": "reset_start", "confirm": True}
    reclaim: dict[str, object] = {"action": "storage_reclaim", "area": "cache", "confirm": True}
    report: dict[str, object] = {"action": "storage_reclaim", "area": "cache"}

    started = perform_installation_act(
        lost, prepare_installation_act(reset, SessionSecrets(reset), _FULL), held_secrets=_no_held_secret
    )
    reclaimed = perform_installation_act(
        lost, prepare_installation_act(reclaim, SessionSecrets(reclaim), _FULL), held_secrets=_no_held_secret
    )

    code = RuntimeRefusalCode.DEADLINE_EXCEEDED.value
    assert started == {"outcome": "unresolved", "code": code, "act": "reset_start", "outcome_read_by": "reset_status"}
    assert reclaimed == {"outcome": "unresolved", "code": code, "act": "storage_reclaim"}
    # A request that changes no record lost nothing: the refusal is the transport's own.
    with pytest.raises(RuntimeRefusalError):
        perform_installation_act(
            lost, prepare_installation_act(report, SessionSecrets(report), _FULL), held_secrets=_no_held_secret
        )


@pytest.mark.anyio
async def test_with_no_runtime_running_the_tool_answers_unavailable_with_the_remedy(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path), override_settings(cadrumo_output_language="en"):
        adapter = RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)
        try:
            read = await adapter.call("installation", {"action": "storage_check"})
            change = await adapter.call("installation", {"action": "storage_reclaim", "area": "cache", "confirm": True})
        finally:
            await adapter.close()

    for reply in (read, change):
        assert reply["outcome"] == "refused" and reply["code"] == "runtime_unavailable"
        assert "manager" in reply["remedy"]
    # The tool asked for no session, started nothing and holds nothing.
    assert adapter.client is None
