"""Inward synthetic ports for canonical snapshot lifecycle and policy decisions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID, uuid4

from pydantic import BaseModel

from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_extraction import ExtractionProfileDefinition
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
from ..borrador_100 import Borrador100Snapshot
from ..borrador_100_operation_ports import (
    Borrador100ImportObservation,
    Borrador100OperationPorts,
    Borrador100PrintedValue,
)
from .test_borrador_100 import _BUCKET_ID, _InMemoryBorradorRepository

PROFILE_ID = UUID(_BUCKET_ID)
CAPTURED_AT = datetime(2026, 10, 1, 12, tzinfo=UTC)


class SnapshotFence:
    """Record actual writer authority and optionally deny a later save."""

    def __init__(self) -> None:
        self.active = False
        self.entries = 0
        self.deny_entry: int | None = None

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        if self.entries + 1 == self.deny_entry:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        self.entries += 1
        self.active = True
        try:
            yield
        finally:
            self.active = False


class SnapshotRepository(_InMemoryBorradorRepository):
    """Canonical repository fixture with concrete writer boundary observations."""

    def __init__(self, fence: SnapshotFence) -> None:
        super().__init__(bucket_id=str(PROFILE_ID))
        self.fence = fence
        self.writes = 0
        self.reads = 0
        self.fail_after_save = False

    @override
    def list_snapshots(self) -> tuple[Borrador100Snapshot, ...]:
        assert not self.fence.active, "lifecycle reads must release COMMIT authority"
        self.reads += 1
        return super().list_snapshots()

    @override
    def save(self, snapshot: Borrador100Snapshot) -> None:
        assert self.fence.active, "only the concrete writer may hold COMMIT authority"
        super().save(snapshot)
        self.writes += 1
        if self.fail_after_save:
            raise ValueError("synthetic writer failed after persistence")

    def seed(self, snapshot: Borrador100Snapshot) -> None:
        """Seed preexisting state without claiming operation writer authority."""
        super().save(snapshot)


class Parser:
    """Observe exact byte/year/profile handoff without a PDF backend in app tests."""

    def __init__(self, fence: SnapshotFence) -> None:
        self.fence = fence
        self.calls = 0
        self.change: dict[str, object] = {}
        self.receipt: Borrador100ImportObservation | None = None

    def parse(
        self, pdf_bytes: bytes, *, filing_year: int, extraction_profile: ExtractionProfileDefinition
    ) -> Borrador100ImportObservation:
        assert not self.fence.active, "PDF parsing must finish before COMMIT authority"
        self.calls += 1
        rows = tuple(
            Borrador100PrintedValue(target.casilla_id, Decimal("0.00")) for target in extraction_profile.target_casillas
        )
        assert len(rows) >= 2
        receipt = Borrador100ImportObservation(
            ejercicio=str(filing_year),
            extraction_profile_id=extraction_profile.id,
            extraction_coverage=Decimal("1"),
            artefact_kind="BORRADOR",
            source_pdf_sha256=sha256(pdf_bytes).hexdigest(),
            values=(replace(rows[0], value=None), *rows[1:]),
            warnings=("synthetic human printed warning",),
        )
        if self.change:
            # The mutation is confined to a parser receipt at the application port.
            receipt = Borrador100ImportObservation(
                ejercicio=cast(str, self.change.get("ejercicio", receipt.ejercicio)),
                extraction_profile_id=cast(
                    str | None, self.change.get("extraction_profile_id", receipt.extraction_profile_id)
                ),
                extraction_coverage=cast(
                    Decimal | None, self.change.get("extraction_coverage", receipt.extraction_coverage)
                ),
                artefact_kind=receipt.artefact_kind,
                source_pdf_sha256=receipt.source_pdf_sha256,
                values=receipt.values,
                warnings=receipt.warnings,
            )
        self.receipt = receipt
        return receipt


class Events:
    """Only fixed phase/effect facts enter the generic operation journal."""

    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []
        self.phases: list[str] = []

    async def phase(self, phase: str) -> None:
        self.phases.append(phase)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class Operands:
    """Keep the full typed result outside generic journal observations."""

    def __init__(self) -> None:
        self.values: list[BaseModel] = []

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        self.values.append(value)
        return "d" * 64


class Subject:
    """One real authority pin with synthetic inward encrypted-storage stand-ins."""

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self.operation = operation
        self.fence = SnapshotFence()
        self.repository = SnapshotRepository(self.fence)
        self.parser = Parser(self.fence)
        self.events = Events()
        self.operands = Operands()
        self.ports = Borrador100OperationPorts(PROFILE_ID, operation, self.repository, self.parser)

    def compose(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> Borrador100OperationPorts:
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
    all_periods: bool = True,
    operations: frozenset[str] | None = None,
    human: bool = False,
) -> AccessAllowed | AccessDenied:
    """Use the canonical evaluator with coherent explicit API-key/session facts."""
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
        valid_from=CAPTURED_AT - timedelta(days=1),
        expires_at=CAPTURED_AT + timedelta(days=1),
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
        issued_at=CAPTURED_AT,
        expires_at=CAPTURED_AT + timedelta(minutes=2),
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
            now=CAPTURED_AT,
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
