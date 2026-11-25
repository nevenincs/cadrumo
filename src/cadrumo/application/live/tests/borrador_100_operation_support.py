"""Inward synthetic ports for canonical snapshot lifecycle and policy decisions."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from typing import cast, override
from uuid import UUID

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessAllowed, AccessDenialCode, AccessDenied
from cadrumo_client.contracts.access_vocabulary import DisclosurePermission

from ....core.operations import OperationEffect
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_extraction import ExtractionProfileDefinition
from ....domain.calculations.registry.schema_references import TemporalSupportEnvelope
from ...operations.access_resolution import ResolvedOperationAccess
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationRegistry
from ...tests.access_authority_support import scoped_policy_decision
from ...tests.operation_host_fakes import executor_context
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..borrador_100 import Borrador100Snapshot
from ..borrador_100_operation_ports import (
    Borrador100ImportObservation,
    Borrador100OperationPorts,
    Borrador100PrintedValue,
)
from .test_borrador_100 import BUCKET_ID, InMemoryBorradorRepository

PROFILE_ID = UUID(BUCKET_ID)
PROFILE_TAX_ID = "12345678Z"
OTHER_TAX_ID = "00001005Q"
CAPTURED_AT = datetime(2026, 10, 1, 12, tzinfo=UTC)


class SnapshotFence:
    """Record actual writer authority and optionally deny a later save."""

    def __init__(self) -> None:
        self.active = False
        self.entries = 0
        self.deny_entry: int | None = None

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        if self.entries + 1 == self.deny_entry:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        self.entries += 1
        self.active = True
        try:
            yield
        finally:
            self.active = False


class SnapshotRepository(InMemoryBorradorRepository):
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
        self,
        pdf_bytes: bytes,
        *,
        filing_year: int,
        supported_filing_years: TemporalSupportEnvelope,
        extraction_profile: ExtractionProfileDefinition,
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
            tax_id=PROFILE_TAX_ID,
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
                tax_id=cast(str | None, self.change.get("tax_id", receipt.tax_id)),
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
        self.profile_tax_id: str | None = PROFILE_TAX_ID
        self.ports = Borrador100OperationPorts(
            PROFILE_ID, operation, self.repository, self.parser, lambda: self.profile_tax_id
        )

    def compose(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> Borrador100OperationPorts:
        assert profile_id == PROFILE_ID and operation is self.operation
        return self.ports

    def context(self, definition_id: str) -> OperationExecutorContext:
        return executor_context(
            definition_id,
            profile_id=str(PROFILE_ID),
            operation=self.operation,
            cancellation=self.fence,
            events=self.events,
            operands=self.operands,
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
    return scoped_policy_decision(
        resolved,
        registry,
        profile_id=PROFILE_ID,
        now=CAPTURED_AT,
        disclosures=disclosures,
        all_periods=all_periods,
        operations=operations,
        human=human,
    )
