"""E2E data-fidelity: Modelo 349 year-over-year intracomunitario cadence continuity.

Modelo 349 (Declaración recapitulativa de operaciones intracomunitarias —
Orden HAC/174/2020) is a periodic recapitulative statement for intra-EU B2B
operations: suppliers of goods or services to IVA-registered counterparties
in other EU member states declare each counterparty's NIF, country code,
operation code, and base imponible (Orden EHA/769/2010 art. 1, Orden
HAC/174/2020 art. 1, Ley 58/2003 art. 93). The period can be monthly
(``"01"``–``"12"``) or quarterly (``"1T"``–``"4T"``); this test uses the
annual 4T period.

The casilla schema (``2020-y-siguientes`` revision) includes:
- ``decl.numero-operadores`` — total number of intracomunitario operators
- ``decl.importe-operaciones`` — total importe of intracomunitario operations
- ``decl.numero-rectificaciones`` — number of operators with rectifications
- ``decl.importe-rectificaciones`` — importe of rectifications
- ``op.codigo-pais`` — EU country code of the counterparty
- ``op.nif-comunitario`` — IVA NIF of the EU counterparty
- ``op.clave-operacion`` — operation code (E=entregas, S=servicios,
  A=adquisiciones, etc.)
- ``op.base-imponible`` — base imponible / importe of the intracomunitario
  operation

There is no calculation engine and no cross-year binding resolver. The
cross-year invariant is data-fidelity and cadence continuity: a 4T filing
for ejercicio N survives the encrypted-SQL roundtrip with all per-operator
fields intact, and ejercicio N+1 is independently retrievable with distinct
values that do not bleed.

Both years are recorded through the :class:`EnrollmentRecorder` via
``record_context_year`` and cross-checked against the authorization manifest.

Legal grounding: Orden EHA/769/2010 art. 1 (form mandate); Orden HAC/174/2020
art. 1 (2020 revision, new period thresholds); Ley 58/2003 art. 93 (registro
de operadores intracomunitarios).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation

from ....core import CasillaId, validated_casilla_id
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository
from ._observation_lookup_support import find_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "349"
_YEAR_N = 2024
_YEAR_N_PLUS_1 = 2025
_PERIOD = "4T"
_CONTEXT_LABEL = "349-intracomunitario-recapitulativo-cadence-year-over-year"
_CLOCK_N = datetime(2025, 1, 27, 10, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_1 = datetime(2026, 1, 27, 10, 0, 0, tzinfo=UTC)


_DECL_NUMERO_OPERADORES_CASILLA: CasillaId = validated_casilla_id("decl.numero-operadores")
_DECL_IMPORTE_OPERACIONES_CASILLA: CasillaId = validated_casilla_id("decl.importe-operaciones")
_DECL_NUMERO_RECTIFICACIONES_CASILLA: CasillaId = validated_casilla_id("decl.numero-rectificaciones")
_DECL_IMPORTE_RECTIFICACIONES_CASILLA: CasillaId = validated_casilla_id("decl.importe-rectificaciones")
_OP_CODIGO_PAIS_CASILLA: CasillaId = validated_casilla_id("op.codigo-pais")
_OP_NIF_COMUNITARIO_CASILLA: CasillaId = validated_casilla_id("op.nif-comunitario")
_OP_CLAVE_OPERACION_CASILLA: CasillaId = validated_casilla_id("op.clave-operacion")
_OP_BASE_IMPONIBLE_CASILLA: CasillaId = validated_casilla_id("op.base-imponible")


def _year_n_observation() -> RegistryModeloObservation:
    """Year-N 349 4T: one intracomunitario supplier to a German counterparty.

    All per-operator fields are non-default and distinct from year-N+1 so
    cross-year field-bleeding surfaces as strict inequality. The counterparty
    NIF is the identity anchor that must survive the roundtrip unchanged.
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period=_PERIOD,
        casilla_values={
            _DECL_NUMERO_OPERADORES_CASILLA: Decimal("1"),
            _DECL_IMPORTE_OPERACIONES_CASILLA: Decimal("85000.00"),
            _DECL_NUMERO_RECTIFICACIONES_CASILLA: Decimal("0"),
            _DECL_IMPORTE_RECTIFICACIONES_CASILLA: Decimal("0"),
            _OP_CODIGO_PAIS_CASILLA: Decimal("276"),  # DE
            _OP_NIF_COMUNITARIO_CASILLA: Decimal("123456789"),
            _OP_CLAVE_OPERACION_CASILLA: Decimal("1"),  # E=entregas
            _OP_BASE_IMPONIBLE_CASILLA: Decimal("85000.00"),
        },
    )


def _year_n_plus_1_observation() -> RegistryModeloObservation:
    """Year-N+1 349 4T: same counterparty NIF but distinct base-imponible.

    The recurring counterparty (same NIF) appears with a larger base in year
    N+1. The base-imponible difference surfaces any cross-year value-bleeding
    as strict inequality.
    """
    return registry_grounded_modelo_observation(
        modelo=_MODELO,
        filing_year=_YEAR_N_PLUS_1,
        period=_PERIOD,
        casilla_values={
            _DECL_NUMERO_OPERADORES_CASILLA: Decimal("1"),
            _DECL_IMPORTE_OPERACIONES_CASILLA: Decimal("112000.00"),
            _DECL_NUMERO_RECTIFICACIONES_CASILLA: Decimal("0"),
            _DECL_IMPORTE_RECTIFICACIONES_CASILLA: Decimal("0"),
            _OP_CODIGO_PAIS_CASILLA: Decimal("276"),  # DE
            _OP_NIF_COMUNITARIO_CASILLA: Decimal("123456789"),
            _OP_CLAVE_OPERACION_CASILLA: Decimal("1"),
            _OP_BASE_IMPONIBLE_CASILLA: Decimal("112000.00"),
        },
    )


def test_year_n_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N 349 casilla values survive the encrypted-SQL roundtrip unchanged."""
    obs_n = _year_n_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period=_PERIOD)
        assert loaded is not None
        assert loaded.observation == obs_n
        assert loaded.source_kind == "app_filing"
        assert loaded.captured_at == _CLOCK_N


def test_year_n_plus_1_observation_persists_and_reloads_strictly(tmp_path: Path) -> None:
    """Year-N+1 349 casilla values survive the roundtrip with a larger base-imponible."""
    obs_n1 = _year_n_plus_1_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period=_PERIOD)
        assert loaded is not None
        assert loaded.observation == obs_n1
        assert loaded.captured_at == _CLOCK_N_PLUS_1


def test_both_observations_are_independently_retrievable_no_bleed(tmp_path: Path) -> None:
    """Both ejercicios are independently addressable; base-imponible does not bleed."""
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period=_PERIOD)
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period=_PERIOD)

        assert loaded_n is not None and loaded_n1 is not None
        assert loaded_n.observation == obs_n
        assert loaded_n1.observation == obs_n1

        base_n = loaded_n.observation.casilla_values[_OP_BASE_IMPONIBLE_CASILLA]
        base_n1 = loaded_n1.observation.casilla_values[_OP_BASE_IMPONIBLE_CASILLA]
        assert base_n == Decimal("85000.00")
        assert base_n1 == Decimal("112000.00")
        assert base_n != base_n1, "op.base-imponible bled between year-N and year-N+1"

        # NIF identity continuity: the same counterparty appears in both years
        nif_n = loaded_n.observation.casilla_values[_OP_NIF_COMUNITARIO_CASILLA]
        nif_n1 = loaded_n1.observation.casilla_values[_OP_NIF_COMUNITARIO_CASILLA]
        assert nif_n == nif_n1 == Decimal("123456789"), "counterparty NIF must be identical in both years"

        assert loaded_n.captured_at != loaded_n1.captured_at


def test_anti_tautology_proof_missing_casilla_surfaces_as_inequality(tmp_path: Path) -> None:
    """Anti-tautology: a missing casilla in the reloaded observation is detectable."""
    obs_n = _year_n_observation()
    obs_n_missing = RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period=_PERIOD,
        observations=tuple(o for o in obs_n.observations if o.casilla_id != _OP_BASE_IMPONIBLE_CASILLA),
    )
    assert obs_n != obs_n_missing

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded = find_observation(repo, _MODELO, filing_year=_YEAR_N, period=_PERIOD)
        assert loaded is not None
        assert loaded.observation != obs_n_missing
        assert loaded.observation == obs_n


def test_modelo_349_intracomunitario_fidelity_enrolls_two_renta_years(tmp_path: Path) -> None:
    """EnrollmentRecorder proves both exercises and matches the authorization manifest.

    Drives the real CalculationObservationRepository for both intracomunitario
    ejercicios (real encrypted-SQLite, no mocks), records each via
    record_context_year, and calls assert_enrollment_matches_manifest. Manifest
    must declare renta_years = [2024, 2025] in the same commit.
    """
    obs_n = _year_n_observation()
    obs_n1 = _year_n_plus_1_observation()

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(repo.prepare_observation_envelope(obs_n, source_kind="app_filing", captured_at=_CLOCK_N))
        loaded_n = find_observation(repo, _MODELO, filing_year=_YEAR_N, period=_PERIOD)
        assert loaded_n is not None and loaded_n.observation == obs_n
        _count_n = sum(1 for _p in repo.iter_modelo(_MODELO) if _p.observation.filing_year == _YEAR_N)

        repo.save(repo.prepare_observation_envelope(obs_n1, source_kind="app_filing", captured_at=_CLOCK_N_PLUS_1))
        loaded_n1 = find_observation(repo, _MODELO, filing_year=_YEAR_N_PLUS_1, period=_PERIOD)
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
