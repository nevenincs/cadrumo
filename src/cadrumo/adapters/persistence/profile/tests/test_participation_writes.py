"""The one participation builder writes exactly the bytes each lifecycle stage owes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile import participation_index as participation_adapter
from cadrumo.adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.participation_writes import build_participation_writes
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.participation_index import TransactionRevisionParticipation
from cadrumo.domain.modelos.work_unit import WorkUnit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "0f4f3a52-9a3b-4f6e-8d0e-6a1b7c2d9e11"
_EXERCISE = filing_year_envelope().horizon
_T0 = datetime(1980, 7, 1, 9, 0, 0, tzinfo=UTC)
_TX_A = "a" * 64
_TX_B = "b" * 64
_REVISION_ID = "c" * 64
_WORK_UNIT_ID = "d" * 64
_FILING_ID = "e" * 64
_PERIOD = Period.from_year_and_code(_EXERCISE, "2T")


def _work_unit() -> WorkUnit:
    return WorkUnit.model_construct(
        work_unit_id=_WORK_UNIT_ID,
        modelo=ModeloCode("303"),
        filing_year=_EXERCISE,
        period=_PERIOD,
    )


def _revision(source_transaction_ids: tuple[str, ...]) -> CalculationRevision:
    return CalculationRevision.model_construct(
        calculation_revision_id=_REVISION_ID,
        source_transaction_ids=source_transaction_ids,
    )


def _expected(state: str, filing_record_id: str | None) -> TransactionRevisionParticipation:
    return TransactionRevisionParticipation(
        calculation_revision_id=_REVISION_ID,
        work_unit_id=_WORK_UNIT_ID,
        modelo=ModeloCode("303"),
        filing_year=_EXERCISE,
        period=_PERIOD,
        revision_state=state,
        filing_record_id=filing_record_id,
    )


@pytest.mark.parametrize(
    ("state", "filing_record_id", "stored_state"),
    [
        (CalculationRevisionState.VERIFICADO_COMPLETO, None, "verificado_completo"),
        (CalculationRevisionState.PRESENTADO, _FILING_ID, "presentado"),
    ],
)
def test_each_stage_writes_the_bytes_of_its_own_hand_built_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: CalculationRevisionState,
    filing_record_id: str | None,
    stored_state: str,
) -> None:
    monkeypatch.setattr(participation_adapter, "now", lambda: _T0)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        repository = TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID)

        writes = build_participation_writes(
            revision=_revision((_TX_A, _TX_B)),
            work_unit=_work_unit(),
            revision_state=state,
            filing_record_id=filing_record_id,
            participation_index_repository=repository,
        )

        expected = tuple(
            repository.to_secure_object_write(
                repository.load(transaction_id).model_copy(
                    update={"participations": (_expected(stored_state, filing_record_id),)}
                )
            )
            for transaction_id in (_TX_A, _TX_B)
        )
        assert [write.payload for write in writes] == [write.payload for write in expected]
        assert writes == expected


def test_a_filed_write_replaces_the_verified_entry_it_succeeds(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        repository = TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID)
        verified = build_participation_writes(
            revision=_revision((_TX_A,)),
            work_unit=_work_unit(),
            revision_state=CalculationRevisionState.VERIFICADO_COMPLETO,
            participation_index_repository=repository,
        )
        assert len(verified) == 1
        repository.save(
            repository.load(_TX_A).model_copy(update={"participations": (_expected("verificado_completo", None),)})
        )

        filed = build_participation_writes(
            revision=_revision((_TX_A,)),
            work_unit=_work_unit(),
            revision_state=CalculationRevisionState.PRESENTADO,
            filing_record_id=_FILING_ID,
            participation_index_repository=repository,
        )

        assert len(filed) == 1
        assert filed[0].payload.count(b'"calculation_revision_id"') == 1
        assert b'"revision_state":"presentado"' in filed[0].payload
        assert _FILING_ID.encode() in filed[0].payload


def test_a_revision_without_contributing_transactions_writes_nothing(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        repository = TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID)

        assert (
            build_participation_writes(
                revision=_revision(()),
                work_unit=_work_unit(),
                revision_state=CalculationRevisionState.VERIFICADO_COMPLETO,
                participation_index_repository=repository,
            )
            == ()
        )
