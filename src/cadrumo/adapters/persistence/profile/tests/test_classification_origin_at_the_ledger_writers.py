"""Every ledger writer records whose decision a classification is, and admits the same write under any label.

The ledger actions run over real secure storage. A write recorded under an
agent's session label is an agent's, because an agent's execution can record no
other label. Each action that sets or changes a classification, its share or a
tax figure records who decided it; an action that changes none of them leaves
the recorded origin as it found it, whatever stamp it leaves. The label and
the recorded origin are facts the writers store: no writer refuses a write for
the label it carries or for who decided the row it replaces.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.ledger.actions_lifecycle import mark_transaction_reviewed_excluded
from cadrumo.application.ledger.actions_manual import (
    detach_manual_transaction_attachments,
    link_manual_transaction_invoice,
)
from cadrumo.application.ledger.actions_split_merge import split_transaction, split_transaction_with_classified_children
from cadrumo.application.ledger.llm_classification import apply_llm_classification, derive_operator_iva_substrate
from cadrumo.application.ledger.llm_classification_ports import LLMClassificationSuggestion
from cadrumo.application.ledger.models import (
    ManualLedgerTransactionPatch,
    SplitChildCommand,
)
from cadrumo.domain.invoices.models import Invoice
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.transactions.classification_origin import ClassificationOrigin
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionLifecycleState

from .classification_origin_support import (
    AGENT,
    BUCKET_ID,
    PERSON,
    Ledger,
    add_row,
    add_row_classified_by_a_rule,
    attach_attachment,
    classify_row,
    composed_ledger,
    store_attachment,
    synthetic_invoice,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROPOSED_BY = "llm:local-text:synthetic"
_ACTORS = pytest.mark.parametrize(
    ("actor", "origin"),
    [(PERSON, ClassificationOrigin.PERSON), (AGENT, ClassificationOrigin.AGENT)],
    ids=["person", "agent"],
)


@pytest.fixture
def ledger(tmp_path: Path) -> Generator[Ledger]:
    with composed_ledger(tmp_path) as composed:
        yield composed


def _derive(ledger: Ledger, transaction_id: str, *, actor: str, category: str = "domestic_general") -> None:
    derive_operator_iva_substrate(
        bucket_id=BUCKET_ID,
        transaction_id=transaction_id,
        iva_category=IvaCategory(category),
        actor=actor,
        source_command="aeat app ledger classify --iva-category --saturate",
        ports=ledger.ports,
    )


def _exclude(ledger: Ledger, transaction_id: str, *, actor: str) -> None:
    mark_transaction_reviewed_excluded(
        bucket_id=BUCKET_ID,
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


def _split(ledger: Ledger, transaction_id: str, *, actor: str) -> None:
    split_transaction(
        bucket_id=BUCKET_ID, transaction_id=transaction_id, children=_PARTS, actor=actor, ports=ledger.ports
    )


def _classified_split(ledger: Ledger, transaction_id: str, *, actor: str) -> None:
    split_transaction_with_classified_children(
        bucket_id=BUCKET_ID,
        transaction_id=transaction_id,
        children=_PARTS,
        child_classifications=tuple(
            ManualLedgerTransactionPatch(business_classification=BusinessClassification.BUSINESS) for _ in _PARTS
        ),
        classified_by=_PROPOSED_BY,
        actor=actor,
        source_command="aeat app ledger split --llm",
        ports=ledger.ports,
    )


def _accept_proposal(ledger: Ledger, transaction_id: str, *, actor: str) -> None:
    apply_llm_classification(
        LLMClassificationSuggestion(
            transaction_id=transaction_id,
            provenance=_PROPOSED_BY,
            classification=BusinessClassification.PERSONAL,
            confidence=Decimal("0.9000"),
            reason="synthetic proposal",
        ),
        bucket_id=BUCKET_ID,
        actor=actor,
        source_command="aeat app ledger classify --llm --apply",
        transaction_repository=ledger.ports.transaction_repository,
        bucket_event_repository=ledger.ports.bucket_event_repository,
    )


def _reclassify(ledger: Ledger, transaction_id: str, *, actor: str) -> None:
    classify_row(ledger, transaction_id, actor=actor, to=BusinessClassification.PERSONAL)


@_ACTORS
def test_a_first_classification_records_who_ran_the_write(
    ledger: Ledger, actor: str, origin: ClassificationOrigin
) -> None:
    """Typed at creation, typed later, accepted from a model, or excluded: the party who ran the write decided."""
    at_creation = add_row(
        ledger, description="classified at creation", actor=actor, classification=BusinessClassification.BUSINESS
    )
    later = add_row(ledger, description="classified later")
    classify_row(ledger, later, actor=actor)
    accepted = add_row(ledger, description="accepted from a model")
    _accept_proposal(ledger, accepted, actor=actor)
    excluded = add_row(ledger, description="excluded")
    _exclude(ledger, excluded, actor=actor)
    unprocessed = add_row(ledger, description="left unprocessed", actor=actor)

    for transaction_id in (at_creation, later, accepted, excluded):
        assert ledger.row(transaction_id).classification_origin is origin, ledger.row(transaction_id).raw.description
    assert ledger.row(accepted).classified_by == _PROPOSED_BY
    assert ledger.row(unprocessed).classification_origin is None


@_ACTORS
def test_a_rules_classification_is_nobodys_whoever_ran_the_rules_and_a_derivation_on_it_is_the_runners(
    ledger: Ledger, actor: str, origin: ClassificationOrigin
) -> None:
    by_rule = add_row(ledger, description="classified by a rule")
    classify_row(ledger, by_rule, actor=actor, stamp="rule:synthetic")
    assert ledger.row(by_rule).classification_origin is ClassificationOrigin.AUTOMATIC

    _derive(ledger, by_rule, actor=actor)

    derived = ledger.row(by_rule)
    assert derived.classified_by == "derived:iva-category"
    assert (derived.taxable_base, derived.iva_amount) == (Decimal("100.00"), Decimal("21.00"))
    assert derived.classification_origin is origin


@_ACTORS
def test_a_write_that_changes_no_classification_fact_restamps_the_row_and_keeps_whose_decision_it_was(
    ledger: Ledger, actor: str, origin: ClassificationOrigin
) -> None:
    """Attaching rebuilds the row and leaves the hand stamp, on a rule's row as on any other."""
    del origin
    by_rule = add_row_classified_by_a_rule(ledger, description="classified by a rule")
    by_hand = add_row(ledger, description="classified by hand", classification=BusinessClassification.BUSINESS)
    by_an_agent = add_row(
        ledger, description="classified by an agent", actor=AGENT, classification=BusinessClassification.BUSINESS
    )
    expected = {
        by_rule: ClassificationOrigin.AUTOMATIC,
        by_hand: ClassificationOrigin.PERSON,
        by_an_agent: ClassificationOrigin.AGENT,
    }

    for index, transaction_id in enumerate(expected):
        attach_attachment(ledger, transaction_id, store_attachment(ledger, str(index).encode("ascii")), actor=actor)

    for transaction_id, kept in expected.items():
        rewritten = ledger.row(transaction_id)
        assert rewritten.classified_by == "manual"
        assert rewritten.attachment_ids
        assert rewritten.classification_origin is kept


def test_a_split_child_classified_in_the_split_records_who_ran_it_and_the_parent_keeps_its_own(
    ledger: Ledger,
) -> None:
    parent = add_row_classified_by_a_rule(ledger, description="classified by a rule")
    before = set(ledger.transactions.load().transactions)

    _classified_split(ledger, parent, actor=AGENT)

    rows = ledger.transactions.load().transactions
    children = [row for transaction_id, row in rows.items() if transaction_id not in before]
    assert len(children) == 2
    assert {child.classification_origin for child in children} == {ClassificationOrigin.AGENT}
    assert rows[parent].lifecycle_state is TransactionLifecycleState.SPLIT
    assert rows[parent].classification_origin is ClassificationOrigin.AUTOMATIC


_Write = Callable[..., None]
_WRITES_IN_PLACE: tuple[tuple[str, _Write], ...] = (
    ("derive", _derive),
    ("reclassify", _reclassify),
    ("accept-proposal", _accept_proposal),
    ("exclude", _exclude),
)
_SPLITS: tuple[tuple[str, _Write], ...] = (("split", _split), ("classified-split", _classified_split))
_DECIDED_BY = pytest.mark.parametrize("decided_by", ["person", "rule", "agent"])


def _row_decided_by(ledger: Ledger, decided_by: str) -> str:
    if decided_by == "rule":
        return add_row_classified_by_a_rule(ledger, description="classified by a rule")
    actor = PERSON if decided_by == "person" else AGENT
    return add_row(
        ledger,
        description=f"classified by the {decided_by}",
        actor=actor,
        classification=BusinessClassification.BUSINESS,
    )


@pytest.mark.parametrize("write", [write for _, write in _WRITES_IN_PLACE], ids=[name for name, _ in _WRITES_IN_PLACE])
@_ACTORS
@_DECIDED_BY
def test_a_write_that_replaces_what_a_row_carries_goes_through_under_either_label_and_records_who_ran_it(
    ledger: Ledger, write: _Write, actor: str, origin: ClassificationOrigin, decided_by: str
) -> None:
    """Whoever decided the row before, the write is stored and the row then names the party who ran it."""
    row = _row_decided_by(ledger, decided_by)
    before = ledger.stored()

    write(ledger, row, actor=actor)

    assert ledger.stored() != before
    assert ledger.row(row).classification_origin is origin


@pytest.mark.parametrize("write", [write for _, write in _SPLITS], ids=[name for name, _ in _SPLITS])
@_ACTORS
@_DECIDED_BY
def test_a_split_goes_through_under_either_label_and_the_parent_keeps_whose_decision_it_was(
    ledger: Ledger, write: _Write, actor: str, origin: ClassificationOrigin, decided_by: str
) -> None:
    del origin
    row = _row_decided_by(ledger, decided_by)
    decided = ledger.row(row).classification_origin

    write(ledger, row, actor=actor)

    parent = ledger.row(row)
    assert parent.lifecycle_state is TransactionLifecycleState.SPLIT
    assert parent.classification_origin is decided


@pytest.mark.parametrize("write", [_exclude, _split, _classified_split], ids=["exclude", "split", "classified-split"])
@pytest.mark.parametrize("linked_by", [PERSON, AGENT], ids=["the-persons-attachment", "the-agents-attachment"])
@pytest.mark.parametrize("actor", [PERSON, AGENT], ids=["person", "agent"])
def test_setting_aside_a_row_that_carries_a_document_goes_through_whoever_linked_it(
    ledger: Ledger, write: _Write, linked_by: str, actor: str
) -> None:
    row = add_row(ledger, description="unprocessed with a document")
    attach_attachment(ledger, row, store_attachment(ledger, b"document"), actor=linked_by)
    before = ledger.stored()

    write(ledger, row, actor=actor)

    assert ledger.stored() != before
    assert ledger.row(row).attachment_ids


@pytest.mark.parametrize("actor", [PERSON, AGENT], ids=["person", "agent"])
def test_a_detachment_removes_the_named_attachment_whoever_linked_it(ledger: Ledger, actor: str) -> None:
    row = add_row(ledger, description="unprocessed with two documents")
    the_persons, the_agents = store_attachment(ledger, b"person"), store_attachment(ledger, b"agent")
    attach_attachment(ledger, row, the_persons, actor=PERSON)
    attach_attachment(ledger, row, the_agents, actor=AGENT)

    detach_manual_transaction_attachments(
        bucket_id=BUCKET_ID, transaction_id=row, actor=actor, attachment_ids=(the_persons,), ports=ledger.ports
    )
    assert ledger.row(row).attachment_ids == (the_agents,)
    detach_manual_transaction_attachments(
        bucket_id=BUCKET_ID, transaction_id=row, actor=actor, attachment_ids=(the_agents,), ports=ledger.ports
    )
    assert ledger.row(row).attachment_ids == ()


@pytest.mark.parametrize("actor", [PERSON, AGENT], ids=["person", "agent"])
@pytest.mark.parametrize("first_linked_by", [PERSON, AGENT], ids=["linked-by-the-person", "linked-by-an-agent"])
def test_a_link_replaces_the_invoice_a_row_already_links_under_either_label(
    ledger: Ledger, actor: str, first_linked_by: str
) -> None:
    first, second = synthetic_invoice("SYNTHETIC-1"), synthetic_invoice("SYNTHETIC-2")
    ledger.invoices.save(build_invoice_catalogue([first, second]))
    row = add_row(ledger, description="unprocessed row to link")

    def link(invoice: Invoice, *, linked_by: str) -> None:
        link_manual_transaction_invoice(
            bucket_id=BUCKET_ID, transaction_id=row, invoice_id=invoice.invoice_id, actor=linked_by, ports=ledger.ports
        )

    link(first, linked_by=first_linked_by)
    assert ledger.row(row).invoice_id == first.invoice_id

    link(second, linked_by=actor)

    assert ledger.row(row).invoice_id == second.invoice_id
    assert row in ledger.invoices.load().invoices[second.invoice_id].linked_transaction_ids
