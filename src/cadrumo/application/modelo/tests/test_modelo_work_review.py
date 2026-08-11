"""Real persistence and registry coverage for the modelo work review projection."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import Period
from ....domain.calculations.registry import InputKind, bundled_authority, revision_date_binding_ids
from ....domain.filing import ModeloValueKind
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    WorkUnit,
    derive_calculation_revision_id,
    derive_work_unit_id,
    upsert_calculation_revision,
    upsert_work_unit,
)
from ....domain.user_profile import UserProfileFact
from ...user_profile import UserProfileLifecycleRepository
from .. import ModeloWorkReview, build_modelo_work_review, calculate_modelo_revision
from .._work_review import ModeloWorkOriginAnomaly
from ._file_flow_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    M130_CARRY_FORWARD_CASILLA,
    M130_INCOME_CASILLA,
    M130_NET_RESULT_CASILLA,
    T0,
    Repos,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_M130 = ModeloCode("130")
_M130_INCOME_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"


def _persist_work_unit(
    repos: Repos,
    *,
    modelo: ModeloCode = _M130,
    filing_year: int = 2026,
    period_code: str = "1T",
) -> WorkUnit:
    work_repo, _, _, _, _ = repos
    period = Period.from_year_and_code(filing_year, period_code)
    revision_id = (
        bundled_authority()
        .snapshot(
            modelo,
            filing_year=filing_year,
            period=period.registry_token,
        )
        .revision.id
    )
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name="130-2026-1T",
        created_at=T0,
        updated_at=T0,
    )
    work_repo.save(upsert_work_unit(work_repo.load(), unit))
    return unit


def test_review_projects_resolvable_work_without_a_calculation_from_real_storage(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    work_unit = _persist_work_unit(repos)
    authority = bundled_authority()

    review = build_modelo_work_review(
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        authority=authority,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
    )

    assert isinstance(review, ModeloWorkReview)
    assert (
        review.registry_revision_id
        == authority.snapshot(
            str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ).revision.id
    )
    assert review.registry_revision_id == work_unit.revision_id
    assert review.calculation_revision_id is None
    assert review.lifecycle_state is None
    assert review.verification_outcome is None
    assert review.findings == ()
    assert review.blockers == ()
    assert review.casillas
    assert all(row.realised_kind is ModeloValueKind.EMPTY and row.value is None for row in review.casillas)
    computed = next(row for row in review.casillas if row.casilla_id == M130_NET_RESULT_CASILLA)
    assert computed.declared_input_kind is InputKind.COMPUTED
    assert computed.origin_anomaly is ModeloWorkOriginAnomaly.BROKEN_CALCULATION_CHAIN


def test_review_joins_real_persisted_calculation_into_origin_layers(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, bucket_event_repo = repos
    work_unit = _persist_work_unit(repos)
    profile_repository = UserProfileLifecycleRepository(bucket_id=_BUCKET_ID)
    profile = profile_repository.load(_BUCKET_ID)
    profile_repository.save(
        profile.model_copy(
            update={
                "facts": (
                    *profile.facts,
                    UserProfileFact(path="iva.m303_regime_composition", value="general"),
                    UserProfileFact(path="iva.redeme_enrolled", value=False),
                    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                    UserProfileFact(
                        path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                        value=False,
                    ),
                ),
            },
        ),
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values={**DEFAULT_130_BINDING_VALUES, _M130_INCOME_BINDING: Decimal("9000")},
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    )

    review = build_modelo_work_review(
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        authority=bundled_authority(),
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
    )
    rows = {row.casilla_id: row for row in review.casillas}

    assert review.calculation_revision_id == revision.calculation_revision_id
    assert review.lifecycle_state is revision.state
    assert rows[M130_INCOME_CASILLA].realised_kind is ModeloValueKind.LITERAL
    assert rows[M130_INCOME_CASILLA].value == Decimal("10000")
    assert rows[M130_INCOME_CASILLA].origin_anomaly is ModeloWorkOriginAnomaly.OPERATOR_OVERRIDE
    assert rows[M130_INCOME_CASILLA].concrete_bindings
    assert rows[M130_INCOME_CASILLA].concrete_bindings[0].resolved is True
    assert rows[M130_NET_RESULT_CASILLA].realised_kind is ModeloValueKind.COMPUTED
    assert rows[M130_NET_RESULT_CASILLA].value == Decimal("7000")
    assert rows[M130_NET_RESULT_CASILLA].origin_anomaly is None
    assert rows[M130_CARRY_FORWARD_CASILLA].realised_kind is ModeloValueKind.COMPUTED
    carry_forward_formula = rows[M130_CARRY_FORWARD_CASILLA].concrete_formula
    assert carry_forward_formula is not None
    assert "modelo-130-resultados-negativos-anteriores" in carry_forward_formula.operand_refs

    equal_value_revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
        binding_values={**DEFAULT_130_BINDING_VALUES, _M130_INCOME_BINDING: Decimal("10000")},
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        bucket_event_repository=bucket_event_repo,
    )
    equal_value_review = build_modelo_work_review(
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        authority=bundled_authority(),
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
    )
    equal_value_income = next(row for row in equal_value_review.casillas if row.casilla_id == M130_INCOME_CASILLA)
    assert equal_value_review.calculation_revision_id == equal_value_revision.calculation_revision_id
    assert equal_value_income.realised_kind is ModeloValueKind.INHERITED
    assert equal_value_income.origin_anomaly is None
    assert equal_value_income.concrete_bindings[0].resolved is True


def test_review_reads_persisted_date_bindings_without_decimal_reinterpretation(repos: Repos) -> None:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    work_unit = _persist_work_unit(
        repos,
        modelo=ModeloCode("100"),
        filing_year=2025,
        period_code="0A",
    )
    snapshot = bundled_authority().snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    date_binding_id = next(iter(sorted(revision_date_binding_ids(snapshot.revision))))
    binding_overrides = {date_binding_id: "1980-01-01"}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides=binding_overrides,
        casilla_values={},
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        binding_overrides=binding_overrides,
        created_at=T0,
        updated_at=T0,
    )
    calculation_repo.save(upsert_calculation_revision(calculation_repo.load(), revision))
    work_repo.save(
        upsert_work_unit(
            work_repo.load(),
            work_unit.model_copy(update={"current_calculation_revision_id": revision_id}),
        ),
    )

    review = build_modelo_work_review(
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        authority=bundled_authority(),
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
    )

    assert review.calculation_revision_id == revision_id
