"""Real encrypted storage for proving that operator work survives edits and recalculation.

Entrypoint tests consume this defining test-support module directly. It seeds
one complete synthetic taxpayer and one work unit through the production doors
(profile capsule, ``create_work_unit``) and hands back the composed calculation
ports, so a test drives the same calculation boundary, edit executor and
persistence writer production uses. Every value is synthetic.

A Modelo 303 unit additionally needs what every real 303 calculation needs: an
activity start that grounds the first period's zero compensation, the
persisted zero IVA-wallet decision that gate reads, and the operator's filing
evidence for the first calculation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

from pydantic import BaseModel

from ...adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
from ...adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts,
    seed_test_profile_record,
)
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.calculations.tests.filing_evidence import general_m303_filing_evidence
from ...application.modelo.calculation_action_ports import CalculationActionPorts
from ...application.modelo.edit_admission import (
    ModeloEditRenewalResultV1,
    admit_modelo_edit_baseline,
    renew_modelo_edit_baseline,
)
from ...application.modelo.edit_contract import ModeloEditMutationFamily
from ...application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditAdmissionResultV1,
    ModeloEditAdmittedV1,
    ModeloEditBaselineV1,
    ModeloEditSubmissionV1,
    ModeloScalarEditIntentV1,
)
from ...application.modelo.edit_receipt_ports import ModeloEditReceiptRepositoryFactory
from ...application.modelo.operation_definitions import (
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    ModeloEditApplyExecutor,
    ModeloEditApplyOperationRequestV1,
    ModeloEditApplySubmissionV1,
    ModeloWorkCalculateExecutor,
    ModeloWorkCalculateRequest,
)
from ...application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
from ...application.modelo.work_lifecycle import create_work_unit
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.operations.owner import OperationExecutorContext
from ...core.errors.hierarchy import CadrumoError
from ...core.hashing import content_hash_hex
from ...core.operations import OperationEffect
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
from ...domain.modelos.work_unit import WorkUnit
from ...domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ..adapter_composition import (
    build_attachment_store,
    build_calculation_action_ports,
    build_modelo_edit_receipt_repository,
    build_work_lifecycle_ports,
)
from ..operation_composition import build_production_operation_registry

SEEDED_AT = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
_BUCKET_ID = "13000000-0000-4000-8000-000000000730"
_SEEDED_TAX_ID = next(str(fact.value) for fact in MODELO_READY_PROFILE_FACTS if fact.path == "identity.tax_id")
"""The identity.tax_id the modelo readiness baseline seeds; the wallet decision is filed under it."""
_ACTIVITY_START = UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1))


@dataclass(slots=True)
class _RecordedEvents:
    """The executor's phase and effect reports, kept for assertions."""

    phases: list[str] = field(default_factory=list)
    effects: list[OperationEffect] = field(default_factory=list)

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


@dataclass(frozen=True, slots=True)
class _ExecutorContext:
    """The narrow slice of the supervisor context the edit executor reads.

    The supervisor itself (journal, lease, custody) is proven by the registered
    executor conformance suite; these tests are about what the edit does to the
    operator's work, so they drive the production executor directly.
    """

    identity: OperationIdentity
    authority_operation: PinnedAuthorityOperation
    events: _RecordedEvents


@dataclass(frozen=True, slots=True)
class AppliedEdit:
    """One executor run: the settled revision id, or the registered refusal it raised."""

    calculation_revision_id: str | None
    refusal: CadrumoError | None
    effects: tuple[OperationEffect, ...]


@dataclass(frozen=True, slots=True)
class SeededOperatorWork:
    """One seeded work unit with the ports and pinned authority that calculate and edit it."""

    work_unit: WorkUnit
    ports: CalculationActionPorts
    operation: PinnedAuthorityOperation
    receipt_repository_factory: ModeloEditReceiptRepositoryFactory

    @property
    def work_unit_id(self) -> str:
        return self.work_unit.work_unit_id

    def head(self) -> CalculationRevision | None:
        """Load the work unit's current calculation revision afresh from storage."""
        unit = self.ports.work_unit_repository.load().get(self.work_unit.work_unit_id)
        if unit is None or unit.current_calculation_revision_id is None:
            return None
        return self.ports.calculation_repository.load().get(unit.current_calculation_revision_id)

    def require_head(self) -> CalculationRevision:
        head = self.head()
        if head is None:
            raise AssertionError("the seeded work unit has no current calculation revision")
        return head

    def admit(self, *, issued_at: datetime | None = None) -> ModeloEditAdmissionResultV1:
        """Admit a fresh edit baseline against the stored catalogues."""
        return admit_modelo_edit_baseline(
            work_unit_id=self.work_unit_id,
            work_catalogue=self.ports.work_unit_repository.load(),
            calculation_catalogue=self.ports.calculation_repository.load(),
            operation=self.operation,
            operation_contracts=build_production_operation_registry().public_contract_set,
            issued_at=issued_at,
        )

    def renew(self, baseline: ModeloEditBaselineV1) -> ModeloEditRenewalResultV1:
        """Renew ``baseline`` against the stored catalogues, as an editor does before review and submit."""
        return renew_modelo_edit_baseline(
            baseline,
            work_catalogue=self.ports.work_unit_repository.load(),
            calculation_catalogue=self.ports.calculation_repository.load(),
            operation=self.operation,
            operation_contracts=build_production_operation_registry().public_contract_set,
        )

    def sibling(self, period_code: str) -> SeededOperatorWork:
        """Create another declaration of the same modelo and year in the same profile."""
        unit = create_work_unit(
            bucket_id=self.work_unit.bucket_id,
            modelo=str(self.work_unit.modelo),
            filing_year=self.work_unit.filing_year,
            period=Period.from_year_and_code(self.work_unit.filing_year, period_code),
            revision_id=str(
                self.operation.revision_for_context(
                    str(self.work_unit.modelo),
                    filing_year=self.work_unit.filing_year,
                    period=Period.from_year_and_code(self.work_unit.filing_year, period_code).registry_token,
                ).id
            ),
            ports=build_work_lifecycle_ports(bucket_id=self.work_unit.bucket_id),
            clock=SEEDED_AT,
            operation=self.operation,
        )
        return SeededOperatorWork(
            work_unit=unit,
            ports=self.ports,
            operation=self.operation,
            receipt_repository_factory=self.receipt_repository_factory,
        )

    def baseline(self) -> ModeloEditBaselineV1:
        admission = self.admit()
        if not isinstance(admission, ModeloEditAdmittedV1):
            raise AssertionError(f"the seeded work unit was refused edit admission: {admission!r}")
        return admission.baseline

    def apply(
        self,
        *,
        scalar: tuple[ModeloScalarEditIntentV1, ...] = (),
        binding: tuple[ModeloBindingEditIntentV1, ...] = (),
        baseline: ModeloEditBaselineV1 | None = None,
    ) -> AppliedEdit:
        """Run one submission through the production edit executor, as the operation would."""
        admitted = baseline if baseline is not None else self.baseline()
        submission = ModeloEditSubmissionV1(
            baseline=admitted,
            mutation_family=ModeloEditMutationFamily.CALCULATE,
            scalar_intents=scalar,
            binding_intents=binding,
        )
        request = OperationRequest(
            definition_id=MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
            subject_ref=self.work_unit_id,
            payload=ModeloEditApplyOperationRequestV1(
                submission=ModeloEditApplySubmissionV1.from_submission(submission)
            ),
        )
        return self._run_edit(
            request, operation_id=content_hash_hex({"baseline": admitted.baseline_id, "submission": repr(submission)})
        )

    def execute(self, request: OperationRequest[BaseModel]) -> CadrumoError | None:
        """Run an edit request a frontend submitted through the production edit executor; its refusal, if any."""
        return self._run_edit(request, operation_id=content_hash_hex({"request": repr(request)})).refusal

    def _run_edit(self, request: OperationRequest[BaseModel], *, operation_id: str) -> AppliedEdit:
        if not isinstance(request.payload, ModeloEditApplyOperationRequestV1):
            raise TypeError("edit executor requires a modelo edit apply request")
        typed_request = OperationRequest[ModeloEditApplyOperationRequestV1](
            definition_id=request.definition_id,
            subject_ref=request.subject_ref,
            payload=request.payload,
            idempotency_key=request.idempotency_key,
        )
        executor = ModeloEditApplyExecutor(
            calculation_action_ports_factory=lambda **_: self.ports,
            receipt_repository_factory=self.receipt_repository_factory,
        )
        events = _RecordedEvents()
        context = _ExecutorContext(
            identity=OperationIdentity(
                operation_id=operation_id,
                definition_id=MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
                subject_ref=self.work_unit_id,
            ),
            authority_operation=self.operation,
            events=events,
        )
        try:
            asyncio.run(
                executor.execute(
                    typed_request,
                    cast(OperationExecutorContext, context),
                )
            )
        except CadrumoError as refused:
            return AppliedEdit(calculation_revision_id=None, refusal=refused, effects=tuple(events.effects))
        head = self.require_head()
        return AppliedEdit(
            calculation_revision_id=head.calculation_revision_id, refusal=None, effects=tuple(events.effects)
        )

    def recalculate(self) -> CalculationRevision:
        """Run the workspace Calculate operation's production executor, with no new answers."""
        executor = ModeloWorkCalculateExecutor(
            calculation_action_ports_factory=lambda **_: self.ports,
            attachment_store_factory=build_attachment_store,
        )
        context = _ExecutorContext(
            identity=OperationIdentity(
                operation_id=content_hash_hex({"recalculate": self.work_unit_id, "at": datetime.now(UTC).isoformat()}),
                definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
                subject_ref=self.work_unit_id,
            ),
            authority_operation=self.operation,
            events=_RecordedEvents(),
        )
        request = OperationRequest(
            definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
            subject_ref=self.work_unit_id,
            payload=ModeloWorkCalculateRequest(work_unit_id=self.work_unit_id, actor="operator:test"),
        )
        asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
        return self.require_head()

    def m303_filing_evidence(self) -> FilingInstanceEvidence:
        """The operator's first-calculation filing evidence for a Modelo 303 unit."""
        return general_m303_filing_evidence(
            self.work_unit.period, reference="test:operator-work", operation=self.operation
        )


def _first_period_zero_iva_decision(unit: WorkUnit, *, operation: PinnedAuthorityOperation) -> None:
    """Persist the zero compensation decision a first 303 period's wallet gate reads.

    Zero is the grounded answer: the seeded activity start is years earlier and
    no prior 303 exists in this fresh bucket, so nothing is pending compensation.
    """
    period_code = unit.period.registry_token
    IvaWalletDecisionRepository().save_decision(
        IvaCompensationReconciliationDecision(
            taxpayer_nif=_SEEDED_TAX_ID,
            target_year=unit.filing_year,
            target_period=unit.period,
            target_registry_snapshot_ref=operation.snapshot(
                "303", filing_year=unit.filing_year, period=period_code
            ).snapshot_ref,
            source_registry_snapshot_refs=(),
            selected_authority="aeat_wallet",
            selected_amount=Decimal("0"),
            wallet_amount=Decimal("0"),
            divergence="match",
            blocked=False,
            stale_wallet=False,
            reason_identity="first_period_zero_aeat_wallet",
            decided_at=SEEDED_AT,
        )
    )


@contextmanager
def seeded_operator_work(
    tmp_path: Path,
    *,
    modelo: str = "130",
    filing_year: int = 2026,
    period_code: str = "1T",
    extra_facts: tuple[UserProfileFact, ...] = (),
) -> Generator[SeededOperatorWork]:
    """Yield one seeded, not yet calculated work unit over isolated encrypted storage.

    ``extra_facts`` are profile facts the declaration needs beyond the
    modelo-ready baseline, such as an attestation the check reads.
    """
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile,
        bundled_indexed_authority().operation() as operation,
    ):
        create_context, _ = profile_authority_contexts()
        seed_test_profile_record(
            create_user_profile_record(
                context=create_context,
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=(*MODELO_READY_PROFILE_FACTS, _ACTIVITY_START, *extra_facts),
                created_at=SEEDED_AT,
                updated_at=SEEDED_AT,
            )
        )
        period = Period.from_year_and_code(filing_year, period_code)
        revision = operation.revision_for_context(modelo, filing_year=filing_year, period=period.registry_token)
        unit = create_work_unit(
            bucket_id=profile.bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=str(revision.id),
            ports=build_work_lifecycle_ports(bucket_id=profile.bucket_id),
            clock=SEEDED_AT,
            operation=operation,
        )
        if modelo == "303":
            _first_period_zero_iva_decision(unit, operation=operation)
        yield SeededOperatorWork(
            work_unit=unit,
            ports=build_calculation_action_ports(bucket_id=profile.bucket_id, operation=operation),
            operation=operation,
            receipt_repository_factory=build_modelo_edit_receipt_repository,
        )
