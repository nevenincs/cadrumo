"""Real CSV source entry into an amendable external Modelo baseline."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....application.modelo import create_work_unit, get_calculation_revision
from ....application.modelo.tests._import_flow_support import _T1, _seed_ready_profile
from ....application.modelo.tests.justificante_metadata import persist_justificante_metadata
from ....core import Period
from ....tests.cli_envelope import unwrap_schema_envelope
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "23323323-2332-4332-8332-233233233233"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID, label="Issue 233 CSV import") as profile:
        yield profile


def test_filing_record_import_file_uses_real_csv_parser_and_persists_lexicals(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    with open_test_profile_session(runtime_profile.bucket_id):
        _seed_ready_profile(bucket_id=runtime_profile.bucket_id)
        work_unit = create_work_unit(
            bucket_id=runtime_profile.bucket_id,
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id="2019-y-siguientes",
            clock=_T1,
        )
        persist_justificante_metadata(
            "REALCSV23301",
            modelo="130",
            filing_year=2026,
            period="1T",
            captured_at=_T1,
            tax_id="00000000T",
        )

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
            work_unit.work_unit_id,
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

    with open_test_profile_session(runtime_profile.bucket_id):
        revision = get_calculation_revision(payload["calculation_revision_id"])
        assert revision.input_values_by_casilla_id == {"01": " 001500.00 ", "02": "300,0"}
    assert json.loads(result.output)["status"] == "success"
