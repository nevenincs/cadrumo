"""Strict model and registry tests for encrypted refusal evidence."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code_by_code
from ....core.identity.digest import ContentDigest
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)
from .._supervisor_execution import _validated_refusal_receipt
from ..capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..errors import OperationDeclarationError
from ..models import (
    OperationFailureErrorCode,
    OperationIdentity,
    OperationRequest,
    OperationTerminalReceipt,
)
from ..owner import OperationExecutorContext
from ..persistence.events import OperationPhaseEvent
from ..persistence.journal import OperationPersistedSnapshot
from ..refusal_evidence import OperationExecutorResult, OperationRefusalEvidence
from ..registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationResultProjector,
    OperationSchemaBindingV1,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
_DETAIL_REF: ContentDigest = "e" * 64
_REFUSAL_CODE = "REFUSED_RUNTIME_FRONTEND"
_OTHER_REFUSAL_CODE = "REFUSED_WIZARD_MISSING_FLAG"


class _RequestPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: str


class _PrivateRefusalDetail(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    detail_code: str


class _PublicTerminalProjection(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    refusal_code: str
    detail_code: str


class _Executor:
    async def execute(
        self,
        request: OperationRequest[_RequestPayload],
        context: OperationExecutorContext,
    ) -> OperationExecutorResult:
        del request, context
        return None


class _InMemoryOperands:
    def __init__(self, detail: _PrivateRefusalDetail) -> None:
        self.detail = detail
        self.resolved_references: list[ContentDigest] = []

    async def put(self, operand: BaseModel, *, written_at: datetime) -> ContentDigest:
        del operand, written_at
        raise AssertionError("refusal evidence validation only resolves the executor-owned detail")

    async def resolve[OperandT: BaseModel](
        self,
        reference: ContentDigest,
        operand_type: type[OperandT],
    ) -> OperandT:
        if reference != _DETAIL_REF:
            raise AssertionError("unexpected refusal detail reference")
        self.resolved_references.append(reference)
        return operand_type.model_validate(self.detail.model_dump(mode="python"))


def _capabilities() -> OperationCapabilities:
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.COOPERATIVE,
        deadline=OperationDeadline.COOPERATIVE,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.REQUEST_BOUND,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.REQUEST_CANCEL,
    )


def _definition(
    refusal_detail_codes: frozenset[OperationFailureErrorCode] = frozenset(),
) -> OperationDefinition:
    return OperationDefinition(
        definition_id="test.refusal.evidence",
        request_type=_RequestPayload,
        result_type=_PrivateRefusalDetail,
        executor_factory=OperationExecutorFactory(
            request_type=_RequestPayload,
            executor_type=_Executor,
            build=_Executor,
        ),
        phase_codes=("phase.started",),
        interaction_kinds=frozenset({OperationInteractionKind.INPUT}),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=refusal_detail_codes,
    )


def _project_refusal_detail(
    detail: BaseModel,
    receipt: OperationTerminalReceipt,
) -> BaseModel:
    if type(detail) is not _PrivateRefusalDetail or receipt.refusal_ref is None:
        raise TypeError("refusal detail projection requires its declared refused outcome")
    return _PublicTerminalProjection(refusal_code=receipt.refusal_ref, detail_code=detail.detail_code)


def _registration(
    definition: OperationDefinition,
    *,
    result_model: type[BaseModel] | None = _PublicTerminalProjection,
    projector: OperationResultProjector | None = _project_refusal_detail,
) -> OperationPublicDefinitionRegistrationV1:
    request_schema = OperationSchemaBindingV1.bind(
        schema_id=f"{definition.definition_id}.request",
        schema_version=1,
        model_type=_RequestPayload,
    )
    result_schema = (
        OperationSchemaBindingV1.bind(
            schema_id=f"{definition.definition_id}.terminal",
            schema_version=1,
            model_type=result_model,
        )
        if result_model is not None
        else None
    )
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=request_schema,
        result_schema=result_schema,
        result_projector=projector,
    )


def _registry(
    definition: OperationDefinition,
    registration: OperationPublicDefinitionRegistrationV1,
) -> OperationRegistry:
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def _running_snapshot(definition: OperationDefinition, contract_digest: ContentDigest) -> OperationPersistedSnapshot:
    identity = OperationIdentity(
        operation_id="a" * 64,
        definition_id=definition.definition_id,
        subject_ref="profile:test",
    )
    phase = OperationPhaseEvent(
        identity=identity,
        revision=0,
        sequence=1,
        timestamp=_NOW,
        code="phase.started",
        phase_code="phase.started",
    )
    return OperationPersistedSnapshot(
        identity=identity,
        definition_contract_digest=contract_digest,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference="d" * 64,
        revision=0,
        lifecycle=OperationLifecycle.RUNNING,
        phase_code=phase.phase_code,
        started_at=_NOW,
        updated_at=_NOW,
        execution_deadline=None,
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
        event_cursor=phase.sequence,
        events=(phase,),
    )


def _terminal_receipt(
    condition: OperationTerminalCondition,
    *,
    refusal_detail_ref: ContentDigest | None = None,
    result_ref: str | None = None,
) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id="test.refusal.evidence",
            subject_ref="profile:test",
        ),
        revision=1,
        condition=condition,
        effect=OperationEffect.NONE,
        settled_at=_NOW,
        result_ref=result_ref,
        refusal_ref=_REFUSAL_CODE if condition is OperationTerminalCondition.REFUSED else None,
        refusal_detail_ref=refusal_detail_ref,
    )


@pytest.mark.parametrize("code", ("REFUSED_NOT_REGISTERED", "ERROR_MODELO_METADATA_RUN"))
def test_refusal_evidence_requires_a_registered_refusal_code(code: str) -> None:
    with pytest.raises(ValidationError, match="registered refusal code"):
        OperationRefusalEvidence(refusal_code=code, detail_ref=_DETAIL_REF)

    with pytest.raises(ValidationError, match="registered refusal code"):
        _definition(refusal_detail_codes=frozenset({code}))


def test_supervisor_evidence_requires_the_exact_declared_code_before_detail_resolution() -> None:
    definition = _definition(refusal_detail_codes=frozenset({_REFUSAL_CODE}))
    registration = _registration(definition)
    registry = _registry(definition, registration)
    snapshot = _running_snapshot(definition, registration.contract.definition_contract_digest)
    operands = _InMemoryOperands(_PrivateRefusalDetail(detail_code="modelo.not_applicable"))

    undeclared = OperationRefusalEvidence(refusal_code=_OTHER_REFUSAL_CODE, detail_ref=_DETAIL_REF)
    with pytest.raises(OperationDeclarationError, match="refusal evidence is not declared"):
        asyncio.run(
            _validated_refusal_receipt(
                registry=registry,
                operands=operands,
                snapshot=snapshot,
                evidence=undeclared,
                settled_at=_NOW,
            )
        )
    assert operands.resolved_references == []

    declared = OperationRefusalEvidence(refusal_code=_REFUSAL_CODE, detail_ref=_DETAIL_REF)
    receipt = asyncio.run(
        _validated_refusal_receipt(
            registry=registry,
            operands=operands,
            snapshot=snapshot,
            evidence=declared,
            settled_at=_NOW,
        )
    )
    assert operands.resolved_references == [_DETAIL_REF]
    assert receipt.condition is OperationTerminalCondition.REFUSED
    assert receipt.refusal_ref == _REFUSAL_CODE
    assert receipt.refusal_detail_ref == _DETAIL_REF
    assert receipt.result_ref is None
    assert receipt.effect is OperationEffect.NONE


@pytest.mark.parametrize(
    ("condition", "result_ref"),
    (
        (OperationTerminalCondition.SUCCEEDED, "result:success"),
        (OperationTerminalCondition.FAILED, None),
    ),
)
def test_refusal_detail_reference_is_refused_on_non_refused_terminals(
    condition: OperationTerminalCondition,
    result_ref: str | None,
) -> None:
    with pytest.raises(ValidationError, match="valid only for a refused operation"):
        _terminal_receipt(
            condition,
            refusal_detail_ref=_DETAIL_REF,
            result_ref=result_ref,
        )


def test_refused_receipt_keeps_result_reference_forbidden_with_detail() -> None:
    receipt = _terminal_receipt(
        OperationTerminalCondition.REFUSED,
        refusal_detail_ref=_DETAIL_REF,
    )
    assert receipt.refusal_ref == _REFUSAL_CODE
    assert receipt.refusal_detail_ref == _DETAIL_REF
    assert receipt.result_ref is None

    with pytest.raises(ValidationError, match="forbids a result reference"):
        _terminal_receipt(
            OperationTerminalCondition.REFUSED,
            refusal_detail_ref=_DETAIL_REF,
            result_ref="result:forbidden",
        )


def test_refusal_opt_in_requires_a_distinct_bound_result_schema_and_projector() -> None:
    definition = _definition(refusal_detail_codes=frozenset({_REFUSAL_CODE}))

    with pytest.raises(ValidationError, match="registered terminal projection schema"):
        _registration(definition, result_model=None, projector=None)

    identical_without_projector = _registration(
        definition,
        result_model=_PrivateRefusalDetail,
        projector=None,
    )
    with pytest.raises(ValidationError, match="explicit projector"):
        _registry(definition, identical_without_projector)

    identical_with_projector = _registration(definition, result_model=_PrivateRefusalDetail)
    with pytest.raises(ValidationError, match="must not declare one"):
        _registry(definition, identical_with_projector)

    distinct_without_projector = _registration(definition, projector=None)
    with pytest.raises(ValidationError, match="explicit projector"):
        _registry(definition, distinct_without_projector)

    distinct_with_projector = _registration(definition)
    registry = _registry(definition, distinct_with_projector)
    assert registry.lookup_public_contract(definition.definition_id).result_schema is not None
    assert distinct_with_projector.result_projector is _project_refusal_detail


def test_refusal_codes_change_the_public_definition_digest_and_default_to_code_only() -> None:
    first = _definition(refusal_detail_codes=frozenset({_REFUSAL_CODE}))
    second = _definition(refusal_detail_codes=frozenset({_OTHER_REFUSAL_CODE}))
    first_contract = _registration(first).contract
    second_contract = _registration(second).contract
    assert first_contract.refusal_detail_codes == frozenset({_REFUSAL_CODE})
    assert second_contract.refusal_detail_codes == frozenset({_OTHER_REFUSAL_CODE})
    assert first_contract.definition_contract_digest != second_contract.definition_contract_digest

    ordinary = _definition()
    ordinary_registration = _registration(ordinary, result_model=None, projector=None)
    registry = _registry(ordinary, ordinary_registration)
    contract = registry.lookup_public_contract(ordinary.definition_id)
    assert ordinary.refusal_detail_codes == frozenset()
    assert contract.refusal_detail_codes == frozenset()
    assert contract.result_schema is None
    assert ordinary_registration.result_projector is None


def test_error_code_registry_categories_used_by_the_fixture_are_canonical() -> None:
    assert get_registered_error_code_by_code(_REFUSAL_CODE).category is ErrorCategory.REFUSED
    assert get_registered_error_code_by_code(_OTHER_REFUSAL_CODE).category is ErrorCategory.REFUSED
