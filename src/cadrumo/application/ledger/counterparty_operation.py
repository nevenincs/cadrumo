"""Guarded counterparty confirmation, withdrawal, and ladder lookup."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.country_code import CountryCodeAlpha2
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...domain.iva.classification import require_iva_territorial_scope
from ...domain.iva.schema import require_eu_member_state
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
from ..operations.owner import OperationExecutorContext
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
from .counterparty_establishment import (
    ConfirmedCounterpartyFacts,
    ConfirmedCounterpartyResolution,
    CounterpartyEstablishmentConflictError,
    confirm_counterparty_establishment,
    confirmed_counterparty_facts_key,
    forget_confirmed_counterparty_facts,
    resolve_confirmed_counterparty_facts,
)
from .counterparty_establishment_ports import (
    CounterpartyEstablishmentRepositoryFactory,
    CounterpartyEstablishmentRepositoryProtocol,
)
from .read_access import resolve_ledger_read_access

LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID = "ledger.counterparty"


class LedgerCounterpartyRequest(BaseModel):
    """One exact-profile action with private counterparty input."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    action: Literal["confirm", "withdraw", "view"]
    tax_identifier: str = Field(min_length=1, max_length=256)
    country_code: CountryCodeAlpha2 | None = None
    territorial_scope: str | None = Field(default=None, min_length=1, max_length=64)
    identification_state: str | None = Field(default=None, min_length=2, max_length=2)
    evidenced_scope: str | None = Field(default=None, min_length=1, max_length=64)
    note: str = Field(default="", max_length=4096)
    asserted_by: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def _action_fields(self) -> LedgerCounterpartyRequest:
        if self.action == "confirm":
            if self.territorial_scope is None and self.identification_state is None:
                raise ValueError("confirmation must answer at least one axis")
            if self.asserted_by is None or not self.asserted_by.strip() or self.evidenced_scope is not None:
                raise ValueError("confirmation requires its actor and no document evidence")
        elif (
            self.territorial_scope is not None
            or self.identification_state is not None
            or self.note
            or self.asserted_by is not None
            or (self.action == "withdraw" and self.evidenced_scope is not None)
        ):
            raise ValueError("counterparty action contains fields outside its declared purpose")
        return self


class CounterpartyFactProjection(BaseModel):
    """Scalar copy of the confirmed fact for the encrypted public result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    counterparty_key: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    canonical_tax_identifier: str = Field(min_length=1, max_length=256)
    territorial_scope: str | None = Field(default=None, min_length=1, max_length=64)
    identification_state: str | None = Field(default=None, min_length=2, max_length=2)
    asserted_by: str = Field(min_length=1, max_length=256)
    asserted_at: datetime
    note: str = Field(default="", max_length=4096)

    @classmethod
    def from_fact(cls, fact: ConfirmedCounterpartyFacts) -> CounterpartyFactProjection:
        """Copy domain tokens into stable string fields at the worker boundary."""
        return cls(
            counterparty_key=fact.counterparty_key,
            canonical_tax_identifier=fact.canonical_tax_identifier,
            territorial_scope=fact.territorial_scope.value if fact.territorial_scope is not None else None,
            identification_state=fact.identification_state.value if fact.identification_state is not None else None,
            asserted_by=fact.asserted_by,
            asserted_at=fact.asserted_at,
            note=fact.note,
        )


class CounterpartyResolutionProjection(BaseModel):
    """Scalar copy of the ladder's answer, including withheld contradictions."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    territorial_scope: str | None = Field(default=None, min_length=1, max_length=64)
    territorial_source: str | None = Field(default=None, min_length=1, max_length=64)
    identification_state: str | None = Field(default=None, min_length=2, max_length=2)
    identification_source: str | None = Field(default=None, min_length=1, max_length=64)
    confirmed_scope: str | None = Field(default=None, min_length=1, max_length=64)
    evidenced_scope: str | None = Field(default=None, min_length=1, max_length=64)
    contradiction_detail: str | None = Field(default=None, min_length=1, max_length=2048)

    @classmethod
    def from_resolution(cls, resolution: ConfirmedCounterpartyResolution) -> CounterpartyResolutionProjection:
        """Retain exactly what the canonical resolver settled or withheld."""
        fact = resolution.fact
        identification = resolution.identification
        contradiction = resolution.contradiction
        return cls(
            territorial_scope=fact.value.value if fact is not None else None,
            territorial_source=fact.source.value if fact is not None else None,
            identification_state=identification.value.value if identification is not None else None,
            identification_source=identification.source.value if identification is not None else None,
            confirmed_scope=contradiction.confirmed_scope.value if contradiction is not None else None,
            evidenced_scope=contradiction.evidenced_scope.value if contradiction is not None else None,
            contradiction_detail=contradiction.detail if contradiction is not None else None,
        )


class LedgerCounterpartyResult(BaseModel):
    """Encrypted operation result containing only the selected action's facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    action: Literal["confirm", "withdraw", "view"]
    tax_identifier: str
    country_code: str | None = None
    evidenced_scope: str | None = Field(default=None, min_length=1, max_length=64)
    facts: CounterpartyFactProjection | None = None
    resolution: CounterpartyResolutionProjection | None = None
    recorded: bool | None = None
    withdrawn: bool | None = None
    changed: bool = False
    conflict_context: tuple[tuple[str, str], ...] | None = None


class _TrackedCounterpartyRepository:
    """Observe canonical service writes without inventing a second writer."""

    def __init__(self, repository: CounterpartyEstablishmentRepositoryProtocol) -> None:
        """Wrap only the repository supplied by the profile worker."""
        self._repository = repository
        self.changed = False

    def load(self, identifier: str) -> ConfirmedCounterpartyFacts | None:
        """Read the existing fact without changing the write marker."""
        return self._repository.load(identifier)

    def save(self, payload: ConfirmedCounterpartyFacts) -> None:
        """Delegate persistence and mark a completed write."""
        self._repository.save(payload)
        self.changed = True

    def delete(self, identifier: str) -> bool:
        """Delegate deletion and mark a completed removal."""
        deleted = self._repository.delete(identifier)
        self.changed = deleted
        return deleted


class LedgerCounterpartyExecutor:
    """Invoke canonical services inside the profile worker's access fence."""

    def __init__(self, repository_factory: CounterpartyEstablishmentRepositoryFactory) -> None:
        """Keep the profile-bound repository factory in the worker."""
        self._repository_factory = repository_factory

    async def execute(
        self, request: OperationRequest[LedgerCounterpartyRequest], context: OperationExecutorContext
    ) -> str:
        """Apply the selected action and publish its encrypted result."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if (
            request.definition_id != LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(bucket_id)
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID)

        def act() -> LedgerCounterpartyResult:
            repository = _TrackedCounterpartyRepository(self._repository_factory(bucket_id=bucket_id))
            if payload.action == "confirm":
                try:
                    outcome = confirm_counterparty_establishment(
                        bucket_id=bucket_id,
                        tax_identifier=payload.tax_identifier,
                        asserted_by=payload.asserted_by or "",
                        territorial_scope=(
                            require_iva_territorial_scope(
                                payload.territorial_scope, operation=context.authority_operation
                            )
                            if payload.territorial_scope is not None
                            else None
                        ),
                        identification_state=(
                            require_eu_member_state(payload.identification_state, authority=context.authority_operation)
                            if payload.identification_state is not None
                            else None
                        ),
                        country_code=payload.country_code,
                        note=payload.note,
                        repository=repository,
                    )
                except CounterpartyEstablishmentConflictError as error:
                    return LedgerCounterpartyResult(
                        profile_id=payload.profile_id,
                        action=payload.action,
                        tax_identifier=payload.tax_identifier,
                        country_code=payload.country_code,
                        conflict_context=tuple(
                            sorted((key, str(value)) for key, value in (error.context or {}).items())
                        ),
                    )
                return LedgerCounterpartyResult(
                    profile_id=payload.profile_id,
                    action=payload.action,
                    tax_identifier=payload.tax_identifier,
                    country_code=payload.country_code,
                    facts=CounterpartyFactProjection.from_fact(outcome.facts),
                    recorded=outcome.recorded,
                    changed=repository.changed,
                )
            if payload.action == "withdraw":
                # An unverifiable identifier must not masquerade as an idempotent no-op.
                if confirmed_counterparty_facts_key(payload.tax_identifier, country_code=payload.country_code) is None:
                    raise ValueError("counterparty identifier is unverifiable")
                withdrawn = forget_confirmed_counterparty_facts(
                    bucket_id=bucket_id,
                    tax_identifier=payload.tax_identifier,
                    country_code=payload.country_code,
                    repository=repository,
                )
                return LedgerCounterpartyResult(
                    profile_id=payload.profile_id,
                    action=payload.action,
                    tax_identifier=payload.tax_identifier,
                    country_code=payload.country_code,
                    withdrawn=withdrawn,
                    changed=repository.changed,
                )
            resolution = resolve_confirmed_counterparty_facts(
                bucket_id=bucket_id,
                tax_identifier=payload.tax_identifier,
                country_code=payload.country_code,
                evidenced_scope=(
                    require_iva_territorial_scope(payload.evidenced_scope, operation=context.authority_operation)
                    if payload.evidenced_scope is not None
                    else None
                ),
                repository=repository,
            )
            return LedgerCounterpartyResult(
                profile_id=payload.profile_id,
                action=payload.action,
                tax_identifier=payload.tax_identifier,
                country_code=payload.country_code,
                evidenced_scope=payload.evidenced_scope,
                resolution=CounterpartyResolutionProjection.from_resolution(resolution),
            )

        async def publish() -> str:
            if payload.action == "view":
                result = await asyncio.to_thread(act)
                await context.events.effect(OperationEffect.NONE)
                return await context.operands.put(result, written_at=now())
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                result = await asyncio.to_thread(act)
                await context.events.effect(OperationEffect.UPDATED if result.changed else OperationEffect.NONE)
                return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(publish(), task_name="ledger-counterparty")


def build_ledger_counterparty_definition(
    repository_factory: CounterpartyEstablishmentRepositoryFactory,
) -> OperationDefinition:
    """Declare private input, a recorded result and honest mutation effects."""
    return OperationDefinition(
        definition_id=LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
        request_type=LedgerCounterpartyRequest,
        result_type=LedgerCounterpartyResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerCounterpartyRequest,
            executor_type=LedgerCounterpartyExecutor,
            build=lambda: LedgerCounterpartyExecutor(repository_factory),
        ),
        phase_codes=(LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,),
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
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def resolve_ledger_counterparty_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile scope, and COMMIT for mutations."""
    if request.definition_id != LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerCounterpartyRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    if request.payload.action == "view":
        return resolved
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return replace(resolved, policy=policy)


def build_ledger_counterparty_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and encrypted result schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=LedgerCounterpartyRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=LedgerCounterpartyResult
        ),
        access_resolver=resolve_ledger_counterparty_access,
    )
