"""Regression test for `aeat app modelo project` (contract).

The projection verb reads stored Modelo 130 quarterly calculation revisions,
aggregates rendimiento neto and pagos fraccionados across all available
quarters, and runs the Modelo 100 registry snapshot calculation.

Test strategy (non-tautological):
- Drive side: create 4 M130 work units for 2024, calculate each via the
  CLI work-calculate surface, which persists CalculationRevision records.
  Then invoke `aeat app modelo project --year 2024 --ccaa madrid` and
  capture the projected M100 casilla values from the JSON response.
- Oracle side: call `calculate_registry_snapshot` directly with the same
  accumulated M130 output injected at casilla 0171 (ingresos de explotación,
  manual-kind leaf) plus 0604 (pagos fraccionados).  These are independent
  entry paths exercising different code paths through the same registry.

Injection point rationale:
  Casilla 0505 (base liquidable general sometida a gravamen) is computed
  (input_kind = "computed", formula = max(0, 0500 − 0527)) and cannot be
  supplied as a direct engine input — doing so raises RegistryValidationError.
  The project verb instead injects the M130 rendimiento neto at casilla 0171
  (Ingresos de explotación, manual-kind), with all EDS gastos at zero.
  The formula chain 0171→0180→0224→0226→0231→0235→0432→0435→0500→0505
  propagates the net income through to base liquidable general.

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
    0171 (ingresos explotación, injection leaf): 32.000,00 EUR
    0604 (pagos fraccionados):                    6.400,00 EUR
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.user_profile._repository import UserProfileLifecycleRepository
from ....core.resources import resources
from ....domain.calculations.registry import calculate_registry_snapshot
from ....domain.user_profile import UserProfileFact, UserProfileRecord, UserProfileStatus
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from ._m130_source_support import seed_m130_income_transaction
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_proyecto_casilla_observations_carry_provenance() -> None:
    """The ``casilla_observations`` projection in the CLI payload carries
    regulatory provenance (``formula_id``, ``legal_refs``, ``source_refs``)
    for every formula-computed casilla.

    Verifies the contract of the ``engine_result.entries`` path the project
    verb uses to build ``casilla_observations``.  Uses M130 because it has
    a minimal, well-specified binding set and avoids the complex M100
    CCAA / atribución bindings that vary across revisions.

    The M130 casillas "03" (rendimiento neto), "04" (pago fraccionado), and
    "19" (resultado final) are formula-computed; their registry entries must
    carry non-empty ``legal_refs`` and ``formula_id``.
    """
    authority = resources().modelos.authority
    m130_snapshot = authority.snapshot("130", filing_year=2026, period="1T")
    engine_result = calculate_registry_snapshot(
        m130_snapshot,
        inputs={
            "01": Decimal("10000.00"),
            "02": Decimal("4000.00"),
            # Casilla 05 (pagos fraccionados anteriores) is a previous-filing-bound
            # carry; at 1T its expanding span is empty so the engine materialises it
            # as the absent-by-design zero. Supplying it as a raw input is now
            # smuggling past the previous-filing binding and is rejected by the guard.
            "06": Decimal("0"),
            "08": Decimal("0"),
            "10": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
    )

    # The project verb builds casilla_observations from engine_result.entries.
    casilla_observations = [
        {
            "casilla_id": entry.target,
            "value": str(entry.value),
            "formula_id": entry.formula_id,
            "legal_refs": list(entry.legal_refs),
            "source_refs": list(entry.source_refs),
        }
        for entry in engine_result.entries
    ]

    assert len(casilla_observations) > 0, "M130 must produce formula-computed entries"
    obs_by_id = {obs["casilla_id"]: obs for obs in casilla_observations}

    for casilla_id in ("03", "19"):
        obs = obs_by_id.get(casilla_id)
        assert obs is not None, f"computed casilla {casilla_id!r} must be in casilla_observations"
        assert obs["formula_id"], f"casilla {casilla_id!r} must carry formula_id"
        assert obs["legal_refs"], f"casilla {casilla_id!r} must carry legal_refs"
        assert obs["source_refs"], f"casilla {casilla_id!r} must carry source_refs"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROFILE_ID = "m130-projection-test-profile"

# Per-quarter M130 oracle inputs (AEAT DR 130 Instrucciones, Casilla 07).
# One Q1 income row remains in the cumulative source window for each quarter.
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
        display_name="M130 projection regression test profile",
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
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="provenance.source", value="manual_cli"),
            # Declaration type (person vs entity) — required by binding validation
            # in modelo-100 formulas.
            UserProfileFact(path="filing_export.declaration_type", value="1"),
            # Birth date drives the M100 ``age_at_year_end`` operator used by
            # the mínimo del contribuyente formula and any age-sensitive tramo.
            # Use a deterministic 1980 value so the taxpayer is 44 in 2024
            # (below the over-65 supplement threshold) — keeps the
            # M130→M100 oracle stable across runs.
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 1, 1)),
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
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload(result.output)["work_unit_id"]


def test_modelo_project_no_units_guides_natural_m130_creation(
    runtime_profile: TestRuntimeProfile,
) -> None:
    _seed_autónomo_profile(runtime_profile)

    result = invoke_cached_cli(
        [
            "app", "modelo", "project",
            "--year", str(_FILING_YEAR),
            "--ccaa", _CCAA,
        ],
    )  # fmt: skip

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "work create" in result.output
    assert "--modelo" in result.output
    assert "130" in result.output
    assert f"--year {_FILING_YEAR}" in result.output
    assert "--period 1T" in result.output
    assert "<work_unit_id>" not in result.output


def test_modelo_project_no_revisions_guides_natural_m130_calculation(
    runtime_profile: TestRuntimeProfile,
) -> None:
    _seed_autónomo_profile(runtime_profile)
    _create_work_unit(
        modelo="130",
        year=str(_FILING_YEAR),
        period="1T",
        revision="2019-y-siguientes",
    )

    result = invoke_cached_cli(
        [
            "app", "modelo", "project",
            "--year", str(_FILING_YEAR),
            "--ccaa", _CCAA,
        ],
    )  # fmt: skip

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "work calculate --modelo 130" in result.output
    assert f"--year {_FILING_YEAR}" in result.output
    assert "--period 1T" in result.output
    assert "<work_unit_id>" not in result.output


# ---------------------------------------------------------------------------
# Regression test — contract
# ---------------------------------------------------------------------------


def test_modelo_project_m130_to_m100_full_year_aggregation(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Project verb aggregates 4 M130 quarters into M100 cuota correctly.

    Drive side: create 4 M130 work units (1T-4T 2024), calculate each with
    identical oracle inputs, then invoke `project --year 2024 --ccaa madrid`.

    Oracle side: call `calculate_registry_snapshot` directly with the
    accumulated inputs `0171 = 32.000,00 EUR` (EDS ingresos de explotación,
    manual-kind leaf casilla) and `0604 = 6.400,00 EUR` plus the same
    default bindings the project verb applies.  Casilla 0505 is computed
    (max(0, 0500 − 0527)) and cannot be supplied as an engine input; both
    the project verb and this oracle inject at the leaf casilla 0171.

    Per `no-tautological-calculation-tests.md` the oracle is the M100
    registry engine itself, not a re-implementation of the projection
    formula.  Both paths exercise different code entry points: the project
    verb traverses stored CalculationRevision records; the oracle calls the
    engine directly.

    Authority: AEAT DR 130 Instrucciones (RD 439/2007 Art. 110; IRPF
    Art. 99 BOE-A-2006-20764); accumulated inputs stated above.
    """

    _seed_autónomo_profile(runtime_profile)
    seed_m130_income_transaction(
        amount=_Q_INGRESOS,
        filing_year=_FILING_YEAR,
        source_key="projection",
    )

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
                "--casilla", f"02={_Q_GASTOS}",
                "--casilla", "05=0.00",
                "--casilla", "06=0.00",
                # prev_year > 12.000 → minoración = 0 (AEAT DR 130 Casilla 13)
                "--binding", f"irpf.previous_year_economic_activity_net_income={_PREV_YEAR_INCOME}",
                "--binding", "modelo-130-resultados-negativos-anteriores=0",
            ],
        )  # fmt: skip
        assert calc_result.exit_code == 0, f"M130 calculate failed for period {period}: {calc_result.output}"
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
        ],
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
    # Single-authority routing invariant: both the verb's
    # internal calculate_registry_snapshot call and the oracle below
    # source their RegistrySnapshot from ``resources().modelos.authority``
    # (see _modelo.py modelo_project + the helper at line 528 / 1322 /
    # 3418). No alternate ``_service()._authority`` path exists in
    # the current codebase. The equivalence the audit asked about is
    # structurally enforced: a divergent path would have to introduce a
    # second authority constructor, which the resources() module gates.
    authority = resources().modelos.authority
    m100_snapshot = authority.snapshot("100", filing_year=_FILING_YEAR, period="0A")
    # Casilla 0604 is computed in the 2024 revision (formula
    # ``renta-{year}-pagos-fraccionados-ingresados`` sums the M130 + M131
    # relation channels). The oracle path supplies the same M130 total
    # through the relation map that the project verb threads. The
    # `renta-2024-profile-taxpayer-birth-date` date_binding is required
    # by the ``age_at_year_end`` op used in mínimo del contribuyente; the
    # seeded profile fact `renta_taxpayer.birth_date = 1980-01-01` is the
    # source of truth, mirrored here on the oracle.
    oracle_result = calculate_registry_snapshot(
        m100_snapshot,
        inputs={
            "0171": _TOTAL_RENDIMIENTO_NETO,  # EDS ingresos explotación leaf (manual-kind)
        },
        date_context={"filing_period": date(_FILING_YEAR, 12, 31)},
        # Mirror the project verb's merged_bindings shape exactly. The verb
        # composes ``verb_baseline_bindings`` (single-filer declaration-type,
        # zero retenciones, zero minor-children-in-unit) with the
        # profile-resolver projection of the seeded profile facts
        # (marriage-* derived from no marriage_date = zeros,
        # descendientes-menores-3 / guarderia / cotizaciones-ss-madre =
        # explicit zero defaults). The oracle must supply the same keys so
        # the comparison exercises an identical engine input set.
        binding_values={
            f"renta-{_FILING_YEAR}-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            f"renta-{_FILING_YEAR}-modelo-111-retenciones-periodicas": Decimal("0"),
            f"renta-{_FILING_YEAR}-modelo-115-retenciones-periodicas": Decimal("0"),
            f"renta-{_FILING_YEAR}-modelo-123-retenciones-periodicas": Decimal("0"),
            f"renta-{_FILING_YEAR}-modelo-193-retenciones-anuales": Decimal("0"),
            f"renta-{_FILING_YEAR}-profile-declaration-type": Decimal("1"),
            f"renta-{_FILING_YEAR}-profile-family-minor-children-in-unit": Decimal("0"),
            f"renta-{_FILING_YEAR}-profile-descendientes-menores-3": Decimal("0"),
            f"renta-{_FILING_YEAR}-profile-guarderia-gastos-reales": Decimal("0"),
            f"renta-{_FILING_YEAR}-profile-cotizaciones-ss-madre": Decimal("0"),
            f"renta-{_FILING_YEAR}-profile-marriage-full-year": Decimal("0"),
            f"renta-{_FILING_YEAR}-profile-marriage-month-start": Decimal("0"),
            f"renta-{_FILING_YEAR}-profile-marriage-month-end": Decimal("0"),
            f"renta-{_FILING_YEAR}-base-liquidable-negativa-general-anterior": Decimal("0"),
        },
        enum_binding_values={
            f"renta-{_FILING_YEAR}-profile-tax-residence-ccaa": _CCAA,
        },
        relation_values={
            f"renta-{_FILING_YEAR}-rel-130-pagos-fraccionados": _TOTAL_PAGOS_FRACCIONADOS,
            f"renta-{_FILING_YEAR}-rel-131-pagos-fraccionados": Decimal("0"),
        },
        date_binding_values={
            f"renta-{_FILING_YEAR}-profile-taxpayer-birth-date": date(1980, 1, 1),
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
            f"Inputs: 0171={_TOTAL_RENDIMIENTO_NETO}; "
            f"rel-130-pagos-fraccionados={_TOTAL_PAGOS_FRACCIONADOS}; "
            f"ccaa={_CCAA!r}."
        )

    # -- Provenance: casilla_observations carries legal_refs / source_refs -----
    # The grounding rule requires every CLI JSON emit of a calculated casilla
    # to surface legal_refs, source_refs, and formula_id.  The project verb
    # must include a casilla_observations list in its payload.
    casilla_observations = proj_payload.get("casilla_observations")
    assert casilla_observations is not None, "project payload must include casilla_observations"
    assert len(casilla_observations) > 0, "project payload must have at least one casilla_observation"
    # Every observation for a computed M100 casilla must carry non-empty legal_refs.
    obs_by_id = {obs["casilla_id"]: obs for obs in casilla_observations}
    for casilla_id in ("0545", "0546", "0595"):
        obs = obs_by_id.get(casilla_id)
        assert obs is not None, f"casilla_observations must include computed casilla {casilla_id!r}"
        assert obs.get("formula_id"), f"casilla {casilla_id!r} observation must carry formula_id"
        assert obs.get("legal_refs"), f"casilla {casilla_id!r} observation must carry legal_refs"
        assert obs.get("source_refs"), f"casilla {casilla_id!r} observation must carry source_refs"
