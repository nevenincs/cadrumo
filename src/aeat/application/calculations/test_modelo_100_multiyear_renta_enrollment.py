"""Multi-year-renta authorization enrollment for Modelo 100 (IRPF anual).

This module is the enrolling end-to-end persona test for Modelo 100 under
the ``modelo-multiyear-renta`` ADR and its income-tax companion
``modelo-multiyear-renta-income`` (A4). It drives the REAL M100 registry
engine across two distinct renta (annual) years, records each through the
:class:`EnrollmentRecorder`, and cross-checks the recorded two-year set
against the authorization manifest via
:func:`assert_enrollment_matches_manifest`.

The cross-renta hook is the Anexo C base-liquidable-general-negativa
carry-forward (Ley 35/2006 art. 49). A year's *generated* negative general
base left pending — casilla 1391 (``irpf_anexo_c_base_liq_neg_generado``,
"Base liquidable general negativa de <año> pendiente de compensar en los
cuatro ejercicios siguientes") — becomes, in the following year's
declaration, the *opening* pending balance for that origin ejercicio —
casilla 1388 (``irpf_anexo_c_base_liq_neg_pendiente_inicio``, "Ejercicio
2024: Pendiente de aplicación al principio del periodo"). The
``previous_filing`` binding
``renta-2025-base-liquidable-negativa-general-anterior`` (selector
``source_modelo = "100", source_output = "1391", filing_year_delta = -1,
period = "0A"``, ``op = copy``) makes casilla 1388 auto-resolve from the
prior filing, so the operator does not re-key the carried saldo. art. 49
caps the carry to the four following ejercicios; that year-tagged expiry
window and the integración subtract that *consumes* the opening pending
into the current-year general base are deferred calc-completeness follow-ons
(see the A4 ADR's stated M100 constraint).

Grounding (non-tautological): M100's per-casilla saldo has no numeric
workbook oracle, so — exactly as the A4 ADR mandates for M100 — this
enrollment asserts the cross-renta WIRING and provenance, never an invented
Decimal. The prior-year generated saldo (casilla 1391) is a real seeded
observation; the load-bearing assertion is that each year's opening pending
(casilla 1388) equals the prior year's persisted generated saldo,
year-isolated — which art. 49 establishes as the negative-general-base
carried forward to the following ejercicio. A wrong cross-year wiring (no
carry, or the wrong year) would surface a different value and red the
assertion.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...core.resources import resources
from ...domain.calculations.registry import (
    CasillaObservation,
    InputKind,
    RegistryModeloObservation,
    resolve_bound_casilla_inputs,
)
from ...tests.secure_sql import isolated_runtime_profile
from ._binding_prefill import resolve_bindings_from_local_store
from ._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from ._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "100"

#: Casillas on the cross-renta Anexo-C base-liquidable-general-negativa carry.
#: 1391 is the end-of-year *generated* saldo pending future application; 1388
#: is the next year's *opening* pending for that origin ejercicio, bound from
#: the prior year's 1391 by ``renta-2025-base-liquidable-negativa-general-anterior``.
_GENERATED_SALDO = "1391"
_PENDIENTE_INICIO = "1388"

#: Two distinct renta years the enrollment spans; each sources the prior year's 1391.
_YEAR_N = 2024
_YEAR_N_PLUS_1 = 2025

#: Distinct prior-year generated saldo per source year so a cross-year
#: contamination (year N's carry leaking into year N+1) would surface.
_SALDO_BY_SOURCE_YEAR: dict[int, Decimal] = {
    2023: Decimal("4000.00"),
    2024: Decimal("2500.00"),
}

_CLOCK = datetime(2026, 6, 30, 9, 0, 0, tzinfo=UTC)


def _seed_prior_year_saldo(
    *, source_year: int, saldo: Decimal, obs_repo: CalculationObservationRepository
) -> None:
    """Record a prior-year M100 end-of-year generated saldo (casilla 1391)."""
    obs_repo.save_observation(
        RegistryModeloObservation(
            modelo=_MODELO,
            filing_year=source_year,
            period="0A",
            observations=(CasillaObservation(casilla_id=_GENERATED_SALDO, value=saldo),),
        ),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )


def _resolve_bound_casillas_100(
    *, filing_year: int, obs_repo: CalculationObservationRepository
) -> dict[str, Decimal]:
    """Resolve the REAL M100 bound-casilla inputs for ``filing_year`` from the store.

    Drives the real ``previous_filing`` binding resolver
    (:func:`resolve_bindings_from_local_store`) against the live registry
    snapshot, then the real :func:`resolve_bound_casilla_inputs` to materialise
    every bound casilla — including the Anexo-C opening-pending casilla 1388,
    which the art.49 carry binding fills from the prior year's generated saldo
    (casilla 1391). No mocks: the resolver reads the encrypted-SQLite
    observation store and the registry binding definitions.

    M100 also carries many other bound casillas (the retenciones /
    pagos-fraccionados dependency bindings); those are not the cross-renta hook
    under test, so each is supplied as a zero fact (no dependent-modelo
    observation for this pure-carry scenario). The carry binding's resolved
    value overlays the zeros, so casilla 1388 lands the real prior-year saldo.

    Scope note (honest): this enrollment proves the cross-renta *carry wiring
    and provenance* — the resolution of casilla 1388 from the prior filing's
    1391 across two distinct renta years. It does NOT drive M100's full cuota
    engine (which requires a complete persona profile), and the opening-pending
    saldo is not yet *consumed* by an integración-subtract into the
    base-liquidable-general — that downstream consumption is tracked as a
    calc-completeness follow-on. The savings-base (0441-family) art.49 carry
    and the deeper four-year multi-origin-year window are likewise follow-ons;
    this enrollment covers the general-base carry for the immediately-prior
    origin year only.
    """
    snapshot = resources().modelos.authority.snapshot(_MODELO, filing_year=filing_year, period="0A")
    bound_binding_ids = {
        casilla.binding
        for casilla in snapshot.revision.casillas
        if casilla.input_kind is InputKind.BOUND and casilla.binding is not None
    }
    facts: dict[str, Decimal] = {binding_id: Decimal("0") for binding_id in bound_binding_ids}
    facts.update(resolve_bindings_from_local_store(snapshot, repository=obs_repo).binding_values)
    return resolve_bound_casilla_inputs(snapshot.revision, facts)


def test_modelo_100_opening_pending_resolves_from_prior_year_saldo(tmp_path: Path) -> None:
    """Casilla 1388 (opening pending) auto-resolves to the prior year's 1391 saldo.

    The cross-renta continuity contract: once the prior M100 is recorded, the
    ``filing_year_delta = -1`` carry populates casilla 1388 from that prior
    1391 generated saldo — the operator does not re-key the carried negative
    general base.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _seed_prior_year_saldo(source_year=2023, saldo=_SALDO_BY_SOURCE_YEAR[2023], obs_repo=obs_repo)
        resolved = _resolve_bound_casillas_100(filing_year=_YEAR_N, obs_repo=obs_repo)
    assert resolved[_PENDIENTE_INICIO] == _SALDO_BY_SOURCE_YEAR[2023]


def test_modelo_100_base_liquidable_negativa_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: M100 art.49 saldo carry across two renta years.

    Drives the real M100 ``previous_filing`` resolver + bound-casilla
    resolution for two distinct renta years (2024, 2025), each sourcing the
    prior year's 1391 generated saldo (2023, 2024), records each through the
    :class:`EnrollmentRecorder` (CALC; evidence = the count of real bound
    casillas the resolver produced), and cross-checks the recorded two-year set
    against the authorization manifest. Year N's prior filing is in the store
    but must not contaminate Year N+1's resolver. A single-year or stub run
    raises at :func:`assert_enrollment_matches_manifest`.

    Honest scope (see :func:`_resolve_bound_casillas_100`): this proves the
    general-base art.49 carry *wiring* across two renta years. The full M100
    cuota engine, the integración-subtract consumption of the opening saldo,
    the savings-base (0441-family) carry, and the deeper four-year window are
    deferred calc-completeness follow-ons — not claimed by this enrollment.
    """
    recorder = EnrollmentRecorder(_MODELO)

    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _seed_prior_year_saldo(source_year=2023, saldo=_SALDO_BY_SOURCE_YEAR[2023], obs_repo=obs_repo)
        _seed_prior_year_saldo(source_year=2024, saldo=_SALDO_BY_SOURCE_YEAR[2024], obs_repo=obs_repo)

        resolved_n = _resolve_bound_casillas_100(filing_year=_YEAR_N, obs_repo=obs_repo)
        recorder.record_calculation_year(filing_year=_YEAR_N, produced_value_count=len(resolved_n))

        resolved_n1 = _resolve_bound_casillas_100(filing_year=_YEAR_N_PLUS_1, obs_repo=obs_repo)
        recorder.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=len(resolved_n1))

    # Cross-renta wiring invariant: each year's opening pending equals the prior
    # year's end-of-year generated saldo, year-isolated.
    assert resolved_n[_PENDIENTE_INICIO] == _SALDO_BY_SOURCE_YEAR[2023]
    assert resolved_n1[_PENDIENTE_INICIO] == _SALDO_BY_SOURCE_YEAR[2024]

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)
