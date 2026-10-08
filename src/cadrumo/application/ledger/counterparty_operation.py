"""Guarded counterparty confirmation, withdrawal, and ladder lookup."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.country_code import CountryCodeAlpha2
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.eu_member_state_catalogue import require_eu_member_state
from ...domain.iva.classification import require_iva_territorial_scope
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.fenced_result import publish_fenced_result
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import ALL_OPERATION_FRONTENDS, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
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
from .read_access import resolve_ledger_commit_access, resolve_ledger_read_access

LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID = "ledger.counterparty"


def _require_confirmation_action_fields(
    *,
    territorial_scope: str | None,
    identification_state: str | None,
    asserted_by: str | None,
    evidenced_scope: str | None,
) -> None:
    """Require an actor and at least one directly confirmed identity axis."""
    if territorial_scope is None and identification_state is None:
        raise ValueError("confirmation must answer at least one axis")
    if asserted_by is None or not asserted_by.strip() or evidenced_scope is not None:
        raise ValueError("confirmation requires its actor and no document evidence")


def _require_non_confirmation_action_fields(
    *,
    action: Literal["withdraw", "view"],
    territorial_scope: str | None,
    identification_state: str | None,
    note: str,
    asserted_by: str | None,
    evidenced_scope: str | None,
) -> None:
    """Keep confirmation-only input out of withdraw and view requests."""
    if (
        territorial_scope is not None
        or identification_state is not None
        or note
        or asserted_by is not None
        or (action == "withdraw" and evidenced_scope is not None)
    ):
        raise ValueError("counterparty action contains fields outside its declared purpose")


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
            _require_confirmation_action_fields(
                territorial_scope=self.territorial_scope,
                identification_state=self.identification_state,
                asserted_by=self.asserted_by,
                evidenced_scope=self.evidenced_scope,
            )
        else:
            _require_non_confirmation_action_fields(
                action=self.action,
                territorial_scope=self.territorial_scope,
                identification_state=self.identification_state,
                note=self.note,
                asserted_by=self.asserted_by,
                evidenced_scope=self.evidenced_scope,
            )
        return self


class CounterpartyFactProjection(BaseModel):
    """Scalar copy of the confirmed fact for the encrypted public result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    counterparty_key: Hex64Str
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


def _confirm_counterparty_action(
    payload: LedgerCounterpartyRequest,
    *,
    bucket_id: str,
    context: OperationExecutorContext,
    repository: _TrackedCounterpartyRepository,
) -> LedgerCounterpartyResult:
    """Confirm selected identity axes, preserving domain conflict facts."""
    try:
        outcome = confirm_counterparty_establishment(
            bucket_id=bucket_id,
            tax_identifier=payload.tax_identifier,
            asserted_by=payload.asserted_by or "",
            territorial_scope=(
                require_iva_territorial_scope(payload.territorial_scope, operation=context.authority_operation)
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
            conflict_context=tuple(sorted((key, str(value)) for key, value in (error.context or {}).items())),
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


def _withdraw_counterparty_action(
    payload: LedgerCounterpartyRequest,
    *,
    bucket_id: str,
    repository: _TrackedCounterpartyRepository,
) -> LedgerCounterpartyResult:
    """Withdraw only a verifiable exact-key fact and report the actual delete."""
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


def _view_counterparty_action(
    payload: LedgerCounterpartyRequest,
    *,
    bucket_id: str,
    context: OperationExecutorContext,
    repository: _TrackedCounterpartyRepository,
) -> LedgerCounterpartyResult:
    """Resolve canonical facts and optional document evidence under one authority."""
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


def _perform_counterparty_action(
    payload: LedgerCounterpartyRequest,
    *,
    bucket_id: str,
    context: OperationExecutorContext,
    repository_factory: CounterpartyEstablishmentRepositoryFactory,
) -> LedgerCounterpartyResult:
    """Create one tracked repository and dispatch the declared action."""
    repository = _TrackedCounterpartyRepository(repository_factory(bucket_id=bucket_id))
    if payload.action == "confirm":
        return _confirm_counterparty_action(payload, bucket_id=bucket_id, context=context, repository=repository)
    if payload.action == "withdraw":
        return _withdraw_counterparty_action(payload, bucket_id=bucket_id, repository=repository)
    return _view_counterparty_action(payload, bucket_id=bucket_id, context=context, repository=repository)


async def _publish_counterparty_action(
    context: OperationExecutorContext,
    *,
    payload: LedgerCounterpartyRequest,
    bucket_id: str,
    repository_factory: CounterpartyEstablishmentRepositoryFactory,
) -> str:
    """Publish views as reads and settle mutations through the irreversible fence."""

    async def run_action() -> LedgerCounterpartyResult:
        return await asyncio.to_thread(
            _perform_counterparty_action,
            payload,
            bucket_id=bucket_id,
            context=context,
            repository_factory=repository_factory,
        )

    return await publish_fenced_result(
        context,
        run_action=run_action,
        is_read=payload.action == "view",
        result_changed=lambda result: result.changed,
    )


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
        if request.definition_id != LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID)
        return await await_cancellation_complete(
            _publish_counterparty_action(
                context,
                payload=payload,
                bucket_id=bucket_id,
                repository_factory=self._repository_factory,
            ),
            task_name="ledger-counterparty",
        )


def build_ledger_counterparty_definition(
    repository_factory: CounterpartyEstablishmentRepositoryFactory,
) -> OperationDefinition:
    """Declare private input, a recorded result and honest mutation effects."""
    return build_single_phase_definition(
        definition_id=LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
        request_type=LedgerCounterpartyRequest,
        result_type=LedgerCounterpartyResult,
        executor_type=LedgerCounterpartyExecutor,
        build=lambda: LedgerCounterpartyExecutor(repository_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def resolve_ledger_counterparty_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile scope, and COMMIT for mutations."""
    if request.definition_id != LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerCounterpartyRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolve = resolve_ledger_read_access if request.payload.action == "view" else resolve_ledger_commit_access
    return resolve(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_counterparty_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and encrypted result schemas."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerCounterpartyResult,
        access_resolver=resolve_ledger_counterparty_access,
    )
