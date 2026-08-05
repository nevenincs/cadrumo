"""CLI modelo typed observation parsing tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# ---------------------------------------------------------------------------
# contract -- _parse_typed_cli_observations typed-boundary warmup
# ---------------------------------------------------------------------------


def test_parse_typed_cli_observations_round_trips_valid_json() -> None:
    """A valid JSON object is parsed into the typed model with all fields preserved."""
    import typer as _typer

    from ....application.aggregation import RetencionObservation
    from ....core.aggregation import RetencionScheme
    from .._modelo_aggregate_cli import _parse_typed_cli_observations

    raw = (
        '{"source_kind": "ledger_transaction", "source_object_id": "txn-001",'
        ' "perceptor_nif": "A12345678", "perceptor_name": "Empresa SL",'
        ' "scheme": "rendimientos_trabajo", "taxable_base": "1000.00",'
        ' "retencion_amount": "190.00", "accrued_on": "2024-01-15"}'
    )
    result = _parse_typed_cli_observations([raw], model=RetencionObservation, flag="--retencion-observation")

    assert len(result) == 1
    obs = result[0]
    assert isinstance(obs, RetencionObservation)
    assert obs.source_kind == "ledger_transaction"
    assert obs.source_object_id == "txn-001"
    assert obs.perceptor_nif == "A12345678"
    assert obs.perceptor_name == "Empresa SL"
    assert obs.scheme == RetencionScheme.WORK_INCOME
    assert obs.accrued_on == "2024-01-15"
    _ = _typer  # ensure import is referenced


def test_parse_typed_cli_observations_rejects_invalid_json_syntax() -> None:
    """A string that is not valid JSON raises ``typer.BadParameter``."""
    import typer as _typer

    from ....application.aggregation import RetencionObservation
    from .._modelo_aggregate_cli import _parse_typed_cli_observations

    with pytest.raises(_typer.BadParameter):
        _parse_typed_cli_observations(["{not: json}"], model=RetencionObservation, flag="--retencion-observation")


def test_parse_typed_cli_observations_rejects_non_object_json() -> None:
    """A JSON value that is not an object (e.g. an array) raises ``typer.BadParameter``."""
    import typer as _typer

    from ....application.aggregation import RetencionObservation
    from .._modelo_aggregate_cli import _parse_typed_cli_observations

    with pytest.raises(_typer.BadParameter):
        _parse_typed_cli_observations(
            ['["not", "an", "object"]'],
            model=RetencionObservation,
            flag="--retencion-observation",
        )


def test_parse_typed_cli_observations_rejects_schema_violation() -> None:
    """A JSON object that fails pydantic validation raises ``typer.BadParameter``.

    An object missing the required ``scheme`` field must be refused with a
    typed validation message, not a bare pydantic traceback.
    """
    import typer as _typer

    from ....application.aggregation import RetencionObservation
    from .._modelo_aggregate_cli import _parse_typed_cli_observations

    missing_scheme = (
        '{"source_kind": "ledger_transaction", "source_object_id": "txn-001",'
        ' "perceptor_nif": "A12345678", "taxable_base": "1000.00",'
        ' "retencion_amount": "190.00", "accrued_on": "2024-01-15"}'
    )
    with pytest.raises(_typer.BadParameter):
        _parse_typed_cli_observations([missing_scheme], model=RetencionObservation, flag="--retencion-observation")


def test_cli_retencion_observation_schema_violation_is_argument_validation(tmp_path: Path) -> None:
    """A malformed retencion observation is refused as a CLI argument error.

    ``aeat app modelo aggregate`` persists observations, so it sits behind the
    profile-bound write guard. The guard runs ahead of the command body that
    parses ``--retencion-observation``, so the run needs a real active profile:
    without one the guard's no-active-profile refusal preempts the argument
    error this test exists to pin.
    """

    missing_scheme = (
        '{"source_kind": "ledger_transaction", "source_object_id": "txn-001",'
        ' "perceptor_nif": "A12345678", "taxable_base": "1000.00",'
        ' "retencion_amount": "190.00", "accrued_on": "2024-01-15"}'
    )

    with isolated_runtime_profile(tmp_path=tmp_path):
        result = invoke_cached_cli(
            [
                "--language",
                "en",
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                "111",
                "--year",
                "2024",
                "--period",
                "1T",
                "--retencion-observation",
                missing_scheme,
            ],
        )

    assert result.exit_code == 2, result.output
    assert "Invalid value" in result.output
    assert "--retencion-observation" in result.output
    assert "not a valid" in result.output
    assert "observation object" in result.output
    assert "scheme: Field required" in result.output
    assert "config repair" not in result.output
    assert "no longer matches the expected schema" not in result.output
