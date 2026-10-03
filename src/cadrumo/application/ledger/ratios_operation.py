"""Profile-bound operations for the existing ledger-ratios CLI verbs."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal, Protocol, cast
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.hierarchy import pydantic_validation_boundary
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
from ...core.unit_proportion import is_unit_proportion
from ...domain.categories.spending_category import SpendingCategory
from ...domain.categories.spending_category_catalogue import require_spending_category
from ...domain.usage_ratios.errors import CensoRatioMismatchError
from ..operations.access_port import OperationAccessResolver
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.read_capture import capture_read_result
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationResultProjector,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .read_access import resolve_ledger_read_access
from .usage_ratio_repository import load_usage_ratio_profile, usage_ratio_profile_with_censo_guard

LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID = "ledger.ratios.list"
LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID = "ledger.ratios.set"
LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID = "ledger.ratios.unset"
LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID = "ledger.ratios.eligible"
LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID = "ledger.ratios.validate"
LEDGER_RATIOS_CENSO_MISMATCH_REFUSAL_CODE = "REFUSED_FINANCIAL_USAGE_RATIOS_CENSO_MISMATCH"
LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE = "REFUSED_CLI_VALIDATION_BOUNDARY"

_Year = Annotated[int, Field(ge=1900, le=9999)]
_CategoryToken = Annotated[str, Field(min_length=1, max_length=96)]
_RatioText = Annotated[str, Field(min_length=1, max_length=128)]


class _ProfileScopedRequest(Protocol):
    profile_id: UUID


def _validate_ratio_text(value: str, *, require_unit: bool) -> str:
    parsed = try_parse_canonical_decimal(value)
    if parsed is None:
        raise ValueError("ratio must be a canonical decimal string")
    if require_unit and not is_unit_proportion(parsed):
        raise ValueError("ratio must be within [0, 1]")
    return value


class LedgerRatiosListRequest(CredentialFreeOperationRequest):
    """Read the exact profile's persisted overrides under one filing year."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    year: _Year


class LedgerRatiosSetRequest(BaseModel):
    """Set one exact-profile override without journaling its numeric input."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    category: _CategoryToken
    ratio: _RatioText
    year: _Year

    @field_validator("ratio")
    @classmethod
    @pydantic_validation_boundary
    def _canonical_ratio(cls, value: str) -> str:
        return _validate_ratio_text(value, require_unit=True)


class LedgerRatiosUnsetRequest(BaseModel):
    """Clear one exact-profile category override."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    category: _CategoryToken


class LedgerRatiosEligibleRequest(CredentialFreeOperationRequest):
    """Read eligible ratio categories and defaults for one filing year."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    year: _Year


class LedgerRatiosValidateRequest(CredentialFreeOperationRequest):
    """Validate the exact profile's stored ratio overrides."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class LedgerRatiosListRow(BaseModel):
    """One bounded per-category override returned by the application."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    category: _CategoryToken
    ratio: _RatioText

    @field_validator("ratio")
    @classmethod
    @pydantic_validation_boundary
    def _unit_ratio(cls, value: str) -> str:
        return _validate_ratio_text(value, require_unit=True)


class _LedgerRatiosListFacts(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    year: _Year
    outcome: Literal["available", "censo_mismatch"]
    rows: tuple[LedgerRatiosListRow, ...] = ()
    count: NonNegativeInt

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _rows_match_outcome(self) -> _LedgerRatiosListFacts:
        if self.outcome == "available" and self.count != len(self.rows):
            raise ValueError("ratio-list count differs from its rows")
        if self.outcome == "censo_mismatch" and (self.count != 0 or self.rows):
            raise ValueError("censo-mismatch result cannot disclose stale ratio rows")
        categories = tuple(row.category for row in self.rows)
        if len(set(categories)) != self.count or categories != tuple(sorted(categories)):
            raise ValueError("ratio-list rows are duplicated or not canonically ordered")
        return self


class LedgerRatiosListResult(_LedgerRatiosListFacts):
    """Encrypted list result retained by the operation supervisor."""


class LedgerRatiosListProjection(_LedgerRatiosListFacts):
    """Independent, bounded frontend projection for the ratio list."""


class LedgerRatiosEligibleRow(BaseModel):
    """Bounded statutory category details shown by ``ratios eligible``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    category: _CategoryToken
    proportionality_kind: _CategoryToken
    default_ratio: _RatioText | None = None
    override_present: bool

    @field_validator("default_ratio")
    @classmethod
    @pydantic_validation_boundary
    def _default_is_unit_ratio(cls, value: str | None) -> str | None:
        return None if value is None else _validate_ratio_text(value, require_unit=True)


class _LedgerRatiosEligibleFacts(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    year: _Year
    rows: tuple[LedgerRatiosEligibleRow, ...]
    count: NonNegativeInt

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _rows_match_count(self) -> _LedgerRatiosEligibleFacts:
        if self.count != len(self.rows) or len({row.category for row in self.rows}) != self.count:
            raise ValueError("eligible ratio rows differ from their count or contain duplicate categories")
        if tuple(row.category for row in self.rows) != tuple(sorted(row.category for row in self.rows)):
            raise ValueError("eligible ratio rows are not canonically ordered")
        return self


class LedgerRatiosEligibleResult(_LedgerRatiosEligibleFacts):
    """Encrypted eligible-category result."""


class LedgerRatiosEligibleProjection(_LedgerRatiosEligibleFacts):
    """Independent, bounded eligible-category frontend projection."""


class LedgerRatiosValidationFinding(BaseModel):
    """One bounded finding from the existing validation service."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    category: _CategoryToken
    kind: Annotated[str, Field(min_length=1, max_length=96)]
    detail: Annotated[str, Field(max_length=300)] = ""


class _LedgerRatiosValidateFacts(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    profile_present: bool
    eligible_count: NonNegativeInt
    overrides_count: NonNegativeInt
    missing_overrides: tuple[_CategoryToken, ...] = ()
    findings: tuple[LedgerRatiosValidationFinding, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _counts_are_coherent(self) -> _LedgerRatiosValidateFacts:
        if self.overrides_count and not self.profile_present:
            raise ValueError("ratio validation count contradicts profile presence")
        if len(set(self.missing_overrides)) != len(self.missing_overrides):
            raise ValueError("ratio validation repeats a missing override")
        return self


class LedgerRatiosValidateResult(_LedgerRatiosValidateFacts):
    """Encrypted validation report."""


class LedgerRatiosValidateProjection(_LedgerRatiosValidateFacts):
    """Independent, bounded validation frontend projection."""


class _LedgerRatiosSetFacts(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    requested_category: _CategoryToken
    category: _CategoryToken
    ratio: _RatioText
    prior_ratio: _RatioText | None = None

    @field_validator("ratio", "prior_ratio")
    @classmethod
    @pydantic_validation_boundary
    def _unit_ratio(cls, value: str | None) -> str | None:
        return None if value is None else _validate_ratio_text(value, require_unit=True)


class LedgerRatiosSetResult(_LedgerRatiosSetFacts):
    """Encrypted exact-profile set result."""


class LedgerRatiosSetProjection(_LedgerRatiosSetFacts):
    """Independent set projection correlated to the submitted category and value."""


class _LedgerRatiosUnsetFacts(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    requested_category: _CategoryToken
    category: _CategoryToken
    outcome: Literal["cleared", "no_override"]
    prior_ratio: _RatioText | None = None

    @field_validator("prior_ratio")
    @classmethod
    @pydantic_validation_boundary
    def _unit_ratio(cls, value: str | None) -> str | None:
        return None if value is None else _validate_ratio_text(value, require_unit=True)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _outcome_matches_prior(self) -> _LedgerRatiosUnsetFacts:
        if (self.outcome == "cleared") != (self.prior_ratio is not None):
            raise ValueError("ratio-unset outcome differs from its prior value")
        return self


class LedgerRatiosUnsetResult(_LedgerRatiosUnsetFacts):
    """Encrypted exact-profile unset result."""


class LedgerRatiosUnsetProjection(_LedgerRatiosUnsetFacts):
    """Independent unset projection, including the explicit no-override outcome."""


def _require_worker_profile(
    request: OperationRequest[Any],
    context: OperationExecutorContext,
    *,
    definition_id: str,
    profile_id: UUID,
) -> str:
    """Refuse any request whose profile or operation identity escaped worker custody."""
    bucket_id = str(profile_id)
    expected_subject = profile_operation_subject(bucket_id)
    if (
        request.definition_id != definition_id
        or request.subject_ref != expected_subject
        or context.identity.definition_id != definition_id
        or context.identity.subject_ref != expected_subject
        or require_active_bucket_id() != bucket_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return bucket_id


class LedgerRatiosListExecutor:
    """Load the censo-guarded ratio profile within its exact-profile worker."""

    async def execute(
        self, request: OperationRequest[LedgerRatiosListRequest], context: OperationExecutorContext
    ) -> str | OperationRefusalEvidence:
        payload = request.payload
        bucket_id = _require_worker_profile(
            cast(OperationRequest[Any], request),
            context,
            definition_id=LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        await context.events.phase(LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID)

        def read() -> LedgerRatiosListResult:
            from ...application.user_profile.censo_sync import bound_raw_afectacion_ratio

            operation = context.authority_operation
            try:
                raw_afectacion = bound_raw_afectacion_ratio(
                    bucket_id=bucket_id,
                    profile_id=bucket_id,
                    operation=operation,
                )
                profile = usage_ratio_profile_with_censo_guard(
                    bucket_id=bucket_id,
                    raw_afectacion_ratio=raw_afectacion,
                    year=payload.year,
                    operation=operation,
                )
            except CensoRatioMismatchError:
                return LedgerRatiosListResult(
                    profile_id=payload.profile_id,
                    year=payload.year,
                    outcome="censo_mismatch",
                    rows=(),
                    count=0,
                )
            rows = tuple(
                LedgerRatiosListRow(category=category.value, ratio=str(ratio))
                for category, ratio in profile.ratios.items()
            )
            return LedgerRatiosListResult(
                profile_id=payload.profile_id,
                year=payload.year,
                outcome="available",
                rows=rows,
                count=len(rows),
            )

        async def capture() -> str | OperationRefusalEvidence:
            result = await asyncio.to_thread(read)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            if result.outcome == "censo_mismatch":
                return OperationRefusalEvidence(
                    refusal_code=LEDGER_RATIOS_CENSO_MISMATCH_REFUSAL_CODE,
                    detail_ref=reference,
                )
            return reference

        return await await_cancellation_complete(capture(), task_name="ledger-ratios-list")


class LedgerRatiosSetExecutor:
    """Apply one ratio override using the existing serialized application service."""

    async def execute(
        self, request: OperationRequest[LedgerRatiosSetRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        bucket_id = _require_worker_profile(
            cast(OperationRequest[Any], request),
            context,
            definition_id=LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        await context.events.phase(LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID)
        operation = context.authority_operation

        def prepare() -> tuple[SpendingCategory, Decimal, Decimal | None]:
            from ...application.user_profile.censo_sync import bound_raw_afectacion_ratio

            category = require_spending_category(
                payload.category,
                effective_date=date(payload.year, 12, 31),
                authority=operation,
            )
            ratio = try_parse_canonical_decimal(payload.ratio)
            if ratio is None:
                raise ValueError("ratio must be a canonical decimal string")
            current = load_usage_ratio_profile(bucket_id=bucket_id, operation=operation)
            current.with_ratio(category, ratio)
            raw_afectacion = bound_raw_afectacion_ratio(
                bucket_id=bucket_id,
                profile_id=bucket_id,
                operation=operation,
            )
            return category, ratio, raw_afectacion

        async def capture() -> str:
            async with context.cancellation.irreversible_section():
                category, ratio, raw_afectacion = await asyncio.to_thread(prepare)
                # The service writes the encrypted override and its audit event
                # through separate stores. Mark the boundary unknown before entry;
                # a completed call below replaces that with UPDATED.
                await context.events.effect(OperationEffect.UNKNOWN)

                def mutate() -> LedgerRatiosSetResult:
                    from .ratios import apply_usage_ratio_override

                    outcome = apply_usage_ratio_override(
                        bucket_id=bucket_id,
                        category=category,
                        ratio=ratio,
                        year=payload.year,
                        profile_id=bucket_id,
                        raw_afectacion_ratio=raw_afectacion,
                        operation=operation,
                    )
                    return LedgerRatiosSetResult(
                        profile_id=payload.profile_id,
                        requested_category=payload.category,
                        category=category.value,
                        ratio=str(outcome.new_ratio),
                        prior_ratio=None if outcome.prior_ratio is None else str(outcome.prior_ratio),
                    )

                result = await asyncio.to_thread(mutate)
                reference = await context.operands.put(result, written_at=now())
                await context.events.effect(OperationEffect.UPDATED)
                return reference

        return await await_cancellation_complete(capture(), task_name="ledger-ratios-set")


class LedgerRatiosUnsetExecutor:
    """Clear one exact-profile override and preserve the service's missing-value refusal."""

    async def execute(
        self, request: OperationRequest[LedgerRatiosUnsetRequest], context: OperationExecutorContext
    ) -> str | OperationRefusalEvidence:
        payload = request.payload
        bucket_id = _require_worker_profile(
            cast(OperationRequest[Any], request),
            context,
            definition_id=LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        await context.events.phase(LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID)
        operation = context.authority_operation

        def prepare() -> tuple[SpendingCategory, str | None]:
            category = require_spending_category(payload.category, authority=operation)
            current = load_usage_ratio_profile(bucket_id=bucket_id, operation=operation)
            prior = current.ratios.get(category)
            return category, None if prior is None else str(prior)

        async def capture() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                category, prior = await asyncio.to_thread(prepare)
                if prior is None:
                    result = LedgerRatiosUnsetResult(
                        profile_id=payload.profile_id,
                        requested_category=payload.category,
                        category=category.value,
                        outcome="no_override",
                        prior_ratio=None,
                    )
                    reference = await context.operands.put(result, written_at=now())
                    await context.events.effect(OperationEffect.NONE)
                    return OperationRefusalEvidence(
                        refusal_code=LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE,
                        detail_ref=reference,
                    )

                await context.events.effect(OperationEffect.UNKNOWN)

                def mutate() -> LedgerRatiosUnsetResult:
                    from .ratios import clear_usage_ratio_override

                    outcome = clear_usage_ratio_override(bucket_id=bucket_id, category=category, operation=operation)
                    return LedgerRatiosUnsetResult(
                        profile_id=payload.profile_id,
                        requested_category=payload.category,
                        category=category.value,
                        outcome="cleared",
                        prior_ratio=None if outcome.prior_ratio is None else str(outcome.prior_ratio),
                    )

                result = await asyncio.to_thread(mutate)
                reference = await context.operands.put(result, written_at=now())
                await context.events.effect(OperationEffect.UPDATED)
                return reference

        return await await_cancellation_complete(capture(), task_name="ledger-ratios-unset")


class LedgerRatiosEligibleExecutor:
    """Project eligible categories from the pinned authority and exact profile."""

    async def execute(
        self, request: OperationRequest[LedgerRatiosEligibleRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        bucket_id = _require_worker_profile(
            cast(OperationRequest[Any], request),
            context,
            definition_id=LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        await context.events.phase(LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID)

        def read() -> LedgerRatiosEligibleResult:
            from .ratios import list_eligible_ratios_for_bucket

            rows = list_eligible_ratios_for_bucket(
                bucket_id=bucket_id,
                year=payload.year,
                operation=context.authority_operation,
            )
            projected = tuple(
                LedgerRatiosEligibleRow(
                    category=row.category.value,
                    proportionality_kind=row.proportionality_kind.value,
                    default_ratio=None if row.default_ratio is None else str(row.default_ratio),
                    override_present=row.override_present,
                )
                for row in rows
            )
            return LedgerRatiosEligibleResult(
                profile_id=payload.profile_id,
                year=payload.year,
                rows=projected,
                count=len(projected),
            )

        return await capture_read_result(context, read, task_name="ledger-ratios-eligible")


class LedgerRatiosValidateExecutor:
    """Run the existing profile validation report inside worker custody."""

    async def execute(
        self, request: OperationRequest[LedgerRatiosValidateRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        bucket_id = _require_worker_profile(
            cast(OperationRequest[Any], request),
            context,
            definition_id=LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        await context.events.phase(LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID)

        def read() -> LedgerRatiosValidateResult:
            from .ratios import validate_ratios_for_bucket

            report = validate_ratios_for_bucket(bucket_id=bucket_id, operation=context.authority_operation)
            return LedgerRatiosValidateResult(
                profile_id=payload.profile_id,
                profile_present=report.profile_present,
                eligible_count=report.eligible_count,
                overrides_count=report.overrides_count,
                missing_overrides=tuple(category.value for category in report.missing_overrides),
                findings=tuple(
                    LedgerRatiosValidationFinding(
                        category=finding.category.value,
                        kind=finding.kind,
                        detail=finding.detail,
                    )
                    for finding in report.findings
                ),
            )

        return await capture_read_result(context, read, task_name="ledger-ratios-validate")


def _definition(
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type,
    *,
    sensitive_input: bool,
    mutation: bool,
    refusal_detail_codes: frozenset[str] = frozenset(),
) -> OperationDefinition:
    """Declare one ratio verb with only the capabilities its service needs."""
    effects = frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    if mutation:
        effects = effects | {OperationEffect.UPDATED}
    storage = (
        OperationRequestStoragePolicy.SECURE_REFERENCE
        if sensitive_input
        else OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
    )
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=executor_type,
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=storage,
            sensitive_input=(
                OperationSensitiveInputPolicy.SECURE_REFERENCE
                if sensitive_input
                else OperationSensitiveInputPolicy.NONE
            ),
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=effects,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=refusal_detail_codes,
    )


def _registration(
    definition: OperationDefinition,
    *,
    projection_type: type[BaseModel],
    access_resolver: OperationAccessResolver,
    result_projector: OperationResultProjector,
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=projection_type,
        result_projector=result_projector,
        access_resolver=access_resolver,
    )


def _whole_profile_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    request_type: type[BaseModel],
) -> ResolvedOperationAccess:
    if request.definition_id != definition_id or not isinstance(request.payload, request_type):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = cast(_ProfileScopedRequest, request.payload)
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=payload.profile_id,
        periods=frozenset(),
    )
    if definition_id not in {LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID, LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID}:
        return resolved
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def _receipt_matches(
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
    effect: OperationEffect,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> None:
    refused = condition is OperationTerminalCondition.REFUSED
    if (
        receipt.identity.definition_id != definition_id
        or receipt.identity.subject_ref != profile_operation_subject(str(profile_id))
        or receipt.condition is not condition
        or receipt.effect is not effect
        or receipt.refusal_ref != refusal_code
        or (receipt.refusal_detail_ref is not None) != (refusal_code is not None)
        or (receipt.result_ref is not None) != (not refused)
    ):
        raise ValueError("ratio projection differs from its terminal receipt")


def _copy_result(result: BaseModel, expected_type: type[BaseModel]) -> BaseModel:
    if type(result) is not expected_type:
        raise ValueError("invalid ratio operation result")
    return expected_type.model_validate(result.model_dump(mode="python"), strict=True)


def _project_list_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> LedgerRatiosListProjection:
    private = cast(LedgerRatiosListResult, _copy_result(result, LedgerRatiosListResult))
    refused = private.outcome == "censo_mismatch"
    _receipt_matches(
        receipt,
        definition_id=LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID,
        profile_id=private.profile_id,
        effect=OperationEffect.NONE,
        condition=OperationTerminalCondition.REFUSED if refused else OperationTerminalCondition.SUCCEEDED,
        refusal_code=LEDGER_RATIOS_CENSO_MISMATCH_REFUSAL_CODE if refused else None,
    )
    return LedgerRatiosListProjection.model_validate(private.model_dump(mode="python"), strict=True)


def _project_set_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> LedgerRatiosSetProjection:
    private = cast(LedgerRatiosSetResult, _copy_result(result, LedgerRatiosSetResult))
    _receipt_matches(
        receipt,
        definition_id=LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID,
        profile_id=private.profile_id,
        effect=OperationEffect.UPDATED,
    )
    return LedgerRatiosSetProjection.model_validate(private.model_dump(mode="python"), strict=True)


def _project_unset_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> LedgerRatiosUnsetProjection:
    private = cast(LedgerRatiosUnsetResult, _copy_result(result, LedgerRatiosUnsetResult))
    refused = private.outcome == "no_override"
    expected = OperationEffect.NONE if refused else OperationEffect.UPDATED
    _receipt_matches(
        receipt,
        definition_id=LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID,
        profile_id=private.profile_id,
        effect=expected,
        condition=OperationTerminalCondition.REFUSED if refused else OperationTerminalCondition.SUCCEEDED,
        refusal_code=LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE if refused else None,
    )
    return LedgerRatiosUnsetProjection.model_validate(private.model_dump(mode="python"), strict=True)


def _project_eligible_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> LedgerRatiosEligibleProjection:
    private = cast(LedgerRatiosEligibleResult, _copy_result(result, LedgerRatiosEligibleResult))
    _receipt_matches(
        receipt,
        definition_id=LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID,
        profile_id=private.profile_id,
        effect=OperationEffect.NONE,
    )
    return LedgerRatiosEligibleProjection.model_validate(private.model_dump(mode="python"), strict=True)


def _project_validate_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> LedgerRatiosValidateProjection:
    private = cast(LedgerRatiosValidateResult, _copy_result(result, LedgerRatiosValidateResult))
    _receipt_matches(
        receipt,
        definition_id=LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID,
        profile_id=private.profile_id,
        effect=OperationEffect.NONE,
    )
    return LedgerRatiosValidateProjection.model_validate(private.model_dump(mode="python"), strict=True)


def _read_access(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
    """Bind ratio disclosures to the exact entire-profile operation scope."""
    request_types = {
        LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID: LedgerRatiosListRequest,
        LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID: LedgerRatiosEligibleRequest,
        LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID: LedgerRatiosValidateRequest,
    }
    expected = request_types.get(request.definition_id)
    if expected is None or not isinstance(request.payload, expected):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _whole_profile_access(request, context, definition_id=request.definition_id, request_type=expected)


def _set_access(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
    return _whole_profile_access(
        request,
        context,
        definition_id=LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID,
        request_type=LedgerRatiosSetRequest,
    )


def _unset_access(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
    return _whole_profile_access(
        request,
        context,
        definition_id=LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID,
        request_type=LedgerRatiosUnsetRequest,
    )


def build_ledger_ratios_list_definition() -> OperationDefinition:
    """Declare the whole-profile, censo-guarded ratio listing."""
    return _definition(
        LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID,
        LedgerRatiosListRequest,
        LedgerRatiosListResult,
        LedgerRatiosListExecutor,
        sensitive_input=False,
        mutation=False,
        refusal_detail_codes=frozenset({LEDGER_RATIOS_CENSO_MISMATCH_REFUSAL_CODE}),
    )


def build_ledger_ratios_list_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the list schemas, whole-profile access scope, and receipt projector."""
    return _registration(
        definition,
        projection_type=LedgerRatiosListProjection,
        access_resolver=_read_access,
        result_projector=_project_list_result,
    )


def build_ledger_ratios_set_definition() -> OperationDefinition:
    """Declare a secure-input, profile-wide usage-ratio mutation."""
    return _definition(
        LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID,
        LedgerRatiosSetRequest,
        LedgerRatiosSetResult,
        LedgerRatiosSetExecutor,
        sensitive_input=True,
        mutation=True,
    )


def build_ledger_ratios_set_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the set schemas, commit access scope, and receipt projector."""
    return _registration(
        definition,
        projection_type=LedgerRatiosSetProjection,
        access_resolver=_set_access,
        result_projector=_project_set_result,
    )


def build_ledger_ratios_unset_definition() -> OperationDefinition:
    """Declare a secure-input, profile-wide usage-ratio clearance."""
    return _definition(
        LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID,
        LedgerRatiosUnsetRequest,
        LedgerRatiosUnsetResult,
        LedgerRatiosUnsetExecutor,
        sensitive_input=True,
        mutation=True,
        refusal_detail_codes=frozenset({LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE}),
    )


def build_ledger_ratios_unset_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the unset schemas, commit access scope, and refusal projector."""
    return _registration(
        definition,
        projection_type=LedgerRatiosUnsetProjection,
        access_resolver=_unset_access,
        result_projector=_project_unset_result,
    )


def build_ledger_ratios_eligible_definition() -> OperationDefinition:
    """Declare the whole-profile eligibility catalogue read."""
    return _definition(
        LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID,
        LedgerRatiosEligibleRequest,
        LedgerRatiosEligibleResult,
        LedgerRatiosEligibleExecutor,
        sensitive_input=False,
        mutation=False,
    )


def build_ledger_ratios_eligible_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the eligibility schemas, whole-profile access scope, and projector."""
    return _registration(
        definition,
        projection_type=LedgerRatiosEligibleProjection,
        access_resolver=_read_access,
        result_projector=_project_eligible_result,
    )


def build_ledger_ratios_validate_definition() -> OperationDefinition:
    """Declare the whole-profile validation report read."""
    return _definition(
        LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID,
        LedgerRatiosValidateRequest,
        LedgerRatiosValidateResult,
        LedgerRatiosValidateExecutor,
        sensitive_input=False,
        mutation=False,
    )


def build_ledger_ratios_validate_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the validation schemas, whole-profile access scope, and projector."""
    return _registration(
        definition,
        projection_type=LedgerRatiosValidateProjection,
        access_resolver=_read_access,
        result_projector=_project_validate_result,
    )


__all__ = [
    "LEDGER_RATIOS_CENSO_MISMATCH_REFUSAL_CODE",
    "LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID",
    "LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID",
    "LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE",
    "LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID",
    "LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID",
    "LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID",
    "LedgerRatiosEligibleProjection",
    "LedgerRatiosEligibleRequest",
    "LedgerRatiosListProjection",
    "LedgerRatiosListRequest",
    "LedgerRatiosSetProjection",
    "LedgerRatiosSetRequest",
    "LedgerRatiosUnsetProjection",
    "LedgerRatiosUnsetRequest",
    "LedgerRatiosValidateProjection",
    "LedgerRatiosValidateRequest",
    "build_ledger_ratios_eligible_definition",
    "build_ledger_ratios_eligible_registration",
    "build_ledger_ratios_list_definition",
    "build_ledger_ratios_list_registration",
    "build_ledger_ratios_set_definition",
    "build_ledger_ratios_set_registration",
    "build_ledger_ratios_unset_definition",
    "build_ledger_ratios_unset_registration",
    "build_ledger_ratios_validate_definition",
    "build_ledger_ratios_validate_registration",
]
