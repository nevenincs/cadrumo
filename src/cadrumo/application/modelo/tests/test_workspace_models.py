"""Contract tests for the strict, read-only Workspace V1 model family."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from ....core import (
    BindingSourceKind,
    CalculationSourceLineageRole,
    OutputLanguage,
    Period,
    RegistrySchemaFamilyDisposition,
    RevisionReviewStatus,
)
from ....domain.modelos import CalculationSourceRef
from ...registry import RegistryClosureLimb, RegistryClosureOwnerDisposition, RegistryClosureRefusal
from .._work_addressing import ModeloVisibleFilingTarget
from .._workspace_models import (
    ModeloWorkspaceBaselineV1,
    ModeloWorkspaceBoundedFacetV1,
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceCapabilityV1,
    ModeloWorkspaceCasillaReferenceV1,
    ModeloWorkspaceContributorIdentityV1,
    ModeloWorkspaceCountFactValueV1,
    ModeloWorkspaceEvidenceFactV1,
    ModeloWorkspaceEvidenceHorizonV1,
    ModeloWorkspaceFacetName,
    ModeloWorkspaceFlagFactValueV1,
    ModeloWorkspaceLocaleDisposition,
    ModeloWorkspaceLocaleSummaryV1,
    ModeloWorkspaceMaterializationRecordV1,
    ModeloWorkspaceProjectionV1,
    ModeloWorkspaceProvenanceRecordV1,
    ModeloWorkspaceReadinessV1,
    ModeloWorkspaceRefusedResultV1,
    ModeloWorkspaceRequestV1,
    ModeloWorkspaceResolvedTargetV1,
    ModeloWorkspaceResultV1,
    ModeloWorkspaceRevisionAssertionDisposition,
    ModeloWorkspaceRevisionAssertionV1,
    ModeloWorkspaceScalarMaterializationRecordV1,
    ModeloWorkspaceSchemaClassification,
    ModeloWorkspaceSchemaIdentityV1,
    ModeloWorkspaceSchemaRecordV1,
    ModeloWorkspaceSchemaReferenceV1,
    ModeloWorkspaceStaticInspectionScopeV1,
    ModeloWorkspaceTextFactValueV1,
    ModeloWorkspaceVersionRefusalV1,
    ModeloWorkspaceVisibleFilingTargetV1,
    ModeloWorkspaceWorkReviewFacetV1,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_DIGEST = "a" * 64
_REVISION_ID = "2025-y-siguientes"


def _target(*, revision_id: str = _REVISION_ID) -> ModeloWorkspaceResolvedTargetV1:
    return ModeloWorkspaceResolvedTargetV1(
        bucket_id="workspace-bucket",
        modelo="130",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        law_selected_revision_id=revision_id,
        review_status=RevisionReviewStatus.PENDING_REVIEW,
        revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            disposition=ModeloWorkspaceRevisionAssertionDisposition.NOT_REQUESTED,
        ),
    )


def _schema_identity() -> ModeloWorkspaceSchemaIdentityV1:
    return ModeloWorkspaceSchemaIdentityV1(
        schema_id="modelo-130-schema",
        schema_fingerprint=_DIGEST,
        field_manifest_digest=_DIGEST,
    )


def _baseline(
    target: ModeloWorkspaceResolvedTargetV1,
    schema_identity: ModeloWorkspaceSchemaIdentityV1,
) -> ModeloWorkspaceBaselineV1:
    return ModeloWorkspaceBaselineV1(
        token=_DIGEST,
        contributor_stamp_digest=_DIGEST,
        target=target,
        selected_revision_id=target.law_selected_revision_id,
        schema_identity=schema_identity,
        locale_catalogue_digest=_DIGEST,
    )


def _contributors() -> tuple[ModeloWorkspaceContributorIdentityV1, ...]:
    return (ModeloWorkspaceContributorIdentityV1(owner="registry", producer="registry.inspection"),)


def _schema_facet(
    target: ModeloWorkspaceResolvedTargetV1,
    schema_identity: ModeloWorkspaceSchemaIdentityV1,
    baseline: ModeloWorkspaceBaselineV1,
    contributors: tuple[ModeloWorkspaceContributorIdentityV1, ...],
    *,
    selected_revision_id: str | None = None,
) -> ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1]:
    return ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1](
        selected_revision_id=target.law_selected_revision_id if selected_revision_id is None else selected_revision_id,
        schema_identity=schema_identity,
        baseline=baseline,
        contributors=contributors,
        facet=ModeloWorkspaceFacetName.SCHEMA,
        disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
        page_size=1,
    )


def _capabilities(
    target: ModeloWorkspaceResolvedTargetV1,
) -> tuple[ModeloWorkspaceCapabilityV1, ...]:
    return tuple(
        ModeloWorkspaceCapabilityV1(
            capability=capability,
            disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
            target=target,
            selected_revision_id=target.law_selected_revision_id,
            producer_owner="workspace",
            producer="workspace.capability",
        )
        for capability in ModeloWorkspaceCapabilityName
    )


def _readiness(target: ModeloWorkspaceResolvedTargetV1) -> ModeloWorkspaceReadinessV1:
    return ModeloWorkspaceReadinessV1(
        profile_id="11111111-1111-4111-8111-111111111111",
        modelo=str(target.modelo),
        revision_id=target.law_selected_revision_id,
        filing_year=target.filing_year,
        period=target.period,
        profile_ready=False,
        per_operation_requirements_assessed=False,
        ready=False,
    )


def _closure_limb(target: ModeloWorkspaceResolvedTargetV1) -> RegistryClosureLimb:
    return RegistryClosureLimb(
        modelo=str(target.modelo),
        revision=target.law_selected_revision_id,
        name="temporal_coverage",
        outcome="unmeasured",
        refusal=RegistryClosureRefusal(
            reason="unmeasured",
            detail="the production closure owner has not measured this revision",
            disposition=RegistryClosureOwnerDisposition(
                limb="temporal_coverage",
                state="deferred",
                owner="registry-closure",
                work_item="registry-closure-port",
                reconsideration_condition="the owner publishes a stamped closure result",
            ),
        ),
    )


def _static_projection(
    *,
    target: ModeloWorkspaceResolvedTargetV1 | None = None,
    readiness: ModeloWorkspaceReadinessV1 | None = None,
    registry_closure_limbs: tuple[RegistryClosureLimb, ...] | None = None,
    capabilities: tuple[ModeloWorkspaceCapabilityV1, ...] | None = None,
) -> ModeloWorkspaceProjectionV1:
    resolved_target = _target() if target is None else target
    schema_identity = _schema_identity()
    baseline = _baseline(resolved_target, schema_identity)
    contributors = _contributors()
    return ModeloWorkspaceProjectionV1(
        admission=ModeloWorkspaceStaticInspectionScopeV1(),
        target=resolved_target,
        schema_identity=schema_identity,
        locale=ModeloWorkspaceLocaleSummaryV1(
            requested_language=OutputLanguage.ES,
            resolved_language=OutputLanguage.ES,
            disposition=ModeloWorkspaceLocaleDisposition.EXACT,
            catalogue_digest=_DIGEST,
        ),
        evidence_horizon=ModeloWorkspaceEvidenceHorizonV1(source_refs=(), evidence_digest=_DIGEST),
        family_dispositions=(),
        contributors=contributors,
        baseline=baseline,
        schema_facet=_schema_facet(resolved_target, schema_identity, baseline, contributors),
        work_review=ModeloWorkspaceWorkReviewFacetV1(
            disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
        ),
        readiness=_readiness(resolved_target) if readiness is None else readiness,
        registry_closure_limbs=(
            (_closure_limb(resolved_target),) if registry_closure_limbs is None else registry_closure_limbs
        ),
        capabilities=_capabilities(resolved_target) if capabilities is None else capabilities,
    )


def test_workspace_request_preserves_the_canonical_visible_target_through_a_strict_round_trip() -> None:
    request = ModeloWorkspaceRequestV1.model_validate_json(
        """{
            "contract_version": 1,
            "target": {
                "kind": "visible_filing",
                "target": {"modelo": "130", "filing_year": 2025, "period": {"filing_year": 2025, "code": "1T"}}
            },
            "admission": {"kind": "static_inspection"},
            "output_language": "es"
        }"""
    )

    assert isinstance(request.target, ModeloWorkspaceVisibleFilingTargetV1)
    assert isinstance(request.target.target, ModeloVisibleFilingTarget)
    assert request.target.target.period.filing_year == 2025
    assert request.target.target.period == Period.from_year_and_code(2025, "1T")
    assert request.output_language is OutputLanguage.ES
    assert ModeloWorkspaceRequestV1.model_validate_json(request.model_dump_json()) == request
    with pytest.raises(ValidationError):
        ModeloWorkspaceRequestV1.model_validate_json(
            """{
                "contract_version": 1,
                "target": {"modelo": "130", "filing_year": 2025, "period": "1T", "revision": "not-allowed"},
                "admission": {"kind": "static_inspection"},
                "output_language": "es"
            }"""
        )
    with pytest.raises(ValidationError):
        request.__setattr__("contract_version", 2)


def test_workspace_result_keeps_version_refusal_outside_the_v1_coordinate_arm() -> None:
    result = ModeloWorkspaceRefusedResultV1(
        refusal=ModeloWorkspaceVersionRefusalV1(requested_version=2),
    )

    decoded = TypeAdapter(ModeloWorkspaceResultV1).validate_json(result.model_dump_json())

    assert isinstance(decoded, ModeloWorkspaceRefusedResultV1)
    assert decoded.refusal.requested_version == 2
    assert decoded.refusal.supported_version == 1
    assert "contract_version" not in decoded.model_dump(mode="json")


def test_workspace_bounded_facet_pins_all_root_consistency_coordinates() -> None:
    target = _target()
    schema_identity = _schema_identity()
    baseline = _baseline(target, schema_identity)
    contributors = _contributors()
    unavailable = _schema_facet(target, schema_identity, baseline, contributors)

    assert unavailable.records == ()
    assert unavailable.baseline == baseline
    assert unavailable.contributors == contributors
    with pytest.raises(ValidationError, match="selected revision"):
        _schema_facet(target, schema_identity, baseline, contributors, selected_revision_id="2024-y-siguientes")
    with pytest.raises(ValidationError, match="contract_version"):
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1].model_validate(
            {
                "contract_version": 2,
                "selected_revision_id": target.law_selected_revision_id,
                "schema_identity": schema_identity,
                "baseline": baseline,
                "contributors": contributors,
                "facet": ModeloWorkspaceFacetName.SCHEMA,
                "disposition": ModeloWorkspaceCapabilityDisposition.UNMEASURED,
                "page_size": 1,
            },
        )
    with pytest.raises(ValidationError, match="unavailable workspace facets"):
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1](
            selected_revision_id=target.law_selected_revision_id,
            schema_identity=schema_identity,
            baseline=baseline,
            contributors=contributors,
            facet=ModeloWorkspaceFacetName.SCHEMA,
            disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
            page_size=1,
            has_more=True,
            next_cursor="next",
        )


@pytest.mark.parametrize(
    "calculation_source",
    (
        CalculationSourceRef(
            resolver_id="ledger-iva",
            resolved_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
            contributor_source_kind="external_taxpayer_document",
            contributor_binding_source=None,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref="transaction:ledger-transaction-42",
            parent_source_ref=None,
            fingerprint="payload-fingerprint:transaction-42",
            dependency_treatment="factual_evidence",
        ),
        CalculationSourceRef(
            resolver_id="ledger-iva",
            resolved_binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
            contributor_source_kind="external_taxpayer_document",
            contributor_binding_source=None,
            lineage_role=CalculationSourceLineageRole.CONTRIBUTOR,
            source_ref="transaction:ledger-transaction-43",
            parent_source_ref="transaction:ledger-transaction-42",
            fingerprint="payload-fingerprint:transaction-43",
            dependency_treatment="direct_annual_settlement",
        ),
    ),
)
def test_workspace_provenance_round_trips_the_exact_canonical_calculation_source_ref(
    calculation_source: CalculationSourceRef,
) -> None:
    provenance = ModeloWorkspaceProvenanceRecordV1(
        subject=ModeloWorkspaceCasillaReferenceV1(casilla_id="0001"),
        calculation_source=calculation_source,
    )

    restored = ModeloWorkspaceProvenanceRecordV1.model_validate_json(provenance.model_dump_json())

    assert restored == provenance
    assert restored.calculation_source == calculation_source
    assert restored.calculation_source.source_ref.startswith("transaction:")
    assert restored.calculation_source.fingerprint == calculation_source.fingerprint
    assert restored.calculation_source.contributor_source_kind == "external_taxpayer_document"
    assert restored.calculation_source.contributor_binding_source is None
    assert restored.calculation_source.dependency_treatment == calculation_source.dependency_treatment


@pytest.mark.parametrize(
    "payload",
    (
        {"kind": "continuity", "continuidad_id": "income-base"},
        {"kind": "formula_operand_binding", "formula_id": "formula-1", "binding_id": "binding-1"},
        {"kind": "relation_target_binding", "relation_id": "relation-1", "binding_id": "binding-1"},
        {"kind": "applicability", "applicability_rule_id": "applicability-1"},
        {"kind": "constraint", "casilla_id": "0001"},
        {"kind": "export_exposure", "casilla_id": "0001", "export_field_id": "FIELD_1"},
    ),
)
def test_workspace_schema_reference_preserves_every_required_canonical_identity_branch(
    payload: dict[str, str],
) -> None:
    reference = TypeAdapter(ModeloWorkspaceSchemaReferenceV1).validate_python(payload)

    assert reference.kind == payload["kind"]


def test_workspace_schema_reference_refuses_an_unclassified_formula_operand() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(ModeloWorkspaceSchemaReferenceV1).validate_python(
            {"kind": "formula_operand_unknown", "formula_id": "formula-1"},
        )


def test_workspace_schema_record_has_typed_destinations_for_every_explanatory_relationship() -> None:
    record = ModeloWorkspaceSchemaRecordV1.model_validate(
        {
            "reference": {"kind": "casilla", "casilla_id": "0001"},
            "section_path": ("filing", "income"),
            "data_type": "decimal",
            "label": {
                "locale_key": "casilla.0001.label",
                "value": "Base imponible",
                "locale": {
                    "requested_language": OutputLanguage.ES,
                    "resolved_language": OutputLanguage.ES,
                    "disposition": ModeloWorkspaceLocaleDisposition.EXACT,
                    "catalogue_digest": _DIGEST,
                },
            },
            "classification": ModeloWorkspaceSchemaClassification.PROJECTED,
            "family_disposition": RegistrySchemaFamilyDisposition.POPULATED,
            "continuity": ({"kind": "continuity", "continuidad_id": "income-base"},),
            "applicability": ({"kind": "applicability", "applicability_rule_id": "income-only"},),
            "constraints": ({"kind": "constraint", "casilla_id": "0001"},),
            "formula_operands": (
                {"kind": "formula_operand_binding", "formula_id": "base-formula", "binding_id": "income-base"},
            ),
            "relation_endpoints": (
                {"kind": "relation_target_binding", "relation_id": "income-relation", "binding_id": "income-base"},
            ),
            "export_exposure": ({"kind": "export_exposure", "casilla_id": "0001", "export_field_id": "BASE_01"},),
        }
    )

    assert record.continuity[0].continuidad_id == "income-base"
    assert record.applicability[0].applicability_rule_id == "income-only"
    assert record.constraints[0].casilla_id == "0001"
    assert record.formula_operands[0].kind == "formula_operand_binding"
    assert record.relation_endpoints[0].kind == "relation_target_binding"
    assert record.export_exposure[0].export_field_id == "BASE_01"
    with pytest.raises(ValidationError, match="at most 16 items"):
        ModeloWorkspaceSchemaRecordV1.model_validate({**record.model_dump(), "section_path": ("section",) * 17})


def test_workspace_materialization_is_a_true_discriminated_union() -> None:
    scalar = TypeAdapter(ModeloWorkspaceMaterializationRecordV1).validate_python(
        {"kind": "scalar", "scalar": {"casilla_id": "0001", "value": "safe-value"}}
    )

    assert isinstance(scalar, ModeloWorkspaceScalarMaterializationRecordV1)
    assert scalar.scalar.value == "safe-value"
    with pytest.raises(ValidationError):
        TypeAdapter(ModeloWorkspaceMaterializationRecordV1).validate_python(
            {
                "kind": "scalar",
                "scalar": {"casilla_id": "0001", "value": "safe-value"},
                "repeated_row": {"binding_id": "income-base", "row_index": 1, "values": []},
            }
        )


def test_workspace_safe_fact_values_discriminate_text_counts_and_flags_without_cross_branch_constraints() -> None:
    count = ModeloWorkspaceEvidenceFactV1(
        name="records",
        value=ModeloWorkspaceCountFactValueV1(value=2),
    )
    flag = ModeloWorkspaceEvidenceFactV1(
        name="measured",
        value=ModeloWorkspaceFlagFactValueV1(value=True),
    )
    text = ModeloWorkspaceEvidenceFactV1(
        name="owner",
        value=ModeloWorkspaceTextFactValueV1(value="registry"),
    )

    assert count.value.value == 2
    assert flag.value.value is True
    assert text.value.value == "registry"
    with pytest.raises(ValidationError):
        ModeloWorkspaceEvidenceFactV1.model_validate(
            {"name": "owner", "value": {"kind": "text", "value": "x" * 257}},
        )


def test_workspace_projection_preserves_canonical_readiness_closure_and_capability_coordinates() -> None:
    projection = _static_projection()

    assert projection.readiness is not None
    assert projection.readiness.per_operation_requirements_assessed is False
    assert projection.registry_closure_limbs[0].name == "temporal_coverage"
    assert all(capability.target == projection.target for capability in projection.capabilities)
    mismatched_target = _target(revision_id="2024-y-siguientes")
    mismatched_capabilities = (
        projection.capabilities[0].model_copy(
            update={"target": mismatched_target, "selected_revision_id": mismatched_target.law_selected_revision_id}
        ),
        *projection.capabilities[1:],
    )

    with pytest.raises(ValidationError, match="capabilities must retain"):
        _static_projection(capabilities=mismatched_capabilities)
    with pytest.raises(ValidationError, match="readiness must retain"):
        _static_projection(readiness=_readiness(mismatched_target))
    with pytest.raises(ValidationError, match="registry closure limbs must retain"):
        _static_projection(registry_closure_limbs=(_closure_limb(mismatched_target),))


def test_workspace_rejects_unbounded_localized_text_cursor_and_capability_revision_drift() -> None:
    target = _target()
    schema_identity = _schema_identity()
    baseline = _baseline(target, schema_identity)
    contributors = _contributors()
    with pytest.raises(ValidationError):
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1](
            selected_revision_id=target.law_selected_revision_id,
            schema_identity=schema_identity,
            baseline=baseline,
            contributors=contributors,
            facet=ModeloWorkspaceFacetName.SCHEMA,
            disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
            page_size=1,
            has_more=True,
            next_cursor="x" * 257,
        )
    with pytest.raises(ValidationError, match="selected_revision_id"):
        ModeloWorkspaceCapabilityV1(
            capability=ModeloWorkspaceCapabilityName.SCHEMA_INSPECTION,
            disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
            target=target,
            selected_revision_id="2024-y-siguientes",
            producer_owner="workspace",
            producer="workspace.capability",
        )
