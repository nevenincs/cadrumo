"""Contract tests for the strict, read-only Workspace V1 model family."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

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
from ...registry.closure import RegistryClosureLimb, RegistryClosureOwnerDisposition, RegistryClosureRefusal
from ..work_addressing import ModeloVisibleFilingTarget
from ..workspace_models import (
    ModeloWorkspaceBaselineV1,
    ModeloWorkspaceBoundedFacetV1,
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceCapabilityV1,
    ModeloWorkspaceCasillaReferenceV1,
    ModeloWorkspaceContributorIdentityV1,
    ModeloWorkspaceCountFactValueV1,
    ModeloWorkspaceCursorV1,
    ModeloWorkspaceEvidenceFactV1,
    ModeloWorkspaceEvidenceHorizonV1,
    ModeloWorkspaceFacetName,
    ModeloWorkspaceFlagFactValueV1,
    ModeloWorkspaceLocaleDisposition,
    ModeloWorkspaceLocaleSummaryV1,
    ModeloWorkspaceLocalizedTextV1,
    ModeloWorkspaceMaterializationRecordV1,
    ModeloWorkspaceProjectionV1,
    ModeloWorkspaceProvenanceRecordV1,
    ModeloWorkspaceReadinessV1,
    ModeloWorkspaceRefusalV1,
    ModeloWorkspaceRefusedResultV1,
    ModeloWorkspaceRequestV1,
    ModeloWorkspaceResolvedTargetV1,
    ModeloWorkspaceResultV1,
    ModeloWorkspaceRevisionAssertionDisposition,
    ModeloWorkspaceRevisionAssertionSource,
    ModeloWorkspaceRevisionAssertionV1,
    ModeloWorkspaceRevisionMismatchRefusalV1,
    ModeloWorkspaceScalarMaterializationRecordV1,
    ModeloWorkspaceSchemaClassification,
    ModeloWorkspaceSchemaIdentityV1,
    ModeloWorkspaceSchemaRecordV1,
    ModeloWorkspaceSchemaReferenceV1,
    ModeloWorkspaceStaticInspectionScopeV1,
    ModeloWorkspaceTechnicalLabelV1,
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
        requested_revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            source=ModeloWorkspaceRevisionAssertionSource.REQUESTED,
            disposition=ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT,
            asserted_revision_id=None,
        ),
        stored_revision_assertion=ModeloWorkspaceRevisionAssertionV1(
            source=ModeloWorkspaceRevisionAssertionSource.STORED,
            disposition=ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT,
            asserted_revision_id=None,
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
        contributor_epoch_digest=_DIGEST,
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
        contributor_epoch_digest=baseline.contributor_epoch_digest,
        contributors=contributors,
        facet=ModeloWorkspaceFacetName.SCHEMA,
        disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
        page_size=1,
    )


def _cursor(
    target: ModeloWorkspaceResolvedTargetV1,
    schema_identity: ModeloWorkspaceSchemaIdentityV1,
    baseline: ModeloWorkspaceBaselineV1,
    *,
    facet: ModeloWorkspaceFacetName = ModeloWorkspaceFacetName.SCHEMA,
) -> ModeloWorkspaceCursorV1:
    return ModeloWorkspaceCursorV1(
        baseline=baseline,
        selected_revision_id=target.law_selected_revision_id,
        schema_identity=schema_identity,
        facet=facet,
        contributor_epoch_digest=baseline.contributor_epoch_digest,
        continuation="next-page",
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
            contributor_epoch_digest=baseline.contributor_epoch_digest,
            contributors=contributors,
            facet=ModeloWorkspaceFacetName.SCHEMA,
            disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
            page_size=1,
            has_more=True,
            next_cursor=_cursor(target, schema_identity, baseline),
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
                "kind": "localized",
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
    assert record.constraints is not None
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
    with pytest.raises(ValidationError):
        ModeloWorkspaceCursorV1.model_validate(
            {**_cursor(target, schema_identity, baseline).model_dump(), "continuation": "x" * 257}
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


def test_workspace_revision_assertion_axes_are_required_independent_and_current_only() -> None:
    requested = ModeloWorkspaceRevisionAssertionV1(
        source=ModeloWorkspaceRevisionAssertionSource.REQUESTED,
        disposition=ModeloWorkspaceRevisionAssertionDisposition.MATCHED,
        asserted_revision_id=_REVISION_ID,
    )
    stored = ModeloWorkspaceRevisionAssertionV1(
        source=ModeloWorkspaceRevisionAssertionSource.STORED,
        disposition=ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT,
        asserted_revision_id=None,
    )
    target = ModeloWorkspaceResolvedTargetV1.model_validate(
        {
            **_target().model_dump(),
            "requested_revision_assertion": requested,
            "stored_revision_assertion": stored,
        }
    )

    assert ModeloWorkspaceResolvedTargetV1.model_validate_json(target.model_dump_json()) == target
    with pytest.raises(ValidationError, match="asserted_revision_id"):
        ModeloWorkspaceRevisionAssertionV1.model_validate(
            {
                "source": ModeloWorkspaceRevisionAssertionSource.REQUESTED,
                "disposition": ModeloWorkspaceRevisionAssertionDisposition.MATCHED,
            }
        )
    with pytest.raises(ValidationError, match="asserted_revision_id"):
        ModeloWorkspaceRevisionAssertionV1.model_validate(
            {
                "source": ModeloWorkspaceRevisionAssertionSource.STORED,
                "disposition": ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT,
            }
        )
    with pytest.raises(ValidationError, match="requested source"):
        ModeloWorkspaceResolvedTargetV1.model_validate(
            {
                **target.model_dump(),
                "requested_revision_assertion": stored,
            }
        )
    with pytest.raises(ValidationError):
        ModeloWorkspaceResolvedTargetV1.model_validate(
            {
                **target.model_dump(),
                "revision" + "_assertion": {
                    "source": "requested",
                    "disposition": "not_present",
                },
            }
        )


def test_workspace_revision_mismatch_refusal_preserves_both_axes_and_every_mismatching_source() -> None:
    requested = ModeloWorkspaceRevisionAssertionV1(
        source=ModeloWorkspaceRevisionAssertionSource.REQUESTED,
        disposition=ModeloWorkspaceRevisionAssertionDisposition.MISMATCHED,
        asserted_revision_id="2024-y-siguientes",
    )
    stored = ModeloWorkspaceRevisionAssertionV1(
        source=ModeloWorkspaceRevisionAssertionSource.STORED,
        disposition=ModeloWorkspaceRevisionAssertionDisposition.MISMATCHED,
        asserted_revision_id="2023-y-siguientes",
    )
    selected_target = ModeloWorkspaceResolvedTargetV1.model_validate(
        {
            **_target().model_dump(),
            "requested_revision_assertion": requested,
            "stored_revision_assertion": stored,
        }
    )
    requested_target = ModeloWorkspaceVisibleFilingTargetV1(
        target=ModeloVisibleFilingTarget(
            modelo=selected_target.modelo,
            filing_year=selected_target.filing_year,
            period=selected_target.period,
        )
    )
    refusal = ModeloWorkspaceRevisionMismatchRefusalV1(
        requested_target=requested_target,
        selected_target=selected_target,
        requested_revision_assertion=requested,
        stored_revision_assertion=stored,
        mismatching_sources=(
            ModeloWorkspaceRevisionAssertionSource.REQUESTED,
            ModeloWorkspaceRevisionAssertionSource.STORED,
        ),
        responsible_owner="application.modelo.work_addressing",
        reconsideration_condition="supply assertions that match the selected revision",
    )

    decoded = TypeAdapter(ModeloWorkspaceRefusalV1).validate_json(refusal.model_dump_json())

    assert decoded == refusal
    assert decoded.mismatching_sources == (
        ModeloWorkspaceRevisionAssertionSource.REQUESTED,
        ModeloWorkspaceRevisionAssertionSource.STORED,
    )
    with pytest.raises(ValidationError, match="every and only mismatching source"):
        ModeloWorkspaceRevisionMismatchRefusalV1(
            requested_target=requested_target,
            selected_target=selected_target,
            requested_revision_assertion=requested,
            stored_revision_assertion=stored,
            mismatching_sources=(ModeloWorkspaceRevisionAssertionSource.REQUESTED,),
            responsible_owner="application.modelo.work_addressing",
            reconsideration_condition="supply assertions that match the selected revision",
        )


@pytest.mark.parametrize(
    ("coordinate", "error"),
    (
        ("baseline", "complete facet consistency coordinate"),
        ("contract_version", "cursor baseline must retain the V1 contract version"),
        ("selected_revision_id", "cursor baseline must retain the selected revision"),
        ("schema_identity", "cursor baseline must retain the schema identity and fingerprint"),
        ("facet", "complete facet consistency coordinate"),
        ("contributor_epoch_digest", "cursor baseline must retain the contributor epoch digest"),
    ),
)
def test_workspace_cursor_coordinate_mutations_are_refused_by_the_bounded_facet(coordinate: str, error: str) -> None:
    target = _target()
    schema_identity = _schema_identity()
    baseline = _baseline(target, schema_identity)
    contributors = _contributors()
    cursor = _cursor(target, schema_identity, baseline)
    available = ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1](
        selected_revision_id=target.law_selected_revision_id,
        schema_identity=schema_identity,
        baseline=baseline,
        contributor_epoch_digest=baseline.contributor_epoch_digest,
        contributors=contributors,
        facet=ModeloWorkspaceFacetName.SCHEMA,
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        page_size=1,
        has_more=True,
        next_cursor=cursor,
    )

    assert (
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1].model_validate_json(available.model_dump_json())
        == available
    )

    alternatives = {
        "baseline": baseline.model_copy(update={"token": "b" * 64}),
        "contract_version": 2,
        "selected_revision_id": "2024-y-siguientes",
        "schema_identity": schema_identity.model_copy(update={"schema_fingerprint": "b" * 64}),
        "facet": ModeloWorkspaceFacetName.PROVENANCE,
        "contributor_epoch_digest": "b" * 64,
    }
    altered_cursor = cursor.model_copy(update={coordinate: alternatives[coordinate]})

    assert {
        field
        for field in (
            "baseline",
            "contract_version",
            "selected_revision_id",
            "schema_identity",
            "facet",
            "contributor_epoch_digest",
        )
        if getattr(altered_cursor, field) != getattr(cursor, field)
    } == {coordinate}
    with pytest.raises(ValidationError, match=error):
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1].model_validate(
            {
                **available.model_dump(),
                "next_cursor": altered_cursor,
            }
        )


def test_workspace_cursor_page_state_and_unavailable_cursor_mutations_are_refused() -> None:
    target = _target()
    schema_identity = _schema_identity()
    baseline = _baseline(target, schema_identity)
    contributors = _contributors()
    cursor = _cursor(target, schema_identity, baseline)
    available = ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1](
        selected_revision_id=target.law_selected_revision_id,
        schema_identity=schema_identity,
        baseline=baseline,
        contributor_epoch_digest=baseline.contributor_epoch_digest,
        contributors=contributors,
        facet=ModeloWorkspaceFacetName.SCHEMA,
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        page_size=1,
        has_more=True,
        next_cursor=cursor,
    )

    with pytest.raises(ValidationError, match="has_more must agree with next_cursor"):
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1].model_validate(
            {**available.model_dump(), "next_cursor": None}
        )
    with pytest.raises(ValidationError, match="has_more must agree with next_cursor"):
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1].model_validate(
            {**available.model_dump(), "has_more": False}
        )
    with pytest.raises(ValidationError, match="contributor epoch digest"):
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1].model_validate(
            {**available.model_dump(), "contributor_epoch_digest": "b" * 64}
        )
    with pytest.raises(ValidationError, match="unavailable workspace facets"):
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1].model_validate(
            {
                **available.model_dump(),
                "disposition": ModeloWorkspaceCapabilityDisposition.UNMEASURED,
            }
        )


def test_workspace_models_have_one_public_module_and_no_private_or_package_binding_remnant() -> None:
    public_module = importlib.import_module("cadrumo.application.modelo.workspace_models")
    package = importlib.import_module("cadrumo.application.modelo")
    private_module = ".".join((*public_module.__name__.split(".")[:-1], "_workspace" + "_models"))
    sys.modules.pop(private_module, None)

    assert public_module.ModeloWorkspaceBaselineV1 is ModeloWorkspaceBaselineV1
    assert ModeloWorkspaceBaselineV1.__module__ == public_module.__name__
    assert package.__all__ == ()
    assert not hasattr(package, "ModeloWorkspaceBaselineV1")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(private_module)


def test_workspace_model_docs_and_active_tree_reach_the_public_module_fixed_point() -> None:
    repository = Path(__file__).resolve().parents[5]
    private_module = "_workspace" + "_models"
    public_module = "workspace_models"
    tracked = subprocess.run(
        ("git", "ls-files", "-z", "--", "src", "docs", "dev"),  # noqa: S607
        capture_output=True,
        check=True,
        cwd=repository,
        text=True,
    ).stdout.split(chr(0))
    scanned_paths = tuple(
        sorted(
            path
            for entry in tracked
            if entry.endswith((".py", ".rst", ".toml"))
            # A path git still tracks can be absent from the working tree while
            # a peer's deletion is in flight.  It carries no content to scan,
            # and reading it would fail the gate on someone else's staging
            # state rather than on a remnant.
            if (path := repository / entry).is_file()
        ),
    )
    remnants = tuple(
        path.relative_to(repository)
        for path in scanned_paths
        if path != Path(__file__).resolve() and private_module in path.read_text(encoding="utf-8")
    )

    assert not remnants
    assert (repository / "docs" / "api" / f"cadrumo.application.modelo.{public_module}.rst").is_file()
    assert public_module in (repository / "docs" / "api" / "cadrumo.application.modelo.rst").read_text(encoding="utf-8")


def test_workspace_schema_record_distinguishes_unmeasured_legal_grounding_from_declared_empty() -> None:
    """None means the producer never carries the grounding; () means it does and declares none."""
    base_payload = {
        "reference": {"kind": "casilla", "casilla_id": "0001"},
        "section_path": ("filing", "income"),
        "data_type": "decimal",
        "label": {
            "kind": "localized",
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
    }

    unmeasured = ModeloWorkspaceSchemaRecordV1.model_validate({**base_payload, "legal_refs": None, "constraints": None})
    declared_empty = ModeloWorkspaceSchemaRecordV1.model_validate({**base_payload, "legal_refs": (), "constraints": ()})

    assert unmeasured.legal_refs is None
    assert unmeasured.constraints is None
    assert declared_empty.legal_refs == ()
    assert declared_empty.constraints == ()
    assert unmeasured != declared_empty

    # Round-trip through JSON must preserve the distinction, not collapse it.
    reloaded = ModeloWorkspaceSchemaRecordV1.model_validate_json(unmeasured.model_dump_json())
    assert reloaded.legal_refs is None
    assert reloaded.constraints is None

    # The default stays () for every caller that does not opt into the None-vs-empty distinction.
    defaulted = ModeloWorkspaceSchemaRecordV1.model_validate(base_payload)
    assert defaulted.legal_refs == ()
    assert defaulted.constraints == ()


def test_workspace_schema_record_label_distinguishes_localized_from_technical() -> None:
    """A formula/binding/relation/parameter row's label is honest about never being translated."""
    base_payload = {
        "reference": {"kind": "formula", "formula_id": "modelo-130-rendimiento-neto"},
        "section_path": ("formulas",),
        "data_type": "formula_id",
        "classification": ModeloWorkspaceSchemaClassification.PROJECTED,
        "family_disposition": RegistrySchemaFamilyDisposition.POPULATED,
    }

    technical = ModeloWorkspaceSchemaRecordV1.model_validate(
        {**base_payload, "label": {"kind": "technical", "identifier": "modelo-130-rendimiento-neto"}}
    )
    assert isinstance(technical.label, ModeloWorkspaceTechnicalLabelV1)
    assert technical.label.identifier == "modelo-130-rendimiento-neto"

    localized = ModeloWorkspaceSchemaRecordV1.model_validate(
        {
            **base_payload,
            "reference": {"kind": "casilla", "casilla_id": "0001"},
            "label": {
                "kind": "localized",
                "locale_key": "casilla.0001.label",
                "value": "Base imponible",
                "locale": {
                    "requested_language": OutputLanguage.ES,
                    "resolved_language": OutputLanguage.ES,
                    "disposition": ModeloWorkspaceLocaleDisposition.EXACT,
                    "catalogue_digest": _DIGEST,
                },
            },
        }
    )
    assert isinstance(localized.label, ModeloWorkspaceLocalizedTextV1)
    assert localized.label.value == "Base imponible"

    # The default constructor path (no explicit "kind") still yields "localized",
    # so every existing caller of ModeloWorkspaceLocalizedTextV1 is unaffected.
    default_kind = ModeloWorkspaceLocalizedTextV1(
        locale_key="k",
        value="v",
        locale=ModeloWorkspaceLocaleSummaryV1(
            requested_language=OutputLanguage.ES,
            resolved_language=OutputLanguage.ES,
            disposition=ModeloWorkspaceLocaleDisposition.EXACT,
            catalogue_digest=_DIGEST,
        ),
    )
    assert default_kind.kind == "localized"

    # Round-trip through JSON must preserve the discriminant.
    reloaded_technical = ModeloWorkspaceSchemaRecordV1.model_validate_json(technical.model_dump_json())
    assert isinstance(reloaded_technical.label, ModeloWorkspaceTechnicalLabelV1)


def test_workspace_ledger_issue_subject_distinguishes_transaction_from_period() -> None:
    """A period-level ledger-preflight issue is represented as itself.

    ``LedgerPreflightIssue.transaction_id`` is ``TransactionId | Literal["__period__"]``
    for exactly one non-transaction case (an unsupported period with no date span).
    Collapsing both arms into one required ``TransactionId`` field would either
    drop the period-level issue or pin it to a fabricated transaction id; the
    discriminated ``ModeloWorkspaceLedgerIssueSubjectV1`` union represents each
    case honestly.
    """
    from ...ledger.preflight import LedgerPreflightIssueReason
    from ..workspace_models import (
        ModeloWorkspaceLedgerIssueV1,
        ModeloWorkspaceLedgerPeriodSubjectV1,
        ModeloWorkspaceLedgerTransactionSubjectV1,
    )

    transaction_issue = ModeloWorkspaceLedgerIssueV1.model_validate(
        {
            "subject": {"kind": "transaction", "transaction_id": "e" * 64},
            "reason": LedgerPreflightIssueReason.MISSING_CATEGORY,
            "detail": "missing IVA category",
        }
    )
    assert isinstance(transaction_issue.subject, ModeloWorkspaceLedgerTransactionSubjectV1)
    assert transaction_issue.subject.transaction_id == "e" * 64

    period_issue = ModeloWorkspaceLedgerIssueV1.model_validate(
        {
            "subject": {"kind": "period"},
            "reason": LedgerPreflightIssueReason.UNSUPPORTED_PERIOD,
            "detail": "period has no date span",
        }
    )
    assert isinstance(period_issue.subject, ModeloWorkspaceLedgerPeriodSubjectV1)
    assert transaction_issue.subject != period_issue.subject

    # Round-trip through JSON must preserve the discriminant in both directions.
    reloaded_transaction = ModeloWorkspaceLedgerIssueV1.model_validate_json(transaction_issue.model_dump_json())
    assert isinstance(reloaded_transaction.subject, ModeloWorkspaceLedgerTransactionSubjectV1)
    reloaded_period = ModeloWorkspaceLedgerIssueV1.model_validate_json(period_issue.model_dump_json())
    assert isinstance(reloaded_period.subject, ModeloWorkspaceLedgerPeriodSubjectV1)
