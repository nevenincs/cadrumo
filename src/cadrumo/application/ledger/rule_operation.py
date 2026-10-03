"""Registered exact-profile access to canonical ledger classification rules."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from uuid import UUID

from pydantic import BaseModel, ValidationError

from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.categories.spending_category_catalogue import require_spending_category, spending_category_tokens
from ...domain.transactions.classification_rule import LedgerClassificationRule
from ...domain.transactions.errors import ClassificationRuleError, TransactionValidationError
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory, require_exact_ledger_action_ports
from .actions_classification import (
    ClassificationRulePlan,
    ClassificationRulePlanRow,
    add_classification_rule,
    apply_classification_rule_match,
    plan_classification_rules,
)
from .commit_fence import (
    LedgerCommitAttemptTracker,
    TrackedLedgerTransactionRepository,
    is_guaranteed_prewrite_failure,
    run_with_ledger_commit_fence,
)
from .models import ApplyRulesAppliedRow, ApplyRulesResult
from .read_access import resolve_ledger_commit_access, resolve_ledger_read_access
from .rule_contracts import (
    LedgerRuleAddExecutionResult,
    LedgerRuleAddProjection,
    LedgerRuleAddRequest,
    LedgerRuleApplyExecutionResult,
    LedgerRuleApplyProjection,
    LedgerRuleApplyRequest,
    LedgerRuleListProjection,
    LedgerRuleListRequest,
    LedgerRuleRowProjection,
    RuleValidationCode,
)
from .rule_repository import LedgerClassificationRuleRepositoryFactory, LedgerClassificationRuleRepositoryProtocol
from .rule_results import (
    LEDGER_RULE_VALIDATION_REFUSAL_CODE,
    build_rule_apply_plan_projection,
    build_rule_apply_result_projection,
    build_rule_apply_validation_projection,
    build_rule_dry_run_projection,
    build_rule_validation_messages,
    project_ledger_rule_add_result,
    project_ledger_rule_apply_result,
    publish_rule_apply_refusal,
)

LEDGER_RULE_ADD_OPERATION_DEFINITION_ID = "ledger.rule.add"
LEDGER_RULE_LIST_OPERATION_DEFINITION_ID = "ledger.rule.list"
LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID = "ledger.rule.apply"


class _TrackedRuleRepository:
    """Track the canonical encrypted rule save without replacing its behavior."""

    def __init__(
        self,
        repository: LedgerClassificationRuleRepositoryProtocol,
        tracker: LedgerCommitAttemptTracker,
    ) -> None:
        self._repository = repository
        self._tracker = tracker

    def save(self, payload: LedgerClassificationRule) -> None:
        self._tracker.call_writer(lambda: self._repository.save(payload))

    def list_rules(self) -> tuple[LedgerClassificationRule, ...]:
        return self._repository.list_rules()


async def _prepare_rule_add(
    payload: LedgerRuleAddRequest,
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    context: OperationExecutorContext,
) -> tuple[LedgerClassificationRule, str | None, str] | OperationRefusalEvidence:
    if not payload.description_pattern.strip():
        projection = _add_validation_projection(
            payload.profile_id,
            code="empty_pattern",
            error=ValueError("description pattern must not be empty or whitespace"),
        )
        return await _publish_add_refusal(context, projection)

    try:
        category_id = _resolve_category(payload.category_id, operation=operation)
    except RegistryValidationError as error:
        with validating_governed_facts(operation):
            examples = spending_category_tokens(authority=operation)
        projection = _add_validation_projection(
            payload.profile_id,
            code="category",
            error=error,
            category_example=examples[0].value if examples else None,
        )
        return await _publish_add_refusal(context, projection)

    actor = payload.actor or bucket_id or "operator"
    try:
        candidate = LedgerClassificationRule.create(
            description_pattern=payload.description_pattern,
            classification=payload.classification,
            category_id=category_id,
            priority=payload.priority,
            actor=actor,
        )
        LedgerRuleRowProjection.from_rule(candidate)
    except (ClassificationRuleError, ValidationError, ValueError) as error:
        projection = _add_validation_projection(payload.profile_id, code="invalid_pattern", error=error)
        return await _publish_add_refusal(context, projection)
    return candidate, category_id, actor


async def _persist_rule_add(
    payload: LedgerRuleAddRequest,
    *,
    bucket_id: str,
    category_id: str | None,
    actor: str,
    repository_factory: LedgerClassificationRuleRepositoryFactory,
    context: OperationExecutorContext,
) -> tuple[LedgerClassificationRule, LedgerCommitAttemptTracker] | OperationRefusalEvidence:
    repository = await asyncio.to_thread(repository_factory, bucket_id=bucket_id)
    tracker = LedgerCommitAttemptTracker()
    tracked_repository = _TrackedRuleRepository(repository, tracker)

    def add() -> LedgerClassificationRule:
        return add_classification_rule(
            bucket_id=bucket_id,
            description_pattern=payload.description_pattern,
            classification=payload.classification,
            category_id=category_id,
            priority=payload.priority,
            actor=actor,
            rule_repository=tracked_repository,
        )

    try:
        rule = await run_with_ledger_commit_fence(
            add,
            tracker=tracker,
            context=context,
            task_name=LEDGER_RULE_ADD_OPERATION_DEFINITION_ID,
        )
    except (ClassificationRuleError, ValidationError, ValueError) as error:
        if not is_guaranteed_prewrite_failure(tracker):
            raise
        refusal = _add_validation_projection(payload.profile_id, code="invalid_pattern", error=error)
        return await _publish_add_refusal(context, refusal)
    return rule, tracker


def _require_candidate_match(candidate: LedgerClassificationRule, saved: LedgerClassificationRule) -> None:
    if (
        saved.rule_id != candidate.rule_id
        or saved.description_pattern != candidate.description_pattern
        or saved.classification is not candidate.classification
        or saved.category_id != candidate.category_id
        or saved.priority != candidate.priority
        or saved.actor != candidate.actor
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


class LedgerRuleAddExecutor:
    """Create one encrypted profile rule through the canonical action service."""

    def __init__(self, repository_factory: LedgerClassificationRuleRepositoryFactory) -> None:
        """Bind the canonical encrypted rule repository factory."""
        self._repository_factory = repository_factory

    async def execute(
        self,
        request: OperationRequest[LedgerRuleAddRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Validate and persist one rule, returning its complete encrypted row."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_operation_identity(request, context, LEDGER_RULE_ADD_OPERATION_DEFINITION_ID, payload.profile_id)
        await context.events.phase(LEDGER_RULE_ADD_OPERATION_DEFINITION_ID)
        operation: PinnedAuthorityOperation = context.authority_operation
        prepared = await _prepare_rule_add(payload, bucket_id=bucket_id, operation=operation, context=context)
        if isinstance(prepared, OperationRefusalEvidence):
            return prepared
        candidate, category_id, actor = prepared

        saved = await _persist_rule_add(
            payload,
            bucket_id=bucket_id,
            category_id=category_id,
            actor=actor,
            repository_factory=self._repository_factory,
            context=context,
        )
        if isinstance(saved, OperationRefusalEvidence):
            return saved
        rule, tracker = saved
        if not tracker.confirmed_write:
            raise InternalInvariantError("canonical rule add returned without entering its encrypted save boundary")
        _require_candidate_match(candidate, rule)
        projection = LedgerRuleAddProjection(
            profile_id=payload.profile_id,
            outcome="added",
            rule=LedgerRuleRowProjection.from_rule(rule),
        )
        return await context.operands.put(LedgerRuleAddExecutionResult(projection=projection), written_at=now())


class LedgerRuleListExecutor:
    """Read complete rules from one injected encrypted profile repository."""

    def __init__(self, repository_factory: LedgerClassificationRuleRepositoryFactory) -> None:
        """Bind the canonical encrypted rule repository factory."""
        self._repository_factory = repository_factory

    async def execute(
        self,
        request: OperationRequest[LedgerRuleListRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Read the complete profile-local rule list in canonical order."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_operation_identity(request, context, LEDGER_RULE_LIST_OPERATION_DEFINITION_ID, payload.profile_id)
        await context.events.phase(LEDGER_RULE_LIST_OPERATION_DEFINITION_ID)
        repository = await asyncio.to_thread(self._repository_factory, bucket_id=bucket_id)
        rules = await asyncio.to_thread(repository.list_rules)
        projection = LedgerRuleListProjection(
            profile_id=payload.profile_id,
            rules=tuple(LedgerRuleRowProjection.from_rule(rule) for rule in rules),
        )
        await context.events.effect(OperationEffect.NONE)
        return await context.operands.put(projection, written_at=now())


class LedgerRuleApplyExecutor:
    """Preview or apply canonical matches with a separate fence per co-commit."""

    def __init__(
        self,
        ports_factory: LedgerActionPortsFactory,
        repository_factory: LedgerClassificationRuleRepositoryFactory,
    ) -> None:
        """Bind exact-profile canonical action ports and encrypted rule storage."""
        self._ports_factory = ports_factory
        self._repository_factory = repository_factory

    async def execute(
        self,
        request: OperationRequest[LedgerRuleApplyRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Preview canonical matches or apply each match behind its write fence."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_operation_identity(request, context, LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID, payload.profile_id)
        await context.events.phase(LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID)
        operation: PinnedAuthorityOperation = context.authority_operation
        ports, repository = await asyncio.gather(
            asyncio.to_thread(self._ports_factory, bucket_id=bucket_id, operation=operation),
            asyncio.to_thread(self._repository_factory, bucket_id=bucket_id),
        )
        require_exact_ledger_action_ports(ports, bucket_id=bucket_id, operation=operation)
        plan = await asyncio.to_thread(
            plan_classification_rules,
            bucket_id=bucket_id,
            reaffirm=payload.reaffirm,
            ports=ports,
            rule_repository=repository,
        )

        if payload.dry_run:
            projection = build_rule_dry_run_projection(payload.profile_id, plan)
            await context.events.effect(OperationEffect.NONE)
            return await context.operands.put(LedgerRuleApplyExecutionResult(projection=projection), written_at=now())

        # Validate every promised live row/count before any transaction write.
        build_rule_apply_plan_projection(payload.profile_id, plan, bucket_event_count=0)
        actor = payload.actor or bucket_id or "operator"
        prepared_result = await _apply_rule_matches(
            plan,
            payload,
            ports=ports,
            bucket_id=bucket_id,
            actor=actor,
            context=context,
        )
        if isinstance(prepared_result, OperationRefusalEvidence):
            return prepared_result
        canonical_result, any_committed_write = prepared_result
        if bool(canonical_result.bucket_event_ids) != any_committed_write:
            raise InternalInvariantError(
                "classification-rule apply co-commit state disagrees with its canonical events"
            )
        effect = OperationEffect.UPDATED if any_committed_write else OperationEffect.NONE
        await context.events.effect(effect)
        projection = build_rule_apply_result_projection(
            payload.profile_id,
            canonical_result,
            bucket_event_count=len(canonical_result.bucket_event_ids),
        )
        return await context.operands.put(LedgerRuleApplyExecutionResult(projection=projection), written_at=now())


async def _apply_rule_matches(
    plan: ClassificationRulePlan,
    payload: LedgerRuleApplyRequest,
    *,
    ports: LedgerActionPorts,
    bucket_id: str,
    actor: str,
    context: OperationExecutorContext,
) -> tuple[ApplyRulesResult, bool] | OperationRefusalEvidence:
    applied_rows: list[ApplyRulesAppliedRow] = []
    bucket_event_ids: list[str] = []
    any_committed_write = False
    for index, row in enumerate(plan.matches):
        committed = await _commit_rule_apply_match(
            row,
            index=index,
            reaffirm=payload.reaffirm,
            ports=ports,
            bucket_id=bucket_id,
            actor=actor,
            prior_commit=any_committed_write,
            profile_id=payload.profile_id,
            context=context,
        )
        if isinstance(committed, OperationRefusalEvidence):
            return committed
        applied_row, event_ids, confirmed_write = committed
        applied_rows.append(applied_row)
        bucket_event_ids.extend(event_ids)
        any_committed_write = any_committed_write or confirmed_write
    result = ApplyRulesResult(
        rules_evaluated=plan.rules_evaluated,
        transactions_scanned=plan.transactions_scanned,
        matched=len(applied_rows),
        skipped_already_classified=plan.skipped_already_classified,
        no_match=plan.no_match,
        applied=tuple(applied_rows),
        bucket_event_ids=tuple(bucket_event_ids),
    )
    return result, any_committed_write


async def _commit_rule_apply_match(
    row: ClassificationRulePlanRow,
    *,
    index: int,
    reaffirm: bool,
    ports: LedgerActionPorts,
    bucket_id: str,
    actor: str,
    prior_commit: bool,
    profile_id: UUID,
    context: OperationExecutorContext,
) -> tuple[ApplyRulesAppliedRow, tuple[str, ...], bool] | OperationRefusalEvidence:
    tracker = LedgerCommitAttemptTracker()
    commit_ports = replace(
        ports,
        transaction_repository=TrackedLedgerTransactionRepository(ports.transaction_repository, tracker),
    )
    try:
        result = await run_with_ledger_commit_fence(
            lambda: apply_classification_rule_match(
                bucket_id=bucket_id,
                row=row,
                actor=actor,
                source_command="aeat app ledger rule apply",
                reaffirm=reaffirm,
                ports=commit_ports,
            ),
            tracker=tracker,
            context=context,
            task_name=f"{LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID}-row-{index + 1}",
            prior_commit=prior_commit,
        )
    except (TransactionValidationError, RegistryValidationError, ValidationError, ValueError) as error:
        if not is_guaranteed_prewrite_failure(tracker):
            raise
        effect = OperationEffect.PARTIAL if prior_commit else OperationEffect.NONE
        await context.events.effect(effect)
        refusal = build_rule_apply_validation_projection(profile_id, error)
        return await publish_rule_apply_refusal(context, refusal)
    if (
        result.ref.bucket_id != bucket_id
        or result.ref.transaction_id != row.transaction_id
        or result.transaction.transaction_id != row.transaction_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    applied = ApplyRulesAppliedRow(
        transaction_id=row.transaction_id,
        matched_rule_id=row.matched_rule_id,
        classification=row.classification,
    )
    return applied, result.bucket_event_ids, tracker.confirmed_write


def _require_operation_identity[RequestPayloadT: BaseModel](
    request: OperationRequest[RequestPayloadT],
    context: OperationExecutorContext,
    definition_id: str,
    profile_id: UUID,
) -> None:
    """Refuse request, subject, active-profile, or owner identity substitution."""
    if request.definition_id != definition_id or context.identity.definition_id != definition_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    require_operation_profile(request, context, profile_id)


def _resolve_category(category_id: str | None, *, operation: PinnedAuthorityOperation) -> str | None:
    """Match the existing CLI trim/blank behavior under the retained authority."""
    trimmed = category_id.strip() if category_id is not None else ""
    if not trimmed:
        return None
    with validating_governed_facts(operation):
        return require_spending_category(trimmed, authority=operation).value


def _add_validation_projection(
    profile_id: UUID,
    *,
    code: RuleValidationCode,
    error: Exception,
    category_example: str | None = None,
) -> LedgerRuleAddProjection:
    """Construct one private refusal detail, never a public successful rule row."""
    return LedgerRuleAddProjection(
        profile_id=profile_id,
        outcome="validation_error",
        validation_code=code,
        validation_messages=build_rule_validation_messages(error),
        category_example=category_example,
    )


async def _publish_add_refusal(
    context: OperationExecutorContext,
    projection: LedgerRuleAddProjection,
) -> OperationRefusalEvidence:
    await context.events.effect(OperationEffect.NONE)
    detail_ref = await context.operands.put(LedgerRuleAddExecutionResult(projection=projection), written_at=now())
    return OperationRefusalEvidence(
        refusal_code=LEDGER_RULE_VALIDATION_REFUSAL_CODE,
        detail_ref=detail_ref,
    )


def _definition[RequestT: BaseModel, ResultT: BaseModel, ExecutorT](
    *,
    definition_id: str,
    request_type: type[RequestT],
    result_type: type[ResultT],
    executor_type: type[ExecutorT],
    build: Callable[[], ExecutorT],
    effects: frozenset[OperationEffect],
    refusal_detail_codes: frozenset[str] = frozenset({LEDGER_RULE_VALIDATION_REFUSAL_CODE}),
) -> OperationDefinition:
    """Declare one CLI-only, exact-profile recorded rule operation."""
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_type=executor_type,
        build=build,
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=effects,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=refusal_detail_codes,
    )


def build_ledger_rule_add_definition(
    repository_factory: LedgerClassificationRuleRepositoryFactory,
) -> OperationDefinition:
    """Declare one secure rule add under an exact-profile all-period commit grant."""
    return _definition(
        definition_id=LEDGER_RULE_ADD_OPERATION_DEFINITION_ID,
        request_type=LedgerRuleAddRequest,
        result_type=LedgerRuleAddExecutionResult,
        executor_type=LedgerRuleAddExecutor,
        build=lambda: LedgerRuleAddExecutor(repository_factory),
        effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
    )


def build_ledger_rule_list_definition(
    repository_factory: LedgerClassificationRuleRepositoryFactory,
) -> OperationDefinition:
    """Declare one full profile-local rule list with no mutation capability."""
    return _definition(
        definition_id=LEDGER_RULE_LIST_OPERATION_DEFINITION_ID,
        request_type=LedgerRuleListRequest,
        result_type=LedgerRuleListProjection,
        executor_type=LedgerRuleListExecutor,
        build=lambda: LedgerRuleListExecutor(repository_factory),
        effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
        refusal_detail_codes=frozenset(),
    )


def build_ledger_rule_apply_definition(
    ports_factory: LedgerActionPortsFactory,
    repository_factory: LedgerClassificationRuleRepositoryFactory,
) -> OperationDefinition:
    """Declare canonical preview and per-transaction rule application."""
    return _definition(
        definition_id=LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID,
        request_type=LedgerRuleApplyRequest,
        result_type=LedgerRuleApplyExecutionResult,
        executor_type=LedgerRuleApplyExecutor,
        build=lambda: LedgerRuleApplyExecutor(ports_factory, repository_factory),
        effects=frozenset(
            {OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.PARTIAL, OperationEffect.UNKNOWN}
        ),
    )


def _resolve_rule_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    profile_id: UUID,
    definition_id: str,
    commit: bool,
) -> ResolvedOperationAccess:
    if request.definition_id != definition_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolve = resolve_ledger_commit_access if commit else resolve_ledger_read_access
    return resolve(request, context, profile_id=profile_id, periods=frozenset())


def resolve_ledger_rule_add_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve the caller's whole-profile add capability and required commit action."""
    if not isinstance(request.payload, LedgerRuleAddRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _resolve_rule_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        definition_id=LEDGER_RULE_ADD_OPERATION_DEFINITION_ID,
        commit=True,
    )


def resolve_ledger_rule_list_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve the caller's whole-profile read-only rule-list capability."""
    if not isinstance(request.payload, LedgerRuleListRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _resolve_rule_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        definition_id=LEDGER_RULE_LIST_OPERATION_DEFINITION_ID,
        commit=False,
    )


def resolve_ledger_rule_apply_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve whole-profile rule apply, requiring commit except for dry-run."""
    if not isinstance(request.payload, LedgerRuleApplyRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _resolve_rule_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        definition_id=LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID,
        commit=not request.payload.dry_run,
    )


def build_ledger_rule_add_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind add request/result schemas and exact-profile admission policy."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerRuleAddProjection,
        result_projector=project_ledger_rule_add_result,
        access_resolver=resolve_ledger_rule_add_access,
    )


def build_ledger_rule_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind list request/result schemas and read-only admission policy."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerRuleListProjection,
        access_resolver=resolve_ledger_rule_list_access,
    )


def build_ledger_rule_apply_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind apply request/result schemas and dry-run-aware admission policy."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerRuleApplyProjection,
        result_projector=project_ledger_rule_apply_result,
        access_resolver=resolve_ledger_rule_apply_access,
    )


__all__ = [
    "LEDGER_RULE_ADD_OPERATION_DEFINITION_ID",
    "LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID",
    "LEDGER_RULE_LIST_OPERATION_DEFINITION_ID",
    "LedgerRuleAddExecutor",
    "LedgerRuleApplyExecutor",
    "LedgerRuleListExecutor",
    "build_ledger_rule_add_definition",
    "build_ledger_rule_add_registration",
    "build_ledger_rule_apply_definition",
    "build_ledger_rule_apply_registration",
    "build_ledger_rule_list_definition",
    "build_ledger_rule_list_registration",
    "resolve_ledger_rule_add_access",
    "resolve_ledger_rule_apply_access",
    "resolve_ledger_rule_list_access",
]
