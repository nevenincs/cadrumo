"""Retired raw Modelo 190 transport stays outside the public capture path."""

from __future__ import annotations

import pytest
import typer
from pydantic import ValidationError

from ....domain.calculations.registry.withholding_bindings import (
    WithholdingObservation,
)
from .._modelo_aggregate_cli import _parse_typed_cli_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_RAW = (
    '{"source_id": "row-1", "perceptor_tax_id": "12345678A", "transaction_date": "2024-06-01",'
    ' "clave": "A", "subclave": "01", "percibido_dinerario": "1000.00",'
    ' "retencion_practicada": "190.00", "base_retenciones": "1000.00",'
    ' "incapacity_cash_perception": "0.00", "incapacity_cash_withholding": "0.00",'
    ' "incapacity_kind_value": "0.00", "incapacity_kind_ingreso_a_cuenta": "0.00",'
    ' "incapacity_kind_repercutido": "0.00", "foral_retention_estatal": "0.00",'
    ' "foral_retention_navarra": "0.00", "foral_retention_araba": "0.00",'
    ' "foral_retention_gipuzkoa": "0.00", "foral_retention_bizkaia": "0.00"}'
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
