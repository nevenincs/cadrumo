"""Installed MCP subprocess resolution is independent of checkout and ``PATH``.

This is a real distribution test, not an in-process unit test. It builds the
committed three-wheel cohort, installs ``cadrumo[agent]`` into a fresh stdlib
virtual environment, launches that environment's absolute ``cadrumo-mcp``
console script outside the checkout, removes product scripts and ``PYTHONPATH``
from the child environment, and calls the public ``execute`` MCP tool.

The call can succeed only if the installed server resolves and executes the
``aeat`` console script beside itself. A source import, ambient executable, or
checkout shim cannot satisfy the probe.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, cast

import pytest
from dev.packaging.installed_mcp_oracle import isolated_mcp_environment
from dev.packaging.smoke_core import _run, _venv_bin, _venv_python
from dev.packaging.smoke_pip_core import _create_pip_venv
from dev.packaging.smoke_split_install import (
    _build_data_wheels,
    _build_root_wheel,
    _head_extract,
)
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_REPO_ROOT = Path(__file__).resolve().parents[5]


def _run_async[T](coroutine: Coroutine[object, object, T]) -> T:
    return asyncio.run(coroutine)


def _installed_script(venv: Path, name: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return (_venv_bin(venv) / f"{name}{suffix}").resolve()


@pytest.fixture(scope="module")
def installed_agent_environment(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Build and install one committed command/data/agent cohort."""
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to build the real installed cohort"

    work_dir = tmp_path_factory.mktemp("installed-mcp-cli-resolution")
    build_root = _head_extract(_REPO_ROOT, work_dir)
    root_wheel = _build_root_wheel(build_root, work_dir, uv)
    data_wheels = _build_data_wheels(build_root, work_dir, uv)
    venv = _create_pip_venv(work_dir, f"{sys.version_info.major}.{sys.version_info.minor}")
    _run(
        [
            str(_venv_python(venv)),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            f"{root_wheel.resolve()}[agent]",
            *(str(wheel.resolve()) for wheel in data_wheels),
        ],
        cwd=work_dir,
    )
    _run([str(_venv_python(venv)), "-m", "pip", "check"], cwd=work_dir)

    mcp_server = _installed_script(venv, "cadrumo-mcp")
    cli = _installed_script(venv, "aeat")
    assert mcp_server.is_file()
    assert cli.is_file()
    return work_dir, mcp_server


async def _call_installed_contract(work_dir: Path, mcp_server: Path) -> dict[str, object]:
    execution_root = work_dir / "outside-checkout"
    execution_root.mkdir()
    environment = isolated_mcp_environment(work_dir / "product-state")
    environment.pop("PYTHONPATH", None)
    assert shutil.which("aeat", path=environment["PATH"]) is None
    assert shutil.which("cadrumo-mcp", path=environment["PATH"]) is None
    assert str(_REPO_ROOT).casefold() not in environment["PATH"].casefold()

    params = StdioServerParameters(
        command=str(mcp_server),
        cwd=str(execution_root),
        env=environment,
        encoding="utf-8",
        encoding_error_handler="strict",
    )
    async with (
        stdio_client(params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        initialized = await session.initialize()
        assert initialized.serverInfo.name == "cadrumo"
        call = await session.call_tool(
            "execute",
            {"command_key": "contract", "arguments": {}},
        )

    assert call.isError is False
    payload = call.structuredContent
    assert isinstance(payload, dict)
    return payload


def test_installed_mcp_executes_sibling_cli_without_checkout_or_path(
    installed_agent_environment: tuple[Path, Path],
) -> None:
    work_dir, mcp_server = installed_agent_environment

    payload = _run_async(_call_installed_contract(work_dir, mcp_server))

    assert payload["command"] == "contract"
    assert payload["status"] == "success"
    result = cast("dict[str, Any]", payload["result"])
    assert isinstance(result, dict)
    assert result["manifest_version"] == "1"
    assert result["envelope_schema_version"] == "2"
    contract = cast("dict[str, Any]", result["contract"])
    assert isinstance(contract, dict)
    assert [root["name"] for root in contract["roots"]] == ["config", "app"]
