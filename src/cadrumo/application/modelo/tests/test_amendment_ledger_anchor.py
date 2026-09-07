"""An amendment anchors to the ledger as it stands when the amendment is filed.

Verify anchors a revision to the ledger it was computed from, and an amendment
stands in for verify without ever calling it. So an amended return carried no
anchor at all -- and ``stale_filed_revisions`` skips a revision whose snapshot
is ``None``, which meant an amended filing could never be reported stale no
matter what its books did afterwards.

The capture has to be FRESH rather than inherited. An amendment is filed now,
against the ledger as it stands now; copying the baseline's anchor would assert
that those older facts were the ones checked, backdating the claim by exactly
the interval the amendment exists to correct.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....application.aggregation.ledger_filing_snapshot import row_fingerprint
from ....domain.transactions.models import TransactionCatalogue
from ..amendment_actions import _amendment_ledger_anchor
from .test_modelo_303_deductible_evidence_gate import _BUCKET_ID, _calculate_irene_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# The `secure_objects` fixture reads this from the requesting module, so it is
# a fixture requirement rather than a convenience alias.
_BUCKET_ID = _BUCKET_ID
_AMENDED_AT = datetime(2026, 6, 11, 9, 0, tzinfo=UTC)


def test_a_revision_with_no_contributors_anchors_to_nothing_and_says_so(
    secure_objects: SecureObjectRepository,
) -> None:
    """``None`` rather than an empty snapshot, which would read as a checked ledger."""
    revision, _sale, _purchase, wu_repo, _cr, _filing, _vr, _events, tx_repo = _calculate_irene_revision(secure_objects)
    work_unit = wu_repo.load().get(revision.work_unit_id)
    assert work_unit is not None

    snapshot, evidence = _amendment_ledger_anchor(
        amendment_draft=revision.model_copy(update={"source_transaction_ids": ()}),
        work_unit=work_unit,
        transaction_repository=tx_repo,
        now=_AMENDED_AT,
    )

    assert snapshot is None
    assert evidence is None


def test_the_anchor_describes_the_ledger_at_amend_time_not_at_baseline_time(
    secure_objects: SecureObjectRepository,
) -> None:
    """The freshness claim, asserted against a row that moved after the baseline.

    The contributing purchase is restated after the baseline revision exists.
    If the anchor were inherited or recomputed against the older facts, its
    row fingerprint would match the ORIGINAL row; a fresh capture matches the
    restated one.
    """
    revision, sale, purchase, wu_repo, _cr, _filing, _vr, _events, tx_repo = _calculate_irene_revision(secure_objects)
    work_unit = wu_repo.load().get(revision.work_unit_id)
    assert work_unit is not None
    assert revision.source_transaction_ids, "the fixture must contribute rows for this to mean anything"

    # Base and cuota restated against the SAME gross, because the catalogue
    # enforces the identity and derives the transaction id from `raw`.
    restated = purchase.model_copy(
        update={"taxable_base": Decimal("210.00"), "iva_amount": Decimal("32.00")},
    )
    tx_repo.save(TransactionCatalogue.from_transactions((sale, restated)))

    snapshot, evidence = _amendment_ledger_anchor(
        amendment_draft=revision,
        work_unit=work_unit,
        transaction_repository=tx_repo,
        now=_AMENDED_AT,
    )

    assert snapshot is not None
    assert evidence is not None
    assert snapshot.captured_at == _AMENDED_AT
    fingerprints = {row.transaction_id: row.fingerprint for row in snapshot.rows}
    assert fingerprints[purchase.transaction_id] == row_fingerprint(restated)
    assert fingerprints[purchase.transaction_id] != row_fingerprint(purchase)


def test_the_anchor_bundles_evidence_covering_every_fingerprinted_contributor(
    secure_objects: SecureObjectRepository,
) -> None:
    """Snapshot and evidence must describe the same rows or neither explains the filing."""
    revision, _sale, _purchase, wu_repo, _cr, _filing, _vr, _events, tx_repo = _calculate_irene_revision(secure_objects)
    work_unit = wu_repo.load().get(revision.work_unit_id)
    assert work_unit is not None

    snapshot, evidence = _amendment_ledger_anchor(
        amendment_draft=revision,
        work_unit=work_unit,
        transaction_repository=tx_repo,
        now=_AMENDED_AT,
    )

    assert snapshot is not None
    assert evidence is not None
    assert evidence.snapshot_fingerprint == snapshot.snapshot_fingerprint
    assert {row.transaction_id for row in evidence.rows} == {row.transaction_id for row in snapshot.rows}
