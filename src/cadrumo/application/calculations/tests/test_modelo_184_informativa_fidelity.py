"""E2E data-fidelity: Modelo 184 year-over-year member attribution continuity.

Modelo 184 (Entidades en régimen de atribución de rentas) is a pure-informativa
annual declaration (Orden HAP/2250/2015). There is no calculation engine and
no ``previous_filing`` binding resolver: the entidad's member list and
attribution percentages are keyed independently each ejercicio. The cross-year
invariant is:

- Member identity continuity: the same miembro NIF appears in both ejercicio N
  and N+1.
- Attribution amounts differ: the base_imponible_assigned values are distinct
  between years so a field-bleeding regression surfaces as strict inequality.
- The encrypted-SQL roundtrip preserves all casilla values exactly — no casilla
  is silently dropped, coerced, or defaulted to zero.
- Anti-tautology probe: an observation missing the attribution-amount casilla
  is strictly unequal to the full observation, confirming the roundtrip
  assertions are not vacuously true.

Both years are recorded through the :class:`EnrollmentRecorder` via
``record_context_year`` (non-calculation mode).
:func:`assert_enrollment_matches_manifest` cross-checks the recorded years
against the authorization manifest's declared ``renta_years`` claim.

Legal grounding: Orden HAP/2250/2015 arts. 1-5 (layout authority); Ley 35/2006
LIRPF arts. 87-89 (atribución de rentas regime); Ley 58/2003 LGT art. 93
(informativa obligation).

Implementation note — observation retrieval pattern:
The ``CalculationObservationRepository`` persists envelopes with an encrypted
``object_key`` column (``EncryptedString``) for at-rest key privacy. The
production retrieval path is ``iter_modelo`` (full-scan + in-Python filter by
modelo) rather than a SQL ``WHERE object_key = ?`` query. These tests follow
the production pattern: save then scan with ``iter_modelo``, filtering by
``(filing_year, period)`` to locate the expected envelope.
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
_MODELO = "184"

#: The two distinct renta ejercicios the fidelity test spans.
_YEAR_N = 2024
_YEAR_N_PLUS_1 = 2025

#: Context label for the EnrollmentRecorder (non-calculation mode).
_CONTEXT_LABEL = "184-informativa-member-attribution-year-over-year"

# Year-N attribution amount: member holds 60% of 12,000 EUR base.
_BASE_N_A = Decimal("7200.00")

# Year-N+1 attribution amount: same member, 60% of 15,000 EUR base.
_BASE_N1_A = Decimal("9000.00")

# Clave del tipo de renta atribuida (casilla 77).
# 4 represents actividades económicas (Ley 35/2006 art. 88).
_CLAVE_RENTA = Decimal("4")

# Subclave (casillas 78-79). 1 = rentas obtenidas en España.
_SUBCLAVE_RENTA = Decimal("1")

_CLOCK_N = datetime(2025, 2, 5, 10, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_1 = datetime(2026, 2, 5, 10, 0, 0, tzinfo=UTC)


_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id("decl.ejercicio")
_DECL_TIPO_DECLARACION_CASILLA: CasillaId = validated_casilla_id("decl.tipo-declaracion")
_TIPO2_CLAVE_CASILLA: CasillaId = validated_casilla_id("tipo2.clave")
_TIPO2_SUBCLAVE_CASILLA: CasillaId = validated_casilla_id("tipo2.subclave")
_TIPO3_MIEMBRO_NIF_CASILLA: CasillaId = validated_casilla_id("tipo3.miembro-nif")
_TIPO2_RENTA_ATRIBUIBLE_IMPORTE_CASILLA: CasillaId = validated_casilla_id("tipo2.renta-atribuible-importe")


def _year_n_observation() -> RegistryModeloObservation:
    """Build the year-N 184 observation for an entidad with one member.

    The member has a non-default attribution amount so a default-silently-zero
    regression surfaces as strict inequality on reload. The casilla layout
    follows the M184 registry (revision "2025-y-siguientes"):

    - ``decl.ejercicio`` (informational — filing year)
    - ``decl.tipo-declaracion`` (informational — 1=originaria)
    - ``tipo2.clave`` (casilla 77 — renta class)
    - ``tipo2.subclave`` (casillas 78-79 — renta subtype)
    - ``tipo3.miembro-nif`` (casillas 18-26 — miembro NIF, on the socio record;
      the tipo-2 field at 9-17 is the DECLARANTE NIF, which is why a casilla
      named for the member was removed from that position)
    - ``tipo2.renta-atribuible-importe`` (casillas 178-190 — attribution amount)
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        casilla_values={
            _DECL_EJERCICIO_CASILLA: Decimal(str(_YEAR_N)),
            _DECL_TIPO_DECLARACION_CASILLA: Decimal("1"),
            _TIPO2_CLAVE_CASILLA: _CLAVE_RENTA,
            _TIPO2_SUBCLAVE_CASILLA: _SUBCLAVE_RENTA,
            # NIF encoded as numeric part (NIF "11111111A" → 11111111).
            _TIPO3_MIEMBRO_NIF_CASILLA: Decimal("11111111"),
            _TIPO2_RENTA_ATRIBUIBLE_IMPORTE_CASILLA: _BASE_N_A,
        },
    )


def _year_n_plus_1_observation() -> RegistryModeloObservation:
    """Build the year-N+1 184 observation for the same entidad.

    The same member appears with the same NIF but a different attribution amount
    (9,000 vs 7,200 in year N). Any field-bleeding regression will surface as
    strict inequality.
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_1,
        period="0A",
        casilla_values={
            _DECL_EJERCICIO_CASILLA: Decimal(str(_YEAR_N_PLUS_1)),
            _DECL_TIPO_DECLARACION_CASILLA: Decimal("1"),
            _TIPO2_CLAVE_CASILLA: _CLAVE_RENTA,
            _TIPO2_SUBCLAVE_CASILLA: _SUBCLAVE_RENTA,
            # Same NIF as year N — identity continuity across exercises.
            _TIPO3_MIEMBRO_NIF_CASILLA: Decimal("11111111"),
            _TIPO2_RENTA_ATRIBUIBLE_IMPORTE_CASILLA: _BASE_N1_A,
        },
    )


def test_year_n_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N 184 casilla values survive the encrypted-SQL roundtrip unchanged.

    All values are non-default. The reload via iter_modelo asserts strict pydantic
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
    """Year-N+1 184 casilla values survive the roundtrip with non-year-N amounts."""
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
    """Both exercises are independently addressable and their amounts do not bleed.

    After persisting both observations:

    - Each reloads to exactly what was stored.
    - Year-N attribution amount (7,200) must not appear in year-N+1 (9,000).
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

    n_vals = loaded_n.observation.casilla_values
    n1_vals = loaded_n1.observation.casilla_values

    assert n_vals[_TIPO2_RENTA_ATRIBUIBLE_IMPORTE_CASILLA] == _BASE_N_A, (
        f"year-N importe should be {_BASE_N_A}; got {n_vals[_TIPO2_RENTA_ATRIBUIBLE_IMPORTE_CASILLA]}"
    )
    assert n1_vals[_TIPO2_RENTA_ATRIBUIBLE_IMPORTE_CASILLA] == _BASE_N1_A, (
        f"year-N+1 importe should be {_BASE_N1_A}; got {n1_vals[_TIPO2_RENTA_ATRIBUIBLE_IMPORTE_CASILLA]}"
    )


def test_member_nif_identity_persists_across_both_exercises(tmp_path: Path) -> None:
    """The miembro NIF stored in year N persists into year N+1 unchanged.

    Ley 35/2006 art. 87 requires the entidad to attribute income to identified
    members. The NIF is the identity anchor for cross-year member reconciliation.
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

        nif_n = loaded_n.observation.casilla_values.get(_TIPO3_MIEMBRO_NIF_CASILLA)
        nif_n1 = loaded_n1.observation.casilla_values.get(_TIPO3_MIEMBRO_NIF_CASILLA)
        assert nif_n is not None, "year-N observation missing tipo3.miembro-nif casilla"
        assert nif_n1 is not None, "year-N+1 observation missing tipo3.miembro-nif casilla"
        assert nif_n == Decimal("11111111"), f"NIF round-trip failed in year N: got {nif_n}"
        assert nif_n1 == Decimal("11111111"), f"NIF round-trip failed in year N+1: got {nif_n1}"
        assert nif_n == nif_n1, f"miembro NIF drifted between year N ({nif_n}) and year N+1 ({nif_n1})"


def test_renta_atribuible_casilla_is_present_and_non_zero_in_both_years(tmp_path: Path) -> None:
    """The attribution amount casilla (178-190) is non-zero in both exercises.

    Completeness-manifest pivot check: the registry's completeness_manifest
    declares ``tipo2.renta-atribuible-importe`` (casillas 178-190) as the
    primary declarable casilla. A reload that silently zeros this field produces
    a content-empty observation indistinguishable from a blank declaration.
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
        val_n = loaded_n.observation.casilla_values.get(_TIPO2_RENTA_ATRIBUIBLE_IMPORTE_CASILLA)
        val_n1 = loaded_n1.observation.casilla_values.get(_TIPO2_RENTA_ATRIBUIBLE_IMPORTE_CASILLA)
        assert val_n is not None and val_n > Decimal("0"), (
            f"year-N tipo2.renta-atribuible-importe must be non-zero; got {val_n}"
        )
        assert val_n1 is not None and val_n1 > Decimal("0"), (
            f"year-N+1 tipo2.renta-atribuible-importe must be non-zero; got {val_n1}"
        )


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: an observation missing the attribution-amount casilla is strictly unequal.

    A mutated observation that omits ``tipo2.renta-atribuible-importe`` must be
    strictly unequal to the full observation, proving the roundtrip assertions
    would catch a save-drops-field regression on the attribution pivot field.
    """
    obs_n = _year_n_observation()
    obs_n_no_importe = RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        observations=tuple(o for o in obs_n.observations if o.casilla_id != _TIPO2_RENTA_ATRIBUIBLE_IMPORTE_CASILLA),
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
            "loaded observation equals the importe-omitted stub — "
            "the roundtrip silently dropped tipo2.renta-atribuible-importe"
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

    A stub or single-year recording turns this test RED, and consequently turns
    test_authorization_coverage_report_and_validity in
    test_modelo_authorization_gate.py RED because the meta-test checks the
    contract call is present in this file.
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
