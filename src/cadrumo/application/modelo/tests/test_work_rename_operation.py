"""Proofs for the registered modelo.work.rename operation."""

from __future__ import annotations

import ast
import inspect
import textwrap
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.operations import OperationCancellation, OperationDurability, OperationEffect
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.calculation_revision import CalculationRevisionAmendmentKind
from ...operations.capabilities import (
    OperationBaselinePolicy,
    OperationConflictScope,
    OperationRequestStoragePolicy,
)
from ...operations.models import CredentialFreeOperationRequest
from ..operation_definitions import (
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
    ModeloExportExecutor,
    ModeloExportPublicResultV1,
    ModeloExportRequest,
    ModeloWorkAmendBaseline,
    ModeloWorkAmendExecutor,
    ModeloWorkAmendOverride,
    ModeloWorkAmendRequest,
    ModeloWorkDiscardBaseline,
    ModeloWorkDiscardExecutor,
    ModeloWorkDiscardPublicResultV1,
    ModeloWorkFileApproval,
    ModeloWorkFileExecutor,
    ModeloWorkFilePublicResultV1,
    ModeloWorkFileRequest,
    ModeloWorkRenameExecutor,
    ModeloWorkRenamePublicResultV1,
    ModeloWorkRenameRequest,
    ModeloWorkVerifyExecutor,
    ModeloWorkVerifyPublicResultV1,
    ModeloWorkVerifyRequest,
    build_modelo_export_definition,
    build_modelo_work_amend_definition,
    build_modelo_work_discard_definition,
    build_modelo_work_discard_registration,
    build_modelo_work_file_definition,
    build_modelo_work_rename_definition,
    build_modelo_work_rename_registration,
    build_modelo_work_verify_definition,
    build_modelo_work_verify_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _test_profile_resolver() -> TaxpayerProfile:
    return TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime.GENERAL)


def _definition():
    return build_modelo_work_rename_definition()


def test_the_definition_enrolls_the_declared_lifecycle_subject() -> None:
    """The operation id is the one the lifecycle writer already names."""
    definition = _definition()

    assert definition.definition_id == MODELO_WORK_RENAME_OPERATION_DEFINITION_ID
    assert definition.definition_id == "modelo.work.rename"


def test_a_rename_is_recorded_and_never_resumed() -> None:
    """A rename is durable and interrupts rather than resuming after owner loss."""
    capabilities = _definition().capabilities

    assert capabilities.durability is OperationDurability.RECORDED
    assert capabilities.conflict_scope is OperationConflictScope.DEFINITION_SUBJECT
    assert OperationEffect.UNKNOWN in capabilities.permitted_effects


def test_the_request_is_credential_free_and_journalable() -> None:
    """A rename names a unit and a label, so the request is safe to journal."""
    definition = _definition()

    assert definition.capabilities.request_storage is OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
    assert issubclass(ModeloWorkRenameRequest, CredentialFreeOperationRequest)


def test_the_request_refuses_an_empty_unit_or_name() -> None:
    """A rename with no subject or no label is refused at the boundary."""
    with pytest.raises(ValidationError):
        ModeloWorkRenameRequest(work_unit_id="", new_name="Q1", actor="operator")
    with pytest.raises(ValidationError):
        ModeloWorkRenameRequest(work_unit_id="unit-1", new_name="", actor="operator")


def test_the_public_result_is_a_projection_not_the_stored_record() -> None:
    """The result carries no lifecycle state a consumer could depend on."""
    fields = set(ModeloWorkRenamePublicResultV1.model_fields)

    assert fields == {"result_version", "work_unit_id", "name", "bucket_id"}
    assert "state" not in fields
    assert "updated_at" not in fields


def test_the_executor_delegates_and_recreates_no_lifecycle_policy() -> None:
    """The executor calls the single writer and decides nothing itself.

    This is the whole point of the enrolment: if the supervised path re-derived
    the rules, a lifecycle refusal would depend on which door the operator came
    through.
    """
    source = inspect.getsource(ModeloWorkRenameExecutor)
    tree = ast.parse(textwrap.dedent(source))
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}

    assert "rename_work_unit" in called
    for forbidden in ("WorkUnitCatalogueRepository", "BucketEventHistoryRepository", "upsert_work_unit"):
        assert forbidden not in source, f"the executor reaches past its writer: {forbidden}"
    assert "DESCARTADO" not in source, "discard policy belongs to the writer, not the enrolment"


def test_the_registration_binds_stable_public_schemas() -> None:
    """Request and result each answer to a versioned public schema id."""
    registration = build_modelo_work_rename_registration(_definition())
    schema_ids = {binding.identity.schema_id for binding in registration.schema_bindings}

    assert "modelo.work.rename.request" in schema_ids
    assert "modelo.work.rename.result" in schema_ids


def test_the_definition_module_is_public_and_importable_directly() -> None:
    """A composition root outside this package must be able to import it."""
    module = __import__("cadrumo.application.modelo.operation_definitions", fromlist=["__all__"])
    package = __import__("cadrumo.application.modelo", fromlist=["__name__"])

    assert not Path(module.__file__ or "").name.startswith("_")
    for name in module.__all__:
        assert not hasattr(package, name), f"the modelo package binds {name}"


def _discard_definition():
    return build_modelo_work_discard_definition()


def test_discard_requires_an_exact_approval_baseline() -> None:
    """Destructive work binds approval to a state, not merely to an id."""
    capabilities = _discard_definition().capabilities

    assert capabilities.baseline is OperationBaselinePolicy.EXACT_APPROVAL
    assert set(ModeloWorkDiscardBaseline.model_fields) == {"work_unit_id", "name", "observed_updated_at"}


def test_a_discard_baseline_carries_what_the_operator_actually_saw() -> None:
    """The observed timestamp is what makes a stale approval refusable."""
    baseline = ModeloWorkDiscardBaseline(
        work_unit_id="unit-1",
        name="130 2026 1T",
        observed_updated_at=datetime(2026, 3, 4, 9, 0, tzinfo=UTC),
    )

    assert baseline.observed_updated_at.tzinfo is not None


def test_the_discard_executor_delegates_and_holds_no_lifecycle_rule() -> None:
    """Whether a discarded unit may be discarded again is the writer's rule."""
    source = inspect.getsource(ModeloWorkDiscardExecutor)
    tree = ast.parse(textwrap.dedent(source))
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}

    assert "discard_work_unit" in called
    assert "DESCARTADO" not in source, "the already-discarded refusal belongs to the writer"
    assert "WorkUnitAlreadyDiscardedError" not in source, "the no-effect refusal is the writer's, not the enrolment's"


def test_the_discard_result_reports_the_settled_transition_only() -> None:
    """The public result says what happened, not what the record now holds."""
    fields = set(ModeloWorkDiscardPublicResultV1.model_fields)

    assert fields == {"result_version", "work_unit_id", "bucket_id", "discarded"}
    assert "state" not in fields


def test_the_two_enrolments_are_distinct_registered_subjects() -> None:
    """Rename and discard never collide on one definition id or schema id."""
    rename = build_modelo_work_rename_registration(_definition())
    discard = build_modelo_work_discard_registration(_discard_definition())
    rename_ids = {binding.identity.schema_id for binding in rename.schema_bindings}
    discard_ids = {binding.identity.schema_id for binding in discard.schema_bindings}

    assert _definition().definition_id != _discard_definition().definition_id
    assert not (rename_ids & discard_ids)


def _verify_definition():
    return build_modelo_work_verify_definition(profile_resolver=_test_profile_resolver)


def test_verify_declares_its_progress_phases_and_claims_no_interaction() -> None:
    """Verification reports progress, and claims no interaction it never performs.

    The platform's REVIEW contract means the executor presents a reviewed
    operand and settles on the operator's verdict. This executor runs straight
    through, so declaring REVIEW would promise an interaction that never
    happens and the registry refuses the registration outright.
    """
    definition = _verify_definition()

    assert definition.interaction_kinds == frozenset()
    assert definition.phase_codes == ("modelo.work.verify.gates", "modelo.work.verify.persist")
    assert definition.capabilities.cancellation is OperationCancellation.COOPERATIVE


def test_the_verify_request_never_carries_the_profile_it_is_judged_against() -> None:
    """A replayed request must not verify against a profile that has since changed."""
    fields = set(ModeloWorkVerifyRequest.model_fields)

    assert "calculation_revision_id" in fields
    assert "workflow_profile" not in fields
    assert not any("profile" in name for name in fields)


def test_the_verify_result_reports_counts_not_a_filing_shaped_payload() -> None:
    """The report is the record of truth; the result says outcome and how much."""
    fields = set(ModeloWorkVerifyPublicResultV1.model_fields)

    assert "finding_count" in fields
    assert "missing_required_casilla_count" in fields
    assert "resolved_casilla_ids" not in fields
    assert "findings" not in fields


def test_the_verify_executor_delegates_and_decides_no_completeness() -> None:
    """The authority owns guarded persistence, its events and the verdict."""
    source = inspect.getsource(ModeloWorkVerifyExecutor)
    tree = ast.parse(textwrap.dedent(source))
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}

    assert "verify_modelo_revision" in called
    for forbidden in ("VerificationReportCatalogueRepository", "granted_verificado_completo", "completeness_status"):
        assert forbidden not in source, f"the executor decides what the authority owns: {forbidden}"


def test_every_enrolment_here_targets_a_distinct_subject() -> None:
    """Three enrolments, three definition ids, no shared schema id."""
    definitions = [_definition(), _discard_definition(), _verify_definition()]
    ids = [definition.definition_id for definition in definitions]

    assert len(set(ids)) == 3
    registrations = [
        build_modelo_work_rename_registration(definitions[0]),
        build_modelo_work_discard_registration(definitions[1]),
        build_modelo_work_verify_registration(definitions[2]),
    ]
    schema_ids = [binding.identity.schema_id for reg in registrations for binding in reg.schema_bindings]

    assert len(set(schema_ids)) == len(schema_ids)


def _file_definition():
    return build_modelo_work_file_definition(profile_resolver=_test_profile_resolver)


def test_filing_approval_names_the_verification_that_justified_it() -> None:
    """A revision re-verified since approval is a different fact."""
    fields = set(ModeloWorkFileApproval.model_fields)

    assert fields == {"calculation_revision_id", "verification_report_id"}
    assert _file_definition().capabilities.baseline is OperationBaselinePolicy.EXACT_APPROVAL


def test_filing_records_locally_and_always_requires_a_human_handoff() -> None:
    """Live submission is prohibited, so handoff is contract, not computation."""
    assert ModeloWorkFilePublicResultV1.model_fields["handoff_required"].default is True

    result = ModeloWorkFilePublicResultV1(
        filing_record_id="record-1",
        work_unit_id="unit-1",
        calculation_revision_id="revision-1",
    )

    assert result.handoff_required


def test_the_filing_executor_reaches_no_remote_surface() -> None:
    """Nothing in this enrolment may submit, send, or transmit to AEAT."""
    source = inspect.getsource(ModeloWorkFileExecutor)
    tree = ast.parse(textwrap.dedent(source))
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}

    assert "file_modelo_revision" in called

    # Scan the CODE, not the prose: this executor's docstring says it never
    # submits, and a substring check would fire on that sentence while missing
    # an actual call spelled through an attribute.
    reached = (
        {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        | called
        | {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    )
    for forbidden in ("submit", "httpx", "requests", "post", "presentar", "sede"):
        assert not any(forbidden in name.lower() for name in reached), (
            f"the filing executor reaches a remote surface: {forbidden}"
        )


def test_the_filing_executor_decides_no_precondition_of_its_own() -> None:
    """Verification state and election legality refuse in the authority."""
    source = inspect.getsource(ModeloWorkFileExecutor)

    for forbidden in ("granted_verificado_completo", "VerificationReportCatalogueRepository", "ModeloRecordCatalogue"):
        assert forbidden not in source, f"the executor duplicates a filing precondition: {forbidden}"


def test_the_filing_request_carries_elections_the_operator_declared() -> None:
    """Refund and payment elections are operator choices, journalled with the request."""
    fields = set(ModeloWorkFileRequest.model_fields)

    assert {"approval", "refund_election", "payment_election", "notes"} <= fields


def _export_definition():
    return build_modelo_export_definition(profile_resolver=_test_profile_resolver)


def test_the_export_result_fingerprints_the_artefact_and_carries_no_bytes() -> None:
    """Custody of the artefact is the operator's; the result only proves which bytes."""
    fields = set(ModeloExportPublicResultV1.model_fields)

    assert {"output_path", "byte_size", "file_sha256"} <= fields
    for carrier in ("bytes", "content", "payload", "document"):
        assert not any(carrier in name for name in fields), f"the export result carries material: {carrier}"


def test_the_export_executor_reaches_no_remote_surface() -> None:
    """An exported artefact reaches AEAT only when a human carries it there."""
    source = inspect.getsource(ModeloExportExecutor)
    tree = ast.parse(textwrap.dedent(source))
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    reached = (
        {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        | called
        | {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    )

    assert "export_modelo_revision" in called
    for forbidden in ("submit", "httpx", "requests", "post", "presentar", "upload"):
        assert not any(forbidden in name.lower() for name in reached), (
            f"the export executor reaches a remote surface: {forbidden}"
        )


def test_the_export_stamps_the_identity_this_invocation_recorded() -> None:
    """The artefact carries the acting operator the journalled request names.

    The acting operator is a fact of the invocation, so it belongs on the
    request the journal preserves rather than in a closure captured when the
    definition was composed. Presenter, taxpayer and product identities stay
    off the request: those are resolved from live state at export time.
    """
    fields = set(ModeloExportRequest.model_fields)

    assert {"calculation_revision_id", "output_path", "actor"} <= fields
    for resolved in ("presenter", "taxpayer_identity", "product_software_identity"):
        assert resolved not in fields, f"the request pins an identity that should be resolved: {resolved}"


def _amend_definition():
    return build_modelo_work_amend_definition()


def test_an_amendment_is_bound_to_the_filed_baseline_it_corrects() -> None:
    """An amendment is only meaningful against a specific filed return."""
    definition = _amend_definition()

    assert set(ModeloWorkAmendBaseline.model_fields) == {"from_filing_record_id"}
    assert definition.capabilities.baseline is OperationBaselinePolicy.EXACT_APPROVAL
    assert definition.interaction_kinds == frozenset()


def test_an_amendment_cannot_be_filed_without_a_stated_reason() -> None:
    """Declaring a previously filed figure wrong requires saying why."""
    with pytest.raises(ValidationError):
        ModeloWorkAmendRequest(
            baseline=ModeloWorkAmendBaseline(from_filing_record_id="record-1"),
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            overrides=(ModeloWorkAmendOverride(casilla_id="03", value="10.00"),),
            reason="",
            actor="operator",
        )


def test_an_amendment_must_correct_at_least_one_casilla() -> None:
    """An amendment that changes nothing is not an amendment."""
    with pytest.raises(ValidationError):
        ModeloWorkAmendRequest(
            baseline=ModeloWorkAmendBaseline(from_filing_record_id="record-1"),
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            overrides=(),
            reason="corrected base",
            actor="operator",
        )


def test_an_override_value_survives_the_wire_exactly() -> None:
    """The public schema carries digits, so no float coercion can round it."""
    override = ModeloWorkAmendOverride(casilla_id="03", value="1234.56")

    assert override.as_decimal() == Decimal("1234.56")
    with pytest.raises(ValidationError):
        ModeloWorkAmendOverride(casilla_id="03", value="not-a-number")


def test_the_amend_executor_decides_no_amendment_legality() -> None:
    """Which kinds a modelo admits and whether the baseline is attested is the authority's."""
    source = inspect.getsource(ModeloWorkAmendExecutor)
    tree = ast.parse(textwrap.dedent(source))
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}

    assert "amend_modelo_revision" in called
    for forbidden in ("RECTIFICATIVA", "SUSTITUTIVA", "aeat_attested", "ModeloRecordCatalogue"):
        assert forbidden not in source, f"the executor duplicates amendment legality: {forbidden}"
