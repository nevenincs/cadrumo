"""E2E threshold/continuity: Modelo 840 IAE alta→baja across 2 annual contexts.

Modelo 840 (Impuesto sobre Actividades Económicas — declaración censal) is an
ad_hoc IAE censal declaration (Orden HAC/2572/2003). Cadence is ad_hoc. The
cross-year invariant is identity-continuity across two distinct annual contexts:
a taxpayer files an ``alta`` (0A) in year N declaring their epígrafe IAE
activity, and a ``baja`` in year N+2 when the activity ceases.

The enrollment evidence class is THRESHOLD_CONTINUITY. The test constructs a
real two-year context (real adapters, real encrypted-SQLite store) spanning two
distinct filing_year values and records both through the EnrollmentRecorder's
context mode. The context label is the un-fakeable evidence token.

Cross-year invariants tested:
- alta (year N) and baja (year N+2) are independently persisted and retrievable.
- The tipo-declaracion casilla distinguishes the two events (non-zero, non-default
  values in both so a drop-then-default regression surfaces as strict inequality).
- Anti-tautology probe: omitting the tipo-declaracion casilla produces strict
  inequality on the reloaded observation.

Legal grounding: RDL 2/2004 arts. 78, 82, 90 (IAE obligation); Orden HAC/2572/2003
apartados 1, 6 (alta/baja event layout).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry import (
    CasillaId,
    RegistryModeloObservation,
    validated_casilla_id,
)
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "840"

#: Two distinct annual contexts. M840 cadence is ad_hoc, period selector = ["0A"].
#: filing_year anchors which renta cycle the event belongs to.
_YEAR_N = 2024  # alta — activity start
_YEAR_N_PLUS_2 = 2026  # baja — activity end (gap year is realistic for IAE lifecycle)

#: Context label for the EnrollmentRecorder (non-calculation / threshold-continuity mode).
_CONTEXT_LABEL = "840-iae-alta-baja-two-annual-contexts"

_CLOCK_N = datetime(2024, 2, 1, 10, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_2 = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"M840 IAE fixture casilla key {value!r} is not a CasillaId") from exc


_DECL_TIPO_DECLARACION_CASILLA: CasillaId = _casilla_id("decl.tipo-declaracion")
_DECL_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.ejercicio")


def _find_observation(
    repo: CalculationObservationRepository,
    *,
    filing_year: int,
    period: str,
):
    """Scan iter_modelo and return the envelope matching (filing_year, period) or None."""
    for payload in repo.iter_modelo(_MODELO):
        obs = payload.observation
        if obs.filing_year == filing_year and obs.period == period:
            return payload
    return None


def _alta_observation() -> RegistryModeloObservation:
    """Build the year-N 840 alta observation.

    Casillas from the "2003-y-siguientes" revision:
    - ``decl.tipo-declaracion``: Decimal("1") = alta
    - ``decl.ejercicio``: the filing year

    Both are non-default so a save-drops-field regression surfaces as inequality.
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        casilla_values={
            # tipo-declaracion: 1 = alta (Orden HAC/2572/2003 apartado 1)
            _DECL_TIPO_DECLARACION_CASILLA: Decimal("1"),
            # ejercicio informational casilla
            _DECL_EJERCICIO_CASILLA: Decimal(str(_YEAR_N)),
        },
    )


def _baja_observation() -> RegistryModeloObservation:
    """Build the year-N+2 840 baja observation.

    Same modelo and period "0A" but different filing_year and a distinct
    tipo-declaracion (3 = baja per Orden HAC/2572/2003 apartado 1). The year
    gap (N to N+2) mirrors a realistic IAE lifecycle where an activity starts,
    runs for at least one full ejercicio, then ceases.
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_2,
        period="0A",
        casilla_values={
            # tipo-declaracion: 3 = baja (Orden HAC/2572/2003 apartado 1)
            _DECL_TIPO_DECLARACION_CASILLA: Decimal("3"),
            _DECL_EJERCICIO_CASILLA: Decimal(str(_YEAR_N_PLUS_2)),
        },
    )


def test_alta_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N 840 alta casilla values survive the encrypted-SQL roundtrip unchanged."""
    obs = _alta_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded = _find_observation(repo, filing_year=_YEAR_N, period="0A")

        assert loaded is not None, f"alta observation not found for ({_MODELO!r}, {_YEAR_N}, '0A') after save"
        assert loaded.observation == obs, "840 alta observation did not survive the encrypted-SQL roundtrip"
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N


def test_baja_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N+2 840 baja casilla values survive the roundtrip unchanged."""
    obs = _baja_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_2)
        loaded = _find_observation(repo, filing_year=_YEAR_N_PLUS_2, period="0A")

        assert loaded is not None
        assert loaded.observation == obs
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N_PLUS_2


def test_alta_and_baja_are_independently_retrievable(tmp_path: Path) -> None:
    """Alta (year N) and baja (year N+2) are independently addressable.

    After persisting both events:

    - Each reloads to exactly what was stored.
    - tipo-declaracion 1 (alta) must not appear in year N+2 (baja=3).
    - Provenance timestamps are distinct.

    The IAE lifecycle contract: an autónomo's alta from year N must remain
    independently retrievable when their year-N+2 baja is added. Neither
    event must contaminate the other's casilla values.
    """
    obs_n = _alta_observation()
    obs_n2 = _baja_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        repo.save_observation(obs_n2, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_2)
        loaded_n = _find_observation(repo, filing_year=_YEAR_N, period="0A")
        loaded_n2 = _find_observation(repo, filing_year=_YEAR_N_PLUS_2, period="0A")

        assert loaded_n is not None
        assert loaded_n2 is not None
        assert loaded_n.observation == obs_n
        assert loaded_n2.observation == obs_n2

        tipo_n = loaded_n.observation.casilla_values[_DECL_TIPO_DECLARACION_CASILLA]
        tipo_n2 = loaded_n2.observation.casilla_values[_DECL_TIPO_DECLARACION_CASILLA]
        assert tipo_n == Decimal("1"), f"year-N tipo should be 1 (alta); got {tipo_n}"
        assert tipo_n2 == Decimal("3"), f"year-N+2 tipo should be 3 (baja); got {tipo_n2}"

        assert loaded_n.captured_at == _CLOCK_N
        assert loaded_n2.captured_at == _CLOCK_N_PLUS_2


def test_ejercicio_casilla_matches_filing_year_in_both_contexts(tmp_path: Path) -> None:
    """The ejercicio casilla encodes the correct filing year in each annual context.

    RDL 2/2004 art. 78 requires IAE declarations to reference a specific ejercicio.
    The ejercicio informational casilla must survive the roundtrip with the exact
    year value; a serialiser that strips or defaults it would silently misdeclare
    the activity year.
    """
    obs_n = _alta_observation()
    obs_n2 = _baja_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        repo.save_observation(obs_n2, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_2)
        loaded_n = _find_observation(repo, filing_year=_YEAR_N, period="0A")
        loaded_n2 = _find_observation(repo, filing_year=_YEAR_N_PLUS_2, period="0A")

        assert loaded_n is not None
        assert loaded_n2 is not None
        ej_n = loaded_n.observation.casilla_values.get(_DECL_EJERCICIO_CASILLA)
        ej_n2 = loaded_n2.observation.casilla_values.get(_DECL_EJERCICIO_CASILLA)
        assert ej_n == Decimal(str(_YEAR_N)), f"ejercicio should be {_YEAR_N}; got {ej_n}"
        assert ej_n2 == Decimal(str(_YEAR_N_PLUS_2)), f"ejercicio should be {_YEAR_N_PLUS_2}; got {ej_n2}"


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: omitting tipo-declaracion produces strict inequality."""
    obs_n = _alta_observation()
    obs_n_no_tipo = RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        observations=tuple(o for o in obs_n.observations if o.casilla_id != _DECL_TIPO_DECLARACION_CASILLA),
    )

    assert obs_n != obs_n_no_tipo, "the full alta observation and the tipo-omitted observation must be strictly unequal"

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded = _find_observation(repo, filing_year=_YEAR_N, period="0A")

        assert loaded is not None
        assert loaded.observation != obs_n_no_tipo, (
            "loaded observation equals the tipo-omitted stub — the roundtrip silently dropped decl.tipo-declaracion"
        )
        assert loaded.observation == obs_n


def test_enrollment_recorder_evidences_two_distinct_annual_contexts_and_matches_manifest(
    tmp_path: Path,
) -> None:
    """EnrollmentRecorder proves both annual contexts and matches the authorization manifest.

    Drives the real CalculationObservationRepository for both years (year N alta
    and year N+2 baja), records each through record_context_year (context mode —
    no calculation engine), and calls assert_enrollment_matches_manifest.
    The manifest entry (authorization.d/840.toml) must declare renta_years =
    [2024, 2026] in the same commit as this test.
    """
    obs_n = _alta_observation()
    obs_n2 = _baja_observation()

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        # --- Year N: alta -----------------------------------------------
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded_n = _find_observation(repo, filing_year=_YEAR_N, period="0A")
        assert loaded_n is not None
        assert loaded_n.observation == obs_n
        _count_n = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N)

        # --- Year N+2: baja ---------------------------------------------
        repo.save_observation(obs_n2, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_2)
        loaded_n2 = _find_observation(repo, filing_year=_YEAR_N_PLUS_2, period="0A")
        assert loaded_n2 is not None
        assert loaded_n2.observation == obs_n2
        _count_n2 = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N_PLUS_2)

    # --- Enrollment recording (outside the profile context) -------------
    recorder = EnrollmentRecorder(_MODELO)
    recorder.record_context_year(
        filing_year=_YEAR_N,
        context_label=_CONTEXT_LABEL,
        persisted_observation_count=(_count_n),
    )
    recorder.record_context_year(
        filing_year=_YEAR_N_PLUS_2,
        context_label=_CONTEXT_LABEL,
        persisted_observation_count=(_count_n2),
    )

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_2), (
        f"expected distinct renta years {(_YEAR_N, _YEAR_N_PLUS_2)!r}; got {evidence.distinct_renta_years!r}"
    )

    assert_enrollment_matches_manifest(evidence)
