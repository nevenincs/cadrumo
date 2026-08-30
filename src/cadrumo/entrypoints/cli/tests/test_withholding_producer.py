"""Producer wire-up: the M190 aggregate path persists withholding observations (#28 P03).

The CLI ``aggregate`` path parses ``--withholding-observation`` JSON into typed
:class:`WithholdingObservation` rows, and for Modelo 190 persists them to the
dedicated encrypted store the percepciones-count resolver later reads — so the
pull and calculate surfaces read ONE source
(``aeat-calculation-aggregation``). Mirrors the RET-1
``--retencion-observation`` producer.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from pydantic import ValidationError

from ....application.aggregation import (
    PercepcionObservationRepository,
    PerModeloAggregationCommand,
    WithholdingObservation,
    persist_percepcion_observations,
)
from ....core.modelo import Modelo
from ....core.period import Period
from ....tests.secure_sql import isolated_runtime_profile
from .._modelo_aggregate_cli import _parse_typed_cli_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_RAW = (
    '{"source_id": "row-1", "perceptor_tax_id": "12345678A", "transaction_date": "2024-06-01",'
    ' "clave": "A", "subclave": "01", "percibido_dinerario": "1000.00",'
    ' "retencion_practicada": "190.00"}'
)


def test_parse_withholding_observation_from_cli_json() -> None:
    """``--withholding-observation`` JSON parses into a typed WithholdingObservation."""
    result = _parse_typed_cli_observations([_RAW], model=WithholdingObservation, flag="--withholding-observation")

    assert len(result) == 1
    obs = result[0]
    assert isinstance(obs, WithholdingObservation)
    assert obs.perceptor_tax_id == "12345678A"
    assert obs.clave == "A"
    assert obs.subclave == "01"


def test_parse_withholding_observation_without_clave_is_refused() -> None:
    """A CLI withholding row missing clave is refused by the typed parser/model path."""
    raw = (
        '{"source_id": "row-1", "perceptor_tax_id": "12345678A", "transaction_date": "2024-06-01",'
        ' "subclave": "01", "percibido_dinerario": "1000.00",'
        ' "retencion_practicada": "190.00"}'
    )

    with pytest.raises(typer.BadParameter, match="clave") as exc_info:
        _parse_typed_cli_observations([raw], model=WithholdingObservation, flag="--withholding-observation")

    assert isinstance(exc_info.value.__cause__, ValidationError)


def test_command_carries_withholding_observations() -> None:
    """PerModeloAggregationCommand carries the parsed withholding observations."""
    parsed = _parse_typed_cli_observations([_RAW], model=WithholdingObservation, flag="--withholding-observation")
    command = PerModeloAggregationCommand(
        modelo=Modelo.M190.value,
        period=Period.from_year_and_code(2024, "0A"),
        withholding_observations=parsed,
    )
    assert command.withholding_observations == parsed


def test_persisted_withholding_set_is_readable_by_the_store(tmp_path: Path) -> None:
    """The producer's persist writes the SAME set the resolver's store later reads (one source)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        parsed = _parse_typed_cli_observations([_RAW], model=WithholdingObservation, flag="--withholding-observation")
        period = Period.from_year_and_code(2024, "0A")
        persist_percepcion_observations(
            modelo=Modelo.M190.value,
            filing_year=2024,
            period=period,
            observations=parsed,
        )
        loaded = PercepcionObservationRepository().load_observations(Modelo.M190.value, period)
        assert set(loaded) == set(parsed)
