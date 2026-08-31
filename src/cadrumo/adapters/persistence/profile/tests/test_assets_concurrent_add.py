"""Two concurrent asset adds both survive.

The assets ledger is a SINGLETON row, so ``add`` is really read-whole-ledger,
rebuild, write-whole-ledger. Performed unguarded, two callers adding DIFFERENT
assets both read the same ledger and the later write silently discarded the
earlier asset.

That is a lost update, not a duplicate identifier: the two assets never met in
one document, so the duplicate check could not have noticed. The only way to
observe it is to interleave the two halves of the read-modify-write, which is
what this module does -- deterministically, by landing the interloping write
inside the guarded unit of work's read-to-write window, rather than by racing
threads and hoping to hit it.

Real behaviour throughout: a real isolated bucket runtime, the real encrypted
SQL backend, and independent repository instances. Nothing is mocked.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....domain.contribuyente.assets.records import AssetClass, AssetRecord, AssetRecordError, AssetsLedgerDocument
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..assets import AssetsLedgerRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "38403840-3840-4384-8384-384038403840"

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


def _asset(identifier: str, *, cost: str) -> AssetRecord:
    return AssetRecord(
        identifier=identifier,
        description=f"asset {identifier}",
        asset_class=AssetClass.ELECTRONICA_INFORMATICA,
        acquisition_date=date(2026, 1, 15),
        cost_basis=Decimal(cost),
    )


def test_sequential_adds_through_independent_instances_accumulate() -> None:
    """Baseline: nothing about two repository instances loses an asset."""
    AssetsLedgerRepository().add(_asset("asset-1", cost="1000.00"))
    AssetsLedgerRepository().add(_asset("asset-2", cost="2000.00"))

    identifiers = [a.identifier for a in AssetsLedgerRepository().load().assets]
    assert sorted(identifiers) == ["asset-1", "asset-2"]


def test_a_concurrent_add_does_not_discard_the_other_asset() -> None:
    """DISCRIMINATING: the interleaving that used to lose an asset.

    The interloping add lands after this guarded attempt's read and before its
    write, which is exactly the window two concurrent callers race in. Before
    the guard, this attempt's write overwrote the interloper and only one asset
    remained.
    """
    repo = AssetsLedgerRepository()
    interloper_written = False

    def _add_one_while_another_lands(current: AssetsLedgerDocument) -> AssetsLedgerDocument:
        nonlocal interloper_written
        if not interloper_written:
            interloper_written = True
            AssetsLedgerRepository().add(_asset("asset-2", cost="2000.00"))
        return AssetsLedgerDocument(assets=(*current.assets, _asset("asset-1", cost="1000.00")))

    # Reaches through the repository's storage kernel deliberately: the point is
    # to interleave INSIDE one guarded add, which the public method does not
    # expose a seam for.
    repo._storage.mutate(_add_one_while_another_lands)

    identifiers = [a.identifier for a in AssetsLedgerRepository().load().assets]
    assert sorted(identifiers) == ["asset-1", "asset-2"]


def test_a_duplicate_identifier_is_still_refused_and_not_retried() -> None:
    """A refusal is not a conflict, so the guard must not retry it.

    Pins that wrapping ``add`` in a retrying unit of work did not turn its
    duplicate refusal into a loop, or into an eventual success.
    """
    AssetsLedgerRepository().add(_asset("dup", cost="1000.00"))

    with pytest.raises(AssetRecordError):
        AssetsLedgerRepository().add(_asset("dup", cost="2000.00"))

    assert len(AssetsLedgerRepository().load().assets) == 1
