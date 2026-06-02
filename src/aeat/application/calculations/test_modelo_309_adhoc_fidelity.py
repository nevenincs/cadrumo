"""E2E data-fidelity: Modelo 309 year-over-year ad-hoc cadence continuity.

Modelo 309 (IVA no periódico — Orden HAC/3625/2003) is an ad-hoc IVA
declaration for operators who trigger an IVA obligation outside the standard
periodic schedule: acquisitions of new means of transport from the EU,
operators under the régimen especial de la agricultura, operators who become
taxable on a recargo-de-equivalencia discharge, or ejecución forzosa
proceedings. The period code is ``"AD-HOC"``.

The casilla schema has five fields:
- ``iva.autorepercutido.intracomunitaria`` — cuota IVA autorepercutida en
  adquisiciones intracomunitarias (nuevos medios de transporte, etc.)
- ``iva.soportado.recargo-equivalencia`` — cuota IVA soportado por minoristas
  en recargo de equivalencia (devolución a viajeros)
- ``iva.cuota-no-periodica-total`` — total cuota (computed: sum of the two above)
- ``decl.ejercicio`` — ejercicio al que se refiere la declaración
- ``decl.tipo-trigger`` — tipo de trigger (medios transporte / agrícola /
  recargo equivalencia / ejecución forzosa)

There is no calculation engine and no cross-year binding resolver. The
cross-year invariant is data-fidelity and cadence continuity: two ad-hoc
observations in distinct ejercicios survive the encrypted-SQL roundtrip,
are independently retrievable, and their cuota values do not bleed between
years.

Legal grounding: Orden HAC/3625/2003 apartados 1 y 3 (form mandate); LIVA
arts. 13, 161 (adquisiciones intracomunitarias medios transporte, recargo de
equivalencia); RD 1624/1992 art. 31 (régimen especial agricultura).
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

_MODELO = "309"
_YEAR_N = 2024
_YEAR_N_PLUS_1 = 2025
_CONTEXT_LABEL = "309-adhoc-iva-no-periodico-cadence-year-over-year"
_CLOCK_N = datetime(2024, 4, 10, 10, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_1 = datetime(2025, 3, 5, 10, 0, 0, tzinfo=UTC)


def _find_observation(repo, *, filing_year, period):
    for payload in repo.iter_modelo(_MODELO):
        obs = payload.observation
        if obs.filing_year == filing_year and obs.period == period:
            return payload
    return None


def _year_n_observation() -> RegistryModeloObservation:
    """Year-N 309: acquisition of a new intracomunitario transport vehicle.

    iva.autorepercutido.intracomunitaria = 4200 (21% on a €20,000 vehicle),
    iva.soportado.recargo-equivalencia = 0, total = 4200. All values are
    non-default so a drop regression surfaces as strict inequality.
    """
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="AD-HOC",
        observations=(
            CasillaObservation(casilla_id="decl.ejercicio", value=Decimal(str(_YEAR_N))),
            CasillaObservation(casilla_id="decl.tipo-trigger", value=Decimal("1")),
            CasillaObservation(
                casilla_id="iva.autorepercutido.intracomunitaria", value=Decimal("4200.00")
            ),
            CasillaObservation(
                casilla_id="iva.soportado.recargo-equivalencia", value=Decimal("0")
            ),
            CasillaObservation(casilla_id="iva.cuota-no-periodica-total", value=Decimal("4200.00")),
        ),
    )


def _year_n_plus_1_observation() -> RegistryModeloObservation:
    """Year-N+1 309: a recargo-de-equivalencia discharge event.

    Distinct cuotas and tipo-trigger = 3 (recargo equivalencia) so any
    cross-year field-bleeding surfaces as strict inequality.
    """
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_1,
        period="AD-HOC",
        observations=(
            CasillaObservation(casilla_id="decl.ejercicio", value=Decimal(str(_YEAR_N_PLUS_1))),
            CasillaObservation(casilla_id="decl.tipo-trigger", value=Decimal("3")),
            CasillaObservation(
                casilla_id="iva.autorepercutido.intracomunitaria", value=Decimal("0")
            ),
            CasillaObservation(
                casilla_id="iva.soportado.recargo-equivalencia", value=Decimal("315.00")
            ),
            CasillaObservation(casilla_id="iva.cuota-no-periodica-total", value=Decimal("315.00")),
        ),
    )


def test_year_n_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N 309 casilla values survive the encrypted-SQL roundtrip unchanged."""
    obs_n = _year_n_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded = _find_observation(repo, filing_year=_YEAR_N, period="AD-HOC")
        assert loaded is not None
        assert loaded.observation == obs_n
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N


def test_year_n_plus_1_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N+1 309 casilla values survive the roundtrip with distinct cuota."""
    obs_n1 = _year_n_plus_1_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period="AD-HOC")
        assert loaded is not None
        assert loaded.observation == obs_n1
        assert loaded.captured_at == _CLOCK_N_PLUS_1


def test_both_observations_are_independently_retrievable_no_bleed(tmp_path: Path) -> None:
    """Both ejercicios are independently addressable; cuota values do not bleed."""
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        repo.save_observation(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded_n = _find_observation(repo, filing_year=_YEAR_N, period="AD-HOC")
        loaded_n1 = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period="AD-HOC")

        assert loaded_n is not None and loaded_n1 is not None
        assert loaded_n.observation == obs_n
        assert loaded_n1.observation == obs_n1

        cuota_n = loaded_n.observation.casilla_values["iva.cuota-no-periodica-total"]
        cuota_n1 = loaded_n1.observation.casilla_values["iva.cuota-no-periodica-total"]
        assert cuota_n == Decimal("4200.00")
        assert cuota_n1 == Decimal("315.00")
        assert cuota_n != cuota_n1, "iva.cuota-no-periodica-total bled between exercises"

        assert loaded_n.captured_at != loaded_n1.captured_at


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: a missing casilla in the reloaded observation is detectable."""
    obs_n = _year_n_observation()
    obs_n_missing = RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="AD-HOC",
        observations=tuple(
            o for o in obs_n.observations if o.casilla_id != "iva.cuota-no-periodica-total"
        ),
    )
    assert obs_n != obs_n_missing

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded = _find_observation(repo, filing_year=_YEAR_N, period="AD-HOC")
        assert loaded is not None
        assert loaded.observation != obs_n_missing
        assert loaded.observation == obs_n


def test_modelo_309_adhoc_fidelity_enrolls_two_renta_years(tmp_path: Path) -> None:
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
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded_n = _find_observation(repo, filing_year=_YEAR_N, period="AD-HOC")
        assert loaded_n is not None and loaded_n.observation == obs_n

        repo.save_observation(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded_n1 = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period="AD-HOC")
        assert loaded_n1 is not None and loaded_n1.observation == obs_n1

    recorder = EnrollmentRecorder(_MODELO)
    recorder.record_context_year(filing_year=_YEAR_N, context_label=_CONTEXT_LABEL)
    recorder.record_context_year(filing_year=_YEAR_N_PLUS_1, context_label=_CONTEXT_LABEL)

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)
