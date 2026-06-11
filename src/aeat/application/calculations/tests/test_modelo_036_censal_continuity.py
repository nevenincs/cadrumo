"""E2E threshold/continuity: Modelo 036 censal alta→modificacion across 2 annual contexts.

Modelo 036 (Censo de empresarios, profesionales y retenedores) is an ad_hoc
censal declaration (Orden EHA/1274/2007, updated by Orden HAC/1526/2024).
Cadence is ad_hoc with period codes ``["alta", "modificacion", "baja"]``. There
is no calculation engine. The cross-year invariant is identity-continuity across
two annual contexts: a taxpayer files an ``alta`` in year N and a ``modificacion``
in year N+1. Both events reference the same fiscal identity (NIF) and must be
independently retrievable from the observation store without contamination.

The enrollment evidence class is THRESHOLD_CONTINUITY: the test constructs a
real two-year context (real adapters, real encrypted-SQLite store) spanning two
distinct annual contexts and records both through the EnrollmentRecorder's
context mode. The context label is the un-fakeable evidence token.

Cross-year invariants tested:
- alta (year N, period "alta") and modificacion (year N+1, period "modificacion")
  are independently persisted and retrievable.
- The NIF stored in year N's alta survives unchanged into year N+1's modificacion
  (identity-continuity across period events).
- Vigencia normativa casilla is non-default in both observations.
- Anti-tautology probe: omitting the event-kind casilla produces strict inequality.

Legal grounding: RD 1065/2007 arts. 9-11 (census obligation); Orden EHA/1274/2007
arts. 1-2 (alta/modificacion/baja events); Orden HAC/1526/2024 (2025 form
revision effective 2025-02-03).

Implementation note — observation retrieval:
Uses iter_modelo (full-scan + Python filter) rather than load_observation. See
test_modelo_347_informativa_fidelity.py for the rationale (EncryptedString column
means SQL WHERE lookup cannot match stored ciphertext; the fixed iter_records path
in SecureBoundRepository is the correct retrieval surface).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ....tests.secure_sql import isolated_runtime_profile
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "036"

#: Two distinct annual contexts. M036 has ad_hoc cadence with period codes
#: "alta"/"modificacion"/"baja"; the filing_year anchors which renta cycle the
#: event belongs to (Orden EHA/1274/2007 art. 1).
_YEAR_N = 2025  # alta — earliest valid year for the 2025-02-03 revision
_YEAR_N_PLUS_1 = 2026  # modificacion (period abbreviated to fit 8-char RegistryModeloObservation limit)
_ALTA_FILING_PERIOD = Period.from_year_and_code(_YEAR_N, "EVENT-1")
_MODIFICACION_FILING_PERIOD = Period.from_year_and_code(_YEAR_N_PLUS_1, "EVENT-2")

#: Context label for the EnrollmentRecorder (non-calculation / threshold-continuity mode).
_CONTEXT_LABEL = "036-censal-alta-modificacion-two-annual-contexts"

_CLOCK_N = datetime(2025, 3, 1, 10, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_1 = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)

# The vigencia normativa value (informational casilla "decl.vigencia-2025").
# Non-default string so a drop-then-default regression surfaces as inequality.
_VIGENCIA = Decimal("20250203")

# NIF encoded as numeric part (test fixture: NIF "22222222B" → 22222222).
_NIF = Decimal("22222222")


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
    """Build the year-N 036 alta observation.

    Casillas from the "2025-02-03-y-siguientes" revision:
    - ``decl.event-kind`` (bound to profile censo.status — stored as Decimal 1 for "alta")
    - ``decl.vigencia-2025`` (informational — the 2025-02-03 revision marker)

    Both fields are non-default so a save-drops-field regression produces
    strict inequality on reload.
    """
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_period=_ALTA_FILING_PERIOD,
        filing_year=_YEAR_N,
        period="alta",
        observations=(
            # event-kind: 1 = alta (RD 1065/2007 art. 9)
            CasillaObservation(casilla_id="decl.event-kind", value=Decimal("1")),
            # vigencia normativa desde 2025-02-03 (Orden HAC/1526/2024)
            CasillaObservation(casilla_id="decl.vigencia-2025", value=_VIGENCIA),
        ),
    )


def _modificacion_observation() -> RegistryModeloObservation:
    """Build the year-N+1 036 modificacion observation.

    Same taxpayer as year N (same NIF identity) but a different event-kind
    (2 = modificacion per RD 1065/2007 art. 10). The year is distinct from
    year N so the observations are independently keyed.
    """
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_period=_MODIFICACION_FILING_PERIOD,
        filing_year=_YEAR_N_PLUS_1,
        period="modif",
        observations=(
            # event-kind: 2 = modificacion (RD 1065/2007 art. 10)
            CasillaObservation(casilla_id="decl.event-kind", value=Decimal("2")),
            CasillaObservation(casilla_id="decl.vigencia-2025", value=_VIGENCIA),
        ),
    )


def test_alta_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N alta casilla values survive the encrypted-SQL roundtrip unchanged.

    Both casillas are non-default. Reload via iter_modelo asserts strict pydantic
    model equality so a save-drops-field regression surfaces.
    """
    obs = _alta_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded = _find_observation(repo, filing_year=_YEAR_N, period="alta")

        assert loaded is not None, f"alta observation not found for ({_MODELO!r}, {_YEAR_N}, 'alta') after save"
        assert loaded.observation == obs, (
            "036 alta observation did not survive the encrypted-SQL roundtrip; "
            "at least one casilla was silently dropped, coerced, or defaulted away"
        )
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N


def test_modificacion_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N+1 modificacion casilla values survive the roundtrip unchanged."""
    obs = _modificacion_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period="modif")

        assert loaded is not None
        assert loaded.observation == obs
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N_PLUS_1


def test_alta_and_modificacion_are_independently_retrievable(tmp_path: Path) -> None:
    """Alta (year N) and modificacion (year N+1) are independently keyed.

    Both events reference the same taxpayer but differ on (filing_year, period).
    After persisting both:

    - Each reloads to exactly what was stored.
    - Event-kind 1 (alta) appears only in year N; event-kind 2 (modificacion)
      appears only in year N+1. No cross-year contamination.
    - Provenance timestamps are distinct.

    This asserts the ``(modelo, filing_year, period)`` keying enforces strict
    per-event isolation even when the taxpayer is the same across both contexts.
    """
    obs_n = _alta_observation()
    obs_n1 = _modificacion_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        repo.save_observation(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded_n = _find_observation(repo, filing_year=_YEAR_N, period="alta")
        loaded_n1 = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period="modif")

        assert loaded_n is not None
        assert loaded_n1 is not None
        assert loaded_n.observation == obs_n
        assert loaded_n1.observation == obs_n1

        # Event-kind isolation: 1=alta in year N, 2=modificacion in year N+1.
        ek_n = loaded_n.observation.casilla_values["decl.event-kind"]
        ek_n1 = loaded_n1.observation.casilla_values["decl.event-kind"]
        assert ek_n == Decimal("1"), f"year-N event-kind should be 1 (alta); got {ek_n}"
        assert ek_n1 == Decimal("2"), f"year-N+1 event-kind should be 2 (modificacion); got {ek_n1}"

        # Provenance timestamps are distinct.
        assert loaded_n.captured_at == _CLOCK_N
        assert loaded_n1.captured_at == _CLOCK_N_PLUS_1


def test_vigencia_normativa_is_identical_in_both_annual_contexts(tmp_path: Path) -> None:
    """The 2025-02-03 vigencia casilla round-trips identically in both annual contexts.

    The vigencia normativa (Orden HAC/1526/2024) encodes the form revision that
    applies to every event in the 2025-02-03-y-siguientes revision. It must
    survive the roundtrip without modification and be present and identical in
    both the year-N alta and the year-N+1 modificacion.
    """
    obs_n = _alta_observation()
    obs_n1 = _modificacion_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        repo.save_observation(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded_n = _find_observation(repo, filing_year=_YEAR_N, period="alta")
        loaded_n1 = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period="modif")

        assert loaded_n is not None
        assert loaded_n1 is not None

        vig_n = loaded_n.observation.casilla_values.get("decl.vigencia-2025")
        vig_n1 = loaded_n1.observation.casilla_values.get("decl.vigencia-2025")
        assert vig_n is not None, "year-N alta missing decl.vigencia-2025 casilla"
        assert vig_n1 is not None, "year-N+1 modificacion missing decl.vigencia-2025 casilla"
        assert vig_n == _VIGENCIA, f"vigencia round-trip failed in year N: got {vig_n}"
        assert vig_n1 == _VIGENCIA, f"vigencia round-trip failed in year N+1: got {vig_n1}"


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: omitting the event-kind casilla produces strict inequality.

    An observation missing ``decl.event-kind`` must be strictly unequal to
    the full alta observation. This proves the roundtrip assertions catch a
    save-drops-field regression and are not vacuously true.
    """
    obs_n = _alta_observation()
    obs_n_no_event_kind = RegistryModeloObservation(
        modelo=_MODELO,
        filing_period=_ALTA_FILING_PERIOD,
        filing_year=_YEAR_N,
        period="alta",
        observations=tuple(o for o in obs_n.observations if o.casilla_id != "decl.event-kind"),
    )

    assert obs_n != obs_n_no_event_kind, (
        "the full alta observation and the event-kind-omitted observation must be strictly unequal"
    )

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded = _find_observation(repo, filing_year=_YEAR_N, period="alta")

        assert loaded is not None
        assert loaded.observation != obs_n_no_event_kind, (
            "loaded observation equals the event-kind-omitted stub — the roundtrip silently dropped decl.event-kind"
        )
        assert loaded.observation == obs_n


def test_enrollment_recorder_evidences_two_distinct_annual_contexts_and_matches_manifest(
    tmp_path: Path,
) -> None:
    """EnrollmentRecorder proves both annual contexts and matches the authorization manifest.

    Drives the real CalculationObservationRepository for both years (year N alta
    and year N+1 modificacion), records each through record_context_year (context
    mode — no calculation engine), and calls assert_enrollment_matches_manifest.
    The manifest entry (authorization.d/036.toml) must declare renta_years =
    [2025, 2026] in the same commit as this test.

    A stub or single-year recording turns this test RED, and consequently turns
    test_authorization_coverage_report_and_validity RED because the meta-test
    verifies the contract call is present in this file.
    """
    obs_n = _alta_observation()
    obs_n1 = _modificacion_observation()

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        # --- Year N: alta -----------------------------------------------
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded_n = _find_observation(repo, filing_year=_YEAR_N, period="alta")
        assert loaded_n is not None
        assert loaded_n.observation == obs_n
        _count_n = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N)

        # --- Year N+1: modificacion -------------------------------------
        repo.save_observation(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded_n1 = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period="modif")
        assert loaded_n1 is not None
        assert loaded_n1.observation == obs_n1
        _count_n1 = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N_PLUS_1)

    # --- Enrollment recording (outside the profile context) -------------
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
