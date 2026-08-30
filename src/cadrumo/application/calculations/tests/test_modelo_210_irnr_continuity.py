"""E2E continuity: Modelo 210 IRNR cross-renta treaty-rate determinism.

Modelo 210 (IRNR autoliquidación no residentes sin establecimiento permanente
— RDLeg 5/2004 TRLIRNR) is filed ad-hoc by non-resident landlords and other
IRNR-obligated filers. Its primary engine (m210-irnr-full-engine contract §D2.2)
resolves: rendimientos_integros → base_imponible (op=copy, TRLIRNR art. 24.1)
→ base_imponible (TRLIRNR art. 24.1 gross path or art. 24.6 UE/EEE expense
deduction path) → tipo_gravamen (irnr_resolve_tipo_gravamen op, TRLIRNR arts. 25.1.a /
25.1.b / 25.1.f / Convenio override) → cuota_integra (base × tipo) →
cuota_diferencial (cuota minus retenciones).

The cross-renta continuity under test: a non-resident UK landlord (Gran
Bretaña, GB) with a Convenio row files the same property-rental declaration
for two consecutive renta years (2025, 2026). The GB/general Convenio row
in the initial seed carries rate=0.24, which coincides with the TRLIRNR
Art 25.1.a baseline (24%). The invariant: the same country_of_fiscal_residence
(GB / general) resolves to the same tipo_gravamen (0.24) via the Convenio
override path in both years, and yields a cuota_integra equal to the Convenio
rate times the declared base in both years — treaty-rate determinism across
annual groupings.

GB is chosen because it has an explicit Convenio row in the primary seed
(the only initial country with a concrete rate entry for tipo_renta=general),
making the override path exercisable without authoring new registry data.

This module is the multi-year-renta authorization enrollment for Modelo 210.
It drives the REAL primary engine (real registry authority, real
calculate_registry_snapshot, real formula evaluation — no mocks) for two
distinct renta years (2025, 2026), recording each through the
:class:`EnrollmentRecorder` and cross-checking via
:func:`assert_enrollment_matches_manifest`.

Grounding (non-tautological): the expected tipo_gravamen (0.24) is declared in
the GB/general convenio row, whose allocation authority is UK treaty art. 6 and
whose rate authority is TRLIRNR art. 25.1.a. The expected cuota_integra is
base × 0.24, where 0.24 comes from the registry parameter table (not the test
author). The assertion is that the engine reads the parameter and applies it; a
parameter-table regression (e.g. the rate silently changed to 0.00) would fail
it. The M210 convenio-rate mutation test proves the engine reads the registry
parameter; this test's job is cross-renta grounding across two annual groupings.

Registry extension note: the M210 2025 revision was extended to open-ended
(valid_to removed, period_selector year_from=2025) because the TRLIRNR
Art 24-25 rate schedule is year-stable. This is a grounded engineering
decision documented in the revision.toml; a genuine statutory rate change
would require a new dated revision.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ....domain.calculations.registry.ids import BindingId
from ....tests.secure_sql import isolated_runtime_profile
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "210"
_YEAR_N = 2025
_YEAR_N_PLUS_1 = 2026

# UK landlord scenario (Olivia persona from section D2.4): GB/general Convenio
# row carries rate=0.24, coinciding with the TRLIRNR Art 25.1.a baseline.
# The Convenio override path is exercised (country_of_fiscal_residence is
# non-None); the resolved rate equals the statutory baseline. This is the
# only primary Convenio row with a real concrete-rate entry for a
# resolvable tipo_renta, making it the canonical baseline enrollment scenario.
_COUNTRY_GB = "GB"
_TIPO_RENTA = "general"
_TIPO_GRAVAMEN_CONVENIO = Decimal("0.24")  # GB/general Convenio row = TRLIRNR art.25.1.a

# The rental base for each year — distinct so a cross-year base bleed
# surfaces as strict inequality in the cuota_integra assertion.
_BASE_YEAR_N = Decimal("18000.00")  # 2025 rental income
_BASE_YEAR_N_PLUS_1 = Decimal("19500.00")  # 2026 rental income (slightly higher)

# Profile-binding id for country_of_fiscal_residence (enum/text channel).
_COUNTRY_BINDING = "m210-2025-profile-country-of-fiscal-residence"
_TIPO_RENTA_CASILLA: CasillaId = validated_casilla_id("tipo_renta", surface="_TIPO_RENTA_CASILLA")
_RENDIMIENTOS_INTEGROS_CASILLA: CasillaId = validated_casilla_id(
    "rendimientos_integros",
    surface="_RENDIMIENTOS_INTEGROS_CASILLA",
)
_GASTOS_DEDUCIBLES_CASILLA: CasillaId = validated_casilla_id(
    "gastos_deducibles",
    surface="_GASTOS_DEDUCIBLES_CASILLA",
)
_RETENCION_PRACTICADA_CASILLA: CasillaId = validated_casilla_id(
    "retencion_practicada",
    surface="_RETENCION_PRACTICADA_CASILLA",
)
_BASE_IMPONIBLE_CASILLA: CasillaId = validated_casilla_id("base_imponible", surface="_BASE_IMPONIBLE_CASILLA")
_TIPO_GRAVAMEN_CASILLA: CasillaId = validated_casilla_id("tipo_gravamen", surface="_TIPO_GRAVAMEN_CASILLA")
_CUOTA_INTEGRA_CASILLA: CasillaId = validated_casilla_id("cuota_integra", surface="_CUOTA_INTEGRA_CASILLA")
_VALOR_CATASTRAL_CASILLA: CasillaId = validated_casilla_id("valor_catastral", surface="_VALOR_CATASTRAL_CASILLA")
_COEFICIENTE_IMPUTACION_CASILLA: CasillaId = validated_casilla_id(
    "coeficiente_imputacion_inmobiliaria",
    surface="_COEFICIENTE_IMPUTACION_CASILLA",
)
_DIAS_IMPUTACION_CASILLA: CasillaId = validated_casilla_id("dias_imputacion", surface="_DIAS_IMPUTACION_CASILLA")
_VALOR_ADQUISICION_CASILLA: CasillaId = validated_casilla_id(
    "valor_adquisicion",
    surface="_VALOR_ADQUISICION_CASILLA",
)
_VALOR_COMPROBADO_ADMINISTRACION_CASILLA: CasillaId = validated_casilla_id(
    "valor_comprobado_administracion",
    surface="_VALOR_COMPROBADO_ADMINISTRACION_CASILLA",
)


def _calculate_210(
    *,
    filing_year: int,
    base: Decimal,
    tipo_renta: str = _TIPO_RENTA,
    country_code: str = _COUNTRY_GB,
    extra_casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
) -> tuple[Mapping[CasillaId, object], int]:
    result = _calculate_210_result(
        filing_year=filing_year,
        base=base,
        tipo_renta=tipo_renta,
        country_code=country_code,
        extra_casilla_inputs=extra_casilla_inputs,
    )
    return result.values, len(result.values)


def _calculate_210_result(
    *,
    filing_year: int,
    base: Decimal,
    tipo_renta: str = _TIPO_RENTA,
    country_code: str = _COUNTRY_GB,
    extra_casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
) -> RegistryCalculationResult:
    """Run the REAL M210 primary engine for a GB non-resident landlord.

    Supplies:
    - rendimientos_integros (manual money casilla) = base
    - tipo_renta (manual text casilla) defaults to "general"
    - m210-2025-profile-country-of-fiscal-residence (enum binding) defaults to "GB"
    - gastos_deducibles / retencion_practicada = 0 unless supplied by the scenario

    Returns the real registry calculation result so tests can inspect value and
    provenance behavior without rebuilding formula logic.
    """
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=filing_year, period="EVENT-1")
    # Text casillas (tipo_renta) and enum bindings (country_of_fiscal_residence)
    # are supplied through text_inputs and enum_binding_values respectively.
    # Numeric manual casillas go through casilla_inputs.
    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {_COUNTRY_BINDING: country_code} if country_code else {}
    text_inputs = {_TIPO_RENTA_CASILLA: tipo_renta}
    casilla_inputs = {
        _RENDIMIENTOS_INTEGROS_CASILLA: base,
        _GASTOS_DEDUCIBLES_CASILLA: Decimal("0"),
        _RETENCION_PRACTICADA_CASILLA: Decimal("0"),
    }
    if extra_casilla_inputs is not None:
        casilla_inputs.update(extra_casilla_inputs)
    # resolve_available_bound_inputs_by_casilla_id handles bound casillas that the engine requires;
    # M210 primary has no previous_filing bindings, so this is a no-op here.
    bound = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    inputs = {**bound, **casilla_inputs}
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        text_inputs=text_inputs,
        date_context={"filing_period": date(filing_year, 12, 31)},
    )


def test_inmobiliaria_cadastral_recent_revision_computes_art_85_base(tmp_path: Path) -> None:
    """M210 inmobiliaria uses the LIRPF Art. 85 1.1% cadastral-value imputation branch."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        values, _ = _calculate_210(
            filing_year=_YEAR_N,
            base=Decimal("0"),
            tipo_renta="inmobiliaria",
            country_code="",
            extra_casilla_inputs={
                _VALOR_CATASTRAL_CASILLA: Decimal("100000.00"),
                _COEFICIENTE_IMPUTACION_CASILLA: Decimal("0.011"),
                _DIAS_IMPUTACION_CASILLA: Decimal("365"),
            },
        )

    assert values[_BASE_IMPONIBLE_CASILLA] == Decimal("1100.00")
    assert values[_TIPO_GRAVAMEN_CASILLA] == Decimal("0.24")
    assert values[_CUOTA_INTEGRA_CASILLA] == Decimal("264.00")


def test_inmobiliaria_without_cadastral_value_uses_half_of_greater_value(tmp_path: Path) -> None:
    """M210 inmobiliaria uses the Art. 85 no-cadastral 50% × 1.1% substitute base."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        values, _ = _calculate_210(
            filing_year=_YEAR_N,
            base=Decimal("0"),
            tipo_renta="inmobiliaria",
            country_code="",
            extra_casilla_inputs={
                _VALOR_CATASTRAL_CASILLA: Decimal("0"),
                _DIAS_IMPUTACION_CASILLA: Decimal("365"),
                _VALOR_ADQUISICION_CASILLA: Decimal("150000.00"),
                _VALOR_COMPROBADO_ADMINISTRACION_CASILLA: Decimal("180000.00"),
            },
        )

    assert values[_BASE_IMPONIBLE_CASILLA] == Decimal("990.00")
    assert values[_TIPO_GRAVAMEN_CASILLA] == Decimal("0.24")
    assert values[_CUOTA_INTEGRA_CASILLA] == Decimal("237.60")


def test_inmobiliaria_cadastral_branch_rejects_unregistered_coefficient(tmp_path: Path) -> None:
    """The imputation coefficient must match a registry-authored Art. 85 rate."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path),
        pytest.raises(
            RegistryValidationError,
            match="coefficient must be one of",
        ),
    ):
        _calculate_210(
            filing_year=_YEAR_N,
            base=Decimal("0"),
            tipo_renta="inmobiliaria",
            country_code="",
            extra_casilla_inputs={
                _VALOR_CATASTRAL_CASILLA: Decimal("100000.00"),
                _COEFICIENTE_IMPUTACION_CASILLA: Decimal("0.005"),
                _DIAS_IMPUTACION_CASILLA: Decimal("365"),
            },
        )


def test_pension_first_band_computes_art_25_1_b_tariff(tmp_path: Path) -> None:
    """M210 pension applies the TRLIRNR Art. 25.1.b 8% first bracket."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        result = _calculate_210_result(
            filing_year=_YEAR_N,
            base=Decimal("10000.00"),
            tipo_renta="pension",
            country_code="",
        )

    values = result.values
    assert values[_BASE_IMPONIBLE_CASILLA] == Decimal("10000.00")
    assert values[_TIPO_GRAVAMEN_CASILLA] == Decimal("0.08")
    assert values[_CUOTA_INTEGRA_CASILLA] == Decimal("800.00")

    observations = {obs.casilla_id: obs for obs in result.observations}
    tipo_observation = observations[_TIPO_GRAVAMEN_CASILLA]
    cuota_observation = observations[_CUOTA_INTEGRA_CASILLA]
    assert "trlirnr-rdleg-5-2004:art-25.1.b" in tipo_observation.legal_refs
    assert "m210-pension-tarifa-2025" in tipo_observation.operand_refs
    assert "trlirnr-rdleg-5-2004:art-25.1.b" in cuota_observation.legal_refs


def test_ue_resident_deductible_expenses_reduce_art_24_6_base(tmp_path: Path) -> None:
    """M210 Art. 24.6 expenses reduce the UE/EEE non-imputed taxable base."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        result = _calculate_210_result(
            filing_year=_YEAR_N,
            base=Decimal("1000.00"),
            tipo_renta="ue_residente",
            country_code="",
            extra_casilla_inputs={_GASTOS_DEDUCIBLES_CASILLA: Decimal("250.00")},
        )

    values = result.values
    assert values[_BASE_IMPONIBLE_CASILLA] == Decimal("750.00")
    assert values[_TIPO_GRAVAMEN_CASILLA] == Decimal("0.19")
    assert values[_CUOTA_INTEGRA_CASILLA] == Decimal("142.50")

    base_observation = next(obs for obs in result.observations if obs.casilla_id == _BASE_IMPONIBLE_CASILLA)
    assert "trlirnr-rdleg-5-2004:art-24" in base_observation.legal_refs
    assert _GASTOS_DEDUCIBLES_CASILLA in base_observation.operand_casilla_refs


def test_non_ue_resident_deductible_expenses_are_refused(tmp_path: Path) -> None:
    """M210 refuses nonzero gastos_deducibles outside the Art. 24.6 UE/EEE path."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path),
        pytest.raises(
            RegistryValidationError,
            match="Art\\. 24\\.6",
        ),
    ):
        _calculate_210(
            filing_year=_YEAR_N,
            base=Decimal("1000.00"),
            tipo_renta="general",
            country_code="GB",
            extra_casilla_inputs={_GASTOS_DEDUCIBLES_CASILLA: Decimal("100.00")},
        )


def test_ar_pension_second_band_uses_domestic_tariff_allocation(tmp_path: Path) -> None:
    """AR/pension treaty allocation delegates the amount to the domestic pension tariff."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        values, _ = _calculate_210(
            filing_year=_YEAR_N,
            base=Decimal("15000.00"),
            tipo_renta="pension",
            country_code="AR",
        )

    assert values[_BASE_IMPONIBLE_CASILLA] == Decimal("15000.00")
    assert values[_TIPO_GRAVAMEN_CASILLA] == Decimal("0.124")
    assert values[_CUOTA_INTEGRA_CASILLA] == Decimal("1860.00")


def test_pension_top_band_carries_fixed_addition_and_marginal_slice(tmp_path: Path) -> None:
    """The top pension band carries 2,970 fixed plus 40% above 18,700."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        values, _ = _calculate_210(
            filing_year=_YEAR_N,
            base=Decimal("20000.00"),
            tipo_renta="pension",
            country_code="",
        )

    assert values[_BASE_IMPONIBLE_CASILLA] == Decimal("20000.00")
    assert values[_TIPO_GRAVAMEN_CASILLA] == Decimal("0.1745")
    assert values[_CUOTA_INTEGRA_CASILLA] == Decimal("3490.00")


def test_year_n_gb_general_tipo_gravamen_is_24pct(tmp_path: Path) -> None:
    """Year N: GB/general landlord resolves tipo_gravamen to 0.24 via Convenio override.

    The GB/general Convenio row (rate=0.24) is read from the registry
    parameter table by the engine. The assertion grounds the rate against the
    Convenio seed entry: 24% is both the Convenio rate for GB/general and the
    TRLIRNR Art 25.1.a baseline.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        values, _ = _calculate_210(filing_year=_YEAR_N, base=_BASE_YEAR_N)

    assert values[_TIPO_GRAVAMEN_CASILLA] == _TIPO_GRAVAMEN_CONVENIO
    assert values[_BASE_IMPONIBLE_CASILLA] == _BASE_YEAR_N
    assert values[_CUOTA_INTEGRA_CASILLA] == (_BASE_YEAR_N * _TIPO_GRAVAMEN_CONVENIO).quantize(Decimal("0.01"))


def test_year_n_plus_1_gb_general_tipo_gravamen_is_24pct(tmp_path: Path) -> None:
    """Year N+1: same GB landlord, same Convenio rate — treaty-rate determinism across years.

    The GB/general Convenio row is year-stable (no annual override change).
    The engine must resolve the same 0.24 for 2026 as for 2025.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        values, _ = _calculate_210(filing_year=_YEAR_N_PLUS_1, base=_BASE_YEAR_N_PLUS_1)

    assert values[_TIPO_GRAVAMEN_CASILLA] == _TIPO_GRAVAMEN_CONVENIO
    assert values[_BASE_IMPONIBLE_CASILLA] == _BASE_YEAR_N_PLUS_1
    assert values[_CUOTA_INTEGRA_CASILLA] == (_BASE_YEAR_N_PLUS_1 * _TIPO_GRAVAMEN_CONVENIO).quantize(Decimal("0.01"))


def test_cuota_integra_differs_between_years_due_to_distinct_bases(tmp_path: Path) -> None:
    """The cuota_integra is distinct between years because the bases differ.

    Anti-cross-year-bleed assertion: the cuota values from each year
    must be strictly different (bases are 18000 vs 19500). If one year's
    base bled into the other's calculation, the cuotas would match
    incorrectly or one would be wrong.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        values_n, _ = _calculate_210(filing_year=_YEAR_N, base=_BASE_YEAR_N)
        values_n1, _ = _calculate_210(filing_year=_YEAR_N_PLUS_1, base=_BASE_YEAR_N_PLUS_1)

    cuota_n = values_n[_CUOTA_INTEGRA_CASILLA]
    cuota_n1 = values_n1[_CUOTA_INTEGRA_CASILLA]
    assert cuota_n != cuota_n1, (
        f"cuota_integra must differ between years (distinct bases); "
        f"got {cuota_n} for both — cross-year base contamination"
    )
    assert cuota_n == (_BASE_YEAR_N * _TIPO_GRAVAMEN_CONVENIO).quantize(Decimal("0.01"))
    assert cuota_n1 == (_BASE_YEAR_N_PLUS_1 * _TIPO_GRAVAMEN_CONVENIO).quantize(Decimal("0.01"))


def test_modelo_210_irnr_continuity_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: GB general-rate landlord across two renta years (2025, 2026).

    Drives the REAL M210 primary engine for both annual groupings (real
    registry authority, real formula evaluation — no mocks). Records each
    year through :class:`EnrollmentRecorder` (calculation mode, evidenced
    by produced casilla count) and cross-checks via
    :func:`assert_enrollment_matches_manifest`.

    Load-bearing assertions:
    - tipo_gravamen = 0.24 in both years (treaty-rate determinism).
    - cuota_integra = base × 0.24 in both years (engine applies the rate).
    - Cuotas are distinct because bases are distinct (no cross-year bleed).

    Grounded in TRLIRNR Art 25.1.a (general non-resident IRNR rate 24%) and
    the GB/general Convenio entry in the primary Convenio seed (rate=0.24,
    year-stable per RDLeg 5/2004 arts. 24-25).
    """
    recorder = EnrollmentRecorder(_MODELO)

    with isolated_runtime_profile(tmp_path=tmp_path):
        # Year N: real primary-engine run.
        values_n, produced_n = _calculate_210(filing_year=_YEAR_N, base=_BASE_YEAR_N)
        recorder.record_calculation_year(filing_year=_YEAR_N, produced_value_count=produced_n)

        # Year N+1: same engine, same treaty rate, distinct base.
        values_n1, produced_n1 = _calculate_210(filing_year=_YEAR_N_PLUS_1, base=_BASE_YEAR_N_PLUS_1)
        recorder.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=produced_n1)

    # Treaty-rate determinism: GB/general Convenio rate 0.24 in both years.
    assert values_n[_TIPO_GRAVAMEN_CASILLA] == _TIPO_GRAVAMEN_CONVENIO
    assert values_n1[_TIPO_GRAVAMEN_CASILLA] == _TIPO_GRAVAMEN_CONVENIO

    # Cuota correctness from Convenio registry parameter (not hand-computed formula).
    assert values_n[_CUOTA_INTEGRA_CASILLA] == (_BASE_YEAR_N * _TIPO_GRAVAMEN_CONVENIO).quantize(Decimal("0.01"))
    assert values_n1[_CUOTA_INTEGRA_CASILLA] == (_BASE_YEAR_N_PLUS_1 * _TIPO_GRAVAMEN_CONVENIO).quantize(
        Decimal("0.01")
    )

    # Cross-renta isolation: distinct cuotas from distinct bases.
    assert values_n[_CUOTA_INTEGRA_CASILLA] != values_n1[_CUOTA_INTEGRA_CASILLA]

    # Authorization-gate enrollment.
    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)
