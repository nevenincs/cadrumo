"""E2E data-fidelity: Modelo 308 year-over-year ad-hoc cadence continuity.

Modelo 308 (IVA no periódico especial — Orden EHA/3786/2008) is an ad-hoc IVA
autoliquidación filed on trigger, not on a regular periodic schedule. It is
used by operators such as recargo-de-equivalencia retailers, art. 30-bis
occasional taxable persons, and art. 21.4 simplified-regime transport
operators (LIVA arts. 21.4, 161, RD 1624/1992 art. 30-bis). The period code
is ``"AD-HOC"``.

There is no calculation engine and no cross-year binding resolver. The
cross-year invariant is data-fidelity and cadence continuity across the
:class:`CalculationObservationRepository` persistence boundary:

- A filing for ejercicio N (an ad-hoc event in that year) is persisted and
  reloads with strict pydantic equality (all casilla values intact).
- The same filer's ad-hoc event in ejercicio N+1 is persisted independently
  and reloads with strict equality and distinct values.
- The two observations are independently addressable by ``(filing_year, period)``
  with no field-bleeding between years.
- Anti-tautology: a mutated observation with one casilla omitted is strictly
  unequal to the full observation.

Both years are recorded through the :class:`EnrollmentRecorder` via
``record_context_year`` (non-calculation mode) and cross-checked against the
authorization manifest.

Legal grounding: LIVA art. 21.4 (simplified-regime transport), LIVA art. 161
(recargo de equivalencia), RD 1624/1992 art. 30-bis (art. 30-bis occasional
taxable persons), Orden EHA/3786/2008 arts. 2, 11.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ..multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from ..observations_repository import CalculationObservationRepository
from ._multi_year_roundtrip_support import assert_two_ejercicio_round_trip
from ._observation_lookup_support import find_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "308"
_YEAR_N = 2024
_YEAR_N_PLUS_1 = 2025
_CONTEXT_LABEL = "308-adhoc-iva-no-periodico-cadence-year-over-year"
_CLOCK_N = datetime(2024, 6, 15, 10, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_1 = datetime(2025, 9, 20, 10, 0, 0, tzinfo=UTC)


_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id("decl.ejercicio")
_DECL_TIPO_SOLICITUD_CASILLA: CasillaId = validated_casilla_id("decl.tipo-solicitud")


def _year_n_observation() -> RegistryModeloObservation:
    """Build the year-N 308 ad-hoc observation.

    Models a sujeto pasivo ocasional (art. 30-bis): ejercicio N, tipo-solicitud
    distinguishes the trigger type. Both casilla values are non-default so a
    drop-then-default regression surfaces as strict inequality.
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="AD-HOC",
        casilla_values={
            _DECL_EJERCICIO_CASILLA: Decimal(str(_YEAR_N)),
            _DECL_TIPO_SOLICITUD_CASILLA: Decimal("1"),
        },
    )


def _year_n_plus_1_observation() -> RegistryModeloObservation:
    """Build the year-N+1 308 ad-hoc observation with a different tipo-solicitud."""
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_1,
        period="AD-HOC",
        casilla_values={
            _DECL_EJERCICIO_CASILLA: Decimal(str(_YEAR_N_PLUS_1)),
            _DECL_TIPO_SOLICITUD_CASILLA: Decimal("2"),
        },
    )


def test_year_n_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N 308 casilla values survive the encrypted-SQL roundtrip unchanged."""
    assert_two_ejercicio_round_trip(
        tmp_path=tmp_path,
        stage="year_n",
        modelo=_MODELO,
        period="AD-HOC",
        obs_n=_year_n_observation(),
        obs_n_plus_1=_year_n_plus_1_observation(),
        year_n=_YEAR_N,
        year_n_plus_1=_YEAR_N_PLUS_1,
        clock_n=_CLOCK_N,
        clock_n_plus_1=_CLOCK_N_PLUS_1,
    )


def test_year_n_plus_1_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N+1 308 casilla values survive the roundtrip with distinct tipo-solicitud."""
    assert_two_ejercicio_round_trip(
        tmp_path=tmp_path,
        stage="year_n_plus_1",
        modelo=_MODELO,
        period="AD-HOC",
        obs_n=_year_n_observation(),
        obs_n_plus_1=_year_n_plus_1_observation(),
        year_n=_YEAR_N,
        year_n_plus_1=_YEAR_N_PLUS_1,
        clock_n=_CLOCK_N,
        clock_n_plus_1=_CLOCK_N_PLUS_1,
    )


def test_both_ad_hoc_observations_are_independently_retrievable(tmp_path: Path) -> None:
    """Both exercises are independently addressable; tipo-solicitud values do not bleed."""
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="AD-HOC")
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period="AD-HOC")

        assert loaded_n is not None
        assert loaded_n1 is not None
        assert loaded_n.observation == obs_n
        assert loaded_n1.observation == obs_n1

        n_tipo = loaded_n.observation.casilla_values[_DECL_TIPO_SOLICITUD_CASILLA]
        n1_tipo = loaded_n1.observation.casilla_values[_DECL_TIPO_SOLICITUD_CASILLA]
        assert n_tipo == Decimal("1")
        assert n1_tipo == Decimal("2")
        assert n_tipo != n1_tipo, "tipo-solicitud bled between year-N and year-N+1"

        assert loaded_n.captured_at == _CLOCK_N
        assert loaded_n1.captured_at == _CLOCK_N_PLUS_1


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: a missing casilla in the reloaded observation is detectable."""
    obs_n = _year_n_observation()
    obs_n_missing = RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="AD-HOC",
        observations=tuple(o for o in obs_n.observations if o.casilla_id != _DECL_TIPO_SOLICITUD_CASILLA),
    )
    assert obs_n != obs_n_missing

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="AD-HOC")
        assert loaded is not None
        assert loaded.observation != obs_n_missing
        assert loaded.observation == obs_n


def test_modelo_308_adhoc_fidelity_enrolls_two_renta_years(tmp_path: Path) -> None:
    """EnrollmentRecorder proves both exercises and matches the authorization manifest.

    Drives the real CalculationObservationRepository for both ad-hoc ejercicios
    (real encrypted-SQLite, no mocks), records each via record_context_year, and
    calls assert_enrollment_matches_manifest. Manifest must declare
    renta_years = [2024, 2025] in the same commit.
    """
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="AD-HOC")
        assert loaded_n is not None and loaded_n.observation == obs_n
        _count_n = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N)

        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period="AD-HOC")
        assert loaded_n1 is not None and loaded_n1.observation == obs_n1
        _count_n1 = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N_PLUS_1)

    recorder = EnrollmentRecorder(_MODELO)
    recorder.record_context_year(
        filing_year=_YEAR_N,
        context_label=_CONTEXT_LABEL,
        persisted_observation_count=_count_n,
    )
    recorder.record_context_year(
        filing_year=_YEAR_N_PLUS_1,
        context_label=_CONTEXT_LABEL,
        persisted_observation_count=_count_n1,
    )

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)
