"""Real CSV source entry into an amendable external Modelo baseline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....application.modelo.calculation_actions import get_calculation_revision
from ....tests.cli_envelope import unwrap_schema_envelope
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend
from ....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

__all__ = ["_isolated_cli_backend"]


def test_filing_record_import_file_uses_real_csv_parser_and_persists_lexicals(
    _isolated_cli_backend: Path,
    tmp_path: Path,
) -> None:
    profile_id = register_cli_profile(
        label="Issue 113 CSV operator",
        complete=False,
        facts={
            "identity.tax_id": "00000000T",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Issue",
            "identity.surnames": "Operator",
            "activities.description": "software",
        },
    )
    completed = invoke_cached_cli(["--format", "json", "config", "profile", "complete-setup"])
    assert completed.exit_code == 0, completed.output
    created = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "130",
            "--year",
            "2026",
            "--period",
            "1T",
        ],
    )
    assert created.exit_code == 0, created.output
    work_unit_id = unwrap_schema_envelope(created.output)["work_unit_id"]

    source = tmp_path / "m130-filed.csv"
    source.write_text("casilla_code;value\n01; 001500.00 \n02;300,0\n", encoding="utf-8")
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "filing-record",
            "import",
            work_unit_id,
            "--evidence-kind",
            "aeat_csv_register",
            "--evidence-id",
            "REALCSV23301",
            "--file",
            str(source),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = unwrap_schema_envelope(result.output)

    with open_test_profile_session(profile_id):
        revision = get_calculation_revision(payload["calculation_revision_id"])
        assert revision.input_values_by_casilla_id == {"01": " 001500.00 ", "02": "300,0"}
    assert json.loads(result.output)["status"] == "success"


def test_failed_csv_file_import_creates_no_filing_or_revision(
    _isolated_cli_backend: Path,
    tmp_path: Path,
) -> None:
    register_cli_profile(
        label="Issue 113 refused CSV",
        complete=False,
        facts={
            "identity.tax_id": "00000000T",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Issue",
            "identity.surnames": "Refusal",
            "activities.description": "software",
        },
    )
    completed = invoke_cached_cli(["--format", "json", "config", "profile", "complete-setup"])
    assert completed.exit_code == 0, completed.output
    created = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "130",
            "--year",
            "2026",
            "--period",
            "1T",
        ],
    )
    assert created.exit_code == 0, created.output
    work_unit_id = unwrap_schema_envelope(created.output)["work_unit_id"]
    partial = tmp_path / "partial.csv"
    partial.write_text("casilla_code;value\n01;1500\n", encoding="utf-8")

    refused = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "filing-record",
            "import",
            work_unit_id,
            "--evidence-kind",
            "aeat_csv_register",
            "--evidence-id",
            "PARTIALCSV113",
            "--file",
            str(partial),
        ],
    )
    assert refused.exit_code != 0
    filings = invoke_cached_cli(["--format", "json", "app", "modelo", "filing-record", "list"])
    assert filings.exit_code == 0, filings.output
    assert unwrap_schema_envelope(filings.output)["record_count"] == 0
    status = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "status", work_unit_id],
    )
    assert status.exit_code == 0, status.output
    status_payload = unwrap_schema_envelope(status.output)
    assert status_payload["current_calculation_revision_id"] is None
    assert status_payload["current_filing_record_id"] is None
