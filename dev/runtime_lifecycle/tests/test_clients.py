"""Packaged CLI, headless TUI adapter and MCP stdio share real runtime authority."""

from __future__ import annotations

import asyncio

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.core.storage_environment import ChildEnvironmentProfile, child_environment

from ..client_probes import _call, _enroll, _mcp_read, _mcp_refuse_profile, _tui
from ..harness import LifecycleHarness

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.serial,
    pytest.mark.windows_only,
    pytest.mark.os_keychain,
    pytest.mark.external_tool,
]


@pytest.mark.anyio
async def test_packaged_client_authentication_and_profile_scope(harness: LifecycleHarness) -> None:
    first = await asyncio.to_thread(harness.create_profile, "Client A")
    second = await asyncio.to_thread(harness.create_profile, "Client B")
    await asyncio.to_thread(harness.cli, "profile", "view", expect_success=False)
    await asyncio.to_thread(_tui, harness, first, admitted=False)
    environment = child_environment(ChildEnvironmentProfile.STRICT, harness.root)
    parameters = StdioServerParameters(
        command=str(harness.package / "bin/cadrumo-mcp.exe"),
        args=[],
        cwd=harness.root,
        env=environment,
    )
    keyed_parameters = parameters.model_copy(update={"args": ["--profile-id", str(first.profile_id)]})
    with (
        (harness.root / "mcp.stderr").open("w", encoding="utf-8") as errors,
        (harness.root / "mcp-key.stderr").open("w", encoding="utf-8") as key_errors,
    ):
        async with (
            stdio_client(parameters, errlog=errors) as (reader, writer),
            ClientSession(reader, writer, read_timeout_seconds=90) as mcp,
            stdio_client(keyed_parameters, errlog=key_errors) as (key_reader, key_writer),
            ClientSession(key_reader, key_writer, read_timeout_seconds=90) as key_mcp,
        ):
            await mcp.initialize()
            await key_mcp.initialize()
            await _call(mcp, "describe", {"definition_id": "auth.local-read"}, admitted=False)
            await _call(key_mcp, "describe", {"definition_id": "auth.local-read"}, admitted=False)
            # The default MCP connection follows the human selector without enrollment or a password.
            for profile, other, label in ((first, second, "Client A"), (second, first, "Client B")):
                await asyncio.to_thread(
                    harness.cli, "login", label, "--secrets-stdin", secret={"passphrase": profile.password}
                )
                view = (await asyncio.to_thread(harness.cli, "profile", "view", profile_secret=profile.password))[
                    "result"
                ]
                assert view["display_name"] == label
                await asyncio.to_thread(_tui, harness, profile, admitted=True)
                await _mcp_read(mcp, profile)
                await _mcp_refuse_profile(mcp, other)
            # The enrolled-key exception stays pinned to A while the human selector is B.
            reference = await _enroll(harness, key_mcp, first)
            await _call(key_mcp, "authenticate", {"credential_reference": str(reference)})
            key_profile_human = harness.connect(first.profile_id)
            await asyncio.to_thread(key_profile_human.client.resume_receipt)
            await asyncio.to_thread(key_profile_human.client.human_sign_out)
            await _mcp_read(key_mcp, first)
            await _mcp_read(mcp, second)
            await _mcp_refuse_profile(key_mcp, second)
            retained = harness.connect(second.profile_id)
            retained.client.resume_receipt()
            boot = retained.wire.hello.boot_id
            await asyncio.to_thread(harness.terminate_runtime, retained)
            await _call(key_mcp, "describe", {"definition_id": "auth.local-read"}, admitted=False)
            recovered = await asyncio.to_thread(harness.connect, second.profile_id, after_boot=boot)
            assert recovered.wire.hello.boot_id != boot
            view = (await asyncio.to_thread(harness.cli, "profile", "view", profile_secret=second.password))["result"]
            assert view["display_name"] == "Client B"
            await asyncio.to_thread(_tui, harness, second, admitted=True)
            await _mcp_read(mcp, second)
            await _call(key_mcp, "authenticate", {"credential_reference": str(reference)})
            await _mcp_read(key_mcp, first)
            signed_out = await asyncio.to_thread(harness.cli, "logout")
            assert signed_out["result"]["human_receipt_revoked"] is True
            await asyncio.to_thread(harness.cli, "profile", "view", expect_success=False)
            await asyncio.to_thread(_tui, harness, second, admitted=False)
            await _call(mcp, "describe", {"definition_id": "auth.local-read"}, admitted=False)
            await _mcp_read(key_mcp, first)
            await _mcp_refuse_profile(key_mcp, second)
            await asyncio.to_thread(harness.stop_manager)
            unavailable = await asyncio.to_thread(
                harness.cli, "profile", "view", profile_secret=second.password, expect_success=False
            )
            assert unavailable["error"]["code"] in {"REFUSED_LOCAL_RUNTIME", "REFUSED_RUNTIME_FRONTEND"}
            await asyncio.to_thread(_tui, harness, first, admitted=False)
            await _call(mcp, "describe", {"definition_id": "auth.local-read"}, admitted=False)
            await _call(key_mcp, "describe", {"definition_id": "auth.local-read"}, admitted=False)
