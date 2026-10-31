"""Launch finite synthetic modules in the configured native Python environment."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from functools import cache
from importlib.metadata import distribution
from pathlib import Path

from cadrumo.core.storage_environment import configured_storage_root
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location


@cache
def runtime_namespace_base() -> Path:
    """Return the controlled base for private temporary integration namespaces.

    POSIX uses the repository-pinned pytest temp root directly: each caller creates
    its own private child, and an extra base directory would consume the bounded
    Unix socket path. Windows uses the isolated test storage root's socket directory.
    Neither platform writes to the account's transport directory.
    """
    if sys.platform == "win32":
        root = configured_storage_root() / storage_location(StorageCategory.CONNECTION_SOCKETS).relative_path()
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        return root
    return Path(tempfile.gettempdir()).resolve()


def native_python() -> Path:
    """Select the interpreter process itself, bypassing Windows venv redirectors."""
    return Path(sys.base_prefix) / "python.exe" if sys.platform == "win32" else Path(sys.executable)


def fixture_environment() -> dict[str, str]:
    """Expose this test environment's dependencies to its synthetic child."""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(sys.path)
    return environment


def _installed_site_packages() -> str:
    # A child that ran on the base interpreter reports the base purelib from
    # sysconfig; the directory holding the installed distribution is the test
    # environment's in every generation.
    return str(Path(str(distribution("cadrumo").locate_file(""))).resolve())


def fixture_arguments(module: str, *arguments: str) -> tuple[str, ...]:
    """Run a fixture after initializing the configured site-packages hooks."""
    return (
        "-c",
        "import runpy, site, sys; site.addsitedir(sys.argv.pop(1)); "
        "runpy.run_module(sys.argv.pop(1), run_name='__main__')",
        _installed_site_packages(),
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
