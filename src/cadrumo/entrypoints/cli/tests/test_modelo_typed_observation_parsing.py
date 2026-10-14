"""Typed CLI observation parsing retains schema refusals."""

from __future__ import annotations

import pytest

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


def test_parse_typed_cli_observations_round_trips_valid_json() -> None:
    """A valid JSON object is parsed into the typed model with all fields preserved."""
    from decimal import Decimal

    from cadrumo.application.aggregation.counterpart import CounterpartObservation
    from cadrumo.core.aggregation import BindingSourceKind
    from cadrumo.entrypoints.cli._modelo_aggregate_cli import _parse_typed_cli_observations

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

    from cadrumo.application.aggregation.counterpart import CounterpartObservation
    from cadrumo.entrypoints.cli._modelo_aggregate_cli import _parse_typed_cli_observations

    with pytest.raises(typer.BadParameter):
        _parse_typed_cli_observations(["{not: json}"], model=CounterpartObservation, flag="--counterpart-observation")


def test_parse_typed_cli_observations_rejects_non_object_json() -> None:
    """A JSON value that is not an object (e.g. an array) raises ``typer.BadParameter``."""
    import typer

    from cadrumo.application.aggregation.counterpart import CounterpartObservation
    from cadrumo.entrypoints.cli._modelo_aggregate_cli import _parse_typed_cli_observations

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

    from cadrumo.application.aggregation.counterpart import CounterpartObservation
    from cadrumo.entrypoints.cli._modelo_aggregate_cli import _parse_typed_cli_observations

    with pytest.raises(typer.BadParameter, match="counterparty_country: Field required"):
        _parse_typed_cli_observations(
            [_COUNTERPART_WITHOUT_COUNTRY], model=CounterpartObservation, flag="--counterpart-observation"
        )
