"""Real-registry integration tests for the Modelo Edit Contract V1 services."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import OutputLanguage, Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.modelos import (
    CalculationRevisionCatalogue,
    ModeloCode,
    WorkUnit,
    WorkUnitCatalogue,
    derive_work_unit_id,
)
from ...operations.registry import OperationSchemaIdentityV1
from .._edit_models import (
    ModeloEditAdmissionRequestV1,
    ModeloEditAdmittedV1,
    ModeloEditCompatibilityTupleV1,
    ModeloEditDomainRefusalV1,
    ModeloEditExistingRowAddressV1,
    ModeloEditMutationFamily,
    ModeloEditParsedValueV1,
    ModeloEditParseRequestV1,
    ModeloEditPreflightEvaluatedV1,
    ModeloEditPreflightRequestV1,
    ModeloEditRefusalCode,
    ModeloEditRefusedV1,
    ModeloEditRowIntentKind,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditStaleBaselineRefusalV1,
    ModeloEditSubmissionV1,
    ModeloEditWritableRowGroupSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
    ModeloRowEditIntentV1,
    ModeloScalarEditIntentV1,
)
from .._edit_services import (
    _writable_row_group_entries,
    admit_modelo_edit,
    parse_modelo_edit_value,
    preflight_modelo_edit,
    reconfirm_modelo_edit_baseline,
)
from ..work_addressing import ModeloExactWorkUnitTarget
from ..workspace_models import ModeloWorkspaceExactWorkUnitTargetV1, ModeloWorkspaceTargetV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "edit-services-bucket"
_MODELO = "131"
_FILING_YEAR = 2025
_PERIOD_CODE = "1T"
_DIGEST = "a" * 64


def _schema_identity() -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1(schema_id="modelo.edit.contract", schema_version=1, schema_fingerprint=_DIGEST)


def _compatibility() -> ModeloEditCompatibilityTupleV1:
    return ModeloEditCompatibilityTupleV1(
        contract_set_digest=_DIGEST,
        operation_definition_id="modelo.calculate",
        definition_contract_digest=_DIGEST,
        request_schema=_schema_identity(),
        result_schema=_schema_identity(),
        review_projection_contract_version=None,
        review_schema=None,
        workspace_refresh_target_schema=_schema_identity(),
        financial_operand_schema=_schema_identity(),
    )


def _period() -> Period:
    return Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE)


def _real_revision_id() -> str:
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=_FILING_YEAR, period=_period().registry_token)
    return snapshot.revision.id


def _work_unit(*, current_calculation_revision_id: str | None = None) -> WorkUnit:
    period = _period()
    revision_id = _real_revision_id()
    now = datetime(2026, 1, 10, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=_MODELO, filing_year=_FILING_YEAR, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(_MODELO),
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision_id,
        name=f"{_MODELO}-{_FILING_YEAR}-{period.registry_token}",
        created_at=now,
        updated_at=now,
        current_calculation_revision_id=current_calculation_revision_id,
    )


def _domain_refusal_code(result: ModeloEditRefusedV1) -> ModeloEditRefusalCode:
    assert isinstance(result.refusal, ModeloEditDomainRefusalV1)
    return result.refusal.code


def _target_for(work_unit: WorkUnit) -> ModeloWorkspaceTargetV1:
    return ModeloWorkspaceExactWorkUnitTargetV1(
        target=ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=work_unit.bucket_id)
    )


def _admit(work_unit: WorkUnit) -> ModeloEditAdmittedV1:
    work_catalogue = WorkUnitCatalogue.from_work_units((work_unit,))
    calculation_catalogue = CalculationRevisionCatalogue()
    result = admit_modelo_edit(
        ModeloEditAdmissionRequestV1(target=_target_for(work_unit), mutation_family=ModeloEditMutationFamily.CALCULATE),
        bucket_id=work_unit.bucket_id,
        work_catalogue=work_catalogue,
        calculation_catalogue=calculation_catalogue,
        compatibility=_compatibility(),
    )
    assert isinstance(result, ModeloEditAdmittedV1)
    return result


def test_admission_resolves_a_real_registry_backed_permitted_surface() -> None:
    """Admission against the real bundled registry yields a populated surface."""
    work_unit = _work_unit()
    admitted = _admit(work_unit)
    baseline = admitted.baseline

    assert baseline.work_unit_id == work_unit.work_unit_id
    assert baseline.law_selected_revision_id == work_unit.revision_id
    writable_scalars = [e for e in baseline.permitted_surface if isinstance(e, ModeloEditWritableScalarSurfaceEntryV1)]
    writable_rows = [e for e in baseline.permitted_surface if isinstance(e, ModeloEditWritableRowGroupSurfaceEntryV1)]
    assert writable_scalars, "modelo 131 declares manual casillas the surface must expose as writable"
    assert writable_rows, "modelo 131 declares manual_input bindings the surface must expose as row groups"
    assert len({e.casilla_id for e in writable_scalars}) == len(writable_scalars)
    assert len({e.binding_id for e in writable_rows}) == len(writable_rows)


def test_admission_refuses_an_absent_work_unit() -> None:
    """A target naming no known work unit refuses with TARGET_ABSENT, not an exception."""
    work_catalogue = WorkUnitCatalogue()
    calculation_catalogue = CalculationRevisionCatalogue()
    target = ModeloWorkspaceExactWorkUnitTargetV1(
        target=ModeloExactWorkUnitTarget(work_unit_id="0" * 64, bucket_id=_BUCKET_ID)
    )
    result = admit_modelo_edit(
        ModeloEditAdmissionRequestV1(target=target, mutation_family=ModeloEditMutationFamily.CALCULATE),
        bucket_id=_BUCKET_ID,
        work_catalogue=work_catalogue,
        calculation_catalogue=calculation_catalogue,
        compatibility=_compatibility(),
    )
    assert isinstance(result, ModeloEditRefusedV1)
    assert _domain_refusal_code(result) is ModeloEditRefusalCode.TARGET_ABSENT


def test_writable_row_group_entries_surfaces_manual_input_bindings_directly() -> None:
    """The row-group projection surfaces exactly the manual-input bindings."""
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=_FILING_YEAR, period=_period().registry_token)
    entries = _writable_row_group_entries(snapshot.revision)
    expected_ids = {b.id for b in snapshot.revision.bindings if b.source.value == "manual_input"}
    assert expected_ids
    assert all(isinstance(entry, ModeloEditWritableRowGroupSurfaceEntryV1) for entry in entries)
    row_group_entries = [entry for entry in entries if isinstance(entry, ModeloEditWritableRowGroupSurfaceEntryV1)]
    assert {entry.binding_id for entry in row_group_entries} == expected_ids
    assert all(entry.allowed_intents for entry in row_group_entries)


def test_parse_accepts_dot_and_comma_decimal_for_the_same_money_casilla() -> None:
    """Both dot- and comma-decimal spellings parse to the identical canonical value."""
    admitted = _admit(_work_unit())
    baseline = admitted.baseline
    scalar_entry = next(e for e in baseline.permitted_surface if isinstance(e, ModeloEditWritableScalarSurfaceEntryV1))

    dot_result = parse_modelo_edit_value(
        ModeloEditParseRequestV1(
            baseline=baseline,
            address=ModeloEditScalarAddressV1(casilla_id=scalar_entry.casilla_id),
            input_kind=InputKind.MANUAL,
            locale=OutputLanguage.ES,
            raw_lexeme="1234.56",
        )
    )
    comma_result = parse_modelo_edit_value(
        ModeloEditParseRequestV1(
            baseline=baseline,
            address=ModeloEditScalarAddressV1(casilla_id=scalar_entry.casilla_id),
            input_kind=InputKind.MANUAL,
            locale=OutputLanguage.ES,
            raw_lexeme="1.234,56",
        )
    )
    assert isinstance(dot_result, ModeloEditParsedValueV1)
    assert isinstance(comma_result, ModeloEditParsedValueV1)
    assert dot_result.value == comma_result.value == Decimal("1234.56")


def test_parse_refuses_a_non_writable_casilla_and_a_malformed_lexeme() -> None:
    """A read-only address and an unparseable lexeme both refuse, never raise."""
    admitted = _admit(_work_unit())
    baseline = admitted.baseline
    writable_ids = {
        e.casilla_id for e in baseline.permitted_surface if isinstance(e, ModeloEditWritableScalarSurfaceEntryV1)
    }
    non_writable = next(
        c.id for c in bundled_authority().snapshot(
            _MODELO, filing_year=_FILING_YEAR, period=_period().registry_token
        ).revision.casillas
        if c.id not in writable_ids
    )
    refused = parse_modelo_edit_value(
        ModeloEditParseRequestV1(
            baseline=baseline,
            address=ModeloEditScalarAddressV1(casilla_id=non_writable),
            input_kind=InputKind.MANUAL,
            locale=OutputLanguage.ES,
            raw_lexeme="100",
        )
    )
    assert isinstance(refused, ModeloEditRefusedV1)
    assert _domain_refusal_code(refused) is ModeloEditRefusalCode.DISALLOWED_INTENT

    writable_id = next(iter(writable_ids))
    garbage = parse_modelo_edit_value(
        ModeloEditParseRequestV1(
            baseline=baseline,
            address=ModeloEditScalarAddressV1(casilla_id=writable_id),
            input_kind=InputKind.MANUAL,
            locale=OutputLanguage.ES,
            raw_lexeme="not-a-number",
        )
    )
    assert isinstance(garbage, ModeloEditRefusedV1)
    assert _domain_refusal_code(garbage) is ModeloEditRefusalCode.PARSE_FAILED


def test_preflight_accepts_an_admitted_intent_and_rejects_a_disallowed_one() -> None:
    """Preflight validates every intent's address against the admitted surface."""
    work_unit = _work_unit()
    admitted = _admit(work_unit)
    baseline = admitted.baseline
    scalar_entry = next(e for e in baseline.permitted_surface if isinstance(e, ModeloEditWritableScalarSurfaceEntryV1))
    row_entry = next(e for e in baseline.permitted_surface if isinstance(e, ModeloEditWritableRowGroupSurfaceEntryV1))

    good_submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        scalar_intents=(
            ModeloScalarEditIntentV1(
                address=ModeloEditScalarAddressV1(casilla_id=scalar_entry.casilla_id),
                kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                value="10",
            ),
        ),
    )
    work_catalogue = WorkUnitCatalogue.from_work_units((work_unit,))
    calculation_catalogue = CalculationRevisionCatalogue()
    evaluated = preflight_modelo_edit(
        ModeloEditPreflightRequestV1(submission=good_submission),
        work_catalogue=work_catalogue,
        calculation_catalogue=calculation_catalogue,
    )
    assert isinstance(evaluated, ModeloEditPreflightEvaluatedV1)

    bad_submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        row_intents=(
            ModeloRowEditIntentV1(
                address=ModeloEditExistingRowAddressV1(binding_id=row_entry.binding_id, row_index=1),
                kind=ModeloEditRowIntentKind.MOVE_ROW,
                move_to_index=2,
            ),
        ),
    )
    refused = preflight_modelo_edit(
        ModeloEditPreflightRequestV1(submission=bad_submission),
        work_catalogue=work_catalogue,
        calculation_catalogue=calculation_catalogue,
    )
    assert isinstance(refused, ModeloEditRefusedV1)
    assert _domain_refusal_code(refused) is ModeloEditRefusalCode.DISALLOWED_INTENT


def test_reconfirm_detects_a_real_conflicting_write_between_admission_and_preflight() -> None:
    """A genuine second write to the same work unit is caught, not merely asserted absent.

    This drives an actual conflicting mutation of the catalogue between
    admission and reconfirmation -- the compare-and-swap guard is worthless if
    only ever exercised on an untouched catalogue.
    """
    work_unit = _work_unit()
    admitted = _admit(work_unit)
    baseline = admitted.baseline

    raced_work_unit = work_unit.model_copy(update={"current_calculation_revision_id": "b" * 64})
    raced_catalogue = WorkUnitCatalogue.from_work_units((raced_work_unit,))
    calculation_catalogue = CalculationRevisionCatalogue()

    stale = reconfirm_modelo_edit_baseline(
        baseline, work_catalogue=raced_catalogue, calculation_catalogue=calculation_catalogue
    )
    assert isinstance(stale, ModeloEditStaleBaselineRefusalV1)
    assert "current_calculation_revision_id" in stale.mismatching_coordinates
    assert "work_catalogue_revision" in stale.mismatching_coordinates

    unchanged_catalogue = WorkUnitCatalogue.from_work_units((work_unit,))
    fresh = reconfirm_modelo_edit_baseline(
        baseline, work_catalogue=unchanged_catalogue, calculation_catalogue=calculation_catalogue
    )
    assert fresh is None
