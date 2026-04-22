"""Parametrised CLI smoke test over every registered schema (wave 124).

For each (modelo, ejercicio) in :const:`SCHEMA_REGISTRY`, the
produce → verify → diff-against-self loop must complete with
zero exit codes:

1. ``aeat submission export <draft>`` writes a byte-exact
   fichero-BOE file.
2. ``aeat submission verify <file> --json`` decodes the file
   back through the matching schema without raising.
3. ``aeat submission diff <file> <file> --json`` reports the
   file identical to itself (status=identical).

A registry entry whose module / build_headers / kind combination
is internally inconsistent would slip past the wave-123 unit-
level checks but fail here — this test exercises the full command
dispatch the same way Kent's shell does.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from . import app
from ._schema_registry import SCHEMA_REGISTRY

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]

_runner = CliRunner()

_REGISTRY_IDS = [f"{m}-{e}" for (m, e) in sorted(SCHEMA_REGISTRY.keys())]
_REGISTRY_KEYS = sorted(SCHEMA_REGISTRY.keys())


def _ejercicio_to_period(ejercicio: str) -> str:
    """Q1 of the target ejercicio as a canonical ``YYYYQ1`` token."""
    return f"{ejercicio}Q1"


def _write_draft(tmp_path: Path, *, modelo: str, period: str) -> Path:
    """Minimal valid draft JSON exercising casilla 01 only — enough to
    satisfy the serialiser's required-header check without requiring
    modelo-specific knowledge of cascade rules."""
    payload = {
        "draft_id": f"SMOKE-{modelo}-{period}",
        "modelo": modelo,
        "period": period,
        "profile_tax_id": "X1234567L",
        "status": "DRAFT",
        "values": {"01": "10000.00"},
        "findings": [],
    }
    draft_path = tmp_path / f"draft-{modelo}-{period}.json"
    draft_path.write_text(json.dumps(payload), encoding="utf-8")
    return draft_path


@pytest.mark.parametrize(("modelo", "ejercicio"), _REGISTRY_KEYS, ids=_REGISTRY_IDS)
def test_registered_schema_round_trips_through_cli(tmp_path: Path, modelo: str, ejercicio: str) -> None:
    """Every registered schema must export, re-verify, and self-diff clean.

    Uses ``--json`` on verify + diff so we assert on the machine-readable
    status field rather than grep-matching rich-formatted output.
    """
    period = _ejercicio_to_period(ejercicio)
    draft_path = _write_draft(tmp_path, modelo=modelo, period=period)
    output_dir = tmp_path / "out"

    # 1. export
    export_result = _runner.invoke(
        app,
        [
            "export",
            str(draft_path),
            "--output-dir",
            str(output_dir),
            "--nombre",
            "KENT",
            "--apellidos",
            "DOE",
            "--tipo",
            "I",
        ],
    )
    assert export_result.exit_code == 0, (
        f"export failed for modelo={modelo} ejercicio={ejercicio}: {export_result.stdout}"
    )
    # Canonical filename {NIF}{YYYY}{PERIODO}.{modelo}
    output_file = output_dir / f"X1234567L{ejercicio}1T.{modelo}"
    assert output_file.exists(), f"expected output file {output_file} not written"
    payload = output_file.read_bytes()
    assert payload.endswith(b"\r\n"), "fichero-BOE payload missing CRLF terminator"

    # 2. verify
    verify_result = _runner.invoke(app, ["verify", str(output_file), "--json"])
    assert verify_result.exit_code == 0, f"verify failed for {output_file.name}: {verify_result.stdout}"
    verify_doc = json.loads(verify_result.stdout)
    assert verify_doc["status"] == "ok"
    assert verify_doc["modelo"] == modelo
    assert verify_doc["ejercicio"] == ejercicio

    # 3. diff against self — must report identical
    diff_result = _runner.invoke(app, ["diff", str(output_file), str(output_file), "--json"])
    assert diff_result.exit_code == 0, f"self-diff failed: {diff_result.stdout}"
    diff_doc = json.loads(diff_result.stdout)
    assert diff_doc["status"] == "identical"
    assert diff_doc["bytes"] == len(payload)
    assert diff_doc["casilla_deltas"] == []
    assert diff_doc["field_deltas"] == []
