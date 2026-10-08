"""Portable help and operator-token checks for the maritime preview leaf."""

from __future__ import annotations

import pytest
import typer

from .._modelo_maritime_cli import _parse_maritime_amounts
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class TestHelpSurfaceLocalisation:
    """Verb help renders in the operator's locale, not as a translation key."""

    @pytest.mark.parametrize(
        ("language", "expected"),
        [("es", "trabajador del mar"), ("en", "Art. 7.p")],
    )
    def test_help_renders_localized_maritime_description(self, language: str, expected: str) -> None:
        result = invoke_cached_cli(
            ["--language", language, "app", "modelo", "work", "preview-maritime-exemption", "--help"],
        )
        assert result.exit_code == 0, result.output
        assert "preview_maritime_exemption_help" not in result.output
        assert expected in result.output or "REBECA" in result.output


class TestAmountGrammarRefusal:
    """The frontend amount parser rejects tokens before submitting to the worker."""

    @pytest.mark.parametrize(
        "raw_amount",
        ["1e3", "+36500", "36.500", "36.500,00", "36500,00", "3 6500", "NaN", "Infinity"],
    )
    def test_non_canonical_annual_salary_refuses(self, raw_amount: str) -> None:
        with pytest.raises(typer.BadParameter) as refusal:
            _parse_maritime_amounts(annual_salary=raw_amount, gross_navigation_income=None)
        assert "--annual-salary" in str(refusal.value)

    @pytest.mark.parametrize("raw_amount", ["1e3", "+36500", "36.500", "36500,00"])
    def test_non_canonical_navigation_income_refuses(self, raw_amount: str) -> None:
        with pytest.raises(typer.BadParameter) as refusal:
            _parse_maritime_amounts(annual_salary=None, gross_navigation_income=raw_amount)
        assert "--gross-navigation-income" in str(refusal.value)
