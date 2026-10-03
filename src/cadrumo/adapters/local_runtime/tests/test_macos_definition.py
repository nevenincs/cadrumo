"""Native property-list parsing only; no agent is registered or started."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from cadrumo.application.runtime.management import RuntimeServiceBinding

from ..posix import posix_storage_identity
from ..service_definitions import macos_agent_plist, runtime_service_arguments

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.skipif(sys.platform != "darwin", reason="requires native macOS property-list parser"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("login_autostart", [False, True])
async def test_native_plist_parser_preserves_literal_binding_without_installation(
    tmp_path: Path, login_autostart: bool
) -> None:
    if sys.platform != "darwin":
        pytest.skip("requires native macOS owner identity")
    root = tmp_path / 'literal %n $HOME "quoted" ü'
    root.mkdir()
    binding = RuntimeServiceBinding(
        executable="/usr/bin/true",
        storage_root=str(root.resolve()),
        storage_identity=posix_storage_identity(root),
        os_owner_id=str(os.getuid()),
        product_version="synthetic-cohort",
    )
    definition = tmp_path / "synthetic.plist"
    definition.write_bytes(macos_agent_plist(binding, login_autostart=login_autostart))
    process = await asyncio.create_subprocess_exec(
        "/usr/bin/plutil",
        "-convert",
        "json",
        "-o",
        "-",
        str(definition),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        close_fds=True,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
        assert process.returncode == 0, stderr.decode(errors="replace")
        assert not stderr, stderr
        document = json.loads(stdout)
        assert document["ProgramArguments"] == [binding.executable, *runtime_service_arguments(binding)]
        assert document["WorkingDirectory"] == binding.storage_root
        assert document["RunAtLoad"] is login_autostart
        assert document["LimitLoadToSessionType"] == "Aqua"
        assert document["KeepAlive"] == ({"SuccessfulExit": False} if login_autostart else False)
    finally:
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(process.wait(), timeout=2)
