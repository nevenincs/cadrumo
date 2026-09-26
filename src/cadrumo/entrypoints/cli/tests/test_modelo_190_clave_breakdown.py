"""Modelo 190 no longer accepts a direct annual-detail mutation transport."""

from __future__ import annotations

import json

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile

from ....adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from .cli_runner import invoke_cached_cli

__all__ = ["_isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _create_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Operator",
            "activities.description": "design",
        },
        log_in=False,
    )


def _withholding(
    *,
    source_id: str,
    nif: str,
    clave: str,
    percibido_dinerario: str = "0",
    percibido_especie: str = "0",
    retencion_practicada: str = "0",
    ingreso_a_cuenta: str = "0",
) -> str:
    return json.dumps(
        {
            "source_id": source_id,
            "perceptor_tax_id": nif,
            "transaction_date": "2025-06-01",
            "clave": clave,
            "subclave": "01",
            "percibido_dinerario": percibido_dinerario,
            "percibido_especie": percibido_especie,
            "retencion_practicada": retencion_practicada,
            "ingreso_a_cuenta": ingreso_a_cuenta,
            "base_retenciones": "0.00",
            "incapacity_cash_perception": "0.00",
            "incapacity_cash_withholding": "0.00",
            "incapacity_kind_value": "0.00",
            "incapacity_kind_ingreso_a_cuenta": "0.00",
            "incapacity_kind_repercutido": "0.00",
            "foral_retention_estatal": "0.00",
            "foral_retention_navarra": "0.00",
            "foral_retention_araba": "0.00",
            "foral_retention_gipuzkoa": "0.00",
            "foral_retention_bizkaia": "0.00",
        },
    )


_OBSERVATIONS = (
    _withholding(
        source_id="a1",
        nif="11111111H",
        clave="A",
        percibido_dinerario="1000.00",
        retencion_practicada="190.00",
    ),
    _withholding(
        source_id="a2",
        nif="22222222J",
        clave="A",
        percibido_dinerario="500.00",
        retencion_practicada="95.00",
    ),
    _withholding(
        source_id="g1",
        nif="11111111H",
        clave="G",
        percibido_dinerario="2000.00",
        percibido_especie="100.00",
        retencion_practicada="400.00",
        ingreso_a_cuenta="20.00",
    ),
)


def _aggregate(args_format: list[str]):
    return invoke_cached_cli(
        [
            *args_format,
            "app",
            "modelo",
            "aggregate",
            "--modelo",
            "190",
            "--year",
            "2025",
            "--period",
            "0A",
            "--withholding-observation",
            _OBSERVATIONS[0],
            "--withholding-observation",
            _OBSERVATIONS[1],
            "--withholding-observation",
            _OBSERVATIONS[2],
        ],
    )


def test_modelo_190_aggregate_refuses_the_retired_raw_withholding_transport() -> None:
    """Annual records must originate from the shared Modelo 111 evidence capture."""
    _create_profile()

    result = _aggregate(["--format", "json"])
    assert result.exit_code != 0
    assert "--withholding-observation is not accepted for Modelo 190" in result.output
