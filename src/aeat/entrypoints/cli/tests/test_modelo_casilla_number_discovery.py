"""CLI discovery tests for casilla-number lookups."""

from __future__ import annotations

import pytest

from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_casillas_number_filter_finds_m100_employment_income_and_withholding() -> None:
    """Operators can find M100 employment boxes by the printed casilla number."""

    salary = invoke_cached_cli(
        [
            "--language",
            "en",
            "app",
            "modelo",
            "casillas",
            "100",
            "--year",
            "2025",
            "--period",
            "0A",
            "--number",
            "0003",
        ],
    )
    withholding = invoke_cached_cli(
        [
            "--language",
            "en",
            "app",
            "modelo",
            "casillas",
            "100",
            "--year",
            "2025",
            "--period",
            "0A",
            "--number",
            "0596",
        ],
    )

    assert salary.exit_code == 0, salary.output
    assert "0003\t0003\tmanual\tfalse\tRetribuciones dinerarias. Importe integro" in salary.output
    assert "0596" not in salary.output

    assert withholding.exit_code == 0, withholding.output
    assert "0596\t0596\tbound\tfalse\tPor rendimientos del trabajo" in withholding.output
    assert "0003" not in withholding.output


def test_casillas_number_filter_is_distinct_from_form_number_filter() -> None:
    """``--number`` covers casilla ids that ``--form-number`` does not."""

    by_casilla = invoke_cached_cli(
        ["app", "modelo", "casillas", "100", "--year", "2025", "--period", "0A", "--number", "0596"],
    )
    by_form = invoke_cached_cli(
        ["app", "modelo", "casillas", "100", "--year", "2025", "--period", "0A", "--form-number", "0596"],
    )

    assert by_casilla.exit_code == 0, by_casilla.output
    assert "0596\t0596\tbound" in by_casilla.output

    assert by_form.exit_code == 0, by_form.output
    data_rows = [
        line
        for line in by_form.output.splitlines()
        if line and not line.startswith("operation\t") and not line.startswith("casilla_id\t")
    ]
    assert data_rows == [], by_form.output
