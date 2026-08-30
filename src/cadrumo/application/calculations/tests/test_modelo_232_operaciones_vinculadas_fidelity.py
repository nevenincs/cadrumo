"""E2E data-fidelity: Modelo 232 year-over-year related-party operation continuity.

Modelo 232 (Operaciones vinculadas e información país por país — Declaración
informativa) is a pure-informativa annual declaration (Orden HFP/816/2017). There
is no calculation engine. The cross-year invariant is data-fidelity of related-party
rows across two ejercicios: the same counterparty (NIF, tipo-vinculacion) appears
with distinct operation amounts in year N and year N+1, and the €100,000 per-year
reporting threshold (RD 634/2015 art. 13) is exercised across both years.

Evidence class: DATA_FIDELITY. Both years are driven through the real
CalculationObservationRepository and recorded via record_context_year.

Cross-year invariants tested:
- A related-party row with NIF and importe > €100,000 persists and reloads with
  strict pydantic equality in year N and year N+1 independently.
- The counterparty NIF survives unchanged across both exercises (identity continuity).
- The importe values are distinct (year N ≠ year N+1) so field-bleeding surfaces.
- The completeness-manifest pivot casilla (``decl.ejercicio``) is non-zero.
- Anti-tautology probe: omitting the importe casilla produces strict inequality.

Legal grounding: Ley 27/2014 LIS arts. 18-19 (transfer pricing / vinculadas
obligation); RD 634/2015 art. 13 (€100,000 threshold); Orden HFP/816/2017 arts.
1-3 (form layout authority).

Implementation note — observation retrieval:
Uses iter_modelo (full-scan + Python filter). See test_modelo_347_informativa_fidelity.py
for the rationale (EncryptedString column, iter_records bugfix required).
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
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from ..observations_repository import CalculationObservationRepository
from ._multi_year_roundtrip_support import assert_two_ejercicio_round_trip
from ._observation_lookup_support import find_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "232"

#: The two distinct renta ejercicios the fidelity test spans.
_YEAR_N = 2024
_YEAR_N_PLUS_1 = 2025

#: Context label for the EnrollmentRecorder (non-calculation / data-fidelity mode).
_CONTEXT_LABEL = "232-operaciones-vinculadas-related-party-year-over-year"

#: The per-year reporting threshold (RD 634/2015 art. 13). Operations with a single
#: counterparty must be declared when total exceeds €100,000. Used to set non-trivial
#: importe values — both years are above threshold so neither year is vacuously empty.
_THRESHOLD_EUR = Decimal("100000.00")

# Year-N operation amount: above threshold, non-round to distinguish from year N+1.
_IMPORTE_N = Decimal("150000.00")

# Year-N+1 operation amount: different from year N so field-bleeding surfaces.
_IMPORTE_N1 = Decimal("210000.00")

_CLOCK_N = datetime(2025, 1, 25, 10, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_1 = datetime(2026, 1, 25, 10, 0, 0, tzinfo=UTC)


_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id("decl.ejercicio")
_DECL_TIPO_EJERCICIO_CASILLA: CasillaId = validated_casilla_id("decl.tipo-ejercicio")
_VINCULADA_NIF_CASILLA: CasillaId = validated_casilla_id("vinculada-1-nif")
_VINCULADA_TIPO_VINCULACION_CASILLA: CasillaId = validated_casilla_id("vinculada-1-tipo-vinculacion")
_VINCULADA_IMPORTE_CASILLA: CasillaId = validated_casilla_id("vinculada-1-importe")


def _year_n_observation() -> RegistryModeloObservation:
    """Build the year-N 232 observation for a sociedad with one related party.

    Casillas from the "2018-y-siguientes" revision:
    - ``decl.ejercicio`` (informational — filing year)
    - ``decl.tipo-ejercicio`` (informational — 1=natural 12-month year)
    - ``vinculada-1-nif`` (informational — counterparty NIF, encoded as numeric part)
    - ``vinculada-1-tipo-vinculacion`` (informational — "A" = matriz/filial per Orden HFP/816/2017)
    - ``vinculada-1-importe`` (informational — operation amount above €100k threshold)

    All values are non-default. The NIF and tipo-vinculacion survive the roundtrip
    as Decimal-encoded (NIF numeric part) and Decimal-encoded (enum ordinal).
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        casilla_values={
            _DECL_EJERCICIO_CASILLA: Decimal(str(_YEAR_N)),
            _DECL_TIPO_EJERCICIO_CASILLA: Decimal("1"),
            _VINCULADA_NIF_CASILLA: Decimal("33333333"),
            _VINCULADA_TIPO_VINCULACION_CASILLA: Decimal("1"),
            _VINCULADA_IMPORTE_CASILLA: _IMPORTE_N,
        },
    )


def _year_n_plus_1_observation() -> RegistryModeloObservation:
    """Build the year-N+1 232 observation for the same sociedad and counterparty.

    Same NIF and tipo-vinculacion (identity continuity), distinct importe
    (field-bleeding regression would surface as strict inequality).
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_1,
        period="0A",
        casilla_values={
            _DECL_EJERCICIO_CASILLA: Decimal(str(_YEAR_N_PLUS_1)),
            _DECL_TIPO_EJERCICIO_CASILLA: Decimal("1"),
            _VINCULADA_NIF_CASILLA: Decimal("33333333"),
            _VINCULADA_TIPO_VINCULACION_CASILLA: Decimal("1"),
            _VINCULADA_IMPORTE_CASILLA: _IMPORTE_N1,
        },
    )


def test_year_n_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N 232 casilla values survive the encrypted-SQL roundtrip unchanged."""
    assert_two_ejercicio_round_trip(
        tmp_path=tmp_path,
        stage="year_n",
        modelo=_MODELO,
        period="0A",
        obs_n=_year_n_observation(),
        obs_n_plus_1=_year_n_plus_1_observation(),
        year_n=_YEAR_N,
        year_n_plus_1=_YEAR_N_PLUS_1,
        clock_n=_CLOCK_N,
        clock_n_plus_1=_CLOCK_N_PLUS_1,
    )


def test_year_n_plus_1_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N+1 232 casilla values survive the roundtrip with non-year-N amounts."""
    assert_two_ejercicio_round_trip(
        tmp_path=tmp_path,
        stage="year_n_plus_1",
        modelo=_MODELO,
        period="0A",
        obs_n=_year_n_observation(),
        obs_n_plus_1=_year_n_plus_1_observation(),
        year_n=_YEAR_N,
        year_n_plus_1=_YEAR_N_PLUS_1,
        clock_n=_CLOCK_N,
        clock_n_plus_1=_CLOCK_N_PLUS_1,
    )


def test_year_n_and_year_n_plus_1_are_independently_retrievable(tmp_path: Path) -> None:
    """Both exercises are independently addressable and operation amounts do not bleed.

    After persisting both observations:

    - Each reloads to exactly what was stored.
    - Year-N importe (150,000) must not appear in year-N+1 (210,000).
    - Provenance timestamps are distinct.
    """
    loaded_n, loaded_n1 = assert_two_ejercicio_round_trip(
        tmp_path=tmp_path,
        stage="both",
        modelo=_MODELO,
        period="0A",
        obs_n=_year_n_observation(),
        obs_n_plus_1=_year_n_plus_1_observation(),
        year_n=_YEAR_N,
        year_n_plus_1=_YEAR_N_PLUS_1,
        clock_n=_CLOCK_N,
        clock_n_plus_1=_CLOCK_N_PLUS_1,
    )
    assert loaded_n is not None
    assert loaded_n1 is not None

    imp_n = loaded_n.observation.casilla_values[_VINCULADA_IMPORTE_CASILLA]
    imp_n1 = loaded_n1.observation.casilla_values[_VINCULADA_IMPORTE_CASILLA]
    assert imp_n == _IMPORTE_N, f"year-N importe should be {_IMPORTE_N}; got {imp_n}"
    assert imp_n1 == _IMPORTE_N1, f"year-N+1 importe should be {_IMPORTE_N1}; got {imp_n1}"


def test_related_party_nif_identity_persists_across_both_exercises(tmp_path: Path) -> None:
    """The counterparty NIF stored in year N survives into year N+1 unchanged.

    LIS art. 18 requires vinculadas declarations to identify the related party
    precisely. The NIF is the identity anchor. A serialiser that truncates or
    coerces the NIF would break cross-year counterparty reconciliation.
    """
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

        nif_n = loaded_n.observation.casilla_values.get(_VINCULADA_NIF_CASILLA)
        nif_n1 = loaded_n1.observation.casilla_values.get(_VINCULADA_NIF_CASILLA)
        assert nif_n is not None, "year-N observation missing vinculada-1-nif"
        assert nif_n1 is not None, "year-N+1 observation missing vinculada-1-nif"
        assert nif_n == Decimal("33333333"), f"NIF round-trip failed in year N: got {nif_n}"
        assert nif_n1 == Decimal("33333333"), f"NIF round-trip failed in year N+1: got {nif_n1}"
        assert nif_n == nif_n1, "counterparty NIF drifted between year N and year N+1"


def test_importe_exceeds_threshold_in_both_years(tmp_path: Path) -> None:
    """Both yearly amounts exceed the €100,000 declaration threshold.

    RD 634/2015 art. 13 gates the M232 filing obligation at €100,000 of
    operations per counterparty per ejercicio. A roundtrip that silently zeros
    the importe would produce a threshold-failing (non-declarable-looking)
    observation. This test confirms both stored importes exceed the threshold.
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
        imp_n = loaded_n.observation.casilla_values.get(_VINCULADA_IMPORTE_CASILLA)
        imp_n1 = loaded_n1.observation.casilla_values.get(_VINCULADA_IMPORTE_CASILLA)
        assert imp_n is not None and imp_n > _THRESHOLD_EUR, (
            f"year-N importe {imp_n} must exceed threshold {_THRESHOLD_EUR}"
        )
        assert imp_n1 is not None and imp_n1 > _THRESHOLD_EUR, (
            f"year-N+1 importe {imp_n1} must exceed threshold {_THRESHOLD_EUR}"
        )


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: omitting vinculada-1-importe produces strict inequality.

    An observation missing the load-bearing amount casilla must be strictly
    unequal to the full observation, proving the roundtrip assertions would
    catch a save-drops-field regression on the amount field.
    """
    obs_n = _year_n_observation()
    obs_n_no_importe = RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        observations=tuple(o for o in obs_n.observations if o.casilla_id != _VINCULADA_IMPORTE_CASILLA),
    )

    assert obs_n != obs_n_no_importe, (
        "the full observation and the importe-omitted observation must be strictly unequal"
    )

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")

        assert loaded is not None
        assert loaded.observation != obs_n_no_importe, (
            "loaded observation equals the importe-omitted stub — the roundtrip silently dropped vinculada-1-importe"
        )
        assert loaded.observation == obs_n


def test_enrollment_recorder_evidences_two_distinct_renta_years_and_matches_manifest(
    tmp_path: Path,
) -> None:
    """EnrollmentRecorder proves both exercises and matches the authorization manifest.

    Drives the real CalculationObservationRepository for both years, records each
    through record_context_year (non-calculation mode), and calls
    assert_enrollment_matches_manifest. The manifest entry (authorization.d/232.toml)
    must declare renta_years = [2024, 2025] in the same commit as this test.
    """
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        # --- Year N -------------------------------------------------------
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")
        assert loaded_n is not None
        assert loaded_n.observation == obs_n
        _count_n = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N)

        # --- Year N+1 -----------------------------------------------------
        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period="0A")
        assert loaded_n1 is not None
        assert loaded_n1.observation == obs_n1
        _count_n1 = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N_PLUS_1)

    # --- Enrollment recording (outside the profile context) ---------------
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
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1), (
        f"expected distinct renta years {(_YEAR_N, _YEAR_N_PLUS_1)!r}; got {evidence.distinct_renta_years!r}"
    )

    assert_enrollment_matches_manifest(evidence)
