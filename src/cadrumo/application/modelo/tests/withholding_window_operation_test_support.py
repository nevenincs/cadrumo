"""Typed synthetic window reads for withholding executor tests."""

from __future__ import annotations

from typing import override

from ...aggregation.retenciones import RetencionObservation
from ...aggregation.withholding_observation_service import (
    EconomicAllocation,
    SourceLiabilitySnapshot,
    WithholdingGenerationAudit,
    WithholdingMutationEnvelope,
    WithholdingMutationMode,
    WithholdingMutationResult,
    WithholdingObservationService,
    WithholdingProjectionEntry,
    WithholdingProjectionIdentity,
    WithholdingProjectionRole,
    WithholdingWindowBaseline,
    WithholdingWindowScope,
    WithholdingWindowState,
)


class WithholdingWindowServiceFixture(WithholdingObservationService):
    """Retain typed read snapshots and reject any unexpected mutation."""

    def __init__(
        self,
        *,
        baseline: WithholdingWindowBaseline,
        generation: int = 0,
        observations: tuple[RetencionObservation, ...] = (),
        include_audit: bool = True,
    ) -> None:
        self.baseline = baseline
        self.generation = generation
        self.observations = observations
        self.include_audit = include_audit
        self.reads: list[WithholdingWindowScope] = []
        self.audit_reads: list[tuple[WithholdingWindowScope, str]] = []

    @override
    def apply(self, envelope: WithholdingMutationEnvelope | None) -> WithholdingMutationResult | None:
        raise AssertionError("the window read fixture must not mutate evidence")

    @override
    def read_window(self, scope: WithholdingWindowScope) -> WithholdingWindowState:
        self.reads.append(scope)
        return WithholdingWindowState(
            scope=scope,
            baseline=self.baseline,
            generation=self.generation,
            persistence_revision_id="b" * 64,
            entries=tuple(_entry(row) for row in self.observations),
        )

    @override
    def read_generation(self, scope: WithholdingWindowScope, generation_id: str) -> WithholdingGenerationAudit | None:
        self.audit_reads.append((scope, generation_id))
        if not self.include_audit:
            return None
        return WithholdingGenerationAudit(
            baseline=WithholdingWindowBaseline(scope_token=scope.token, generation_id=generation_id),
            parent_generation_id="c" * 64,
            mode=WithholdingMutationMode.APPEND,
        )


def _entry(row: RetencionObservation) -> WithholdingProjectionEntry:
    identity = WithholdingProjectionIdentity(
        source_kind=row.source_kind.value,
        source_object_id=row.source_object_id,
        source_revision_id="b" * 64,
        recognition_event_id="synthetic-recognition",
        allocation_id="synthetic-allocation",
        projection_role=WithholdingProjectionRole.RETENCION,
    )
    settlement = row.taxable_base - row.retencion_amount
    return WithholdingProjectionEntry(
        identity=identity,
        allocation=EconomicAllocation(
            liability=SourceLiabilitySnapshot(
                source_kind=identity.source_kind,
                source_object_id=identity.source_object_id,
                source_revision_id=identity.source_revision_id,
                liability_base=row.taxable_base,
                liability_withholding=row.retencion_amount,
                liability_settlement=settlement,
            ),
            recognition_event_id=identity.recognition_event_id,
            allocation_id=identity.allocation_id,
            allocated_base=row.taxable_base,
            allocated_withholding=row.retencion_amount,
            allocated_settlement=settlement,
        ),
        retencion=row,
    )
