"""Multi-year-renta authorization enrollment for Modelo 100 (IRPF anual).

This module is the enrolling end-to-end persona test for Modelo 100 under
the ``modelo-multiyear-renta`` contract and its income-tax companion
``modelo-multiyear-renta-income`` (A4). It drives the REAL M100 calculation
engine (``calculate_modelo_revision``) across two distinct renta (annual)
years, records each through the :class:`EnrollmentRecorder`, and cross-checks
the recorded two-year set against the authorization manifest via
:func:`assert_enrollment_matches_manifest`.

The cross-renta hook is the Anexo C base-liquidable-general-negativa
carry-forward. A year's *generated* negative general base left pending —
casilla 1391 (``irpf_anexo_c_base_liq_neg_generado``, "Base liquidable
general negativa de <año> pendiente de compensar en los cuatro ejercicios
siguientes") — becomes, in the following year's declaration, the *opening*
pending balance for the immediately-prior origin ejercicio — casilla 1388
(``irpf_anexo_c_base_liq_neg_pendiente_inicio``; in the 2025 revision its
label is "Ejercicio 2024: Pendiente de aplicación al principio del
periodo", in the 2024 revision "Ejercicio 2023: ..."). The
``previous_filing`` binding ``renta-{year}-base-liquidable-negativa-general-anterior``
(selector ``source_modelo = "100", source_casilla_id = "1391",
filing_year_delta = -1, period = "0A"``, ``op = copy``) makes casilla 1388
auto-resolve from the prior filing, so the operator does not re-key the
carried saldo. The carry is origin-year-matched in both revisions (each
revision's 1388 is the immediately-prior origin year).

Calc-mode (honest evidence): each renta year is driven through the REAL
``calculate_modelo_revision`` — the same full-engine path M130/M200/M202/M151
use — so the ``evidence_class = calculation`` manifest label is backed by an
actual calculation, not resolver output. A taxpayer-unit ``UserProfileRecord``
is seeded so the ``source = "profile"`` bindings (tax-residence CCAA, taxpayer
birth date, declaration type, marital status, ...) auto-resolve through
``_resolve_profile_bindings_for_calculation``; no profile fact is hand-fed
through the caller channel. The carried prior-year saldo is the one
``previous_filing`` fact resolved from the local observation store and supplied
through the binding channel (mirroring the production calculate path, which
does not itself scan the store for previous_filing bindings).

Grounding (non-tautological): M100's per-casilla saldo has no numeric workbook
oracle, so the load-bearing assertion is the cross-renta WIRING invariant —
each year's opening pending (casilla 1388) equals the prior year's persisted
generated saldo (casilla 1391), year-isolated — established by the AEAT M100
Anexo-C carry-forward. The prior-year saldo is a real seeded observation, never
a value hand-computed from the formula under test. A wrong cross-year wiring
(no carry, or the wrong origin year) would surface a different value and red
the assertion.

Honest scope: this enrollment proves the GENERAL-base carry for the
immediately-prior origin ejercicio. The integración-subtract that *consumes*
the opening saldo into the current-year base reduction, the savings-base
(0441-family) art.49 carry, and the deeper four-year multi-origin-year window
are deferred calc-completeness follow-ons — not claimed here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ids import BindingId, RelationId
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ...modelo._calculation_actions import calculate_modelo_revision
from ...modelo.work_lifecycle import create_work_unit
from .._binding_prefill import resolve_bindings_from_local_store
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from ..observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "100"
_PROFILE_ID = "10010000-0000-4100-8100-000000000101"
_BUCKET_ID = _PROFILE_ID
_PERIOD = "0A"


#: Casillas on the cross-renta Anexo-C base-liquidable-general-negativa carry.
#: 1391 is the end-of-year *generated* saldo pending future application; 1388
#: is the next year's *opening* pending for the immediately-prior origin
#: ejercicio, bound from the prior year's 1391 by the carry binding.


_GENERATED_SALDO: CasillaId = validated_casilla_id("1391")
_PENDIENTE_INICIO: CasillaId = validated_casilla_id("1388")

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


def _snapshot(filing_year: int) -> RegistrySnapshot:
    return bundled_authority().snapshot(_MODELO, filing_year=filing_year, period=_PERIOD)


def _seed_prior_year_saldo(*, source_year: int, saldo: Decimal, obs_repo: CalculationObservationRepository) -> None:
    """Record a prior-year M100 end-of-year generated saldo (casilla 1391)."""
    obs_repo.save(
        obs_repo.prepare_observation_envelope(
            registry_grounded_modelo_observation(
                modelo=_MODELO,
                filing_year=source_year,
                period=_PERIOD,
                casilla_values={_GENERATED_SALDO: saldo},
            ),
            source_kind="app_filing",
            captured_at=_CLOCK,
        )
    )


def _seed_taxpayer_unit_profile() -> None:
    """Seed a realistic single-taxpayer ``UserProfileRecord``.

    The seeded facts cover every ``source = "profile"`` binding M100's calc
    chain consumes across the 2024 and 2025 revisions (tax-residence CCAA,
    taxpayer birth date for ``age_at_year_end``, declaration type, marital
    status and the derived marriage facts, minor-children count). The profile
    is the substrate of record, so ``calculate_modelo_revision`` auto-resolves
    these via ``_resolve_profile_bindings_for_calculation`` — no profile fact
    is hand-fed through the caller binding channel.
    """
    # The display_name MUST match the label the isolated_runtime_profile
    # fixture stamps on the bucket's profile manifest ("Test runtime profile");
    # a divergent label trips the torn-rename guard in CommittedProfileView.
    record = UserProfileRecord(
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
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.sex", value="H"),
            UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
            UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            # Single taxpayer, no dependants: every family / guardería / descendant
            # Decimal-channel profile fact is a true zero for this persona.
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
            UserProfileFact(path="renta_family.descendientes_count", value=Decimal("0")),
            UserProfileFact(path="renta_family.cotizaciones_ss_madre_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
            UserProfileFact(path="renta_family.unidad_familiar_otros_miembros_base", value=Decimal("0")),
            UserProfileFact(path="renta_family.madrid_nacimiento_adopcion_eligible_count", value=Decimal("0")),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    seed_test_profile_record(record)


def _calculate_100(*, filing_year: int, obs_repo: CalculationObservationRepository):
    """Run the REAL M100 ``calculate_modelo_revision`` for ``filing_year``.

    Resolves the ``previous_filing`` carry from the local observation store and
    supplies it (plus a zero default for every other non-profile binding)
    through the caller binding channel; the seeded user profile auto-resolves
    the ``source = "profile"`` bindings; relations are supplied as zero (no
    dependent-modelo activity for this pure-carry persona). Returns the
    persisted :class:`CalculationRevision`.
    """
    snapshot = _snapshot(filing_year)
    carry = resolve_bindings_from_local_store(snapshot, repository=obs_repo).binding_values
    # Every non-profile binding defaults to zero through the caller channel;
    # the previous_filing carry overlays its real resolved value. profile
    # bindings are deliberately omitted so the profile resolver fills them.
    binding_values: dict[BindingId, Decimal] = {
        binding.id: Decimal("0") for binding in snapshot.revision.bindings if binding.source != "profile"
    }
    binding_values.update(carry)
    relation_values: dict[RelationId, Decimal] = {relation.id: Decimal("0") for relation in snapshot.revision.relations}

    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    event_repo = BucketEventHistoryRepository()
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=_MODELO,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, _PERIOD),
        revision_id=str(filing_year),
        repository=work_repo,
        clock=_CLOCK,
    )
    return calculate_modelo_revision(
        work_unit.work_unit_id,
        actor=_BUCKET_ID,
        casilla_inputs={},
        binding_values=binding_values,
        relation_values=relation_values,
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=_CLOCK,
    )


def test_modelo_100_opening_pending_resolves_from_prior_year_saldo(tmp_path: Path) -> None:
    """A real M100 calculation lands casilla 1388 from the prior year's 1391 saldo.

    The cross-renta continuity contract: once the prior M100 is recorded, the
    ``filing_year_delta = -1`` carry populates casilla 1388 from that prior
    1391 generated saldo, and a real ``calculate_modelo_revision`` emits it —
    the operator does not re-key the carried negative general base.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        obs_repo = CalculationObservationRepository()
        _seed_taxpayer_unit_profile()
        _seed_prior_year_saldo(source_year=2023, saldo=_SALDO_BY_SOURCE_YEAR[2023], obs_repo=obs_repo)
        revision = _calculate_100(filing_year=_YEAR_N, obs_repo=obs_repo)
    assert Decimal(revision.casilla_values[_PENDIENTE_INICIO]) == _SALDO_BY_SOURCE_YEAR[2023]


def test_modelo_100_base_liquidable_negativa_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: M100 general-base saldo carry across two renta years.

    Drives the REAL M100 ``calculate_modelo_revision`` for two distinct renta
    years (2024, 2025), each sourcing the prior year's 1391 generated saldo
    (2023, 2024), records each through the :class:`EnrollmentRecorder` (CALC;
    evidence = the produced-value count from the real engine run), and
    cross-checks the recorded two-year set against the authorization manifest.
    Year N's prior filing is in the store but must not contaminate Year N+1's
    resolver. A single-year or stub run raises at
    :func:`assert_enrollment_matches_manifest`.

    Honest scope: this proves the general-base carry *wiring* across two renta
    years through the full calc. The integración-subtract consumption of the
    opening saldo, the savings-base (0441-family) carry, and the deeper
    four-year window are deferred calc-completeness follow-ons — not claimed by
    this enrollment.
    """
    recorder = EnrollmentRecorder(_MODELO)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        obs_repo = CalculationObservationRepository()
        _seed_taxpayer_unit_profile()
        _seed_prior_year_saldo(source_year=2023, saldo=_SALDO_BY_SOURCE_YEAR[2023], obs_repo=obs_repo)
        _seed_prior_year_saldo(source_year=2024, saldo=_SALDO_BY_SOURCE_YEAR[2024], obs_repo=obs_repo)

        revision_n = _calculate_100(filing_year=_YEAR_N, obs_repo=obs_repo)
        recorder.record_calculation_year(filing_year=_YEAR_N, produced_value_count=len(revision_n.casilla_values))

        revision_n1 = _calculate_100(filing_year=_YEAR_N_PLUS_1, obs_repo=obs_repo)
        recorder.record_calculation_year(
            filing_year=_YEAR_N_PLUS_1,
            produced_value_count=len(revision_n1.casilla_values),
        )

    # Cross-renta wiring invariant: each year's opening pending equals the prior
    # year's end-of-year generated saldo, year-isolated.
    assert Decimal(revision_n.casilla_values[_PENDIENTE_INICIO]) == _SALDO_BY_SOURCE_YEAR[2023]
    assert Decimal(revision_n1.casilla_values[_PENDIENTE_INICIO]) == _SALDO_BY_SOURCE_YEAR[2024]

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)
