"""CLI surface tests for ``aeat app ledger preflight``."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    from ....application.user_profile._orchestration import profile_create_storage_span
    from ....application.user_profile._testing import register_minimal_profile
    from ....application.workflow._persistence import workflow_state_repository

    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="operator"),
        )
        yield


def test_preflight_requires_period_flag() -> None:
    """The verb requires --period; missing it surfaces as a Typer usage error."""

    result = _invoke(["app", "ledger", "preflight", "--year", "2026"])
    assert result.exit_code != 0, result.output


def test_preflight_empty_catalogue_is_ready() -> None:
    """An active bucket with no transactions stays ready but warns that zero is an operator assertion."""

    result = _invoke(["app", "ledger", "preflight", "--period", "1T", "--year", "2026"])
    assert result.exit_code == 0, result.output
    assert "checked\t0" in result.output
    assert "issues\t0" in result.output
    assert "ready\ttrue" in result.output
    assert "advisory\tempty_ledger" in result.output
    assert "aeat app ledger add --help" in result.output
    assert "aeat app ledger import --help" in result.output


def test_preflight_empty_catalogue_json_notice_marks_warning() -> None:
    """The empty-ledger advisory is part of the JSON envelope, not only text output."""

    result = _invoke(["--format", "json", "app", "ledger", "preflight", "--period", "1T", "--year", "2026"])

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == "warning", envelope
    assert envelope["result"]["ready"] is True, envelope
    assert envelope["result"]["checked_transaction_count"] == 0, envelope
    notice = envelope["notices"][0]
    assert notice["severity"] == "warning"
    assert notice["code"] == "ledger.preflight.empty_period"
    assert notice["suggestion"] == "aeat app ledger add --help; aeat app ledger import --help"
    assert notice["context"] == {"period": "1T", "year": "2026"}


def test_preflight_rejects_malformed_period() -> None:
    """A period that does not match the canonical regex is rejected
    before the application service is reached."""

    result = _invoke(["app", "ledger", "preflight", "--period", "not-a-period", "--year", "2026"])
    assert result.exit_code != 0, result.output


def test_preflight_help_advertises_local_only() -> None:
    """Help text must signal `local-only` so the operator cannot mistake
    the verb for an AEAT-contacting probe."""

    result = _invoke(["app", "ledger", "preflight", "--help"])
    assert result.exit_code == 0, result.output
    assert any(token in result.output.lower() for token in ("local-only", "local;", "nunca", "csak helyi")), (
        result.output
    )


def test_status_period_readiness_issues_include_tax_diagnostic_fields() -> None:
    add = _invoke(
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

    result = _invoke(["app", "ledger", "status", "--period", "05", "--year", "2026"])

    assert result.exit_code == 0, result.output
    assert "Ready\tFalse" in result.output or "ready\tFalse" in result.output
    assert "readiness_issue\t" in result.output
    assert "classification=BUSINESS" in result.output or "classification=business" in result.output
    assert "category_id=-" in result.output
    assert "taxable_base=-" in result.output
    assert "iva_rate=-" in result.output
    assert "iva_amount=-" in result.output
    assert "reason=missing_category" in result.output


def test_status_money_totals_are_labelled_as_business_scope() -> None:
    business = _invoke(
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
            "business expense",
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.00",
            "--category-id",
            "material_oficina",
            "--idempotency-key",
            "status-business-scope",
        ],
    )
    assert business.exit_code == 0, business.output
    personal = _invoke(
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-03",
            "--amount",
            "900.00",
            "--direction",
            "OUTGOING",
            "--description",
            "personal rent",
            "--classification",
            "PERSONAL",
            "--idempotency-key",
            "status-personal-excluded",
        ],
    )
    assert personal.exit_code == 0, personal.output

    result = _invoke(["app", "ledger", "status", "--period", "05", "--year", "2026"])

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert "business_expense_total\t121" in lines
    assert "business_net_total\t-121" in lines
    assert not any(line.startswith("expense_total\t") for line in lines)
    assert not any(line.startswith("net_total\t") for line in lines)
    assert "900" not in result.output
