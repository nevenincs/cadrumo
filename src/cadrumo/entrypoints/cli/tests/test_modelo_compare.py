"""Regression test for `aeat app modelo compare` (contract).

The compare verb resolves the most recent VERIFICADO_COMPLETO (or BORRADOR)
revision for each of two filing years and emits per-casilla delta rows
(year_b - year_a) grouped by section.

Test strategy (non-tautological):
- Use Modelo 130 (``2019-y-siguientes`` revision, valid for 2025 and 2026).
  M130 needs only simple bindings, so both years can produce complete
  CalculationRevision records via the CLI `work calculate` surface.
- Create two M130 work units (2025 and 2026) with materially different
  ingresos (casilla 01) values and identical gastos and bindings.
- Capture per-casilla values from each ``work calculate`` JSON response.
- Invoke ``aeat app modelo compare --year 2025 --year 2026 --modelo 130``.
- Assert: delta rows for key output casillas (03, 04, 07, 19) match
  (year_b_value - year_a_value) derived from the two independent calculate
  calls.
- Anti-tautology: supply identical gastos (casilla 02) in both years.
  Assert the delta row for casilla 02 is exactly zero, proving the verb
  does not manufacture differences for equal values.

Oracle: the CLI ``work calculate`` path, an independent code path from the
compare verb, which reads stored CalculationRevision records rather than
re-running the engine.

Authority for M130 casilla arithmetic:
  AEAT DR 130 Instrucciones, Casilla 07 «Resultado parcial apartado I»;
  IRPF Art. 99 (BOE-A-2006-20764); RD 439/2007 Art. 110.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.modelo_cli import create_modelo_work_unit_via_cli
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from ._m130_source_support import seed_m130_expense_transaction, seed_m130_income_transaction

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROFILE_ID = "c0117a5e-c011-4c01-8c01-17a5ec0117a5"

# Two materially different source-owned ingresos for 2025 vs 2026.
# Oracle: rendimiento neto = ingresos - gastos; pago fraccionado = 20%.
# Authority: AEAT DR 130 Instrucciones, Casilla 03 and 04.
_INGRESOS_2025 = Decimal("12000.00")
_INGRESOS_2026 = Decimal("20000.00")

# Same gastos in both years — the anti-tautology casilla.
# Delta for casilla 02 must be exactly zero.
_GASTOS_BOTH = "4000.00"

# Previous-year income above 12,000 so minoración = 0 in both years.
# Authority: AEAT DR 130 Instrucciones, Casilla 13.
_PREV_YEAR_INCOME = "13000.00"

# Key output casillas to assert against the oracle.
# 03 = rendimiento neto, 04 = pago fraccionado, 07 = resultado I, 19 = final.
_RESULT_CASILLAS: tuple[CasillaId, ...] = (
    validated_casilla_id("03", surface="_RESULT_CASILLAS"),
    validated_casilla_id("04", surface="_RESULT_CASILLAS"),
    validated_casilla_id("07", surface="_RESULT_CASILLAS"),
    validated_casilla_id("19", surface="_RESULT_CASILLAS"),
)

# Anti-tautology: casilla 02 (gastos) is identical across both years.
_TAUTOLOGY_CASILLA: CasillaId = validated_casilla_id("02", surface="_TAUTOLOGY_CASILLA")
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = _TAUTOLOGY_CASILLA
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("03", surface="_M130_RENDIMIENTO_NETO_CASILLA")
_M130_PAGOS_PREVIOS_CASILLA: CasillaId = validated_casilla_id("05", surface="_M130_PAGOS_PREVIOS_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_RESULTADO_PARCIAL_CASILLA: CasillaId = validated_casilla_id(
    "07",
    surface="_M130_RESULTADO_PARCIAL_CASILLA",
)
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_RESULTADO_FINAL_CASILLA")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runtime_profile(
    tmp_path: Path,
) -> Iterator[TestRuntimeProfile]:
    """Real-session backend for the compare verb regression test.

    Uses ``isolated_runtime_profile`` (real KEK/DEK, real SQLite per
    active bucket).  Extra env overrides provide non-bucket directories.
    """

    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Modelo compare regression test profile",
    ) as profile:
        yield profile


def _seed_natural_person_profile(runtime_profile: TestRuntimeProfile) -> None:
    record = UserProfileRecord(
        schema_id="cadrumo.user_profile",
        # Sourced from the schema, never pinned: a literal goes stale the moment
        # the profile schema is revised, and the record then refuses to validate
        # against its own canonical version.
        schema_version=load_user_profile_schema().version,
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(
            UserProfileFact(path="identity.name", value="Compare Test Autónomo"),
            UserProfileFact(path="identity.surnames", value="Compare Test Autónomo"),
            UserProfileFact(path="identity.tax_id", value="11223344B"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(
                path="taxpayer_type.irpf_income_categories",
                value="actividad_economica",
            ),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="provenance.source", value="manual_cli"),
        ),
    )
    seed_test_profile_record(record, root=runtime_profile.storage_root, label="Compare test profile")


def _casilla_id_from_payload(value: object) -> CasillaId:
    """Validate one JSON payload key against the canonical CasillaId contract."""
    return validated_casilla_id(value, surface="test casilla id")


def _calculate_m130(work_unit_id: str, *, filing_year: int, ingresos: Decimal, gastos: str) -> dict[CasillaId, str]:
    """Calculate M130 and return casilla_values dict.

    Oracle inputs (AEAT DR 130 Instrucciones):
      casilla 01 = source-owned ingresos, 02 = source-owned gastos (both
      bucket-derived from the ledger), 05 = 0, 06 = 0.
      prev_year_income > 12,000 so minoración (13) = 0.

    Casilla 02 (gastos) is a bucket-bound casilla aggregated from deductible
    OUTGOING ledger rows; it cannot be supplied via ``--casilla``, so the gasto
    is seeded as a real expense transaction.
    """
    seed_m130_income_transaction(
        amount=ingresos,
        filing_year=filing_year,
        source_key=f"compare-{filing_year}",
    )
    seed_m130_expense_transaction(
        amount=Decimal(gastos),
        filing_year=filing_year,
        source_key=f"compare-{filing_year}",
    )
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", f"{_M130_PAGOS_PREVIOS_CASILLA}=0.00",
            "--casilla", f"{_M130_RETENCIONES_CASILLA}=0.00",
            "--binding", f"irpf.previous_year_economic_activity_net_income={_PREV_YEAR_INCOME}",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    raw_values = _payload(result.output)["casilla_values"]
    assert isinstance(raw_values, dict), f"casilla_values must be an object, got {type(raw_values).__name__}"
    return {_casilla_id_from_payload(key): str(value) for key, value in raw_values.items()}


# ---------------------------------------------------------------------------
# Regression tests — contract
# ---------------------------------------------------------------------------


def test_modelo_compare_m130_two_year_delta_rows(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Compare verb emits correct per-casilla deltas for two M130 filing years.

    Drive: create M130 work units for 2025 (ingresos=12,000) and 2026
    (ingresos=20,000), calculate each via ``work calculate``.
    Oracle: year_b_value - year_a_value from the two calculate payloads.
    Compare: invoke ``modelo compare --year 2025 --year 2026 --modelo 130``
    and assert delta_rows match oracle for key result casillas.

    Anti-tautology: casilla 02 (gastos) is identical across both years;
    its delta must be zero.

    Authority: AEAT DR 130 Instrucciones, Casilla 07 (RD 439/2007 Art. 110;
    IRPF Art. 99 BOE-A-2006-20764).
    """

    _seed_natural_person_profile(runtime_profile)

    # -- Create and calculate M130 2025 (year_a) ----------------------------
    wuid_2025 = create_modelo_work_unit_via_cli(
        modelo="130",
        filing_year=2025,
        period="1T",
        revision="2019-y-siguientes",
    )
    values_2025 = _calculate_m130(
        wuid_2025,
        filing_year=2025,
        ingresos=_INGRESOS_2025,
        gastos=_GASTOS_BOTH,
    )

    # -- Create and calculate M130 2026 (year_b) ----------------------------
    wuid_2026 = create_modelo_work_unit_via_cli(
        modelo="130",
        filing_year=2026,
        period="1T",
        revision="2019-y-siguientes",
    )
    values_2026 = _calculate_m130(
        wuid_2026,
        filing_year=2026,
        ingresos=_INGRESOS_2026,
        gastos=_GASTOS_BOTH,
    )

    # Verify oracle values are non-zero and materially different.
    # Oracle: casilla 07 = max(0, 20% x (01 - 02)) - 05 - 06
    # 2025: 20% x (12000 - 4000) = 1600; 2026: 20% x (20000 - 4000) = 3200.
    assert Decimal(values_2025[_M130_RESULTADO_PARCIAL_CASILLA]) == Decimal("1600.00"), (
        f"2025 oracle casilla 07: expected 1600.00, got {values_2025[_M130_RESULTADO_PARCIAL_CASILLA]!r}"
    )
    assert Decimal(values_2026[_M130_RESULTADO_PARCIAL_CASILLA]) == Decimal("3200.00"), (
        f"2026 oracle casilla 07: expected 3200.00, got {values_2026[_M130_RESULTADO_PARCIAL_CASILLA]!r}"
    )

    # -- Run compare verb ---------------------------------------------------
    compare_result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "compare",
            "--year", "2025",
            "--year", "2026",
            "--modelo", "130",
        ],
    )  # fmt: skip
    assert compare_result.exit_code == 0, compare_result.output
    assert "Traceback" not in compare_result.output

    payload = _payload(compare_result.output)
    assert payload["year_a"] == 2025
    assert payload["year_b"] == 2026
    assert payload["modelo"] == "130"

    # Build casilla_id → row lookup from delta_rows.
    delta_by_casilla: dict[CasillaId, dict[str, object]] = {
        _casilla_id_from_payload(row["casilla_id"]): row for row in payload["delta_rows"]
    }

    # -- Assert result casilla deltas match oracle (year_b - year_a) --------
    for casilla_id in _RESULT_CASILLAS:
        val_a = Decimal(values_2025.get(casilla_id, "0"))
        val_b = Decimal(values_2026.get(casilla_id, "0"))
        expected_delta = val_b - val_a

        assert casilla_id in delta_by_casilla, (
            f"Casilla {casilla_id} missing from compare delta_rows; available: {sorted(delta_by_casilla)[:15]}"
        )
        row = delta_by_casilla[casilla_id]
        actual_delta = Decimal(str(row["delta"]))

        assert actual_delta == expected_delta, (
            f"Casilla {casilla_id}: compare delta {actual_delta} != "
            f"oracle (year_b - year_a) = {val_b} - {val_a} = {expected_delta}. "
            f"Row: {row}"
        )

        # Materially different ingresos must produce non-zero deltas.
        assert expected_delta != Decimal("0"), (
            f"Casilla {casilla_id}: expected non-zero delta with "
            f"ingresos_2025={_INGRESOS_2025}, ingresos_2026={_INGRESOS_2026}, "
            f"got {expected_delta}. Check M130 formula sensitivity."
        )

    # -- Anti-tautology: casilla 02 (gastos) must have delta = 0 -----------
    # Both years used identical gastos; the compare verb must surface zero,
    # not an artificial difference.
    assert _TAUTOLOGY_CASILLA in delta_by_casilla, (
        f"Anti-tautology casilla {_TAUTOLOGY_CASILLA!r} missing from compare output."
    )
    row_tautology = delta_by_casilla[_TAUTOLOGY_CASILLA]
    assert Decimal(str(row_tautology["delta"])) == Decimal("0"), (
        f"Casilla {_TAUTOLOGY_CASILLA} (gastos): both years supplied "
        f"{_GASTOS_BOTH}; expected delta=0, "
        f"got {row_tautology['delta']!r}. Anti-tautology check failed."
    )


def test_compare_delta_rows_carry_provenance() -> None:
    """delta_rows produced by ``modelo compare`` carry formula_id / legal_refs /
    source_refs from the typed CasillaObservation envelope.

    This test exercises the ``obs_by_id`` lookup used inside ``modelo_compare``
    directly against real M130 registry engine output, bypassing the CLI stack
    that depends on wizard-catalogue registration.

    Authority: AEAT DR 130 Instrucciones; IRPF Art. 99 (BOE-A-2006-20764).
    """
    authority = bundled_authority()
    snap = authority.snapshot("130", filing_year=2026, period="1T")
    engine_result = calculate_registry_snapshot(
        snap,
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("10000"),
            _M130_GASTOS_CASILLA: Decimal("4000"),
            # Casilla 05 (pagos fraccionados anteriores) is a previous-filing-bound
            # carry; at 1T its expanding span is empty so the engine materialises it
            # as the absent-by-design zero. Supplying it as a raw input is now
            # smuggling past the previous-filing binding and is rejected by the guard.
            _M130_RETENCIONES_CASILLA: Decimal("0"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
    )

    # Simulate the obs_by_id lookup from modelo_compare.
    obs_by_id: dict[CasillaId, CasillaObservation] = {obs.casilla_id: obs for obs in engine_result.observations}

    # Computed casillas (03, 07, 19) must carry non-empty provenance.
    for casilla_id in (
        _M130_RENDIMIENTO_NETO_CASILLA,
        _M130_RESULTADO_PARCIAL_CASILLA,
        _M130_RESULTADO_FINAL_CASILLA,
    ):
        obs = obs_by_id.get(casilla_id)
        assert obs is not None, f"Casilla {casilla_id!r} absent from engine_result.observations"
        assert obs.formula_id, f"Computed casilla {casilla_id!r}: formula_id must be non-empty in compare delta_rows"
        assert obs.legal_refs, f"Computed casilla {casilla_id!r}: legal_refs must be non-empty in compare delta_rows"
        assert obs.source_refs, f"Computed casilla {casilla_id!r}: source_refs must be non-empty in compare delta_rows"

    # Input casilla (01) must have empty formula_id (not formula-computed).
    input_obs = obs_by_id.get(_M130_INGRESOS_CASILLA)
    assert input_obs is not None, "Casilla '01' (ingresos) must appear in observations"
    assert input_obs.formula_id is None, "Input casilla '01' must have formula_id=None (not formula-computed)"
