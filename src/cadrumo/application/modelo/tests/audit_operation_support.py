"""Canonical evidence-service fixtures with observed worker and writer boundaries."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast, override
from uuid import UUID

from ....core.operations import profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...evidence.models import EvidenceBundle
from ...evidence.ports import EvidenceBundlePorts
from ...evidence.service import EvidenceBundleService
from ...evidence.tests.test_evidence import InMemoryEvidenceBundleRepository, InMemoryEvidenceWorkUnits
from ...operations.owner import OperationExecutorContext
from ..audit_operation_ports import ModeloAuditOperationPorts
from .m036_operation_support import PROFILE_ID, CommitFence, Events, Operands

WORK_UNIT_ID = "a" * 64
REVISION_ID = "b" * 64
FILING_ID = "c" * 64
NOTE = "synthetic raw operator audit note"
SOURCE_ADDRESS = "synthetic raw document locator"


class Repository(InMemoryEvidenceBundleRepository):
    """Established inward repository detecting misplaced COMMIT or operation writes."""

    def __init__(self, fence: CommitFence) -> None:
        super().__init__()
        self.fence = fence
        self.reads = 0
        self.writes = 0

    @override
    def load(self, identifier: str) -> EvidenceBundle | None:
        assert not self.fence.active, "manifest preparation and post-write reads remain outside COMMIT"
        self.reads += 1
        return super().load(identifier)

    @override
    def save(self, payload: EvidenceBundle) -> None:
        self.writes += 1
        super().save(payload)


class Subject:
    """Reuse typed context and policy fixtures, with canonical evidence service ports."""

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        self.operation = operation
        self.fence = CommitFence()
        self.events = Events()
        self.operands = Operands()
        self.evidence_repository = Repository(self.fence)
        self.work_units = InMemoryEvidenceWorkUnits(work_unit_ids={WORK_UNIT_ID})
        self.evidence = EvidenceBundlePorts(repository=self.evidence_repository, work_units=self.work_units)
        self.service = EvidenceBundleService(ports=self.evidence)
        self.bundle = self.service.build(
            bucket_id=str(PROFILE_ID),
            work_unit_id=WORK_UNIT_ID,
            calculation_revision_id=REVISION_ID,
            filing_record_id=FILING_ID,
            notes=NOTE,
            record_payloads={("calculation_revision", SOURCE_ADDRESS): b"synthetic confidential calculation evidence"},
        )
        self.evidence_repository.writes = 0
        self.audit_ports = ModeloAuditOperationPorts(PROFILE_ID, operation, self.evidence)

    def compose_audit(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> ModeloAuditOperationPorts:
        """Verify exact worker profile and the one supplied genuine publication pin."""
        assert profile_id == PROFILE_ID and operation is self.operation
        return self.audit_ports

    def context(self, definition_id: str) -> OperationExecutorContext:
        """Expose synthetic inward execution ports without native acceptance claims."""
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
