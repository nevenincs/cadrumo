"""Real supervisor coverage for reconciliation of encrypted live captures."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from uuid import uuid4

import pytest

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.modelo_reconciliation import ModeloReconciliationPersistence
from ...application.modelo.reconciliation_import_operation import ModeloReconciliationImportProjection
from ...application.modelo.reconciliation_pull_operation import (
    MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
    ModeloReconciliationPullRequest,
)
from ...application.modelo.reconciliation_records import ModeloReconciliationRecord
from ...core.config import override_settings
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.buckets.event import BucketEvent
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..justificante_composition import build_justificante_capture_service
from . import modelo_operation_test_support
from . import test_registered_executor_conformance as conformance
from .test_modelo_reconciliation_import_operation import _CommitWitness

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_registered_pull_reconciles_encrypted_capture_under_exact_profile_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: PinnedAuthorityOperation
) -> None:
    """A foreign profile cannot read the capture; the correct worker guards its atomic write."""
    witness = _CommitWitness(MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID)
    original_compose = conformance.compose_operation_services
    monkeypatch.setattr(
        conformance,
        "compose_operation_services",
        partial(original_compose, execution_authority=witness),
    )
    original_persist = ModeloReconciliationPersistence.persist_with_event

    def guarded_persist(
        persistence: ModeloReconciliationPersistence,
        record: ModeloReconciliationRecord,
        event: BucketEvent,
    ) -> None:
        assert witness.active
        assert record.bucket_id == str(witness.profile_id)
        assert record.bucket_event_id == event.event_id
        witness.events.append(("atomic-persist", event.event_id))
        original_persist(persistence, record, event)

    monkeypatch.setattr(ModeloReconciliationPersistence, "persist_with_event", guarded_persist)

    with conformance._runtime(tmp_path / "modelo-reconciliation-pull", cleanup=conformance._CloseWitness()) as (
        driver,
        registry,
        profile_id,
    ):
        witness.profile_id = profile_id
        subject_ref = profile_operation_subject(str(profile_id))
        with override_settings(cadrumo_active_profile=str(profile_id)):
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            pdf = (
                Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "justificantes" / "130" / "2024-1T.pdf"
            ).read_bytes()
            snapshot = build_justificante_capture_service(str(profile_id)).capture(
                modelo=str(unit.modelo),
                filing_year=unit.filing_year,
                period=unit.period,
                expediente_id="202413000000001Z",
                csv="ABCD1234EFGH",
                pdf_bytes=pdf,
                pdf_sha256=sha256_hex(pdf),
                captured_at=datetime(2026, 9, 29, tzinfo=UTC),
            )
            before_records = tuple(ModeloReconciliationPersistence().iter_records())
            before_events = BucketEventHistoryRepository().load().events

        request = ModeloReconciliationPullRequest(
            profile_id=profile_id,
            work_unit_id=unit.work_unit_id,
            snapshot_id=snapshot.snapshot_id,
            actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        )
        with override_settings(cadrumo_active_profile=str(uuid4())):
            refused_submission, refused_observation = asyncio.run(
                driver.run(
                    definition_id=MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=request,
                )
            )
        refused = asyncio.run(
            driver.services.submission.supervisor.inspect(refused_submission.receipt.operation_id)
        ).terminal_receipt
        assert refused is not None
        assert refused.condition is OperationTerminalCondition.REFUSED
        assert refused.effect is OperationEffect.NONE
        assert refused_observation.projection.terminal_condition is OperationTerminalCondition.REFUSED
        assert witness.events == []

        with override_settings(cadrumo_active_profile=str(profile_id)):
            submission, observation = asyncio.run(
                driver.run(
                    definition_id=MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=request,
                )
            )
            terminal = asyncio.run(
                driver.services.submission.supervisor.inspect(submission.receipt.operation_id)
            ).terminal_receipt
            after_records = tuple(ModeloReconciliationPersistence().iter_records())
            after_events = BucketEventHistoryRepository().load().events

        assert terminal is not None
        assert terminal.condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.effect is OperationEffect.UPDATED
        assert observation.projection.effect is OperationEffect.UPDATED
        projection = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
            operation_id=submission.receipt.operation_id,
            terminal_revision=observation.projection.revision,
            projection_type=ModeloReconciliationImportProjection,
        )
        assert isinstance(projection, ModeloReconciliationImportProjection)
        assert projection.bucket_id == str(profile_id)
        assert projection.work_unit_id == unit.work_unit_id
        assert projection.source_path.endswith(snapshot.snapshot_id)
        assert after_records[: len(before_records)] == before_records
        assert len(after_records) == len(before_records) + 1
        assert after_records[-1].bucket_event_id in after_events
        assert set(before_events).issubset(after_events)
        assert witness.events[:3] == [
            ("commit-enter", submission.receipt.operation_id),
            ("atomic-persist", after_records[-1].bucket_event_id),
            ("commit-exit", submission.receipt.operation_id),
        ]
