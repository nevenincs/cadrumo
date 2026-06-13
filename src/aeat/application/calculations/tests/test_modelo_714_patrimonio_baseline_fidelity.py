"""E2E data-fidelity: Modelo 714 Patrimonio prior-year wealth baseline across 2 renta years.

Modelo 714 (Impuesto sobre el Patrimonio) is the annual wealth-tax
declaration (Ley 19/1991, Orden HAC/1023/2021). Its initial enrollment is
DATA_FIDELITY + threshold-continuity (no calculation engine yet — the
casillas are ``input_kind = manual``; the tarifa art. 30 + límite art. 31
deferred calc is a follow-on contract). This module proves the part that can be built now: the
prior-year wealth base carries across two distinct renta ejercicios through
the real encrypted-SQLite observation store with strict pydantic equality.

The scenario (grounded against the Ley 19/1991 thresholds committed in the
legal catalogue):
- Year N: patrimonio neto / base imponible €2.100.000 (above the €2.000.000
  Modelo-714 filing obligation, Orden HAC/1023/2021), base liquidable
  €1.400.000 after the €700.000 mínimo exento (Ley 19/1991 art. 28), and a
  cuota íntegra as an arbitrary non-default manual entry (baseline contract has no calc
  engine; the art. 30 escala computation is deferred — this figure
  is a roundtrip-fidelity input, not an escala-derived value).
- Year N+1: the wealth base grows to €2.300.000 (base liquidable €1.600.000)
  — a distinct ejercicio whose figures must not bleed into year N.

The fidelity tests cover (mirroring the 720 prior-year-baseline pattern):
- Strict pydantic equality on reload for both years.
- Per-ejercicio valuation isolation (year N ≠ year N+1; no bleeding).
- The ejercicio casilla correctly encodes the filing year (cross-year key).
- Both years' base imponible exceeds the €2.000.000 filing-obligation threshold.
- Anti-tautology probe: omitting the cuota casilla surfaces strict inequality.
- EnrollmentRecorder over both ejercicios + assert_enrollment_matches_manifest.

Evidence class: DATA_FIDELITY (baseline contract; the prior-year-base ``previous_filing``
binding and the deferred tarifa/límite calc are follow-on work). Legal grounding:
Ley 19/1991 art. 28 (base liquidable / €700.000 mínimo exento), art. 30 (escala
0,2-3,5 %), art. 31 (límite conjunto 60 % / suelo 80 %), art. 4.Nueve (vivienda
habitual €300.000); Orden HAC/1023/2021 (Modelo 714, €2.000.000 obligación).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ....tests.secure_sql import isolated_runtime_profile
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository

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
_CUOTA_INTEGRA_N = Decimal("8523.36")  # arbitrary manual baseline figure (no calc; NOT escala-derived)

# Year-N+1 wealth figures (distinct ejercicio; grown base).
_BASE_IMPONIBLE_N1 = Decimal("2300000.00")
_BASE_LIQUIDABLE_N1 = Decimal("1600000.00")
_CUOTA_INTEGRA_N1 = Decimal("10523.36")

_CLOCK_N = datetime(2024, 5, 15, 10, 0, 0, tzinfo=UTC)  # M714 deadline window ~ Apr-Jun
_CLOCK_N_PLUS_1 = datetime(2025, 5, 15, 10, 0, 0, tzinfo=UTC)


def _find_observation(repo: CalculationObservationRepository, *, filing_year: int, period: str):
    """Scan iter_modelo and return the envelope matching (filing_year, period) or None."""
    for payload in repo.iter_modelo(_MODELO):
        obs = payload.observation
        if obs.filing_year == filing_year and obs.period == period:
            return payload
    return None


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
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=filing_year,
        period="0A",
        observations=(
            CasillaObservation(casilla_id="decl.ejercicio", value=Decimal(str(filing_year))),
            CasillaObservation(casilla_id="patrimonio.base-imponible", value=base_imponible),
            CasillaObservation(casilla_id="patrimonio.base-liquidable", value=base_liquidable),
            CasillaObservation(casilla_id="patrimonio.cuota-integra", value=cuota),
            CasillaObservation(casilla_id="patrimonio.total-cuota-integra", value=cuota),
            CasillaObservation(casilla_id="patrimonio.cuota-a-ingresar", value=cuota),
        ),
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
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded = _find_observation(repo, filing_year=_YEAR_N, period="0A")

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
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        repo.save_observation(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded_n = _find_observation(repo, filing_year=_YEAR_N, period="0A")
        loaded_n1 = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period="0A")

        assert loaded_n is not None
        assert loaded_n1 is not None
        assert loaded_n.observation == obs_n
        assert loaded_n1.observation == obs_n1

        n_vals = loaded_n.observation.casilla_values
        n1_vals = loaded_n1.observation.casilla_values
        assert n_vals["decl.ejercicio"] == Decimal(str(_YEAR_N))
        assert n1_vals["decl.ejercicio"] == Decimal(str(_YEAR_N_PLUS_1))
        # Wealth bases must not bleed between ejercicios.
        assert n_vals["patrimonio.base-imponible"] == _BASE_IMPONIBLE_N
        assert n1_vals["patrimonio.base-imponible"] == _BASE_IMPONIBLE_N1
        assert n_vals["patrimonio.base-imponible"] != n1_vals["patrimonio.base-imponible"]


def test_both_years_base_exceeds_filing_obligation_threshold(tmp_path: Path) -> None:
    """Both ejercicios' base imponible exceeds the €2.000.000 Modelo-714 filing obligation.

    A roundtrip that silently zeroed a base would produce a sub-threshold
    (non-declarable) wealth record. Confirms both stored bases clear the
    obligation threshold (Orden HAC/1023/2021).
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(_year_n_observation(), source_kind="app_filing", captured_at=_CLOCK_N)
        repo.save_observation(_year_n_plus_1_observation(), source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded_n = _find_observation(repo, filing_year=_YEAR_N, period="0A")
        loaded_n1 = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period="0A")

        assert loaded_n is not None
        assert loaded_n1 is not None
        assert loaded_n.observation.casilla_values["patrimonio.base-imponible"] > _FILING_OBLIGATION_EUR
        assert loaded_n1.observation.casilla_values["patrimonio.base-imponible"] > _FILING_OBLIGATION_EUR


def test_anti_tautology_proof_missing_cuota_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: omitting the cuota casilla produces strict inequality."""
    obs_n = _year_n_observation()
    obs_n_no_cuota = RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        observations=tuple(o for o in obs_n.observations if o.casilla_id != "patrimonio.cuota-integra"),
    )
    assert obs_n != obs_n_no_cuota

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded = _find_observation(repo, filing_year=_YEAR_N, period="0A")

        assert loaded is not None
        assert loaded.observation != obs_n_no_cuota, (
            "loaded observation equals the cuota-omitted stub — the roundtrip dropped patrimonio.cuota-integra"
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
    contract for the baseline behavior; the deferred tarifa/límite calc is follow-on.
    """
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded_n = _find_observation(repo, filing_year=_YEAR_N, period="0A")
        assert loaded_n is not None
        assert loaded_n.observation == obs_n
        _count_n = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N)

        repo.save_observation(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded_n1 = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period="0A")
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
