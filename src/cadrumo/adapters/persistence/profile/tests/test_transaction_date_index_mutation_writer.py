"""Derived routing writes use actual admission and never confirm convergence as a write."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete

from .....domain.transactions.models import TransactionCatalogue
from ...storage.errors import SecureObjectRevisionConflictError
from ...storage.sql.orm import TransactionDateIndexRow
from ...storage.sql.secure_objects import SecureObjectRepository
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..transactions import TransactionCatalogueRepository
from .test_transaction_date_index import _transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter, pytest.mark.usefixtures("authority_operation")]
_BUCKET = "44444444-4444-4444-8444-444444444444"


def _catalogue() -> TransactionCatalogue:
    row = _transaction(
        provider_id="admitted-index",
        filing_date=date(2026, 2, 10),
        amount=Decimal("12.00"),
        description="synthetic routing fixture",
    )
    return TransactionCatalogue.from_transactions((row,))


def test_lazy_index_rebuild_is_admitted_once_and_unchanged_sync_is_a_noop(tmp_path: Path) -> None:
    admissions = 0

    def admitted(write: Callable[[], None]) -> None:
        nonlocal admissions
        write()
        admissions += 1

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        ordinary = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=profile.repository)
        catalogue = _catalogue()
        ordinary.save(catalogue)
        with profile.repository.guarded_session_scope() as session:
            session.execute(delete(TransactionDateIndexRow).where(TransactionDateIndexRow.bucket_id == _BUCKET))
        objects = SecureObjectRepository(
            engine=profile.repository.engine,
            namespace_registry=profile.repository.namespace_registry,
            active_session_bucket_id=_BUCKET,
            require_secure_active_session=True,
            mutation_writer=admitted,
        )
        tracked = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=objects)
        partition = tracked.partition_by_date_range(date(2026, 1, 1), date(2026, 3, 31))
        assert partition.in_window == catalogue
        assert not partition.index_complete and admissions == 0
        tracked._sync_date_index(catalogue)
        assert admissions == 1
        assert tracked.partition_by_date_range(date(2026, 1, 1), date(2026, 3, 31)).index_complete
        tracked._sync_date_index(catalogue)
        assert admissions == 1, "equal prepared maps must return without entering writer admission"


def test_concurrent_convergence_rejects_prepared_baseline_then_reloads_without_another_admission(
    tmp_path: Path,
) -> None:
    admissions = 0
    confirmed = 0
    conflicts: list[SecureObjectRevisionConflictError] = []
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        ordinary = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=profile.repository)
        catalogue = _catalogue()
        ordinary.save(catalogue)
        with profile.repository.guarded_session_scope() as session:
            session.execute(delete(TransactionDateIndexRow).where(TransactionDateIndexRow.bucket_id == _BUCKET))

        def admitted(write: Callable[[], None]) -> None:
            nonlocal admissions, confirmed
            admissions += 1
            ordinary._sync_date_index(catalogue)
            try:
                write()
            except SecureObjectRevisionConflictError as conflict:
                conflicts.append(conflict)
                raise
            confirmed += 1

        objects = SecureObjectRepository(
            engine=profile.repository.engine,
            namespace_registry=profile.repository.namespace_registry,
            active_session_bucket_id=_BUCKET,
            require_secure_active_session=True,
            mutation_writer=admitted,
        )
        tracked = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=objects)
        tracked._sync_date_index(catalogue)
        assert tracked.load_for_date_range(date(2026, 1, 1), date(2026, 3, 31)) == catalogue
    assert admissions == len(conflicts) == 1 and confirmed == 0
