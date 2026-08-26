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
    ModeloEditCompatibilityRefusalV1,
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
    ModeloEditSchemaIdentityV1,
    ModeloEditStaleBaselineRefusalV1,
    ModeloEditSubmissionV1,
    ModeloEditWritableRowGroupSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
    ModeloRowEditIntentV1,
    ModeloScalarEditIntentV1,
)
from .._edit_services import (
    _completeness_manifest_digest,
    _writable_row_group_entries,
    admit_modelo_edit,
    modelo_edit_request_schema_identity,
    modelo_edit_result_schema_identity,
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
        request_schema=modelo_edit_request_schema_identity(),
        result_schema=modelo_edit_result_schema_identity(),
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
    assert not writable_rows, "no modelo 131 manual_input binding is a real row set; none may surface as a row group"
    assert len({e.casilla_id for e in writable_scalars}) == len(writable_scalars)


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


def test_admission_refuses_a_stale_compatibility_tuple() -> None:
    """A schema fingerprint that no longer matches this consumer's own model refuses."""
    work_unit = _work_unit()
    work_catalogue = WorkUnitCatalogue.from_work_units((work_unit,))
    stale_compatibility = _compatibility().model_copy(
        update={
            "request_schema": _compatibility().request_schema.model_copy(
                update={"schema_fingerprint": "f" * 64}
            )
        }
    )
    result = admit_modelo_edit(
        ModeloEditAdmissionRequestV1(target=_target_for(work_unit), mutation_family=ModeloEditMutationFamily.CALCULATE),
        bucket_id=_BUCKET_ID,
        work_catalogue=work_catalogue,
        calculation_catalogue=CalculationRevisionCatalogue(),
        compatibility=stale_compatibility,
    )
    assert isinstance(result, ModeloEditRefusedV1)
    assert isinstance(result.refusal, ModeloEditCompatibilityRefusalV1)
    assert result.refusal.requested_axis == "request_schema"


def test_writable_row_group_entries_surfaces_none_of_the_real_manual_input_bindings() -> None:
    """No modelo 131 manual_input binding is a real row set, so none may surface as one.

    A registry-wide audit found every ``manual_input`` binding declares
    ``aggregation = {op = "copy"}`` (a 1:1 scalar copy) with no row index --
    modelo 131's ninety-seven are static fichero-BOE record-field positions.
    Admitting any of them under ADD_ROW/UPDATE_ROW/DELETE_ROW would let an
    intent address a static field under a fabricated row semantic.
    """
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=_FILING_YEAR, period=_period().registry_token)
    manual_input_bindings = {b.id for b in snapshot.revision.bindings if b.source.value == "manual_input"}
    assert manual_input_bindings, "the fixture must still exercise a real manual_input population"
    entries = _writable_row_group_entries(snapshot.revision)
    assert entries == ()


def test_edit_schema_identity_is_never_confused_with_the_workspace_field_manifest_digest() -> None:
    """The edit contract's completeness digest and the S278 field-manifest digest are independent.

    Both real producers run over the SAME registry revision. Proves three
    things at once: the two digests are genuinely different values (not a
    tautological self-comparison), they now live under distinct field names
    on distinct types (``ModeloEditSchemaIdentityV1.completeness_manifest_digest``
    versus ``ModeloWorkspaceSchemaIdentityV1.field_manifest_digest``), and
    mutating ONLY the registry's completeness manifest moves the completeness
    digest while leaving the S278 field-manifest digest -- computed from the
    unrelated public registry TYPE denominator -- untouched.
    """
    from ..workspace_manifest import generate_modelo_workspace_field_manifest
    from ..workspace_models import ModeloWorkspaceSchemaIdentityV1

    snapshot = bundled_authority().snapshot(_MODELO, filing_year=_FILING_YEAR, period=_period().registry_token)
    revision = snapshot.revision

    completeness_digest = _completeness_manifest_digest(revision.completeness_manifest)
    field_manifest_digest = generate_modelo_workspace_field_manifest(snapshot).manifest_digest
    assert completeness_digest != field_manifest_digest

    edit_identity = ModeloEditSchemaIdentityV1(
        schema_id="modelo-131-cross-producer", schema_fingerprint="a" * 64, completeness_manifest_digest=completeness_digest
    )
    workspace_identity = ModeloWorkspaceSchemaIdentityV1(
        schema_id="modelo-131-cross-producer", schema_fingerprint="a" * 64, field_manifest_digest=field_manifest_digest
    )
    assert not hasattr(edit_identity, "field_manifest_digest")
    assert not hasattr(workspace_identity, "completeness_manifest_digest")

    assert revision.completeness_manifest is not None, "modelo 131 must declare a real completeness manifest"
    mutated_manifest = revision.completeness_manifest.model_copy(
        update={"manual_extraction": True, "manual_extraction_reason": "cross-producer independence test"}
    )
    mutated_completeness_digest = _completeness_manifest_digest(mutated_manifest)
    mutated_revision = revision.model_copy(update={"completeness_manifest": mutated_manifest})
    mutated_snapshot = snapshot.model_copy(update={"revision": mutated_revision})

    assert mutated_completeness_digest != completeness_digest
    assert generate_modelo_workspace_field_manifest(mutated_snapshot).manifest_digest == field_manifest_digest


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

    # No modelo 131 manual_input binding admits a row-group entry (none is a
    # real row set), so ANY row intent -- against any binding id -- refuses as
    # disallowed; the address below names no real binding on purpose.
    bad_submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        row_intents=(
            ModeloRowEditIntentV1(
                address=ModeloEditExistingRowAddressV1(binding_id="a" * 64, row_index=1),
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
