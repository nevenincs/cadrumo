"""The merge gate's shard recipe runs both of its passes and fails with the first failed one.

The recipe is executed by ``just`` itself, from the real justfile, in a scratch
working directory. A stand-in ``uv`` earlier on PATH answers the shard
selection by writing one test file and answers each pytest pass with the exit
status the case gives it, recording which pass ran.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

import pytest

from dev.packaging.command_execution import run_command
from dev.paths import REPO_ROOT

from ..lane_recipe_commands import resolve_just_executable

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RECIPE: Final = "test-gate-shard"
_STAND_IN_UV: Final = """#!/usr/bin/env bash
case " $* " in
  *" dev.ci.gate_shards "*)
    while [ "$#" -gt 0 ]; do
      if [ "$1" = "--output" ]; then mkdir -p "$(dirname "$2")"; printf 'tests/test_probe.py\\n' > "$2"; fi
      shift
    done
    exit 0 ;;
  *" -n0 "*) echo serial >> "$PASS_LOG"; exit "$SERIAL_STATUS" ;;
  *" pytest "*) echo parallel >> "$PASS_LOG"; exit "$PARALLEL_STATUS" ;;
esac
echo "unexpected uv call: $*" >&2
exit 97
"""


def _run_shard(tmp_path: Path, parallel: int, serial: int) -> tuple[int, list[str]]:
    shims = tmp_path / "bin"
    shims.mkdir()
    stand_in = shims / "uv"
    stand_in.write_text(_STAND_IN_UV, encoding="utf-8", newline="\n")
    stand_in.chmod(0o755)
    work = tmp_path / "work"
    work.mkdir()
    pass_log = tmp_path / "passes.txt"
    environment = {
        **os.environ,
        "PATH": f"{shims}{os.pathsep}{os.environ['PATH']}",
        "PASS_LOG": str(pass_log),
        "PARALLEL_STATUS": str(parallel),
        "SERIAL_STATUS": str(serial),
    }
    result = run_command(
        [
            resolve_just_executable(),
            "--justfile",
            str(REPO_ROOT / "justfile"),
            "--working-directory",
            str(work),
            _RECIPE,
            "1/1",
        ],
        cwd=work,
        environment=environment,
        timeout_seconds=120,
    )
    passes = pass_log.read_text(encoding="utf-8").split() if pass_log.exists() else []
    assert "unexpected uv call" not in result.stderr, result.stderr
    return result.returncode, passes


@pytest.mark.parametrize(
    ("parallel", "serial", "expected"),
    [
        pytest.param(0, 0, 0, id="both-pass"),
        pytest.param(1, 0, 1, id="parallel-fails-serial-still-runs"),
        pytest.param(0, 1, 1, id="serial-fails"),
        pytest.param(1, 2, 1, id="both-fail-the-parallel-status-wins"),
        pytest.param(5, 0, 0, id="no-parallel-test"),
        pytest.param(0, 5, 0, id="no-serial-test"),
    ],
)
def test_the_shard_runs_both_passes_and_fails_with_the_first_failed_one(
    tmp_path: Path, parallel: int, serial: int, expected: int
) -> None:
    status, passes = _run_shard(tmp_path, parallel, serial)
    assert passes == ["parallel", "serial"]
    assert status == expected


def test_a_shard_that_selects_no_test_in_either_pass_fails(tmp_path: Path) -> None:
    status, passes = _run_shard(tmp_path, 5, 5)
    assert passes == ["parallel", "serial"]
    assert status == 1
