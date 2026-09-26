"""The candidate compiler's process spawn stays where its exemption says, and dies with its parent."""

from __future__ import annotations

import ast
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from .. import candidate_compile_process
from ..candidate_compile_process import PARENT_EXITED_EXIT_CODE

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SPAWN_MODULE = Path(candidate_compile_process.__file__).resolve()
_SPAWN_FUNCTION = "run_candidate_compiler"
_SPAWN_CALLS = frozenset({"run", "Popen"})
_WATCHDOG_PROBE = """
import sys
import time

from dev.registry.pipeline.candidate_compile_process import exit_when_parent_exits

exit_when_parent_exits()
print("ready", flush=True)
time.sleep(60)
sys.exit(0)
"""


def _subprocess_spawns_in(source: str, function_name: str) -> int:
    """Count ``subprocess.run``/``subprocess.Popen`` calls inside one module-level function."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return sum(
                1
                for call in ast.walk(node)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "subprocess"
                and call.func.attr in _SPAWN_CALLS
            )
    return 0


def test_the_subprocess_exemption_names_the_module_that_still_spawns() -> None:
    """The S603 exemption is keyed on the spawn module, which must still perform the spawn."""
    exemptions = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["ruff"]["lint"][
        "per-file-ignores"
    ]
    module_key = _SPAWN_MODULE.relative_to(REPO_ROOT).as_posix()

    assert "S603" in exemptions[module_key]
    assert _subprocess_spawns_in(_SPAWN_MODULE.read_text(encoding="utf-8"), _SPAWN_FUNCTION) == 1


def test_the_spawn_guard_detects_a_module_without_the_spawn() -> None:
    """TEETH: the same check over the module with its spawn removed finds nothing to exempt."""
    source = _SPAWN_MODULE.read_text(encoding="utf-8")
    without_spawn = source.replace("subprocess.Popen(", "_not_a_spawn(")

    assert without_spawn != source
    assert _subprocess_spawns_in(without_spawn, _SPAWN_FUNCTION) == 0


def test_the_compiler_process_exits_when_its_parent_lifetime_pipe_closes() -> None:
    """A closed lifetime pipe, which is what a dead parent leaves behind, ends the child with its own status."""
    with subprocess.Popen(
        [sys.executable, "-s", "-c", _WATCHDOG_PROBE],
        cwd=REPO_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ) as process:
        try:
            assert process.stdin is not None
            assert process.stdout is not None
            assert process.stdout.readline().strip() == b"ready"
            time.sleep(0.5)
            assert process.poll() is None, "an open lifetime pipe must keep the child running"

            process.stdin.close()

            assert process.wait(timeout=10) == PARENT_EXITED_EXIT_CODE
        finally:
            if process.poll() is None:
                process.kill()
