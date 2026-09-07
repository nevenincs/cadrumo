"""Recapturing a sealed revision's evidence after the operator attaches it.

The filing gates read the frozen evidence bundle, not the ledger, so evidence
attached after a revision is sealed has until now been unreachable: the bundle
is never recomputed, a sealed revision cannot be re-verified, and recalculating
returns the same content-addressed revision because attaching a document
changes no tax fact. That dead end is the stated reason the sibling filing gate
was left deliberately fail-open on several axes, so the way out has to exist
and be proven before the gate can be tightened onto it.

These tests hold the two halves apart: the recapture must close a real gap
without moving the revision's identity, and it must refuse outright when the
tax facts themselves have moved, because that is staleness and its remedy is a
fresh calculation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....domain.buckets.event import BucketEventType
from ....domain.transactions.models import TransactionCatalogue
from .._ledger_evidence_gate import deductible_iva_evidence_gap_transaction_ids
from ..action_errors import CalculationRevisionStateError, LedgerEvidenceRecaptureRefusedError
from ..verification_actions import recapture_ledger_filing_evidence
from .test_modelo_303_deductible_evidence_gate import (
    _BUCKET_ID,
    _calculate_irene_revision,
    _persist_legacy_verified_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RECAPTURED_AT = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)


def test_recapture_closes_the_evidence_gap_without_moving_the_revision_identity(
    secure_objects: SecureObjectRepository,
) -> None:
    """The dead end opens: the gate stops refusing and the id is untouched."""
    revision, sale, purchase, wu_repo, cr_repo, _filing, _vr, event_repo, tx_repo = _calculate_irene_revision(
        secure_objects,
    )
    sealed = _persist_legacy_verified_revision(revision, cr_repo=cr_repo, tx_repo=tx_repo)
    blocked = deductible_iva_evidence_gap_transaction_ids(sealed)
    assert purchase.transaction_id in blocked, "the fixture must start from a real refusal"

    # The operator answers the refusal the only way the product offers: they
    # attach the document to the ledger row. No tax fact changes.
    tx_repo.save(
        TransactionCatalogue.from_transactions(
            (sale, purchase.model_copy(update={"attachment_ids": ("purchase-invoice-scan",)})),
        ),
    )

    result = recapture_ledger_filing_evidence(
        sealed.calculation_revision_id,
        actor="operator",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        bucket_event_repository=event_repo,
        clock=_RECAPTURED_AT,
    )

    assert result.newly_evidenced_transaction_ids == (purchase.transaction_id,)
    assert result.recaptured_at == _RECAPTURED_AT
    # The identity claim, asserted by lookup rather than by comparing a field:
    # the revision is still addressable under the id it was sealed with.
    refreshed = cr_repo.load().get(sealed.calculation_revision_id)
    assert refreshed is not None
    assert refreshed.updated_at == _RECAPTURED_AT
    assert refreshed.ledger_filing_snapshot == sealed.ledger_filing_snapshot
    assert deductible_iva_evidence_gap_transaction_ids(refreshed) == ()


def test_recapture_leaves_a_bucket_event_because_the_old_bundle_is_not_retained(
    secure_objects: SecureObjectRepository,
) -> None:
    """Replacing a sealed bundle must extend the audit trail, not edit it."""
    revision, sale, purchase, wu_repo, cr_repo, _filing, _vr, event_repo, tx_repo = _calculate_irene_revision(
        secure_objects,
    )
    sealed = _persist_legacy_verified_revision(revision, cr_repo=cr_repo, tx_repo=tx_repo)
    tx_repo.save(
        TransactionCatalogue.from_transactions(
            (sale, purchase.model_copy(update={"attachment_ids": ("purchase-invoice-scan",)})),
        ),
    )

    recapture_ledger_filing_evidence(
        sealed.calculation_revision_id,
        actor="auditor",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        bucket_event_repository=event_repo,
        clock=_RECAPTURED_AT,
    )

    recorded = [
        event
        for event in event_repo.load().for_bucket(_BUCKET_ID)
        if event.event_type is BucketEventType.MODELO_LEDGER_EVIDENCE_RECAPTURED
    ]
    assert len(recorded) == 1
    assert recorded[0].actor == "auditor"
    assert recorded[0].object_id == sealed.calculation_revision_id
    assert recorded[0].payload["newly_evidenced_count"] == "1"


def test_recapture_refuses_when_a_contributing_row_changed_a_tax_fact(
    secure_objects: SecureObjectRepository,
) -> None:
    """A moved fingerprint is staleness; re-bundling would hide it."""
    revision, sale, purchase, wu_repo, cr_repo, _filing, _vr, event_repo, tx_repo = _calculate_irene_revision(
        secure_objects,
    )
    sealed = _persist_legacy_verified_revision(revision, cr_repo=cr_repo, tx_repo=tx_repo)
    # Not an attachment this time: the deducted cuota itself moves. Base and
    # cuota are restated against the SAME gross, because the catalogue enforces
    # `base + cuota + recargo == gross` to the cent and derives the transaction
    # id from `raw` -- so a drift that keeps the bank line intact and re-splits
    # it is both the valid edit and the realistic one.
    restated = purchase.model_copy(
        update={"taxable_base": Decimal("210.00"), "iva_amount": Decimal("32.00")},
    )
    tx_repo.save(TransactionCatalogue.from_transactions((sale, restated)))

    with pytest.raises(LedgerEvidenceRecaptureRefusedError):
        recapture_ledger_filing_evidence(
            sealed.calculation_revision_id,
            actor="operator",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            transaction_repository=tx_repo,
            bucket_event_repository=event_repo,
            clock=_RECAPTURED_AT,
        )

    untouched = cr_repo.load().get(sealed.calculation_revision_id)
    assert untouched is not None
    assert untouched.ledger_filing_evidence == sealed.ledger_filing_evidence


def test_recapture_refuses_a_draft_because_only_a_sealed_bundle_is_frozen(
    secure_objects: SecureObjectRepository,
) -> None:
    """A draft has no frozen bundle to rescue; recalculating is the path."""
    revision, _sale, _purchase, wu_repo, cr_repo, _filing, _vr, event_repo, tx_repo = _calculate_irene_revision(
        secure_objects,
    )

    with pytest.raises(CalculationRevisionStateError):
        recapture_ledger_filing_evidence(
            revision.calculation_revision_id,
            actor="operator",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            transaction_repository=tx_repo,
            bucket_event_repository=event_repo,
            clock=_RECAPTURED_AT,
        )
