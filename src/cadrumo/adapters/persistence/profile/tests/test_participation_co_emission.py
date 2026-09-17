"""Integration proof: the participation index co-emits with verify and file.

Reconstructs participation from REAL calculation revisions persisted through the
production persistence helpers against a real encrypted SQLite store — no mocks. A
revision over two ledger transactions verifies, then files; the test asserts a
participation entry lands for every ``source_transaction_id``, that the filed
entry carries the ``filing_record_id``, and that the lifecycle write-guard
``blocking_modelo_references`` keeps returning the live-scan blockers unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger.actions_common import blocking_modelo_references
from cadrumo.application.modelo.revision_persistence import persist_filed_revision
from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.period import Period
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo.domain.calculations.registry.bindings import CasillaObservation
from cadrumo.domain.calculations.registry.casilla_membership import casillas_by_id
from cadrumo.domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_RESULTADO_CASILLA,
)
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.participation_index import (
    TransactionRevisionParticipation,
    upsert_transaction_participation,
)
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "5fb44bbf-c0c5-4701-b2a9-d4d521e66fb5"  # was 'modelo-participation-co-emission'
_T0 = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)


def _hex(seed: str) -> str:
    return (seed * 64)[:64]


_TX_A = _hex("a")
_TX_B = _hex("b")
# The Modelo 303 result casilla: a filed observation must name a casilla the
# selected registry revision declares, and its value states the disposition.
_M303_RESULT_CASILLA: CasillaId = M303_COMPENSATION_RESULTADO_CASILLA


def _iva_wallet_repositories() -> tuple[CalculationObservationRepository, IvaCompensationHistoryRepository]:
    """Build the two real IVA adapters directly for this persistence test."""
    objects = secure_object_repository_for_active_bucket()
    return (
        CalculationObservationRepository(objects=objects),
        IvaCompensationHistoryRepository(objects=objects),
    )


def _seed_borrador(
    *,
    cr_repo: CalculationRevisionCatalogueRepository,
    wu_repo: WorkUnitCatalogueRepository,
) -> tuple[CalculationRevision, WorkUnit]:
    """Persist a BORRADOR revision over two ledger transactions plus its work unit."""
    snapshot = published_snapshot("303", filing_year=2024, period="2T")
    revision_id_seed = str(snapshot.revision.id)
    result_casilla = casillas_by_id(snapshot.revision)[_M303_RESULT_CASILLA]
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "2T"),
        revision_id=revision_id_seed,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=Period.from_year_and_code(2024, "2T"),
        revision_id=revision_id_seed,
        name="303-2024-2T",
        created_at=_T0,
        updated_at=_T0,
    )
    wu_repo.save(upsert_work_unit(wu_repo.load(), work_unit))

    source_transaction_ids = (_TX_A, _TX_B)
    input_values_by_casilla_id = {_M303_RESULT_CASILLA: "1000.00"}
    casilla_values = {_M303_RESULT_CASILLA: Decimal("1000.00")}
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides={},
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=input_values_by_casilla_id,
        source_transaction_ids=source_transaction_ids,
        casilla_values=casilla_values,
        observations=(
            CasillaObservation(
                casilla_id=_M303_RESULT_CASILLA,
                value=Decimal("1000.00"),
                legal_refs=tuple(result_casilla.legal_refs),
                source_refs=tuple(result_casilla.source_refs),
            ),
        ),
        created_at=_T0,
        updated_at=_T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    return revision, work_unit


def _seed_verified_participation(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    calculation_repository: CalculationRevisionCatalogueRepository,
    participation_index_repository: TransactionParticipationIndexRepository,
    actor: str,
    now: datetime,
) -> None:
    """Seed the verified state and prior index rows for the filing co-write proof."""
    revisions, revisions_revision_id = calculation_repository.load_revisioned()
    verified = target.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": now,
            "verified_by": actor.strip(),
            "updated_at": now,
        },
    )
    updated_catalogue = upsert_calculation_revision(revisions, verified)
    participation_writes = []
    for transaction_id in verified.source_transaction_ids:
        index = participation_index_repository.load(transaction_id)
        participation = TransactionRevisionParticipation(
            calculation_revision_id=verified.calculation_revision_id,
            work_unit_id=work_unit.work_unit_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            revision_state=CalculationRevisionState.VERIFICADO_COMPLETO.value,
        )
        updated = upsert_transaction_participation(index, participation)
        participation_writes.append(participation_index_repository.to_secure_object_write(updated))
    calculation_repository.save_with_secure_object_writes(
        updated_catalogue,
        tuple(participation_writes),
        expected_revision_id=revisions_revision_id,
    )


def test_verify_then_file_co_emits_participation_for_every_source_transaction(tmp_path: Path) -> None:
    """Verify then file a revision; the participation index records both transactions."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            cr_repo = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
            wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID)
            fr_repo = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID)
            bv_repo = _bucket_event_repository()
            participation_repo = TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID)

            revision, work_unit = _seed_borrador(cr_repo=cr_repo, wu_repo=wu_repo)

            # --- VERIFY (co-emits VERIFICADO_COMPLETO participations) ---
            verified_at = _T0 + timedelta(hours=3)
            _seed_verified_participation(
                target=revision,
                actor="aeat.cli.modelo.verify",
                now=verified_at,
                work_unit=work_unit,
                calculation_repository=cr_repo,
                participation_index_repository=participation_repo,
            )

            index_a = participation_repo.load(_TX_A)
            index_b = participation_repo.load(_TX_B)
            assert len(index_a.participations) == 1
            assert len(index_b.participations) == 1
            verified_entry = index_a.participations[0]
            assert verified_entry.calculation_revision_id == revision.calculation_revision_id
            assert verified_entry.revision_state == "verificado_completo"
            assert verified_entry.modelo == "303"
            assert verified_entry.filing_year == 2024
            assert verified_entry.period == Period.from_year_and_code(2024, "2T")
            assert verified_entry.filing_record_id is None

            # --- FILE (replaces the verified entry in place, gaining filing_record_id) ---
            verified_revision = cr_repo.load().get(revision.calculation_revision_id)
            assert verified_revision is not None
            assert verified_revision.state is CalculationRevisionState.VERIFICADO_COMPLETO

            filed_at = verified_at + timedelta(hours=1)
            calculation_observation_repository, iva_compensation_history_repository = _iva_wallet_repositories()
            prorrata_repository = ProrrataRegisterRepository(bucket_id=_BUCKET_ID)
            filing_record = persist_filed_revision(
                target=verified_revision,
                work_unit=work_unit,
                work_units=wu_repo.load(),
                notes=None,
                actor="aeat.cli.modelo.file",
                now=filed_at,
                calculation_repository=cr_repo,
                filing_repository=fr_repo,
                work_unit_repository=wu_repo,
                bucket_event_repository=bv_repo,
                calculation_observation_repository=calculation_observation_repository,
                iva_compensation_history_repository=iva_compensation_history_repository,
                participation_index_repository=participation_repo,
                prorrata_register_repository=prorrata_repository,
                # The seeded result is a positive amount due, so the filing is an ingreso.
                result_disposition=ResultDisposition.INGRESO,
                operation=_authority_operation_for_test,
            )

            filed_index_a = participation_repo.load(_TX_A)
            filed_index_b = participation_repo.load(_TX_B)

            # --- write-guard live-scan correctness is unchanged by the index ---
            blockers = blocking_modelo_references(
                bucket_id=_BUCKET_ID,
                transaction_ids=(_TX_A,),
                work_unit_repository=wu_repo,
                calculation_repository=cr_repo,
            )

        # The verified entry was replaced in place — still exactly one per transaction.
        assert len(filed_index_a.participations) == 1
        assert len(filed_index_b.participations) == 1
        filed_entry = filed_index_a.participations[0]
        assert filed_entry.calculation_revision_id == revision.calculation_revision_id
        assert filed_entry.revision_state == "presentado"
        assert filed_entry.filing_record_id == filing_record.filing_record_id

        # The live write-guard scan still returns the PRESENTADO revision as a blocker.
        assert len(blockers) == 1
        assert blockers[0].calculation_revision_id == revision.calculation_revision_id
        assert blockers[0].revision_state == "presentado"


def _bucket_event_repository():
    from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository

    return BucketEventHistoryRepository()
