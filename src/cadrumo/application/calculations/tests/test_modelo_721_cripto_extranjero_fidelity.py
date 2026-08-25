"""E2E data-fidelity: Modelo 721 monedas virtuales en el extranjero across 2 annual cycles.

Modelo 721 (Declaración informativa sobre monedas virtuales situadas en el
extranjero — Orden HFP/886/2023, BOE-A-2023-17429) is a pure-informativa
annual declaration grounded in DA-18 letra d of Ley 58/2003 LGT (as
introduced by DA-10 of Ley 11/2021) and developed by RD 1065/2007 art.
42-quater (introduced by RD 249/2023).

The obligation applies to residents who hold virtual currencies abroad through
a THIRD-PARTY custodian (foreign exchange, custodial-wallet provider) whose
aggregate 31-December value exceeds €50,000 (art. 42-quater threshold,
mirroring the €50,000 initial threshold of the 720/arts.42-bis/ter/54-bis
structure). First ejercicio is 2023 (filed January–March 2024).

The multi-year contract: the same crypto position declared in ejercicio N is
used as the prior-year baseline in ejercicio N+1. If the 31-December aggregate
grew > €20,000 over the last-declared baseline (the re-declaration increment
threshold per art. 42-quater), a new declaration is required in N+1 even if
the filer would otherwise be below threshold. This mirrors the M720 A3
re-declaration trigger for bienes y derechos.

This module covers the data-fidelity and advisory-trigger layer:

- Year N (2023): custodian Coinbase (US) holding BTC at €60,000 and ETH at
  €55,000 at 31 December 2023. Both exceed the €50,000 initial threshold.
- Year N+1 (2024): same custodian/tokens, BTC grown to €87,000 (+€27,000 >
  €20,000 delta → re-declaration required), ETH at €63,000 (+€8,000 ≤ €20,000).
- Observations persist via the real CalculationObservationRepository and reload
  with strict pydantic equality. Token identity (custodio + moneda.clave-token)
  survives the roundtrip unchanged — the cross-year baseline resolver's anchor.
- The advisory helper fires when the grown BTC custodian+token pair is absent
  from the current declaration, and stays silent when the required token is
  present or the delta stays below the €20,000 re-declaration threshold.
- Anti-tautology: omitting the saldo-31-diciembre casilla produces strict
  inequality, proving the roundtrip assertions are not vacuously true.

Evidence class: THRESHOLD_CONTINUITY. The two-year per-custodian/per-token
roundtrip together with valuation isolation, identity continuity, and the
advisory trigger constitute the current real ≥2-renta threshold-continuity
contract.

Legal grounding: DA-18 letra d Ley 58/2003 LGT (obligation); Ley 11/2021
DA-10 (enabling statute); RD 1065/2007 art. 42-quater (reglamentary development,
€50,000 initial threshold, €20,000 re-declaration delta); Orden HFP/886/2023
arts. 1-3 (form approval, filing period January–March following ejercicio).

See Also:
    :mod:`~application.calculations._foreign_asset_redeclaration`
        Shared M720/M721 re-declaration advisory implementation exercised here.
    :func:`~application.calculations._foreign_asset_redeclaration.modelo_721_redeclaration_advisory_findings`
        Modelo 721 advisory entry point pinned by the grown/omitted BTC case.
    :class:`~application.calculations._observations_repository.CalculationObservationRepository`
        Real repository used for the two-year observation roundtrip.
    :class:`~domain.calculations.registry.RegistryModeloObservation`
        Registry-grounded modelo observation envelope persisted by the test.
    :class:`~domain.calculations.registry.CasillaObservation`
        Typed casilla row carrying legal and source provenance.
    :mod:`~application.calculations.tests.test_modelo_720_prior_year_baseline_fidelity`
        Modelo 720 threshold-continuity sibling over foreign asset classes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import (
    CasillaId,
    ForeignAssetObligationGroup,
    RegistryAuthorityGrade,
    validated_casilla_id,
)
from cadrumo.domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....domain.modelos import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ....tests.registry_observations import registry_grounded_observation_rows
from ....tests.secure_sql import isolated_runtime_profile
from ..._foreign_asset_thresholds import foreign_asset_declaration_thresholds
from .._foreign_asset_redeclaration import modelo_721_redeclaration_advisory_findings
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository
from ._multi_year_roundtrip_support import assert_two_ejercicio_round_trip
from ._observation_lookup_support import find_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "721"

#: Two distinct renta ejercicios the fidelity test spans.
#: First ejercicio for M721 is 2023; enrollment uses 2023/2024.
_YEAR_N = 2023
_YEAR_N_PLUS_1 = 2024

#: Context label for the EnrollmentRecorder (non-calculation / threshold-continuity mode).
_CONTEXT_LABEL = "721-monedas-virtuales-extranjero-prior-year-baseline-two-annual-cycles"

#: Initial declaration threshold per RD 1065/2007 art. 42-quater (same structure
#: as 720: €50,000 aggregate value at 31 December through a third-party custodian).
_MONEDAS_VIRTUALES_THRESHOLD = foreign_asset_declaration_thresholds(
    modelo=_MODELO,
    filing_year=_YEAR_N_PLUS_1,
)[ForeignAssetObligationGroup.MONEDAS_VIRTUALES]
_INITIAL_THRESHOLD_EUR = _MONEDAS_VIRTUALES_THRESHOLD.initial_declaration_floor_eur

#: Re-declaration increment threshold per art. 42-quater: if 31-December aggregate
#: grew > €20,000 over the last-declared baseline, a new declaration is required.
_REDECLARATION_DELTA_EUR = _MONEDAS_VIRTUALES_THRESHOLD.redeclaration_increase_delta_eur

# Year-N (2023) valuations at 31 December 2023 (both above €50k initial threshold).
_BTC_N = Decimal("60000.00")  # BTC via Coinbase, above €50k threshold
_ETH_N = Decimal("55000.00")  # ETH via Coinbase, above €50k threshold

# Year-N+1 (2024) valuations at 31 December 2024.
# BTC: +€27,000 (> €20k delta → re-declaration required per art. 42-quater)
# ETH: +€8,000 (≤ €20k delta → not required)
_BTC_N1 = Decimal("87000.00")
_ETH_N1 = Decimal("63000.00")

#: Custodian identity anchor: Coinbase (US-based custodian).
#: Must survive the roundtrip unchanged — identity-continuity contract.
#: Encoded as Decimal for CasillaObservation (text-content stored as numeric).
_CUSTODIO_NOMBRE = Decimal("1")  # proxy for "Coinbase Inc" — numeric sentinel
_CUSTODIO_PAIS = Decimal("840")  # US ISO 3166-1 numeric country code

# Clock timestamps (M721 filing window: 1 January – 31 March following ejercicio).
_CLOCK_N = datetime(2024, 2, 15, 10, 0, 0, tzinfo=UTC)  # filed for ejercicio 2023
_CLOCK_N_PLUS_1 = datetime(2025, 2, 15, 10, 0, 0, tzinfo=UTC)  # filed for ejercicio 2024


_EJERCICIO_CASILLA: CasillaId = validated_casilla_id("ejercicio")
_TIPO_DECLARACION_CASILLA: CasillaId = validated_casilla_id("tipo-declaracion")
_CUSTODIO_NOMBRE_CASILLA: CasillaId = validated_casilla_id("custodio.nombre-razon-social")
_CUSTODIO_CODIGO_PAIS_CASILLA: CasillaId = validated_casilla_id("custodio.codigo-pais")
_MONEDA_CLAVE_TOKEN_CASILLA: CasillaId = validated_casilla_id("moneda.clave-token")
_MONEDA_SALDO_CASILLA: CasillaId = validated_casilla_id("moneda.saldo-31-diciembre")
_SALDO_31_DICIEMBRE_CASILLAS: tuple[CasillaId, ...] = (_MONEDA_SALDO_CASILLA,)
_M721_SOURCE_REFS = ("aeat-modelo-721-procedure",)
_M721_LEGAL_REFS = _MONEDAS_VIRTUALES_THRESHOLD.legal_refs


def _values_for(observation: RegistryModeloObservation, casilla_id: CasillaId) -> tuple[Decimal, ...]:
    values: list[Decimal] = []
    for item in observation.observations:
        if item.casilla_id != casilla_id:
            continue
        assert isinstance(item.value, Decimal), f"casilla {casilla_id!r} must carry a numeric observation"
        values.append(item.value)
    return tuple(values)


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
                legal_refs=_M721_LEGAL_REFS,
                source_refs=_M721_SOURCE_REFS,
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
            (_CUSTODIO_NOMBRE_CASILLA, _CUSTODIO_NOMBRE),
            (_CUSTODIO_CODIGO_PAIS_CASILLA, _CUSTODIO_PAIS),
            (_MONEDA_CLAVE_TOKEN_CASILLA, Decimal("1")),
            (_MONEDA_SALDO_CASILLA, _BTC_N),
            (_MONEDA_CLAVE_TOKEN_CASILLA, Decimal("2")),
            (_MONEDA_SALDO_CASILLA, _ETH_N),
        ),
    )


def _year_n_plus_1_advisory_observation() -> RegistryModeloObservation:
    return _advisory_observation(
        filing_year=_YEAR_N_PLUS_1,
        casilla_values=(
            (_EJERCICIO_CASILLA, Decimal(str(_YEAR_N_PLUS_1))),
            (_TIPO_DECLARACION_CASILLA, Decimal("1")),
            (_CUSTODIO_NOMBRE_CASILLA, _CUSTODIO_NOMBRE),
            (_CUSTODIO_CODIGO_PAIS_CASILLA, _CUSTODIO_PAIS),
            (_MONEDA_CLAVE_TOKEN_CASILLA, Decimal("1")),
            (_MONEDA_SALDO_CASILLA, _BTC_N1),
            (_MONEDA_CLAVE_TOKEN_CASILLA, Decimal("2")),
            (_MONEDA_SALDO_CASILLA, _ETH_N1),
        ),
    )


def _year_n_plus_1_advisory_without_btc() -> RegistryModeloObservation:
    return _advisory_observation(
        filing_year=_YEAR_N_PLUS_1,
        casilla_values=(
            (_EJERCICIO_CASILLA, Decimal(str(_YEAR_N_PLUS_1))),
            (_TIPO_DECLARACION_CASILLA, Decimal("1")),
            (_CUSTODIO_NOMBRE_CASILLA, _CUSTODIO_NOMBRE),
            (_CUSTODIO_CODIGO_PAIS_CASILLA, _CUSTODIO_PAIS),
            (_MONEDA_CLAVE_TOKEN_CASILLA, Decimal("2")),
            (_MONEDA_SALDO_CASILLA, _ETH_N1),
        ),
    )


def _year_n_plus_1_advisory_without_eth() -> RegistryModeloObservation:
    return _advisory_observation(
        filing_year=_YEAR_N_PLUS_1,
        casilla_values=(
            (_EJERCICIO_CASILLA, Decimal(str(_YEAR_N_PLUS_1))),
            (_TIPO_DECLARACION_CASILLA, Decimal("1")),
            (_CUSTODIO_NOMBRE_CASILLA, _CUSTODIO_NOMBRE),
            (_CUSTODIO_CODIGO_PAIS_CASILLA, _CUSTODIO_PAIS),
            (_MONEDA_CLAVE_TOKEN_CASILLA, Decimal("1")),
            (_MONEDA_SALDO_CASILLA, _BTC_N1),
        ),
    )


def _year_n_observation() -> RegistryModeloObservation:
    """Build the year-N (2023) M721 observation: BTC €60k + ETH €55k at 31 Dec.

    Per-token rows reuse the canonical registry row casillas; the ordered
    observation tuple preserves row multiplicity that ``casilla_values`` cannot
    represent. Both valuations exceed the €50,000 initial threshold per art.
    42-quater / RD 1065/2007. All values are non-default so a save-drops-field
    regression surfaces as strict inequality on reload.
    """
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        observations=registry_grounded_observation_rows(
            modelo=_MODELO,
            # APPLICABILITY grade. Modelo 721 declares tax_domain and
            # calculation_class "informative" and ships no export or
            # formulas family: it reports holdings abroad and computes no
            # liability, so the FILING default asks for capability the
            # modelo neither has nor claims.
            grade=RegistryAuthorityGrade.APPLICABILITY,
            filing_year=_YEAR_N,
            period="0A",
            casilla_values=(
                # Declarante header casillas (completeness-manifest anchors)
                (_EJERCICIO_CASILLA, Decimal(str(_YEAR_N))),
                (_TIPO_DECLARACION_CASILLA, Decimal("1")),
                # Custodian identity (shared across both token rows)
                (_CUSTODIO_NOMBRE_CASILLA, _CUSTODIO_NOMBRE),
                (_CUSTODIO_CODIGO_PAIS_CASILLA, _CUSTODIO_PAIS),
                # BTC row — token identity + 31-December valuation
                (_MONEDA_CLAVE_TOKEN_CASILLA, Decimal("1")),  # BTC=1
                (_MONEDA_SALDO_CASILLA, _BTC_N),
                # ETH row — token identity + 31-December valuation
                (_MONEDA_CLAVE_TOKEN_CASILLA, Decimal("2")),  # ETH=2
                (_MONEDA_SALDO_CASILLA, _ETH_N),
            ),
        ),
    )


def _year_n_plus_1_observation() -> RegistryModeloObservation:
    """Build the year-N+1 (2024) M721 observation: BTC €87k + ETH €63k at 31 Dec.

    Same custodian and token identifiers as year N (identity continuity). Distinct
    valuations so field-bleeding between years surfaces as strict inequality. BTC
    delta (+€27k > €20k) exceeds the re-declaration threshold; ETH delta (+€8k)
    does not.
    """
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_1,
        period="0A",
        observations=registry_grounded_observation_rows(
            modelo=_MODELO,
            grade=RegistryAuthorityGrade.APPLICABILITY,
            filing_year=_YEAR_N_PLUS_1,
            period="0A",
            casilla_values=(
                (_EJERCICIO_CASILLA, Decimal(str(_YEAR_N_PLUS_1))),
                (_TIPO_DECLARACION_CASILLA, Decimal("1")),
                (_CUSTODIO_NOMBRE_CASILLA, _CUSTODIO_NOMBRE),
                (_CUSTODIO_CODIGO_PAIS_CASILLA, _CUSTODIO_PAIS),
                # BTC row — same token identity, grown valuation (+€27k)
                (_MONEDA_CLAVE_TOKEN_CASILLA, Decimal("1")),
                (_MONEDA_SALDO_CASILLA, _BTC_N1),
                # ETH row — same token identity, grown valuation (+€8k)
                (_MONEDA_CLAVE_TOKEN_CASILLA, Decimal("2")),
                (_MONEDA_SALDO_CASILLA, _ETH_N1),
            ),
        ),
    )


def _year_n_plus_1_observation_without_btc() -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_1,
        period="0A",
        observations=registry_grounded_observation_rows(
            modelo=_MODELO,
            grade=RegistryAuthorityGrade.APPLICABILITY,
            filing_year=_YEAR_N_PLUS_1,
            period="0A",
            casilla_values=(
                (_EJERCICIO_CASILLA, Decimal(str(_YEAR_N_PLUS_1))),
                (_TIPO_DECLARACION_CASILLA, Decimal("1")),
                (_CUSTODIO_NOMBRE_CASILLA, _CUSTODIO_NOMBRE),
                (_CUSTODIO_CODIGO_PAIS_CASILLA, _CUSTODIO_PAIS),
                (_MONEDA_CLAVE_TOKEN_CASILLA, Decimal("2")),
                (_MONEDA_SALDO_CASILLA, _ETH_N1),
            ),
        ),
    )


def _year_n_plus_1_observation_without_eth() -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_1,
        period="0A",
        observations=registry_grounded_observation_rows(
            modelo=_MODELO,
            grade=RegistryAuthorityGrade.APPLICABILITY,
            filing_year=_YEAR_N_PLUS_1,
            period="0A",
            casilla_values=(
                (_EJERCICIO_CASILLA, Decimal(str(_YEAR_N_PLUS_1))),
                (_TIPO_DECLARACION_CASILLA, Decimal("1")),
                (_CUSTODIO_NOMBRE_CASILLA, _CUSTODIO_NOMBRE),
                (_CUSTODIO_CODIGO_PAIS_CASILLA, _CUSTODIO_PAIS),
                (_MONEDA_CLAVE_TOKEN_CASILLA, Decimal("1")),
                (_MONEDA_SALDO_CASILLA, _BTC_N1),
            ),
        ),
    )


def test_row_set_multiplicity_is_preserved_only_in_ordered_observations() -> None:
    """Repeated M721 row casillas cannot be represented by the scalar casilla_values view."""
    observation = _year_n_observation()

    assert _values_for(observation, _MONEDA_CLAVE_TOKEN_CASILLA) == (Decimal("1"), Decimal("2"))
    assert _values_for(observation, _MONEDA_SALDO_CASILLA) == (_BTC_N, _ETH_N)
    assert observation.casilla_values[_MONEDA_CLAVE_TOKEN_CASILLA] == Decimal("2")
    assert observation.casilla_values[_MONEDA_SALDO_CASILLA] == _ETH_N


def test_year_n_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N (2023) M721 casilla values survive the encrypted-SQL roundtrip unchanged.

    Both BTC and ETH 31-December valuations are above the €50,000 initial threshold.
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
    """Year-N+1 (2024) M721 casilla values survive the roundtrip with non-year-N valuations."""
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
    - Year-N BTC valuation (60,000) must not appear in year-N+1 (87,000).
    - ejercicio casilla correctly encodes the filing year for each cycle.
    - Provenance timestamps are distinct.

    This asserts the (modelo, filing_year, period) keying enforces strict per-cycle
    isolation — a critical invariant for the prior-year baseline resolver to read
    the correct year's figures.
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

    assert n_vals[_EJERCICIO_CASILLA] == Decimal(str(_YEAR_N))
    assert n1_vals[_EJERCICIO_CASILLA] == Decimal(str(_YEAR_N_PLUS_1))

    # BTC saldo does not bleed between cycles.
    btc_n = _values_for(loaded_n.observation, _MONEDA_SALDO_CASILLA)[0]
    btc_n1 = _values_for(loaded_n1.observation, _MONEDA_SALDO_CASILLA)[0]
    assert btc_n == _BTC_N, f"year-N BTC saldo should be {_BTC_N}; got {btc_n}"
    assert btc_n1 == _BTC_N1, f"year-N+1 BTC saldo should be {_BTC_N1}; got {btc_n1}"
    assert btc_n != btc_n1, "BTC saldo bled between year-N and year-N+1"


def test_token_identity_persists_across_both_annual_cycles(tmp_path: Path) -> None:
    """Token and custodian identifiers survive the roundtrip unchanged across both cycles.

    Orden HFP/886/2023 art. 2 requires per-custodian/per-token identification.
    The clave-token is the anchor for the prior-year baseline resolver to match
    year-N+1 rows against year-N baseline. A serialiser that truncates or coerces
    the identifier would break the cross-year match and disable the re-declaration
    trigger detection.
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

        # BTC token identity: clave-token=1 must survive unchanged in both cycles.
        token_ids_n = _values_for(loaded_n.observation, _MONEDA_CLAVE_TOKEN_CASILLA)
        token_ids_n1 = _values_for(loaded_n1.observation, _MONEDA_CLAVE_TOKEN_CASILLA)
        assert token_ids_n == (Decimal("1"), Decimal("2")), f"token round-trip failed in year N: {token_ids_n}"
        assert token_ids_n1 == (Decimal("1"), Decimal("2")), f"token round-trip failed in year N+1: {token_ids_n1}"
        assert token_ids_n == token_ids_n1, "moneda.clave-token ordering drifted between year N and year N+1"

        # Custodian country identity: codigo-pais=840 (US) must survive unchanged.
        pais_n = loaded_n.observation.casilla_values.get(_CUSTODIO_CODIGO_PAIS_CASILLA)
        pais_n1 = loaded_n1.observation.casilla_values.get(_CUSTODIO_CODIGO_PAIS_CASILLA)
        assert pais_n == _CUSTODIO_PAIS, f"custodio.codigo-pais round-trip failed year N: got {pais_n}"
        assert pais_n1 == _CUSTODIO_PAIS, f"custodio.codigo-pais round-trip failed year N+1: got {pais_n1}"
        assert pais_n == pais_n1, "custodio.codigo-pais drifted between year N and year N+1"


def test_both_year_n_valuations_exceed_initial_threshold(tmp_path: Path) -> None:
    """Year-N BTC (€60k) and ETH (€55k) both exceed the €50k initial declaration threshold.

    RD 1065/2007 art. 42-quater requires declaration when the 31-December aggregate
    through a third-party custodian exceeds €50,000. A roundtrip that silently zeros
    a valuation would produce a sub-threshold (non-declarable) observation.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(_year_n_observation(), source_kind="app_filing", captured_at=_CLOCK_N)
        )
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")

        assert loaded is not None
        val_btc, val_eth = _values_for(loaded.observation, _MONEDA_SALDO_CASILLA)
        assert val_btc >= _INITIAL_THRESHOLD_EUR, (
            f"year-N BTC saldo {val_btc} must be >= {_INITIAL_THRESHOLD_EUR} initial threshold"
        )
        assert val_eth >= _INITIAL_THRESHOLD_EUR, (
            f"year-N ETH saldo {val_eth} must be >= {_INITIAL_THRESHOLD_EUR} initial threshold"
        )


def test_year_n_plus_1_btc_delta_exceeds_redeclaration_threshold(tmp_path: Path) -> None:
    """Year-N+1 BTC growth (+€27k) exceeds the €20k re-declaration increment threshold.

    Scenario: year-N BTC = €60,000; year-N+1 BTC = €87,000; delta = +€27,000.
    This exceeds the €20,000 increment threshold per art. 42-quater, so the
    filer must re-declare the BTC position in 2024 even if they would otherwise
    not be obliged. The test asserts both stored values are correct and the
    re-declaration trigger condition is satisfied in the stored data.

    The application advisory helper is tested separately below because it also needs
    the current declaration row set to prove the grown token is absent.
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

        val_n = _values_for(loaded_n.observation, _MONEDA_SALDO_CASILLA)[0]
        val_n1 = _values_for(loaded_n1.observation, _MONEDA_SALDO_CASILLA)[0]

        delta = val_n1 - val_n
        assert delta > _REDECLARATION_DELTA_EUR, (
            f"year-N+1 minus year-N BTC delta ({delta}) must exceed €{_REDECLARATION_DELTA_EUR} "
            f"to satisfy art. 42-quater re-declaration trigger condition"
        )


def test_redeclaration_advisory_fires_when_grown_btc_token_is_absent_from_current_declaration() -> None:
    findings = modelo_721_redeclaration_advisory_findings(
        prior_observation=_year_n_advisory_observation(),
        current_observation=_year_n_plus_1_advisory_observation(),
        current_declaration_observation=_year_n_plus_1_advisory_without_btc(),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind is ModeloVerificationFindingKind.ADVISORY
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert finding.message_locale_key == "application.modelo.findings.foreign_asset_redeclaration"
    assert dict(finding.message_facts) == {
        "modelo_code": _MODELO,
        "filing_year": _YEAR_N_PLUS_1,
        "position_key": "monedas_virtuales|1|840|1",
        "group_code": ForeignAssetObligationGroup.MONEDAS_VIRTUALES.value,
        "prior_value_eur": _BTC_N,
        "current_value_eur": _BTC_N1,
        "delta_value_eur": _BTC_N1 - _BTC_N,
        "redeclaration_increase_threshold_eur": _REDECLARATION_DELTA_EUR,
    }
    assert "rd-1065-2007:art-42-quater" in finding.legal_refs
    assert "aeat-modelo-721-procedure" in finding.source_refs


def test_redeclaration_advisory_is_silent_when_required_token_is_declared_or_delta_is_below_threshold() -> None:
    assert (
        modelo_721_redeclaration_advisory_findings(
            prior_observation=_year_n_advisory_observation(),
            current_observation=_year_n_plus_1_advisory_observation(),
            current_declaration_observation=_year_n_plus_1_advisory_observation(),
        )
        == ()
    )

    assert (
        modelo_721_redeclaration_advisory_findings(
            prior_observation=_year_n_advisory_observation(),
            current_observation=_year_n_plus_1_advisory_observation(),
            current_declaration_observation=_year_n_plus_1_advisory_without_eth(),
        )
        == ()
    )


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: omitting the saldo-31-diciembre casilla produces strict inequality."""
    obs_n = _year_n_observation()
    obs_n_no_saldo = RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period="0A",
        observations=tuple(o for o in obs_n.observations if o.casilla_id not in _SALDO_31_DICIEMBRE_CASILLAS),
    )

    assert obs_n != obs_n_no_saldo, "the full observation and the saldo-omitted observation must be strictly unequal"

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")

        assert loaded is not None
        assert loaded.observation != obs_n_no_saldo, (
            "loaded observation equals the saldo-omitted stub — "
            "the roundtrip silently dropped btc/eth saldo-31-diciembre casillas"
        )
        assert loaded.observation == obs_n


def test_enrollment_recorder_evidences_two_distinct_annual_cycles_and_matches_manifest(
    tmp_path: Path,
) -> None:
    """EnrollmentRecorder proves both annual cycles and matches the authorization manifest.

    Drives the real CalculationObservationRepository for both ejercicios (2023, 2024),
    records each through record_context_year (non-calculation / threshold-continuity mode),
    and calls assert_enrollment_matches_manifest. The manifest entry
    (authorization.d/721.toml) must declare renta_years = [2023, 2024] in the same
    commit as this test.

    Evidence class: THRESHOLD_CONTINUITY. The two-year per-custodian/per-token
    roundtrip plus advisory-trigger assertions constitute the current
    threshold-continuity contract for M721.
    """
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()

        # --- Year N (2023) ---------------------------------------------------
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period="0A")
        assert loaded_n is not None
        assert loaded_n.observation == obs_n
        _count_n = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N)

        # --- Year N+1 (2024) -------------------------------------------------
        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period="0A")
        assert loaded_n1 is not None
        assert loaded_n1.observation == obs_n1
        _count_n1 = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N_PLUS_1)

    # --- Enrollment recording (outside the profile context) ------------------
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
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1), (
        f"expected distinct renta years {(_YEAR_N, _YEAR_N_PLUS_1)!r}; got {evidence.distinct_renta_years!r}"
    )

    assert_enrollment_matches_manifest(evidence)
