"""The savings link fields persist through the encrypted transaction store and load back unchanged."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.transactions.models import TransactionCatalogue
from .....domain.transactions.tests.savings_link_rows import savings_row
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..transactions import TransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "18181818-1818-4181-8181-181818181818"


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def test_savings_links_round_trip_through_the_store(tmp_path: Path) -> None:
    rows = (
        savings_row(provider_id="interest", posicion_ref="deposito-1", concepto_capital_mobiliario="intereses"),
        savings_row(provider_id="dividend", posicion_ref="valores-1", concepto_capital_mobiliario="dividendos"),
        savings_row(provider_id="plain"),
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id, objects=profile.repository)
        repository.save(TransactionCatalogue.from_transactions(rows))

        authenticated = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository).load()
        full = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository).load_fully_validated()

    for loaded in (authenticated, full):
        by_id = {row.transaction_id: row for row in loaded.transactions.values()}
        for saved in rows:
            restored = by_id[saved.transaction_id]
            assert restored == saved
            assert restored.posicion_ref == saved.posicion_ref
            assert restored.concepto_capital_mobiliario == saved.concepto_capital_mobiliario
    linked = next(row for row in full.transactions.values() if row.raw.provider_transaction_id == "dividend")
    assert str(linked.concepto_capital_mobiliario) == "dividendos"
