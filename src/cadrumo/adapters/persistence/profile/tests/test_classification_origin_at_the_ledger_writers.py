"""Every ledger writer records whose decision a classification is, and refuses an agent the person's.

The ledger actions run over real secure storage. A write recorded under an
agent's session label is an agent's, because an agent's execution can record no
other label. Each action that sets or changes a classification, its share or a
tax figure records who decided it; an action that changes none of them leaves
the recorded origin as it found it, whatever stamp it leaves. Each action that
would replace, split or exclude what the person gave a row refuses a write
recorded under an agent's label, and stores nothing.

These refusals are the writers' own. The executors refuse first, before they
declare an effect, and are covered where the real runtime is.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger.action_ports import LedgerActionPorts
from cadrumo.application.ledger.actions_lifecycle import mark_transaction_reviewed_excluded
from cadrumo.application.ledger.actions_manual import (
    attach_manual_transaction_evidence,
    create_manual_transaction,
    detach_manual_transaction_attachments,
    link_manual_transaction_invoice,
    update_manual_transaction_fields,
)
from cadrumo.application.ledger.actions_split_merge import split_transaction, split_transaction_with_classified_children
from cadrumo.application.ledger.llm_classification import apply_llm_classification, derive_operator_iva_substrate
from cadrumo.application.ledger.llm_classification_ports import LLMClassificationSuggestion
from cadrumo.application.ledger.models import (
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    SplitChildCommand,
)
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.domain.attachments.enums import AttachmentKind, AttachmentSource
from cadrumo.domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus
from cadrumo.domain.invoices.models import Invoice, InvoiceLine
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.transactions.classification_origin import ClassificationOrigin
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import Transaction

from .ledger_action_create_support import ledger_ports_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "43434343-4343-4343-8343-434343434343"
_PERSON = "synthetic-person"
_AGENT = f"agent:mcp.attended.{UUID('5aa00000-0000-4000-8000-0000000000dd')}"
_NOW_DATE = date(2025, 1, 21)
_PDF_BYTES = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\norigin-at-the-writers\n%%EOF\n"
_BUSINESS = BusinessClassification.BUSINESS
_PROPOSED_BY = "llm:local-text:synthetic"
_ACTORS = pytest.mark.parametrize(
    ("actor", "origin"),
    [(_PERSON, ClassificationOrigin.PERSON), (_AGENT, ClassificationOrigin.AGENT)],
    ids=["person", "agent"],
)


@dataclass(frozen=True, slots=True)
class _Ledger:
    """One isolated profile's real ledger ports and the repositories a test reads back through."""

    ports: LedgerActionPorts
    transactions: TransactionCatalogueRepository
    events: BucketEventHistoryRepository
    invoices: InvoiceCatalogueRepository
    attachments: AttachmentStore

    def row(self, transaction_id: str) -> Transaction:
        stored = self.transactions.load().get(transaction_id)
        assert stored is not None
        return stored

    def stored(self) -> tuple[dict[str, Transaction], frozenset[str]]:
        """Every stored row and event id: what a refused write must leave exactly as it was."""
        return dict(self.transactions.load().transactions), frozenset(self.events.load().events)


@pytest.fixture
def ledger(tmp_path: Path) -> Generator[_Ledger]:
    with _ledger(tmp_path) as composed:
        yield composed


@contextmanager
def _ledger(tmp_path: Path) -> Generator[_Ledger]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        transactions = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        events = BucketEventHistoryRepository(objects=objects)
        invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        attachments = AttachmentStore(objects=objects)
        with ledger_ports_for_test(
            bucket_id=_BUCKET_ID,
            objects=objects,
            transaction_repository=transactions,
            bucket_event_repository=events,
            invoice_repository=invoices,
            attachment_store=attachments,
        ) as ports:
            yield _Ledger(
                ports=ports, transactions=transactions, events=events, invoices=invoices, attachments=attachments
            )


def _add(
    ledger: _Ledger,
    *,
    description: str,
    actor: str = _PERSON,
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
) -> str:
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=_NOW_DATE,
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description=description,
            business_classification=classification,
            actor=actor,
        ),
        ports=ledger.ports,
    )
    return created.ref.transaction_id


def _classify(
    ledger: _Ledger,
    transaction_id: str,
    *,
    actor: str,
    stamp: str | None = None,
    to: BusinessClassification = _BUSINESS,
) -> None:
    update_manual_transaction_fields(
        bucket_id=_BUCKET_ID,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch(business_classification=to),
        actor=actor,
        source_command="aeat app ledger classify",
        classified_by_override=stamp,
        ports=ledger.ports,
    )


def _by_a_rule(ledger: _Ledger, *, description: str) -> str:
    transaction_id = _add(ledger, description=description)
    _classify(ledger, transaction_id, actor=_PERSON, stamp="rule:synthetic")
    return transaction_id


def _attachment(ledger: _Ledger, marker: bytes) -> str:
    attachment = add_attachment(
        ledger.attachments,
        content=AttachmentBytesContent(data=_PDF_BYTES + marker),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="synthetic-evidence",
            mime_type="application/pdf",
            captured_at=datetime(2025, 1, 21, tzinfo=UTC),
            bucket_id=_BUCKET_ID,
        ),
    )
    return attachment.attachment_id


def _attach(ledger: _Ledger, transaction_id: str, attachment_id: str, *, actor: str) -> None:
    attach_manual_transaction_evidence(
        bucket_id=_BUCKET_ID,
        transaction_id=transaction_id,
        actor=actor,
        attachment_ids=(attachment_id,),
        ports=ledger.ports,
    )


def _derive(ledger: _Ledger, transaction_id: str, *, actor: str, category: str = "domestic_general") -> None:
    derive_operator_iva_substrate(
        bucket_id=_BUCKET_ID,
        transaction_id=transaction_id,
        iva_category=IvaCategory(category),
        actor=actor,
        source_command="aeat app ledger classify --iva-category --saturate",
        ports=ledger.ports,
    )


def _exclude(ledger: _Ledger, transaction_id: str, *, actor: str) -> None:
    mark_transaction_reviewed_excluded(
        bucket_id=_BUCKET_ID,
        transaction_id=transaction_id,
        actor=actor,
        reason="synthetic exclusion",
        transaction_repository=ledger.ports.transaction_repository,
        bucket_event_repository=ledger.ports.bucket_event_repository,
        work_unit_repository=ledger.ports.work_unit_repository,
        calculation_repository=ledger.ports.calculation_repository,
    )


_PARTS = (
    SplitChildCommand(amount=Decimal("100.00"), description="first part"),
    SplitChildCommand(amount=Decimal("21.00"), description="second part"),
)


def _split(ledger: _Ledger, transaction_id: str, *, actor: str) -> None:
    split_transaction(
        bucket_id=_BUCKET_ID, transaction_id=transaction_id, children=_PARTS, actor=actor, ports=ledger.ports
    )


def _classified_split(ledger: _Ledger, transaction_id: str, *, actor: str) -> None:
    split_transaction_with_classified_children(
        bucket_id=_BUCKET_ID,
        transaction_id=transaction_id,
        children=_PARTS,
        child_classifications=tuple(ManualLedgerTransactionPatch(business_classification=_BUSINESS) for _ in _PARTS),
        classified_by=_PROPOSED_BY,
        actor=actor,
        source_command="aeat app ledger split --llm",
        ports=ledger.ports,
    )


def _accept_proposal(ledger: _Ledger, transaction_id: str, *, actor: str) -> None:
    apply_llm_classification(
        LLMClassificationSuggestion(
            transaction_id=transaction_id,
            provenance=_PROPOSED_BY,
            classification=BusinessClassification.PERSONAL,
            confidence=Decimal("0.9000"),
            reason="synthetic proposal",
        ),
        bucket_id=_BUCKET_ID,
        actor=actor,
        source_command="aeat app ledger classify --llm --apply",
        transaction_repository=ledger.ports.transaction_repository,
        bucket_event_repository=ledger.ports.bucket_event_repository,
    )


def _reclassify(ledger: _Ledger, transaction_id: str, *, actor: str) -> None:
    _classify(ledger, transaction_id, actor=actor, to=BusinessClassification.PERSONAL)


@_ACTORS
def test_a_first_classification_records_who_ran_the_write(
    ledger: _Ledger, actor: str, origin: ClassificationOrigin
) -> None:
    """Typed at creation, typed later, accepted from a model, or excluded: the party who ran the write decided."""
    at_creation = _add(ledger, description="classified at creation", actor=actor, classification=_BUSINESS)
    later = _add(ledger, description="classified later")
    _classify(ledger, later, actor=actor)
    accepted = _add(ledger, description="accepted from a model")
    _accept_proposal(ledger, accepted, actor=actor)
    excluded = _add(ledger, description="excluded")
    _exclude(ledger, excluded, actor=actor)
    unprocessed = _add(ledger, description="left unprocessed", actor=actor)

    for transaction_id in (at_creation, later, accepted, excluded):
        assert ledger.row(transaction_id).classification_origin is origin, ledger.row(transaction_id).raw.description
    assert ledger.row(accepted).classified_by == _PROPOSED_BY
    assert ledger.row(unprocessed).classification_origin is None


@_ACTORS
def test_a_rules_classification_is_nobodys_whoever_ran_the_rules_and_a_derivation_on_it_is_the_runners(
    ledger: _Ledger, actor: str, origin: ClassificationOrigin
) -> None:
    by_rule = _add(ledger, description="classified by a rule")
    _classify(ledger, by_rule, actor=actor, stamp="rule:synthetic")
    assert ledger.row(by_rule).classification_origin is ClassificationOrigin.AUTOMATIC

    _derive(ledger, by_rule, actor=actor)

    derived = ledger.row(by_rule)
    assert derived.classified_by == "derived:iva-category"
    assert (derived.taxable_base, derived.iva_amount) == (Decimal("100.00"), Decimal("21.00"))
    assert derived.classification_origin is origin


@_ACTORS
def test_a_write_that_changes_no_classification_fact_restamps_the_row_and_keeps_whose_decision_it_was(
    ledger: _Ledger, actor: str, origin: ClassificationOrigin
) -> None:
    """Attaching rebuilds the row and leaves the hand stamp, on a rule's row as on any other."""
    del origin
    by_rule = _by_a_rule(ledger, description="classified by a rule")
    by_hand = _add(ledger, description="classified by hand", classification=_BUSINESS)
    by_an_agent = _add(ledger, description="classified by an agent", actor=_AGENT, classification=_BUSINESS)
    expected = {
        by_rule: ClassificationOrigin.AUTOMATIC,
        by_hand: ClassificationOrigin.PERSON,
        by_an_agent: ClassificationOrigin.AGENT,
    }

    for index, transaction_id in enumerate(expected):
        _attach(ledger, transaction_id, _attachment(ledger, str(index).encode("ascii")), actor=actor)

    for transaction_id, kept in expected.items():
        rewritten = ledger.row(transaction_id)
        assert rewritten.classified_by == "manual"
        assert rewritten.attachment_ids
        assert rewritten.classification_origin is kept


def test_a_split_child_classified_in_the_split_records_who_ran_it_and_the_parent_keeps_its_own(
    ledger: _Ledger,
) -> None:
    parent = _by_a_rule(ledger, description="classified by a rule")
    before = set(ledger.transactions.load().transactions)

    _classified_split(ledger, parent, actor=_AGENT)

    rows = ledger.transactions.load().transactions
    children = [row for transaction_id, row in rows.items() if transaction_id not in before]
    assert len(children) == 2
    assert {child.classification_origin for child in children} == {ClassificationOrigin.AGENT}
    assert rows[parent].lifecycle_state is TransactionLifecycleState.SPLIT
    assert rows[parent].classification_origin is ClassificationOrigin.AUTOMATIC


_Write = Callable[..., None]
_REPLACING_WRITES: tuple[tuple[str, _Write], ...] = (
    ("derive", _derive),
    ("reclassify", _reclassify),
    ("accept-proposal", _accept_proposal),
    ("exclude", _exclude),
    ("split", _split),
    ("classified-split", _classified_split),
)
_WRITES = pytest.mark.parametrize(
    "write", [write for _, write in _REPLACING_WRITES], ids=[name for name, _ in _REPLACING_WRITES]
)


@_WRITES
@pytest.mark.parametrize("stamp", ["manual", "llm", "derived"])
def test_a_write_under_an_agents_label_is_refused_at_the_writer_on_a_row_the_person_decided(
    ledger: _Ledger, write: _Write, stamp: str
) -> None:
    """Whatever stamp the person's decision left, and with nothing stored by the refused write."""
    if stamp == "llm":
        row = _add(ledger, description="the person's row")
        _classify(ledger, row, actor=_PERSON, stamp=_PROPOSED_BY)
    else:
        row = _add(ledger, description="the person's row", classification=_BUSINESS)
        if stamp == "derived":
            _derive(ledger, row, actor=_PERSON, category="domestic_reduced")
    assert ledger.row(row).classified_by.startswith(stamp)
    assert ledger.row(row).classification_origin is ClassificationOrigin.PERSON
    before = ledger.stored()

    with pytest.raises(ProfileAccessRefusedError) as refused:
        write(ledger, row, actor=_AGENT)

    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
    assert ledger.stored() == before


@_WRITES
@pytest.mark.parametrize("decided_by", ["rule", "agent"])
def test_the_same_write_under_an_agents_label_goes_through_on_a_row_a_rule_or_an_agent_decided(
    ledger: _Ledger, write: _Write, decided_by: str
) -> None:
    if decided_by == "rule":
        row = _by_a_rule(ledger, description="classified by a rule")
    else:
        row = _add(ledger, description="classified by an agent", actor=_AGENT, classification=_BUSINESS)
    before = ledger.stored()

    write(ledger, row, actor=_AGENT)

    assert ledger.stored() != before


@_WRITES
def test_the_same_write_under_the_persons_label_goes_through_on_the_row_they_decided(
    ledger: _Ledger, write: _Write
) -> None:
    row = _add(ledger, description="the person's row", classification=_BUSINESS)
    before = ledger.stored()

    write(ledger, row, actor=_PERSON)

    assert ledger.stored() != before


@pytest.mark.parametrize("write", [_exclude, _split, _classified_split], ids=["exclude", "split", "classified-split"])
@pytest.mark.parametrize("linked_by", [_PERSON, _AGENT], ids=["the-persons-attachment", "the-agents-attachment"])
def test_setting_aside_an_unprocessed_row_under_an_agents_label_turns_on_who_linked_its_attachment(
    ledger: _Ledger, write: _Write, linked_by: str
) -> None:
    """The row records who linked each attachment, and an agent's own does not close the row to it."""
    row = _add(ledger, description="unprocessed with a document")
    _attach(ledger, row, _attachment(ledger, b"document"), actor=linked_by)
    before = ledger.stored()

    if linked_by == _PERSON:
        with pytest.raises(ProfileAccessRefusedError) as refused:
            write(ledger, row, actor=_AGENT)
        assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
        assert ledger.stored() == before
    else:
        write(ledger, row, actor=_AGENT)
        assert ledger.stored() != before


def test_a_detachment_under_an_agents_label_removes_what_an_agent_linked_and_not_what_the_person_linked(
    ledger: _Ledger,
) -> None:
    row = _add(ledger, description="unprocessed with two documents")
    the_persons, the_agents = _attachment(ledger, b"person"), _attachment(ledger, b"agent")
    _attach(ledger, row, the_persons, actor=_PERSON)
    _attach(ledger, row, the_agents, actor=_AGENT)
    before = ledger.stored()

    for requested in ((the_persons,), (the_agents, the_persons)):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            detach_manual_transaction_attachments(
                bucket_id=_BUCKET_ID, transaction_id=row, actor=_AGENT, attachment_ids=requested, ports=ledger.ports
            )
        assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
        assert ledger.stored() == before

    detach_manual_transaction_attachments(
        bucket_id=_BUCKET_ID, transaction_id=row, actor=_AGENT, attachment_ids=(the_agents,), ports=ledger.ports
    )
    assert ledger.row(row).attachment_ids == (the_persons,)
    detach_manual_transaction_attachments(
        bucket_id=_BUCKET_ID, transaction_id=row, actor=_PERSON, attachment_ids=(the_persons,), ports=ledger.ports
    )
    assert ledger.row(row).attachment_ids == ()


def _invoice(number: str) -> Invoice:
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": _BUCKET_ID,
            "invoice_number": number,
            "issued_at": _NOW_DATE,
            "counterparty_name": "Synthetic Supplier",
            "counterparty_tax_id": "A58818501",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "payment_status": PaymentStatus.PENDING,
            "lines": (
                InvoiceLine.model_validate(
                    {
                        "description": "synthetic expense",
                        "quantity": Decimal("1"),
                        "unit_price": Decimal("100.00"),
                        "subtotal": Decimal("100.00"),
                        "iva_rate": IvaRate.from_registry("RATE_21"),
                        "iva_amount": Decimal("21.00"),
                    },
                ),
            ),
        },
    )


def test_a_link_under_an_agents_label_does_not_replace_the_invoice_a_row_already_links(ledger: _Ledger) -> None:
    """The person's label replaces it as before; the row does not record who linked the earlier one."""
    first, second = _invoice("SYNTHETIC-1"), _invoice("SYNTHETIC-2")
    ledger.invoices.save(build_invoice_catalogue([first, second]))
    row = _add(ledger, description="unprocessed row to link")

    def link(invoice: Invoice, *, actor: str) -> None:
        link_manual_transaction_invoice(
            bucket_id=_BUCKET_ID, transaction_id=row, invoice_id=invoice.invoice_id, actor=actor, ports=ledger.ports
        )

    link(first, actor=_AGENT)
    assert ledger.row(row).invoice_id == first.invoice_id
    before = ledger.stored()

    with pytest.raises(ProfileAccessRefusedError) as refused:
        link(second, actor=_AGENT)

    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
    assert ledger.stored() == before
    assert second.invoice_id not in {
        invoice_id for invoice_id, stored in ledger.invoices.load().invoices.items() if stored.linked_transaction_ids
    }

    link(second, actor=_PERSON)
    assert ledger.row(row).invoice_id == second.invoice_id
