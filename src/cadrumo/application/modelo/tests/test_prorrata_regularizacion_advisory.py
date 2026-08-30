"""Calculate-path advisory wiring for the annual prorrata-general regularización.

Exercises :func:`~application.modelo._prorrata_regularizacion_advisory.collect_prorrata_regularizacion_diagnostics`
against a REAL registry-loaded Modelo 303 revision and a REAL encrypted
:class:`~application.calculations.CalculationObservationRepository` inside
a genuine bucket runtime (``isolated_runtime_profile``) — no mocks, no stubs.
The pure LIVA arts. 104-105 math itself is proven in
``domain/iva/tests/test_prorrata_regularizacion.py`` and the pure advisory
projection in ``application/calculations/tests/test_prorrata_regularizacion.py``;
this module proves the projection is actually WIRED into the calculate-path
advisory fan-out, which was the gap the review found (the builder shipped with
zero production callers).

See Also:
    :mod:`~application.modelo._prorrata_regularizacion_advisory`
        Collector under test for the calculate-path prorrata advisory fan-out.
    :func:`~application.calculations._prorrata_regularizacion.build_prorrata_missing_provisional_advisory`
        Pure missing-carry builder used by the mid-year unresolved-register
        regression.
    :func:`~application.calculations._prorrata_regularizacion.derive_prorrata_applicability`
        Fail-closed-to-visible projection that decides whether prorrata applies.
    :class:`~domain.prorrata_register.ProrrataRegisterEntry`
        Bucket-persisted register input for active-prorrata coverage.
    :class:`~application.calculations.CalculationObservationRepository`
        Real encrypted observation store used for prior-year definitive carry
        lookup.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Modelo, ProrrataRegisterRegime
from ....core.casilla_id import validated_casilla_id
from ....core.aggregation import BindingSourceKind
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.prorrata_register import ProrrataRegister, ProrrataRegisterEntry
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA, CalculationObservationRepository
from ...prorrata_register import ProrrataRegisterRepository
from .._prorrata_regularizacion_advisory import collect_prorrata_regularizacion_diagnostics

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "108e9631-8e8f-4a81-840f-39ba3e07a70b"  # was 'prorrata-advisory-bucket'
_YEAR = 2026
_PRIOR_YEAR = 2025

_VOLUMEN_TOTAL_ID = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_VOLUMEN_CON_DERECHO_ID = validated_casilla_id("iva.prorrata-volumen-con-derecho", surface="test casilla id")
_PORCENTAJE_ID = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")
_CUOTA_DEDUCIBLE_TOTAL_ID = validated_casilla_id("iva.cuota-deducible-total", surface="test casilla id")


def _revision(*, period: str = "4T"):
    snapshot = bundled_authority().snapshot(Modelo.M303.value, filing_year=_YEAR, period=period)
    return snapshot.revision


def _seed_prior_year_percentage(obs_repo: CalculationObservationRepository, *, percentage: Decimal) -> None:
    observation = registry_grounded_modelo_observation(
        modelo=Modelo.M303.value,
        filing_year=_PRIOR_YEAR,
        period="4T",
        casilla_values={_PORCENTAJE_ID: percentage},
    )
    obs_repo.save(obs_repo.prepare_observation_envelope(observation, source_kind="aeat_sede_justificante"))


def test_advisory_fires_when_prior_year_percentage_available_and_differs(tmp_path: Path) -> None:
    """A real prior-year percentage lets the pure builder run and surface the delta.

    Volumen total 100.000, con derecho 80.000 -> sin-derecho 20.000 (prorrata
    applies). Prior-year (2025) definitiva percentage 90%; current year (2026)
    definitiva percentage 80% -> an ``ingreso`` regularización is due on
    casilla 44.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        obs_repo = CalculationObservationRepository(objects=profile.repository)
        _seed_prior_year_percentage(obs_repo, percentage=Decimal("90"))

        casilla_values = {
            _VOLUMEN_TOTAL_ID: Decimal("100000"),
            _VOLUMEN_CON_DERECHO_ID: Decimal("80000"),
            _PORCENTAJE_ID: Decimal("80"),
            _CUOTA_DEDUCIBLE_TOTAL_ID: Decimal("20000.00"),
        }
        diagnostics = collect_prorrata_regularizacion_diagnostics(
            _revision(),
            casilla_values,
            modelo=Modelo.M303.value,
            period_token="4T",
            filing_year=_YEAR,
            observation_repository=obs_repo,
        )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.binding_source is BindingSourceKind.PRORRATA_REGULARIZACION
    assert "44" in diagnostic.message
    assert "ingreso" in diagnostic.message


def test_advisory_fires_pending_when_no_prior_year_observation_exists(tmp_path: Path) -> None:
    """No-silent-under-declaration: prorrata applies but the prior-year carry is absent.

    The operator has no stored 2025 M303 observation on this machine, so the
    provisional percentage cannot be sourced honestly; the collector alerts
    that casilla 44 must be checked manually rather than fabricating a figure
    or staying silent.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        obs_repo = CalculationObservationRepository(objects=profile.repository)

        casilla_values = {
            _VOLUMEN_TOTAL_ID: Decimal("100000"),
            _VOLUMEN_CON_DERECHO_ID: Decimal("80000"),
            _PORCENTAJE_ID: Decimal("80"),
            _CUOTA_DEDUCIBLE_TOTAL_ID: Decimal("20000.00"),
        }
        diagnostics = collect_prorrata_regularizacion_diagnostics(
            _revision(),
            casilla_values,
            modelo=Modelo.M303.value,
            period_token="4T",
            filing_year=_YEAR,
            observation_repository=obs_repo,
        )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.casilla_id == _PORCENTAJE_ID
    assert "44" in diagnostic.message
    assert str(_PRIOR_YEAR) in diagnostic.message


def test_no_advisory_when_no_sin_derecho_operations(tmp_path: Path) -> None:
    """Prorrata does not apply (100% con-derecho) -> no advisory noise."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        obs_repo = CalculationObservationRepository(objects=profile.repository)

        casilla_values = {
            _VOLUMEN_TOTAL_ID: Decimal("100000"),
            _VOLUMEN_CON_DERECHO_ID: Decimal("100000"),
            _PORCENTAJE_ID: Decimal("100"),
            _CUOTA_DEDUCIBLE_TOTAL_ID: Decimal("20000.00"),
        }
        diagnostics = collect_prorrata_regularizacion_diagnostics(
            _revision(),
            casilla_values,
            modelo=Modelo.M303.value,
            period_token="4T",
            filing_year=_YEAR,
            observation_repository=obs_repo,
        )

    assert diagnostics == ()


def test_no_advisory_on_mid_year_quarter(tmp_path: Path) -> None:
    """A mid-year quarter (1T) is never a regularisation event (LIVA art. 105.Cuatro)."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        obs_repo = CalculationObservationRepository(objects=profile.repository)

        casilla_values = {
            _VOLUMEN_TOTAL_ID: Decimal("100000"),
            _VOLUMEN_CON_DERECHO_ID: Decimal("80000"),
            _PORCENTAJE_ID: Decimal("80"),
            _CUOTA_DEDUCIBLE_TOTAL_ID: Decimal("20000.00"),
        }
        diagnostics = collect_prorrata_regularizacion_diagnostics(
            _revision(),
            casilla_values,
            modelo=Modelo.M303.value,
            period_token="1T",
            filing_year=_YEAR,
            observation_repository=obs_repo,
        )

    assert diagnostics == ()


def test_mid_year_active_prorrata_without_provisional_emits_missing_carry(tmp_path: Path) -> None:
    """An active general-prorrata register entry with no ladder value is visible in 1T."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        obs_repo = CalculationObservationRepository(objects=profile.repository)
        ProrrataRegisterRepository(bucket_id=_BUCKET, objects=profile.repository).save(
            ProrrataRegister(
                entries=(
                    ProrrataRegisterEntry(
                        ejercicio=_YEAR,
                        regime=ProrrataRegisterRegime.GENERAL,
                        especial_transition=None,
                    ),
                ),
            ),
        )

        diagnostics = collect_prorrata_regularizacion_diagnostics(
            _revision(period="1T"),
            {},
            modelo=Modelo.M303.value,
            period_token="1T",
            filing_year=_YEAR,
            bucket_id=_BUCKET,
            observation_repository=obs_repo,
        )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.binding_source is BindingSourceKind.PRORRATA_REGULARIZACION
    assert diagnostic.casilla_id == CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA
    assert "definitiva del ejercicio anterior" in diagnostic.message
    assert "por defecto" in diagnostic.message


def test_no_advisory_for_non_m303_modelo(tmp_path: Path) -> None:
    """Only Modelo 303 declares the prorrata semantic roles; every other modelo is silent."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        obs_repo = CalculationObservationRepository(objects=profile.repository)

        diagnostics = collect_prorrata_regularizacion_diagnostics(
            _revision(),
            {},
            modelo=Modelo.M130.value,
            period_token="4T",
            filing_year=_YEAR,
            observation_repository=obs_repo,
        )

    assert diagnostics == ()
