"""``modelo.aggregate`` renders the canonical aggregation result, not a looser shell.

``ModeloAggregateResult`` is the JSON transport for
:class:`~application.aggregation.PerModeloAggregationResult`. It redeclared that
result's fields as bare strings, string lists, and unbounded integers, so the
envelope shell admitted an empty modelo, an unknown provider, a bogus source
kind, and negative counters the canonical result refuses. These tests pin the
projection: what the service produces round-trips, and what the service could
never produce is refused before it reaches an operator.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....application.aggregation import (
    CounterpartObservation,
    PerModeloAggregationCommand,
    PerModeloAggregationContributor,
    PerModeloAggregationResult,
    aggregate_per_modelo,
)
from ....core import Modelo
from ....core.period import Period
from ....core.aggregation import BindingSourceKind
from ....core.aggregation import OperationKind347
from .._modelo_payloads import ModeloAggregateResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PERIOD = Period.from_year_and_code(2025, "0A")


def _real_result() -> PerModeloAggregationResult:
    """Run the real aggregation service over a real observation."""
    observation = CounterpartObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id="tx-001",
        counterparty_nif="12345678Z",
        counterparty_name="Proveedor Ejemplo SL",
        counterparty_country="ES",
        operation_kind=OperationKind347.DELIVERY.value,
        operation_period="0A",
        taxable_base=Decimal("4000.00"),
        invoice_total=Decimal("4840.00"),
        accrued_on="2025-03-15",
    )
    return aggregate_per_modelo(
        PerModeloAggregationCommand(
            modelo=Modelo.M347.value,
            period=_PERIOD,
            counterpart_observations=(observation,),
        ),
    )


def _valid_payload_fields() -> dict[str, object]:
    result = _real_result()
    return {
        "modelo": result.modelo,
        "period": result.period,
        "provider": result.provider,
        "observation_count": result.log_fields.observation_count,
        "source_kinds": list(result.source_kinds),
        "result_row_count": result.log_fields.result_row_count,
    }


def test_projection_carries_the_canonical_result_verbatim() -> None:
    """Every projected field equals the service result it was built from."""
    result = _real_result()

    payload = ModeloAggregateResult.from_aggregation_result(result)

    assert payload.modelo == result.modelo
    assert payload.period == result.period
    assert payload.provider is result.provider
    assert payload.source_kinds == list(result.source_kinds)
    assert payload.observation_count == result.log_fields.observation_count
    assert payload.result_row_count == result.log_fields.result_row_count


def test_projection_json_round_trips_through_its_own_rendering() -> None:
    """The JSON rendering re-validates to an equal payload.

    The closed enums render as their string tokens on the wire and are lifted
    back to members on re-validation, so the transport shape stays JSON-safe
    without loosening the field types.
    """
    payload = ModeloAggregateResult.from_aggregation_result(_real_result())
    rendered = payload.model_dump(mode="json")

    assert rendered["provider"] == PerModeloAggregationContributor.COUNTERPART.value
    assert rendered["source_kinds"] == [kind.value for kind in payload.source_kinds]
    assert ModeloAggregateResult.model_validate(rendered) == payload


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("modelo", ""),
        ("modelo", "3" * 17),
        ("provider", "bogus"),
        ("observation_count", -1),
        ("result_row_count", -2),
        ("source_kinds", ["bogus"]),
        (
            "source_kinds",
            [BindingSourceKind.LEDGER_TRANSACTION, BindingSourceKind.LEDGER_TRANSACTION],
        ),
    ],
)
def test_malformed_transport_fields_are_refused(field: str, value: object) -> None:
    """A shape the canonical result could never produce is refused at the boundary.

    Each of these was accepted by the previous bare-string / unbounded-integer
    shell, so an envelope could report an empty modelo, an unknown provider, a
    source kind outside the closed taxonomy, or a negative count.
    """
    fields = _valid_payload_fields()
    fields[field] = value

    with pytest.raises(ValidationError):
        ModeloAggregateResult.model_validate(fields)


def test_valid_transport_fields_are_accepted() -> None:
    """The positive control for the refusals above."""
    payload = ModeloAggregateResult.model_validate(_valid_payload_fields())

    assert payload.provider is PerModeloAggregationContributor.COUNTERPART
    assert payload.observation_count >= 0
