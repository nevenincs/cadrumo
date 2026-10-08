"""Launch finite synthetic modules in the configured native Python environment."""

from __future__ import annotations

import asyncio
import os
import sys
import sysconfig
from pathlib import Path

from cadrumo.core.storage_environment import storage_directory
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location


def runtime_namespace_base() -> Path:
    """Create the configured socket base for temporary integration namespaces."""
    root = storage_directory("CADRUMO_RUNTIME_SOCKET_DIR", storage_location(StorageCategory.RUNTIME_SOCKETS).subpath)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def native_python() -> Path:
    """Select the interpreter process itself, bypassing Windows venv redirectors."""
    return Path(sys.base_prefix) / "python.exe" if sys.platform == "win32" else Path(sys.executable)


def fixture_environment() -> dict[str, str]:
    """Expose this test environment's dependencies to its synthetic child."""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(sys.path)
    return environment


def fixture_arguments(module: str, *arguments: str) -> tuple[str, ...]:
    """Run a fixture after initializing the configured site-packages hooks."""
    return (
        "-c",
        "import runpy, site, sys; site.addsitedir(sys.argv.pop(1)); "
        "runpy.run_module(sys.argv.pop(1), run_name='__main__')",
        sysconfig.get_path("purelib"),
        module,
        *arguments,
    )


async def launch_fixture(module: str, *arguments: str) -> asyncio.subprocess.Process:
    """Launch the direct fixture owner with test-owned standard streams."""
    return await asyncio.create_subprocess_exec(
        str(native_python()),
        *fixture_arguments(module, *arguments),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=fixture_environment(),
    )
