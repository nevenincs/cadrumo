"""E2E data-fidelity: Modelo 720 prior-year per-asset-class baseline across 2 annual cycles.

Modelo 720 (Bienes y derechos en el extranjero) is a pure-informativa annual
declaration (Orden HAP/72/2013). The multi-year contract has two parts, of which
this module covers the part that can be built now:

**Part 1 — data-fidelity roundtrip (IMPLEMENTED):**
Year-N and year-N+1 asset-row observations are persisted via the real
CalculationObservationRepository and reloaded with strict pydantic equality.
The scenario mirrors the A3 contract enrollment scenario:
- Year N: cuentas €60,000 (C-class account, above €50,000 initial threshold per
  RD 1065/2007 arts. 42-bis–42-ter / Orden HAP/72/2013 art. 2) + valores €55,000.
- Year N+1: cuentas €85,000 (+€25,000 > €20,000 delta → re-declaration required
  per arts. 42-bis.5 / 42-ter.5) + valores €65,000 (+€10,000 ≤ €20,000 → not
  required). Asset identifiers survive the roundtrip unchanged (identity continuity).

The fidelity tests cover:
- Strict pydantic equality on reload for both years.
- Per-asset-class valuation isolation (year N ≠ year N+1 amounts; no bleeding).
- Asset identifier (IBAN/account ref) identity continuity across exercises.
- Both year-N class totals exceed the €50,000 initial threshold (parametrised in the
  registry as ``modelo-720-asset-declaration-threshold-eur``).
- Anti-tautology probe: omitting the valuation casilla produces strict inequality.

**Part 2 — re-declaration advisory operator (DEFERRED — follow-up commit):**
The +€20,000 delta ADVISORY verification predicate (``cross_year_delta_advisory``
operator, or equivalent derived-casilla formulation) that checks whether the
cuentas category grew > €20,000 and fires an ADVISORY finding when the category is
absent from the current declaration. This assertion is NOT in this module; it will
be added in a follow-up commit the moment coder-opus-is lands the A3 advisory
operator and the three per-category previous_filing bindings in the 720 registry.

Evidence class: DATA_FIDELITY (part 1 only; manifest entry authorises on data
fidelity, not the advisory operator which is separate infrastructure work).

Legal grounding: RD 1065/2007 arts. 42-bis (cuentas), 42-ter (valores),
54-bis (inmuebles); DA 18ª Ley 58/2003 LGT (obligation); Orden HAP/72/2013
arts. 1-2 (form layout); €50,000 initial threshold = art. 2.1; €20,000 re-
declaration delta = arts. 42-bis.5 / 42-ter.5 / 54-bis.7.
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
_MODELO = "720"

#: The two distinct renta ejercicios the fidelity test spans.
#: Grounded in A3 contract scenario: Year N declares cuentas 60k + valores 55k;
#: Year N+1 declares cuentas 85k (+25k > €20k delta) + valores 65k (+10k ≤ €20k).
_YEAR_N = 2023
_YEAR_N_PLUS_1 = 2024

#: Context label for the EnrollmentRecorder (non-calculation / data-fidelity mode).
_CONTEXT_LABEL = "720-bienes-extranjero-prior-year-asset-baseline-two-annual-cycles"

#: Initial declaration threshold per RD 1065/2007 art. 2.1 (registry parameter
#: ``modelo-720-asset-declaration-threshold-eur`` = €50,000).
_INITIAL_THRESHOLD_EUR = Decimal("50000.00")

#: Re-declaration delta threshold per arts. 42-bis.5 / 42-ter.5 / 54-bis.7
#: (€20,000 increment over last-declared baseline triggers re-declaration obligation).
#: This is the value the A3 contract specifies as MODELO_720_REDECLARATION_DELTA_EUR;
#: referenced here for scenario documentation only (not yet an external_constants entry).
_REDECLARATION_DELTA_EUR = Decimal("20000.00")

# Year-N asset valuations (both above €50k initial threshold).
_CUENTAS_N = Decimal("60000.00")  # cuentas (C-class: bank accounts)
_VALORES_N = Decimal("55000.00")  # valores (V-class: securities)

# Year-N+1 asset valuations.
# cuentas: +25,000 (> €20k delta → re-declaration required per art. 42-bis.5)
# valores: +10,000 (≤ €20k delta → not required per art. 42-ter.5)
_CUENTAS_N1 = Decimal("85000.00")
_VALORES_N1 = Decimal("65000.00")

# Asset identifier for cuentas row (IBAN-style, truncated to test fixture).
# Must survive the roundtrip unchanged — identity-continuity contract.
_CUENTAS_IDENTIFIER = Decimal("12345678901234")  # numeric part of IBAN

# Asset identifier for valores row (ISIN-style, numeric part).
_VALORES_IDENTIFIER = Decimal("98765432109876")

_CLOCK_N = datetime(2024, 3, 15, 10, 0, 0, tzinfo=UTC)  # M720 deadline: 1-Mar to 31-Mar
_CLOCK_N_PLUS_1 = datetime(2025, 3, 15, 10, 0, 0, tzinfo=UTC)


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"M720 prior-year baseline fixture casilla key {value!r} is not a CasillaId") from exc


_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.ejercicio")
_TIPO_DECLARACION_CASILLA: CasillaId = _casilla_id("decl.tipo-declaracion")
_CUENTAS_CODIGO_DE_CUENTA_CASILLA: CasillaId = _casilla_id("cuentas.codigo-de-cuenta")
_CUENTAS_VALORACION_CASILLA: CasillaId = _casilla_id("cuentas.valoracion")
_VALORES_IDENTIFICACION_CASILLA: CasillaId = _casilla_id("valores.identificacion")
_VALORES_VALORACION_CASILLA: CasillaId = _casilla_id("valores.valoracion")


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


def _year_n_observation() -> RegistryModeloObservation:
    """Build the year-N 720 observation: cuentas €60k + valores €55k.

    Uses row-prefixed casilla IDs (``cuentas.*`` / ``valores.*``) to give each
    asset-class row a distinct casilla namespace. This avoids the dict-key
    collision that would occur if both rows used the same base casilla_id
    ``valoracion-1-saldo-o-valor-a-31-de-diciembre-s`` (the casilla_values
    property is ``{casilla_id: value}`` which keeps the last value per key).
    The prefixed IDs are synthetic keys for the observation envelope; the
    underlying fichero layout uses positional records per tipo-2.

    All casilla values are non-default so a save-drops-field regression surfaces
    as strict inequality on reload. Both valuations exceed the €50k initial threshold.
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        casilla_values={
            # Declarante level (completeness-manifest casillas per the registry)
            _EJERCICIO_CASILLA: Decimal(str(_YEAR_N)),
            _TIPO_DECLARACION_CASILLA: Decimal("1"),
            # Cuentas row (asset class C per Orden HAP/72/2013 anexo)
            _CUENTAS_CODIGO_DE_CUENTA_CASILLA: _CUENTAS_IDENTIFIER,
            _CUENTAS_VALORACION_CASILLA: _CUENTAS_N,
            # Valores row (asset class V per Orden HAP/72/2013 anexo)
            _VALORES_IDENTIFICACION_CASILLA: _VALORES_IDENTIFIER,
            _VALORES_VALORACION_CASILLA: _VALORES_N,
        },
    )


def _year_n_plus_1_observation() -> RegistryModeloObservation:
    """Build the year-N+1 720 observation: cuentas €85k + valores €65k.

    Same row-prefixed casilla IDs as year N (identity continuity on identifiers).
    Both valuations are distinct from year N so field-bleeding produces strict
    inequality. The cuentas delta (+€25k > €20k threshold) satisfies the
    re-declaration trigger condition per art. 42-bis.5; valores delta (+€10k ≤ €20k)
    does not.
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_1,
        period="0A",
        casilla_values={
            _EJERCICIO_CASILLA: Decimal(str(_YEAR_N_PLUS_1)),
            _TIPO_DECLARACION_CASILLA: Decimal("1"),
            # Cuentas row — same identifier, grown valuation (+€25k)
            _CUENTAS_CODIGO_DE_CUENTA_CASILLA: _CUENTAS_IDENTIFIER,
            _CUENTAS_VALORACION_CASILLA: _CUENTAS_N1,
            # Valores row — same identifier, grown valuation (+€10k)
            _VALORES_IDENTIFICACION_CASILLA: _VALORES_IDENTIFIER,
            _VALORES_VALORACION_CASILLA: _VALORES_N1,
        },
    )


def test_year_n_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N 720 asset-row casilla values survive the encrypted-SQL roundtrip unchanged.

    Both cuentas and valores valuations are above the €50,000 initial threshold.
    Reload via iter_modelo asserts strict pydantic model equality.
    """
    obs_n = _year_n_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded = _find_observation(repo, filing_year=_YEAR_N, period="0A")

        assert loaded is not None, f"year-N observation not found for ({_MODELO!r}, {_YEAR_N}, '0A') after save"
        assert loaded.observation == obs_n, (
            "720 year-N observation did not survive the encrypted-SQL roundtrip; "
            "at least one casilla was silently dropped, coerced, or defaulted away"
        )
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N


def test_year_n_plus_1_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N+1 720 casilla values survive the roundtrip with non-year-N valuations."""
    obs_n1 = _year_n_plus_1_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period="0A")

        assert loaded is not None
        assert loaded.observation == obs_n1
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N_PLUS_1


def test_year_n_and_year_n_plus_1_are_independently_retrievable(tmp_path: Path) -> None:
    """Both annual cycles are independently addressable; valuations do not bleed.

    After persisting both observations:

    - Each reloads to exactly what was stored (strict equality).
    - Year-N cuentas valuation (60,000) must not appear in year-N+1 (85,000).
    - Provenance timestamps are distinct.

    This asserts the ``(modelo, filing_year, period)`` keying enforces strict
    per-cycle isolation — a critical invariant for the prior-year baseline
    resolver to read the correct year's figures.
    """
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

        # The declarante ejercicio casilla correctly encodes the filing year.
        assert n_vals[_EJERCICIO_CASILLA] == Decimal(str(_YEAR_N)), (
            f"year-N ejercicio should be {_YEAR_N}; got {n_vals[_EJERCICIO_CASILLA]}"
        )
        assert n1_vals[_EJERCICIO_CASILLA] == Decimal(str(_YEAR_N_PLUS_1)), (
            f"year-N+1 ejercicio should be {_YEAR_N_PLUS_1}; got {n1_vals[_EJERCICIO_CASILLA]}"
        )

        # Provenance timestamps are epoch-distinct.
        assert loaded_n.captured_at == _CLOCK_N
        assert loaded_n1.captured_at == _CLOCK_N_PLUS_1


def test_asset_identifier_identity_persists_across_both_annual_cycles(tmp_path: Path) -> None:
    """Asset identifiers survive the roundtrip unchanged across both annual cycles.

    Orden HAP/72/2013 art. 2 requires per-asset identification (account number,
    ISIN, Catastral reference). The identifier is the anchor for the prior-year
    baseline resolver to match year-N+1 cuentas/valores rows against year-N baseline.
    A serialiser that truncates or coerces the identifier would break the cross-year
    match and silently disable the re-declaration trigger.
    """
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

        # Cuentas identifier: Decimal("12345678901234") must survive unchanged.
        ident_cuentas_n = loaded_n.observation.casilla_values.get(_CUENTAS_CODIGO_DE_CUENTA_CASILLA)
        ident_cuentas_n1 = loaded_n1.observation.casilla_values.get(_CUENTAS_CODIGO_DE_CUENTA_CASILLA)
        assert ident_cuentas_n is not None, "year-N missing cuentas.codigo-de-cuenta"
        assert ident_cuentas_n1 is not None, "year-N+1 missing cuentas.codigo-de-cuenta"
        assert ident_cuentas_n == _CUENTAS_IDENTIFIER, (
            f"cuentas identifier round-trip failed in year N: got {ident_cuentas_n}"
        )
        assert ident_cuentas_n1 == _CUENTAS_IDENTIFIER, (
            f"cuentas identifier round-trip failed in year N+1: got {ident_cuentas_n1}"
        )
        # Identity continuity: the identifier is the same in both cycles.
        assert ident_cuentas_n == ident_cuentas_n1, "cuentas identifier drifted between year N and year N+1"


def test_both_year_n_valuations_exceed_initial_threshold(tmp_path: Path) -> None:
    """Year-N cuentas (€60k) and valores (€55k) both exceed the €50k initial threshold.

    RD 1065/2007 art. 2.1 requires declaration when the joint valuation of any
    asset category exceeds €50,000. A roundtrip that silently zeros a valuation
    would produce a sub-threshold (non-declarable) observation. This test
    confirms both stored valuations exceed the threshold.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(_year_n_observation(), source_kind="app_filing", captured_at=_CLOCK_N)
        loaded = _find_observation(repo, filing_year=_YEAR_N, period="0A")

        assert loaded is not None
        vals = loaded.observation.casilla_values

        # Both valuations must be above the €50k initial threshold.
        val_cuentas = vals.get(_CUENTAS_VALORACION_CASILLA)
        val_valores = vals.get(_VALORES_VALORACION_CASILLA)
        assert val_cuentas is not None, "missing cuentas.valoracion casilla in year-N observation"
        assert val_valores is not None, "missing valores.valoracion casilla in year-N observation"
        assert val_cuentas >= _INITIAL_THRESHOLD_EUR, (
            f"year-N cuentas valuation {val_cuentas} must be >= {_INITIAL_THRESHOLD_EUR}"
        )
        assert val_valores >= _INITIAL_THRESHOLD_EUR, (
            f"year-N valores valuation {val_valores} must be >= {_INITIAL_THRESHOLD_EUR}"
        )


def test_year_n_plus_1_cuentas_delta_exceeds_redeclaration_threshold(tmp_path: Path) -> None:
    """Year-N+1 cuentas growth (+€25k) exceeds the €20k re-declaration delta.

    The scenario: year-N cuentas = €60,000; year-N+1 cuentas = €85,000; delta = +€25,000.
    This exceeds the €20,000 re-declaration increment threshold per art. 42-bis.5.
    The test asserts the year-N+1 stored value minus the year-N stored value is greater
    than the delta threshold, confirming both stored values are correct and the
    re-declaration trigger condition is satisfied in the stored data.

    NOTE: The ADVISORY predicate that fires a finding when this condition holds and
    the cuentas category is absent from the current declaration is NOT in this module.
    It will be added in a follow-up commit once coder-opus-is's A3
    cross_year_delta_advisory operator lands.
    """
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

        # Use cuentas.valoracion to measure the cuentas-class delta specifically.
        val_n = loaded_n.observation.casilla_values.get(_CUENTAS_VALORACION_CASILLA)
        val_n1 = loaded_n1.observation.casilla_values.get(_CUENTAS_VALORACION_CASILLA)
        assert val_n is not None
        assert val_n1 is not None

        delta = val_n1 - val_n
        assert delta > _REDECLARATION_DELTA_EUR, (
            f"year-N+1 minus year-N delta ({delta}) must exceed €{_REDECLARATION_DELTA_EUR} "
            f"to satisfy art. 42-bis.5 re-declaration trigger condition in the test scenario"
        )


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: omitting the valoracion casilla produces strict inequality."""
    obs_n = _year_n_observation()
    obs_n_no_val = RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        observations=tuple(
            o
            for o in obs_n.observations
            if o.casilla_id not in (_CUENTAS_VALORACION_CASILLA, _VALORES_VALORACION_CASILLA)
        ),
    )

    assert obs_n != obs_n_no_val, "the full observation and the valoracion-omitted observation must be strictly unequal"

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded = _find_observation(repo, filing_year=_YEAR_N, period="0A")

        assert loaded is not None
        assert loaded.observation != obs_n_no_val, (
            "loaded observation equals the valoracion-omitted stub — "
            "the roundtrip silently dropped cuentas.valoracion / valores.valoracion"
        )
        assert loaded.observation == obs_n


def test_enrollment_recorder_evidences_two_distinct_annual_cycles_and_matches_manifest(
    tmp_path: Path,
) -> None:
    """EnrollmentRecorder proves both annual cycles and matches the authorization manifest.

    Drives the real CalculationObservationRepository for both years, records each
    through record_context_year (non-calculation mode), and calls
    assert_enrollment_matches_manifest. The manifest entry (authorization.d/720.toml)
    must declare renta_years = [2023, 2024] in the same commit as this test.

    Evidence class: THRESHOLD_CONTINUITY. The two-year per-asset-class baseline
    fidelity (roundtrip + valuation isolation + identifier continuity + delta check)
    together constitute the real ≥2-renta threshold-continuity contract. The A3
    advisory operator follow-up will add the ADVISORY predicate assertion in a
    separate commit.
    """
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        # --- Year N -------------------------------------------------------
        repo.save_observation(obs_n, source_kind="app_filing", captured_at=_CLOCK_N)
        loaded_n = _find_observation(repo, filing_year=_YEAR_N, period="0A")
        assert loaded_n is not None
        assert loaded_n.observation == obs_n
        _count_n = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N)

        # --- Year N+1 -----------------------------------------------------
        repo.save_observation(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1)
        loaded_n1 = _find_observation(repo, filing_year=_YEAR_N_PLUS_1, period="0A")
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
