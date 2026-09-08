from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ..command import run

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_command_run_streams_and_persists_identity(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    command = (sys.executable, "-c", "print('observable signal')")

    status = run(command, repository=tmp_path, family="audit-runs", label="audit-probe")

    assert status == 0
    assert "observable signal" in capsys.readouterr().out
    run_dir = next((tmp_path / ".logs" / "audit-runs").glob("*/*"))
    metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert metadata["command"] == list(command)
    assert metadata["exit_status"] == 0
    assert "COMMAND " in (run_dir / "run.log").read_text(encoding="utf-8")


def test_command_run_preserves_failure_status(tmp_path: Path) -> None:
    status = run(
        (sys.executable, "-c", "raise SystemExit(7)"),
        repository=tmp_path,
        family="audit-runs",
        label="audit-probe",
    )

    assert status == 7


def test_command_run_confines_child_temp_and_cache_paths(tmp_path: Path) -> None:
    probe = (
        "import json, os, pathlib, tempfile; "
        "pathlib.Path(os.environ['CADRUMO_DEV_ARTIFACTS_DIR']).joinpath('paths.json').write_text("
        "json.dumps({'temp': tempfile.gettempdir(), 'cache': os.environ['XDG_CACHE_HOME']}))"
    )
    status = run((sys.executable, "-c", probe), repository=tmp_path, family="audit-runs", label="path-probe")

    assert status == 0
    run_dir = next((tmp_path / ".logs" / "audit-runs").glob("*/*"))
    paths = json.loads((run_dir / "artifacts" / "paths.json").read_text(encoding="utf-8"))
    assert Path(paths["temp"]).resolve() == (run_dir / "scratch").resolve()
    assert Path(paths["cache"]).resolve() == (run_dir / "cache").resolve()
