"""Canonical local Modelo 036 lifecycle under exact worker and disclosure authority.

Inward fixtures exercise the real service, registry compiler and access evaluator;
they do not claim native encrypted-storage or external filing acceptance.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.buckets.event import BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.censo_modelos import CensoModeloEventKind
from ....domain.modelos.errors import Modelo036PriorAltaRequiredError, Modelo036TerminalStateError
from ...operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ...operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDenialCode,
    AccessDenied,
    Availability,
    DisclosureCategory,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import m036_lifecycle as lifecycle_module
from .. import m036_operation as module
from ..m036_lifecycle import (
    M036DeclarationAmbiguousError,
    M036DeclarationNotFoundError,
    M036DeclarationResult,
    derive_m036_declaration_id,
)
from ..m036_operation_ports import M036OperationPorts
from .m036_operation_support import INSTANT, PROFILE_ID, Subject, policy_decision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]
_NOTE = "synthetic human filing note"
_RECEIPT = "synthetic-human-receipt"


def _record_request(
    kind: CensoModeloEventKind = CensoModeloEventKind.ALTA,
    *,
    day: int = 4,
) -> OperationRequest[module.M036RecordRequest]:
    return OperationRequest[module.M036RecordRequest](
        definition_id=module.M036_RECORD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=module.M036RecordRequest(
            profile_id=PROFILE_ID,
            event_kind=kind,
            declared_on=date(2026, 6, day),
            sede_justificante=_RECEIPT,
            note=_NOTE,
        ),
    )


def _read_request(*, query: bool, declaration_id: str | None = None) -> OperationRequest[module.M036ReadRequest]:
    return OperationRequest[module.M036ReadRequest](
        definition_id=module.M036_QUERY_OPERATION_DEFINITION_ID if query else module.M036_READ_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=module.M036ReadRequest(
            profile_id=PROFILE_ID,
            kind="list" if declaration_id is None else "view",
            declaration_id=declaration_id,
        ),
    )


def _registry(subject: Subject) -> OperationRegistry:
    definitions = module.build_m036_operation_definitions(subject.compose)
    return OperationRegistry(
        definitions=tuple(sorted(definitions, key=lambda definition: definition.definition_id)),
        public_registrations=tuple(
            sorted(
                module.build_m036_operation_registrations(definitions),
                key=lambda registration: registration.contract.definition_id,
            )
        ),
    )


def _result_access(subject: Subject, registry: OperationRegistry, *, definition_id: str) -> ResolvedOperationAccess:
    request = (
        _record_request()
        if definition_id == module.M036_RECORD_OPERATION_DEFINITION_ID
        else _read_request(query=definition_id == module.M036_QUERY_OPERATION_DEFINITION_ID)
    )
    return module.resolve_m036_operation_access(
        OperationRequest[BaseModel](
            definition_id=request.definition_id, subject_ref=request.subject_ref, payload=request.payload
        ),
        OperationAccessContext(
            profile_id=PROFILE_ID,
            destination_id=uuid4(),
            action=AccessAction.RESULT,
            frontend=OperationFrontendProjection.MCP
            if definition_id == module.M036_QUERY_OPERATION_DEFINITION_ID
            else OperationFrontendProjection.CLI,
            contract=registry.lookup_public_contract(definition_id),
            published_authority=Availability.AVAILABLE,
            authority_operation=subject.operation,
        ),
    )


@pytest.fixture
def subject(authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch) -> Subject:
    monkeypatch.setattr(module, "require_active_bucket_id", lambda: str(PROFILE_ID))
    monkeypatch.setattr(lifecycle_module, "now", lambda: INSTANT)
    return Subject(authority_operation)


def test_real_family_registration_compiles_complete_human_and_safe_schemas(subject: Subject) -> None:
    registry = _registry(subject)
    for definition_id in (
        module.M036_READ_OPERATION_DEFINITION_ID,
        module.M036_QUERY_OPERATION_DEFINITION_ID,
        module.M036_RECORD_OPERATION_DEFINITION_ID,
    ):
        contract = registry.lookup_public_contract(definition_id)
        assert contract.result_schema is not None and contract.result_schema.schema_id == definition_id + ".result"
        assert OperationEffect.UNKNOWN in registry.lookup(definition_id).capabilities.permitted_effects
    assert "note" in module.M036DeclarationSnapshot.model_fields
    assert "sede_justificante" in module.M036DeclarationSnapshot.model_fields
    assert "note" not in module.M036QueryDeclaration.model_fields
    assert "sede_justificante" not in module.M036QueryDeclaration.model_fields
    assert registry.lookup(module.M036_RECORD_OPERATION_DEFINITION_ID).permitted_frontends == frozenset(
        {OperationFrontendProjection.CLI}
    )
    assert (
        OperationEffect.PARTIAL
        not in registry.lookup(module.M036_RECORD_OPERATION_DEFINITION_ID).capabilities.permitted_effects
    )


@pytest.mark.asyncio
async def test_canonical_alta_modificacion_baja_reuses_atomic_record_and_event_service(subject: Subject) -> None:
    expected_events = (
        BucketEventType.CENSO_DECLARATION_ALTA,
        BucketEventType.CENSO_DECLARATION_MODIFICACION,
        BucketEventType.CENSO_DECLARATION_BAJA,
    )
    for index, kind in enumerate(CensoModeloEventKind):
        request = _record_request(kind, day=4 + index)
        await module.M036RecordExecutor(subject.compose).execute(request, subject.context(request.definition_id))
        result = cast(module.M036RecordExecutionResult, subject.operands.values[-1]).projection
        canonical = result.declaration.to_declaration()
        expected_id = derive_m036_declaration_id(
            profile_id=str(PROFILE_ID),
            event_kind=kind,
            declared_on=request.payload.declared_on,
            sede_justificante=_RECEIPT,
        )
        assert canonical.declaration_id == expected_id
        assert canonical == subject.repository.load(expected_id)
        assert canonical.note == _NOTE and canonical.sede_justificante == _RECEIPT
        assert subject.events.effects[-1] is OperationEffect.UPDATED
    assert subject.repository.writes == subject.fence.entries == 3
    assert tuple(event.event_type for event in subject.audit.catalogue.events.values()) == expected_events
    assert all(event.payload_version == 1 for event in subject.audit.catalogue.events.values())
    assert all(_NOTE not in phase and _RECEIPT not in phase for phase in subject.events.phases)
    assert not subject.fence.active


@pytest.mark.asyncio
async def test_record_preserves_canonical_retry_identity_without_inventing_noop(subject: Subject) -> None:
    request = _record_request()
    for _ in range(2):
        await module.M036RecordExecutor(subject.compose).execute(request, subject.context(request.definition_id))
    first = cast(module.M036RecordExecutionResult, subject.operands.values[0]).projection
    second = cast(module.M036RecordExecutionResult, subject.operands.values[1]).projection
    assert first.declaration.declaration_id == second.declaration.declaration_id
    assert len(subject.repository.records) == 1
    assert subject.repository.writes == subject.fence.entries == 2
    assert subject.events.effects[-1] is OperationEffect.UPDATED


@pytest.mark.asyncio
async def test_canonical_sequence_refusals_do_not_reach_writer(subject: Subject) -> None:
    request = _record_request(CensoModeloEventKind.MODIFICACION)
    with pytest.raises(Modelo036PriorAltaRequiredError):
        await module.M036RecordExecutor(subject.compose).execute(request, subject.context(request.definition_id))
    assert subject.repository.writes == subject.fence.entries == 0
    for kind, day in ((CensoModeloEventKind.ALTA, 4), (CensoModeloEventKind.BAJA, 5)):
        request = _record_request(kind, day=day)
        await module.M036RecordExecutor(subject.compose).execute(request, subject.context(request.definition_id))
    request = _record_request(CensoModeloEventKind.ALTA, day=6)
    with pytest.raises(Modelo036TerminalStateError):
        await module.M036RecordExecutor(subject.compose).execute(request, subject.context(request.definition_id))
    assert subject.repository.writes == subject.fence.entries == 2
    assert subject.events.effects[-1] is OperationEffect.NONE


@pytest.mark.asyncio
@pytest.mark.parametrize("committed", [False, True])
async def test_atomic_writer_authority_and_uncertain_failure_settle_truthfully(
    subject: Subject, committed: bool
) -> None:
    subject.fence.deny = not committed
    subject.repository.fail_after_commit = committed
    request = _record_request()
    with pytest.raises((ProfileAccessRefusedError, ValueError)):
        await module.M036RecordExecutor(subject.compose).execute(request, subject.context(request.definition_id))
    assert subject.events.effects[-1] is (OperationEffect.UNKNOWN if committed else OperationEffect.NONE)
    assert subject.repository.writes == (1 if committed else 0)
    assert bool(subject.audit.catalogue.events) is committed
    assert bool(subject.repository.records) is committed
    assert not subject.operands.values and not subject.fence.active


@pytest.mark.asyncio
async def test_shared_read_preserves_full_human_rows_and_only_reviewed_agent_facts(subject: Subject) -> None:
    request = _record_request()
    await module.M036RecordExecutor(subject.compose).execute(request, subject.context(request.definition_id))
    record = cast(module.M036RecordExecutionResult, subject.operands.values[-1]).projection.declaration
    for query in (False, True):
        request = _read_request(query=query, declaration_id=record.declaration_id[:16])
        await module.M036ReadExecutor(subject.compose, query=query).execute(
            request, subject.context(request.definition_id)
        )
    human = cast(module.M036ReadExecutionResult, subject.operands.values[-2]).projection
    agent = cast(module.M036QueryExecutionResult, subject.operands.values[-1]).projection
    assert human.declarations[0].to_declaration() == record.to_declaration()
    row = agent.declarations[0]
    assert row.profile_id == PROFILE_ID and row.declaration_id == record.declaration_id
    assert (
        row.event_kind == record.event_kind
        and row.declared_on == record.declared_on
        and row.recorded_at == record.recorded_at
    )
    assert row.note_present and row.justificante_present
    assert _NOTE not in agent.model_dump_json() and _RECEIPT not in agent.model_dump_json()
    assert subject.repository.writes == subject.fence.entries == 1
    assert subject.events.effects[-1] is OperationEffect.NONE


@pytest.mark.asyncio
async def test_empty_list_and_list_order_are_canonical_without_sorting_again(subject: Subject) -> None:
    request = _read_request(query=True)
    await module.M036ReadExecutor(subject.compose, query=True).execute(request, subject.context(request.definition_id))
    empty = cast(module.M036QueryExecutionResult, subject.operands.values[-1]).projection
    assert empty.declarations == ()
    first = M036DeclarationResult(
        declaration_id="f" * 64,
        bucket_id=str(PROFILE_ID),
        profile_id=str(PROFILE_ID),
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 4),
        recorded_at=INSTANT,
    )
    second = first.model_copy(update={"declaration_id": "a" * 64, "note": ""})
    subject.repository.seed(first)
    subject.repository.seed(second)
    await module.M036ReadExecutor(subject.compose, query=True).execute(request, subject.context(request.definition_id))
    rows = cast(module.M036QueryExecutionResult, subject.operands.values[-1]).projection.declarations
    assert tuple(row.declaration_id for row in rows) == (first.declaration_id, second.declaration_id)
    assert not rows[0].note_present and rows[1].note_present
    assert subject.repository.writes == subject.fence.entries == 0


@pytest.mark.asyncio
async def test_lookup_codes_remain_distinguishable_and_prefix_ambiguity_is_not_guessed(subject: Subject) -> None:
    request = _read_request(query=True, declaration_id="a")
    with pytest.raises(M036DeclarationNotFoundError) as missing:
        await module.M036ReadExecutor(subject.compose, query=True).execute(
            request, subject.context(request.definition_id)
        )
    assert missing.value.code.code == "REFUSED_M036_DECLARATION_NOT_FOUND"
    first = M036DeclarationResult(
        declaration_id="a" * 64,
        bucket_id=str(PROFILE_ID),
        profile_id=str(PROFILE_ID),
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 4),
        recorded_at=INSTANT,
    )
    subject.repository.seed(first)
    subject.repository.seed(first.model_copy(update={"declaration_id": "a" * 63 + "b"}))
    with pytest.raises(M036DeclarationAmbiguousError) as ambiguous:
        await module.M036ReadExecutor(subject.compose, query=True).execute(
            request, subject.context(request.definition_id)
        )
    assert ambiguous.value.code.code == "REFUSED_M036_DECLARATION_AMBIGUOUS"
    assert not subject.operands.values


@pytest.mark.asyncio
async def test_worker_pin_and_profile_refusal_precedes_storage(subject: Subject) -> None:
    wrong = replace(subject.ports, profile_id=uuid4())

    def compose(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> M036OperationPorts:
        return wrong

    request = _read_request(query=True)
    with pytest.raises(ProfileAccessRefusedError):
        await module.M036ReadExecutor(compose, query=True).execute(request, subject.context(request.definition_id))
    assert subject.repository.reads == subject.repository.writes == 0


@pytest.mark.parametrize("missing", [DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES, None])
def test_query_result_requires_exact_destination_complete_disclosure_and_all_periods(
    subject: Subject, missing: DisclosureCategory | None
) -> None:
    registry = _registry(subject)
    resolved = _result_access(subject, registry, definition_id=module.M036_QUERY_OPERATION_DEFINITION_ID)
    disclosures = frozenset(
        permission for permission in resolved.policy.disclosures if permission.category is not missing
    )
    decision = policy_decision(resolved, registry, disclosures=disclosures)
    if missing is None:
        assert isinstance(decision, AccessAllowed)
        wrong_destination = frozenset(
            permission.model_copy(update={"destination_id": uuid4()}) for permission in disclosures
        )
        denied = policy_decision(resolved, registry, disclosures=wrong_destination)
        assert isinstance(denied, AccessDenied) and denied.code is AccessDenialCode.DISCLOSURE_DENIED
        restricted = policy_decision(resolved, registry, disclosures=disclosures, all_periods=False)
        assert isinstance(restricted, AccessDenied) and restricted.code is AccessDenialCode.PERIOD_DENIED
    else:
        assert isinstance(decision, AccessDenied) and decision.code is AccessDenialCode.DISCLOSURE_DENIED


@pytest.mark.parametrize(
    "definition_id", [module.M036_READ_OPERATION_DEFINITION_ID, module.M036_RECORD_OPERATION_DEFINITION_ID]
)
def test_query_scope_and_api_authority_cannot_authorize_full_human_purposes(
    subject: Subject, definition_id: str
) -> None:
    registry = _registry(subject)
    resolved = _result_access(subject, registry, definition_id=definition_id)
    allowed = policy_decision(resolved, registry, disclosures=resolved.policy.disclosures, human=True)
    assert isinstance(allowed, AccessAllowed)
    automated = policy_decision(resolved, registry, disclosures=resolved.policy.disclosures)
    assert isinstance(automated, AccessDenied) and automated.code is AccessDenialCode.HUMAN_AUTHORITY_REQUIRED
    query_only = policy_decision(
        resolved,
        registry,
        disclosures=resolved.policy.disclosures,
        human=True,
        operations=frozenset({module.M036_QUERY_OPERATION_DEFINITION_ID}),
    )
    assert isinstance(query_only, AccessDenied) and query_only.code is AccessDenialCode.OPERATION_DENIED


def test_observation_is_only_metadata_and_record_commit_is_declared(subject: Subject) -> None:
    registry = _registry(subject)
    request = _record_request()
    public = OperationRequest[BaseModel](
        definition_id=request.definition_id, subject_ref=request.subject_ref, payload=request.payload
    )
    context = OperationAccessContext(
        profile_id=PROFILE_ID,
        destination_id=uuid4(),
        action=AccessAction.OBSERVE,
        frontend=OperationFrontendProjection.CLI,
        contract=registry.lookup_public_contract(request.definition_id),
        published_authority=Availability.AVAILABLE,
        authority_operation=subject.operation,
    )
    observed = module.resolve_m036_operation_access(public, context)
    assert AccessAction.COMMIT in observed.policy.actions
    assert len(observed.policy.disclosures) == 1
    permission = next(iter(observed.policy.disclosures))
    assert (
        permission.category is DisclosureCategory.OPERATION_METADATA
        and permission.projection_id == OPERATION_OBSERVATION_PROJECTION_ID
    )
    with pytest.raises(ProfileAccessRefusedError):
        module.resolve_m036_operation_access(public, replace(context, frontend=OperationFrontendProjection.MCP))


def test_projector_correlates_purpose_and_write_effect(subject: Subject) -> None:
    result = module.M036QueryExecutionResult(
        projection=module.M036QueryProjection(profile_id=PROFILE_ID, kind="list", declarations=())
    )
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=module.M036_QUERY_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(PROFILE_ID)),
        ),
        revision=1,
        settled_at=INSTANT,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        result_ref="d" * 64,
    )
    assert module.project_m036_operation_result(result, receipt) == result.projection
    for defect in (
        {"effect": OperationEffect.UPDATED},
        {"identity": receipt.identity.model_copy(update={"definition_id": module.M036_READ_OPERATION_DEFINITION_ID})},
    ):
        with pytest.raises(ValueError):
            module.project_m036_operation_result(result, receipt.model_copy(update=defect))
    with pytest.raises(ValidationError):
        module.M036ReadRequest(profile_id=PROFILE_ID, kind="list", declaration_id="a")
