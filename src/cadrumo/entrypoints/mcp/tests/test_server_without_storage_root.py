"""The MCP server speaks the protocol when storage-root resolution refuses.

A machine carrying retired former-product state makes the default storage-root
resolution raise :class:`~cadrumo.core.FormerProductStateError`. That refusal
must surface on the tool calls that actually need storage - never kill the
server before it can complete ``initialize``/``tools/list``. This regression
drives the REAL ``cadrumo-mcp`` console script over stdio with a fabricated
retired-state platform root and no ``CADRUMO_*`` overrides, exactly the
environment a real client on an upgrader's machine provides. It pins the
startup chain that died four separate ways during the distribution campaign:
import-time registry settings, the schema-build config subtree, the adapter
module constants, and the eager telemetry-directory resolution.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import IO, Any

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "storage-root-regression", "version": "0"},
    },
}


def _server_executable() -> Path:
    name = "cadrumo-mcp.exe" if sys.platform == "win32" else "cadrumo-mcp"
    executable = Path(sysconfig.get_path("scripts")).resolve() / name
    if not executable.is_file():
        pytest.fail(f"cadrumo-mcp console script is missing from this environment: {executable}")
    return executable


def _retired_state_environment(tmp_path: Path) -> dict[str, str]:
    """A per-OS platform-data root whose retired ``aeat`` state triggers the refusal."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}
    hostile_root = tmp_path / "platform-data-with-retired-state"
    if sys.platform == "win32":
        former_product_root = hostile_root / "aeat"
        environment["LOCALAPPDATA"] = str(hostile_root)
    elif sys.platform == "darwin":
        hostile_home = tmp_path / "home-with-retired-state"
        former_product_root = hostile_home / "Library" / "Application Support" / "aeat"
        environment["HOME"] = str(hostile_home)
    else:
        former_product_root = hostile_root / "aeat"
        environment["XDG_DATA_HOME"] = str(hostile_root)
    former_product_root.mkdir(parents=True)
    (former_product_root / "custody-marker.bin").write_bytes(b"retired-aeat-state-must-remain")
    return environment


def _read_response(stdout: IO[str], target_id: int) -> dict[str, Any]:
    while True:
        line = stdout.readline()
        if not line:
            pytest.fail(f"server closed stdout before answering request id {target_id}")
        stripped = line.strip()
        if not stripped:
            continue
        message = json.loads(stripped)
        if message.get("id") == target_id:
            assert isinstance(message, dict)
            return message


def test_server_completes_initialize_and_tools_list_when_storage_root_refuses(tmp_path: Path) -> None:
    environment = _retired_state_environment(tmp_path)
    process = subprocess.Popen(  # noqa: S603 - the executable is this environment's own console script
        [str(_server_executable())],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        text=True,
        encoding="utf-8",
    )
    try:
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(json.dumps(_INITIALIZE) + "\n")
        process.stdin.flush()
        initialize = _read_response(process.stdout, 1)
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n")
        process.stdin.flush()
        tools = _read_response(process.stdout, 2)
    finally:
        process.kill()
        stderr_text = process.stderr.read() if process.stderr is not None else ""
    assert initialize["result"]["serverInfo"]["name"] == "cadrumo"
    assert len(tools["result"]["tools"]) > 0
    # The degradation is visible, never silent: the startup note names the
    # storage-root refusal on stderr, which the client's MCP log captures.
    assert "serving without telemetry" in stderr_text
