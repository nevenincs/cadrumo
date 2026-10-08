"""Runtime help and syntax errors precede logging, storage and application imports."""

from __future__ import annotations

import asyncio
import os
import sys
import sysconfig
from pathlib import Path

import pytest

from ..arguments import parse_runtime_arguments

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OWNER_ARGUMENTS = [
    "--storage-root",
    "synthetic-runtime-root",
    "--storage-identity",
    "synthetic-identity",
    "--expected-version",
    "synthetic-version",
]
_IMPORT_GUARD = """
import importlib.abc
import runpy
import sys

class ImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] == 'pydantic' or fullname.startswith((
            'cadrumo.core', 'cadrumo.application', 'cadrumo.adapters', 'cadrumo.domain',
            'cadrumo.entrypoints.runtime.main',
        )):
            raise AssertionError('runtime dependency imported before parsing: ' + fullname)

sys.meta_path.insert(0, ImportGuard())
sys.argv = ['cadrumo-runtime', *sys.argv[1:]]
runpy.run_module('cadrumo.entrypoints.runtime', run_name='__main__')
"""


@pytest.mark.parametrize("supervised", [False, True])
def test_owner_arguments_are_parsed_without_materializing_storage(tmp_path: Path, supervised: bool) -> None:
    root = tmp_path / "absent-root"
    arguments = [*_OWNER_ARGUMENTS]
    arguments[1] = str(root)
    if supervised:
        arguments.append("--supervised")
    options = parse_runtime_arguments(arguments)
    assert options.storage_root == root
    assert options.storage_identity == "synthetic-identity"
    assert options.expected_version == "synthetic-version"
    assert options.supervised is supervised
    assert not root.exists()


@pytest.mark.parametrize(
    ("arguments", "exit_code", "message"),
    [
        (["--help"], 0, "--storage-identity"),
        ([], 2, "the following arguments are required"),
        ([*_OWNER_ARGUMENTS, "--bogus"], 2, "unrecognized arguments: --bogus"),
        ([*_OWNER_ARGUMENTS, "--storage-id", "other"], 2, "unrecognized arguments: --storage-id other"),
        (["--storage-root"], 2, "expected one argument"),
    ],
)
@pytest.mark.parametrize("launch", ["guarded-module", "executable"])
@pytest.mark.asyncio
async def test_help_and_invalid_invocations_do_not_initialize_runtime(
    tmp_path: Path, arguments: list[str], exit_code: int, message: str, launch: str
) -> None:
    if launch == "guarded-module":
        command = [sys.executable, "-I", "-c", _IMPORT_GUARD, *arguments]
    else:
        name = "cadrumo-runtime.exe" if sys.platform == "win32" else "cadrumo-runtime"
        command = [str(Path(sysconfig.get_path("scripts")) / name), *arguments]
    environment = os.environ.copy()
    environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(tmp_path / "absent-storage")
    environment["CADRUMO_LOG_DIR"] = str(tmp_path / "absent-logs")
    environment["CADRUMO_AUTHORITY_ROOT"] = str(tmp_path / "absent-authority")
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=tmp_path,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        output, errors = await asyncio.wait_for(process.communicate(), timeout=None)
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
    assert process.returncode == exit_code, output + errors
    assert message in (output if exit_code == 0 else errors).decode()
    assert not (errors if exit_code == 0 else output)
    assert not tuple(tmp_path.iterdir())
