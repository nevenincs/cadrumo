"""Regression test for `aeat app modelo project` (S117).

The projection verb reads stored Modelo 130 quarterly calculation revisions,
aggregates rendimiento neto and pagos fraccionados across all available
quarters, and runs the Modelo 100 registry snapshot calculation.

Test strategy (non-tautological):
- Drive side: create 4 M130 work units for 2024, calculate each via the
  CLI work-calculate surface, which persists CalculationRevision records.
  Then invoke `aeat app modelo project --year 2024 --ccaa madrid` and
  capture the projected M100 casilla values from the JSON response.
- Oracle side: call `calculate_registry_snapshot` directly with the same
  accumulated M130 outputs (0505 = sum of casilla 03, 0604 = sum of
  casilla 19).  These are independent entry paths exercising different
  code paths through the same registry.

Authority for M130 oracle inputs:
  AEAT DR 130 Instrucciones, Casilla 04 «20 por 100»; Casilla 19
  «Resultado final»; IRPF Art. 99 (BOE-A-2006-20764);
  RD 439/2007 Art. 110.

  Per-quarter worked example (4 identical quarters for determinism):
    casilla 01 (ingresos):           12.000,00 EUR
    casilla 02 (gastos):              4.000,00 EUR
    casilla 03 (rendimiento neto):    8.000,00 EUR  [= 01 - 02]
    casilla 04 (pago fraccionado):    1.600,00 EUR  [= 20% x 8.000]
    casilla 13 (minoración):              0,00 EUR  [prev_year > 12.000]
    casilla 17 (diferencia):          1.600,00 EUR
    casilla 19 (resultado final):     1.600,00 EUR  [= 17 - 18 = 17 - 0]

  4 quarters accumulated:
    0505 (base liquidable general):  32.000,00 EUR
    0604 (pagos fraccionados):        6.400,00 EUR
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.application.user_profile._repository import UserProfileLifecycleRepository
from aeat.core.resources import resources
from aeat.domain.calculations.registry import calculate_registry_snapshot
from aeat.domain.user_profile import UserProfileFact, UserProfileRecord, UserProfileStatus
from aeat.tests.cli_runner import invoke_cached_cli
from aeat.tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROFILE_ID = "m130-projection-test-profile"

# Per-quarter M130 oracle inputs (AEAT DR 130 Instrucciones, Casilla 07)
_Q_INGRESOS = Decimal("12000.00")
_Q_GASTOS = Decimal("4000.00")
# prev_year > 12.000 → minoración = 0
_PREV_YEAR_INCOME = Decimal("13000.00")

# Derived oracle accumulation over 4 quarters
_TOTAL_RENDIMIENTO_NETO = Decimal("32000.00")  # 4 x 8.000
_TOTAL_PAGOS_FRACCIONADOS = Decimal("6400.00")  # 4 x 1.600

_FILING_YEAR = 2024
_CCAA = "madrid"

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


def _payload(output: str) -> dict:
    raw = json.loads(output)
    if isinstance(raw, dict) and "schema_version" in raw and "result" in raw:
        return raw["result"]
    return raw


@pytest.fixture
def runtime_profile(
    tmp_path: Path,
) -> Iterator[TestRuntimeProfile]:
    """Real-session backend for M130→M100 projection regression test.

    Uses ``isolated_runtime_profile`` (real KEK/DEK, real SQLite per
    active bucket).  Extra env overrides provide the non-bucket
    directories work-unit commands read from settings.
    """

    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="M130 projection regression test profile",
    ) as profile:
        yield profile


def _seed_autónomo_profile(runtime_profile: TestRuntimeProfile) -> None:
    """Seed an autónomo (estimación directa) IRPF profile."""

    record = UserProfileRecord(
        schema_id="aeat.user_profile",
        schema_version=1,
        profile_id=_PROFILE_ID,
        display_name="Projection Test Autónomo",
        status=UserProfileStatus.ACTIVE,
        facts=(
            UserProfileFact(path="identity.name", value="Projection Test Autónomo"),
            UserProfileFact(path="identity.tax_id", value="87654321X"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(
                path="taxpayer_type.irpf_income_categories",
                value="actividad_economica",
            ),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.ccaa", value=_CCAA),
            UserProfileFact(
                path="tax_residence.jurisdiction_scope", value="common_regime"
            ),
            UserProfileFact(path="provenance.source", value="manual_cli"),
        ),
    )
    lifecycle = UserProfileLifecycleRepository(
        bucket_id=_PROFILE_ID,
        objects=runtime_profile.repository,
    )
    lifecycle.save(record)


def _create_work_unit(modelo: str, year: str, period: str, revision: str) -> str:
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", modelo,
            "--year", year,
            "--period", period,
            "--revision", revision,
        ]
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload(result.output)["work_unit_id"]


# ---------------------------------------------------------------------------
# Regression test — S117
# ---------------------------------------------------------------------------


def test_modelo_project_m130_to_m100_full_year_aggregation(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Project verb aggregates 4 M130 quarters into M100 cuota correctly.

    Drive side: create 4 M130 work units (1T-4T 2024), calculate each with
    identical oracle inputs, then invoke `project --year 2024 --ccaa madrid`.

    Oracle side: call `calculate_registry_snapshot` directly with the
    accumulated inputs `0505 = 32.000,00 EUR` and `0604 = 6.400,00 EUR`
    plus the same default bindings the project verb applies.

    Per `no-tautological-calculation-tests.md` the oracle is the M100
    registry engine itself, not a re-implementation of the projection
    formula.  Both paths exercise different code entry points: the project
    verb traverses stored CalculationRevision records; the oracle calls the
    engine directly.

    Authority: AEAT DR 130 Instrucciones (RD 439/2007 Art. 110; IRPF
    Art. 99 BOE-A-2006-20764); accumulated inputs stated above.
    """

    _seed_autónomo_profile(runtime_profile)

    # -- Create and calculate 4 M130 quarterly work units -------------------
    quarters = ["1T", "2T", "3T", "4T"]
    for period in quarters:
        work_unit_id = _create_work_unit(
            modelo="130",
            year=str(_FILING_YEAR),
            period=period,
            revision="2019-y-siguientes",
        )
        calc_result = invoke_cached_cli(
            [
                "--format", "json",
                "app", "modelo", "work", "calculate", work_unit_id,
                "--casilla", f"01={_Q_INGRESOS}",
                "--casilla", f"02={_Q_GASTOS}",
                "--casilla", "05=0.00",
                "--casilla", "06=0.00",
                # prev_year > 12.000 → minoración = 0 (AEAT DR 130 Casilla 13)
                "--binding", f"irpf.previous_year_economic_activity_net_income={_PREV_YEAR_INCOME}",
                "--binding", "modelo-130-resultados-negativos-anteriores=0",
            ]
        )  # fmt: skip
        assert calc_result.exit_code == 0, (
            f"M130 calculate failed for period {period}: {calc_result.output}"
        )
        quarter_payload = _payload(calc_result.output)
        assert "casilla_values" in quarter_payload, calc_result.output
        # Verify oracle inputs produce expected per-quarter values.
        assert Decimal(quarter_payload["casilla_values"]["03"]) == Decimal("8000.00"), (
            f"Period {period} casilla 03 (rendimiento neto): expected 8000.00, "
            f"got {quarter_payload['casilla_values']['03']!r}"
        )
        assert Decimal(quarter_payload["casilla_values"]["19"]) == Decimal("1600.00"), (
            f"Period {period} casilla 19 (resultado final): expected 1600.00 "
            f"(20% x 8000, AEAT DR 130 Casilla 04), got "
            f"{quarter_payload['casilla_values']['19']!r}"
        )

    # -- Run the projection verb -------------------------------------------
    project_result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "project",
            "--year", str(_FILING_YEAR),
            "--ccaa", _CCAA,
        ]
    )  # fmt: skip
    assert project_result.exit_code == 0, project_result.output
    assert "Traceback" not in project_result.output
    proj_payload = _payload(project_result.output)

    assert proj_payload["quarters_filed"] == 4
    assert proj_payload["is_extrapolated"] is False

    # Verify accumulated aggregation matches oracle totals.
    assert Decimal(proj_payload["m130_accumulated"]["rendimiento_neto"]) == _TOTAL_RENDIMIENTO_NETO, (
        f"Accumulated rendimiento neto: expected {_TOTAL_RENDIMIENTO_NETO}, "
        f"got {proj_payload['m130_accumulated']['rendimiento_neto']!r}"
    )
    assert Decimal(proj_payload["m130_accumulated"]["pagos_fraccionados"]) == _TOTAL_PAGOS_FRACCIONADOS, (
        f"Accumulated pagos fraccionados: expected {_TOTAL_PAGOS_FRACCIONADOS}, "
        f"got {proj_payload['m130_accumulated']['pagos_fraccionados']!r}"
    )

    # -- Oracle: direct M100 registry calculation --------------------------
    # This is the independent entry path that proves the projection verb
    # produces the same result as calling the M100 engine directly with the
    # same accumulated inputs.  Per no-tautological-calculation-tests.md,
    # the expected value comes from the registry engine, not from
    # re-implementing the IRPF tariff formula.
    #
    # Single-authority routing invariant (FU-W07-F): both the verb's
    # internal calculate_registry_snapshot call and the oracle below
    # source their RegistrySnapshot from ``resources().modelos.authority``
    # (see _modelo.py modelo_project + the helper at line 528 / 1322 /
    # 3418). No alternate ``_service()._authority`` path exists in
    # the current codebase. The equivalence the audit asked about is
    # structurally enforced: a divergent path would have to introduce a
    # second authority constructor, which the resources() module gates.
    authority = resources().modelos.authority
    m100_snapshot = authority.snapshot("100", filing_year=_FILING_YEAR, period="0A")
    oracle_result = calculate_registry_snapshot(
        m100_snapshot,
        inputs={
            "0505": _TOTAL_RENDIMIENTO_NETO,
            "0604": _TOTAL_PAGOS_FRACCIONADOS,
        },
        date_context={"filing_period": date(_FILING_YEAR, 12, 31)},
        binding_values={
            f"renta-{_FILING_YEAR}-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            f"renta-{_FILING_YEAR}-modelo-111-retenciones-periodicas": Decimal("0"),
            f"renta-{_FILING_YEAR}-modelo-115-retenciones-periodicas": Decimal("0"),
            f"renta-{_FILING_YEAR}-modelo-123-retenciones-periodicas": Decimal("0"),
            f"renta-{_FILING_YEAR}-modelo-193-retenciones-anuales": Decimal("0"),
        },
        enum_binding_values={
            f"renta-{_FILING_YEAR}-profile-tax-residence-ccaa": _CCAA,
        },
    )

    # Assert projected M100 casilla values equal oracle values.
    proj_m100 = proj_payload["m100_projection"]

    casilla_map = {
        "0545": "cuota_integra_estatal_0545",
        "0546": "cuota_integra_autonomica_0546",
        "0595": "cuota_liquida_estatal_0595",
        "0596": "cuota_liquida_autonomica_0596",
        "0597": "cuota_resultante_0597",
    }

    for casilla_id, payload_key in casilla_map.items():
        oracle_value = oracle_result.values.get(casilla_id, Decimal("0"))
        projected_value = Decimal(proj_m100[payload_key])
        assert projected_value == oracle_value, (
            f"M100 casilla {casilla_id}: project verb returned {projected_value}, "
            f"oracle (direct calculate_registry_snapshot) returned {oracle_value}. "
            f"Inputs: 0505={_TOTAL_RENDIMIENTO_NETO}, 0604={_TOTAL_PAGOS_FRACCIONADOS}, "
            f"ccaa={_CCAA!r}."
        )
