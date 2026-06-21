"""Throwaway repro for export-output-safety EDGE-MED-1."""
from __future__ import annotations
from pathlib import Path
import pytest
from typer.testing import CliRunner
from aeat.entrypoints.cli import app
from aeat.entrypoints.cli.tests.test_modelo_export_verb import (
    _isolated_backend, _set_export_profile_name, _seed_exportable_modelo_111_revision,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

def test_repro_existing_dir_leaves_tmp_orphan(cli_runner: CliRunner, tmp_path: Path) -> None:
    _set_export_profile_name()
    work_unit_id, _ = _seed_exportable_modelo_111_revision()
    existing_dir = tmp_path / "outdir"
    existing_dir.mkdir()
    result = cli_runner.invoke(app, ["app", "modelo", "export", work_unit_id, "--output", str(existing_dir)])
    print("EXIT", result.exit_code)
    print("OUTPUT", repr(result.output))
    if result.exception:
        import traceback
        print("EXC", "".join(traceback.format_exception(result.exception)))
    orphan = existing_dir.with_name(existing_dir.name + ".tmp")
    print("ORPHAN EXISTS", orphan.exists(), "size", orphan.stat().st_size if orphan.exists() else 0)
