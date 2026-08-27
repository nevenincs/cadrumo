"""E2E data-fidelity: Modelo 714 Patrimonio prior-year wealth baseline across 2 renta years.

Modelo 714 (Impuesto sobre el Patrimonio) is the annual wealth-tax
declaration (Ley 19/1991, Orden HAC/1023/2021). Its baseline enrollment keeps
an E2E DATA_FIDELITY + threshold-continuity proof separate from the registry
calculation tests: the current registry computes the art. 30 cuota íntegra
scale and the art. 31 80 %-floor reference, while this module proves the
prior-year wealth base carries across two distinct renta ejercicios through
the real encrypted-SQLite observation store with strict pydantic equality.

The scenario (grounded against the Ley 19/1991 thresholds committed in the
legal catalogue):
- Year N: patrimonio neto / base imponible €2.100.000 (above the €2.000.000
  Modelo-714 filing obligation, Orden HAC/1023/2021), base liquidable
  €1.400.000 after the €700.000 mínimo exento (Ley 19/1991 art. 28), and a
  cuota íntegra as an arbitrary non-default stored entry. This fixture value
  is a roundtrip-fidelity input, not an oracle for the art. 30 escala; the
  escala is verified by the dedicated M714 registry calculation tests.
- Year N+1: the wealth base grows to €2.300.000 (base liquidable €1.600.000)
  — a distinct ejercicio whose figures must not bleed into year N.

The fidelity tests cover (mirroring the 720 prior-year-baseline pattern):
- Strict pydantic equality on reload for both years.
- Per-ejercicio valuation isolation (year N ≠ year N+1; no bleeding).
- The ejercicio casilla correctly encodes the filing year (cross-year key).
- Both years' base imponible exceeds the €2.000.000 filing-obligation threshold.
- Anti-tautology probe: omitting the cuota casilla surfaces strict inequality.
- EnrollmentRecorder over both ejercicios + assert_enrollment_matches_manifest.

Evidence class: DATA_FIDELITY (baseline persistence contract). Legal
grounding: Ley 19/1991 art. 28 (base liquidable / €700.000 mínimo exento),
art. 30 (escala 0,2-3,5 %), art. 31 (límite conjunto 60 % / suelo 80 %),
art. 4.Nueve (vivienda habitual €300.000); Orden HAC/1023/2021 (Modelo 714,
€2.000.000 obligación).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, validated_casilla_id
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository
from ._observation_lookup_support import find_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "714"

#: The two distinct renta ejercicios the wealth-baseline fidelity test spans.
_YEAR_N = 2023
_YEAR_N_PLUS_1 = 2024

#: Context label for the EnrollmentRecorder (data-fidelity / non-calculation mode).
_CONTEXT_LABEL = "714-patrimonio-prior-year-wealth-baseline-two-ejercicios"

#: Modelo-714 filing-obligation threshold: net wealth > €2.000.000 (Orden
#: HAC/1023/2021), independent of the €700.000 art. 28 mínimo exento.
_FILING_OBLIGATION_EUR = Decimal("2000000.00")

# Year-N wealth figures (above the €2.000.000 filing obligation).
_BASE_IMPONIBLE_N = Decimal("2100000.00")  # patrimonio neto
_BASE_LIQUIDABLE_N = Decimal("1400000.00")  # tras €700.000 mínimo exento (art. 28)
_CUOTA_INTEGRA_N = Decimal("8523.36")  # stored baseline fixture; formula oracle lives in registry tests

# Year-N+1 wealth figures (distinct ejercicio; grown base).
_BASE_IMPONIBLE_N1 = Decimal("2300000.00")
_BASE_LIQUIDABLE_N1 = Decimal("1600000.00")
_CUOTA_INTEGRA_N1 = Decimal("10523.36")

_CLOCK_N = datetime(2024, 5, 15, 10, 0, 0, tzinfo=UTC)  # M714 deadline window ~ Apr-Jun
_CLOCK_N_PLUS_1 = datetime(2025, 5, 15, 10, 0, 0, tzinfo=UTC)


_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id("decl.ejercicio")
_PATRIMONIO_BASE_IMPONIBLE_CASILLA: CasillaId = validated_casilla_id("patrimonio.base-imponible")
_PATRIMONIO_BASE_LIQUIDABLE_CASILLA: CasillaId = validated_casilla_id("patrimonio.base-liquidable")
_PATRIMONIO_CUOTA_INTEGRA_CASILLA: CasillaId = validated_casilla_id("patrimonio.cuota-integra")
_PATRIMONIO_TOTAL_CUOTA_INTEGRA_CASILLA: CasillaId = validated_casilla_id("patrimonio.total-cuota-integra")
_PATRIMONIO_CUOTA_A_INGRESAR_CASILLA: CasillaId = validated_casilla_id("patrimonio.cuota-a-ingresar")


def _observation(
    *,
    filing_year: int,
    base_imponible: Decimal,
    base_liquidable: Decimal,
    cuota: Decimal,
) -> RegistryModeloObservation:
    """Build a 714 observation with non-default values on every casilla.

    Uses the registry casilla ids authored in the 714 baseline schema. All values
    are non-default so a save-drops-field regression surfaces as strict
    inequality on reload.
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=filing_year,
        period="0A",
        casilla_values={
            _DECL_EJERCICIO_CASILLA: Decimal(str(filing_year)),
            _PATRIMONIO_BASE_IMPONIBLE_CASILLA: base_imponible,
            _PATRIMONIO_BASE_LIQUIDABLE_CASILLA: base_liquidable,
            _PATRIMONIO_CUOTA_INTEGRA_CASILLA: cuota,
            _PATRIMONIO_TOTAL_CUOTA_INTEGRA_CASILLA: cuota,
            _PATRIMONIO_CUOTA_A_INGRESAR_CASILLA: cuota,
        },
    )


def _year_n_observation() -> RegistryModeloObservation:
    return _observation(
        filing_year=_YEAR_N,
        base_imponible=_BASE_IMPONIBLE_N,
        base_liquidable=_BASE_LIQUIDABLE_N,
        cuota=_CUOTA_INTEGRA_N,
    )


def _year_n_plus_1_observation() -> RegistryModeloObservation:
    return _observation(
        filing_year=_YEAR_N_PLUS_1,
        base_imponible=_BASE_IMPONIBLE_N1,
        base_liquidable=_BASE_LIQUIDABLE_N1,
        cuota=_CUOTA_INTEGRA_N1,
    )


def test_year_n_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N 714 wealth-base casilla values survive the encrypted-SQL roundtrip unchanged."""
    obs_n = _year_n_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")

        assert loaded is not None, f"year-N observation not found for ({_MODELO!r}, {_YEAR_N}, '0A')"
        assert loaded.observation == obs_n, (
            "714 year-N observation did not survive the encrypted-SQL roundtrip; "
            "a casilla was silently dropped, coerced, or defaulted away"
        )
        assert loaded.captured_at == _CLOCK_N


def test_year_n_and_year_n_plus_1_are_independently_retrievable(tmp_path: Path) -> None:
    """Both ejercicios are independently addressable; wealth bases do not bleed."""
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period="0A")

        assert loaded_n is not None
        assert loaded_n1 is not None
        assert loaded_n.observation == obs_n
        assert loaded_n1.observation == obs_n1

        n_vals = loaded_n.observation.casilla_values
        n1_vals = loaded_n1.observation.casilla_values
        assert n_vals[_DECL_EJERCICIO_CASILLA] == Decimal(str(_YEAR_N))
        assert n1_vals[_DECL_EJERCICIO_CASILLA] == Decimal(str(_YEAR_N_PLUS_1))
        # Wealth bases must not bleed between ejercicios.
        assert n_vals[_PATRIMONIO_BASE_IMPONIBLE_CASILLA] == _BASE_IMPONIBLE_N
        assert n1_vals[_PATRIMONIO_BASE_IMPONIBLE_CASILLA] == _BASE_IMPONIBLE_N1
        assert n_vals[_PATRIMONIO_BASE_IMPONIBLE_CASILLA] != n1_vals[_PATRIMONIO_BASE_IMPONIBLE_CASILLA]


def test_both_years_base_exceeds_filing_obligation_threshold(tmp_path: Path) -> None:
    """Both ejercicios' base imponible exceeds the €2.000.000 Modelo-714 filing obligation.

    A roundtrip that silently zeroed a base would produce a sub-threshold
    (non-declarable) wealth record. Confirms both stored bases clear the
    obligation threshold (Orden HAC/1023/2021).
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(_year_n_observation(), source_kind="app_filing", captured_at=_CLOCK_N)
        )
        repo.save(
            repo.prepare_observation_envelope(
                _year_n_plus_1_observation(), source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1
            )
        )
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period="0A")

        assert loaded_n is not None
        assert loaded_n1 is not None
        assert loaded_n.observation.casilla_values[_PATRIMONIO_BASE_IMPONIBLE_CASILLA] > _FILING_OBLIGATION_EUR
        assert loaded_n1.observation.casilla_values[_PATRIMONIO_BASE_IMPONIBLE_CASILLA] > _FILING_OBLIGATION_EUR


def test_anti_tautology_proof_missing_cuota_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: omitting the cuota casilla produces strict inequality."""
    obs_n = _year_n_observation()
    obs_n_no_cuota = RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        observations=tuple(o for o in obs_n.observations if o.casilla_id != _PATRIMONIO_CUOTA_INTEGRA_CASILLA),
    )
    assert obs_n != obs_n_no_cuota

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")

        assert loaded is not None
        assert loaded.observation != obs_n_no_cuota, (
            "loaded observation equals the cuota-omitted observation; the roundtrip dropped patrimonio.cuota-integra"
        )
        assert loaded.observation == obs_n


def test_enrollment_recorder_evidences_two_ejercicios_and_matches_manifest(tmp_path: Path) -> None:
    """EnrollmentRecorder proves both ejercicios and matches the authorization manifest.

    Drives the real CalculationObservationRepository for both renta years, records
    each through record_context_year (data-fidelity / non-calculation mode), and
    calls assert_enrollment_matches_manifest. The manifest entry
    (authorization.d/714.toml) declares renta_years = [2023, 2024] in the same
    commit as this test. Evidence class DATA_FIDELITY: the two-year wealth-base
    fidelity (roundtrip + isolation + obligation-threshold) is the real ≥2-renta
    persistence contract; formula correctness is covered by the registry tests.
    """
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")
        assert loaded_n is not None
        assert loaded_n.observation == obs_n
        _count_n = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N)

        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period="0A")
        assert loaded_n1 is not None
        assert loaded_n1.observation == obs_n1
        _count_n1 = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N_PLUS_1)

    recorder = EnrollmentRecorder(_MODELO)
    recorder.record_context_year(
        filing_year=_YEAR_N,
        context_label=_CONTEXT_LABEL,
        persisted_observation_count=(_count_n),
    )
    recorder.record_context_year(
        filing_year=_YEAR_N_PLUS_1,
        context_label=_CONTEXT_LABEL,
        persisted_observation_count=(_count_n1),
    )

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)
