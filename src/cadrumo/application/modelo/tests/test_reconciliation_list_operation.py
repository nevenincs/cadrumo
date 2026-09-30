"""The registered reconciliation list stays whole-profile and field-bounded."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.config import override_settings
from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    Availability,
    DisclosureCategory,
    OperationAccessRequest,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import reconciliation_list_operation as operation_module
from ..reconciliation_list_operation import (
    MAX_MODELO_RECONCILIATION_SOURCE_PATH_LENGTH,
    MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID,
    ModeloReconciliationListEntryProjection,
    ModeloReconciliationListExecutor,
    ModeloReconciliationListProjection,
    ModeloReconciliationListRequest,
    build_modelo_reconciliation_list_definition,
    build_modelo_reconciliation_list_registration,
)
from ..reconciliation_records import (
    ModeloReconciliationDiff,
    ModeloReconciliationDiffKind,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationHistoryEntry,
    ModeloReconciliationVerdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_NOW = datetime(2026, 3, 10, 12, tzinfo=UTC)
_WORK_A = "1" * 64
_WORK_B = "2" * 64


def _history_entry(
    *,
    event_id: str,
    work_unit_id: str = _WORK_A,
    bucket_id: UUID = _PROFILE,
    reconciled_at: datetime = _NOW,
    source_path: str = "C:/synthetic/evidence/receipt.pdf",
    actor: str = "synthetic-test-operator",
) -> ModeloReconciliationHistoryEntry:
    return ModeloReconciliationHistoryEntry(
        event_id=event_id,
        bucket_id=str(bucket_id),
        work_unit_id=work_unit_id,
        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        source_path=source_path,
        verdict=ModeloReconciliationVerdict.MISMATCHES,
        diff_count=1,
        diffs=(
            ModeloReconciliationDiff(
                field_name="total_ingresar",
                work_unit_value="100.00",
                evidence_value="101.00",
                kind="total_ingresar_mismatch",
                diff_kind=ModeloReconciliationDiffKind.HEADER_FIELD,
            ),
        ),
        actor=actor,
        reconciled_at=reconciled_at,
    )


def _request(
    *, profile_id: UUID = _PROFILE, work_unit_id: str | None = None
) -> OperationRequest[ModeloReconciliationListRequest]:
    return OperationRequest[ModeloReconciliationListRequest](
        definition_id=MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ModeloReconciliationListRequest(profile_id=profile_id, work_unit_id=work_unit_id),
    )


def _context(
    registration,
    *,
    action: AccessAction = AccessAction.SUBMIT,
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
    profile_id: UUID = _PROFILE,
    admitted: OperationAccessRequest | None = None,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=frontend,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
    )


def _registered():
    definition = build_modelo_reconciliation_list_definition()
    registration = build_modelo_reconciliation_list_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return definition, registration, registry


def test_public_projection_keeps_cli_fields_and_omits_private_record_detail() -> None:
    first = _history_entry(event_id="a" * 64)
    second = _history_entry(event_id="b" * 64, reconciled_at=datetime(2026, 3, 10, 13, tzinfo=UTC))
    projection = ModeloReconciliationListProjection(
        profile_id=_PROFILE,
        work_unit_id=None,
        reconciliation_count=2,
        reconciliations=(
            ModeloReconciliationListEntryProjection.from_history_entry(first),
            ModeloReconciliationListEntryProjection.from_history_entry(second),
        ),
    )

    dumped = projection.model_dump(mode="json")
    assert ModeloReconciliationListProjection.model_validate_json(projection.model_dump_json()) == projection
    assert set(dumped) == {"result_version", "profile_id", "work_unit_id", "reconciliation_count", "reconciliations"}
    assert set(dumped["reconciliations"][0]) == {
        "event_id",
        "bucket_id",
        "work_unit_id",
        "source_kind",
        "source_path",
        "verdict",
        "diff_count",
        "actor",
        "reconciled_at",
    }
    assert dumped["reconciliations"][0]["source_path"] == first.source_path
    assert "diffs" not in dumped["reconciliations"][0]
    assert len(dumped["reconciliations"]) == 2


def test_public_projection_rejects_wrong_scope_duplicates_order_and_unbounded_fields() -> None:
    first = ModeloReconciliationListEntryProjection.from_history_entry(_history_entry(event_id="a" * 64))
    later = ModeloReconciliationListEntryProjection.from_history_entry(
        _history_entry(event_id="b" * 64, reconciled_at=datetime(2026, 3, 10, 13, tzinfo=UTC))
    )
    other_profile = ModeloReconciliationListEntryProjection.from_history_entry(
        _history_entry(event_id="c" * 64, bucket_id=_OTHER)
    )
    other_unit = ModeloReconciliationListEntryProjection.from_history_entry(
        _history_entry(event_id="d" * 64, work_unit_id=_WORK_B)
    )
    with pytest.raises(ValidationError):
        ModeloReconciliationListProjection(profile_id=_PROFILE, reconciliation_count=0, reconciliations=(first,))
    for rows, filter_id in (
        ((other_profile,), None),
        ((other_unit,), _WORK_A),
        ((first, first), None),
        ((later, first), None),
    ):
        with pytest.raises(ValidationError):
            ModeloReconciliationListProjection(
                profile_id=_PROFILE,
                work_unit_id=filter_id,
                reconciliation_count=len(rows),
                reconciliations=rows,
            )
    too_long = _history_entry(event_id="e" * 64, source_path="x" * (MAX_MODELO_RECONCILIATION_SOURCE_PATH_LENGTH + 1))
    with pytest.raises(ValidationError):
        ModeloReconciliationListEntryProjection.from_history_entry(too_long)
    with pytest.raises(ValidationError):
        _history_entry(event_id="f" * 64, source_path="ok", actor="x" * 129)


def test_access_resolves_whole_profile_disclosure_and_requires_all_periods() -> None:
    definition, registration, registry = _registered()
    request = _request(work_unit_id=_WORK_A)
    resolved = resolve_operation_access(
        registry=registry,
        request=cast(OperationRequest[BaseModel], request),
        context=_context(registration, frontend=OperationFrontendProjection.MCP),
    )
    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.period_independent and not resolved.request.periods
    assert resolved.policy.allow_period_independent and resolved.policy.requires_all_periods
    assert definition.permitted_frontends == frozenset(
        {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
    )

    result_admission = OperationAccessRequest(
        profile_id=_PROFILE,
        definition_id=definition.definition_id,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        periods=frozenset(),
        period_independent=True,
        destination_id=uuid4(),
    )
    result_context = _context(registration, action=AccessAction.RESULT, admitted=result_admission)
    result_resolved = resolve_operation_access(
        registry=registry,
        request=cast(OperationRequest[BaseModel], _request(work_unit_id=_WORK_A)),
        context=result_context,
    )
    result_permission = next(iter(result_resolved.policy.disclosures))
    assert result_permission.destination_id == result_context.destination_id
    assert result_permission.projection_id == registration.contract.result_schema.schema_id
    assert result_permission.category is DisclosureCategory.TAX_VALUES

    scope = AccessScope(
        operations=frozenset({definition.definition_id}),
        actions=frozenset({AccessAction.SUBMIT}),
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )
    from ...user_profile.access_policy import operation_scope_refusal

    assert operation_scope_refusal(request=resolved.request, policy=resolved.policy, scope=scope) is None
    finite_scope = scope.model_copy(update={"periods": frozenset({Period.from_year_and_code(2026, "1T")})})
    refused = operation_scope_refusal(request=resolved.request, policy=resolved.policy, scope=finite_scope)
    assert refused is not None and refused.code is AccessDenialCode.PERIOD_DENIED


def test_wrong_profile_is_refused_before_access_is_admitted() -> None:
    _, registration, registry = _registered()
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=cast(OperationRequest[BaseModel], _request(profile_id=_OTHER)),
            context=_context(registration),
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_executor_projects_the_existing_filter_and_order_without_private_diffs(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = (
        _history_entry(event_id="a" * 64),
        _history_entry(event_id="b" * 64, reconciled_at=datetime(2026, 3, 10, 13, tzinfo=UTC)),
    )
    calls: list[tuple[str, str | None, object]] = []

    def read_history(*, bucket_id: str, operation: PinnedAuthorityOperation, work_unit_id: str | None):
        calls.append((bucket_id, work_unit_id, operation))
        return entries

    monkeypatch.setattr(
        "cadrumo.application.modelo.reconciliation_list_operation.list_modelo_reconciliations", read_history
    )
    recorded: list[BaseModel] = []
    effects: list[OperationEffect] = []

    class Events:
        async def phase(self, code: str) -> None:
            assert code == MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            recorded.append(operand)
            return "f" * 64

    pinned = cast(PinnedAuthorityOperation, cast(object, object()))
    context = cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=OperationIdentity(
                    operation_id="a" * 64,
                    definition_id=MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                ),
                authority_operation=pinned,
                events=Events(),
                operands=Operands(),
            ),
        ),
    )
    request = _request(work_unit_id=_WORK_A)
    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        reference = asyncio.run(ModeloReconciliationListExecutor().execute(request, context))

    assert reference == "f" * 64
    assert calls == [(str(_PROFILE), _WORK_A, pinned)]
    assert effects == [OperationEffect.NONE]
    projection = ModeloReconciliationListProjection.model_validate(recorded[0])
    assert tuple(row.event_id for row in projection.reconciliations) == ("a" * 64, "b" * 64)
    assert projection.work_unit_id == _WORK_A
    assert "diffs" not in projection.model_dump_json()


def test_executor_refuses_active_profile_mismatch_before_read(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(
        "cadrumo.application.modelo.reconciliation_list_operation.list_modelo_reconciliations",
        lambda **_kwargs: calls.append(object()),
    )
    context = cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=OperationIdentity(
                    operation_id="a" * 64,
                    definition_id=MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                ),
                authority_operation=cast(PinnedAuthorityOperation, cast(object, object())),
                events=SimpleNamespace(phase=lambda _code: None),
            ),
        ),
    )
    with override_settings(cadrumo_active_profile=str(_OTHER)), pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(ModeloReconciliationListExecutor().execute(_request(), context))
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert calls == []


@pytest.mark.parametrize("oversize_kind", ["path", "document"])
def test_executor_refuses_oversized_public_result_without_truncating(
    monkeypatch: pytest.MonkeyPatch, oversize_kind: str
) -> None:
    entry = _history_entry(
        event_id="a" * 64,
        source_path=("x" * (MAX_MODELO_RECONCILIATION_SOURCE_PATH_LENGTH + 1))
        if oversize_kind == "path"
        else "C:/synthetic/evidence.pdf",
    )
    monkeypatch.setattr(operation_module, "list_modelo_reconciliations", lambda **_kwargs: (entry,))
    if oversize_kind == "document":
        monkeypatch.setattr(operation_module, "_RESULT_DOCUMENT_MAX_BYTES", 1)
    effects: list[OperationEffect] = []

    class Events:
        async def phase(self, _code: str) -> None:
            pass

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    class Operands:
        async def put(self, _operand: BaseModel, *, written_at: datetime) -> str:
            pytest.fail("oversized output must be refused before publication")

    context = cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=OperationIdentity(
                    operation_id="a" * 64,
                    definition_id=MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                ),
                authority_operation=cast(PinnedAuthorityOperation, cast(object, object())),
                events=Events(),
                operands=Operands(),
            ),
        ),
    )
    with override_settings(cadrumo_active_profile=str(_PROFILE)), pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(ModeloReconciliationListExecutor().execute(_request(), context))
    assert refused.value.reason is AccessDenialCode.OPERATION_DENIED
    assert effects == []
