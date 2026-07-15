"""Modelo 100 base-liquidable-general-negative compensation — LIRPF Art. 50.3.

The prior-year generated negative base liquidable general (1391) is copied to
the next filing's Anexo C opening balance (1388). Its current-year applied
amount (1389) computes the Form 100 compensation line (0501), which the base
liquidable general formula (0500) subtracts. Art. 50.3 supplies the four-year
carry rule and requires compensation against positive base liquidable general.

Art. 48 is separate: its 25-percent rule governs the base imponible general
integration of gains and losses (0432/0433). It does not govern the 1391 →
1388 → 1389 → 0501 carry, and 1389 must not alter 0435.

The live differential asserts that applying an Anexo C amount reduces 0501 and
0500 by that amount while leaving 0435 unchanged; it derives the expected
relationship from the independently stated statutory base sequence, without
reimplementing the registry formulas.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    BindingId,
    CasillaId,
    RegistrySnapshot,
    RelationId,
    validated_casilla_id,
)
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.modelos import CalculationRevision, ModeloVerificationFindingKind
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ...modelo import calculate_modelo_revision, create_work_unit
from ...modelo._verification_actions import _evaluate_verification_predicates
from ...user_profile import UserProfileLifecycleRepository
from .._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: cap_le_when_positive predicates ignore the profile; supply a minimal real one.
_CASILLA_ONLY_PROFILE = TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime.GENERAL)

_STOCK_PREDICATE_ID = "modelo-100-2025-compensacion-base-neg-general-no-excede-stock"
_LIMITE_PREDICATE_ID = "modelo-100-2025-compensacion-base-neg-general-no-excede-limite"
_BASE_LIQUIDABLE_ART_50_REF = "ley-35-2006:art-50"
_GENERAL_BASE_ART_48_REF = "ley-35-2006:art-48"
_SAVINGS_BASE_ART_49_REF = "ley-35-2006:art-49"
_APLICADA_MAXIMA_FORMULA_ID = "renta-2025-base-liquidable-negativa-general-2024-aplicada-maxima"
_COMPENSACION_TOTAL_FORMULA_ID = "renta-2025-base-liquidable-negativa-general-compensacion-total"
_ANEXO_C_BASE_NEGATIVA_GENERAL_CONSTRUCT_ID = "renta-anexo-c-base-liquidable-negativa-general"

_MODELO = "100"
_PROFILE_ID = "10010000-0000-4100-8100-000000000100"
_BUCKET_ID = _PROFILE_ID
_PERIOD = "0A"
_FILING_YEAR = 2025


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"M100 base negativa fixture casilla key {value!r} is not a CasillaId") from exc


#: Anexo-C base-liquidable-general-negativa casillas (ejercicio-2024 origin).
_PENDIENTE_INICIO: CasillaId = _casilla_id("1388")  # opening pending (bound from prior 1391)
_APLICADO: CasillaId = _casilla_id("1389")  # Anexo C applied amount
_PENDIENTE_FIN: CasillaId = _casilla_id("1390")  # remainder rolled forward = 1388 − 1389
_APLICADA_MAXIMA: CasillaId = _casilla_id("base-liq-neg-general-2024-aplicada-maxima")  # Art. 50.3 ceiling
_BASE_IMPONIBLE_GENERAL: CasillaId = _casilla_id("0435")
_BASE_LIQUIDABLE_GENERAL: CasillaId = _casilla_id("0500")
_PRIOR_NEGATIVE_BASE_CASILLA: CasillaId = _casilla_id("1391")

#: Trabajo income leaf (Retribuciones dinerarias, importe íntegro) — a manual
#: input that produces a positive base liquidable general before the Art. 50.3 carry.
_TRABAJO_INGRESO: CasillaId = _casilla_id("0003")

_CLOCK = datetime(2026, 6, 30, 9, 0, 0, tzinfo=UTC)


def _seed_taxpayer_unit_profile() -> None:
    """Seed a single-taxpayer profile so the profile-sourced bindings resolve."""
    record = UserProfileRecord(
        profile_id=_PROFILE_ID,
        display_name="Test runtime profile",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="identity.name", value="Test"),
            UserProfileFact(path="identity.surnames", value="Operator"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.sex", value="H"),
            UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
            UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
            UserProfileFact(path="filing_export.declaration_type", value="1"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendientes_count", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendientes_minimos_aggregate_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.gastos_guarderia_reales_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.cotizaciones_ss_madre_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendientes_menores_3_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=Decimal("0")),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID).save(record)


def _seed_prior_negative_base(*, saldo: Decimal, obs_repo: CalculationObservationRepository) -> None:
    """Record the prior-year (2024) generated negative general base (casilla 1391).

    The ``previous_filing`` carry binding resolves this into the current year's
    opening pending (casilla 1388).
    """
    obs_repo.save_observation(
        registry_grounded_modelo_observation(
            modelo=_MODELO,
            filing_year=_FILING_YEAR - 1,
            period=_PERIOD,
            casilla_values={_PRIOR_NEGATIVE_BASE_CASILLA: saldo},
        ),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )


def _zeroed_channels(snapshot: RegistrySnapshot) -> tuple[dict[BindingId, Decimal], dict[RelationId, Decimal]]:
    binding_values = {binding.id: Decimal("0") for binding in snapshot.revision.bindings if binding.source != "profile"}
    relation_values = {relation.id: Decimal("0") for relation in snapshot.revision.relations}
    return binding_values, relation_values


def _calculate(*, casilla_inputs: dict[CasillaId, Decimal], obs_repo: CalculationObservationRepository):
    """Run the REAL M100 ``calculate_modelo_revision`` for filing year 2025."""
    snapshot = _snapshot()
    from .._binding_prefill import resolve_bindings_from_local_store

    carry = resolve_bindings_from_local_store(snapshot, repository=obs_repo).binding_values
    binding_values, relation_values = _zeroed_channels(snapshot)
    binding_values.update(carry)

    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    event_repo = BucketEventHistoryRepository()
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=_MODELO,
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, _PERIOD),
        revision_id=str(_FILING_YEAR),
        repository=work_repo,
        clock=_CLOCK,
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor=_BUCKET_ID,
        casilla_inputs=casilla_inputs,
        binding_values=binding_values,
        relation_values=relation_values,
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=_CLOCK,
    )
    return revision


def _snapshot():
    return resources().modelos.authority.snapshot(_MODELO, filing_year=_FILING_YEAR, period=_PERIOD)


def _v(revision: CalculationRevision, casilla: CasillaId) -> Decimal:
    return Decimal(revision.casilla_values[casilla])


def test_base_liquidable_negative_compensation_surfaces_cite_art50_not_art48_or_art49() -> None:
    revision = _snapshot().revision
    cap_formula = next(formula for formula in revision.formulas if formula.id == _APLICADA_MAXIMA_FORMULA_ID)
    compensation_formula = next(
        formula for formula in revision.formulas if formula.id == _COMPENSACION_TOTAL_FORMULA_ID
    )
    opening_pending = next(casilla for casilla in revision.casillas if casilla.id == _PENDIENTE_INICIO)
    compensation = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("0501"))
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _APLICADA_MAXIMA)
    construct = next(
        construct for construct in revision.constructs if construct.id == _ANEXO_C_BASE_NEGATIVA_GENERAL_CONSTRUCT_ID
    )

    for refs in (
        cap_formula.legal_refs,
        compensation_formula.legal_refs,
        opening_pending.legal_refs,
        compensation.legal_refs,
        casilla.legal_refs,
        construct.legal_refs,
    ):
        assert _BASE_LIQUIDABLE_ART_50_REF in refs
        assert _GENERAL_BASE_ART_48_REF not in refs
        assert _SAVINGS_BASE_ART_49_REF not in refs


@pytest.mark.parametrize("filing_year", [2024, 2025])
def test_opening_and_applied_base_liquidable_casillas_cite_art50(filing_year: int) -> None:
    revision = resources().modelos.authority.snapshot(_MODELO, filing_year=filing_year, period=_PERIOD).revision
    casillas = {casilla.id: casilla for casilla in revision.casillas}

    for casilla_id in (_PENDIENTE_INICIO, _APLICADO):
        assert _BASE_LIQUIDABLE_ART_50_REF in casillas[casilla_id].legal_refs
        assert _GENERAL_BASE_ART_48_REF not in casillas[casilla_id].legal_refs
        assert _SAVINGS_BASE_ART_49_REF not in casillas[casilla_id].legal_refs


# --- Oracle: the carried negative base is consumed (live), reducing the base ----


def test_applied_compensation_reduces_base_liquidable_general_by_applied_amount(tmp_path: Path) -> None:
    """An Anexo C applied amount reduces 0501 and 0500, not the Art. 48 base.

    Two real calculations share every input except the applied amount 1389:
    the baseline applies zero and the compensated run applies A. Art. 50.3
    makes 0501 the base-liquidation compensation, so 0501 and 0500 change by
    A while 0435 remains the unchanged Art. 48 base-imponible result.
    """
    ingreso = Decimal("40000.00")
    prior_negative = Decimal("3000.00")
    applied = Decimal("2000.00")  # ≤ prior pending and positive base-liquidables-general headroom

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        obs_repo = CalculationObservationRepository()
        _seed_taxpayer_unit_profile()
        _seed_prior_negative_base(saldo=prior_negative, obs_repo=obs_repo)

        baseline = _calculate(
            casilla_inputs={_TRABAJO_INGRESO: ingreso, _APLICADO: Decimal("0")},
            obs_repo=obs_repo,
        )
        compensated = _calculate(
            casilla_inputs={_TRABAJO_INGRESO: ingreso, _APLICADO: applied},
            obs_repo=obs_repo,
        )

    # The carried negative base is live: 1388 is populated from the prior 1391.
    assert _v(baseline, _PENDIENTE_INICIO) == prior_negative
    assert _v(compensated, _PENDIENTE_INICIO) == prior_negative

    # Art. 50.3 consumption: 0501 and base liquidable general drop by the
    # applied amount, while the Art. 48 base imponible general stays fixed.
    base_liq_drop = _v(baseline, _BASE_LIQUIDABLE_GENERAL) - _v(compensated, _BASE_LIQUIDABLE_GENERAL)
    base_imp_drop = _v(baseline, _BASE_IMPONIBLE_GENERAL) - _v(compensated, _BASE_IMPONIBLE_GENERAL)
    assert _v(baseline, _casilla_id("0501")) == Decimal("0")
    assert _v(compensated, _casilla_id("0501")) == applied
    assert base_imp_drop == Decimal("0")
    assert base_liq_drop == applied

    # Remainder rolls forward: 1390 = 1388 − 1389.
    assert _v(compensated, _PENDIENTE_FIN) == prior_negative - applied
    # The positive BLG headroom exceeds the stock, so the Art. 50.3 ceiling is the stock.
    assert _v(compensated, _APLICADA_MAXIMA) == prior_negative


# --- Fail-closed: no prior negative base → result unchanged ----------------------


def test_no_prior_negative_base_leaves_result_unchanged(tmp_path: Path) -> None:
    """A taxpayer with no prior negative base liquidable general sees zero change.

    The ceiling collapses to zero, the applied amount is forced to zero, and the
    base liquidable general equals the no-compensation baseline.
    """
    ingreso = Decimal("40000.00")

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        obs_repo = CalculationObservationRepository()
        _seed_taxpayer_unit_profile()
        # No prior-year 1391 seeded → carry resolves to zero.
        result = _calculate(
            casilla_inputs={_TRABAJO_INGRESO: ingreso, _APLICADO: Decimal("0")},
            obs_repo=obs_repo,
        )

    assert _v(result, _PENDIENTE_INICIO) == Decimal("0")
    assert _v(result, _APLICADA_MAXIMA) == Decimal("0")
    assert _v(result, _PENDIENTE_FIN) == Decimal("0")


# --- Fail-closed: over-application is BLOCKED by the verification predicates -----
#
# The BLOCKING cap_le_when_positive predicates are exercised directly against
# hand-built casilla maps (the M200 BIN-cap test pattern). Non-tautological: the
# predicates are the registry's own, evaluated against an over-claim / under-claim
# we construct, not a re-run of the cap formula. The ceiling value itself is
# produced by the real cap formula in the E2E calc above.


def _predicate(predicate_id: str):
    revision = resources().modelos.authority.validate_modelo(_MODELO).revisions["2025"]
    predicate = next(p for p in revision.verification_predicates if p.predicate_id == predicate_id)
    assert predicate.finding_kind == "BLOCKING_RULE"
    assert "cap_le_when_positive" in predicate.expression
    return predicate


def test_applied_exceeding_stock_is_blocked() -> None:
    """1389 > 1388 (the pending stock) fires the stock BLOCKING predicate."""
    predicate = _predicate(_STOCK_PREDICATE_ID)
    casilla_values = {
        _PENDIENTE_INICIO: Decimal("1000.00"),  # stock
        _APLICADO: Decimal("2500.00"),  # over the stock
    }
    findings = _evaluate_verification_predicates((predicate,), casilla_values, _CASILLA_ONLY_PROFILE)
    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert _STOCK_PREDICATE_ID in findings[0].message


def test_applied_exceeding_art50_ceiling_is_blocked() -> None:
    """1389 above the supplied Art. 50.3 ceiling is refused."""
    predicate = _predicate(_LIMITE_PREDICATE_ID)
    casilla_values = {
        _APLICADA_MAXIMA: Decimal("10000.00"),  # ceiling = 25%·40000 headroom
        _APLICADO: Decimal("15000.00"),  # over the ceiling
    }
    findings = _evaluate_verification_predicates((predicate,), casilla_values, _CASILLA_ONLY_PROFILE)
    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert _LIMITE_PREDICATE_ID in findings[0].message


def test_upper_bound_predicates_do_not_fire_below_limits() -> None:
    """The local upper-bound predicates do not fire below their supplied limits.

    This only proves the two predicate contracts; it makes no separate claim
    about the Art. 50.3 requirement to compensate at the maximum amount allowed.
    """
    stock_predicate = _predicate(_STOCK_PREDICATE_ID)
    limite_predicate = _predicate(_LIMITE_PREDICATE_ID)
    casilla_values = {
        _PENDIENTE_INICIO: Decimal("3000.00"),
        _APLICADA_MAXIMA: Decimal("3000.00"),
        _APLICADO: Decimal("1500.00"),  # below both bounds
    }
    assert _evaluate_verification_predicates((stock_predicate,), casilla_values, _CASILLA_ONLY_PROFILE) == []
    assert _evaluate_verification_predicates((limite_predicate,), casilla_values, _CASILLA_ONLY_PROFILE) == []


def test_applying_exactly_the_limits_is_permitted() -> None:
    """Applying exactly the stock / ceiling is permitted (<= holds at equality)."""
    stock_predicate = _predicate(_STOCK_PREDICATE_ID)
    limite_predicate = _predicate(_LIMITE_PREDICATE_ID)
    casilla_values = {
        _PENDIENTE_INICIO: Decimal("3000.00"),
        _APLICADA_MAXIMA: Decimal("3000.00"),
        _APLICADO: Decimal("3000.00"),
    }
    assert _evaluate_verification_predicates((stock_predicate,), casilla_values, _CASILLA_ONLY_PROFILE) == []
    assert _evaluate_verification_predicates((limite_predicate,), casilla_values, _CASILLA_ONLY_PROFILE) == []
