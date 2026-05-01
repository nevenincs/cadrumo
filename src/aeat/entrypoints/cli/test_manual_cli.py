"""Smoke tests for the ``aeat manual`` CLI surface."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from ...domain.manuals.errors import RuleExtractionError
from . import app
from ._errors import error_boundary_under_test

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_runner = CliRunner()


class TestManualCli:
    """CLI subcommands are reachable and the planned-blocker shape holds."""

    def test_manual_help_lists_all_subcommands(self) -> None:
        """`aeat manual --help` enumerates every v1 subcommand."""
        result = _runner.invoke(app, ["manual", "--help"])
        assert result.exit_code == 0, result.output
        for name in ("fetch", "structure", "extract-rules", "translate", "verify", "list", "show"):
            assert name in result.output

    def test_structure_command_raises_pending_21(self) -> None:
        """`aeat manual structure` raises RuleExtractionError referencing #21."""
        with error_boundary_under_test():
            result = _runner.invoke(
                app,
                ["manual", "structure", "--manual", "iva", "--year", "2025"],
            )
        assert result.exit_code != 0
        assert isinstance(result.exception, RuleExtractionError)
        assert "#21" in str(result.exception)

    def test_extract_rules_command_raises_pending_21(self) -> None:
        """`aeat manual extract-rules` raises RuleExtractionError referencing #21."""
        with error_boundary_under_test():
            result = _runner.invoke(
                app,
                [
                    "manual",
                    "extract-rules",
                    "--manual",
                    "iva",
                    "--year",
                    "2025",
                    "--section",
                    "sec1",
                ],
            )
        assert result.exit_code != 0
        assert isinstance(result.exception, RuleExtractionError)

    def test_translate_command_raises_pending_21(self) -> None:
        """`aeat manual translate` raises RuleExtractionError referencing #21."""
        with error_boundary_under_test():
            result = _runner.invoke(
                app,
                [
                    "manual",
                    "translate",
                    "--manual",
                    "iva",
                    "--year",
                    "2025",
                    "--section",
                    "sec1",
                ],
            )
        assert result.exit_code != 0
        assert isinstance(result.exception, RuleExtractionError)

    def test_fetch_rejects_unknown_manual(self) -> None:
        """Invalid --manual triggers a typer BadParameter exit."""
        result = _runner.invoke(
            app,
            ["manual", "fetch", "--manual", "sociedades", "--year", "2025"],
        )
        assert result.exit_code != 0
        assert "unknown manual" in result.output or "sociedades" in result.output
