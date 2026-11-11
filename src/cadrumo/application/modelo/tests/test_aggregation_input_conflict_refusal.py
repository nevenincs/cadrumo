"""A calculation input the filer supplied that contradicts its own sources is refused, not failed.

A box typed over a computed figure, a Modelo 210 income type chosen against
the ledger route, or detail rows that disagree with the rows the records give
are all the filer's to put right, so the calculation is refused before anything
is written. A resolver handoff the code itself wired wrongly is no input of the
filer's and stays a failure.

Every one of those refusals serves a door: the declared verdict says whether the
filer decides between the contradicting statements or whether nothing the filer
does inside the product settles it. A lookup of a calculation revision that is
not stored serves the declarations list, unless its raise site chose a sharper
door.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from cadrumo.domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from cadrumo.domain.user_profile.values import create_user_profile_record

from ....core.casilla_id import validated_casilla_id
from ....core.errors.error_codes import ErrorCategory, get_registered_error_code
from ....core.irnr import M210GrossIncomeSourceMode
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.calculation_revision_m303_handoff import M303RegimenSimplificadoAnnualSummaryHandoff
from ....domain.modelos.row_models import Modelo210AgrupacionRentaRow, Modelo349OperadorRow
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.transactions.m210_income_classification import resolve_m210_payer_mode
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ..action_errors import (
    CalculationRevisionNotFoundError,
    ModeloAggregationBindingError,
    ModeloAggregationInputConflictError,
)
from ..calculation_bucket_actions import (
    _merge_bucket_bound_inputs,
    _reject_manual_m210_agrupacion_rows_in_ledger_mode,
    _reject_manual_m210_gross_income_override_in_ledger_mode,
    _validate_m210_official_tipo_renta_selection,
)
from ..calculation_modelo_adjustments import union_detail_rows_by_identity
from ..calculation_source_guards import (
    assert_no_novel_source_kinds,
    m210_gross_source_mode,
    require_m303_regimen_simplificado_annual_summary_arrival_values,
    require_m303_regimen_simplificado_annual_summary_handoff,
)
from ..preconditions import build_modelo_precondition_failure_for_scenario
from ..work_profile import ModeloWorkProfile

pytestmark = [pytest.mark.usefixtures("authority_operation"), pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "34343434-3434-4343-8343-343434343434"


def _assert_door(error: ModeloAggregationBindingError, scenario: str, outcome: NoRecoveryOutcome) -> None:
    """The refusal serves a declared verdict that names no action and says why none exists."""
    failure = error.precondition_failure
    assert failure is not None
    assert failure.subject_leaf_key == "modelo.work.calculate"
    assert failure.scenario_id == f"modelo.work.calculate.{scenario}"
    assert failure.verdict.action is None
    assert failure.verdict.no_recovery_outcome is outcome
    assert error.terminal_precondition_verdict == failure.verdict


def _work_unit(modelo: str, period_code: str) -> WorkUnit:
    snapshot = published_snapshot(modelo, filing_year=filing_year_envelope().horizon, period=period_code)
    year = snapshot.snapshot_ref.modelo_year
    period = Period.from_year_and_code(year, period_code)
    stamp = datetime(year, 1, 1, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=modelo, filing_year=year, period=period, revision_id=snapshot.revision.id
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=year,
        period=period,
        revision_id=snapshot.revision.id,
        name="refusal-door",
        created_at=stamp,
        updated_at=stamp,
    )


def _work_profile(operation: PinnedAuthorityOperation) -> ModeloWorkProfile:
    stamp = datetime(filing_year_envelope().horizon, 1, 1, tzinfo=UTC)
    return ModeloWorkProfile(
        record=create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                *RENTA_UNMARRIED_TAXPAYER_FACTS,
            ),
            created_at=stamp,
            updated_at=stamp,
            context=operation.profile_create_context(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )


def test_an_input_conflict_is_registered_as_a_refusal() -> None:
    """DISCRIMINATING: the supervisor settles a REFUSED registration as refused."""
    assert get_registered_error_code(ModeloAggregationInputConflictError).category is ErrorCategory.REFUSED
    assert issubclass(ModeloAggregationInputConflictError, ModeloAggregationBindingError)


def test_a_figure_typed_over_a_computed_box_is_an_input_conflict() -> None:
    revision = published_snapshot("303", filing_year=filing_year_envelope().horizon, period="1T").revision
    computed = next(casilla.id for casilla in revision.casillas if casilla.input_kind.value == "computed")

    with pytest.raises(ModeloAggregationInputConflictError) as refused:
        _merge_bucket_bound_inputs(revision=revision, casilla_inputs={}, bound_inputs={computed: Decimal("1")})

    assert get_registered_error_code(refused.value).category is ErrorCategory.REFUSED
    _assert_door(refused.value, "bound_inputs.computed_casilla_bound", NoRecoveryOutcome.TERMINAL)
    verdict = refused.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.evidence[0].values["computed_casilla_ids"] == computed


def test_a_miswired_resolver_handoff_stays_a_failure() -> None:
    """ANTI-VACUITY: the base error, raised for wiring the filer never touches, stays ERROR."""
    assert get_registered_error_code(ModeloAggregationBindingError).category is ErrorCategory.ERROR


def test_a_manual_gross_income_over_the_ledger_route_serves_an_operator_decision() -> None:
    with pytest.raises(ModeloAggregationInputConflictError) as refused:
        _reject_manual_m210_gross_income_override_in_ledger_mode(
            mode=M210GrossIncomeSourceMode.LEDGER, casilla_inputs={"rendimientos_integros": Decimal("1")}
        )

    _assert_door(
        refused.value, "m210.gross_income_source.ledger_with_manual_gross_income", NoRecoveryOutcome.OPERATOR_DECISION
    )


def test_the_manual_route_keeps_a_typed_gross_income() -> None:
    """ANTI-VACUITY: the same input under the manual route is admitted."""
    _reject_manual_m210_gross_income_override_in_ledger_mode(
        mode=M210GrossIncomeSourceMode.MANUAL, casilla_inputs={"rendimientos_integros": Decimal("1")}
    )


def test_the_ledger_route_without_an_official_tipo_renta_code_serves_an_operator_decision() -> None:
    with pytest.raises(ModeloAggregationInputConflictError) as refused:
        _validate_m210_official_tipo_renta_selection(
            mode=M210GrossIncomeSourceMode.LEDGER, m210_official_tipo_renta_code=None, text_casilla_inputs={}
        )

    _assert_door(refused.value, "m210.tipo_renta.ledger_selection_missing", NoRecoveryOutcome.OPERATOR_DECISION)


def test_an_unrecognised_official_tipo_renta_code_serves_an_operator_decision() -> None:
    with pytest.raises(ModeloAggregationInputConflictError) as refused:
        _validate_m210_official_tipo_renta_selection(
            mode=M210GrossIncomeSourceMode.MANUAL, m210_official_tipo_renta_code="ZZ", text_casilla_inputs={}
        )

    _assert_door(refused.value, "m210.tipo_renta.official_code_mismatch", NoRecoveryOutcome.OPERATOR_DECISION)


def test_manual_agrupacion_rows_over_the_ledger_route_serve_an_operator_decision() -> None:
    row = Modelo210AgrupacionRentaRow(
        source_id="manual-renta-jan",
        tipo_renta_code="01",
        importe=Decimal("100.00"),
        tipo_gravamen=Decimal("0.24"),
        pagador_mode=resolve_m210_payer_mode(effective_date=date(filing_year_envelope().horizon, 1, 1)),
        pagador_id="ES-PAGADOR-1",
        deriva_de_bien_derecho=False,
    )

    with pytest.raises(ModeloAggregationInputConflictError) as refused:
        _reject_manual_m210_agrupacion_rows_in_ledger_mode(mode=M210GrossIncomeSourceMode.LEDGER, detail_rows=(row,))

    _assert_door(
        refused.value,
        "m210.gross_income_source.ledger_with_manual_agrupacion_rows",
        NoRecoveryOutcome.OPERATOR_DECISION,
    )


def test_the_ledger_route_on_another_modelo_serves_an_operator_decision() -> None:
    work_unit = _work_unit("303", "1T")

    with pytest.raises(ModeloAggregationInputConflictError) as refused:
        m210_gross_source_mode(work_unit, M210GrossIncomeSourceMode.LEDGER)

    _assert_door(refused.value, "m210.gross_income_source.ledger_on_other_modelo", NoRecoveryOutcome.OPERATOR_DECISION)
    assert m210_gross_source_mode(work_unit, None) is None


def test_two_detail_rows_naming_one_declarant_differently_serve_an_operator_decision() -> None:
    def operator_row(importe: Decimal) -> Modelo349OperadorRow:
        return Modelo349OperadorRow(
            codigo_pais="DE",
            nif_comunitario="DE123456789",
            razon_social="Deutschland GmbH",
            clave_operacion="E",
            importe=importe,
        )

    with pytest.raises(ModeloAggregationInputConflictError) as refused:
        union_detail_rows_by_identity(
            resolver_rows=(operator_row(Decimal("1000.00")),), caller_rows=(operator_row(Decimal("2500.00")),)
        )

    _assert_door(refused.value, "detail_rows.identity_conflict", NoRecoveryOutcome.OPERATOR_DECISION)


def test_a_binding_source_no_resolver_handles_serves_a_terminal_door() -> None:
    revision = published_snapshot("303", filing_year=filing_year_envelope().horizon, period="1T").revision
    # The typed provider union is closed, so an unrouted kind only exists as a
    # stand-in exposing the one attribute the gate reads.
    unrouted = SimpleNamespace(id="synthetic-unrouted-binding", source="synthetic_unrouted_source")
    patched = revision.model_copy(update={"bindings": (*revision.bindings, unrouted)})

    with pytest.raises(ModeloAggregationBindingError) as refused:
        assert_no_novel_source_kinds(patched)

    _assert_door(refused.value, "source_bindings.novel_source_kind", NoRecoveryOutcome.TERMINAL)
    assert get_registered_error_code(refused.value).category is ErrorCategory.ERROR


def test_a_handoff_the_revision_does_not_declare_serves_a_terminal_door(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    revision = published_snapshot("303", filing_year=filing_year_envelope().horizon, period="1T").revision
    handoff = M303RegimenSimplificadoAnnualSummaryHandoff.model_construct(values={})

    with pytest.raises(ModeloAggregationBindingError) as refused:
        require_m303_regimen_simplificado_annual_summary_handoff(
            revision=revision, profile=_work_profile(authority_operation), handoff=handoff
        )

    _assert_door(refused.value, "m303_annual_summary.handoff_required", NoRecoveryOutcome.TERMINAL)


def test_an_engine_result_that_diverges_from_its_handoff_serves_a_terminal_door() -> None:
    casilla = validated_casilla_id("iva.anual.cuota-devengada-total")
    handoff = M303RegimenSimplificadoAnnualSummaryHandoff.model_construct(values={casilla: Decimal("5.00")})

    with pytest.raises(ModeloAggregationBindingError) as refused:
        require_m303_regimen_simplificado_annual_summary_arrival_values(
            casilla_values={casilla: Decimal("6.00")}, handoff=handoff
        )

    _assert_door(refused.value, "m303_annual_summary.arrival_mismatch", NoRecoveryOutcome.TERMINAL)
    require_m303_regimen_simplificado_annual_summary_arrival_values(
        casilla_values={casilla: Decimal("5.00")}, handoff=handoff
    )


def test_a_missing_calculation_revision_serves_the_declarations_list() -> None:
    refused = CalculationRevisionNotFoundError(
        translated_message="application.modelo.errors.calculation_revision_not_found",
        context={"calculation_revision_id": "feedfacefeedface"},
    )

    verdict = refused.terminal_precondition_verdict
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.list"
    assert nested_terminal_precondition_verdict(refused) == verdict
    assert refused.precondition_failure is None


def test_a_missing_calculation_revision_keeps_the_door_its_raise_site_chose() -> None:
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.work.verify",
        scenario_id="modelo.work.verify.calculation_revision.work_unit_target_discarded",
        evidence_id="modelo.work.verify.calculation_revision.addressing",
        evidence_values={"work_unit_state": "descartado"},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )
    refused = CalculationRevisionNotFoundError(precondition_failure=failure)

    assert refused.terminal_precondition_verdict == failure.verdict
    assert refused.terminal_precondition_verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
