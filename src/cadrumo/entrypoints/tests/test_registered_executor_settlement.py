"""Verify executor settlement and persistence outcomes at critical boundaries."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ...application.ledger.models import ManualLedgerTransactionCommand
from ...application.ledger.tests.manual_transaction_support import create_manual_transaction
from ...application.ledger.track_operation import LedgerTrackProjection, LedgerTrackRequest
from ...application.modelo.amendment_action_ports import AmendmentActionPorts
from ...application.modelo.operation_definitions import resolve_active_workflow_profile
from ...application.modelo.work_amend_contracts import ModeloWorkAmendRequest
from ...application.operations.frontend_projection import OperationNoPendingInteractionV1
from ...application.operations.frontend_requests import OperationCancellationRequestV1, OperationCancellationSuccessV1
from ...core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.filing_record import ModeloRecordCatalogue
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ..adapter_composition import build_amendment_action_ports, build_filing_action_ports
from ..ledger_action_composition import compose_ledger_action_ports
from . import modelo_operation_test_support
from .registered_executor_case_support import _CloseWitness, _HeldClock, _resolve_result_projection, _runtime
from .registered_executor_payload_support import _payload
from .registered_executor_scenario_constants import _OPERATOR_SCOPE_PORTS

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_ledger_track_uses_null_when_no_finalized_revision_participates(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """An empty encrypted index stays JSON null for a real ledger transaction."""
    with _runtime(tmp_path / "ledger-track-empty", cleanup=_CloseWitness()) as (driver, registry, profile_id):
        ports = compose_ledger_action_ports(bucket_id=str(profile_id), operation=operation)
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=str(profile_id),
                booked_date=date(2025, 1, 15),
                amount=Decimal("12.00"),
                direction=TransactionDirection.INCOMING,
                description="conformance track empty-index seed",
                business_classification=BusinessClassification.BUSINESS,
                taxable_base=Decimal("12.00"),
                iva_rate=Decimal("0"),
                iva_amount=Decimal("0"),
                actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            ),
            ports=ports,
            occurred_at=now(),
        )
        request = LedgerTrackRequest(profile_id=profile_id, transaction_prefix=created.ref.transaction_id[:12])
        submitted, observed = asyncio.run(
            driver.run(
                definition_id="ledger.track",
                subject_ref=profile_operation_subject(str(profile_id)),
                payload=request,
                secret=None,
            )
        )
        assert observed.projection.lifecycle is OperationLifecycle.TERMINAL
        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert observed.projection.effect is OperationEffect.NONE
        track = _resolve_result_projection(
            driver,
            registry,
            definition_id="ledger.track",
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=LedgerTrackProjection,
        )
        assert isinstance(track, LedgerTrackProjection)
        assert track.transaction.transaction_id == created.ref.transaction_id
        assert track.participated_in is None
        index = TransactionParticipationIndexRepository(bucket_id=str(profile_id)).load(created.ref.transaction_id)
        assert index.transaction_id == created.ref.transaction_id
        assert index.participations == ()
        assert isinstance(observed.projection.pending_interaction, OperationNoPendingInteractionV1)
        asyncio.run(
            driver.review_not_pending(
                operation_id=submitted.receipt.operation_id,
                revision=observed.projection.revision,
                registry=registry,
            )
        )


@pytest.mark.parametrize("raced_catalogue", ["filing", "work_unit", "calculation"])
def test_amendment_co_commit_refuses_each_stale_catalogue_without_partial_writes(
    tmp_path: Path,
    raced_catalogue: str,
    monkeypatch: pytest.MonkeyPatch,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The real amendment writer preserves a valid concurrent write on every CAS axis."""
    filing_record_id: str | None = None
    work_unit_id: str | None = None
    calculation_revision_id: str | None = None
    raced: list[str] = []
    raced_calculation_instants: list[datetime] = []
    concurrent_filing_note = "concurrent filing catalogue update"
    concurrent_work_unit_name = "Concurrent work-unit update"

    def amendment_ports_factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> AmendmentActionPorts:
        ports = build_amendment_action_ports(bucket_id=bucket_id, operation=operation)
        if raced_catalogue == "filing":
            filing_repository = cast(ModeloRecordCatalogueRepository, ports.filing_repository)
            original_filing_load = filing_repository.load_revisioned

            def load_revisioned() -> tuple[ModeloRecordCatalogue, str]:
                catalogue, revision_id = original_filing_load()
                if not raced:
                    assert filing_record_id is not None
                    record = catalogue.get(filing_record_id)
                    assert record is not None
                    concurrent_record = record.model_copy(update={"notes": concurrent_filing_note})
                    filing_repository.save(
                        ModeloRecordCatalogue(records={**catalogue.records, filing_record_id: concurrent_record})
                    )
                    raced.append(raced_catalogue)
                return catalogue, revision_id

            monkeypatch.setattr(filing_repository, "load_revisioned", load_revisioned)
        elif raced_catalogue == "work_unit":
            work_unit_repository = cast(WorkUnitCatalogueRepository, ports.work_unit_repository)
            original_work_unit_load = work_unit_repository.load_revisioned

            def load_revisioned() -> tuple[WorkUnitCatalogue, str]:
                catalogue, revision_id = original_work_unit_load()
                if not raced:
                    assert work_unit_id is not None
                    original_unit = catalogue.get(work_unit_id)
                    assert original_unit is not None
                    updated_at = max(now(), original_unit.updated_at) + timedelta(seconds=1)
                    concurrent_unit = WorkUnit.model_validate(
                        {
                            **original_unit.model_dump(mode="python"),
                            "name": concurrent_work_unit_name,
                            "updated_at": updated_at,
                        },
                        strict=True,
                    )
                    work_unit_repository.save(
                        WorkUnitCatalogue(work_units={**catalogue.work_units, work_unit_id: concurrent_unit})
                    )
                    raced.append(raced_catalogue)
                return catalogue, revision_id

            monkeypatch.setattr(work_unit_repository, "load_revisioned", load_revisioned)
        elif raced_catalogue == "calculation":
            calculation_repository = cast(CalculationRevisionCatalogueRepository, ports.calculation_repository)
            original_calculation_load = calculation_repository.load_revisioned

            def load_revisioned(
                *, operation: PinnedAuthorityOperation | None = None
            ) -> tuple[CalculationRevisionCatalogue, str]:
                catalogue, revision_id = original_calculation_load(operation=operation)
                if not raced:
                    assert calculation_revision_id is not None
                    revision = catalogue.get(calculation_revision_id)
                    assert revision is not None
                    lifecycle_instants = (
                        revision.created_at,
                        revision.updated_at,
                        revision.verified_at,
                        revision.filed_at,
                        revision.superseded_at,
                        revision.discarded_at,
                    )
                    updated_at = max(instant for instant in lifecycle_instants if instant is not None) + timedelta(
                        seconds=1
                    )
                    concurrent_revision = revision.model_copy(update={"updated_at": updated_at})
                    calculation_repository.save(
                        CalculationRevisionCatalogue(
                            revisions={
                                **catalogue.revisions,
                                calculation_revision_id: concurrent_revision,
                            }
                        )
                    )
                    raced_calculation_instants.append(updated_at)
                    raced.append(raced_catalogue)
                return catalogue, revision_id

            monkeypatch.setattr(calculation_repository, "load_revisioned", load_revisioned)
        else:  # pragma: no cover - parametrization is deliberately closed.
            raise AssertionError(f"unknown amendment CAS catalogue: {raced_catalogue}")
        return ports

    with _runtime(
        tmp_path / f"amendment-cas-{raced_catalogue}",
        cleanup=_CloseWitness(),
        amendment_action_ports_factory=amendment_ports_factory,
    ) as (driver, registry, profile_id):
        definition = registry.lookup("modelo.work.amend")
        subject_ref, payload, secret = _payload(
            definition,
            profile_id=profile_id,
            tmp_path=tmp_path / f"amendment-cas-{raced_catalogue}",
            operation=operation,
        )
        assert secret is None
        assert isinstance(payload, ModeloWorkAmendRequest)
        filing_record_id = payload.baseline.from_filing_record_id

        records_before = ModeloRecordCatalogueRepository().load()
        baseline = records_before.get(filing_record_id)
        assert baseline is not None
        work_unit_id = baseline.work_unit_id
        calculation_revision_id = baseline.calculation_revision_id
        work_units_before = WorkUnitCatalogueRepository().load()
        calculations_before = CalculationRevisionCatalogueRepository().load()
        events_before = BucketEventHistoryRepository().load()
        original_work_unit = work_units_before.get(work_unit_id)
        assert original_work_unit is not None
        assert calculations_before.get(calculation_revision_id) is not None

        submitted, observed = asyncio.run(
            driver.run(definition_id=definition.definition_id, subject_ref=subject_ref, payload=payload)
        )
        assert observed.projection.lifecycle is OperationLifecycle.TERMINAL
        assert observed.projection.terminal_condition is OperationTerminalCondition.FAILED
        assert observed.projection.effect is OperationEffect.UNKNOWN
        assert observed.projection.result_ref is None
        assert observed.projection.diagnostic_ref is not None
        assert raced == [raced_catalogue]

        records_after = ModeloRecordCatalogueRepository().load()
        work_units_after = WorkUnitCatalogueRepository().load()
        calculations_after = CalculationRevisionCatalogueRepository().load()
        events_after = BucketEventHistoryRepository().load()
        if raced_catalogue == "filing":
            concurrent_record = records_after.get(filing_record_id)
            assert concurrent_record is not None
            assert concurrent_record.notes == concurrent_filing_note
            expected_records = dict(records_before.records)
            expected_records[filing_record_id] = concurrent_record
            assert records_after.records == expected_records
        else:
            assert records_after.records == records_before.records
        if raced_catalogue == "work_unit":
            concurrent_unit = work_units_after.get(work_unit_id)
            assert concurrent_unit is not None
            assert concurrent_unit.name == concurrent_work_unit_name
            assert concurrent_unit.updated_at > original_work_unit.updated_at
            expected_work_units = dict(work_units_before.work_units)
            expected_work_units[work_unit_id] = concurrent_unit
            assert work_units_after.work_units == expected_work_units
        else:
            assert work_units_after.work_units == work_units_before.work_units
        if raced_catalogue == "calculation":
            concurrent_revision = calculations_after.get(calculation_revision_id)
            assert concurrent_revision is not None
            assert len(raced_calculation_instants) == 1
            assert concurrent_revision.updated_at == raced_calculation_instants[0]
            expected_revisions = dict(calculations_before.revisions)
            expected_revisions[calculation_revision_id] = concurrent_revision
            assert calculations_after.revisions == expected_revisions
        else:
            assert calculations_after.revisions == calculations_before.revisions
        assert events_after.events == events_before.events
        assert not any(record.amends_filing_record_id is not None for record in records_after.records.values())
        assert submitted.receipt.operation_id == observed.projection.operation_id


def test_calculate_refused_before_persisting_reports_no_effect(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A precondition refusal settles REFUSED with NONE, never the open UNKNOWN.

    Modelo 303 filing evidence addressed to a Modelo 130 unit is refused while
    the executor is still only reading, so nothing can have been written and
    the truthful effect is NONE.
    """
    with _runtime(tmp_path / "calculate-refusal", cleanup=_CloseWitness()) as (driver, registry, profile_id):
        definition = registry.lookup("modelo.work.calculate")
        unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
        payload = definition.request_type.model_validate(
            {
                "work_unit_id": unit.work_unit_id,
                "actor": modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                "ordinary_m303_filing_evidence": {"joint_return_elected": False},
            },
            strict=True,
        )

        _submitted, observed = asyncio.run(
            driver.run(definition_id=definition.definition_id, subject_ref=unit.work_unit_id, payload=payload)
        )

        assert observed.projection.lifecycle is OperationLifecycle.TERMINAL
        assert observed.projection.terminal_condition is OperationTerminalCondition.REFUSED
        assert observed.projection.refusal_ref == "REFUSED_MODELO_M303_FILING_EVIDENCE"
        assert observed.projection.effect is OperationEffect.NONE


def test_censo_cooperative_cancellation_settles_after_its_irreversible_section(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Drive manual cancellation through the public control service to its exact terminal receipt."""
    reached_boundary = asyncio.Event()
    release_boundary = asyncio.Event()

    async def before_irreversible_section() -> None:
        reached_boundary.set()
        await release_boundary.wait()

    cleanup = _CloseWitness()
    with _runtime(
        tmp_path / "censo-cancellation",
        cleanup=cleanup,
        before_irreversible_section=before_irreversible_section,
    ) as (driver, registry, profile_id):
        definition = registry.lookup("user-profile.censo-review")
        subject_ref, payload, secret = _payload(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )

        async def run() -> None:
            submitted = await driver.prepare(
                definition_id=definition.definition_id,
                subject_ref=subject_ref,
                payload=payload,
                secret=secret,
            )
            await driver.services.submission.start(submitted.receipt.operation_id)
            await driver.services.submission.settled(submitted.receipt.operation_id)
            waiting = await driver.observe(submitted.receipt.operation_id)
            operation_id = await driver.respond_apply(submitted, waiting)
            await reached_boundary.wait()
            running = await driver.observe(operation_id)
            requested = await driver.services.cancellation.request(
                OperationCancellationRequestV1(operation_id=operation_id, expected_revision=running.projection.revision)
            )
            assert isinstance(requested, OperationCancellationSuccessV1)
            assert requested.cancellation_acknowledged is False
            release_boundary.set()
            terminal = await driver.await_terminal(operation_id)
            assert terminal.projection.terminal_condition is OperationTerminalCondition.CANCELLED
            assert terminal.projection.effect is OperationEffect.NONE
            assert terminal.projection.cancellation_acknowledged is True
            assert terminal.projection.cleanup_deadline_at is not None
            assert cleanup.closed is True

        asyncio.run(run())


def test_censo_execution_deadline_settles_its_actual_cooperative_safe_stop(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Let the supervisor-owned deadline drive the production CENSO continuation to timed out.

    The deadline must pass while the review waits, not while the executor is
    still working up to it: a deadline that expires first stops the executor
    before any review exists. Holding the supervisor clock until the review is
    on offer fixes that order on any host instead of racing a 50 ms budget.
    """
    cleanup = _CloseWitness()
    clock = _HeldClock()
    with _runtime(
        tmp_path / "censo-deadline",
        cleanup=cleanup,
        execution_timeout=timedelta(milliseconds=50),
        clock=clock,
    ) as (driver, registry, profile_id):
        definition = registry.lookup("user-profile.censo-review")
        subject_ref, payload, secret = _payload(
            definition, profile_id=profile_id, tmp_path=tmp_path, operation=operation
        )

        async def run() -> None:
            submitted, waiting = await driver.run(
                definition_id=definition.definition_id,
                subject_ref=subject_ref,
                payload=payload,
                secret=secret,
            )
            assert waiting.projection.execution_deadline_at is not None
            await asyncio.sleep(max((waiting.projection.execution_deadline_at - now()).total_seconds(), 0) + 0.01)
            clock.release()
            operation_id = await driver.respond_apply(submitted, waiting)
            terminal = await driver.await_terminal(operation_id)
            assert terminal.projection.terminal_condition is OperationTerminalCondition.TIMED_OUT
            assert terminal.projection.effect is OperationEffect.NONE
            assert terminal.projection.cancellation_requested is True
            assert terminal.projection.cancellation_acknowledged is True
            assert terminal.projection.cleanup_deadline_at is not None
            assert cleanup.closed is True

        asyncio.run(run())


def test_the_filing_authority_accepts_the_registered_operation_fixture(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The direct filing door accepts the same genuine grant as the executor.

    This control uses the same seeded and verified revision, actor and workflow
    profile as the registered operation. It separates fixture/domain validity
    from any future operation-wrapper regression without fabricating a report.
    """
    from ...application.modelo.filing_actions import file_modelo_revision

    with _runtime(tmp_path / "authority-control", cleanup=_CloseWitness()) as (_driver, _registry, profile_id):
        revision_id, report_id = modelo_operation_test_support.seeded_modelo_verification_report(
            profile_id, operation=operation
        )

        with bundled_indexed_authority().operation() as operation:
            record = file_modelo_revision(
                revision_id,
                approved_verification_report_id=report_id,
                certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                ports=build_filing_action_ports(bucket_id=str(profile_id), operation=operation),
                actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
                workflow_profile=resolve_active_workflow_profile(operation),
                operation=operation,
                notes=None,
            ).record

        assert record is not None, "the filing authority produced no record for a verified-complete revision"
