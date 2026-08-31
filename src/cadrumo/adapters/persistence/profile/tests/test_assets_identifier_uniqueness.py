"""One asset identifier, one asset -- on every write path into the ledger.

``AssetsLedgerRepository.add`` refused a repeated ``AssetRecord.identifier``,
but the public ``save`` / ``save_assets`` path accepted any
``AssetsLedgerDocument`` and wrote it straight through. The same repository
therefore held two competing uniqueness contracts: incremental writes rejected
a duplicate natural key while bulk replacement persisted two rows under one,
leaving later lookup and amortisation consumers -- which reference an asset BY
identifier -- without a canonical asset.

The invariant now lives on the document, so it holds for insert, for bulk
replacement, and at the read boundary alike.

Real behaviour throughout: a real isolated bucket runtime and the real
encrypted secure-object backend. Nothing is mocked.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....domain.contribuyente.assets.records import AssetClass, AssetRecord, AssetRecordError, AssetsLedgerDocument
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..assets import AssetsLedgerRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "50505050-5050-4050-8050-505050505050"
_DUPLICATE_ID = "dup"

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


def _asset(identifier: str, *, description: str, cost: str) -> AssetRecord:
    return AssetRecord(
        identifier=identifier,
        description=description,
        asset_class=AssetClass.ELECTRONICA_INFORMATICA,
        acquisition_date=date(2026, 1, 15),
        cost_basis=Decimal(cost),
    )


def test_duplicate_identifiers_are_refused_by_the_document() -> None:
    """The invariant is on the document, so no write path can bypass it.

    DISCRIMINATING: this construction used to succeed, and it is the exact
    value ``save`` received. Asserting at the document rather than only through
    the repository is what pins that the rule cannot be reintroduced on one
    write path and not the other.
    """
    with pytest.raises(ValidationError) as excinfo:
        AssetsLedgerDocument(
            assets=(
                _asset(_DUPLICATE_ID, description="first", cost="1000.00"),
                _asset(_DUPLICATE_ID, description="second", cost="2000.00"),
            ),
        )

    # Names the offending identifier, so the refusal is attributable to the
    # duplicate rather than to any other validation failure on the document.
    assert _DUPLICATE_ID in str(excinfo.value)


def test_bulk_save_cannot_persist_two_assets_under_one_identifier() -> None:
    """The public bulk persistence boundary revalidates a pre-built document.

    ``model_construct`` is Pydantic's documented no-validation constructor;
    callers receiving an already-constructed document can therefore not rely
    on its construction boundary having run.  This uses the real document and
    encrypted repository to prove ``save`` itself restores the identifier
    invariant before any ciphertext is written.
    """
    repo = AssetsLedgerRepository()
    duplicate_document = AssetsLedgerDocument.model_construct(
        assets=(
            _asset(_DUPLICATE_ID, description="first", cost="1000.00"),
            _asset(_DUPLICATE_ID, description="second", cost="2000.00"),
        ),
    )

    with pytest.raises(ValidationError):
        repo.save(duplicate_document)

    assert AssetsLedgerRepository().load().assets == ()


def test_incremental_add_still_refuses_a_repeated_identifier() -> None:
    """``add`` keeps its own operator-facing typed refusal.

    The document invariant is the structural backstop; ``add`` stays the layer
    that names the offending asset in the operator's own error, so tightening
    the document did not silently downgrade that diagnostic.
    """
    repo = AssetsLedgerRepository()
    repo.add(_asset(_DUPLICATE_ID, description="first", cost="1000.00"))

    with pytest.raises(AssetRecordError):
        repo.add(_asset(_DUPLICATE_ID, description="second", cost="2000.00"))


def test_distinct_identifiers_still_round_trip_through_bulk_save() -> None:
    """POSITIVE CONTROL: a legitimate multi-asset ledger still saves and loads.

    Without this, the refusals above are equally satisfied by a document that
    rejects every multi-row ledger, which would make the asset ledger useless.
    """
    repo = AssetsLedgerRepository()
    document = AssetsLedgerDocument(
        assets=(
            _asset("asset-1", description="first", cost="1000.00"),
            _asset("asset-2", description="second", cost="2000.00"),
        ),
    )
    repo.save(document)

    loaded = AssetsLedgerRepository().load()
    assert [asset.identifier for asset in loaded.assets] == ["asset-1", "asset-2"]
    assert loaded == document
