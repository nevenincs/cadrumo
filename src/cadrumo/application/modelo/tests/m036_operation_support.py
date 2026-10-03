"""Inward lifecycle fixtures with observable atomic writer authority."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID, uuid4

from pydantic import BaseModel

from ....core.operations import OperationEffect, profile_operation_subject
from ....core.secure_object_write import SecureObjectWrite
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import ResolvedOperationAccess
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationRegistry
from ...user_profile.access_contracts import (
    AccessAllowed,
    AccessDenialCode,
    AccessDenied,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    Availability,
    DisclosurePermission,
    LoginEligibility,
    OsLoginContext,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
    SessionState,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ...user_profile.operation_access_policy import evaluate_operation_access
from ..m036_lifecycle import M036DeclarationAmbiguousError, M036DeclarationNotFoundError, M036DeclarationResult
from ..m036_lifecycle_ports import M036LifecyclePorts
from ..m036_operation_ports import M036OperationPorts
from .test_m036_lifecycle_service import _DeclarationRepository, _EventRepository

PROFILE_ID = UUID("32323232-3232-4232-8232-323232323232")
INSTANT = datetime(2026, 10, 1, 12, tzinfo=UTC)


class CommitFence:
    """Authorize actual persistence only; service preparation must stay outside."""

    def __init__(self) -> None:
        self.active = False
        self.entries = 0
        self.deny = False

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        if self.deny:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        self.active = True
        self.entries += 1
        try:
            yield
        finally:
            self.active = False


class EventRepository(_EventRepository):
    """The established revisioned audit fixture with a preparation detector."""

    def __init__(self, fence: CommitFence) -> None:
        super().__init__()
        self.fence = fence

    @override
    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        assert not self.fence.active, "audit preparation must not hold COMMIT authority"
        return super().load_revisioned()

    @override
    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        assert not self.fence.active, "prepare the existing audit write before COMMIT"
        return super().to_secure_object_write(catalogue, expected_revision_id=expected_revision_id)


class DeclarationRepository(_DeclarationRepository):
    """Atomic declaration/event fixture detecting legacy unfenced writes."""

    def __init__(self, events: EventRepository, fence: CommitFence) -> None:
        super().__init__(events)
        self.fence = fence
        self.reads = 0
        self.writes = 0
        self.fail_after_commit = False

    @override
    def list_snapshots(self) -> tuple[M036DeclarationResult, ...]:
        assert not self.fence.active, "canonical sequence reads must precede COMMIT"
        self.reads += 1
        return super().list_snapshots()

    @override
    def resolve(self, declaration_id: str) -> M036DeclarationResult:
        matches = tuple(row for row in self.list_snapshots() if row.declaration_id.startswith(declaration_id))
        if not matches:
            raise M036DeclarationNotFoundError("synthetic unknown declaration")
        if len(matches) > 1:
            raise M036DeclarationAmbiguousError("synthetic ambiguous declaration")
        return matches[0]

    @override
    def save(self, declaration: M036DeclarationResult) -> None:
        assert self.fence.active, "durable declaration writes require operation authority"
        super().save(declaration)

    @override
    def save_with_secure_object_writes(
        self,
        declaration: M036DeclarationResult,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        assert self.fence.active and len(extra_writes) == 1
        super().save_with_secure_object_writes(declaration, extra_writes)
        self.writes += 1
        if self.fail_after_commit:
            raise ValueError("synthetic atomic writer committed before raising")

    def seed(self, declaration: M036DeclarationResult) -> None:
        """Prepare already recorded state without authorizing an operation write."""
        super().save(declaration)


class Events:
    """Capture only fixed phase/effect facts in the generic journal stand-in."""

    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []
        self.phases: list[str] = []

    async def phase(self, value: str) -> None:
        self.phases.append(value)

    async def effect(self, value: OperationEffect) -> None:
        self.effects.append(value)


class Operands:
    """Retain synthetic typed protected results separately from journal facts."""

    def __init__(self) -> None:
        self.values: list[BaseModel] = []

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        self.values.append(value)
        return "d" * 64


class Subject:
    """One genuine authority pin and observable inward lifecycle capabilities."""

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self.operation = operation
        self.fence = CommitFence()
        self.events = Events()
        self.operands = Operands()
        self.audit = EventRepository(self.fence)
        self.repository = DeclarationRepository(self.audit, self.fence)
        self.ports = M036OperationPorts(PROFILE_ID, operation, M036LifecyclePorts(self.repository, self.audit))

    def compose(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> M036OperationPorts:
        assert profile_id == PROFILE_ID and operation is self.operation
        return self.ports

    def context(self, definition_id: str) -> OperationExecutorContext:
        return cast(
            OperationExecutorContext,
            SimpleNamespace(
                identity=SimpleNamespace(
                    definition_id=definition_id, subject_ref=profile_operation_subject(str(PROFILE_ID))
                ),
                authority_operation=self.operation,
                cancellation=self.fence,
                events=self.events,
                operands=self.operands,
            ),
        )


def policy_decision(
    resolved: ResolvedOperationAccess,
    registry: OperationRegistry,
    *,
    disclosures: frozenset[DisclosurePermission],
    human: bool = False,
    all_periods: bool = True,
    operations: frozenset[str] | None = None,
) -> AccessAllowed | AccessDenied:
    """Exercise the actual evaluator with coherent explicit login/grant facts."""
    scope = AccessScope(
        operations=operations if operations is not None else frozenset({resolved.request.definition_id}),
        actions=frozenset({resolved.request.action}),
        disclosures=disclosures,
        periods=None if all_periods else frozenset(),
        allow_period_independent=True,
        allow_delegation=False,
    )
    binding = ProfileAccessBinding(
        profile_id=PROFILE_ID,
        installation_id=uuid4(),
        os_owner_id="synthetic-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )
    grant = AutomationGrant(
        grant_id=uuid4(),
        binding=binding,
        client_id=uuid4(),
        generation=1,
        profile_lock_generation=0,
        state=AuthorityState.ACTIVE,
        scope=scope,
        valid_from=INSTANT - timedelta(days=1),
        expires_at=INSTANT + timedelta(days=1),
        unattended=True,
        allow_os_lock=False,
    )
    key = ApiKeyRecord(
        key_id=uuid4(),
        grant_id=grant.grant_id,
        binding=binding,
        generation=1,
        state=AuthorityState.ACTIVE,
        valid_from=grant.valid_from,
        expires_at=grant.expires_at,
    )
    session = AccessSession(
        session_id=uuid4(),
        binding=binding,
        profile_lock_generation=0,
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        client_id=grant.client_id,
        kind=SessionKind.HUMAN if human else SessionKind.API_KEY,
        originating_login_id="synthetic-login" if human else None,
        state=SessionState.ACTIVE,
        scope=scope,
        grant_id=None if human else grant.grant_id,
        grant_generation=None if human else grant.generation,
        key_id=None if human else key.key_id,
        key_generation=None if human else key.generation,
        issued_at=INSTANT,
        expires_at=INSTANT + timedelta(minutes=2),
        issued_monotonic=100.0,
    )
    return evaluate_operation_access(
        request=resolved.request,
        policy=resolved.policy,
        registry=registry,
        session=session,
        ancestors=(),
        grant=None if human else grant,
        key=None if human else key,
        profile=ProfileAccessState(
            binding=binding,
            lock_generation=0,
            globally_locked=False,
            automation_enabled=True,
            scope=scope,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.AVAILABLE,
        ),
        context=AccessEvaluationContext(
            now=INSTANT,
            monotonic_now=100.0,
            clock_rollback_detected=False,
            runtime_boot_id=session.runtime_boot_id,
            connection_id=session.connection_id,
            authenticated_client_id=grant.client_id,
            login_contexts=(
                OsLoginContext(
                    login_id="synthetic-login",
                    os_owner_id=binding.os_owner_id,
                    active=True,
                    locked=False,
                    unattended=LoginEligibility.ELIGIBLE,
                    credential_facilities=Availability.AVAILABLE,
                ),
            ),
            private_work_available=True,
        ),
    )
