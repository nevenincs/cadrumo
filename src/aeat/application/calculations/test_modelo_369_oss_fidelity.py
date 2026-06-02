"""E2E data-fidelity: Modelo 369 OSS Esquema Unión year-over-year cadence continuity.

Modelo 369 (Declaración IVA OSS — Orden HAC/610/2021) is the quarterly
One-Stop-Shop autoliquidación for the Esquema Unión: operators established in
Spain who supply goods or services B2C to consumers in other EU member states
declare and pay the destination-state IVA centrally via the OSS portal (LIVA
arts. 163-unvicies to 163-quatervicies, Directiva 2021/285/UE). The period
code is ``"1T"``–``"4T"`` (quarterly).

The casilla schema (``esquema-union`` revision) includes:
- ``decl.ejercicio`` — ejercicio
- ``decl.periodo`` — quarterly period code
- ``iva.union.de.services-cuota`` — IVA OSS Unión destination DE, servicios
- ``iva.union.fr.services-cuota`` — IVA OSS Unión destination FR, servicios
- ``iva.union.de.goods-distance-cuota`` — IVA OSS Unión destination DE, ventas a
  distancia + interfaces electrónicas
- ``iva.union.cuota-total`` — total (computed: sum cross-destination)

There is no cross-year binding resolver. The cross-year invariant is
data-fidelity and cadence continuity: a quarterly filing for ejercicio N
survives the encrypted-SQL roundtrip, and the same period in ejercicio N+1
is independently retrievable with distinct cuota values that do not bleed.

Both years are recorded through the :class:`EnrollmentRecorder` via
``record_context_year`` and cross-checked against the authorization manifest.

Legal grounding: LIVA arts. 163-unvicies to 163-quatervicies (OSS regime);
Orden HAC/610/2021 arts. 1–3 (form mandate, quarterly cadence); Directiva
2021/285/UE (One-Stop-Shop reform).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ...tests.secure_sql import isolated_runtime_profile
from ._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from ._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_MODELO = "369"
_YEAR_N = 2024
_YEAR_N_PLUS_1 = 2025
_PERIOD = "2T"
_CONTEXT_LABEL = "369-oss-esquema-union-quarterly-cadence-year-over-year"
_CLOCK_N = datetime(2024, 7, 31, 10, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_1 = datetime(2025, 7, 31, 10, 0, 0, tzinfo=UTC)


def _find_observation(repo, *, filing_year, period):
    for payload in repo.iter_modelo(_MODELO):
        obs = payload.observation
        if obs.filing_year == filing_year and obs.period == period:
            return payload
    return None


def _year_n_observation() -> RegistryModeloObservation:
    """Year-N 369 2T: Spanish OSS operator supplying services to DE and FR.

    All cuota values are non-zero and distinct so a drop-then-default or
    cross-destination contamination surfaces as strict inequality.
    cuota-total = 1890.00 + 945.00 + 2100.00 = 4935.00.
    """
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period=_PERIOD,
        observations=(
            CasillaObservation(casilla_id="decl.ejercicio", value=Decimal(str(_YEAR_N))),
            CasillaObservation(casilla_id="decl.periodo", value=Decimal("2")),
            CasillaObservation(
                casilla_id="iva.union.de.services-cuota", value=Decimal("1890.00")
            ),
            CasillaObservation(
                casilla_id="iva.union.fr.services-cuota", value=Decimal("945.00")
            ),
            CasillaObservation(
                casilla_id="iva.union.de.goods-distance-cuota", value=Decimal("2100.00")
            ),
            CasillaObservation(casilla_id="iva.union.cuota-total", value=Decimal("4935.00")),
        ),
    )


def _year_n_plus_1_observation() -> RegistryModeloObservation:
    """Year-N+1 369 2T: distinct cuotas so cross-year bleeding surfaces loudly."""
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_1,
        period=_PERIOD,
        observations=(
            CasillaObservation(casilla_id="decl.ejercicio", value=Decimal(str(_YEAR_N_PLUS_1))),
            CasillaObservation(casilla_id="decl.periodo", value=Decimal("2")),
            CasillaObservation(
                casilla_id="iva.union.de.services-cuota", value=Decimal("2310.00")
            ),
            CasillaObservation(
                casilla_id="iva.union.fr.services-cuota", value=Decimal("1155.00")
            ),
            CasillaObservation(
                casilla_id="iva.union.de.goods-distance-cuota", value=Decimal("3150.00")
            ),
            CasillaObservation(casilla_id="iva.union.cuota-total", value=Decimal("6615.00")),
        ),
    )


def test_year_n_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N 369 casilla values survive the encrypted-SQL roundtrip unchanged."""
    obs_n = _year_n_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded = _find_observation(repo, filing_year=_YEAR_N, period=_PERIOD)
        assert loaded is not None
        assert loaded.observation == obs_n
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N


def test_year_n_plus_1_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N+1 369 casilla values survive the roundtrip with distinct cuotas."""
    obs_n1 = _year_n_plus_1_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period=_PERIOD)
        assert loaded is not None
        assert loaded.observation == obs_n1
        assert loaded.captured_at == _CLOCK_N_PLUS_1


def test_both_observations_are_independently_retrievable_no_bleed(tmp_path: Path) -> None:
    """Both ejercicios are independently addressable; cuota-total values do not bleed."""
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        repo.save_observation(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded_n = _find_observation(repo, filing_year=_YEAR_N, period=_PERIOD)
        loaded_n1 = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period=_PERIOD)

        assert loaded_n is not None and loaded_n1 is not None
        assert loaded_n.observation == obs_n
        assert loaded_n1.observation == obs_n1

        total_n = loaded_n.observation.casilla_values["iva.union.cuota-total"]
        total_n1 = loaded_n1.observation.casilla_values["iva.union.cuota-total"]
        assert total_n == Decimal("4935.00")
        assert total_n1 == Decimal("6615.00")
        assert total_n != total_n1, "iva.union.cuota-total bled between year-N and year-N+1"

        assert loaded_n.captured_at != loaded_n1.captured_at


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: a missing casilla in the reloaded observation is detectable."""
    obs_n = _year_n_observation()
    obs_n_missing = RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period=_PERIOD,
        observations=tuple(
            o for o in obs_n.observations if o.casilla_id != "iva.union.cuota-total"
        ),
    )
    assert obs_n != obs_n_missing

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded = _find_observation(repo, filing_year=_YEAR_N, period=_PERIOD)
        assert loaded is not None
        assert loaded.observation != obs_n_missing
        assert loaded.observation == obs_n


def test_modelo_369_oss_fidelity_enrolls_two_renta_years(tmp_path: Path) -> None:
    """EnrollmentRecorder proves both exercises and matches the authorization manifest.

    Drives the real CalculationObservationRepository for both OSS ejercicios
    (real encrypted-SQLite, no mocks), records each via record_context_year, and
    calls assert_enrollment_matches_manifest. Manifest must declare
    renta_years = [2024, 2025] in the same commit.
    """
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded_n = _find_observation(repo, filing_year=_YEAR_N, period=_PERIOD)
        assert loaded_n is not None and loaded_n.observation == obs_n

        repo.save_observation(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded_n1 = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period=_PERIOD)
        assert loaded_n1 is not None and loaded_n1.observation == obs_n1

    recorder = EnrollmentRecorder(_MODELO)
    recorder.record_context_year(filing_year=_YEAR_N, context_label=_CONTEXT_LABEL)
    recorder.record_context_year(filing_year=_YEAR_N_PLUS_1, context_label=_CONTEXT_LABEL)

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)
