"""Integration proof: the participation index co-emits with verify and file.

Reconstructs participation from REAL calculation revisions persisted through the
production persist helpers (``_persist_verified_revision_evidence`` and
``persist_filed_revision``) against a real encrypted SQLite store — no mocks. A
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

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ....application.ledger.actions_common import blocking_modelo_references
from ....core import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._revision_persistence import persist_filed_revision
from .._verification_actions import _persist_verified_revision_evidence

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "5fb44bbf-c0c5-4701-b2a9-d4d521e66fb5"  # was 'modelo-participation-co-emission'
_T0 = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)


def _hex(seed: str) -> str:
    return (seed * 64)[:64]


_TX_A = _hex("a")
_TX_B = _hex("b")
_IVA_BASE_IMPONIBLE_CASILLA: CasillaId = validated_casilla_id(
    "iva.base-imponible",
    surface="_IVA_BASE_IMPONIBLE_CASILLA",
)


def _seed_borrador(
    *,
    cr_repo: CalculationRevisionCatalogueRepository,
    wu_repo: WorkUnitCatalogueRepository,
) -> tuple[CalculationRevision, WorkUnit]:
    """Persist a BORRADOR revision over two ledger transactions plus its work unit."""
    revision_id_seed = "303"
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
    input_values_by_casilla_id = {_IVA_BASE_IMPONIBLE_CASILLA: "1000.00"}
    casilla_values = {_IVA_BASE_IMPONIBLE_CASILLA: Decimal("1000.00")}
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
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=input_values_by_casilla_id,
        source_transaction_ids=source_transaction_ids,
        casilla_values=casilla_values,
        observations=(
            CasillaObservation(
                casilla_id=_IVA_BASE_IMPONIBLE_CASILLA,
                value=Decimal("1000.00"),
                legal_refs=("ley-37-1992:art-164",),
                source_refs=("participation-co-emission-test",),
            ),
        ),
        created_at=_T0,
        updated_at=_T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    return revision, work_unit


def test_verify_then_file_co_emits_participation_for_every_source_transaction(tmp_path: Path) -> None:
    """Verify then file a revision; the participation index records both transactions."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        cr_repo = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
        wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID)
        fr_repo = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID)
        bv_repo = _bucket_event_repository()
        participation_repo = TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID)

        revision, work_unit = _seed_borrador(cr_repo=cr_repo, wu_repo=wu_repo)

        # --- VERIFY (co-emits VERIFICADO_COMPLETO participations) ---
        verified_at = _T0 + timedelta(hours=3)
        revisions, revisions_revision_id = cr_repo.load_revisioned()
        _persist_verified_revision_evidence(
            target=revision,
            actor="aeat.cli.modelo.verify",
            now=verified_at,
            revisions=revisions,
            revisions_revision_id=revisions_revision_id,
            work_unit=work_unit,
            transaction_repository=None,
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
            participation_index_repository=participation_repo,
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
    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository

    return BucketEventHistoryRepository()
