"""Real-CLI coverage for ledger source-jurisdiction export fidelity."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RUNNER = CliRunner()
_PROFILE_ID = "source-jurisdiction-export"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_PROFILE_ID),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id=_PROFILE_ID,
                overrides={
                    "taxpayer_type.fiscal_residency": "non_resident_irnr",
                    "taxpayer_type.country_of_fiscal_residence": "GB",
                    "taxpayer_type.representante_fiscal_nif": "12345678Z",
                    "taxpayer_type.representante_fiscal_nombre": "Test Representative",
                },
            ),
        )
        try:
            yield
        finally:
            dispose_engine()


def _add_manual_row(*, date: str, description: str, source_jurisdiction: str) -> str:
    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            date,
            "--amount",
            "100.00",
            "--direction",
            "INCOMING",
            "--description",
            description,
            "--source-jurisdiction",
            source_jurisdiction,
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["result"]["transaction_id"]


def _export_rows(tmp_path: Path, export_format: str) -> list[dict[str, str]]:
    output = tmp_path / f"ledger-source-jurisdiction.{export_format}"
    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "export", "--output", str(output), "--export-format", export_format],
    )
    assert result.exit_code == 0, result.output
    if export_format == "csv":
        with output.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    return [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize("export_format", ["csv", "jsonl"])
def test_non_resident_add_source_jurisdiction_reaches_canonical_exports(
    tmp_path: Path,
    export_format: str,
) -> None:
    """IRNR explicit source jurisdictions survive add through canonical export."""
    expected = {
        "Spanish-source rent": "ES",
        "German-source rent": "DE",
        "French-source rent": "FR",
    }
    for index, (description, jurisdiction) in enumerate(expected.items(), start=1):
        _add_manual_row(
            date=f"2026-04-0{index}",
            description=description,
            source_jurisdiction=jurisdiction,
        )

    rows = _export_rows(tmp_path, export_format)
    by_description = {row["description"]: row["source_jurisdiction"] for row in rows}
    assert by_description == expected


@pytest.mark.parametrize("export_format", ["csv", "jsonl"])
def test_import_csv_source_jurisdiction_reaches_canonical_exports(
    tmp_path: Path,
    export_format: str,
) -> None:
    """Canonical import rows with source_jurisdiction keep that provenance on export."""
    statement = tmp_path / "with-source-jurisdiction.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID,source_jurisdiction\n"
        "2026-04-01,Client ES,Spanish consulting,100.00,EUR,source-es,ES\n"
        "2026-04-02,Client GB,UK consulting,200.00,EUR,source-gb,GB\n",
        encoding="utf-8",
    )

    imported = _RUNNER.invoke(app, ["app", "ledger", "import", str(statement), "--provider", "csv"])
    assert imported.exit_code == 0, imported.output

    rows = _export_rows(tmp_path, export_format)
    by_description = {row["description"]: row["source_jurisdiction"] for row in rows}
    assert by_description == {
        "Spanish consulting": "ES",
        "UK consulting": "GB",
    }
