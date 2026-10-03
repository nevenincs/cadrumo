"""Whole-profile access, strict transport, and terminal receipts for ledger rules."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....application.ledger.action_ports import LedgerActionPorts
from ....application.ledger.actions_common import save_transaction_catalogue_and_events
from ....application.ledger.commit_fence import (
    LedgerCommitAttemptTracker,
    TrackedLedgerTransactionRepository,
    is_guaranteed_prewrite_failure,
    run_with_ledger_commit_fence,
)
from ....application.ledger.persistence_ports import LedgerPersistenceConflictError
from ....application.ledger.protocols import (
    BucketEventHistoryCoCommitWriterProtocol,
    RevisionGuardedTransactionCatalogueCoCommitWriterProtocol,
)
from ....application.ledger.rule_repository import LedgerClassificationRuleRepositoryProtocol
from ....application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ....application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ....application.operations.owner import OperationExecutorContext
from ....application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ....application.operations.registry_schema_validation import strict_model_json_schema
from ....application.user_profile.access_contracts import AccessAction, Availability
from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.secure_object_write import SecureObjectWrite
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.classification_rule import LedgerClassificationRule
from ....domain.transactions.enums import BusinessClassification
from ....domain.transactions.models import LedgerDatePartition, Transaction, TransactionCatalogue
from ..rule_contracts import (
    LedgerRuleAddProjection,
    LedgerRuleAddRequest,
    LedgerRuleApplyExecutionResult,
    LedgerRuleApplyProjection,
    LedgerRuleApplyRequest,
    LedgerRuleListProjection,
    LedgerRuleListRequest,
    LedgerRuleRowProjection,
)
from ..rule_operation import (
    LEDGER_RULE_ADD_OPERATION_DEFINITION_ID,
    LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID,
    LEDGER_RULE_LIST_OPERATION_DEFINITION_ID,
    _TrackedRuleRepository,
    build_ledger_rule_add_definition,
    build_ledger_rule_add_registration,
    build_ledger_rule_apply_definition,
    build_ledger_rule_apply_registration,
    build_ledger_rule_list_definition,
    build_ledger_rule_list_registration,
)
from ..rule_results import LEDGER_RULE_VALIDATION_REFUSAL_CODE

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_NOW = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)


def _rule(*, pattern: str = "^office", priority: int = 12, created_at: datetime = _NOW) -> LedgerClassificationRule:
    return LedgerClassificationRule.create(
        description_pattern=pattern,
        classification=BusinessClassification.BUSINESS,
        category_id="material_oficina",
        priority=priority,
        actor="rule-test-operator",
        created_at=created_at,
    )


def _registry() -> tuple[OperationRegistry, dict[str, OperationPublicDefinitionRegistrationV1]]:
    def unused_repository(*, bucket_id: str) -> LedgerClassificationRuleRepositoryProtocol:
        raise AssertionError(f"unexpected repository composition for {bucket_id}")

    def unused_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
        raise AssertionError(f"unexpected ports composition for {bucket_id}: {operation!r}")

    add = build_ledger_rule_add_definition(unused_repository)
    listing = build_ledger_rule_list_definition(unused_repository)
    apply = build_ledger_rule_apply_definition(unused_ports, unused_repository)
    registrations = {
        LEDGER_RULE_ADD_OPERATION_DEFINITION_ID: build_ledger_rule_add_registration(add),
        LEDGER_RULE_LIST_OPERATION_DEFINITION_ID: build_ledger_rule_list_registration(listing),
        LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID: build_ledger_rule_apply_registration(apply),
    }
    return (
        OperationRegistry(
            definitions=(add, listing, apply),
            public_registrations=tuple(registrations[key] for key in sorted(registrations)),
        ),
        registrations,
    )


def _request(definition_id: str, *, profile_id: UUID = _PROFILE, dry_run: bool = False) -> OperationRequest[BaseModel]:
    if definition_id == LEDGER_RULE_ADD_OPERATION_DEFINITION_ID:
        payload: BaseModel = LedgerRuleAddRequest(
            profile_id=profile_id,
            description_pattern="^office",
            classification=BusinessClassification.BUSINESS,
            category_id="material_oficina",
        )
    elif definition_id == LEDGER_RULE_LIST_OPERATION_DEFINITION_ID:
        payload = LedgerRuleListRequest(profile_id=profile_id)
    else:
        payload = LedgerRuleApplyRequest(profile_id=profile_id, dry_run=dry_run)
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=payload,
    )


def _access_context(
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    profile_id: UUID = _PROFILE,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


@pytest.mark.parametrize(
    ("definition_id", "dry_run", "commit_required"),
    (
        (LEDGER_RULE_ADD_OPERATION_DEFINITION_ID, False, True),
        (LEDGER_RULE_LIST_OPERATION_DEFINITION_ID, False, False),
        (LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID, False, True),
        (LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID, True, False),
    ),
)
def test_access_is_exact_profile_and_all_period_with_commit_only_for_writes(
    definition_id: str,
    dry_run: bool,
    commit_required: bool,
) -> None:
    registry, registrations = _registry()
    context = _access_context(registrations[definition_id])

    resolved = resolve_operation_access(
        registry=registry,
        request=_request(definition_id, dry_run=dry_run),
        context=context,
    )

    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.period_independent is True
    assert resolved.request.periods == frozenset()
    assert resolved.policy.requires_all_periods is True
    assert (AccessAction.COMMIT in resolved.policy.actions) is commit_required


def test_access_refuses_a_different_context_profile() -> None:
    registry, registrations = _registry()
    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry,
            request=_request(LEDGER_RULE_LIST_OPERATION_DEFINITION_ID),
            context=_access_context(registrations[LEDGER_RULE_LIST_OPERATION_DEFINITION_ID], profile_id=_OTHER_PROFILE),
        )


def test_registrations_are_cli_only_and_wire_graphs_are_closed() -> None:
    registry, registrations = _registry()
    assert {definition.definition_id for definition in registry.definitions} >= set(registrations)
    assert all(
        registry.lookup(definition_id).permitted_frontends == frozenset({OperationFrontendProjection.CLI})
        for definition_id in registrations
    )
    for definition_id in (LEDGER_RULE_ADD_OPERATION_DEFINITION_ID, LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID):
        definition = registry.lookup(definition_id)
        registration = registrations[definition_id]
        assert definition.refusal_detail_codes == frozenset({LEDGER_RULE_VALIDATION_REFUSAL_CODE})
        assert registration.result_projector is not None
        result_schema = registration.contract.result_schema
        assert result_schema is not None
        assert registry.lookup_public_schema_binding(result_schema).model_type is not definition.result_type
    listing = registry.lookup(LEDGER_RULE_LIST_OPERATION_DEFINITION_ID)
    assert listing.result_type is LedgerRuleListProjection
    assert listing.refusal_detail_codes == frozenset()
    assert registrations[LEDGER_RULE_LIST_OPERATION_DEFINITION_ID].result_projector is None
    assert LedgerRuleAddRequest.model_json_schema()["additionalProperties"] is False
    assert LedgerRuleListProjection.model_json_schema()["additionalProperties"] is False
    assert LedgerRuleApplyProjection.model_json_schema()["additionalProperties"] is False

    add_request = cast(LedgerRuleAddRequest, _request(LEDGER_RULE_ADD_OPERATION_DEFINITION_ID).payload)
    assert LedgerRuleAddRequest.model_validate_json(add_request.model_dump_json()) == add_request
    with pytest.raises(ValidationError):
        LedgerRuleListRequest.model_validate({"profile_id": str(_PROFILE), "all_profiles": True})


def test_rule_rows_preserve_every_stored_field_across_operation_dtos() -> None:
    source = _rule(created_at=_NOW.replace(microsecond=123456))
    row = LedgerRuleRowProjection.from_rule(source)
    add = LedgerRuleAddProjection(profile_id=_PROFILE, outcome="added", rule=row)
    listing = LedgerRuleListProjection(profile_id=_PROFILE, rules=(row,))
    sealed_add = LedgerRuleAddProjection.model_validate_json(add.model_dump_json())
    sealed_list = LedgerRuleListProjection.model_validate_json(listing.model_dump_json())

    assert sealed_add.rule == row
    assert sealed_list.rules == (row,)
    assert row.rule_id == source.rule_id
    assert row.description_pattern == source.description_pattern
    assert row.classification is source.classification
    assert row.category_id == source.category_id
    assert row.priority == source.priority
    assert row.actor == source.actor
    assert row.created_at == source.created_at
    assert sealed_add.rule is not None
    assert sealed_add.rule.created_at.microsecond == 123456
    assert sealed_list.rules[0].created_at.microsecond == 123456


@pytest.mark.parametrize("model", [LedgerRuleAddProjection, LedgerRuleListProjection, LedgerRuleApplyProjection])
def test_rule_public_projections_compile_under_the_canonical_schema_contract(model: type[BaseModel]) -> None:
    schema = strict_model_json_schema(model)
    assert schema["additionalProperties"] is False
    assert schema == model.model_json_schema(mode="validation") == model.model_json_schema(mode="serialization")


@pytest.mark.parametrize("created_at", [_NOW.replace(tzinfo=None), _NOW.astimezone(timezone(timedelta(hours=1)))])
def test_rule_public_rows_refuse_unknown_or_non_utc_creation_instants(created_at: datetime) -> None:
    raw = LedgerRuleRowProjection.from_rule(_rule()).model_dump(mode="python") | {"created_at": created_at}
    with pytest.raises(ValidationError):
        LedgerRuleRowProjection.model_validate(raw)


def test_apply_projector_keeps_partial_receipt_typed_and_rejects_wrong_effect() -> None:
    registration_id = LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID
    refusal = LedgerRuleApplyProjection(
        profile_id=_PROFILE,
        outcome="validation_error",
        validation_code="invalid_command",
        validation_messages=("transaction update was refused before its write boundary",),
    )
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=registration_id,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.PARTIAL,
        settled_at=_NOW,
        refusal_ref=LEDGER_RULE_VALIDATION_REFUSAL_CODE,
        refusal_detail_ref="c" * 64,
    )

    def unused_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
        raise AssertionError(f"unexpected ports composition for {bucket_id}: {operation!r}")

    def unused_repository(*, bucket_id: str) -> LedgerClassificationRuleRepositoryProtocol:
        raise AssertionError(f"unexpected repository composition for {bucket_id}")

    registration = build_ledger_rule_apply_registration(
        build_ledger_rule_apply_definition(unused_ports, unused_repository)
    )
    projected = registration.result_projector
    assert projected is not None
    stored = LedgerRuleApplyExecutionResult(projection=refusal)
    assert projected(stored, receipt) == refusal
    with pytest.raises(ValueError, match="invalid ledger rule apply result"):
        projected(refusal, receipt)

    wrong_effect = receipt.model_copy(update={"effect": OperationEffect.UPDATED})
    with pytest.raises(ValueError, match="incompatible terminal receipt"):
        projected(stored, wrong_effect)


class _FenceProbe:
    def __init__(self) -> None:
        self.active = False
        self.entries = 0

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        assert not self.active
        self.active = True
        self.entries += 1
        try:
            yield
        finally:
            self.active = False


class _EventHistoryProbe:
    def __init__(self, fence: _FenceProbe) -> None:
        self._fence = fence
        self.reads = 0

    def exists(self) -> bool:
        return False

    def load(self) -> BucketEventHistoryCatalogue:
        return BucketEventHistoryCatalogue()

    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        raise AssertionError(f"unexpected standalone event save: {catalogue!r}")

    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        assert not self._fence.active
        _ = catalogue, expected_revision_id
        return cast(SecureObjectWrite, object())

    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        assert not self._fence.active, "retry reads must happen outside the co-commit fence"
        self.reads += 1
        return BucketEventHistoryCatalogue(), f"event-revision-{self.reads}"


class _ConflictThenWriteProbe:
    def __init__(self, fence: _FenceProbe, *, fail_after_mutation: bool) -> None:
        self._fence = fence
        self._fail_after_mutation = fail_after_mutation
        self.calls = 0
        self.mutated = False
        self.bucket_id = str(_PROFILE)

    def exists(self) -> bool:
        return False

    def load(self) -> TransactionCatalogue:
        return TransactionCatalogue()

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        _ = start, end
        return TransactionCatalogue()

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        _ = tuple(transaction_ids)
        return TransactionCatalogue()

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        _ = start, end
        return LedgerDatePartition(in_window=TransactionCatalogue(), index_complete=True)

    def save(self, catalogue: TransactionCatalogue) -> None:
        raise AssertionError(f"unexpected standalone transaction save: {catalogue!r}")

    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        assert self._fence.active, "the co-commit must run inside the operation fence"
        _ = catalogue, extra_writes
        self.calls += 1
        if self.calls == 1:
            raise LedgerPersistenceConflictError("test revision changed before the co-commit")
        self.mutated = True
        if self._fail_after_mutation:
            raise ValueError("test repository raised after a possible partial mutation")

    def replace_if_current_with_secure_object_writes(
        self,
        current: Transaction,
        replacement: Transaction,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        _ = current, replacement, extra_writes
        raise AssertionError("unexpected baseline-guarded transaction write")


class _EffectProbe:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


@pytest.mark.parametrize("fail_after_mutation", [False, True])
def test_canonical_co_commit_retries_outside_fence_and_preserves_uncertain_write(
    fail_after_mutation: bool,
) -> None:
    fence = _FenceProbe()
    events = _EffectProbe()
    event_repository = _EventHistoryProbe(fence)
    backing_repository = _ConflictThenWriteProbe(fence, fail_after_mutation=fail_after_mutation)
    tracker = LedgerCommitAttemptTracker()
    tracked_repository = TrackedLedgerTransactionRepository(backing_repository, tracker)
    assert not isinstance(tracked_repository, RevisionGuardedTransactionCatalogueCoCommitWriterProtocol)
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(cancellation=fence, events=events),
    )

    def canonical_co_commit() -> None:
        save_transaction_catalogue_and_events(
            transaction_repository=tracked_repository,
            event_repository=cast(BucketEventHistoryCoCommitWriterProtocol, event_repository),
            catalogue=TransactionCatalogue(),
            events=(),
        )

    if fail_after_mutation:
        with pytest.raises(ValueError, match="after a possible partial mutation"):
            asyncio.run(
                run_with_ledger_commit_fence(
                    canonical_co_commit,
                    tracker=tracker,
                    context=context,
                    task_name="ledger.rule.apply-test",
                )
            )
    else:
        asyncio.run(
            run_with_ledger_commit_fence(
                canonical_co_commit,
                tracker=tracker,
                context=context,
                task_name="ledger.rule.apply-test",
            )
        )

    assert backing_repository.calls == 2
    assert backing_repository.mutated is True
    assert event_repository.reads == 2
    assert fence.entries == 2
    assert fence.active is False
    assert tracker.attempt_count == 2
    assert tracker.confirmed_write is (not fail_after_mutation)
    assert tracker.has_uncertain_write is fail_after_mutation
    assert is_guaranteed_prewrite_failure(tracker) is False
    assert events.effects == (
        [OperationEffect.UNKNOWN, OperationEffect.NONE, OperationEffect.UNKNOWN]
        if fail_after_mutation
        else [OperationEffect.UNKNOWN, OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    )


class _RuleRepositoryProbe:
    def __init__(self, fence: _FenceProbe) -> None:
        self._fence = fence
        self.saved: list[LedgerClassificationRule] = []

    def save(self, payload: LedgerClassificationRule) -> None:
        assert self._fence.active, "the encrypted rule save must run inside the operation fence"
        self.saved.append(payload)

    def list_rules(self) -> tuple[LedgerClassificationRule, ...]:
        return tuple(self.saved)


def test_rule_add_save_uses_the_same_precise_writer_fence() -> None:
    fence = _FenceProbe()
    events = _EffectProbe()
    repository = _RuleRepositoryProbe(fence)
    tracker = LedgerCommitAttemptTracker()
    tracked_repository = _TrackedRuleRepository(repository, tracker)
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(cancellation=fence, events=events),
    )

    asyncio.run(
        run_with_ledger_commit_fence(
            lambda: tracked_repository.save(_rule()),
            tracker=tracker,
            context=context,
            task_name="ledger.rule.add-test",
        )
    )

    assert len(repository.saved) == 1
    assert fence.entries == 1
    assert fence.active is False
    assert tracker.confirmed_write is True
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
