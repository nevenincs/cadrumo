"""E2E data-fidelity: Modelo 360 year-over-year ad-hoc cadence continuity.

Modelo 360 (Solicitud de devolución de cuotas del IVA soportadas por
empresarios o profesionales no establecidos en el territorio de aplicación
del impuesto pero establecidos en la Comunidad — Orden EHA/789/2010,
modificada por HAP/841/2016) is an ad-hoc refund request filed by EU-based
businesses for Spanish IVA they incurred but could not deduct (Directiva
2008/9/CE, LIVA art. 117-bis). The period code is ``"AD-HOC"``.

The casilla schema has two fields:
- ``decl.ejercicio`` — ejercicio al que se refiere la solicitud
- ``decl.estado-miembro`` — Estado miembro de devolución donde se soportaron
  las cuotas (the EU member state of the claimant's establishment)

There is no calculation engine and no cross-year binding resolver. The
cross-year invariant is data-fidelity and cadence continuity: two ad-hoc
refund requests in distinct ejercicios survive the encrypted-SQL roundtrip,
are independently retrievable, and their estado-miembro values do not bleed
between years.

Legal grounding: LIVA art. 117-bis (devolución a no establecidos en la
Comunidad); Orden EHA/789/2010 arts. 1, 4 (form mandate, filing procedure);
Directiva 2008/9/CE (EU non-resident IVA refund directive).
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
from ..observations_repository import CalculationObservationRepository
from ._observation_lookup_support import find_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "360"
_YEAR_N = 2024
_YEAR_N_PLUS_1 = 2025
_CONTEXT_LABEL = "360-adhoc-devolucion-iva-no-establecidos-cadence-year-over-year"
_CLOCK_N = datetime(2024, 9, 30, 10, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_1 = datetime(2025, 9, 30, 10, 0, 0, tzinfo=UTC)

# estado-miembro codes: 276 = DE (Germany), 250 = FR (France)
# Using integer Decimal so the casilla_values dict returns a comparable value
_ESTADO_MIEMBRO_N = Decimal("276")  # claimant established in Germany in year N
_ESTADO_MIEMBRO_N_PLUS_1 = Decimal("250")  # claimant moves to France for year N+1


_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id("decl.ejercicio")
_DECL_ESTADO_MIEMBRO_CASILLA: CasillaId = validated_casilla_id("decl.estado-miembro")


def _year_n_observation() -> RegistryModeloObservation:
    """Year-N 360 refund request from a Germany-established operator."""
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="AD-HOC",
        casilla_values={
            _DECL_EJERCICIO_CASILLA: Decimal(str(_YEAR_N)),
            _DECL_ESTADO_MIEMBRO_CASILLA: _ESTADO_MIEMBRO_N,
        },
    )


def _year_n_plus_1_observation() -> RegistryModeloObservation:
    """Year-N+1 360 refund request from a France-established operator.

    Distinct estado-miembro code ensures cross-year value-bleeding fails loudly.
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_1,
        period="AD-HOC",
        casilla_values={
            _DECL_EJERCICIO_CASILLA: Decimal(str(_YEAR_N_PLUS_1)),
            _DECL_ESTADO_MIEMBRO_CASILLA: _ESTADO_MIEMBRO_N_PLUS_1,
        },
    )


def test_year_n_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N 360 casilla values survive the encrypted-SQL roundtrip unchanged."""
    obs_n = _year_n_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="AD-HOC")
        assert loaded is not None
        assert loaded.observation == obs_n
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N


def test_year_n_plus_1_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N+1 360 casilla values survive the roundtrip with a different estado-miembro."""
    obs_n1 = _year_n_plus_1_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period="AD-HOC")
        assert loaded is not None
        assert loaded.observation == obs_n1
        assert loaded.captured_at == _CLOCK_N_PLUS_1


def test_both_observations_are_independently_retrievable_no_bleed(tmp_path: Path) -> None:
    """Both ejercicios are independently addressable; estado-miembro does not bleed."""
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="AD-HOC")
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period="AD-HOC")

        assert loaded_n is not None and loaded_n1 is not None
        assert loaded_n.observation == obs_n
        assert loaded_n1.observation == obs_n1

        em_n = loaded_n.observation.casilla_values[_DECL_ESTADO_MIEMBRO_CASILLA]
        em_n1 = loaded_n1.observation.casilla_values[_DECL_ESTADO_MIEMBRO_CASILLA]
        assert em_n == _ESTADO_MIEMBRO_N
        assert em_n1 == _ESTADO_MIEMBRO_N_PLUS_1
        assert em_n != em_n1, "decl.estado-miembro bled between year-N and year-N+1"

        assert loaded_n.captured_at != loaded_n1.captured_at


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: a missing casilla in the reloaded observation is detectable."""
    obs_n = _year_n_observation()
    obs_n_missing = RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="AD-HOC",
        observations=tuple(o for o in obs_n.observations if o.casilla_id != _DECL_ESTADO_MIEMBRO_CASILLA),
    )
    assert obs_n != obs_n_missing

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="AD-HOC")
        assert loaded is not None
        assert loaded.observation != obs_n_missing
        assert loaded.observation == obs_n


def test_modelo_360_adhoc_fidelity_enrolls_two_renta_years(tmp_path: Path) -> None:
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
