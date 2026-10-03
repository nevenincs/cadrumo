"""Registered exact-profile access to canonical ledger classification rules."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, ValidationError, model_validator

from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import InternalInvariantError
from ...core.hex import Hex64Str
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.categories.spending_category_catalogue import require_spending_category, spending_category_tokens
from ...domain.transactions.classification_rule import (
    LedgerClassificationRule,
    RuleActor,
    RuleDescriptionPattern,
    RulePriority,
)
from ...domain.transactions.enums import BusinessClassification
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
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory
from .actions_classification import (
    ClassificationRulePlan,
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
from .read_access import resolve_ledger_read_access
from .rule_repository import LedgerClassificationRuleRepositoryFactory, LedgerClassificationRuleRepositoryProtocol

LEDGER_RULE_ADD_OPERATION_DEFINITION_ID = "ledger.rule.add"
LEDGER_RULE_LIST_OPERATION_DEFINITION_ID = "ledger.rule.list"
LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID = "ledger.rule.apply"
LEDGER_RULE_VALIDATION_REFUSAL_CODE = "REFUSED_CLI_VALIDATION_BOUNDARY"

_MAX_VALIDATION_MESSAGES = 32
_VALIDATION_MESSAGE = Annotated[str, Field(min_length=1, max_length=2048)]
_VALIDATION_MESSAGES = Annotated[tuple[_VALIDATION_MESSAGE, ...], Field(max_length=_MAX_VALIDATION_MESSAGES)]
_RuleValidationCode = Literal["empty_pattern", "invalid_pattern", "category", "invalid_command"]


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


class LedgerRuleRowProjection(BaseModel):
    """Complete stored rule projection used by add, list, and apply matching."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    rule_id: Hex64Str
    description_pattern: RuleDescriptionPattern
    classification: BusinessClassification
    category_id: str | None = None
    priority: RulePriority
    actor: RuleActor
    created_at: datetime

    @model_validator(mode="after")
    def _canonical_rule(self) -> LedgerRuleRowProjection:
        """Validate canonical rule meaning without custom public field schemas."""
        LedgerClassificationRule.model_validate(self.model_dump(mode="python"))
        return self

    @classmethod
    def from_rule(cls, rule: LedgerClassificationRule) -> LedgerRuleRowProjection:
        """Copy every canonical persisted field without changing its meaning."""
        return cls(
            rule_id=str(rule.rule_id),
            description_pattern=rule.description_pattern,
            classification=rule.classification,
            category_id=rule.category_id,
            priority=rule.priority,
            actor=rule.actor,
            created_at=rule.created_at,
        )


class LedgerRuleAddRequest(BaseModel):
    """Private secure-reference input for ``ledger.rule.add``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    # Keep this as a plain string at the operation boundary so an empty or
    # whitespace-only value reaches the canonical pre-write refusal path and
    # retains the existing CLI's instructive message.
    description_pattern: str
    classification: BusinessClassification
    category_id: str | None = None
    priority: RulePriority = 100
    actor: str | None = None


class LedgerRuleAddProjection(BaseModel):
    """Complete saved rule or bounded validation refusal for rule add."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    outcome: Literal["added", "validation_error"]
    rule: LedgerRuleRowProjection | None = None
    validation_code: _RuleValidationCode | None = None
    validation_messages: _VALIDATION_MESSAGES = ()
    category_example: str | None = None

    @model_validator(mode="after")
    def _complete_outcome(self) -> LedgerRuleAddProjection:
        if self.outcome == "added":
            if (
                self.rule is None
                or self.validation_code is not None
                or self.validation_messages
                or self.category_example
            ):
                raise ValueError("added rule projection requires one rule and no refusal details")
        elif (
            self.rule is not None
            or self.validation_code is None
            or not self.validation_messages
            or (self.validation_code == "category") != (self.category_example is not None)
        ):
            raise ValueError("rule add validation projection requires only bounded refusal details")
        return self


class LedgerRuleListRequest(BaseModel):
    """Credential-free selector for the active profile's complete rule list."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class LedgerRuleListProjection(BaseModel):
    """All stored rules in the repository's canonical evaluation order."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    rules: tuple[LedgerRuleRowProjection, ...]


class LedgerRuleApplyRequest(BaseModel):
    """Private exact-profile rule apply or non-mutating preview request."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    reaffirm: bool = False
    dry_run: bool = False
    actor: str | None = None


class LedgerRuleApplyMatchProjection(BaseModel):
    """One exact dry-run match, including the existing raw description field."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: TransactionId
    description: str
    matched_rule_id: Hex64Str
    classification: BusinessClassification


class LedgerRuleApplyAppliedProjection(BaseModel):
    """One transaction the canonical rule engine reports as applied."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: TransactionId
    matched_rule_id: Hex64Str
    classification: BusinessClassification


class LedgerRuleApplyProjection(BaseModel):
    """Full CLI payload semantics plus the worker-owned profile/effect evidence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    outcome: Literal["dry_run", "applied", "validation_error"]
    # Dry-run payload fields; kept identical to the existing CLI schema.
    dry_run: Literal[True] | None = None
    would_match: tuple[LedgerRuleApplyMatchProjection, ...] | None = None
    count: NonNegativeInt | None = None
    # Successful live-apply payload fields; kept identical to the existing CLI schema.
    rules_evaluated: NonNegativeInt | None = None
    transactions_scanned: NonNegativeInt | None = None
    matched: NonNegativeInt | None = None
    skipped_already_classified: NonNegativeInt | None = None
    no_match: NonNegativeInt | None = None
    applied: tuple[LedgerRuleApplyAppliedProjection, ...] | None = None
    # Internal operation correlation; the CLI renderer deliberately does not emit it.
    bucket_event_count: NonNegativeInt = 0
    validation_code: _RuleValidationCode | None = None
    validation_messages: _VALIDATION_MESSAGES = ()

    @model_validator(mode="after")
    def _complete_outcome(self) -> LedgerRuleApplyProjection:
        dry_fields = (self.dry_run, self.would_match, self.count)
        live_fields = (
            self.rules_evaluated,
            self.transactions_scanned,
            self.matched,
            self.skipped_already_classified,
            self.no_match,
            self.applied,
        )
        if self.outcome == "dry_run":
            if (
                self.dry_run is not True
                or self.would_match is None
                or self.count != len(self.would_match)
                or any(value is not None for value in live_fields)
                or self.bucket_event_count
                or self.validation_code is not None
                or self.validation_messages
            ):
                raise ValueError("dry-run projection requires only a no-effect match preview")
        elif self.outcome == "applied":
            if (
                any(value is not None for value in dry_fields)
                or any(value is None for value in live_fields)
                or self.matched != len(self.applied or ())
                or self.validation_code is not None
                or self.validation_messages
            ):
                raise ValueError("applied projection requires complete live counts and applied rows")
        elif (
            any(value is not None for value in dry_fields + live_fields)
            or self.bucket_event_count
            or self.validation_code is None
            or not self.validation_messages
        ):
            raise ValueError("rule apply validation projection requires only bounded refusal details")
        return self


class LedgerRuleAddExecutionResult(BaseModel):
    """Encrypted add outcome released only through its validated terminal receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: LedgerRuleAddProjection


class LedgerRuleApplyExecutionResult(BaseModel):
    """Encrypted apply outcome, including refusal evidence requiring receipt validation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: LedgerRuleApplyProjection


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
        _require_operation_identity(request, context, LEDGER_RULE_ADD_OPERATION_DEFINITION_ID, bucket_id)
        await context.events.phase(LEDGER_RULE_ADD_OPERATION_DEFINITION_ID)
        operation: PinnedAuthorityOperation = context.authority_operation

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
            # Validate the canonical regex and the full result before the durable
            # rule-store call; the service repeats the same domain construction.
            candidate = LedgerClassificationRule.create(
                description_pattern=payload.description_pattern,
                classification=payload.classification,
                category_id=category_id,
                priority=payload.priority,
                actor=actor,
            )
            LedgerRuleRowProjection.from_rule(candidate)
        except (ClassificationRuleError, ValidationError, ValueError) as error:
            projection = _add_validation_projection(
                payload.profile_id,
                code="invalid_pattern",
                error=error,
            )
            return await _publish_add_refusal(context, projection)

        repository = await asyncio.to_thread(self._repository_factory, bucket_id=bucket_id)
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

        if not tracker.confirmed_write:
            raise InternalInvariantError("canonical rule add returned without entering its encrypted save boundary")
        if (
            rule.rule_id != candidate.rule_id
            or rule.description_pattern != candidate.description_pattern
            or rule.classification is not candidate.classification
            or rule.category_id != candidate.category_id
            or rule.priority != candidate.priority
            or rule.actor != candidate.actor
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
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
        _require_operation_identity(request, context, LEDGER_RULE_LIST_OPERATION_DEFINITION_ID, bucket_id)
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
        _require_operation_identity(request, context, LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID, bucket_id)
        await context.events.phase(LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID)
        operation: PinnedAuthorityOperation = context.authority_operation
        ports, repository = await asyncio.gather(
            asyncio.to_thread(self._ports_factory, bucket_id=bucket_id, operation=operation),
            asyncio.to_thread(self._repository_factory, bucket_id=bucket_id),
        )
        _require_exact_ports(ports, bucket_id=bucket_id, operation=operation)
        plan = await asyncio.to_thread(
            plan_classification_rules,
            bucket_id=bucket_id,
            reaffirm=payload.reaffirm,
            ports=ports,
            rule_repository=repository,
        )

        if payload.dry_run:
            projection = _dry_run_projection(payload.profile_id, plan)
            await context.events.effect(OperationEffect.NONE)
            return await context.operands.put(LedgerRuleApplyExecutionResult(projection=projection), written_at=now())

        # Validate every promised live row/count before any transaction write.
        _apply_plan_projection(payload.profile_id, plan, bucket_event_count=0)
        actor = payload.actor or bucket_id or "operator"
        applied_rows: list[ApplyRulesAppliedRow] = []
        bucket_event_ids: list[str] = []
        any_committed_write = False
        for index, row in enumerate(plan.matches):
            tracker = LedgerCommitAttemptTracker()
            commit_ports = replace(
                ports,
                transaction_repository=TrackedLedgerTransactionRepository(ports.transaction_repository, tracker),
            )
            try:
                result = await run_with_ledger_commit_fence(
                    lambda row=row, commit_ports=commit_ports: apply_classification_rule_match(
                        bucket_id=bucket_id,
                        row=row,
                        actor=actor,
                        source_command="aeat app ledger rule apply",
                        reaffirm=payload.reaffirm,
                        ports=commit_ports,
                    ),
                    tracker=tracker,
                    context=context,
                    task_name=f"{LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID}-row-{index + 1}",
                    prior_commit=any_committed_write,
                )
            except (TransactionValidationError, RegistryValidationError, ValidationError, ValueError) as error:
                if not is_guaranteed_prewrite_failure(tracker):
                    raise
                effect = OperationEffect.PARTIAL if any_committed_write else OperationEffect.NONE
                await context.events.effect(effect)
                refusal = _apply_validation_projection(payload.profile_id, error)
                return await _publish_apply_refusal(context, refusal)

            any_committed_write = any_committed_write or tracker.confirmed_write

            if (
                result.ref.bucket_id != bucket_id
                or result.ref.transaction_id != row.transaction_id
                or result.transaction.transaction_id != row.transaction_id
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

            bucket_event_ids.extend(result.bucket_event_ids)
            applied_rows.append(
                ApplyRulesAppliedRow(
                    transaction_id=row.transaction_id,
                    matched_rule_id=row.matched_rule_id,
                    classification=row.classification,
                ),
            )

        canonical_result = ApplyRulesResult(
            rules_evaluated=plan.rules_evaluated,
            transactions_scanned=plan.transactions_scanned,
            matched=len(applied_rows),
            skipped_already_classified=plan.skipped_already_classified,
            no_match=plan.no_match,
            applied=tuple(applied_rows),
            bucket_event_ids=tuple(bucket_event_ids),
        )
        if bool(canonical_result.bucket_event_ids) != any_committed_write:
            raise InternalInvariantError(
                "classification-rule apply co-commit state disagrees with its canonical events"
            )
        effect = OperationEffect.UPDATED if any_committed_write else OperationEffect.NONE
        await context.events.effect(effect)
        projection = _apply_result_projection(
            payload.profile_id,
            canonical_result,
            bucket_event_count=len(canonical_result.bucket_event_ids),
        )
        return await context.operands.put(LedgerRuleApplyExecutionResult(projection=projection), written_at=now())


def _require_operation_identity[RequestPayloadT: BaseModel](
    request: OperationRequest[RequestPayloadT],
    context: OperationExecutorContext,
    definition_id: str,
    bucket_id: str,
) -> None:
    """Refuse request, subject, active-profile, or owner identity substitution."""
    subject = profile_operation_subject(bucket_id)
    if (
        request.definition_id != definition_id
        or context.identity.definition_id != definition_id
        or request.subject_ref != subject
        or context.identity.subject_ref != subject
        or require_active_bucket_id() != bucket_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_exact_ports(
    ports: LedgerActionPorts,
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
) -> None:
    """Refuse any broad ledger capability not bound to the active request."""
    if ports.operation is not operation or ports.transaction_repository.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    for repository in (ports.invoice_repository, ports.work_unit_repository, ports.calculation_repository):
        if getattr(repository, "bucket_id", None) != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _resolve_category(category_id: str | None, *, operation: PinnedAuthorityOperation) -> str | None:
    """Match the existing CLI trim/blank behavior under the retained authority."""
    trimmed = category_id.strip() if category_id is not None else ""
    if not trimmed:
        return None
    with validating_governed_facts(operation):
        return require_spending_category(trimmed, authority=operation).value


def _validation_messages(error: Exception) -> _VALIDATION_MESSAGES:
    """Keep only bounded validation locations or the canonical error sentence."""
    messages: list[str] = []
    if isinstance(error, ValidationError):
        validation_errors = error.errors(include_input=False, include_context=False, include_url=False)
        for item in validation_errors[:_MAX_VALIDATION_MESSAGES]:
            location = item.get("loc", ())
            field_path = ".".join(str(part) for part in location if part != "__root__")
            message = str(item.get("msg", "")).removeprefix("Value error, ").strip()
            detail = f"{field_path}: {message}" if field_path else message
            if detail:
                messages.append(detail[:2048])
    else:
        detail = str(error).strip()
        if detail:
            messages.append(detail[:2048])
    if not messages:
        messages.append("ledger classification rule values did not satisfy validation")
    return tuple(messages[:_MAX_VALIDATION_MESSAGES])


def _add_validation_projection(
    profile_id: UUID,
    *,
    code: _RuleValidationCode,
    error: Exception,
    category_example: str | None = None,
) -> LedgerRuleAddProjection:
    """Construct one private refusal detail, never a public successful rule row."""
    return LedgerRuleAddProjection(
        profile_id=profile_id,
        outcome="validation_error",
        validation_code=code,
        validation_messages=_validation_messages(error),
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


def _dry_run_projection(profile_id: UUID, plan: ClassificationRulePlan) -> LedgerRuleApplyProjection:
    """Preserve every existing preview row and its exact match ordering."""
    rows = tuple(
        LedgerRuleApplyMatchProjection(
            transaction_id=row.transaction_id,
            description=row.description,
            matched_rule_id=row.matched_rule_id,
            classification=row.classification,
        )
        for row in plan.matches
    )
    return LedgerRuleApplyProjection(
        profile_id=profile_id,
        outcome="dry_run",
        dry_run=True,
        would_match=rows,
        count=len(rows),
    )


def _apply_plan_projection(
    profile_id: UUID,
    plan: ClassificationRulePlan,
    *,
    bucket_event_count: int,
) -> LedgerRuleApplyProjection:
    """Build the full live projection promised by a plan before its first write."""
    result = ApplyRulesResult(
        rules_evaluated=plan.rules_evaluated,
        transactions_scanned=plan.transactions_scanned,
        matched=len(plan.matches),
        skipped_already_classified=plan.skipped_already_classified,
        no_match=plan.no_match,
        applied=tuple(
            ApplyRulesAppliedRow(
                transaction_id=row.transaction_id,
                matched_rule_id=row.matched_rule_id,
                classification=row.classification,
            )
            for row in plan.matches
        ),
        bucket_event_ids=(),
    )
    return _apply_result_projection(profile_id, result, bucket_event_count=bucket_event_count)


def _apply_result_projection(
    profile_id: UUID,
    result: ApplyRulesResult,
    *,
    bucket_event_count: int,
) -> LedgerRuleApplyProjection:
    """Copy all current live CLI counts and applied rows into the operation DTO."""
    return LedgerRuleApplyProjection(
        profile_id=profile_id,
        outcome="applied",
        rules_evaluated=result.rules_evaluated,
        transactions_scanned=result.transactions_scanned,
        matched=result.matched,
        skipped_already_classified=result.skipped_already_classified,
        no_match=result.no_match,
        applied=tuple(
            LedgerRuleApplyAppliedProjection(
                transaction_id=row.transaction_id,
                matched_rule_id=row.matched_rule_id,
                classification=row.classification,
            )
            for row in result.applied
        ),
        bucket_event_count=bucket_event_count,
    )


def _apply_validation_projection(profile_id: UUID, error: Exception) -> LedgerRuleApplyProjection:
    """Build bounded refusal detail after a known no-write per-row validation."""
    return LedgerRuleApplyProjection(
        profile_id=profile_id,
        outcome="validation_error",
        validation_code="invalid_command",
        validation_messages=_validation_messages(error),
    )


async def _publish_apply_refusal(
    context: OperationExecutorContext,
    projection: LedgerRuleApplyProjection,
) -> OperationRefusalEvidence:
    detail_ref = await context.operands.put(LedgerRuleApplyExecutionResult(projection=projection), written_at=now())
    return OperationRefusalEvidence(
        refusal_code=LEDGER_RULE_VALIDATION_REFUSAL_CODE,
        detail_ref=detail_ref,
    )


def _project_add_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerRuleAddExecutionResult:
        raise ValueError("invalid ledger rule add result")
    projection = result.projection
    if receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id)):
        raise ValueError("ledger rule add result belongs to another profile")
    if projection.outcome == "added":
        if (
            receipt.condition is not OperationTerminalCondition.SUCCEEDED
            or receipt.result_ref is None
            or receipt.refusal_ref is not None
            or receipt.refusal_detail_ref is not None
            or receipt.effect is not OperationEffect.UPDATED
            or projection.rule is None
        ):
            raise ValueError("ledger rule add success has an incompatible terminal receipt")
    elif (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.refusal_ref != LEDGER_RULE_VALIDATION_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
        or receipt.result_ref is not None
        or receipt.effect is not OperationEffect.NONE
        or projection.rule is not None
    ):
        raise ValueError("ledger rule add refusal has an incompatible terminal receipt")
    return projection


def _project_apply_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerRuleApplyExecutionResult:
        raise ValueError("invalid ledger rule apply result")
    projection = result.projection
    if receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id)):
        raise ValueError("ledger rule apply result belongs to another profile")
    if projection.outcome == "validation_error":
        if (
            receipt.condition is not OperationTerminalCondition.REFUSED
            or receipt.refusal_ref != LEDGER_RULE_VALIDATION_REFUSAL_CODE
            or receipt.refusal_detail_ref is None
            or receipt.result_ref is not None
            or receipt.effect not in {OperationEffect.NONE, OperationEffect.PARTIAL}
        ):
            raise ValueError("ledger rule apply refusal has an incompatible terminal receipt")
        return projection
    expected_effect = (
        (OperationEffect.UPDATED if projection.bucket_event_count else OperationEffect.NONE)
        if projection.outcome == "applied"
        else OperationEffect.NONE
    )
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.effect is not expected_effect
    ):
        raise ValueError("ledger rule apply success has an incompatible terminal receipt")
    return projection


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
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=build,
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
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
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
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
    resolved = resolve_ledger_read_access(request, context, profile_id=profile_id, periods=frozenset())
    if not commit:
        return resolved
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


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
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=LedgerRuleAddRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=LedgerRuleAddProjection,
        ),
        result_projector=_project_add_result,
        access_resolver=resolve_ledger_rule_add_access,
    )


def build_ledger_rule_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind list request/result schemas and read-only admission policy."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=LedgerRuleListRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=LedgerRuleListProjection,
        ),
        access_resolver=resolve_ledger_rule_list_access,
    )


def build_ledger_rule_apply_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind apply request/result schemas and dry-run-aware admission policy."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=LedgerRuleApplyRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=LedgerRuleApplyProjection,
        ),
        result_projector=_project_apply_result,
        access_resolver=resolve_ledger_rule_apply_access,
    )


__all__ = [
    "LEDGER_RULE_ADD_OPERATION_DEFINITION_ID",
    "LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID",
    "LEDGER_RULE_LIST_OPERATION_DEFINITION_ID",
    "LEDGER_RULE_VALIDATION_REFUSAL_CODE",
    "LedgerRuleAddExecutor",
    "LedgerRuleAddProjection",
    "LedgerRuleAddRequest",
    "LedgerRuleApplyAppliedProjection",
    "LedgerRuleApplyExecutor",
    "LedgerRuleApplyMatchProjection",
    "LedgerRuleApplyProjection",
    "LedgerRuleApplyRequest",
    "LedgerRuleListExecutor",
    "LedgerRuleListProjection",
    "LedgerRuleListRequest",
    "LedgerRuleRowProjection",
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
