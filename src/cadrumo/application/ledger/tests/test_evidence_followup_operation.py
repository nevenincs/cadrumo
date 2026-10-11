"""All-period access and receipt-bound public contracts for evidence follow-up reads."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import cast, get_args
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....application.ledger.attachment_review import AttachmentReviewItem
from ....application.ledger.confirmation_gate import confirmation_blockers
from ....application.ledger.consent_withdrawal import ConsentedDispatch
from ....application.ledger.evidence_followup_contracts import (
    DRAFT_TEXT_FIELDS_WITHHELD_FROM_AGENTS,
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    AttachmentStoreFactory,
    CloudDerivedArtefactProjection,
    ConsentedDispatchProjection,
    ConsentWithdrawalSurveyProjection,
    EvidenceConsentEntriesFactory,
    EvidenceReviewQueueRowProjection,
    LedgerEvidenceAttachmentQueueExecutionResult,
    LedgerEvidenceAttachmentQueueProjection,
    LedgerEvidenceAttachmentQueueRequest,
    LedgerEvidenceAttachmentViewExecutionResult,
    LedgerEvidenceAttachmentViewProjection,
    LedgerEvidenceAttachmentViewRequest,
    LedgerEvidenceConsentListExecutionResult,
    LedgerEvidenceConsentListProjection,
    LedgerEvidenceConsentListRequest,
    LedgerEvidenceFollowupOperationPorts,
    LedgerEvidenceReviewListExecutionResult,
    LedgerEvidenceReviewListProjection,
    LedgerEvidenceReviewListRequest,
    LedgerEvidenceReviewSummaryExecutionResult,
    LedgerEvidenceReviewSummaryProjection,
    LedgerEvidenceReviewViewExecutionResult,
    LedgerEvidenceReviewViewProjection,
    LedgerEvidenceReviewViewRequest,
)
from ....application.ledger.evidence_followup_registration import (
    build_ledger_evidence_followup_definitions,
    build_ledger_evidence_followup_registrations,
    build_ledger_evidence_review_summary_definition,
    build_ledger_evidence_review_summary_registration,
)
from ....application.ledger.evidence_followup_registration import (
    project_attachment_queue_result as _project_attachment_queue,
)
from ....application.ledger.evidence_followup_registration import (
    project_attachment_view_result as _project_attachment_view,
)
from ....application.ledger.evidence_followup_registration import (
    project_consent_list_result as _project_consent_list,
)
from ....application.ledger.evidence_followup_registration import (
    project_review_list_result as _project_review_list,
)
from ....application.ledger.evidence_followup_registration import (
    project_review_summary_result as _project_review_summary,
)
from ....application.ledger.evidence_followup_registration import (
    project_review_view_result as _project_review_view,
)
from ....application.ledger.extraction_draft_repository import ExtractionDraftRepositoryFactory
from ....application.ledger.invoice_draft_records import (
    DraftDiscrepancyFinding,
    FieldAmbiguityCandidate,
    FieldProvenance,
    InvoiceDraft,
    InvoiceDraftLine,
)
from ....application.ledger.invoice_evidence_operation_dtos import (
    ConfirmationBlockerProjectionV1,
    InvoiceDraftProjectionV1,
)
from ....application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ....application.operations.models import OperationId, OperationIdentity, OperationRequest, OperationTerminalReceipt
from ....application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationRegistry,
)
from ....application.user_profile.access_contracts import (
    AccessAction,
    Availability,
    DisclosureCategory,
)
from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ....core.config import Settings, load_settings
from ....core.draft_discrepancy import DraftDiscrepancyKind
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.time.clock import now
from ....domain.attachments.enums import AttachmentSource

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_ATTACHMENT_ID = "a" * 64
_EVIDENCE_REFERENCE = "evidence-followup-reference"
_DRIVE_FILE_ID = "1AbcDEfgHIjkLMnoPQRstuVWxyz12345"
_VALID_RECORDED_AT = datetime(2026, 10, 3, 12, 30, tzinfo=UTC)
_NAIVE_RECORDED_AT = datetime(2026, 10, 3, 12, 30)
_OFFSET_RECORDED_AT = datetime(2026, 10, 3, 14, 30, tzinfo=timezone(timedelta(hours=2)))

_DEFINITION_IDS = (
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
)


def _consented_dispatch_projection(instant: datetime) -> BaseModel:
    return ConsentedDispatchProjection(
        profile_bucket_id=str(_PROFILE),
        evidence_content_address="a" * 64,
        provider="fixture-provider",
        model="fixture-model",
        surface="evidence-extraction",
        recorded_at=instant,
    )


def _cloud_derived_artefact_projection(instant: datetime) -> BaseModel:
    return CloudDerivedArtefactProjection(
        evidence_reference=_EVIDENCE_REFERENCE,
        provenance_stamp="fixture-provenance",
        drafted_at=instant,
    )


def _evidence_review_queue_row_projection(instant: datetime) -> BaseModel:
    return EvidenceReviewQueueRowProjection(
        evidence_reference=_EVIDENCE_REFERENCE,
        extractor="fixture-reader",
        drafted_at=instant,
        blocking_count=0,
        advisory_count=0,
    )


def _ledger_evidence_review_view_projection(instant: datetime) -> BaseModel:
    return LedgerEvidenceReviewViewProjection(
        profile_id=_PROFILE,
        evidence_reference=_EVIDENCE_REFERENCE,
        extractor="fixture-reader",
        drafted_at=instant,
        draft=InvoiceDraftProjectionV1.from_draft(InvoiceDraft()),
    )


_UTC_INSTANT_PROJECTION_CASES: tuple[tuple[str, str, Callable[[datetime], BaseModel]], ...] = (
    ("consented-dispatch", "recorded_at", _consented_dispatch_projection),
    ("cloud-derived-artefact", "drafted_at", _cloud_derived_artefact_projection),
    ("review-queue-row", "drafted_at", _evidence_review_queue_row_projection),
    ("review-view", "drafted_at", _ledger_evidence_review_view_projection),
)


@pytest.mark.parametrize(
    ("_case_name", "field_name", "build_projection"),
    _UTC_INSTANT_PROJECTION_CASES,
    ids=tuple(case[0] for case in _UTC_INSTANT_PROJECTION_CASES),
)
def test_evidence_followup_instants_are_required_utc_datetime_json_fields(
    _case_name: str,
    field_name: str,
    build_projection: Callable[[datetime], BaseModel],
) -> None:
    projection = build_projection(_VALID_RECORDED_AT)
    projection_type = type(projection)
    value = getattr(projection, field_name)

    assert value is _VALID_RECORDED_AT
    assert value == _VALID_RECORDED_AT
    assert value.utcoffset() == timedelta(0)
    assert projection_type.model_fields[field_name].is_required()
    schema = projection_type.model_json_schema()
    assert field_name in schema["required"]
    assert schema["properties"][field_name]["format"] == "date-time"

    restored = projection_type.model_validate_json(projection.model_dump_json())
    assert getattr(restored, field_name) == _VALID_RECORDED_AT

    missing_value = projection.model_dump()
    del missing_value[field_name]
    with pytest.raises(ValidationError) as error:
        projection_type.model_validate(missing_value)
    assert error.value.errors()[0]["loc"] == (field_name,)
    assert error.value.errors()[0]["type"] == "missing"


@pytest.mark.parametrize(
    ("_case_name", "field_name", "build_projection"),
    _UTC_INSTANT_PROJECTION_CASES,
    ids=tuple(case[0] for case in _UTC_INSTANT_PROJECTION_CASES),
)
@pytest.mark.parametrize(
    "instant",
    (
        pytest.param(_NAIVE_RECORDED_AT, id="naive"),
        pytest.param(_OFFSET_RECORDED_AT, id="nonzero-offset"),
    ),
)
def test_evidence_followup_instants_reject_naive_and_non_utc_values(
    _case_name: str,
    field_name: str,
    build_projection: Callable[[datetime], BaseModel],
    instant: datetime,
) -> None:
    with pytest.raises(ValidationError) as error:
        build_projection(instant)
    assert error.value.errors()[0]["loc"] == (field_name,)
    assert error.value.errors()[0]["type"] == "value_error"


def _unused_attachment_store(bucket_id: str, /):
    raise AssertionError(bucket_id)


def _unused_draft_store(*, bucket_id: str, settings: Settings):
    raise AssertionError((bucket_id, settings))


def _unused_consent_entries(*, bucket_id: str) -> tuple[ConsentedDispatch, ...]:
    raise AssertionError(bucket_id)


def _unopened_ports() -> LedgerEvidenceFollowupOperationPorts:
    return LedgerEvidenceFollowupOperationPorts(
        settings=load_settings(),
        attachment_store_factory=cast(AttachmentStoreFactory, _unused_attachment_store),
        extraction_draft_repository_factory=cast(ExtractionDraftRepositoryFactory, _unused_draft_store),
        consent_entries_factory=cast(EvidenceConsentEntriesFactory, _unused_consent_entries),
    )


def _registry() -> OperationRegistry:
    definitions = build_ledger_evidence_followup_definitions(_unopened_ports())
    registrations = build_ledger_evidence_followup_registrations(definitions)
    return OperationRegistry(definitions=definitions, public_registrations=registrations)


def _summary_registry() -> OperationRegistry:
    definition = build_ledger_evidence_review_summary_definition(_unopened_ports())
    registration = build_ledger_evidence_review_summary_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def _request(definition_id: str, *, subject_profile_id: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    payload: BaseModel
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID:
        payload = LedgerEvidenceAttachmentQueueRequest(profile_id=_PROFILE)
    elif definition_id == LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID:
        payload = LedgerEvidenceAttachmentViewRequest(profile_id=_PROFILE, attachment_id=_ATTACHMENT_ID)
    elif definition_id == LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID:
        payload = LedgerEvidenceConsentListRequest(profile_id=_PROFILE)
    elif definition_id == LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID:
        payload = LedgerEvidenceReviewListRequest(profile_id=_PROFILE)
    elif definition_id == LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID:
        payload = LedgerEvidenceReviewViewRequest(profile_id=_PROFILE, evidence_reference=_EVIDENCE_REFERENCE)
    else:
        raise AssertionError(definition_id)
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(subject_profile_id)),
        payload=payload,
    )


def _access_context(
    contract: OperationPublicDefinitionContractV1,
    *,
    profile_id: UUID = _PROFILE,
    action: AccessAction = AccessAction.RESULT,
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=frontend,
        contract=contract,
        published_authority=Availability.AVAILABLE,
    )


def _receipt(definition_id: str, *, profile_id: UUID = _PROFILE) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id=cast(OperationId, "f" * 64),
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(profile_id)),
        ),
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=now(),
        result_ref="a" * 64,
    )


def _sample_attachment() -> AttachmentReviewItem:
    return AttachmentReviewItem(
        attachment_id=_ATTACHMENT_ID,
        sha256=_ATTACHMENT_ID,
        mime_type="application/xml",
        bytes_size=64,
        source=AttachmentSource.GOOGLE_DRIVE,
        provider_locator=_DRIVE_FILE_ID,
        captured_at="2026-09-30T11:30:00+00:00",
        linked_invoice_ids=(),
        pending_review=True,
    )


type _Projector = Callable[[BaseModel, OperationTerminalReceipt], BaseModel]


def _projection_and_projector(definition_id: str) -> tuple[BaseModel, BaseModel, _Projector]:
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID:
        projection = LedgerEvidenceAttachmentQueueProjection(profile_id=_PROFILE, count=0, rows=())
        return (
            LedgerEvidenceAttachmentQueueExecutionResult(profile_id=_PROFILE, result=projection),
            projection,
            _project_attachment_queue,
        )
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID:
        projection = LedgerEvidenceAttachmentViewProjection(profile_id=_PROFILE, item=_sample_attachment())
        return (
            LedgerEvidenceAttachmentViewExecutionResult(profile_id=_PROFILE, result=projection),
            projection,
            _project_attachment_view,
        )
    if definition_id == LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID:
        projection = LedgerEvidenceConsentListProjection(
            profile_id=_PROFILE,
            survey=ConsentWithdrawalSurveyProjection(),
        )
        return (
            LedgerEvidenceConsentListExecutionResult(profile_id=_PROFILE, result=projection),
            projection,
            _project_consent_list,
        )
    if definition_id == LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID:
        projection = LedgerEvidenceReviewListProjection(profile_id=_PROFILE)
        return (
            LedgerEvidenceReviewListExecutionResult(profile_id=_PROFILE, result=projection),
            projection,
            _project_review_list,
        )
    if definition_id == LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID:
        projection = LedgerEvidenceReviewViewProjection(
            profile_id=_PROFILE,
            evidence_reference=_EVIDENCE_REFERENCE,
            extractor="fixture-reader",
            drafted_at=now(),
            draft=InvoiceDraftProjectionV1.from_draft(InvoiceDraft()),
        )
        return (
            LedgerEvidenceReviewViewExecutionResult(profile_id=_PROFILE, result=projection),
            projection,
            _project_review_view,
        )
    raise AssertionError(definition_id)


@pytest.mark.parametrize("definition_id", _DEFINITION_IDS)
def test_every_read_requires_profile_wide_tax_value_disclosure(definition_id: str) -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(definition_id)
    request = _request(definition_id)
    context = _access_context(contract)

    resolved = resolve_operation_access(registry=registry, request=request, context=context)

    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.periods == frozenset()
    assert resolved.request.period_independent is True
    assert resolved.policy.requires_all_periods is True
    assert resolved.policy.allow_period_independent is True
    result_schema = contract.result_schema
    assert result_schema is not None
    assert any(
        disclosure.destination_id == context.destination_id
        and disclosure.projection_id == result_schema.schema_id
        and disclosure.category is DisclosureCategory.TAX_VALUES
        for disclosure in resolved.policy.disclosures
    )


@pytest.mark.parametrize("definition_id", _DEFINITION_IDS)
def test_every_read_refuses_a_foreign_profile_subject(definition_id: str) -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(definition_id)

    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry,
            request=_request(definition_id, subject_profile_id=_OTHER_PROFILE),
            context=_access_context(contract),
        )


@pytest.mark.parametrize("definition_id", _DEFINITION_IDS)
def test_each_projector_requires_its_successful_none_effect_receipt(definition_id: str) -> None:
    result, projection, projector = _projection_and_projector(definition_id)
    receipt = _receipt(definition_id)

    assert projector(result, receipt) == projection

    wrong_effect = receipt.model_copy(update={"effect": OperationEffect.UPDATED})
    with pytest.raises(ValueError):
        projector(result, wrong_effect)


_MCP_DEFINITION_IDS = (
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
)

_ATTACHMENT_ITEM_FIELDS = frozenset(
    {
        "attachment_id",
        "sha256",
        "mime_type",
        "bytes_size",
        "source",
        "provider_locator",
        "captured_at",
        "linked_invoice_ids",
        "pending_review",
    }
)

# Every model a result reaches and the fields it declares. A new field on any of
# them changes a set and fails the test below, so it is read for document
# content and host paths before an agent can receive it.
_MCP_RESULT_FIELDS: dict[str, dict[str, frozenset[str]]] = {
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID: {
        "LedgerEvidenceAttachmentQueueProjection": frozenset({"profile_id", "count", "rows"}),
        "AttachmentReviewItem": _ATTACHMENT_ITEM_FIELDS,
    },
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID: {
        "LedgerEvidenceAttachmentViewProjection": frozenset({"profile_id", "item"}),
        "AttachmentReviewItem": _ATTACHMENT_ITEM_FIELDS,
    },
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID: {
        "LedgerEvidenceConsentListProjection": frozenset({"profile_id", "survey"}),
        "ConsentWithdrawalSurveyProjection": frozenset(
            {"consented_dispatches", "cloud_derived_artefacts", "transmitted_bytes_are_unrecallable"}
        ),
        "ConsentedDispatchProjection": frozenset(
            {"profile_bucket_id", "evidence_content_address", "provider", "model", "surface", "recorded_at"}
        ),
        "CloudDerivedArtefactProjection": frozenset(
            {"evidence_reference", "provenance_stamp", "transport", "drafted_at"}
        ),
    },
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID: {
        "LedgerEvidenceReviewListProjection": frozenset({"profile_id", "filters", "rows"}),
        "EvidenceReviewQueueRowProjection": frozenset(
            {
                "evidence_reference",
                "extractor",
                "drafted_at",
                "blocking_count",
                "reasons",
                "advisory_count",
                "advisories",
            }
        ),
    },
}


def _nested_models(annotation: object) -> tuple[type[BaseModel], ...]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return (annotation,)
    return tuple(model for argument in get_args(annotation) for model in _nested_models(argument))


def _result_fields(root: type[BaseModel]) -> dict[str, frozenset[str]]:
    """Name every model reachable from ``root`` through its fields, with the fields it declares."""
    fields: dict[str, frozenset[str]] = {}
    pending = [root]
    while pending:
        model = pending.pop()
        if model.__name__ in fields:
            continue
        fields[model.__name__] = frozenset(model.model_fields)
        for field in model.model_fields.values():
            pending.extend(_nested_models(field.annotation))
    return fields


def _registered_result_model(registry: OperationRegistry, definition_id: str) -> type[BaseModel]:
    registration = registry.lookup_public_registration(definition_id)
    result_schema = registration.contract.result_schema
    assert result_schema is not None
    return next(binding.model_type for binding in registration.schema_bindings if binding.identity == result_schema)


@pytest.mark.parametrize("definition_id", _MCP_DEFINITION_IDS)
def test_each_evidence_metadata_read_is_admitted_on_the_mcp_frontend_without_a_commit_door(
    definition_id: str,
) -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(definition_id)

    resolved = resolve_operation_access(
        registry=registry,
        request=_request(definition_id),
        context=_access_context(contract, action=AccessAction.SUBMIT, frontend=OperationFrontendProjection.MCP),
    )
    assert resolved.request.frontend is OperationFrontendProjection.MCP
    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.period_independent is True
    assert AccessAction.COMMIT not in resolved.policy.actions


@pytest.mark.parametrize("definition_id", _MCP_DEFINITION_IDS)
def test_each_mcp_admitted_evidence_read_declares_only_metadata_fields(definition_id: str) -> None:
    result_model = _registered_result_model(_registry(), definition_id)

    assert _result_fields(result_model) == _MCP_RESULT_FIELDS[definition_id]


# ---------------------------------------------------------------------------
# The agent-facing review summary
# ---------------------------------------------------------------------------

_SUPPLIER_NAME = "SUMINISTROS SINTETICOS DEL NORTE SL"
_INVOICE_NUMBER = "SYN-2026-000417"
_REGIME_LEGEND = "Operacion con inversion del sujeto pasivo segun texto impreso sintetico"
_LINE_DESCRIPTION = "Mantenimiento trimestral de instalaciones sinteticas"
_SUPPLIER_ANCHOR = "Emisor: SUMINISTROS SINTETICOS DEL NORTE SL (impreso)"
_REFUSED_ANCHOR = "Total factura impreso en otra pagina sintetica"
_ROLE_EVIDENCE = "Bloque Datos del emisor impreso sintetico"
_PROVENANCE_NOTE = "nota sintetica que cita el documento impreso"
_CANDIDATE_VALUE = "1.234,56 candidato sintetico"
_CANDIDATE_ANCHOR = "TOTAL 1.234,56 EUR ancla sintetica"
_OTHER_CANDIDATE_VALUE = "1,234.56 candidato alterno sintetico"
_DISCREPANCY_DETAIL = "la base 100.00 mas la cuota 21.00 no cierra con el total impreso sintetico"

_DOCUMENT_TEXTS = (
    _SUPPLIER_NAME,
    _INVOICE_NUMBER,
    _REGIME_LEGEND,
    _LINE_DESCRIPTION,
    _SUPPLIER_ANCHOR,
    _REFUSED_ANCHOR,
    _ROLE_EVIDENCE,
    _PROVENANCE_NOTE,
    _CANDIDATE_VALUE,
    _CANDIDATE_ANCHOR,
    _OTHER_CANDIDATE_VALUE,
    _DISCREPANCY_DETAIL,
)


def _draft_with_document_text() -> InvoiceDraft:
    return InvoiceDraft(
        supplier_name=_SUPPLIER_NAME,
        invoice_number=_INVOICE_NUMBER,
        regime_legend=_REGIME_LEGEND,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("125.00"),
        lines=(
            InvoiceDraftLine(
                description=_LINE_DESCRIPTION,
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("21"),
                iva_amount=Decimal("21.00"),
            ),
        ),
        provenance=(
            FieldProvenance(
                field="supplier_name",
                origin=FieldOrigin.TEXT_LAYER,
                grounding=FieldGroundingOutcome.ANCHORED,
                anchor=_SUPPLIER_ANCHOR,
                role_evidence=_ROLE_EVIDENCE,
                note=_PROVENANCE_NOTE,
            ),
            FieldProvenance(
                field="grand_total",
                origin=FieldOrigin.TEXT_LAYER,
                grounding=FieldGroundingOutcome.AMBIGUOUS,
                refused_anchor=_REFUSED_ANCHOR,
                candidates=(
                    FieldAmbiguityCandidate(value=_CANDIDATE_VALUE, anchor=_CANDIDATE_ANCHOR),
                    FieldAmbiguityCandidate(value=_OTHER_CANDIDATE_VALUE),
                ),
            ),
        ),
        discrepancies=(
            DraftDiscrepancyFinding(
                kind=DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
                field="grand_total",
                detail=_DISCREPANCY_DETAIL,
                expected=Decimal("121.00"),
                observed=Decimal("125.00"),
            ),
        ),
        raw_text_length=2_048,
    )


def _review_view_with_document_text() -> LedgerEvidenceReviewViewProjection:
    draft = _draft_with_document_text()
    return LedgerEvidenceReviewViewProjection(
        profile_id=_PROFILE,
        evidence_reference=_EVIDENCE_REFERENCE,
        extractor="fixture-reader",
        drafted_at=_VALID_RECORDED_AT,
        draft=InvoiceDraftProjectionV1.from_draft(draft),
        blockers=tuple(ConfirmationBlockerProjectionV1.from_blocker(row) for row in confirmation_blockers(draft)),
    )


def _summary_request() -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerEvidenceReviewViewRequest(profile_id=_PROFILE, evidence_reference=_EVIDENCE_REFERENCE),
    )


def test_the_review_summary_is_admitted_alike_on_every_frontend_without_a_commit_door() -> None:
    registry = _summary_registry()
    contract = registry.lookup_public_contract(LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID)

    resolved = {
        frontend: resolve_operation_access(
            registry=registry,
            request=_summary_request(),
            context=_access_context(contract, action=AccessAction.SUBMIT, frontend=frontend),
        )
        for frontend in OperationFrontendProjection
    }

    assert len({answer.policy for answer in resolved.values()}) == 1
    for frontend, answer in resolved.items():
        assert answer.request.frontend is frontend
        assert answer.request.profile_id == _PROFILE
        assert answer.request.period_independent is True
        # A session under the person's sign-in and one under an enrolled key differ
        # in kind alone, and only a human-only policy tells the two apart.
        assert answer.policy.requires_human is False
        assert AccessAction.COMMIT not in answer.policy.actions


def test_the_review_summary_keeps_every_finding_and_figure_and_no_text_from_the_document() -> None:
    view = _review_view_with_document_text()
    assert view.blockers
    carried_by_the_view = view.model_dump_json()
    assert [text for text in _DOCUMENT_TEXTS if text not in carried_by_the_view] == []

    summary = LedgerEvidenceReviewSummaryProjection.from_review_view(view)

    released = summary.model_dump_json()
    assert [text for text in _DOCUMENT_TEXTS if text in released] == []
    assert summary.text_withheld is True
    assert summary.withheld_text_fields == ("supplier_name", "invoice_number", "regime_legend")
    assert summary.evidence_reference == _EVIDENCE_REFERENCE
    assert summary.drafted_at == _VALID_RECORDED_AT
    assert summary.grand_total == view.draft.grand_total
    assert summary.taxable_base == view.draft.taxable_base
    assert summary.iva_rate == view.draft.iva_rate
    assert summary.raw_text_length == 2_048
    (line,) = summary.lines
    assert line.description_withheld is True
    assert line.taxable_base == view.draft.lines[0].taxable_base
    supplier, total = summary.fields
    assert (supplier.field, supplier.origin, supplier.grounding) == (
        "supplier_name",
        FieldOrigin.TEXT_LAYER,
        FieldGroundingOutcome.ANCHORED,
    )
    assert (supplier.anchor_withheld, supplier.role_evidence_withheld, supplier.note_withheld) == (True, True, True)
    assert supplier.refused_anchor_withheld is False
    assert (total.field, total.grounding, total.candidate_count) == (
        "grand_total",
        FieldGroundingOutcome.AMBIGUOUS,
        2,
    )
    assert total.refused_anchor_withheld is True
    (discrepancy,) = summary.discrepancies
    assert discrepancy.kind is DraftDiscrepancyKind.ARITHMETIC_CLOSURE
    assert discrepancy.field == "grand_total"
    assert discrepancy.expected == view.draft.discrepancies[0].expected
    assert discrepancy.observed == view.draft.discrepancies[0].observed
    assert discrepancy.detail_withheld is True
    assert [(row.blocker_id, row.reason, row.field) for row in summary.blockers] == [
        (row.blocker_id, row.reason, row.field) for row in view.blockers
    ]
    assert [row.candidate_count for row in summary.blockers] == [len(row.candidates) for row in view.blockers]


def test_a_draft_that_holds_no_text_is_summarised_as_withholding_nothing() -> None:
    view = LedgerEvidenceReviewViewProjection(
        profile_id=_PROFILE,
        evidence_reference=_EVIDENCE_REFERENCE,
        extractor="fixture-reader",
        drafted_at=_VALID_RECORDED_AT,
        draft=InvoiceDraftProjectionV1.from_draft(InvoiceDraft(grand_total=Decimal("10.00"))),
    )

    summary = LedgerEvidenceReviewSummaryProjection.from_review_view(view)

    assert summary.text_withheld is False
    assert summary.withheld_text_fields == ()
    assert summary.grand_total == view.draft.grand_total


def test_the_summary_projector_releases_the_summary_and_the_view_projector_still_releases_the_text() -> None:
    view = _review_view_with_document_text()
    summary = LedgerEvidenceReviewSummaryProjection.from_review_view(view)
    summary_receipt = _receipt(LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID)

    released = _project_review_summary(
        LedgerEvidenceReviewSummaryExecutionResult(profile_id=_PROFILE, result=summary), summary_receipt
    )

    assert released == summary
    with pytest.raises(ValueError):
        _project_review_summary(
            LedgerEvidenceReviewSummaryExecutionResult(profile_id=_PROFILE, result=summary),
            _receipt(LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID),
        )
    with pytest.raises(ValueError):
        _project_review_summary(
            LedgerEvidenceReviewViewExecutionResult(profile_id=_PROFILE, result=view), summary_receipt
        )
    person_view = _project_review_view(
        LedgerEvidenceReviewViewExecutionResult(profile_id=_PROFILE, result=view),
        _receipt(LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID),
    )
    assert person_view == view
    assert _SUPPLIER_NAME in person_view.model_dump_json()


# What the summary does with each field of the person's draft projection. A
# field the draft gains is in none of these sets and fails the test below, so
# it is read for document text before an agent can receive anything of it.
_DRAFT_FIELDS_RELEASED_AS_TYPED_VALUES = frozenset(
    {
        "proposed_supply_nature",
        "suggested_kind",
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "grand_total",
        "recargo_amount",
        "retencion_rate",
        "retencion_amount",
        "suplidos_amount",
        "iva_breakdown",
        "transcription_sha256",
        "raw_text_length",
    }
)
_DRAFT_FIELDS_REDUCED_BY_THE_SUMMARY = frozenset({"lines", "provenance", "discrepancies", "facturae_invoice_class"})


def test_every_field_of_the_person_draft_is_released_typed_reduced_or_withheld_as_text() -> None:
    declared = frozenset(InvoiceDraftProjectionV1.model_fields)
    withheld = frozenset(DRAFT_TEXT_FIELDS_WITHHELD_FROM_AGENTS)

    assert len(withheld) == len(DRAFT_TEXT_FIELDS_WITHHELD_FROM_AGENTS)
    assert withheld.isdisjoint(_DRAFT_FIELDS_RELEASED_AS_TYPED_VALUES | _DRAFT_FIELDS_REDUCED_BY_THE_SUMMARY)
    assert withheld | _DRAFT_FIELDS_RELEASED_AS_TYPED_VALUES | _DRAFT_FIELDS_REDUCED_BY_THE_SUMMARY == declared
    assert withheld.isdisjoint(LedgerEvidenceReviewSummaryProjection.model_fields)
    assert frozenset(LedgerEvidenceReviewSummaryProjection.model_fields) >= _DRAFT_FIELDS_RELEASED_AS_TYPED_VALUES


def test_the_review_summary_declares_only_the_fields_read_for_document_text() -> None:
    assert _result_fields(LedgerEvidenceReviewSummaryProjection) == {
        "LedgerEvidenceReviewSummaryProjection": frozenset(
            {
                "profile_id",
                "evidence_reference",
                "extractor",
                "drafted_at",
                "suggested_kind",
                "proposed_supply_nature",
                "structured_invoice_class",
                "taxable_base",
                "iva_rate",
                "iva_amount",
                "grand_total",
                "recargo_amount",
                "retencion_rate",
                "retencion_amount",
                "suplidos_amount",
                "lines",
                "iva_breakdown",
                "transcription_sha256",
                "raw_text_length",
                "fields",
                "discrepancies",
                "blockers",
                "label_reading_fallback",
                "party_attribution_advisory",
                "country_vocabulary_warnings",
                "withheld_text_fields",
                "text_withheld",
            }
        ),
        "PublicDecimal": frozenset({"decimal"}),
        "EvidenceReviewLineSummary": frozenset(
            {
                "quantity",
                "unit_price",
                "taxable_base",
                "iva_rate",
                "iva_amount",
                "recargo_rate",
                "recargo_amount",
                "description_withheld",
            }
        ),
        "InvoiceDraftRateBreakdownProjectionV1": frozenset(
            {"iva_rate", "taxable_base", "iva_amount", "recargo_rate", "recargo_amount"}
        ),
        "EvidenceReviewFieldSummary": frozenset(
            {
                "field",
                "origin",
                "grounding",
                "anchor_self_reported",
                "attribution_unverified",
                "derived_from",
                "candidate_count",
                "anchor_withheld",
                "refused_anchor_withheld",
                "role_evidence_withheld",
                "note_withheld",
            }
        ),
        "EvidenceReviewDiscrepancySummary": frozenset({"kind", "field", "expected", "observed", "detail_withheld"}),
        "EvidenceReviewBlockerSummary": frozenset(
            {"blocker_id", "reason", "field", "candidate_count", "detail_withheld"}
        ),
        "LabelReadingFallbackProjectionV1": frozenset(
            {"cause", "unread_fields", "reader_error_type", "failed_condition_id"}
        ),
        "PartyAttributionAdvisoryProjection": frozenset({"parties"}),
        "PartyAttributionWarningProjection": frozenset({"role", "fields", "scope_if_attributed"}),
        "EvidenceReviewCountryWarningSummary": frozenset({"role", "field", "status"}),
    }
