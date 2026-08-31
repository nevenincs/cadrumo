"""CLI ``--file`` spreadsheet import for local filed observations.

A cert-free path: a hand-authored CSV or XLSX spreadsheet of
``casilla_code, value`` rows reconstructs a past filing's casilla values into a
non-official local observation, without any AEAT certificate or live pull.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from ....application.calculations._binding_prefill import resolve_bindings_from_local_store
from ....application.calculations.observations_repository import CalculationObservationRepository
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....tests.cli_envelope import unwrap_envelope_notices, unwrap_schema_envelope
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SPREADSHEET_OBSERVATION_PROFILE_ID = "35353535-3535-4535-8535-353535353535"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Real active encrypted profile storage for the spreadsheet-import CLI tests."""
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_SPREADSHEET_OBSERVATION_PROFILE_ID,
        label="Spreadsheet local observation CLI test",
    ) as profile:
        yield profile


def test_observe_local_from_csv_spreadsheet_persists_non_official_observation(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    """A CSV spreadsheet of casilla_code,value rows imports through ``--file``.

    Drives the real CLI, persists into the real encrypted observation store,
    and confirms the stamped source kind stays non-official
    (``no-silent-under-declaration``) while still
    feeding the ``previous_filing`` calculation-prefill resolver.
    """
    sheet = tmp_path / "m100-2024.csv"
    sheet.write_text(
        "casilla_code,value\n1391,0\n0224,0\n1479,0\n1553,0\n1577,0\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "filing-record",
            "observe-local",
            "--modelo",
            "100",
            "--year",
            "2024",
            "--period",
            "0A",
            "--by",
            "operator-spreadsheet",
            "--file",
            str(sheet),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == "warning"
    payload = unwrap_schema_envelope(result.output)
    assert payload["operation"] == "modelo.filing_record.observe_local"
    assert payload["observation_key"] == "100:2024:0A"
    assert payload["source_kind"] == "operator_manual"
    assert payload["official_evidence"] is False
    assert payload["filing_record_created"] is False
    assert payload["aeat_accepted"] is False
    assert payload["casilla_values"] == {
        "0224": "0",
        "1391": "0",
        "1479": "0",
        "1553": "0",
        "1577": "0",
    }
    notices = unwrap_envelope_notices(result.output)
    assert [notice["code"] for notice in notices] == ["modelo.filing_record.observe_local.non_official"]

    with open_test_profile_session(runtime_profile.bucket_id):
        repository = CalculationObservationRepository()
        observed = repository.load_observation("100", Period.from_year_and_code(2024, "0A"))
        assert observed is not None
        # non-official regardless of --set vs --file transport
        assert observed.source_kind == "operator_manual"
        assert observed.observation.casilla_values["1391"] == Decimal("0")

        m100_snapshot = bundled_authority().snapshot("100", filing_year=2025, period="0A")
        m100_prefill = resolve_bindings_from_local_store(m100_snapshot, repository=repository)
        assert m100_prefill.binding_values["renta-2025-base-liquidable-negativa-general-anterior"] == Decimal("0")


def test_observe_local_from_xlsx_spreadsheet_persists_values(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    """An XLSX spreadsheet of casilla_code,value rows imports identically to CSV."""
    sheet = tmp_path / "m100-2024.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.append(["casilla_code", "value"])
    worksheet.append(["1391", 100])
    worksheet.append(["0224", 25.5])
    workbook.save(sheet)

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "filing-record",
            "observe-local",
            "--modelo",
            "100",
            "--year",
            "2023",
            "--period",
            "0A",
            "--by",
            "operator-spreadsheet-xlsx",
            "--file",
            str(sheet),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = unwrap_schema_envelope(result.output)
    assert payload["source_kind"] == "operator_manual"
    assert payload["casilla_values"] == {"0224": "25.5", "1391": "100"}


def test_observe_local_set_overrides_file_value_for_same_casilla(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    """A ``--set`` flag for a casilla already present in ``--file`` wins."""
    sheet = tmp_path / "m100-2024.csv"
    sheet.write_text("casilla_code,value\n1391,0\n", encoding="utf-8")

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "filing-record",
            "observe-local",
            "--modelo",
            "100",
            "--year",
            "2022",
            "--period",
            "0A",
            "--by",
            "operator-override",
            "--file",
            str(sheet),
            "--set",
            "1391=42",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = unwrap_schema_envelope(result.output)
    assert payload["casilla_values"] == {"1391": "42"}


def test_observe_local_rejects_invalid_casilla_code_in_spreadsheet(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    """A spreadsheet row with an invalid casilla_code surfaces a readable CLI error."""
    sheet = tmp_path / "bad.csv"
    sheet.write_text("casilla_code,value\n???not-valid???,10\n", encoding="utf-8")

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "filing-record",
            "observe-local",
            "--modelo",
            "100",
            "--year",
            "2021",
            "--period",
            "0A",
            "--file",
            str(sheet),
        ],
    )
    assert result.exit_code != 0
    assert "not a valid CasillaId" in result.output


def test_observe_local_rejects_non_numeric_spreadsheet_value(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    """A spreadsheet row with a non-numeric value cites the offending row."""
    sheet = tmp_path / "bad.csv"
    sheet.write_text("casilla_code,value\n1391,not-a-number\n", encoding="utf-8")

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "filing-record",
            "observe-local",
            "--modelo",
            "100",
            "--year",
            "2020",
            "--period",
            "0A",
            "--file",
            str(sheet),
        ],
    )
    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["category"] == "REFUSED"
    # Structural, not prose: the refusal must cite the offending row by the data
    # this test supplied -- the casilla code and the rejected value. Asserting a
    # phrase from the message itself pins localized wording, which drifts on any
    # rewording or locale switch while the behaviour stays correct.
    assert "1391" in error["message"]
    assert "not-a-number" in error["message"]


def test_observe_local_requires_set_or_file(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Neither ``--set`` nor ``--file`` supplied is refused with a clear error."""
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "filing-record",
            "observe-local",
            "--modelo",
            "100",
            "--year",
            "2024",
            "--period",
            "0A",
        ],
    )
    assert result.exit_code != 0
    assert "--set" in result.output
    assert "--file" in result.output
