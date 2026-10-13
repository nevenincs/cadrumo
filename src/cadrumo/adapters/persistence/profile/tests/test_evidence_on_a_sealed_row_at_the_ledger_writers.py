"""Evidence on a row a finalized revision cites, and an identifier that names no evidence.

The ledger actions run over real secure storage, with a finalized revision
citing the row. Linking evidence leaves what the revision sealed, whichever
mechanism stamped the row: the row's identity and fingerprint stay as they
were, the attach is admitted, and the cited revisions are reported as stale.
Linking purchase evidence changes how a calculation reads the row and makes it
the linker's; a supplementary attachment does not. An identifier of only
whitespace names no evidence: it links nothing and decides nothing.

A confirmation that carries a reason is a change to the row, so it is refused
on a sealed row, and the refusal names the field and shows no value.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.application.aggregation.ledger_filing_snapshot import (
    compute_ledger_filing_snapshot,
    evaluate_ledger_filing_staleness,
    row_fingerprint,
)
from cadrumo.application.ledger.actions_manual import (
    attach_manual_transaction_evidence,
    update_manual_transaction_fields,
)
from cadrumo.application.ledger.attachment_mutation_operation import LedgerAttachRequest
from cadrumo.application.ledger.models import ManualLedgerTransactionPatch, ManualLedgerTransactionResult
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.modelos.ledger_filing_snapshot import LedgerFilingSnapshot
from cadrumo.domain.transactions.classification_origin import ClassificationOrigin
from cadrumo.domain.transactions.enums import BusinessClassification
from cadrumo.domain.transactions.errors import TransactionValidationError

from .classification_origin_support import (
    AGENT,
    BUCKET_ID,
    PERSON,
    Ledger,
    add_row,
    add_row_classified_by_a_rule,
    composed_ledger,
    store_attachment,
    synthetic_invoice,
)
from .ledger_action_persistence_support import persist_verified_revision_citing_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_BLANK = "   "


@pytest.fixture
def ledger(tmp_path: Path) -> Generator[Ledger]:
    with composed_ledger(tmp_path) as composed:
        yield composed


def _seal(ledger: Ledger, row: str) -> LedgerFilingSnapshot:
    persist_verified_revision_citing_transaction(
        ledger.objects, transaction_id=row, bucket_id=BUCKET_ID, operation=ledger.ports.operation
    )
    snapshot = compute_ledger_filing_snapshot(
        source_transaction_ids=(row,),
        catalogue=ledger.transactions.load(),
        captured_at=datetime(2025, 2, 1, tzinfo=UTC),
    )
    assert evaluate_ledger_filing_staleness(snapshot, ledger.transactions.load()).is_stale is False
    return snapshot


def _attach(
    ledger: Ledger, row: str, *, evidence: str | None = None, attachments: tuple[str, ...] = ()
) -> ManualLedgerTransactionResult:
    return attach_manual_transaction_evidence(
        bucket_id=BUCKET_ID,
        transaction_id=row,
        purchase_invoice_evidence_id=evidence,
        attachment_ids=attachments,
        actor=PERSON,
        ports=ledger.ports,
    )


def _sealed_rule_row(ledger: Ledger) -> str:
    return add_row_classified_by_a_rule(ledger, description="stamped by a rule and cited by a finalized revision")


def _sealed_hand_row(ledger: Ledger) -> str:
    return add_row(
        ledger,
        description="stamped by hand and cited by a finalized revision",
        classification=BusinessClassification.BUSINESS,
    )


_ROWS = pytest.mark.parametrize(
    ("make_row", "origin_after_a_document", "stamp"),
    [
        (_sealed_rule_row, ClassificationOrigin.AUTOMATIC, "rule:synthetic"),
        (_sealed_hand_row, ClassificationOrigin.PERSON, "manual"),
    ],
    ids=["stamped-by-a-rule", "stamped-by-hand"],
)


@_ROWS
def test_a_person_attaching_a_supplementary_document_to_a_sealed_row_moves_nothing_it_sealed(
    ledger: Ledger, make_row: Callable[[Ledger], str], origin_after_a_document: ClassificationOrigin, stamp: str
) -> None:
    row = make_row(ledger)
    assert ledger.row(row).classified_by == stamp
    snapshot = _seal(ledger, row)
    before = ledger.row(row)

    result = _attach(ledger, row, attachments=(store_attachment(ledger, b"supplementary"),))

    after = ledger.row(row)
    assert len(after.attachment_ids) == 1
    assert after.transaction_id == before.transaction_id
    assert row_fingerprint(after) == row_fingerprint(before)
    assert evaluate_ledger_filing_staleness(snapshot, ledger.transactions.load()).is_stale is False
    assert len(result.stale_finalized_revisions) == 1
    assert after.classification_origin is origin_after_a_document


@_ROWS
def test_a_person_linking_purchase_evidence_to_a_sealed_row_takes_it_and_reports_the_revision_stale(
    ledger: Ledger, make_row: Callable[[Ledger], str], origin_after_a_document: ClassificationOrigin, stamp: str
) -> None:
    del origin_after_a_document, stamp
    invoice = synthetic_invoice("SYNTHETIC-1")
    ledger.invoices.save(build_invoice_catalogue([invoice]))
    row = make_row(ledger)
    snapshot = _seal(ledger, row)
    before = ledger.row(row)

    result = _attach(ledger, row, evidence=invoice.invoice_id)

    after = ledger.row(row)
    assert after.purchase_invoice_evidence_id == invoice.invoice_id
    assert after.transaction_id == before.transaction_id
    assert row_fingerprint(after) == row_fingerprint(before)
    assert evaluate_ledger_filing_staleness(snapshot, ledger.transactions.load()).is_stale is False
    assert len(result.stale_finalized_revisions) == 1
    assert after.classification_origin is ClassificationOrigin.PERSON


def test_an_identifier_of_only_whitespace_names_no_evidence_in_the_request() -> None:
    request = LedgerAttachRequest(
        profile_id=_PROFILE, transaction_id="a" * 12, purchase_invoice_evidence_id=_BLANK, attachment_ids=("b" * 64,)
    )
    padded = LedgerAttachRequest(profile_id=_PROFILE, transaction_id="a" * 12, purchase_invoice_evidence_id=" c ")

    assert request.purchase_invoice_evidence_id is None
    assert padded.purchase_invoice_evidence_id == "c"


@pytest.mark.parametrize("blank", ["", _BLANK])
def test_a_blank_identifier_links_nothing_and_takes_no_row_at_the_writer(ledger: Ledger, blank: str) -> None:
    by_an_agent = add_row(
        ledger, description="classified by an agent", actor=AGENT, classification=BusinessClassification.BUSINESS
    )
    attachment = store_attachment(ledger, b"beside a blank identifier")
    before = ledger.row(by_an_agent)
    assert before.classification_origin is ClassificationOrigin.AGENT

    _attach(ledger, by_an_agent, evidence=blank, attachments=(attachment,))

    after = ledger.row(by_an_agent)
    assert after.purchase_invoice_evidence_id is None
    assert after.attachment_ids == (attachment,)
    assert after.classification_origin is ClassificationOrigin.AGENT


@pytest.mark.parametrize("blank", ["", _BLANK])
def test_a_blank_identifier_alone_is_refused_and_stores_nothing(ledger: Ledger, blank: str) -> None:
    by_an_agent = add_row(
        ledger, description="classified by an agent", actor=AGENT, classification=BusinessClassification.BUSINESS
    )
    before = ledger.stored()

    with pytest.raises(TransactionValidationError):
        _attach(ledger, by_an_agent, evidence=blank)

    assert ledger.stored() == before


def test_a_confirmation_with_a_reason_is_refused_on_a_sealed_row_and_names_the_field_not_the_value(
    ledger: Ledger,
) -> None:
    row = _sealed_hand_row(ledger)
    snapshot = _seal(ledger, row)
    before = ledger.stored()
    reason = "synthetic reason that must not be echoed"

    with pytest.raises(TransactionValidationError) as refused:
        update_manual_transaction_fields(
            bucket_id=BUCKET_ID,
            transaction_id=row,
            patch=ManualLedgerTransactionPatch.model_validate(
                {"business_classification": BusinessClassification.BUSINESS, "notes": reason}
            ),
            actor=PERSON,
            source_command="aeat app ledger classify",
            ports=ledger.ports,
        )

    context = refused.value.context or {}
    assert context["changed_fields"] == "notes"
    assert "calculation_revision_id" in context
    assert reason not in str(refused.value)
    assert reason not in context.values()
    assert ledger.stored() == before
    assert evaluate_ledger_filing_staleness(snapshot, ledger.transactions.load()).is_stale is False
