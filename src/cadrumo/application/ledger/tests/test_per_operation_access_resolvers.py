"""Each per-operation access resolver admits only its own definition and payload type for its own profile.

The expected refusal codes and the COMMIT door are stated per resolver here, independently of the
shared helpers they delegate to, so a resolver that derived its identity from the request would fail.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability

from ....core.operations import profile_operation_subject
from ...export.calculation_review_xlsx_operation import (
    CalculationReviewXlsxRequest,
    build_calculation_review_xlsx_definition,
    build_calculation_review_xlsx_registration,
)
from ...inventory.registered_evidence_operation import (
    InventoryEvidenceAddRequest,
    resolve_inventory_evidence_add_access,
)
from ...inventory.registered_options_operation import (
    InventoryOptionsRequest,
    resolve_inventory_options_access,
)
from ...invoices.catalogue_add_operation import (
    InvoiceAddRequest,
    resolve_invoice_add_access,
)
from ...invoices.catalogue_remove_operation import (
    InvoiceRemoveRequest,
    resolve_invoice_remove_access,
)
from ...invoices.catalogue_update_operation import (
    InvoiceUpdateRequest,
    resolve_invoice_update_access,
)
from ...invoices.figures_preview_operation import (
    InvoiceFiguresPreviewRequest,
    resolve_invoice_figures_preview_access,
)
from ...modelo.invoice_withholding_capture_operation import (
    ModeloInvoiceWithholdingCaptureRequest,
    resolve_modelo_invoice_withholding_capture_access,
)
from ...modelo.reconciliation_export_operation import (
    ReconciliationExportXlsxRequest,
    build_reconciliation_export_xlsx_definition,
    build_reconciliation_export_xlsx_registration,
)
from ...modelo.reconciliation_import_operation import (
    ModeloReconciliationImportRequest,
    resolve_modelo_reconciliation_import_access,
)
from ...modelo.reconciliation_pull_operation import (
    ModeloReconciliationPullRequest,
    resolve_modelo_reconciliation_pull_access,
)
from ...operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ...operations.models import OperationRequest
from ...operations.operation_definition import OperationDefinition
from ...operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ...overview.pipeline_operation import (
    OverviewPipelineRequest,
    resolve_overview_pipeline_access,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..action_ports import LedgerActionPorts
from ..add_operation import (
    LedgerAddRequest,
    resolve_ledger_add_access,
)
from ..allocate_operation import (
    LedgerAllocateRequest,
    resolve_ledger_allocate_access,
)
from ..attachment_mutation_operation import (
    LedgerAttachRequest,
    LedgerDetachRequest,
    resolve_ledger_attach_access,
    resolve_ledger_detach_access,
)
from ..bulk_classify_operation import (
    LedgerBulkClassifyRequest,
    resolve_ledger_bulk_classify_access,
)
from ..check_operation import (
    LedgerCheckRequest,
    resolve_ledger_check_access,
)
from ..classify_operation import (
    LedgerClassifyRequest,
    resolve_ledger_classify_access,
)
from ..entry_options_operation import (
    LedgerEntryOptionsRequest,
    resolve_ledger_entry_options_access,
)
from ..evidence_add_operation import (
    LedgerEvidenceAddRequest,
    resolve_ledger_evidence_add_access,
)
from ..evidence_mutation_operation import (
    LedgerEvidenceRemoveRequest,
    LedgerEvidenceUpdateRequest,
    resolve_ledger_evidence_remove_access,
    resolve_ledger_evidence_update_access,
)
from ..evidence_read_operation import (
    LedgerEvidenceListRequest,
    LedgerEvidenceQueryRequest,
    LedgerEvidenceViewRequest,
    build_ledger_evidence_list_definition,
    build_ledger_evidence_list_registration,
    build_ledger_evidence_query_definition,
    build_ledger_evidence_query_registration,
    build_ledger_evidence_view_definition,
    build_ledger_evidence_view_registration,
)
from ..history_operation import (
    LedgerHistoryRequest,
    resolve_ledger_history_access,
    resolve_ledger_history_typed_access,
)
from ..known_values_operation import (
    LedgerKnownValuesRequest,
    resolve_ledger_known_values_access,
)
from ..lifecycle_contracts import LedgerLifecycleMutationRequest
from ..lifecycle_mutation_operation import (
    resolve_ledger_archive_access,
    resolve_ledger_exclude_access,
    resolve_ledger_restore_access,
    resolve_ledger_stash_access,
)
from ..merge_operation import (
    LedgerMergeRequest,
    resolve_ledger_merge_access,
)
from ..operator_iva_operation import (
    LedgerOperatorIvaRequest,
    resolve_ledger_operator_iva_access,
)
from ..participation_operation import (
    LedgerParticipationRequest,
    resolve_ledger_participation_access,
)
from ..participation_rebuild_operation import (
    LedgerParticipationRebuildRequest,
    resolve_ledger_participation_rebuild_access,
)
from ..remove_operation import build_ledger_remove_definition, build_ledger_remove_registration
from ..rule_trial_operation import (
    LedgerRuleTrialRequest,
    resolve_ledger_rule_trial_access,
)
from ..split_check_operation import LedgerSplitCheckRequest, resolve_ledger_split_check_access
from ..split_operation import (
    LedgerSplitRequest,
    resolve_ledger_split_access,
)
from ..staged_check_operation import (
    LedgerStagedCheckRequest,
    resolve_ledger_staged_check_access,
)
from ..status_operation import (
    LedgerStatusRequest,
    resolve_ledger_status_access,
)
from ..track_operation import (
    LedgerTrackRequest,
    resolve_ledger_track_access,
)
from ..update_operation import (
    LedgerUpdateRequest,
    resolve_ledger_update_access,
)
from ..view_operation import (
    LedgerViewRequest,
    resolve_ledger_view_access,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")

type _Resolver = Callable[[OperationRequest[BaseModel], OperationAccessContext], ResolvedOperationAccess]


class _ForeignRequest(BaseModel):
    profile_id: UUID


def _unused_factory(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("an access resolver must not build an executor")


def _registered_resolver(
    build_definition: Callable[[Callable[..., NoReturn]], OperationDefinition],
    build_registration: Callable[[OperationDefinition], OperationPublicDefinitionRegistrationV1],
) -> _Resolver:
    resolver = build_registration(build_definition(_unused_factory)).access_resolver
    assert resolver is not None
    return resolver


def _unused_ports(*, bucket_id: str, operation: object) -> LedgerActionPorts:
    raise AssertionError(f"unexpected operation execution for {bucket_id} with {operation!r}")


def _base_registration() -> OperationPublicDefinitionRegistrationV1:
    return build_ledger_remove_registration(build_ledger_remove_definition(_unused_ports))


def _context(definition_id: str) -> OperationAccessContext:
    contract = _base_registration().contract.model_copy(update={"definition_id": definition_id})
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=contract,
        published_authority=Availability.AVAILABLE,
    )


def _request(payload: BaseModel, *, definition_id: str, profile_id: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel].model_construct(
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=payload,
    )


# (resolver, definition id, payload type, whether the resolved policy carries the COMMIT door)
_RESOLVERS = [
    pytest.param(
        resolve_inventory_evidence_add_access,
        "ledger.inventory.evidence.add",
        InventoryEvidenceAddRequest,
        True,
        id="ledger.inventory.evidence.add",
    ),
    pytest.param(
        resolve_inventory_options_access,
        "ledger.inventory.options",
        InventoryOptionsRequest,
        False,
        id="ledger.inventory.options",
    ),
    pytest.param(resolve_invoice_add_access, "ledger.invoice.add", InvoiceAddRequest, True, id="ledger.invoice.add"),
    pytest.param(
        resolve_invoice_remove_access, "ledger.invoice.remove", InvoiceRemoveRequest, True, id="ledger.invoice.remove"
    ),
    pytest.param(
        resolve_invoice_update_access, "ledger.invoice.update", InvoiceUpdateRequest, True, id="ledger.invoice.update"
    ),
    pytest.param(
        resolve_invoice_figures_preview_access,
        "ledger.invoice.preview",
        InvoiceFiguresPreviewRequest,
        False,
        id="ledger.invoice.preview",
    ),
    pytest.param(resolve_ledger_add_access, "ledger.add", LedgerAddRequest, True, id="ledger.add"),
    pytest.param(resolve_ledger_allocate_access, "ledger.allocate", LedgerAllocateRequest, True, id="ledger.allocate"),
    pytest.param(
        resolve_ledger_bulk_classify_access,
        "ledger.classify.bulk",
        LedgerBulkClassifyRequest,
        True,
        id="ledger.classify.bulk",
    ),
    pytest.param(resolve_ledger_check_access, "ledger.check", LedgerCheckRequest, False, id="ledger.check"),
    pytest.param(
        resolve_ledger_classify_access,
        "ledger.classify.single",
        LedgerClassifyRequest,
        True,
        id="ledger.classify.single",
    ),
    pytest.param(
        resolve_ledger_entry_options_access,
        "ledger.entry-options",
        LedgerEntryOptionsRequest,
        False,
        id="ledger.entry-options",
    ),
    pytest.param(
        resolve_ledger_evidence_add_access,
        "ledger.evidence.add",
        LedgerEvidenceAddRequest,
        True,
        id="ledger.evidence.add",
    ),
    pytest.param(
        resolve_ledger_known_values_access,
        "ledger.known-values",
        LedgerKnownValuesRequest,
        False,
        id="ledger.known-values",
    ),
    pytest.param(resolve_ledger_merge_access, "ledger.merge", LedgerMergeRequest, True, id="ledger.merge"),
    pytest.param(
        resolve_ledger_operator_iva_access,
        "ledger.classify.iva-derive",
        LedgerOperatorIvaRequest,
        True,
        id="ledger.classify.iva-derive",
    ),
    pytest.param(
        resolve_ledger_participation_access,
        "ledger.participation",
        LedgerParticipationRequest,
        False,
        id="ledger.participation",
    ),
    pytest.param(
        resolve_ledger_participation_rebuild_access,
        "ledger.participation.rebuild",
        LedgerParticipationRebuildRequest,
        True,
        id="ledger.participation.rebuild",
    ),
    pytest.param(
        resolve_ledger_rule_trial_access, "ledger.rule.trial", LedgerRuleTrialRequest, False, id="ledger.rule.trial"
    ),
    pytest.param(
        resolve_ledger_split_check_access, "ledger.split.check", LedgerSplitCheckRequest, False, id="ledger.split.check"
    ),
    pytest.param(
        resolve_ledger_split_access, "ledger.split.manual", LedgerSplitRequest, True, id="ledger.split.manual"
    ),
    pytest.param(
        resolve_ledger_staged_check_access,
        "ledger.staged.check",
        LedgerStagedCheckRequest,
        False,
        id="ledger.staged.check",
    ),
    pytest.param(resolve_ledger_status_access, "ledger.status", LedgerStatusRequest, False, id="ledger.status"),
    pytest.param(resolve_ledger_track_access, "ledger.track", LedgerTrackRequest, False, id="ledger.track"),
    pytest.param(resolve_ledger_update_access, "ledger.update", LedgerUpdateRequest, True, id="ledger.update"),
    pytest.param(resolve_ledger_view_access, "ledger.view", LedgerViewRequest, False, id="ledger.view"),
    pytest.param(
        resolve_ledger_evidence_update_access,
        "ledger.evidence.update",
        LedgerEvidenceUpdateRequest,
        True,
        id="ledger.evidence.update",
    ),
    pytest.param(
        resolve_ledger_evidence_remove_access,
        "ledger.evidence.remove",
        LedgerEvidenceRemoveRequest,
        True,
        id="ledger.evidence.remove",
    ),
    pytest.param(
        _registered_resolver(build_ledger_evidence_list_definition, build_ledger_evidence_list_registration),
        "ledger.evidence.list",
        LedgerEvidenceListRequest,
        False,
        id="ledger.evidence.list",
    ),
    pytest.param(
        _registered_resolver(build_ledger_evidence_view_definition, build_ledger_evidence_view_registration),
        "ledger.evidence.view",
        LedgerEvidenceViewRequest,
        False,
        id="ledger.evidence.view",
    ),
    pytest.param(
        _registered_resolver(build_ledger_evidence_query_definition, build_ledger_evidence_query_registration),
        "ledger.evidence.query",
        LedgerEvidenceQueryRequest,
        False,
        id="ledger.evidence.query",
    ),
    pytest.param(resolve_ledger_history_access, "ledger.history", LedgerHistoryRequest, False, id="ledger.history"),
    pytest.param(
        resolve_ledger_history_typed_access,
        "ledger.history.typed",
        LedgerHistoryRequest,
        False,
        id="ledger.history.typed",
    ),
    pytest.param(resolve_ledger_attach_access, "ledger.attach", LedgerAttachRequest, True, id="ledger.attach"),
    pytest.param(resolve_ledger_detach_access, "ledger.detach", LedgerDetachRequest, True, id="ledger.detach"),
    pytest.param(
        resolve_ledger_archive_access, "ledger.archive", LedgerLifecycleMutationRequest, True, id="ledger.archive"
    ),
    pytest.param(resolve_ledger_stash_access, "ledger.stash", LedgerLifecycleMutationRequest, True, id="ledger.stash"),
    pytest.param(
        resolve_ledger_restore_access, "ledger.restore", LedgerLifecycleMutationRequest, True, id="ledger.restore"
    ),
    pytest.param(
        resolve_ledger_exclude_access, "ledger.exclude", LedgerLifecycleMutationRequest, True, id="ledger.exclude"
    ),
    pytest.param(
        resolve_overview_pipeline_access, "overview.pipeline", OverviewPipelineRequest, False, id="overview.pipeline"
    ),
    pytest.param(
        _registered_resolver(build_calculation_review_xlsx_definition, build_calculation_review_xlsx_registration),
        "export.calculation-review-xlsx",
        CalculationReviewXlsxRequest,
        True,
        id="export.calculation-review-xlsx",
    ),
    pytest.param(
        _registered_resolver(
            build_reconciliation_export_xlsx_definition, build_reconciliation_export_xlsx_registration
        ),
        "modelo.reconcile.export-xlsx",
        ReconciliationExportXlsxRequest,
        True,
        id="modelo.reconcile.export-xlsx",
    ),
    pytest.param(
        resolve_modelo_invoice_withholding_capture_access,
        "modelo.aggregate.capture_received_invoice_retencion",
        ModeloInvoiceWithholdingCaptureRequest,
        True,
        id="modelo.aggregate.capture_received_invoice_retencion",
    ),
    pytest.param(
        resolve_modelo_reconciliation_import_access,
        "modelo.reconcile.import",
        ModeloReconciliationImportRequest,
        True,
        id="modelo.reconcile.import",
    ),
    pytest.param(
        resolve_modelo_reconciliation_pull_access,
        "modelo.reconcile.pull",
        ModeloReconciliationPullRequest,
        True,
        id="modelo.reconcile.pull",
    ),
]


def _refusal(
    resolver: _Resolver, request: OperationRequest[BaseModel], context: OperationAccessContext
) -> AccessDenialCode:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolver(request, context)
    return refused.value.reason


@pytest.mark.parametrize(("resolver", "definition_id", "payload_type", "commits"), _RESOLVERS)
def test_resolver_admits_its_own_request_and_adds_commit_only_when_it_mutates(
    resolver: _Resolver, definition_id: str, payload_type: type[BaseModel], commits: bool
) -> None:
    payload = payload_type.model_construct(profile_id=_PROFILE)

    resolved = resolver(_request(payload, definition_id=definition_id), _context(definition_id))

    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.definition_id == definition_id
    assert (AccessAction.COMMIT in resolved.policy.actions) is commits


@pytest.mark.parametrize(("resolver", "definition_id", "payload_type", "commits"), _RESOLVERS)
def test_resolver_refuses_another_definition_as_unavailable(
    resolver: _Resolver, definition_id: str, payload_type: type[BaseModel], commits: bool
) -> None:
    payload = payload_type.model_construct(profile_id=_PROFILE)

    assert (
        _refusal(resolver, _request(payload, definition_id="ledger.other-operation"), _context(definition_id))
        is AccessDenialCode.OPERATION_UNAVAILABLE
    )


@pytest.mark.parametrize(("resolver", "definition_id", "payload_type", "commits"), _RESOLVERS)
def test_resolver_refuses_another_payload_type_as_unavailable(
    resolver: _Resolver, definition_id: str, payload_type: type[BaseModel], commits: bool
) -> None:
    request = _request(_ForeignRequest(profile_id=_PROFILE), definition_id=definition_id)

    assert _refusal(resolver, request, _context(definition_id)) is AccessDenialCode.OPERATION_UNAVAILABLE


@pytest.mark.parametrize(("resolver", "definition_id", "payload_type", "commits"), _RESOLVERS)
def test_resolver_refuses_a_foreign_profile_as_a_mismatch(
    resolver: _Resolver, definition_id: str, payload_type: type[BaseModel], commits: bool
) -> None:
    payload = payload_type.model_construct(profile_id=_OTHER_PROFILE)
    request = _request(payload, definition_id=definition_id, profile_id=_OTHER_PROFILE)

    assert _refusal(resolver, request, _context(definition_id)) is AccessDenialCode.PROFILE_MISMATCH


@pytest.mark.parametrize(("resolver", "definition_id", "payload_type", "commits"), _RESOLVERS)
def test_resolver_checks_the_definition_and_payload_before_the_profile(
    resolver: _Resolver, definition_id: str, payload_type: type[BaseModel], commits: bool
) -> None:
    foreign = _request(
        _ForeignRequest(profile_id=_OTHER_PROFILE), definition_id=definition_id, profile_id=_OTHER_PROFILE
    )
    other_definition = _request(
        payload_type.model_construct(profile_id=_OTHER_PROFILE),
        definition_id="ledger.other-operation",
        profile_id=_OTHER_PROFILE,
    )

    assert _refusal(resolver, foreign, _context(definition_id)) is AccessDenialCode.OPERATION_UNAVAILABLE
    assert _refusal(resolver, other_definition, _context(definition_id)) is AccessDenialCode.OPERATION_UNAVAILABLE


@pytest.mark.parametrize(("resolver", "definition_id", "payload_type", "commits"), _RESOLVERS)
def test_resolver_refuses_a_subject_of_another_profile_as_a_mismatch(
    resolver: _Resolver, definition_id: str, payload_type: type[BaseModel], commits: bool
) -> None:
    request = _request(
        payload_type.model_construct(profile_id=_PROFILE), definition_id=definition_id, profile_id=_OTHER_PROFILE
    )

    assert _refusal(resolver, request, _context(definition_id)) is AccessDenialCode.PROFILE_MISMATCH
