"""Unit tests for the structure of the ``aeat cloud`` sub-app.

The Cloud Functions / Run / Storage commands themselves require live
credentials and are exercised by the smoke suite. Here we only
verify the typer command-tree shape so a refactor that drops a verb is
caught at unit-test time.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from .cloud import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


class TestCloudCommandTree:
    """The cloud sub-app must expose every documented verb."""

    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_top_level_help_lists_subapps(self) -> None:
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "functions" in result.stdout
        assert "run" in result.stdout
        assert "storage" in result.stdout

    def test_functions_help_lists_verbs(self) -> None:
        result = self.runner.invoke(app, ["functions", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "describe" in result.stdout

    def test_run_help_lists_verbs(self) -> None:
        result = self.runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "describe" in result.stdout

    def test_storage_help_lists_verbs(self) -> None:
        result = self.runner.invoke(app, ["storage", "--help"])
        assert result.exit_code == 0
        assert "buckets" in result.stdout
        assert "ls" in result.stdout
