"""CLI surface tests for ``aeat app ledger preflight``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="operator"),
        )
        yield


def test_preflight_requires_period_flag(cli_runner: CliRunner) -> None:
    """The verb requires --period; missing it surfaces as a Typer usage error."""

    result = cli_runner.invoke(app, ["app", "ledger", "preflight", "--year", "2026"])
    assert result.exit_code != 0, result.output


def test_preflight_empty_catalogue_is_ready(cli_runner: CliRunner) -> None:
    """An active bucket with no transactions reports ready=true and 0 issues."""

    result = cli_runner.invoke(app, ["app", "ledger", "preflight", "--period", "1T", "--year", "2026"])
    assert result.exit_code == 0, result.output
    assert "checked\t0" in result.output
    assert "issues\t0" in result.output
    assert "ready\ttrue" in result.output


def test_preflight_rejects_malformed_period(cli_runner: CliRunner) -> None:
    """A period that does not match the canonical regex is rejected
    before the application service is reached."""

    result = cli_runner.invoke(app, ["app", "ledger", "preflight", "--period", "not-a-period", "--year", "2026"])
    assert result.exit_code != 0, result.output


def test_preflight_help_advertises_local_only(cli_runner: CliRunner) -> None:
    """Help text must signal `local-only` so the operator cannot mistake
    the verb for an AEAT-contacting probe."""

    result = cli_runner.invoke(app, ["app", "ledger", "preflight", "--help"])
    assert result.exit_code == 0, result.output
    assert any(token in result.output.lower() for token in ("local-only", "local;", "nunca", "csak helyi")), (
        result.output
    )


def test_status_period_readiness_issues_include_tax_diagnostic_fields(cli_runner: CliRunner) -> None:
    add = cli_runner.invoke(
        app,
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-02",
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            "classified but tax facts missing",
            "--classification",
            "BUSINESS",
            "--idempotency-key",
            "status-tax-diagnostics",
        ],
    )
    assert add.exit_code == 0, add.output

    result = cli_runner.invoke(app, ["app", "ledger", "status", "--period", "05", "--year", "2026"])

    assert result.exit_code == 0, result.output
    assert "Ready\tFalse" in result.output or "ready\tFalse" in result.output
    assert "readiness_issue\t" in result.output
    assert "classification=BUSINESS" in result.output or "classification=business" in result.output
    assert "category_id=-" in result.output
    assert "taxable_base=-" in result.output
    assert "iva_rate=-" in result.output
    assert "iva_amount=-" in result.output
    assert "reason=missing_category" in result.output
