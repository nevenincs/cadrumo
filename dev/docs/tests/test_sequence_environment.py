"""Sequence children keep owned scratch while discarding operator routing."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.docs.sequences.checks import english_pinned_environment
from dev.packaging.command_execution import run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_child_keeps_scratch_without_inheriting_runtime_routing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = tmp_path / "short-scratch"
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", str(tmp_path / "parent-state"))
    monkeypatch.setenv("CADRUMO_TEMP_DIR", str(scratch))
    monkeypatch.setenv("CADRUMO_RUNTIME_SOCKET_DIR", str(tmp_path / "operator-sockets"))
    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "hu")
    environment = english_pinned_environment()
    assert "CADRUMO_RUNTIME_SOCKET_DIR" not in environment
    assert "CADRUMO_LOCAL_STORAGE_ROOT" not in environment
    assert "AEAT_OUTPUT_LANGUAGE" not in environment
    result = run_command(
        [
            sys.executable,
            "-c",
            "from cadrumo.core.storage_environment import prepare_temporary_directory; "
            "print(prepare_temporary_directory())",
        ],
        cwd=REPO_ROOT,
        environment=environment,
    )
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == scratch.resolve()
