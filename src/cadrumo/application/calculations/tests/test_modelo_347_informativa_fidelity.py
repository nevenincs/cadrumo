"""E2E data-fidelity: Modelo 347 year-over-year counterparty identity continuity.

Modelo 347 (Operaciones con terceras personas) is a pure-informativa annual
declaration (Orden EHA/3012/2008). There is no calculation engine and no
``previous_filing`` binding resolver: the operator keys each ejercicio's
counterparty list independently. The cross-year invariant is data-fidelity
and identity continuity across the :class:`CalculationObservationRepository`
persistence boundary:

- A counterparty whose total operations in ejercicio N exceed the €3,000
  reporting threshold (Orden EHA/3012/2008 art. 3.1) is persisted in the
  year-N declaration.
- The same counterparty appears again in ejercicio N+1 with a distinct
  quarterly breakdown.
- After both observations are persisted, each can be scanned from the store
  and the casilla values are exactly equal to what was stored — no field is
  silently dropped, coerced, or defaulted away.
- The counterparty NIF, clave-operacion, and every quarterly importe survive
  the encrypted-SQL roundtrip unchanged.
- Anti-tautology probe: a mutated observation that omits a casilla is strictly
  unequal to the full observation, confirming the roundtrip assertions are not
  vacuously true.

Both years are recorded through the :class:`EnrollmentRecorder` via
``record_context_year`` (non-calculation mode; the context label is the
un-fakeable evidence token for data-fidelity modelos).
:func:`assert_enrollment_matches_manifest` cross-checks the recorded years
against the authorization manifest's declared ``renta_years`` claim.

Legal grounding: Orden EHA/3012/2008 art. 3.1 (€3,000 threshold per
counterparty); RD 1065/2007 art. 31 (quarterly breakdown fields);
Orden HAC/1431/2025 (2025 revision of the form layout).

Implementation note — observation retrieval pattern:
The ``CalculationObservationRepository`` persists envelopes with an encrypted
``object_key`` column (``EncryptedString``) for at-rest key privacy. The
production retrieval path is ``iter_modelo`` (full-scan + in-Python filter by
modelo) rather than a SQL ``WHERE object_key = ?`` query (which cannot match
the stored ciphertext since AES-256-GCM uses a random nonce). These tests
follow the production pattern: save then scan with ``iter_modelo``, filtering
by ``(filing_year, period)`` to locate the expected envelope.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, validated_casilla_id
from ....domain.calculations.registry import (
    RegistryModeloObservation,
)
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository
from ._multi_year_roundtrip_support import assert_two_ejercicio_round_trip
from ._observation_lookup_support import find_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "347"

#: The two distinct renta ejercicios the fidelity test spans.
_YEAR_N = 2024
_YEAR_N_PLUS_1 = 2025

#: Context label used by the enrollment recorder (non-calculation mode).
_CONTEXT_LABEL = "347-informativa-counterparty-identity-year-over-year"

_CLOCK_N = datetime(2025, 2, 10, 9, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_1 = datetime(2026, 2, 10, 9, 0, 0, tzinfo=UTC)


_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id("decl.ejercicio")
_DECL_TIPO_DECLARACION_CASILLA: CasillaId = validated_casilla_id("decl.tipo-declaracion")
_CONTRAPARTE_NIF_CASILLA: CasillaId = validated_casilla_id("contraparte.nif")
_CONTRAPARTE_CLAVE_OPERACION_CASILLA: CasillaId = validated_casilla_id("contraparte.clave-operacion")
_CONTRAPARTE_IMPORTE_Q1_CASILLA: CasillaId = validated_casilla_id("contraparte.importe-Q1")
_CONTRAPARTE_IMPORTE_Q2_CASILLA: CasillaId = validated_casilla_id("contraparte.importe-Q2")
_CONTRAPARTE_IMPORTE_Q3_CASILLA: CasillaId = validated_casilla_id("contraparte.importe-Q3")
_CONTRAPARTE_IMPORTE_Q4_CASILLA: CasillaId = validated_casilla_id("contraparte.importe-Q4")


def _year_n_observation() -> RegistryModeloObservation:
    """Build the year-N 347 observation for a filer with one counterparty.

    Total (Q1+Q2+Q3+Q4) = 1000+1200+900+1500 = 4600 EUR, clearing the €3,000
    threshold per Orden EHA/3012/2008 art. 3.1. All casilla values are non-zero
    so a drop-then-default regression surfaces as strict inequality.
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        casilla_values={
            _DECL_EJERCICIO_CASILLA: Decimal(str(_YEAR_N)),
            _DECL_TIPO_DECLARACION_CASILLA: Decimal("1"),
            _CONTRAPARTE_NIF_CASILLA: Decimal("12345678"),
            _CONTRAPARTE_CLAVE_OPERACION_CASILLA: Decimal("1"),
            _CONTRAPARTE_IMPORTE_Q1_CASILLA: Decimal("1000.00"),
            _CONTRAPARTE_IMPORTE_Q2_CASILLA: Decimal("1200.00"),
            _CONTRAPARTE_IMPORTE_Q3_CASILLA: Decimal("900.00"),
            _CONTRAPARTE_IMPORTE_Q4_CASILLA: Decimal("1500.00"),
        },
    )


def _year_n_plus_1_observation() -> RegistryModeloObservation:
    """Build the year-N+1 347 observation for the same filer.

    The recurring counterparty appears with the same NIF but a different
    quarterly breakdown. All importes are distinct from year N so a cross-year
    field-bleeding regression surfaces as strict inequality.
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_1,
        period="0A",
        casilla_values={
            _DECL_EJERCICIO_CASILLA: Decimal(str(_YEAR_N_PLUS_1)),
            _DECL_TIPO_DECLARACION_CASILLA: Decimal("1"),
            _CONTRAPARTE_NIF_CASILLA: Decimal("12345678"),
            _CONTRAPARTE_CLAVE_OPERACION_CASILLA: Decimal("1"),
            _CONTRAPARTE_IMPORTE_Q1_CASILLA: Decimal("2000.00"),
            _CONTRAPARTE_IMPORTE_Q2_CASILLA: Decimal("2500.00"),
            _CONTRAPARTE_IMPORTE_Q3_CASILLA: Decimal("1800.00"),
            _CONTRAPARTE_IMPORTE_Q4_CASILLA: Decimal("3200.00"),
        },
    )


def test_year_n_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N 347 casilla values survive the encrypted-SQL roundtrip unchanged.

    All values are non-default; reload via iter_modelo asserts strict pydantic
    model equality so a save-drops-field regression surfaces.
    """
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
    """Year-N+1 347 casilla values survive the roundtrip with non-year-N importes."""
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
    """Both exercises are independently addressable; their amounts do not bleed.

    After persisting both observations:

    - Each reloads to exactly what was stored (strict equality).
    - Year-N Q1 importe (1000) must not appear in year-N+1 (2000).
    - Provenance timestamps must be distinct.

    This asserts the ``(filing_year, period)`` isolation the repository enforces.
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

    n_values = loaded_n.observation.casilla_values
    n1_values = loaded_n1.observation.casilla_values

    assert n_values[_CONTRAPARTE_IMPORTE_Q1_CASILLA] == Decimal("1000.00"), (
        f"year-N Q1 importe should be 1000.00; got {n_values[_CONTRAPARTE_IMPORTE_Q1_CASILLA]}"
    )
    assert n1_values[_CONTRAPARTE_IMPORTE_Q1_CASILLA] == Decimal("2000.00"), (
        f"year-N+1 Q1 importe should be 2000.00; got {n1_values[_CONTRAPARTE_IMPORTE_Q1_CASILLA]}"
    )


def test_counterparty_nif_identity_persists_across_both_exercises(tmp_path: Path) -> None:
    """The counterparty NIF stored in year N persists into year N+1 unchanged.

    The identity-continuity assertion for the cross-year threshold mechanism
    (Orden EHA/3012/2008 art. 3.1): a counterparty who triggered the threshold
    in year N must be identifiable as the same entity in year N+1.
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

        nif_n = loaded_n.observation.casilla_values.get(_CONTRAPARTE_NIF_CASILLA)
        nif_n1 = loaded_n1.observation.casilla_values.get(_CONTRAPARTE_NIF_CASILLA)
        assert nif_n is not None, "year-N observation missing contraparte.nif casilla"
        assert nif_n1 is not None, "year-N+1 observation missing contraparte.nif casilla"
        assert nif_n == Decimal("12345678"), f"NIF round-trip failed in year N: got {nif_n}"
        assert nif_n1 == Decimal("12345678"), f"NIF round-trip failed in year N+1: got {nif_n1}"
        assert nif_n == nif_n1, "counterparty NIF drifted between year N and year N+1"


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: a missing casilla in the reloaded observation is detectable.

    A mutated observation that omits Q4 importe is strictly unequal to the full
    observation. This proves the roundtrip assertions in the other tests would
    catch a save-drops-field regression and are not vacuously true.
    """
    obs_n = _year_n_observation()
    obs_n_missing_q4 = RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        observations=tuple(o for o in obs_n.observations if o.casilla_id != _CONTRAPARTE_IMPORTE_Q4_CASILLA),
    )

    assert obs_n != obs_n_missing_q4, "the full observation and the Q4-omitted observation must be strictly unequal"

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")

        assert loaded is not None
        assert loaded.observation != obs_n_missing_q4, (
            "loaded observation equals the Q4-omitted stub — "
            "the roundtrip silently dropped Q4 (save-drops-field regression)"
        )
        assert loaded.observation == obs_n


def test_enrollment_recorder_evidences_two_distinct_renta_years_and_matches_manifest(
    tmp_path: Path,
) -> None:
    """EnrollmentRecorder proves both exercises and matches the authorization manifest.

    This is the gate-enrollment assertion. It drives the real
    CalculationObservationRepository for both years via a real isolated_runtime_profile
    (real encrypted-SQLite backend — no mocks), records each year through
    record_context_year (non-calculation mode), and calls
    assert_enrollment_matches_manifest. The manifest entry must declare
    renta_years = [2024, 2025] in the same commit.

    A stub that records zero years, one year, or a mismatched year set turns this
    test RED — and consequently turns test_authorization_coverage_report_and_validity
    in test_modelo_authorization_gate.py RED because the meta-test checks the
    contract call is present in this file.
    """
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        # --- Year N: persist and verify the fidelity roundtrip ------------------
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")
        assert loaded_n is not None
        assert loaded_n.observation == obs_n
        _count_n = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N)

        # --- Year N+1: persist and verify the fidelity roundtrip ----------------
        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period="0A")
        assert loaded_n1 is not None
        assert loaded_n1.observation == obs_n1
        _count_n1 = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N_PLUS_1)

    # --- Enrollment recording (outside the profile context) -------------------
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
