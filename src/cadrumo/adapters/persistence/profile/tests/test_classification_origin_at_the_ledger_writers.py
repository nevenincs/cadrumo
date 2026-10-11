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
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.domain.invoices.models import Invoice
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.transactions.classification_origin import ClassificationOrigin
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionLifecycleState

from .classification_origin_support import (
    AGENT,
    BUCKET_ID,
    BUSINESS,
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
        child_classifications=tuple(ManualLedgerTransactionPatch(business_classification=BUSINESS) for _ in _PARTS),
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
    at_creation = add_row(ledger, description="classified at creation", actor=actor, classification=BUSINESS)
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
    by_hand = add_row(ledger, description="classified by hand", classification=BUSINESS)
    by_an_agent = add_row(ledger, description="classified by an agent", actor=AGENT, classification=BUSINESS)
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
    ledger: Ledger, write: _Write, stamp: str
) -> None:
    """Whatever stamp the person's decision left, and with nothing stored by the refused write."""
    if stamp == "llm":
        row = add_row(ledger, description="the person's row")
        classify_row(ledger, row, actor=PERSON, stamp=_PROPOSED_BY)
    else:
        row = add_row(ledger, description="the person's row", classification=BUSINESS)
        if stamp == "derived":
            _derive(ledger, row, actor=PERSON, category="domestic_reduced")
    assert ledger.row(row).classified_by.startswith(stamp)
    assert ledger.row(row).classification_origin is ClassificationOrigin.PERSON
    before = ledger.stored()

    with pytest.raises(ProfileAccessRefusedError) as refused:
        write(ledger, row, actor=AGENT)

    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
    assert ledger.stored() == before


@_WRITES
@pytest.mark.parametrize("decided_by", ["rule", "agent"])
def test_the_same_write_under_an_agents_label_goes_through_on_a_row_a_rule_or_an_agent_decided(
    ledger: Ledger, write: _Write, decided_by: str
) -> None:
    if decided_by == "rule":
        row = add_row_classified_by_a_rule(ledger, description="classified by a rule")
    else:
        row = add_row(ledger, description="classified by an agent", actor=AGENT, classification=BUSINESS)
    before = ledger.stored()

    write(ledger, row, actor=AGENT)

    assert ledger.stored() != before


@_WRITES
def test_the_same_write_under_the_persons_label_goes_through_on_the_row_they_decided(
    ledger: Ledger, write: _Write
) -> None:
    row = add_row(ledger, description="the person's row", classification=BUSINESS)
    before = ledger.stored()

    write(ledger, row, actor=PERSON)

    assert ledger.stored() != before


@pytest.mark.parametrize("write", [_exclude, _split, _classified_split], ids=["exclude", "split", "classified-split"])
@pytest.mark.parametrize("linked_by", [PERSON, AGENT], ids=["the-persons-attachment", "the-agents-attachment"])
def test_setting_aside_an_unprocessed_row_under_an_agents_label_turns_on_who_linked_its_attachment(
    ledger: Ledger, write: _Write, linked_by: str
) -> None:
    """The row records who linked each attachment, and an agent's own does not close the row to it."""
    row = add_row(ledger, description="unprocessed with a document")
    attach_attachment(ledger, row, store_attachment(ledger, b"document"), actor=linked_by)
    before = ledger.stored()

    if linked_by == PERSON:
        with pytest.raises(ProfileAccessRefusedError) as refused:
            write(ledger, row, actor=AGENT)
        assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
        assert ledger.stored() == before
    else:
        write(ledger, row, actor=AGENT)
        assert ledger.stored() != before


def test_a_detachment_under_an_agents_label_removes_what_an_agent_linked_and_not_what_the_person_linked(
    ledger: Ledger,
) -> None:
    row = add_row(ledger, description="unprocessed with two documents")
    the_persons, the_agents = store_attachment(ledger, b"person"), store_attachment(ledger, b"agent")
    attach_attachment(ledger, row, the_persons, actor=PERSON)
    attach_attachment(ledger, row, the_agents, actor=AGENT)
    before = ledger.stored()

    for requested in ((the_persons,), (the_agents, the_persons)):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            detach_manual_transaction_attachments(
                bucket_id=BUCKET_ID, transaction_id=row, actor=AGENT, attachment_ids=requested, ports=ledger.ports
            )
        assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
        assert ledger.stored() == before

    detach_manual_transaction_attachments(
        bucket_id=BUCKET_ID, transaction_id=row, actor=AGENT, attachment_ids=(the_agents,), ports=ledger.ports
    )
    assert ledger.row(row).attachment_ids == (the_persons,)
    detach_manual_transaction_attachments(
        bucket_id=BUCKET_ID, transaction_id=row, actor=PERSON, attachment_ids=(the_persons,), ports=ledger.ports
    )
    assert ledger.row(row).attachment_ids == ()


def test_a_link_under_an_agents_label_does_not_replace_the_invoice_a_row_already_links(ledger: Ledger) -> None:
    """The person's label replaces it as before; the row does not record who linked the earlier one."""
    first, second = synthetic_invoice("SYNTHETIC-1"), synthetic_invoice("SYNTHETIC-2")
    ledger.invoices.save(build_invoice_catalogue([first, second]))
    row = add_row(ledger, description="unprocessed row to link")

    def link(invoice: Invoice, *, actor: str) -> None:
        link_manual_transaction_invoice(
            bucket_id=BUCKET_ID, transaction_id=row, invoice_id=invoice.invoice_id, actor=actor, ports=ledger.ports
        )

    link(first, actor=AGENT)
    assert ledger.row(row).invoice_id == first.invoice_id
    before = ledger.stored()

    with pytest.raises(ProfileAccessRefusedError) as refused:
        link(second, actor=AGENT)

    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
    assert ledger.stored() == before
    assert second.invoice_id not in {
        invoice_id for invoice_id, stored in ledger.invoices.load().invoices.items() if stored.linked_transaction_ids
    }

    link(second, actor=PERSON)
    assert ledger.row(row).invoice_id == second.invoice_id
