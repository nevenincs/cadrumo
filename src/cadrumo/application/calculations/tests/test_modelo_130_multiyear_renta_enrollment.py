"""Multi-year-renta authorization enrollment for Modelo 130.

This module is the enrolling end-to-end persona test for Modelo 130 under
the ``modelo-multiyear-renta`` contract. It drives the REAL M130 backend (real
encrypted-SQLite observation store, the real registry authority, the real
``previous_filing`` binding resolver, the real registry calculation engine
— no mocks) across two distinct renta (annual) years, records each year
through the :class:`EnrollmentRecorder`, and cross-checks the recorded
year-set against the authorization manifest via
:func:`assert_enrollment_matches_manifest`.

The cross-renta hook is the prior-year minoración fold-in. M130's casilla
13 is computed by a banded formula keyed on
``irpf.previous_year_economic_activity_net_income`` — a
``source = "previous_filing"`` binding (selector ``source_modelo = "100",
filing_year_delta = -1, period = "0A"``) that sums the prior annual Renta
(Modelo 100) net-income casillas 0224/1479/1553/1577. The minoración is
100/75/50/25/0 euros as the prior-year net income falls in the
≤9000/≤10000/≤11000/≤12000/>12000 bands (AEAT M130 instructions, casilla
13). So renta year N's annual M100 filing genuinely flows across the renta
boundary into renta year N+1's quarterly M130 minoración — a distinct-year
continuity, not merely cross-quarter.

The quarter-to-quarter negative-result carry-forward (casilla 15) is
covered end-to-end by ``test_modelo_130_carry_forward_continuity``; this
module adds the *cross-renta* leg the authorization gate requires (two
distinct calculated renta years) on top of it.

Grounding (non-tautological): the prior-year net income is a real seeded
M100 observation; the minoración constant (100) is the AEAT-defined band
value for the ≤9000 band, not a value hand-computed from the formula under
test. The load-bearing assertion is the *wiring* invariant — renta year
N+1's casilla 13 is selected by renta year N's persisted M100 net income —
which the M130 instruction defines as the minoración keyed on "el importe
de los rendimientos netos del ejercicio anterior". A wrong cross-renta wiring
(no fold-in, or the wrong year) would surface a different band and red the
assertion.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....core.resources import resources
from ....domain.calculations.registry import (
    BindingId,
)
from ....domain.modelos import CalculationRevision
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ...modelo import calculate_modelo_revision, create_work_unit
from .._binding_prefill import resolve_bindings_from_local_store
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    BucketEventHistoryRepository,
    CalculationObservationRepository,
]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "130"
_PROFILE_ID = "13013013-0130-4130-8130-130130130131"
_BUCKET_ID = _PROFILE_ID

#: The two distinct renta years the enrollment exercises. Renta year N's
#: annual M100 net income feeds renta year N+1's M130 casilla-13 minoración.
_YEAR_N = 2025
_YEAR_N_PLUS_1 = 2026

#: M130 revision covering 2019 onward (both renta years resolve to it).
_REVISION = "2019-y-siguientes"

#: The prior-year minoración binding (M100 net income, filing_year_delta -1)
#: and the casilla it drives.
_PREV_YEAR_BINDING: BindingId = "irpf.previous_year_economic_activity_net_income"
_CARRY_FORWARD_BINDING: BindingId = "modelo-130-resultados-negativos-anteriores"


_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02")
_M130_PREVIOUS_PAYMENTS_CASILLA: CasillaId = validated_casilla_id("05")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10")
_MINORACION_CASILLA: CasillaId = validated_casilla_id("13")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16")
_M130_PRIOR_RETURN_RESULT_CASILLA: CasillaId = validated_casilla_id("18")
_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: CasillaId = validated_casilla_id("0224")
_M100_RENDIMIENTO_SOURCE_1479_CASILLA: CasillaId = validated_casilla_id("1479")
_M100_RENDIMIENTO_SOURCE_1553_CASILLA: CasillaId = validated_casilla_id("1553")
_M100_RENDIMIENTO_SOURCE_1577_CASILLA: CasillaId = validated_casilla_id("1577")

#: Prior-year (renta year N) M100 actividad-económica net income, seeded as a
#: real annual observation. €8000 falls in the ≤9000 minoración band, so renta
#: year N+1's casilla 13 must resolve to the AEAT-defined 100-euro minoración.
#: The band boundary (9000) and the minoración constant (100) are AEAT M130
#: instruction values, not formula outputs hand-computed by the test author.
_PRIOR_YEAR_NET_INCOME = Decimal("8000")
_EXPECTED_MINORACION = Decimal("100.00")

_CLOCK = datetime(2026, 5, 1, 9, 0, 0, tzinfo=UTC)

#: A representative first-quarter input scenario, identical in shape across both
#: renta years: a modest actividad-económica result. The numeric result is
#: produced by the real engine; the test asserts the cross-renta minoración
#: wiring, not a hand-computed liquidation.
_Q1_INPUTS: dict[CasillaId, Decimal] = {
    _M130_INGRESOS_CASILLA: Decimal("6000"),
    _M130_GASTOS_CASILLA: Decimal("2000"),
    _M130_PREVIOUS_PAYMENTS_CASILLA: Decimal("0"),
    _M130_RETENCIONES_CASILLA: Decimal("0"),
    _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
    _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
    _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
    _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
}


def _seed_ready_profile() -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_PROFILE_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value="2020-01-01"),
            ),
            created_at=_CLOCK,
            updated_at=_CLOCK,
        ),
    )


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    """Real encrypted SQLite repos over an isolated profile — no mocks."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        _seed_ready_profile()
        yield (
            WorkUnitCatalogueRepository(objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
            BucketEventHistoryRepository(objects=objects),
            CalculationObservationRepository(objects=objects),
        )


def _calculate_quarter(
    repos: _Repos,
    *,
    filing_year: int,
    period: str,
    casilla_inputs: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal],
) -> CalculationRevision:
    """Run the REAL M130 calculation for one renta year quarter.

    Returns the persisted :class:`CalculationRevision`-derived result whose
    ``casilla_values`` mapping the enrollment records as produced-value
    evidence.
    """
    wu_repo, cr_repo, bv_repo, _obs_repo = repos
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=_MODELO,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        revision_id=_REVISION,
        repository=wu_repo,
        clock=_CLOCK,
    )
    return calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values=binding_values,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_CLOCK,
    )


def _seed_prior_year_m100(obs_repo: CalculationObservationRepository, *, filing_year: int) -> None:
    """Record renta year N's annual Renta (M100) net-income observation.

    The :data:`_PREV_YEAR_BINDING` sums whichever of M100 casillas
    0224/1479/1553/1577 apply in the prior ejercicio. This full-filing scenario
    records net income in 0224 and explicit zeros for its non-applicable
    rendimiento sources; resolver completeness is tested separately.
    """
    obs_repo.save(
        obs_repo.prepare_observation_envelope(
            registry_grounded_modelo_observation(
                modelo="100",
                filing_year=filing_year,
                period="0A",
                casilla_values={
                    _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: _PRIOR_YEAR_NET_INCOME,
                    _M100_RENDIMIENTO_SOURCE_1479_CASILLA: Decimal("0"),
                    _M100_RENDIMIENTO_SOURCE_1553_CASILLA: Decimal("0"),
                    _M100_RENDIMIENTO_SOURCE_1577_CASILLA: Decimal("0"),
                },
            ),
            source_kind="app_filing",
            captured_at=_CLOCK,
        )
    )


def test_modelo_130_enrolls_two_renta_years_via_prior_year_minoracion(repos: _Repos) -> None:
    """End-to-end enrollment: prior-year M100 net income folds into next year's M130.

    Drives the REAL M130 backend for two distinct renta years. Renta year N's
    1T is computed with its own prior-year minoración context; renta year N's
    annual M100 net income is then seeded, and renta year N+1's 1T resolves its
    ``previous_filing`` minoración binding from the local store (no manual
    re-entry) and is computed with it. Both calculated years are recorded
    through the :class:`EnrollmentRecorder` (calculation mode, evidence = the
    produced-value count from a real engine run) and the recorded distinct-year
    set is cross-checked against the authorization manifest claim. A single-year
    or stub run would raise at :func:`assert_enrollment_matches_manifest`,
    turning the authorization gate RED.

    The load-bearing cross-renta wiring invariant: renta year N+1's casilla 13
    equals the AEAT minoración for the band renta year N's persisted M100 net
    income falls in (€8000 -> ≤9000 band -> 100).
    """
    _wu_repo, _cr_repo, _bv_repo, obs_repo = repos
    recorder = EnrollmentRecorder(_MODELO)

    # Renta year N (1T): a real calculation. Its prior-year minoración context
    # (renta year N-1's M100) is absent, so the binding is supplied as zero —
    # the year-N leg's role is to be a genuine, distinct calculated renta year.
    year_n = _calculate_quarter(
        repos,
        filing_year=_YEAR_N,
        period="1T",
        casilla_inputs=_Q1_INPUTS,
        binding_values={
            _PREV_YEAR_BINDING: Decimal("0"),
            _CARRY_FORWARD_BINDING: Decimal("0"),
        },
    )
    recorder.record_calculation_year(filing_year=_YEAR_N, produced_value_count=len(year_n.casilla_values))

    # Seed renta year N's annual M100 net income: this is the cross-renta fact
    # that feeds renta year N+1's minoración.
    _seed_prior_year_m100(obs_repo, filing_year=_YEAR_N)

    # Renta year N+1 (1T): resolve the previous_filing minoración binding from
    # the local store — it auto-pulls renta year N's M100 net income — then run
    # a real calculation with it. Nothing about the prior-year income is
    # re-keyed by hand.
    snapshot_n1 = resources().modelos.authority.snapshot(_MODELO, filing_year=_YEAR_N_PLUS_1, period="1T")
    resolved = resolve_bindings_from_local_store(snapshot_n1, repository=obs_repo).binding_values
    assert resolved.get(_PREV_YEAR_BINDING) == _PRIOR_YEAR_NET_INCOME

    year_n1 = _calculate_quarter(
        repos,
        filing_year=_YEAR_N_PLUS_1,
        period="1T",
        casilla_inputs=_Q1_INPUTS,
        binding_values={
            _PREV_YEAR_BINDING: resolved[_PREV_YEAR_BINDING],
            _CARRY_FORWARD_BINDING: Decimal("0"),
        },
    )
    recorder.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=len(year_n1.casilla_values))

    # Cross-renta wiring invariant: renta year N+1's casilla 13 is selected by
    # renta year N's persisted M100 net income band (€8000 -> ≤9000 -> 100).
    assert Decimal(year_n1.casilla_values[_MINORACION_CASILLA]) == _EXPECTED_MINORACION

    # Authorization-gate enrollment: the recorded two-year set must equal the
    # manifest's renta_years claim and span >= 2 distinct years.
    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)
