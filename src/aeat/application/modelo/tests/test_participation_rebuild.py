"""Rebuild the participation index from a real finalized-revision catalogue.

Seeds a calculation-revision catalogue with finalized revisions (verified and
filed) plus a borrador, persisted through the real encrypted repositories, runs
``rebuild_participation_index``, and asserts every finalized revision's
``source_transaction_ids`` land in the rebuilt index while the borrador is
excluded and filed revisions carry their ``filing_record_id``. No mocks — the
rebuild reads the same encrypted catalogues the production write path persists.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ....core import Period
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._filing_record import ModeloRecord, ModeloRecordStatus, derive_filing_record_id
from ....domain.modelos._filing_repository import ModeloRecordCatalogueRepository, upsert_filing_record
from ....domain.modelos._participation_index import TransactionParticipationIndexRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....tests.secure_sql import isolated_runtime_profile
from .._participation_index_rebuild import rebuild_participation_index

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "modelo-participation-rebuild"
_T0 = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)

_TX_FILED = "1" * 64
_TX_VERIFIED = "2" * 64
_TX_BORRADOR = "3" * 64
_TX_SHARED = "4" * 64  # touched by both the filed and the verified revision


def _hex(seed: str) -> str:
    return (seed * 64)[:64]


def _work_unit(*, modelo: str, period: str, revision_seed: str) -> WorkUnit:
    typed_period = Period.from_year_and_code(2024, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=2024,
        period=typed_period,
        revision_id=revision_seed,
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=2024,
        period=typed_period,
        revision_id=revision_seed,
        name=f"{modelo}-2024-{period}",
        created_at=_T0,
        updated_at=_T0,
    )


def _revision(*, work_unit: WorkUnit, state: CalculationRevisionState, txids: tuple[str, ...]) -> CalculationRevision:
    inputs = {"iva.base-imponible": "1000.00"}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        inputs_snapshot=inputs,
        binding_overrides={},
        casilla_values={},
        source_transaction_ids=txids,
    )
    extra: dict[str, datetime | str] = {}  # only datetime / actor-label keys; **splat below is scaffolding
    if state in {CalculationRevisionState.VERIFICADO_COMPLETO, CalculationRevisionState.PRESENTADO}:
        extra["verified_at"] = _T0 + timedelta(hours=1)
        extra["verified_by"] = "aeat.cli.modelo.verify"
    if state is CalculationRevisionState.PRESENTADO:
        extra["filed_at"] = _T0 + timedelta(hours=2)
        extra["filed_by"] = "aeat.cli.modelo.file"
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=state,
        inputs_snapshot=inputs,
        source_transaction_ids=txids,
        created_at=_T0,
        updated_at=_T0 + timedelta(hours=2),
        **extra,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]  # test scaffolding: conditional datetime/actor-label **dict splat
    )


def test_rebuild_includes_finalized_excludes_borrador_and_carries_filing_record(tmp_path: Path) -> None:
    """Rebuild folds every finalized revision in, drops borrador, carries filing_record_id."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        cr_repo = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
        wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID)
        fr_repo = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID)

        filed_wu = _work_unit(modelo="303", period="1T", revision_seed="303")
        verified_wu = _work_unit(modelo="130", period="2T", revision_seed="130")
        borrador_wu = _work_unit(modelo="303", period="3T", revision_seed="303b")

        filed_rev = _revision(
            work_unit=filed_wu,
            state=CalculationRevisionState.PRESENTADO,
            txids=(_TX_FILED, _TX_SHARED),
        )
        verified_rev = _revision(
            work_unit=verified_wu,
            state=CalculationRevisionState.VERIFICADO_COMPLETO,
            txids=(_TX_VERIFIED, _TX_SHARED),
        )
        borrador_rev = _revision(
            work_unit=borrador_wu,
            state=CalculationRevisionState.BORRADOR,
            txids=(_TX_BORRADOR,),
        )

        work_units = wu_repo.load()
        for wu in (filed_wu, verified_wu, borrador_wu):
            work_units = upsert_work_unit(work_units, wu)
        wu_repo.save(work_units)

        revisions = cr_repo.load()
        for rev in (filed_rev, verified_rev, borrador_rev):
            revisions = upsert_calculation_revision(revisions, rev)
        cr_repo.save(revisions)

        # A filing record bound to the filed revision so rebuild can attach filing_record_id.
        filing_id = derive_filing_record_id(
            work_unit_id=filed_wu.work_unit_id,
            calculation_revision_id=filed_rev.calculation_revision_id,
            filed_at=_T0 + timedelta(hours=2),
            filed_by="aeat.cli.modelo.file",
        )
        filing_record = ModeloRecord(
            filing_record_id=filing_id,
            work_unit_id=filed_wu.work_unit_id,
            calculation_revision_id=filed_rev.calculation_revision_id,
            bucket_id=_BUCKET_ID,
            modelo=ModeloCode("303"),
            filing_year=2024,
            period=Period.from_year_and_code(2024, "1T"),
            filed_at=_T0 + timedelta(hours=2),
            filed_by="aeat.cli.modelo.file",
            status=ModeloRecordStatus.VIGENTE,
        )
        fr_repo.save(upsert_filing_record(fr_repo.load(), filing_record))

        stats = rebuild_participation_index(bucket_id=_BUCKET_ID)

        participation_repo = TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID)
        index_filed = participation_repo.load(_TX_FILED)
        index_verified = participation_repo.load(_TX_VERIFIED)
        index_borrador = participation_repo.load(_TX_BORRADOR)
        index_shared = participation_repo.load(_TX_SHARED)

    # Two finalized revisions folded in (borrador excluded).
    assert stats.revision_count == 2
    # Four transaction objects gained at least one entry: filed, verified, shared (borrador excluded).
    assert stats.transaction_count == 3
    # filed(2 tx) + verified(2 tx) = 4 participation entries.
    assert stats.participation_count == 4

    # Borrador transaction has no entry.
    assert index_borrador.participations == ()

    # Filed revision entry carries filing_record_id.
    (filed_entry,) = index_filed.participations
    assert filed_entry.revision_state == "presentado"
    assert filed_entry.filing_record_id == filing_id

    # Verified revision entry has no filing_record_id.
    (verified_entry,) = index_verified.participations
    assert verified_entry.revision_state == "verificado_completo"
    assert verified_entry.filing_record_id is None

    # Shared transaction carries BOTH revisions' participations.
    shared_revisions = {p.calculation_revision_id for p in index_shared.participations}
    assert shared_revisions == {filed_rev.calculation_revision_id, verified_rev.calculation_revision_id}


def test_rebuild_on_empty_catalogue_writes_nothing(tmp_path: Path) -> None:
    """An empty revision catalogue rebuilds to zero participations."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        stats = rebuild_participation_index(bucket_id=_BUCKET_ID)

    assert stats.revision_count == 0
    assert stats.transaction_count == 0
    assert stats.participation_count == 0
