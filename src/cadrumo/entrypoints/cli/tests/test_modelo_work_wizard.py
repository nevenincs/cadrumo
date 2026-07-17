"""Real terminal-boundary coverage for ``aeat app modelo work wizard``."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401
from ._m130_source_support import seed_m130_expense_transaction, seed_m130_income_transaction
from ._modelo_work_ux_support import _create_m130_work_unit

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _create_profile() -> None:
    result = _invoke(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--irpf-income-categories",
            "actividad_economica",
            "--tax-id",
            "12345678Z",
            "--name",
            "Operator",
            "--surnames",
            "Wizard",
            "--activity",
            "design",
        ],
    )
    assert result.exit_code == 0, result.output


def test_wizard_non_interactive_host_refuses_with_instructive_message() -> None:
    """A real non-TTY invocation refuses before attempting an interactive prompt."""
    _create_profile()
    seed_m130_income_transaction(
        amount=Decimal("3000.00"),
        filing_year=2025,
        source_key="wizard-non-interactive",
    )
    seed_m130_expense_transaction(
        amount=Decimal("600.00"),
        filing_year=2025,
        source_key="wizard-non-interactive",
    )
    work_unit_id = _create_m130_work_unit()

    result = _invoke(["--format", "json", "app", "modelo", "work", "wizard", work_unit_id])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "interactive" in result.output.lower() or "console" in result.output.lower()
