"""Modelo 100 (IRPF) base liquidable general negativa compensation — art. 48 LIRPF.

A prior-year negative *base imponible general* left pending (carried into the
current year as casilla 1388, ``irpf_anexo_c_base_liq_neg_pendiente_inicio``,
bound from the prior filing's casilla 1391) is compensated against the current
year's positive saldo (a) — "su importe se compensará en los cuatro años
siguientes ... con el saldo positivo de las rentas previstas en el párrafo a)
de este artículo ... con el límite del 25 por ciento de dicho saldo positivo"
(Ley 35/2006 art. 48). Before this fix the carried 1388 was DEAD: no formula
consumed it, so a taxpayer holding a prior negative general base over-declared.

The fix mirrors the proven Modelo 200 BIN compensation pattern:

* casilla 1388 — opening pending (already bound from the prior filing's 1391);
* casilla 1389 — operator-elective APPLIED amount (manual input);
* casilla ``base-liq-neg-general-2024-aplicada-maxima`` — internal art. 48
  ceiling = ``min(1388, max(0, 25%·0432 − 0433))``;
* the base imponible general formula (casilla 0435) subtracts 1389, clamped
  non-negative;
* casilla 1390 — remainder rolled forward = ``1388 − 1389``;
* two BLOCKING verification predicates bound 1389 (≤ 1388 stock; ≤ ceiling).

Grounding (non-tautological): the load-bearing assertion is the *consumption
WIRING* — that electing an applied amount A (within the art. 48 headroom)
reduces the base liquidable general by exactly A relative to an otherwise
identical filing that elects zero. The expectation (Δbase = −A) is derived from
art. 48's "su importe se compensará ... con el saldo positivo" — the
compensation reduces the positive general base by the applied amount — NOT from
the formula under test. The two runs share every other input, so the entire
income chain that produces casilla 0432 is held constant and the differential
isolates the art. 48 integration. A taxpayer with no prior negative base (the
fail-closed case) sees zero change. Over-application is refused by the BLOCKING
gates.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import (
    BindingId,
    CasillaId,
    RelationId,
    validated_casilla_id,
)
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.modelos._verification_report import ModeloVerificationFindingKind
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ...modelo import calculate_modelo_revision, create_work_unit
from ...modelo._actions import _evaluate_verification_predicates
from ...user_profile import UserProfileLifecycleRepository
from .._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: cap_le_when_positive predicates ignore the profile; supply a minimal real one.
_CASILLA_ONLY_PROFILE = TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime.GENERAL)

_STOCK_PREDICATE_ID = "modelo-100-2025-compensacion-base-neg-general-no-excede-stock"
_LIMITE_PREDICATE_ID = "modelo-100-2025-compensacion-base-neg-general-no-excede-limite"

_MODELO = "100"
_BUCKET_ID = "operator"
_PERIOD = "0A"
_FILING_YEAR = 2025


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"M100 base negativa fixture casilla key {value!r} is not a CasillaId") from exc

#: Anexo-C base-liquidable-general-negativa casillas (ejercicio-2024 origin).
_PENDIENTE_INICIO: CasillaId = _casilla_id("1388")  # opening pending (bound from prior 1391)
_APLICADO: CasillaId = _casilla_id("1389")  # operator-elective applied amount
_PENDIENTE_FIN: CasillaId = _casilla_id("1390")  # remainder rolled forward = 1388 − 1389
_APLICADA_MAXIMA: CasillaId = _casilla_id("base-liq-neg-general-2024-aplicada-maxima")  # internal art. 48 ceiling
_BASE_IMPONIBLE_GENERAL: CasillaId = _casilla_id("0435")
_BASE_LIQUIDABLE_GENERAL: CasillaId = _casilla_id("0500")
_PRIOR_NEGATIVE_BASE_CASILLA: CasillaId = _casilla_id("1391")

#: Trabajo income leaf (Retribuciones dinerarias, importe íntegro) — a manual
#: input that drives a positive saldo (a) / base imponible general so the art. 48
#: headroom is positive.
_TRABAJO_INGRESO: CasillaId = _casilla_id("0003")

_CLOCK = datetime(2026, 6, 30, 9, 0, 0, tzinfo=UTC)


def _seed_taxpayer_unit_profile() -> None:
    """Seed a single-taxpayer profile so the profile-sourced bindings resolve."""
    record = UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Test runtime profile",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.sex", value="varon"),
            UserProfileFact(path="renta_taxpayer.marital_status", value="soltero"),
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


def _zeroed_channels(snapshot) -> tuple[dict[BindingId, Decimal], dict[RelationId, Decimal]]:
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


def _v(revision, casilla: CasillaId) -> Decimal:
    return Decimal(revision.casilla_values[casilla])


# --- Oracle: the carried negative base is consumed (live), reducing the base ----


def test_applied_compensation_reduces_base_liquidable_general_by_applied_amount(tmp_path: Path) -> None:
    """Electing applied amount A (within art. 48 headroom) reduces the base by A.

    Two real calculations share every input except the applied amount 1389:
    the baseline elects zero, the compensated run elects A. art. 48 reduces the
    positive general base by the applied compensation, so the base liquidable
    general must drop by exactly A. The differential isolates the art. 48
    integration from the income chain (held constant across both runs); the
    expected Δ = −A is grounded in the statute, not the formula under test.
    """
    ingreso = Decimal("40000.00")
    prior_negative = Decimal("3000.00")
    applied = Decimal("2000.00")  # ≤ prior_negative AND ≤ 25%·base headroom (10000)

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

    # art. 48 consumption: base liquidable general drops by exactly the applied
    # amount; the base imponible general (its upstream) drops by the same amount.
    base_liq_drop = _v(baseline, _BASE_LIQUIDABLE_GENERAL) - _v(compensated, _BASE_LIQUIDABLE_GENERAL)
    base_imp_drop = _v(baseline, _BASE_IMPONIBLE_GENERAL) - _v(compensated, _BASE_IMPONIBLE_GENERAL)
    assert base_imp_drop == applied
    assert base_liq_drop == applied

    # Remainder rolls forward: 1390 = 1388 − 1389.
    assert _v(compensated, _PENDIENTE_FIN) == prior_negative - applied
    # Ceiling = min(stock, 25%·base) = min(3000, 10000) = 3000.
    assert _v(compensated, _APLICADA_MAXIMA) == prior_negative


# --- Fail-closed: no prior negative base → result unchanged ----------------------


def test_no_prior_negative_base_leaves_result_unchanged(tmp_path: Path) -> None:
    """A taxpayer with no prior negative general base (1388 = 0) sees zero change.

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


def test_applied_exceeding_art48_ceiling_is_blocked() -> None:
    """1389 above the art. 48 ceiling (min(stock, 25%·base headroom)) is refused."""
    predicate = _predicate(_LIMITE_PREDICATE_ID)
    casilla_values = {
        _APLICADA_MAXIMA: Decimal("10000.00"),  # ceiling = 25%·40000 headroom
        _APLICADO: Decimal("15000.00"),  # over the ceiling
    }
    findings = _evaluate_verification_predicates((predicate,), casilla_values, _CASILLA_ONLY_PROFILE)
    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert _LIMITE_PREDICATE_ID in findings[0].message


def test_electing_less_than_limits_is_permitted() -> None:
    """Electing LESS than the stock and the ceiling raises no finding.

    Compensation is a right, not a mandate — applying below both bounds is
    legitimate and neither BLOCKING gate may refuse it.
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
