"""Repository-backed ledger modelo-readiness preflight tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import TransactionCatalogue
from ....tests.secure_sql import isolated_runtime_profile
from ..preflight import preflight_ledger_tax_readiness
from ._preflight_test_support import (
    _BUCKET_ID,
    _OTHER_BUCKET_ID,
    _Q2_2026,
    _transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_preflight_repository_path_loads_bucket_catalogue(secure_objects: SecureObjectRepository) -> None:
    objects = secure_objects
    repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
    repository.save(TransactionCatalogue.from_transactions((_transaction("row-ready"),)))

    report = preflight_ledger_tax_readiness(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
    )

    assert report.ready is True
    assert report.checked_transaction_count == 1
    assert report.issues == ()


def test_preflight_default_repository_loads_active_runtime_bucket(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(
            TransactionCatalogue.from_transactions((_transaction("row-ready"),)),
        )

        report = preflight_ledger_tax_readiness(bucket_id=profile.bucket_id, period=_Q2_2026)

    assert report.ready is True
    assert report.checked_transaction_count == 1
    assert report.issues == ()


def test_preflight_rejects_repository_bucket_mismatch(secure_objects: SecureObjectRepository) -> None:
    objects = secure_objects
    with pytest.raises(TransactionValidationError, match="bucket_id"):
        preflight_ledger_tax_readiness(
            bucket_id=_BUCKET_ID,
            period=_Q2_2026,
            transaction_repository=TransactionCatalogueRepository(bucket_id=_OTHER_BUCKET_ID, objects=objects),
        )
