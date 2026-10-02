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

from ...adapters.outbound.calculation_summary_pdf.summary_container import write_calculation_summary_pdf
from ...adapters.persistence.profile.review_package_signing import (
    build_review_package_signing_keypair_capability,
)
from ...application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from ...application.modelo.export_projection import ModeloExportPublicResultV3
from ...application.modelo.filing_projection import ModeloFilingRecordSnapshot
from ...application.modelo.lifecycle_advisories import ModeloLifecycleAdvisories
from ...application.modelo.operation_definitions import (
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
    ModeloExportExecutor,
    ModeloExportRequest,
    ModeloWorkAmendBaseline,
    ModeloWorkAmendExecutor,
    ModeloWorkAmendOverride,
    ModeloWorkAmendRequest,
    ModeloWorkDiscardBaseline,
    ModeloWorkDiscardExecutor,
    ModeloWorkDiscardPublicResultV2,
    ModeloWorkFileApproval,
    ModeloWorkFileExecutor,
    ModeloWorkFilePublicResultV2,
    ModeloWorkFileRequest,
    ModeloWorkRenameExecutor,
    ModeloWorkRenamePublicResultV2,
    ModeloWorkRenameRequest,
    ModeloWorkVerifyExecutor,
    ModeloWorkVerifyPublicResultV2,
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
from ...application.modelo.operator_inputs import ModeloExportOperatorInput
from ...application.modelo.tests.operator_scope_fakes import build_inward_operator_scope_ports_for_active_route
from ...application.modelo.verification_preconditions import ModeloVerificationResult
from ...application.modelo.verification_projection import ModeloVerificationSnapshot
from ...application.operations.capabilities import (
    OperationBaselinePolicy,
    OperationConflictScope,
    OperationRequestStoragePolicy,
)
from ...application.operations.models import CredentialFreeOperationRequest
from ...core.operations import OperationCancellation, OperationDurability, OperationEffect
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.deadlines.models import IVARegime, TaxpayerProfile
from ...domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from ...domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    derive_filing_record_id,
)
from ...domain.modelos.verification_report import (
    VerificationCompletenessStatus,
    VerificationReport,
    derive_verification_report_id,
)
from ..adapter_composition import (
    build_active_work_lifecycle_ports,
    build_amendment_action_ports,
    build_filing_action_ports,
    build_modelo_export_ports,
    build_verification_repository_bundle,
)

_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports_for_active_route()
_CERTIFICATE_SECRET_BACKEND_FACTORY = InMemoryCertificateSecretBackendFactory()

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _test_profile_resolver(operation: PinnedAuthorityOperation) -> TaxpayerProfile:
    del operation
    return TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime("GENERAL"))


def _definition():
    return build_modelo_work_rename_definition(work_lifecycle_ports_factory=build_active_work_lifecycle_ports)


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
        ModeloWorkRenameRequest(
            work_unit_id="",
            new_name="Q1",
            actor="operator",
            observed_name="Q1",
            observed_updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    with pytest.raises(ValidationError):
        ModeloWorkRenameRequest(
            work_unit_id="a" * 64,
            new_name="",
            actor="operator",
            observed_name="Q1",
            observed_updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_the_public_result_is_a_projection_not_the_stored_record() -> None:
    """The result carries a validated committed snapshot under its versioned schema."""
    fields = set(ModeloWorkRenamePublicResultV2.model_fields)

    assert fields == {"result_version", "work_unit_id", "name", "bucket_id", "unit"}
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

    assert "rename_work_unit" in {
        argument.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "to_thread"
        for argument in node.args[:1]
        if isinstance(argument, ast.Name)
    }
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
    definition_path = Path(inspect.getfile(build_modelo_work_rename_registration))
    definition_tree = ast.parse(definition_path.read_text(encoding="utf-8"))
    definition_all = next(
        node.value
        for node in definition_tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
    )
    exported_names = set(ast.literal_eval(definition_all))

    package_path = definition_path.with_name("__init__.py")
    package_tree = ast.parse(package_path.read_text(encoding="utf-8"))
    package_binding_names: set[str] = set()
    for node in package_tree.body:
        if isinstance(node, ast.Import):
            package_binding_names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            package_binding_names.update(alias.asname or alias.name for alias in node.names if alias.name != "*")
        elif isinstance(node, ast.Assign):
            package_binding_names.update(
                target.id for target in node.targets if isinstance(target, ast.Name) and target.id != "__all__"
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id != "__all__":
            package_binding_names.add(node.target.id)
        elif isinstance(node, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef)):
            package_binding_names.add(node.name)

    assert not definition_path.name.startswith("_")
    assert not exported_names.intersection(package_binding_names)


def _discard_definition():
    return build_modelo_work_discard_definition(work_lifecycle_ports_factory=build_active_work_lifecycle_ports)


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

    assert "discard_work_unit" in {
        argument.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "to_thread"
        for argument in node.args[:1]
        if isinstance(argument, ast.Name)
    }
    assert "DESCARTADO" not in source, "the already-discarded refusal belongs to the writer"
    assert "WorkUnitAlreadyDiscardedError" not in source, "the no-effect refusal is the writer's, not the enrolment's"


def test_the_discard_result_reports_the_settled_transition_only() -> None:
    """The public result retains the writer-returned unit, never a later reread."""
    fields = set(ModeloWorkDiscardPublicResultV2.model_fields)

    assert fields == {"result_version", "work_unit_id", "bucket_id", "discarded", "unit"}
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
    return build_modelo_work_verify_definition(
        certificate_secret_backend_factory=_CERTIFICATE_SECRET_BACKEND_FACTORY,
        profile_resolver=_test_profile_resolver,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        verification_repository_bundle_factory=build_verification_repository_bundle,
    )


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


def test_the_verify_result_round_trips_the_exact_report_and_refuses_false_summary() -> None:
    """A public summary may not contradict its actual persisted report."""
    revision_id = "a" * 64
    report_id = derive_verification_report_id(
        calculation_revision_id=revision_id,
        completeness_status=VerificationCompletenessStatus.COMPLETE,
        findings=(),
        verified_by="operator",
    )
    report = VerificationReport(
        verification_report_id=report_id,
        calculation_revision_id=revision_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303", revision_id="2026-y-siguientes", modelo_year=2026, period="1T"
        ),
        completeness_status=VerificationCompletenessStatus.COMPLETE,
        findings=(),
        run_at=datetime(2026, 4, 1, tzinfo=UTC),
        verified_by="operator",
        granted_verificado_completo=True,
    )
    result = ModeloWorkVerifyPublicResultV2(
        verification=ModeloVerificationSnapshot.from_verification(
            ModeloVerificationResult(report=report, published=True, finding_preconditions=())
        ),
        advisories=ModeloLifecycleAdvisories(
            work_unit_id="b" * 64,
            calculation_revision_id=revision_id,
            modelo="303",
            filing_year=2026,
            period="1T",
        ),
        verification_report_id=report_id,
        calculation_revision_id=revision_id,
        completeness_status="complete",
        granted_verificado_completo=True,
        finding_count=0,
        missing_required_casilla_count=0,
    )
    assert ModeloWorkVerifyPublicResultV2.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError, match="verification summary"):
        ModeloWorkVerifyPublicResultV2.model_validate(result.model_dump(mode="python") | {"finding_count": 1})


def test_the_verify_executor_delegates_and_decides_no_completeness() -> None:
    """The authority owns guarded persistence, its events and the verdict."""
    source = inspect.getsource(ModeloWorkVerifyExecutor)
    tree = ast.parse(textwrap.dedent(source))
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}

    assert "verify_modelo_revision_with_preconditions" in called
    for forbidden in ("VerificationReportCatalogueRepository", "VerificationCompletenessStatus.COMPLETE"):
        assert forbidden not in source, f"the executor decides what the authority owns: {forbidden}"
    assert "report.granted_verificado_completo" in source
    assert "report.completeness_status.value" in source


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
    return build_modelo_work_file_definition(
        certificate_secret_backend_factory=_CERTIFICATE_SECRET_BACKEND_FACTORY,
        filing_action_ports_factory=build_filing_action_ports,
        profile_resolver=_test_profile_resolver,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )


def test_filing_approval_names_the_verification_that_justified_it() -> None:
    """A revision re-verified since approval is a different fact."""
    fields = set(ModeloWorkFileApproval.model_fields)

    assert fields == {"calculation_revision_id", "verification_report_id"}
    assert _file_definition().capabilities.baseline is OperationBaselinePolicy.EXACT_APPROVAL


def test_filing_records_locally_and_always_requires_a_human_handoff() -> None:
    """The public V2 receipt round-trips and cannot contradict its record."""
    work_unit_id = "b" * 64
    revision_id = "a" * 64
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id, calculation_revision_id=revision_id, filed_by="operator"
    )
    record = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id="91fb7268-c9d4-4309-879c-d44fa7970f9d",
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        filed_at=datetime(2026, 4, 1, tzinfo=UTC),
        filed_by="operator",
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    result = ModeloWorkFilePublicResultV2(
        record=ModeloFilingRecordSnapshot.from_record(record),
        advisories=ModeloLifecycleAdvisories(
            work_unit_id=work_unit_id,
            calculation_revision_id=revision_id,
            modelo="303",
            filing_year=2026,
            period="1T",
        ),
        published=True,
        filing_record_id=filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
    )
    assert ModeloWorkFilePublicResultV2.model_validate_json(result.model_dump_json()) == result
    assert result.handoff_required is True
    with pytest.raises(ValidationError, match="filing summary"):
        ModeloWorkFilePublicResultV2.model_validate(result.model_dump() | {"calculation_revision_id": "c" * 64})


def test_the_filing_executor_reaches_no_remote_surface() -> None:
    """Nothing in this enrolment may submit, send, or transmit to AEAT."""
    source = inspect.getsource(ModeloWorkFileExecutor)
    tree = ast.parse(textwrap.dedent(source))
    # Names, not only direct calls: the authority runs off the event loop
    # through ``functools.partial``, which references it without calling it.
    called = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

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
    return build_modelo_export_definition(
        export_ports_factory=build_modelo_export_ports,
        signing_keypair_capability_factory=build_review_package_signing_keypair_capability,
        calculation_summary_pdf_writer=write_calculation_summary_pdf,
        profile_resolver=_test_profile_resolver,
    )


def test_the_export_result_fingerprints_the_artefact_and_carries_no_bytes() -> None:
    """Custody of the artefact is the operator's; the result only proves which bytes."""
    fields = set(ModeloExportPublicResultV3.model_fields)

    assert {"result_version", "output_path", "byte_size", "file_sha256", "handoff_required"} <= fields
    for carrier in ("bytes", "content", "payload", "document"):
        assert not any(carrier in name for name in fields), f"the export result carries material: {carrier}"


def test_export_request_refuses_a_relative_output_path() -> None:
    """The requesting frontend must resolve its destination before submission."""
    with pytest.raises(ValidationError, match="export output path must be resolved by the requesting frontend"):
        ModeloExportRequest.model_validate(
            {
                "calculation_revision_id": "revision-1",
                "output_path": "reports/return.txt",
                "actor": "operator:test",
            },
            strict=True,
        )


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


@pytest.mark.parametrize("election", ["refund_election", "payment_election", "prior_domiciliation_election"])
def test_the_export_request_accepts_each_election_the_command_line_accepts(election: str) -> None:
    """One revision must export as the same declaration type whichever surface asked.

    The operation once took no election at all, so a Modelo 303 export
    through it failed where the command line, supplying its defaults,
    reached the export gates.
    """
    operation_field = ModeloExportRequest.model_fields[election]
    command_line_field = ModeloExportOperatorInput.model_fields[election]

    assert operation_field.annotation is command_line_field.annotation
    assert operation_field.default is command_line_field.default


def test_the_export_executor_hands_every_election_to_the_export_command() -> None:
    """An election the request carries but the executor drops would reach the export as its default.

    Read over the whole executor rather than its entry method: the elections
    shape the fichero-BOE's declaration type, so the command they thread into is
    built in the arm that publishes that artefact.
    """
    source = textwrap.dedent(inspect.getsource(ModeloExportExecutor))
    [command] = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ModeloExportCommand"
    ]
    threaded = {
        keyword.arg
        for keyword in command.keywords
        if isinstance(keyword.value, ast.Attribute) and keyword.value.attr == keyword.arg
    }

    assert {"refund_election", "payment_election", "prior_domiciliation_election"} <= threaded


def _amend_definition():
    return build_modelo_work_amend_definition(amendment_action_ports_factory=build_amendment_action_ports)


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
