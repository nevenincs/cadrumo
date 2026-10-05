"""Real supervisor coverage for reconciliation of encrypted live captures."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from functools import partial
from pathlib import Path
from uuid import uuid4

import pytest

from ...adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
from ...adapters.outbound.aeat.sede.schema import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    ObservedCasillaValue,
)
from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.modelo_reconciliation import ModeloReconciliationPersistence
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...application.modelo.reconciliation_import_operation import ModeloReconciliationImportProjection
from ...application.modelo.reconciliation_list_operation import ModeloReconciliationListEntryProjection
from ...application.modelo.reconciliation_pull_operation import (
    MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
    ModeloReconciliationPullRequest,
)
from ...application.modelo.reconciliation_records import (
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationRecord,
    ModeloReconciliationVerdict,
    list_modelo_reconciliations,
)
from ...core.casilla_value_kind import CasillaValueKind
from ...core.config import override_settings
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...domain.buckets.event import BucketEvent
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ..justificante_composition import build_justificante_capture_service
from . import modelo_operation_test_support
from . import test_registered_executor_conformance as conformance
from .test_modelo_reconciliation_import_operation import _CommitWitness

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("source", "invalid_evidence"),
    [
        (ModeloReconciliationEvidenceKind.JUSTIFICANTE, None),
        (ModeloReconciliationEvidenceKind.DECLARATION, None),
        (ModeloReconciliationEvidenceKind.DECLARATION, "wrong_period"),
        (ModeloReconciliationEvidenceKind.DECLARATION, "empty_casillas"),
        (ModeloReconciliationEvidenceKind.DECLARATION, "non_numeric_casillas"),
        (ModeloReconciliationEvidenceKind.DECLARATION, "stale_snapshot"),
        (ModeloReconciliationEvidenceKind.DECLARATION, "missing_revision"),
    ],
)
def test_registered_pull_reconciles_encrypted_capture_under_exact_profile_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
    source: ModeloReconciliationEvidenceKind,
    invalid_evidence: str | None,
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
            revision_id: str | None = None
            if source is ModeloReconciliationEvidenceKind.DECLARATION:
                revision_id = modelo_operation_test_support.seeded_modelo_calculation_revision(
                    profile_id, operation=operation
                )
                revision = CalculationRevisionCatalogueRepository().load(operation=operation).get(revision_id)
                assert revision is not None
                unit = WorkUnitCatalogueRepository().load().get(revision.work_unit_id)
                assert unit is not None
                values = dict(revision.casilla_values)
                values["19"] = Decimal("123.45")
                store = FiledDeclaracionObservationStore(tmp_path / "filed")
                manifest = FiledDeclaracionObservation(
                    modelo=str(unit.modelo),
                    ejercicio=unit.filing_year,
                    period=unit.period,
                    expediente_id="202513000000001Z",
                    status="ALTA",
                    presented_at=datetime(2025, 4, 20, tzinfo=UTC),
                    authenticated_identity=modelo_operation_test_support.SEEDED_SOURCE_TAX_ID,
                    artefacts=(
                        FiledDeclaracionArtefact(
                            kind="submitted_file",
                            source_url="https://sede.agenciatributaria.gob.es/test",
                            content_type="text/plain",
                            byte_count=5,
                            sha256=sha256_hex(b"filed"),
                            captured_at=datetime(2026, 9, 29, tzinfo=UTC),
                        ),
                    ),
                    casillas=tuple(
                        ObservedCasillaValue(
                            casilla_id=key,
                            value=str(value),
                            value_kind=CasillaValueKind.NUMERIC,
                            source_artefact_kind="submitted_file",
                            source_locator="synthetic",
                            confidence=1.0,
                        )
                        for key, value in values.items()
                    ),
                    extraction_coverage={"submitted_file": 1.0},
                    registry_snapshot_ref=RegistrySnapshotRef(
                        modelo=unit.modelo,
                        modelo_year=unit.filing_year,
                        period=unit.period.registry_token,
                        revision_id=unit.revision_id,
                    ),
                )
                if invalid_evidence == "wrong_period":
                    manifest = manifest.model_copy(
                        update={
                            "period": Period.from_year_and_code(unit.filing_year, "2T"),
                            "registry_snapshot_ref": manifest.registry_snapshot_ref.model_copy(update={"period": "2T"}),
                        }
                    )
                elif invalid_evidence == "empty_casillas":
                    manifest = manifest.model_copy(update={"casillas": ()})
                elif invalid_evidence == "non_numeric_casillas":
                    manifest = manifest.model_copy(
                        update={
                            "casillas": tuple(
                                row.model_copy(update={"value_kind": CasillaValueKind.TEXT})
                                for row in manifest.casillas
                            ),
                        }
                    )
                elif invalid_evidence == "stale_snapshot":
                    manifest = manifest.model_copy(
                        update={
                            "registry_snapshot_ref": manifest.registry_snapshot_ref.model_copy(
                                update={"revision_id": "retired-revision"}
                            ),
                        }
                    )
                observation_id = store.persist_observation(manifest, operation=operation).name
                snapshot_id = None
            else:
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
                snapshot_id = snapshot.snapshot_id
                observation_id = None
            before_records = tuple(ModeloReconciliationPersistence().iter_records())
            before_events = BucketEventHistoryRepository().load().events

        request = ModeloReconciliationPullRequest(
            profile_id=profile_id,
            work_unit_id=unit.work_unit_id,
            snapshot_id=snapshot_id,
            observation_id=observation_id,
            source_kind=source,
            calculation_revision_id=("a" * 64 if invalid_evidence == "missing_revision" else revision_id)
            if source is ModeloReconciliationEvidenceKind.DECLARATION
            else None,
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
        if invalid_evidence is not None:
            assert terminal.condition is OperationTerminalCondition.REFUSED
            assert terminal.effect is OperationEffect.NONE
            assert observation.projection.terminal_condition is OperationTerminalCondition.REFUSED
            assert after_records == before_records
            assert after_events == before_events
            assert witness.events == []
            return
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
        assert projection.source_path.endswith(snapshot_id or observation_id or "unreachable")
        if source is ModeloReconciliationEvidenceKind.DECLARATION:
            assert projection.calculation_revision_id == revision_id
            assert projection.verdict is ModeloReconciliationVerdict.MISMATCHES
            difference = next(diff for diff in projection.diffs if diff.field_name == "19")
            assert difference.evidence_value == "123.45"
            assert difference.legal_refs and difference.source_refs
            assert projection.advisories == ()
        with override_settings(cadrumo_active_profile=str(profile_id)):
            history = list_modelo_reconciliations(bucket_id=str(profile_id), operation=operation)
        assert history[-1].calculation_revision_id == projection.calculation_revision_id
        assert after_records[-1].calculation_revision_id == projection.calculation_revision_id
        assert history[-1].advisory_count == len(projection.advisories)
        assert ModeloReconciliationListEntryProjection.from_history_entry(history[-1]).advisory_count == len(
            projection.advisories
        )
        assert after_records[: len(before_records)] == before_records
        assert len(after_records) == len(before_records) + 1
        assert after_records[-1].bucket_event_id in after_events
        assert set(before_events).issubset(after_events)
        assert witness.events[:3] == [
            ("commit-enter", submission.receipt.operation_id),
            ("atomic-persist", after_records[-1].bucket_event_id),
            ("commit-exit", submission.receipt.operation_id),
        ]
