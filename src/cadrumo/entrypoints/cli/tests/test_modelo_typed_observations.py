"""CLI modelo typed observation parsing tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_VALID_COUNTERPART = (
    '{"source_kind": "ledger_transaction", "source_object_id": "ctr-001",'
    ' "counterparty_nif": "B00000001", "counterparty_name": "Cliente SL",'
    ' "counterparty_country": "ES", "operation_kind": "entregas_y_prestaciones",'
    ' "operation_period": "0A", "taxable_base": "2000.00",'
    ' "invoice_total": "2000.00", "accrued_on": "2025-03-01"}'
)

_COUNTERPART_WITHOUT_COUNTRY = (
    '{"source_kind": "ledger_transaction", "source_object_id": "ctr-001",'
    ' "counterparty_nif": "B00000001", "counterparty_name": "Cliente SL",'
    ' "operation_kind": "entregas_y_prestaciones", "operation_period": "0A",'
    ' "taxable_base": "2000.00", "invoice_total": "2000.00", "accrued_on": "2025-03-01"}'
)

# ---------------------------------------------------------------------------
# contract -- _parse_typed_cli_observations typed-boundary warmup
# ---------------------------------------------------------------------------


def test_parse_typed_cli_observations_round_trips_valid_json() -> None:
    """A valid JSON object is parsed into the typed model with all fields preserved."""
    from decimal import Decimal

    from ....application.aggregation.counterpart import CounterpartObservation
    from ....core.aggregation import BindingSourceKind
    from .._modelo_aggregate_cli import _parse_typed_cli_observations

    result = _parse_typed_cli_observations(
        [_VALID_COUNTERPART], model=CounterpartObservation, flag="--counterpart-observation"
    )

    assert len(result) == 1
    obs = result[0]
    assert isinstance(obs, CounterpartObservation)
    assert obs.source_kind == BindingSourceKind.LEDGER_TRANSACTION
    assert obs.source_object_id == "ctr-001"
    assert obs.counterparty_nif == "B00000001"
    assert obs.counterparty_name == "Cliente SL"
    assert obs.counterparty_country == "ES"
    assert obs.taxable_base == Decimal("2000.00")
    assert obs.accrued_on == "2025-03-01"


def test_parse_typed_cli_observations_rejects_invalid_json_syntax() -> None:
    """A string that is not valid JSON raises ``typer.BadParameter``."""
    import typer

    from ....application.aggregation.counterpart import CounterpartObservation
    from .._modelo_aggregate_cli import _parse_typed_cli_observations

    with pytest.raises(typer.BadParameter):
        _parse_typed_cli_observations(["{not: json}"], model=CounterpartObservation, flag="--counterpart-observation")


def test_parse_typed_cli_observations_rejects_non_object_json() -> None:
    """A JSON value that is not an object (e.g. an array) raises ``typer.BadParameter``."""
    import typer

    from ....application.aggregation.counterpart import CounterpartObservation
    from .._modelo_aggregate_cli import _parse_typed_cli_observations

    with pytest.raises(typer.BadParameter):
        _parse_typed_cli_observations(
            ['["not", "an", "object"]'],
            model=CounterpartObservation,
            flag="--counterpart-observation",
        )


def test_parse_typed_cli_observations_rejects_schema_violation() -> None:
    """A JSON object that fails pydantic validation raises ``typer.BadParameter``.

    An object missing the required ``counterparty_country`` field must be
    refused with a typed validation message, not a bare pydantic traceback.
    """
    import typer

    from ....application.aggregation.counterpart import CounterpartObservation
    from .._modelo_aggregate_cli import _parse_typed_cli_observations

    with pytest.raises(typer.BadParameter, match="counterparty_country: Field required"):
        _parse_typed_cli_observations(
            [_COUNTERPART_WITHOUT_COUNTRY], model=CounterpartObservation, flag="--counterpart-observation"
        )


def test_cli_counterpart_observation_schema_violation_is_argument_validation(tmp_path: Path) -> None:
    """A malformed counterpart observation is refused as a CLI argument error.

    ``aeat app modelo aggregate`` sits behind the profile-bound write guard,
    which runs ahead of the command body that parses
    ``--counterpart-observation``, so the run needs a real active profile:
    without one the guard's no-active-profile refusal preempts the argument
    error this test exists to pin.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
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
