"""Contract tests for the strict Modelo Edit Contract V1 model family."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ....core import OutputLanguage, Period
from ....domain.calculations.registry.schema_input_kind import InputKind
from ...operations.registry import OperationSchemaIdentityV1
from .._edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditAdmittedV1,
    ModeloEditBaselineV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditCompatibilityTupleV1,
    ModeloEditDomainRefusalV1,
    ModeloEditExecutionNoEffectV1,
    ModeloEditExecutionUpdatedV1,
    ModeloEditExistingRowAddressV1,
    ModeloEditFindingSeverity,
    ModeloEditFindingV1,
    ModeloEditMutationFamily,
    ModeloEditMutationResultReceiptV1,
    ModeloEditNewRowCorrelationV1,
    ModeloEditParseRequestV1,
    ModeloEditPreflightEvaluatedV1,
    ModeloEditRefusalCode,
    ModeloEditRefusedV1,
    ModeloEditRowIntentKind,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSchemaIdentityV1,
    ModeloEditStaleBaselineRefusalV1,
    ModeloEditSubmissionV1,
    ModeloEditVersionHeader,
    ModeloEditWritableRowGroupSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
    ModeloMutationCapabilityProjectionV1,
    ModeloMutationCapabilityRowV1,
    ModeloRowEditIntentV1,
    ModeloScalarEditIntentV1,
    read_modelo_edit_version_header,
)
from ..workspace_models import ModeloWorkspaceCapabilityDisposition

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_DIGEST = "a" * 64
_WORK_UNIT_ID = "b" * 64
_CALC_REVISION_ID = "c" * 64
_BASELINE_ID = "d" * 64
_RECEIPT_ID = "e" * 64
_BUCKET_EVENT_ID = "f" * 64
_OPERATION_ID = "0" * 64
_REVISION_ID = "2025-y-siguientes"


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


def _scalar_surface_entry() -> ModeloEditWritableScalarSurfaceEntryV1:
    return ModeloEditWritableScalarSurfaceEntryV1(
        casilla_id="casilla-01",
        data_type="money",
        allowed_intents=(ModeloEditScalarIntentKind.SET_TYPED_VALUE, ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE),
    )


def _row_surface_entry(*, reorderable: bool = True) -> ModeloEditWritableRowGroupSurfaceEntryV1:
    return ModeloEditWritableRowGroupSurfaceEntryV1(
        binding_id="binding-01",
        allowed_intents=(
            ModeloEditRowIntentKind.ADD_ROW,
            ModeloEditRowIntentKind.UPDATE_ROW,
            ModeloEditRowIntentKind.DELETE_ROW,
            ModeloEditRowIntentKind.MOVE_ROW,
        ),
        reorderable=reorderable,
    )


def _baseline(*, mutation_family: ModeloEditMutationFamily = ModeloEditMutationFamily.CALCULATE) -> ModeloEditBaselineV1:
    now = datetime.now(UTC)
    return ModeloEditBaselineV1(
        compatibility=_compatibility(),
        bucket_id="edit-bucket",
        modelo="130",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        work_unit_id=_WORK_UNIT_ID,
        work_catalogue_revision=_DIGEST,
        calculation_catalogue_revision=_DIGEST,
        current_calculation_revision_id=None,
        law_selected_revision_id=_REVISION_ID,
        schema_identity=ModeloEditSchemaIdentityV1(
            schema_id="modelo-130-schema", schema_fingerprint=_DIGEST, completeness_manifest_digest=_DIGEST
        ),
        schema_version=1,
        permitted_surface=(_scalar_surface_entry(), _row_surface_entry()),
        permitted_surface_digest=_DIGEST,
        mutation_family=mutation_family,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        baseline_id=_BASELINE_ID,
    )


def test_version_header_reads_only_the_version() -> None:
    """The exact version dispatcher reads the header without touching anything else."""
    header = read_modelo_edit_version_header({"edit_contract_version": 1, "target": object()})
    assert header == ModeloEditVersionHeader(edit_contract_version=1)
    assert read_modelo_edit_version_header({}) is None
    assert read_modelo_edit_version_header({"edit_contract_version": "1"}) is None


def test_compatibility_tuple_requires_review_axis_together() -> None:
    """The REVIEW axis declares its version and schema together or neither."""
    _compatibility()  # both None: constructs cleanly
    with pytest.raises(ValidationError, match="REVIEW axis"):
        ModeloEditCompatibilityTupleV1(
            contract_set_digest=_DIGEST,
            operation_definition_id="modelo.calculate",
            definition_contract_digest=_DIGEST,
            request_schema=_schema_identity(),
            result_schema=_schema_identity(),
            review_projection_contract_version=1,
            review_schema=None,
            workspace_refresh_target_schema=_schema_identity(),
            financial_operand_schema=_schema_identity(),
        )


def test_baseline_is_frozen_and_rejects_unknown_fields() -> None:
    """The baseline is strict, frozen, and rejects extra fields at construction."""
    baseline = _baseline()
    with pytest.raises(ValidationError):
        baseline.baseline_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Extra inputs"):
        ModeloEditBaselineV1(
            **{**baseline.model_dump(mode="python"), "unexpected_field": "x"}  # ty: ignore[invalid-argument-type]  # reason: deliberately malformed kwargs to prove the strict extra="forbid" refusal
        )


def test_baseline_rejects_duplicate_surface_addresses() -> None:
    """Two surface entries addressing the same casilla refuse construction."""
    fields = _baseline().model_dump(mode="python")
    fields["permitted_surface"] = (_scalar_surface_entry(), _scalar_surface_entry())
    with pytest.raises(ValidationError, match="permitted surface must address"):
        ModeloEditBaselineV1(**fields)


def test_baseline_rejects_expiry_at_or_before_issue() -> None:
    """A baseline whose expiry does not strictly follow its issue time refuses."""
    now = datetime.now(UTC)
    fields = _baseline().model_dump(mode="python")
    fields["issued_at"] = now
    fields["expires_at"] = now
    with pytest.raises(ValidationError, match="strictly after"):
        ModeloEditBaselineV1(**fields)


def test_row_group_surface_entry_requires_reorderable_for_move() -> None:
    """MOVE_ROW may not appear in the allowed set unless the group is reorderable."""
    with pytest.raises(ValidationError, match="reorderable"):
        _row_surface_entry(reorderable=False)


def test_scalar_intent_value_shape_matches_kind() -> None:
    """Only SET_TYPED_VALUE may carry a value; the others must omit it."""
    address = ModeloEditScalarAddressV1(casilla_id="casilla-01")
    ModeloScalarEditIntentV1(address=address, kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE, value="120.50")
    with pytest.raises(ValidationError, match="requires a typed value"):
        ModeloScalarEditIntentV1(address=address, kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE, value=None)
    with pytest.raises(ValidationError, match="only SET_TYPED_VALUE"):
        ModeloScalarEditIntentV1(address=address, kind=ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE, value="120.50")


def test_binding_intent_value_shape_matches_kind() -> None:
    """Only SET_OVERRIDE_VALUE may carry a value; REMOVE_OVERRIDE must omit it."""
    address = ModeloEditBindingAddressV1(binding_id="binding-01")
    ModeloBindingEditIntentV1(address=address, kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE, value="120.50")
    with pytest.raises(ValidationError, match="requires a typed value"):
        ModeloBindingEditIntentV1(address=address, kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE, value=None)
    with pytest.raises(ValidationError, match="only SET_OVERRIDE_VALUE"):
        ModeloBindingEditIntentV1(address=address, kind=ModeloEditBindingIntentKind.REMOVE_OVERRIDE, value="120.50")


def test_row_intent_shape_matches_kind() -> None:
    """Add, update, delete and move each demand a distinct address/row shape."""
    new_address = ModeloEditNewRowCorrelationV1(binding_id="binding-01", client_correlation_id="row-1")
    existing_address = ModeloEditExistingRowAddressV1(binding_id="binding-01", row_index=1)
    scalar = ModeloScalarEditIntentV1(
        address=ModeloEditScalarAddressV1(casilla_id="casilla-01"),
        kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
        value="10",
    )

    ModeloRowEditIntentV1(address=new_address, kind=ModeloEditRowIntentKind.ADD_ROW, row=(scalar,))
    with pytest.raises(ValidationError, match="ADD_ROW requires"):
        ModeloRowEditIntentV1(address=existing_address, kind=ModeloEditRowIntentKind.ADD_ROW, row=(scalar,))

    ModeloRowEditIntentV1(address=existing_address, kind=ModeloEditRowIntentKind.UPDATE_ROW, row=(scalar,))
    with pytest.raises(ValidationError, match="UPDATE_ROW requires"):
        ModeloRowEditIntentV1(address=existing_address, kind=ModeloEditRowIntentKind.UPDATE_ROW, row=None)

    ModeloRowEditIntentV1(address=existing_address, kind=ModeloEditRowIntentKind.DELETE_ROW)
    with pytest.raises(ValidationError, match="DELETE_ROW requires"):
        ModeloRowEditIntentV1(address=existing_address, kind=ModeloEditRowIntentKind.DELETE_ROW, row=(scalar,))

    ModeloRowEditIntentV1(address=existing_address, kind=ModeloEditRowIntentKind.MOVE_ROW, move_to_index=2)
    with pytest.raises(ValidationError, match="MOVE_ROW requires"):
        ModeloRowEditIntentV1(address=existing_address, kind=ModeloEditRowIntentKind.MOVE_ROW, move_to_index=None)


def test_submission_rejects_duplicate_addresses_and_mismatched_family() -> None:
    """Duplicate or contradictory address intents and a family mismatch both refuse."""
    baseline = _baseline()
    scalar = ModeloScalarEditIntentV1(
        address=ModeloEditScalarAddressV1(casilla_id="casilla-01"),
        kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
        value="10",
    )
    ModeloEditSubmissionV1(
        baseline=baseline, mutation_family=ModeloEditMutationFamily.CALCULATE, scalar_intents=(scalar,)
    )
    with pytest.raises(ValidationError, match="must not address the same casilla"):
        ModeloEditSubmissionV1(
            baseline=baseline,
            mutation_family=ModeloEditMutationFamily.CALCULATE,
            scalar_intents=(scalar, scalar),
        )
    with pytest.raises(ValidationError, match="must match its baseline"):
        ModeloEditSubmissionV1(
            baseline=baseline,
            mutation_family=ModeloEditMutationFamily.RECALCULATE,
            scalar_intents=(scalar,),
        )


def test_domain_refusal_rejects_the_typed_stale_baseline_code() -> None:
    """A stale-baseline code requires the dedicated compare-and-swap refusal shape."""
    with pytest.raises(ValidationError, match="typed compare-and-swap refusal"):
        ModeloEditDomainRefusalV1(
            code=ModeloEditRefusalCode.STALE_EDIT_BASELINE,
            responsible_owner="modelo.edit",
            reconsideration_condition="retry with a freshly admitted baseline",
        )
    ModeloEditStaleBaselineRefusalV1(
        baseline_id=_BASELINE_ID,
        mismatching_coordinates=("work_catalogue_revision",),
        responsible_owner="modelo.edit",
        reconsideration_condition="retry with a freshly admitted baseline",
    )
    with pytest.raises(ValidationError, match="must be unique"):
        ModeloEditStaleBaselineRefusalV1(
            baseline_id=_BASELINE_ID,
            mismatching_coordinates=("work_catalogue_revision", "work_catalogue_revision"),
            responsible_owner="modelo.edit",
            reconsideration_condition="retry with a freshly admitted baseline",
        )


def test_mutation_capability_row_requires_definition_when_available() -> None:
    """AVAILABLE composes with a registered operation definition, never without one."""
    with pytest.raises(ValidationError, match="requires its registered operation definition"):
        ModeloMutationCapabilityRowV1(
            mutation_id="calculate",
            owning_producer="modelo.calculation",
            revision_id=_REVISION_ID,
            disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        )
    row = ModeloMutationCapabilityRowV1(
        mutation_id="calculate",
        owning_producer="modelo.calculation",
        revision_id=_REVISION_ID,
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        operation_definition_id="modelo.calculate",
    )
    projection = ModeloMutationCapabilityProjectionV1(rows=(row,))
    with pytest.raises(ValidationError, match="unique mutation ids"):
        ModeloMutationCapabilityProjectionV1(rows=(row, row))
    assert projection.rows[0].mutation_id == "calculate"


def test_execution_result_discriminates_on_effect() -> None:
    """The execution result union discriminates strictly on the ``effect`` field."""
    receipt = ModeloEditMutationResultReceiptV1(
        receipt_id=_RECEIPT_ID,
        operation_id=_OPERATION_ID,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        baseline_id=_BASELINE_ID,
        work_unit_id=_WORK_UNIT_ID,
        calculation_revision_id=_CALC_REVISION_ID,
        bucket_event_id=_BUCKET_EVENT_ID,
        committed_at=datetime.now(UTC),
        result_destination="modelo/edit/receipt",
    )
    updated = ModeloEditExecutionUpdatedV1(receipt=receipt)
    assert updated.effect.value == "updated"

    refusal = ModeloEditStaleBaselineRefusalV1(
        baseline_id=_BASELINE_ID,
        mismatching_coordinates=("calculation_catalogue_revision",),
        responsible_owner="modelo.edit",
        reconsideration_condition="retry with a freshly admitted baseline",
    )
    no_effect = ModeloEditExecutionNoEffectV1(refusal=refusal)
    assert no_effect.effect.value == "none"


def test_admission_result_and_parse_request_round_trip_through_json() -> None:
    """Success and refusal arms round-trip through strict JSON without loss."""
    admitted = ModeloEditAdmittedV1(baseline=_baseline())
    assert ModeloEditAdmittedV1.model_validate_json(admitted.model_dump_json()) == admitted

    refused = ModeloEditRefusedV1(
        refusal=ModeloEditDomainRefusalV1(
            code=ModeloEditRefusalCode.TARGET_ABSENT,
            responsible_owner="modelo.edit",
            reconsideration_condition="resupply a valid target",
        )
    )
    assert ModeloEditRefusedV1.model_validate_json(refused.model_dump_json()) == refused

    parse_request = ModeloEditParseRequestV1(
        baseline=_baseline(),
        address=ModeloEditScalarAddressV1(casilla_id="casilla-01"),
        input_kind=InputKind.MANUAL,
        locale=OutputLanguage.ES,
        raw_lexeme="1.234,56",
    )
    assert ModeloEditParseRequestV1.model_validate_json(parse_request.model_dump_json()) == parse_request


def test_preflight_evaluated_findings_reference_the_shared_address_union() -> None:
    """A finding may cite a scalar or row address, or omit one for global scope."""
    finding = ModeloEditFindingV1(
        code="cross_field_conflict",
        severity=ModeloEditFindingSeverity.ERROR,
        address=ModeloEditScalarAddressV1(casilla_id="casilla-01"),
    )
    evaluated = ModeloEditPreflightEvaluatedV1(baseline_id=_BASELINE_ID, findings=(finding,))
    assert evaluated.findings[0].severity is ModeloEditFindingSeverity.ERROR

    global_finding = ModeloEditFindingV1(code="calculation_incomplete", severity=ModeloEditFindingSeverity.WARNING)
    assert global_finding.address is None
