"""A person who confirms or completes a classification is recorded as the one who decided it.

The ledger actions run over real secure storage. A person who submits the
classification a rule, a model or an agent already gave a row has accepted it:
the row records them as the one who decided although no value moves, and the
history records the classification they confirmed. A person who sets any
tax-bearing fact of such a row is recorded the same way; one who edits only a
note or a label is not. Nobody else is recorded by restating a row. Who
decided a row is a stored fact: a write under any label that changes a
tax-bearing fact, or sets the row aside or restores it, is stored whoever
decided the row and whoever set it aside.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.ledger.actions_lifecycle import (
    archive_manual_transaction,
    restore_manual_transaction,
    stash_manual_transaction,
)
from cadrumo.application.ledger.actions_manual import update_manual_transaction_fields
from cadrumo.application.ledger.models import ManualLedgerTransactionPatch, ManualLedgerTransactionResult
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.eu_member_state_catalogue import require_eu_member_state
from cadrumo.domain.calculations.registry.iva_deduction_catalogue import require_iva_deduction_fact_kind
from cadrumo.domain.transactions.classification_origin import (
    CLASSIFICATION_DECISION_FIELDS,
    ClassificationOrigin,
    classification_facts,
)
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.m210_income_classification import (
    M210IncomeClassification,
    required_m210_payer_mode_for_code,
    resolve_m210_payer_mode,
)

from .classification_origin_support import (
    AGENT,
    BUCKET_ID,
    PERSON,
    Ledger,
    add_row,
    add_row_classified_by_a_rule,
    classify_row,
    composed_ledger,
)
from .test_classification_origin_at_the_ledger_writers import _PROPOSED_BY, _accept_proposal, _derive

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLASSIFY = "aeat app ledger classify"
_ADD = "aeat app ledger add"
_PARTIES = pytest.mark.parametrize("party", ["agent", "rule", "model"])


@pytest.fixture
def ledger(tmp_path: Path) -> Generator[Ledger]:
    with composed_ledger(tmp_path) as composed:
        yield composed


def _row_decided_by(ledger: Ledger, party: str) -> str:
    """Store a business row whose classification ``party`` decided, with the stamp that party's write leaves."""
    if party == "agent":
        return add_row(
            ledger, description="classified by an agent", actor=AGENT, classification=BusinessClassification.BUSINESS
        )
    if party == "rule":
        return add_row_classified_by_a_rule(ledger, description="classified by a rule")
    row = add_row(ledger, description="classified from a model's proposal")
    classify_row(ledger, row, actor=AGENT, stamp=_PROPOSED_BY)
    return row


def _write(
    ledger: Ledger,
    row: str,
    values: dict[str, object],
    *,
    actor: str,
    source_command: str = _CLASSIFY,
    reaffirm: bool = False,
) -> ManualLedgerTransactionResult:
    return update_manual_transaction_fields(
        bucket_id=BUCKET_ID,
        transaction_id=row,
        patch=ManualLedgerTransactionPatch.model_validate(values),
        actor=actor,
        source_command=source_command,
        reaffirm=reaffirm,
        ports=ledger.ports,
    )


@_PARTIES
@pytest.mark.parametrize("reaffirm", [False, True], ids=["plain", "reaffirm"])
@pytest.mark.parametrize("source_command", [_CLASSIFY, _ADD], ids=["another-reason", "same-reason"])
def test_a_person_confirming_the_classification_a_row_already_has_takes_the_row_and_the_history_shows_it(
    ledger: Ledger, party: str, reaffirm: bool, source_command: str
) -> None:
    """No value moves, and the write is neither skipped nor refused as changing nothing."""
    row = _row_decided_by(ledger, party)
    given = ledger.row(row)
    assert given.classification_origin is not ClassificationOrigin.PERSON
    events_before = set(ledger.events.load().events)

    confirmed = _write(
        ledger,
        row,
        {"business_classification": BusinessClassification.BUSINESS},
        actor=PERSON,
        source_command=source_command,
        reaffirm=reaffirm,
    )

    stored = ledger.row(row)
    assert classification_facts(stored) == classification_facts(given)
    assert stored.classification_origin is ClassificationOrigin.PERSON
    assert stored.classified_by == "manual"
    recorded = {
        event_id: event for event_id, event in ledger.events.load().events.items() if event_id not in events_before
    }
    assert set(recorded) == set(confirmed.bucket_event_ids) and recorded
    assert {event.actor for event in recorded.values()} == {PERSON}
    assert BucketEventType.LEDGER_TRANSACTION_CLASSIFIED in {event.event_type for event in recorded.values()}


def test_a_person_restating_their_own_classification_writes_nothing(ledger: Ledger) -> None:
    """The row is already theirs, so the confirmation stays the no-op it was."""
    row = add_row(ledger, description="the person's row", classification=BusinessClassification.BUSINESS)
    before = ledger.stored()

    restated = _write(
        ledger, row, {"business_classification": BusinessClassification.BUSINESS}, actor=PERSON, source_command=_ADD
    )

    assert restated.bucket_event_ids == ()
    assert ledger.stored() == before


def test_an_agents_label_restating_the_persons_classification_takes_nothing(ledger: Ledger) -> None:
    """Otherwise submitting the value a row already has would be a way to take it."""
    row = add_row(ledger, description="the person's row", classification=BusinessClassification.BUSINESS)
    before = ledger.stored()

    restated = _write(
        ledger, row, {"business_classification": BusinessClassification.BUSINESS}, actor=AGENT, source_command=_ADD
    )

    assert restated.bucket_event_ids == ()
    assert ledger.stored() == before
    personal = add_row(ledger, description="the person's personal row", classification=BusinessClassification.PERSONAL)
    _accept_proposal(ledger, personal, actor=AGENT)
    assert ledger.row(personal).classification_origin is ClassificationOrigin.PERSON


def test_a_person_running_the_derivation_an_agent_ran_or_accepting_the_proposal_an_agent_accepted_takes_the_row(
    ledger: Ledger,
) -> None:
    derived = add_row_classified_by_a_rule(ledger, description="classified by a rule")
    _derive(ledger, derived, actor=AGENT)
    figures = classification_facts(ledger.row(derived))
    assert ledger.row(derived).classification_origin is ClassificationOrigin.AGENT
    accepted = add_row(ledger, description="accepted from a model")
    _accept_proposal(ledger, accepted, actor=AGENT)
    assert ledger.row(accepted).classification_origin is ClassificationOrigin.AGENT

    _derive(ledger, derived, actor=PERSON)
    _accept_proposal(ledger, accepted, actor=PERSON)

    assert classification_facts(ledger.row(derived)) == figures
    for row in (derived, accepted):
        assert ledger.row(row).classification_origin is ClassificationOrigin.PERSON


def _m210(_ledger_unused: Ledger) -> M210IncomeClassification:
    devengo = date(2025, 1, 21)
    return M210IncomeClassification(
        official_tipo_renta_code="35",
        gross_income_amount=Decimal("121.00"),
        applicable_rate=Decimal("0.24"),
        payer_mode=required_m210_payer_mode_for_code("35", effective_date=devengo)
        or resolve_m210_payer_mode(effective_date=devengo),
        payer_id=None,
        asset_or_right_id="ES-ACTIVO-210",
    )


_FIELD_VALUES: dict[str, Callable[[Ledger], object]] = {
    "counterparty_country": lambda ledger: "DE",
    "counterparty_identification_state": lambda ledger: require_eu_member_state("DE", authority=ledger.ports.operation),
    "deduction_fact_kind": lambda ledger: require_iva_deduction_fact_kind(
        "domestic_current", authority=ledger.ports.operation
    ),
    "investment_asset_id": lambda ledger: "bi-0001",
    "m210_income_classification": _m210,
}
_FIELDS = pytest.mark.parametrize("field", list(_FIELD_VALUES))


@_FIELDS
@pytest.mark.parametrize("with_classification", [True, False], ids=["classification", "update"])
def test_a_person_setting_one_further_tax_bearing_fact_on_an_agents_row_takes_the_row(
    ledger: Ledger, field: str, with_classification: bool
) -> None:
    """Through a classification that restates the class, and through an update that sets the fact alone."""
    row = add_row(
        ledger, description="classified by an agent", actor=AGENT, classification=BusinessClassification.BUSINESS
    )
    values: dict[str, object] = {field: _FIELD_VALUES[field](ledger)}
    if with_classification:
        values["business_classification"] = BusinessClassification.BUSINESS

    _write(ledger, row, values, actor=PERSON)

    assert field in CLASSIFICATION_DECISION_FIELDS
    assert getattr(ledger.row(row), field) is not None
    assert ledger.row(row).classification_origin is ClassificationOrigin.PERSON


_CHANGES: dict[str, Callable[[Ledger], object]] = {
    **_FIELD_VALUES,
    "source_jurisdiction": lambda ledger: "FR",
    "category_id": lambda ledger: "material_oficina",
    "amount": lambda ledger: Decimal("242.00"),
    "booked_date": lambda ledger: date(2025, 2, 21),
    "direction": lambda ledger: TransactionDirection.INCOMING,
}


@pytest.mark.parametrize("field", list(_CHANGES))
@pytest.mark.parametrize(
    ("decided_by", "actor", "origin"),
    [(PERSON, AGENT, ClassificationOrigin.AGENT), (AGENT, PERSON, ClassificationOrigin.PERSON)],
    ids=["agent-on-the-persons-row", "person-on-an-agents-row"],
)
def test_a_write_that_changes_a_tax_bearing_fact_is_stored_under_either_label_and_records_who_ran_it(
    ledger: Ledger, field: str, decided_by: str, actor: str, origin: ClassificationOrigin
) -> None:
    """Whichever fact it is: the writer compares the one set the origin is decided from."""
    row = add_row(
        ledger, description="a classified row", actor=decided_by, classification=BusinessClassification.BUSINESS
    )
    before = ledger.stored()

    changed = _write(ledger, row, {field: _CHANGES[field](ledger)}, actor=actor)

    assert field in CLASSIFICATION_DECISION_FIELDS
    assert ledger.stored() != before
    assert ledger.row(changed.ref.transaction_id).classification_origin is origin


@pytest.mark.parametrize("values", [{"notes": "a note"}, {"group_label": "a label"}], ids=["note", "label"])
def test_an_edit_that_sets_no_tax_bearing_fact_neither_takes_a_row_nor_is_refused(
    ledger: Ledger, values: dict[str, object]
) -> None:
    """A note or a label decides nothing about how the row is taxed, whoever writes it."""
    by_an_agent = add_row(
        ledger, description="classified by an agent", actor=AGENT, classification=BusinessClassification.BUSINESS
    )
    by_the_person = add_row(ledger, description="the person's row", classification=BusinessClassification.BUSINESS)

    _write(ledger, by_an_agent, values, actor=PERSON, source_command="aeat app ledger update")
    _write(ledger, by_the_person, values, actor=AGENT, source_command="aeat app ledger update")

    assert not set(values) & CLASSIFICATION_DECISION_FIELDS
    assert ledger.row(by_an_agent).classification_origin is ClassificationOrigin.AGENT
    assert ledger.row(by_the_person).classification_origin is ClassificationOrigin.PERSON


_SetAside = Callable[..., ManualLedgerTransactionResult]
_SET_ASIDES = pytest.mark.parametrize(
    ("set_aside", "state"),
    [
        (archive_manual_transaction, TransactionLifecycleState.ARCHIVED),
        (stash_manual_transaction, TransactionLifecycleState.STASHED),
    ],
    ids=["archive", "stash"],
)


def _lifecycle(act: _SetAside, ledger: Ledger, row: str, *, actor: str) -> None:
    act(bucket_id=BUCKET_ID, transaction_id=row, actor=actor, reason="synthetic", ports=ledger.ports)


_LABELS = [PERSON, AGENT]
_LABEL_IDS = ["person", "agent"]


@_SET_ASIDES
@pytest.mark.parametrize("set_aside_by", _LABELS, ids=[f"set-aside-by-{label}" for label in _LABEL_IDS])
@pytest.mark.parametrize("restored_by", _LABELS, ids=[f"restored-by-{label}" for label in _LABEL_IDS])
def test_a_row_is_set_aside_and_restored_under_either_label_whoever_decided_it_and_whoever_set_it_aside(
    ledger: Ledger, set_aside: _SetAside, state: TransactionLifecycleState, set_aside_by: str, restored_by: str
) -> None:
    """The row records who ran each archive, stash and restore; none of them is refused for that record."""
    for row in (
        add_row(ledger, description="unprocessed"),
        add_row_classified_by_a_rule(ledger, description="classified by a rule"),
        add_row(
            ledger, description="classified by an agent", actor=AGENT, classification=BusinessClassification.BUSINESS
        ),
        add_row(ledger, description="the person's row", classification=BusinessClassification.BUSINESS),
    ):
        decided = ledger.row(row).classification_origin

        _lifecycle(set_aside, ledger, row, actor=set_aside_by)
        assert ledger.row(row).lifecycle_state is state
        assert ledger.row(row).lifecycle_lineage[-1].actor == set_aside_by

        _lifecycle(restore_manual_transaction, ledger, row, actor=restored_by)
        assert ledger.row(row).lifecycle_state is TransactionLifecycleState.ACTIVE
        assert ledger.row(row).lifecycle_lineage[-1].actor == restored_by
        assert ledger.row(row).classification_origin is decided


@pytest.mark.parametrize("stashed_by", _LABELS, ids=[f"stashed-by-{label}" for label in _LABEL_IDS])
@pytest.mark.parametrize("archived_by", _LABELS, ids=[f"archived-by-{label}" for label in _LABEL_IDS])
def test_a_stashed_row_is_archived_and_restored_under_either_label_whoever_stashed_it(
    ledger: Ledger, stashed_by: str, archived_by: str
) -> None:
    row = add_row_classified_by_a_rule(ledger, description="classified by a rule")
    _lifecycle(stash_manual_transaction, ledger, row, actor=stashed_by)

    _lifecycle(archive_manual_transaction, ledger, row, actor=archived_by)
    assert ledger.row(row).lifecycle_state is TransactionLifecycleState.ARCHIVED

    _lifecycle(restore_manual_transaction, ledger, row, actor=archived_by)
    assert ledger.row(row).lifecycle_state is TransactionLifecycleState.ACTIVE
