"""E2E data-fidelity: Modelo 720 prior-year per-asset-class baseline across 2 annual cycles.

Modelo 720 (Bienes y derechos en el extranjero) is a pure-informativa annual
declaration (Orden HAP/72/2013). The multi-year contract has two parts, of which
this module covers the part that can be built now:

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
- The committed ``previous_filing`` bindings resolve the year-N valuation baseline
  from the real local observation store for the year-N+1 filing context.
- The re-declaration advisory consumes that resolved prior baseline and fires only
  for the grown/omitted cuentas block.
- Anti-tautology probe: omitting the valuation casilla produces strict inequality.

Evidence class: THRESHOLD_CONTINUITY.

Legal grounding: RD 1065/2007 arts. 42-bis (cuentas), 42-ter (valores),
54-bis (inmuebles); DA 18ª Ley 58/2003 LGT (obligation); Orden HAP/72/2013
arts. 1-2 (form layout); €50,000 initial threshold = art. 2.1; €20,000 re-
declaration delta = arts. 42-bis.5 / 42-ter.5 / 54-bis.7.

See Also:
    :mod:`~application.calculations._foreign_asset_redeclaration`
        Shared M720/M721 re-declaration advisory implementation exercised here.
    :func:`~application.calculations._foreign_asset_redeclaration.modelo_720_redeclaration_advisory_findings`
        Modelo 720 advisory entry point pinned by the grown/omitted cuentas case.
    :class:`~application.calculations.observations_repository.CalculationObservationRepository`
        Real repository used for the two-year observation roundtrip.
    :class:`~domain.calculations.registry.RegistryModeloObservation`
        Registry-grounded modelo observation envelope persisted by the test.
    :class:`~domain.calculations.registry.CasillaObservation`
        Typed casilla row carrying legal and source provenance.
    :mod:`~application.calculations.tests.test_modelo_721_cripto_extranjero_fidelity`
        Modelo 721 threshold-continuity sibling over the virtual-currency axis.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.foreign_asset_obligation import ForeignAssetObligationGroup
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.modelos.verification_report import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile, isolated_two_bucket_runtime
from ..._foreign_asset_thresholds import foreign_asset_declaration_thresholds
from ...aggregation import CalculationSourceContext
from .._binding_prefill import resolve_bindings_from_local_store
from .._foreign_asset_redeclaration import modelo_720_redeclaration_advisory_findings
from .._multi_year import (
    EnrollmentRecorder,
    PreviousFilingSourceResolver,
    assert_enrollment_matches_manifest,
)
from ..observations_repository import CalculationObservationRepository
from ._multi_year_roundtrip_support import assert_two_ejercicio_round_trip
from ._observation_lookup_support import find_observation

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
_M720_THRESHOLDS = foreign_asset_declaration_thresholds(modelo=_MODELO, filing_year=_YEAR_N_PLUS_1)
_INITIAL_THRESHOLD_EUR = _M720_THRESHOLDS[ForeignAssetObligationGroup.CUENTAS].initial_declaration_floor_eur

#: Re-declaration delta threshold per arts. 42-bis.5 / 42-ter.5 / 54-bis.7
#: (€20,000 increment over last-declared baseline triggers re-declaration obligation).
_REDECLARATION_DELTA_EUR = _M720_THRESHOLDS[ForeignAssetObligationGroup.CUENTAS].redeclaration_increase_delta_eur

# Year-N asset valuations (both above €50k initial threshold).
_CUENTAS_N = Decimal("60000.00")  # cuentas (C-class: bank accounts)
_VALORES_N = Decimal("55000.00")  # valores (V-class: securities)
_INMUEBLES_N = Decimal("0.00")

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


_EJERCICIO_CASILLA: CasillaId = validated_casilla_id("decl.ejercicio")
_TIPO_DECLARACION_CASILLA: CasillaId = validated_casilla_id("decl.tipo-declaracion")
_CUENTAS_CODIGO_DE_CUENTA_CASILLA: CasillaId = validated_casilla_id("cuentas.codigo-de-cuenta")
_CUENTAS_VALORACION_CASILLA: CasillaId = validated_casilla_id("cuentas.valoracion")
_VALORES_IDENTIFICACION_CASILLA: CasillaId = validated_casilla_id("valores.identificacion")
_VALORES_VALORACION_CASILLA: CasillaId = validated_casilla_id("valores.valoracion")
_INMUEBLES_VALORACION_CASILLA: CasillaId = validated_casilla_id("inmuebles.valoracion")

_CUENTAS_BASELINE_BINDING = "modelo-720-prior-year-cuentas-valoracion-baseline"
_VALORES_BASELINE_BINDING = "modelo-720-prior-year-valores-valoracion-baseline"
_INMUEBLES_BASELINE_BINDING = "modelo-720-prior-year-inmuebles-valoracion-baseline"
_BASELINE_BINDINGS = frozenset(
    {
        _CUENTAS_BASELINE_BINDING,
        _VALORES_BASELINE_BINDING,
        _INMUEBLES_BASELINE_BINDING,
    }
)

_M720_SOURCE_REFS = ("aeat-modelo-720-procedure",)
_M720_HEADER_LEGAL_REFS = ("ley-58-2003:da-18",)
_M720_CUENTAS_LEGAL_REFS = _M720_THRESHOLDS[ForeignAssetObligationGroup.CUENTAS].legal_refs
_M720_VALORES_LEGAL_REFS = _M720_THRESHOLDS[ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS].legal_refs
_M720_INMUEBLES_LEGAL_REFS = _M720_THRESHOLDS[ForeignAssetObligationGroup.INMUEBLES].legal_refs
_M720_CASILLA_LEGAL_REFS = {
    _CUENTAS_CODIGO_DE_CUENTA_CASILLA: _M720_CUENTAS_LEGAL_REFS,
    _CUENTAS_VALORACION_CASILLA: _M720_CUENTAS_LEGAL_REFS,
    _VALORES_IDENTIFICACION_CASILLA: _M720_VALORES_LEGAL_REFS,
    _VALORES_VALORACION_CASILLA: _M720_VALORES_LEGAL_REFS,
    _INMUEBLES_VALORACION_CASILLA: _M720_INMUEBLES_LEGAL_REFS,
}


def _advisory_observation(
    *,
    filing_year: int,
    casilla_values: tuple[tuple[CasillaId, Decimal], ...],
) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=filing_year,
        period="0A",
        observations=tuple(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                legal_refs=_M720_CASILLA_LEGAL_REFS.get(casilla_id, _M720_HEADER_LEGAL_REFS),
                source_refs=_M720_SOURCE_REFS,
            )
            for casilla_id, value in casilla_values
        ),
    )


def _year_n_advisory_observation() -> RegistryModeloObservation:
    return _advisory_observation(
        filing_year=_YEAR_N,
        casilla_values=(
            (_EJERCICIO_CASILLA, Decimal(str(_YEAR_N))),
            (_TIPO_DECLARACION_CASILLA, Decimal("1")),
            (_CUENTAS_CODIGO_DE_CUENTA_CASILLA, _CUENTAS_IDENTIFIER),
            (_CUENTAS_VALORACION_CASILLA, _CUENTAS_N),
            (_VALORES_IDENTIFICACION_CASILLA, _VALORES_IDENTIFIER),
            (_VALORES_VALORACION_CASILLA, _VALORES_N),
        ),
    )


def _year_n_plus_1_advisory_observation() -> RegistryModeloObservation:
    return _advisory_observation(
        filing_year=_YEAR_N_PLUS_1,
        casilla_values=(
            (_EJERCICIO_CASILLA, Decimal(str(_YEAR_N_PLUS_1))),
            (_TIPO_DECLARACION_CASILLA, Decimal("1")),
            (_CUENTAS_CODIGO_DE_CUENTA_CASILLA, _CUENTAS_IDENTIFIER),
            (_CUENTAS_VALORACION_CASILLA, _CUENTAS_N1),
            (_VALORES_IDENTIFICACION_CASILLA, _VALORES_IDENTIFIER),
            (_VALORES_VALORACION_CASILLA, _VALORES_N1),
        ),
    )


def _year_n_plus_1_advisory_without_cuentas() -> RegistryModeloObservation:
    return _advisory_observation(
        filing_year=_YEAR_N_PLUS_1,
        casilla_values=(
            (_EJERCICIO_CASILLA, Decimal(str(_YEAR_N_PLUS_1))),
            (_TIPO_DECLARACION_CASILLA, Decimal("1")),
            (_VALORES_IDENTIFICACION_CASILLA, _VALORES_IDENTIFIER),
            (_VALORES_VALORACION_CASILLA, _VALORES_N1),
        ),
    )


def _year_n_plus_1_advisory_without_valores() -> RegistryModeloObservation:
    return _advisory_observation(
        filing_year=_YEAR_N_PLUS_1,
        casilla_values=(
            (_EJERCICIO_CASILLA, Decimal(str(_YEAR_N_PLUS_1))),
            (_TIPO_DECLARACION_CASILLA, Decimal("1")),
            (_CUENTAS_CODIGO_DE_CUENTA_CASILLA, _CUENTAS_IDENTIFIER),
            (_CUENTAS_VALORACION_CASILLA, _CUENTAS_N1),
        ),
    )


def _prior_baseline_observation_from_bindings(binding_values: dict[str, Decimal]) -> RegistryModeloObservation:
    return _advisory_observation(
        filing_year=_YEAR_N,
        casilla_values=(
            (_CUENTAS_VALORACION_CASILLA, binding_values[_CUENTAS_BASELINE_BINDING]),
            (_VALORES_VALORACION_CASILLA, binding_values[_VALORES_BASELINE_BINDING]),
            (_INMUEBLES_VALORACION_CASILLA, binding_values[_INMUEBLES_BASELINE_BINDING]),
        ),
    )


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


def _year_n_observation_with_explicit_inmuebles_zero() -> RegistryModeloObservation:
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        casilla_values={
            _EJERCICIO_CASILLA: Decimal(str(_YEAR_N)),
            _TIPO_DECLARACION_CASILLA: Decimal("1"),
            _CUENTAS_CODIGO_DE_CUENTA_CASILLA: _CUENTAS_IDENTIFIER,
            _CUENTAS_VALORACION_CASILLA: _CUENTAS_N,
            _VALORES_IDENTIFICACION_CASILLA: _VALORES_IDENTIFIER,
            _VALORES_VALORACION_CASILLA: _VALORES_N,
            _INMUEBLES_VALORACION_CASILLA: _INMUEBLES_N,
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


def _year_n_plus_1_observation_without_cuentas() -> RegistryModeloObservation:
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_1,
        period="0A",
        casilla_values={
            _EJERCICIO_CASILLA: Decimal(str(_YEAR_N_PLUS_1)),
            _TIPO_DECLARACION_CASILLA: Decimal("1"),
            _VALORES_IDENTIFICACION_CASILLA: _VALORES_IDENTIFIER,
            _VALORES_VALORACION_CASILLA: _VALORES_N1,
        },
    )


def _year_n_plus_1_observation_without_valores() -> RegistryModeloObservation:
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_1,
        period="0A",
        casilla_values={
            _EJERCICIO_CASILLA: Decimal(str(_YEAR_N_PLUS_1)),
            _TIPO_DECLARACION_CASILLA: Decimal("1"),
            _CUENTAS_CODIGO_DE_CUENTA_CASILLA: _CUENTAS_IDENTIFIER,
            _CUENTAS_VALORACION_CASILLA: _CUENTAS_N1,
        },
    )


def test_year_n_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N 720 asset-row casilla values survive the encrypted-SQL roundtrip unchanged.

    Both cuentas and valores valuations are above the €50,000 initial threshold.
    Reload via iter_modelo asserts strict pydantic model equality.
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
    """Year-N+1 720 casilla values survive the roundtrip with non-year-N valuations."""
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
    """Both annual cycles are independently addressable; valuations do not bleed.

    After persisting both observations:

    - Each reloads to exactly what was stored (strict equality).
    - Year-N cuentas valuation (60,000) must not appear in year-N+1 (85,000).
    - Provenance timestamps are distinct.

    This asserts the ``(modelo, filing_year, period)`` keying enforces strict
    per-cycle isolation — a critical invariant for the prior-year baseline
    resolver to read the correct year's figures.
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

    # The declarante ejercicio casilla correctly encodes the filing year.
    assert n_vals[_EJERCICIO_CASILLA] == Decimal(str(_YEAR_N)), (
        f"year-N ejercicio should be {_YEAR_N}; got {n_vals[_EJERCICIO_CASILLA]}"
    )
    assert n1_vals[_EJERCICIO_CASILLA] == Decimal(str(_YEAR_N_PLUS_1)), (
        f"year-N+1 ejercicio should be {_YEAR_N_PLUS_1}; got {n1_vals[_EJERCICIO_CASILLA]}"
    )


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
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period="0A")

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
        repo.save(
            repo.prepare_observation_envelope(_year_n_observation(), source_kind="app_filing", captured_at=_CLOCK_N)
        )
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")

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

    The application advisory helper is tested separately below because it also needs
    the current declaration row set to prove the grown category is absent. This is
    advisory-layer coverage only; the registry `previous_filing` bindings are live
    registry data resolved by test_previous_filing_baseline_drives_redeclaration_advisory_for_omitted_grown_cuentas
    below.
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


def test_previous_filing_baseline_drives_redeclaration_advisory_for_omitted_grown_cuentas(tmp_path: Path) -> None:
    obs_n = _year_n_observation_with_explicit_inmuebles_zero()
    assert obs_n.casilla_values[_INMUEBLES_VALORACION_CASILLA] == _INMUEBLES_N
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        snapshot_n1 = bundled_authority().snapshot(_MODELO, filing_year=_YEAR_N_PLUS_1, period="0A")
        report = resolve_bindings_from_local_store(snapshot_n1, repository=repo, captured_at=_CLOCK_N_PLUS_1)

    assert dict(report.binding_values) == {
        _CUENTAS_BASELINE_BINDING: _CUENTAS_N,
        _VALORES_BASELINE_BINDING: _VALORES_N,
        _INMUEBLES_BASELINE_BINDING: _INMUEBLES_N,
    }
    assert {item.binding_id for item in report.prefilled} == _BASELINE_BINDINGS
    assert {item.source_modelo for item in report.prefilled} == {_MODELO}
    assert {item.source_filing_year for item in report.prefilled} == {_YEAR_N}
    assert {item.source_periods for item in report.prefilled} == {("0A",)}
    assert {item.dependency_treatment for item in report.prefilled} == {"factual_evidence"}

    prior_baseline = _prior_baseline_observation_from_bindings(dict(report.binding_values))
    findings = modelo_720_redeclaration_advisory_findings(
        prior_observation=prior_baseline,
        current_observation=_year_n_plus_1_advisory_observation(),
        current_declaration_observation=_year_n_plus_1_advisory_without_cuentas(),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind is ModeloVerificationFindingKind.ADVISORY
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert finding.message_locale_key == "application.modelo.findings.foreign_asset_redeclaration"
    assert dict(finding.message_facts) == {
        "modelo_code": _MODELO,
        "filing_year": _YEAR_N_PLUS_1,
        "position_key": ForeignAssetObligationGroup.CUENTAS.value,
        "group_code": ForeignAssetObligationGroup.CUENTAS.value,
        "prior_value_eur": _CUENTAS_N,
        "current_value_eur": _CUENTAS_N1,
        "delta_value_eur": _CUENTAS_N1 - _CUENTAS_N,
        "redeclaration_increase_threshold_eur": _REDECLARATION_DELTA_EUR,
    }
    assert "rd-1065-2007:art-42-bis" in finding.legal_refs
    assert "aeat-modelo-720-procedure" in finding.source_refs


def test_previous_filing_baselines_do_not_cross_taxpayer_buckets(tmp_path: Path) -> None:
    """A factual-evidence carry resolves only from its own encrypted taxpayer bucket.

    The primary bucket holds the real 2023 Modelo 720 observation; the secondary
    bucket holds none. Both resolve the same 2024 snapshot through the production
    source-mesh adapter. This proves the factual-evidence values and their
    treatment provenance cannot leak across taxpayers while preserving the
    primary calculation input.
    """
    prior_observation = _year_n_observation_with_explicit_inmuebles_zero()
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=_YEAR_N_PLUS_1, period="0A")
    expected_bindings = {
        _CUENTAS_BASELINE_BINDING: _CUENTAS_N,
        _VALORES_BASELINE_BINDING: _VALORES_N,
        _INMUEBLES_BASELINE_BINDING: _INMUEBLES_N,
    }

    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        primary_repository = CalculationObservationRepository(objects=runtime.primary.repository)
        secondary_repository = CalculationObservationRepository(objects=runtime.secondary.repository)
        primary_repository.save(
            primary_repository.prepare_observation_envelope(
                prior_observation,
                source_kind="app_filing",
                captured_at=_CLOCK_N,
            )
        )
        primary_resolution = PreviousFilingSourceResolver(
            repository=primary_repository,
            registry_snapshot=snapshot,
        ).resolve(
            CalculationSourceContext(
                bucket_id=runtime.primary.bucket_id,
                modelo=_MODELO,
                filing_year=_YEAR_N_PLUS_1,
                period=Period.from_year_and_code(_YEAR_N_PLUS_1, "0A"),
                revision=snapshot.revision,
            )
        )
        with runtime.switch_to_secondary():
            secondary_resolution = PreviousFilingSourceResolver(
                repository=secondary_repository,
                registry_snapshot=snapshot,
            ).resolve(
                CalculationSourceContext(
                    bucket_id=runtime.secondary.bucket_id,
                    modelo=_MODELO,
                    filing_year=_YEAR_N_PLUS_1,
                    period=Period.from_year_and_code(_YEAR_N_PLUS_1, "0A"),
                    revision=snapshot.revision,
                )
            )

    assert dict(primary_resolution.binding_values) == expected_bindings
    assert primary_resolution.unresolved_binding_ids == ()
    assert {item.dependency_treatment for item in primary_resolution.provenance} == {"factual_evidence"}
    assert {item.source_ref.rsplit(":", maxsplit=1)[-1] for item in primary_resolution.provenance} == _BASELINE_BINDINGS
    assert dict(secondary_resolution.binding_values) == {}
    assert set(secondary_resolution.unresolved_binding_ids) == _BASELINE_BINDINGS
    assert secondary_resolution.provenance == ()


def test_previous_filing_baseline_does_not_invent_absent_inmuebles_zero(tmp_path: Path) -> None:
    obs_n = _year_n_observation()
    assert _INMUEBLES_VALORACION_CASILLA not in obs_n.casilla_values
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        snapshot_n1 = bundled_authority().snapshot(_MODELO, filing_year=_YEAR_N_PLUS_1, period="0A")

        with pytest.raises(RegistryValidationError, match="inmuebles\\.valoracion"):
            resolve_bindings_from_local_store(snapshot_n1, repository=repo, captured_at=_CLOCK_N_PLUS_1)


def test_redeclaration_advisory_is_silent_when_required_group_is_declared_or_delta_is_below_threshold() -> None:
    assert (
        modelo_720_redeclaration_advisory_findings(
            prior_observation=_year_n_advisory_observation(),
            current_observation=_year_n_plus_1_advisory_observation(),
            current_declaration_observation=_year_n_plus_1_advisory_observation(),
        )
        == ()
    )

    assert (
        modelo_720_redeclaration_advisory_findings(
            prior_observation=_year_n_advisory_observation(),
            current_observation=_year_n_plus_1_advisory_observation(),
            current_declaration_observation=_year_n_plus_1_advisory_without_valores(),
        )
        == ()
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
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")

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
    fidelity plus the application advisory assertions exercise the advisory layer
    this informativa can currently support without a numeric calculation engine.
    This test covers the enrollment cycle, not binding resolution: the
    `previous_filing` baseline bindings are live registry data and are exercised
    by test_previous_filing_baseline_drives_redeclaration_advisory_for_omitted_grown_cuentas
    above. What remains unwired for M720 is the advisory's INPUT, not its
    trigger. The trigger is live:
    :func:`~application.calculations.modelo_720_redeclaration_advisory_findings`
    is reached on the verification path through the application-layer gate,
    which resolves the law-determined revision and folds the evidence,
    prior-baseline and declaration observations before calling it.

    What does not arrive is the evidence. The single production calculate
    entry point takes an input bundle carrying no observation field of any
    kind, so the foreign-asset resolver always runs with an empty collection,
    the revision's row bindings carry no asset rows, and the gate returns at
    its own `if not evidence.observations` guard. That boundary is
    deliberate rather than missing: the campaign that enrolled the resolver
    recorded that it did not approve a durable foreign-asset observation
    store, and the explicit observations parameter is the injection point
    left for one.

    So a reader arriving here should look at the supply, not the wiring. The
    wiring question is settled and re-deriving it has already cost this
    codebase one wrong finding reported upward.
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
