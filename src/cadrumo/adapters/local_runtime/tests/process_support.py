"""Launch finite synthetic modules in the configured native Python environment."""

from __future__ import annotations

import asyncio
import os
import sys
import sysconfig
from pathlib import Path


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
