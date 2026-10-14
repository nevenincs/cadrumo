"""CLI modelo typed observation parsing tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from .cli_runner import invoke_cached_cli
from .runtime_profile_backend import runtime_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_COUNTERPART_WITHOUT_COUNTRY = (
    '{"source_kind": "ledger_transaction", "source_object_id": "ctr-001",'
    ' "counterparty_nif": "B00000001", "counterparty_name": "Cliente SL",'
    ' "operation_kind": "entregas_y_prestaciones", "operation_period": "0A",'
    ' "taxable_base": "2000.00", "invoice_total": "2000.00", "accrued_on": "2025-03-01"}'
)


# ---------------------------------------------------------------------------
# contract -- _parse_typed_cli_observations typed-boundary warmup
# ---------------------------------------------------------------------------


def test_cli_counterpart_observation_schema_violation_is_argument_validation(tmp_path: Path) -> None:
    """A malformed counterpart observation is refused as a CLI argument error.

    ``aeat app modelo aggregate`` sits behind the profile-bound write guard,
    which runs ahead of the command body that parses
    ``--counterpart-observation``, so the run needs a real active profile:
    without one the guard's no-active-profile refusal preempts the argument
    error this test exists to pin.
    """
    with runtime_cli_profile(tmp_path=tmp_path):
        result = invoke_cached_cli(
            [
                "--language",
                "en",
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                "347",
                "--year",
                "2024",
                "--period",
                "0A",
                "--counterpart-observation",
                _COUNTERPART_WITHOUT_COUNTRY,
            ],
        )

    assert result.exit_code == 2, result.output
    assert "Invalid value" in result.output
    assert "--counterpart-observation" in result.output
    assert "not a valid" in result.output
    assert "observation object" in result.output
    assert "counterparty_country: Field required" in result.output
    assert "config repair" not in result.output
    assert "no longer matches the expected schema" not in result.output
