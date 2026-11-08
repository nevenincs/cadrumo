"""Repository-backed ledger modelo-readiness preflight tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.profile.usage_ratios import load_usage_ratios
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger.preflight import preflight_ledger_tax_readiness
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.transactions.errors import TransactionValidationError
from cadrumo.domain.transactions.models import TransactionCatalogue

from .preflight_transaction_support import preflight_transaction

_BUCKET_ID = "22222222-2222-4222-8222-222222222222"
_OTHER_BUCKET_ID = "23232323-2323-4323-8323-232323232323"
_Q2_2026 = Period.from_year_and_code(2026, "2T")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_preflight_repository_path_loads_bucket_catalogue(secure_objects: SecureObjectRepository) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        objects = secure_objects
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        repository.save(TransactionCatalogue.from_transactions((preflight_transaction("row-ready"),)))

        report = preflight_ledger_tax_readiness(
            bucket_id=_BUCKET_ID,
            period=_Q2_2026,
            usage_ratio_profile_loader=load_usage_ratios,
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
            invoice_reader=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
            operation=_authority_operation_for_test,
        )

        assert report.ready is True
        assert report.checked_transaction_count == 1
        assert report.issues == ()


def test_preflight_default_repository_loads_active_runtime_bucket(tmp_path: Path) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(
                TransactionCatalogue.from_transactions((preflight_transaction("row-ready"),)),
            )

            report = preflight_ledger_tax_readiness(
                bucket_id=profile.bucket_id,
                period=_Q2_2026,
                usage_ratio_profile_loader=load_usage_ratios,
                invoice_reader=InvoiceCatalogueRepository(bucket_id=profile.bucket_id),
                operation=_authority_operation_for_test,
            )

        assert report.ready is True
        assert report.checked_transaction_count == 1
        assert report.issues == ()


def test_preflight_rejects_repository_bucket_mismatch(secure_objects: SecureObjectRepository) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        objects = secure_objects
        with pytest.raises(TransactionValidationError, match="bucket_id"):
            preflight_ledger_tax_readiness(
                bucket_id=_BUCKET_ID,
                period=_Q2_2026,
                usage_ratio_profile_loader=load_usage_ratios,
                transaction_repository=TransactionCatalogueRepository(bucket_id=_OTHER_BUCKET_ID, objects=objects),
                invoice_reader=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
                operation=_authority_operation_for_test,
            )
