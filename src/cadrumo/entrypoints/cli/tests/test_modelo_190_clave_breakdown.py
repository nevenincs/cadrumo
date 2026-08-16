"""The Modelo 190 aggregate output renders a per-clave retención breakdown.

``aeat app modelo aggregate --modelo 190`` ingests the per-perceptor-clave
withholding detail and persists it to the dedicated store the percepciones-count
resolver reads. Previously its result surfaced only the observation/result
totals, so a filer could not reconcile the annual figures against the per-clave
amounts of the individual Modelo 111 quarterly filings. The command now projects
the ingested withholding detail into a per-clave breakdown (distinct percepción
count, percibido total, retención total) on both the JSON payload and the text
output. The breakdown is a pure projection of the same store the calculate path
reads (one-aggregation-path), not a recomputation of the M190 engine.
"""

from __future__ import annotations

import json

import pytest

from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from ....tests.user_profile import register_cli_profile

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


def test_modelo_190_aggregate_json_carries_per_clave_breakdown() -> None:
    """The JSON payload exposes one typed per-clave row with correct figures."""
    _create_profile()

    result = _aggregate(["--format", "json"])
    assert result.exit_code == 0, result.output

    payload = _payload(result.output)
    assert payload["operation"] == "modelo.aggregate"
    breakdown = {row["clave"]: row for row in payload["clave_breakdown"]}
    assert set(breakdown) == {"A", "G"}

    # Clave A: two distinct perceptores, percibido = 1000 + 500, retención = 190 + 95.
    assert breakdown["A"]["percepcion_count"] == 2
    assert breakdown["A"]["percibido_total"] == "1500.00"
    assert breakdown["A"]["retencion_total"] == "285.00"
    # Clave G: one percepción, percibido = dinerario + especie, retención = practicada + ingreso a cuenta.
    assert breakdown["G"]["percepcion_count"] == 1
    assert breakdown["G"]["percibido_total"] == "2100.00"
    assert breakdown["G"]["retencion_total"] == "420.00"


def test_modelo_190_aggregate_text_renders_per_clave_rows() -> None:
    """The human text output lists one ``clave_breakdown`` row per clave."""
    _create_profile()

    result = _aggregate([])
    assert result.exit_code == 0, result.output

    output = result.output
    assert "clave\tpercepcion_count\tpercibido_total\tretencion_total" in output
    assert "clave_breakdown\tA\t2\t1500.00\t285.00" in output
    assert "clave_breakdown\tG\t1\t2100.00\t420.00" in output
