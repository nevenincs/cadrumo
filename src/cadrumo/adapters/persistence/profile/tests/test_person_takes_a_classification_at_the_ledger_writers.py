"""A person who confirms or completes a classification owns it, and an agent's label then changes nothing of it.

The ledger actions run over real secure storage. A person who submits the
classification a rule, a model or an agent already gave a row has accepted it:
the row becomes theirs although no value moves, and the history records the
classification they confirmed. A person who sets any tax-bearing fact of such
a row takes it the same way; one who edits only a note or a label does not.
Nobody else takes a row by restating it. Once the row is the person's, a write
recorded under an agent's label that would change any tax-bearing fact of it,
or archive or stash it, is refused at the writer with nothing stored, and an
agent's label restores only what an agent's label set aside.
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
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
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

from .test_classification_origin_at_the_ledger_writers import (
    _AGENT,
    _BUCKET_ID,
    _BUSINESS,
    _PERSON,
    _PROPOSED_BY,
    _REPLACING_WRITES,
    _accept_proposal,
    _add,
    _by_a_rule,
    _classify,
    _derive,
    _exclude,
    _Ledger,
    _ledger,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLASSIFY = "aeat app ledger classify"
_ADD = "aeat app ledger add"
_PARTIES = pytest.mark.parametrize("party", ["agent", "rule", "model"])


@pytest.fixture
def ledger(tmp_path: Path) -> Generator[_Ledger]:
    with _ledger(tmp_path) as composed:
        yield composed


def _row_decided_by(ledger: _Ledger, party: str) -> str:
    """Store a business row whose classification ``party`` decided, with the stamp that party's write leaves."""
    if party == "agent":
        return _add(ledger, description="classified by an agent", actor=_AGENT, classification=_BUSINESS)
    if party == "rule":
        return _by_a_rule(ledger, description="classified by a rule")
    row = _add(ledger, description="classified from a model's proposal")
    _classify(ledger, row, actor=_AGENT, stamp=_PROPOSED_BY)
    return row


def _write(
    ledger: _Ledger,
    row: str,
    values: dict[str, object],
    *,
    actor: str,
    source_command: str = _CLASSIFY,
    reaffirm: bool = False,
) -> ManualLedgerTransactionResult:
    return update_manual_transaction_fields(
        bucket_id=_BUCKET_ID,
        transaction_id=row,
        patch=ManualLedgerTransactionPatch.model_validate(values),
        actor=actor,
        source_command=source_command,
        reaffirm=reaffirm,
        ports=ledger.ports,
    )


def _refused(act: Callable[[], object]) -> bool:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        act()
    return refused.value.reason is AccessDenialCode.FRONTEND_DENIED


def _every_agent_write_is_refused(ledger: _Ledger, row: str) -> bool:
    """Run each replacing write under an agent's label; each must be refused and store nothing."""
    before = ledger.stored()
    for name, write in _REPLACING_WRITES:
        assert _refused(lambda write=write: write(ledger, row, actor=_AGENT)), name
        assert ledger.stored() == before, name
    return True


@_PARTIES
@pytest.mark.parametrize("reaffirm", [False, True], ids=["plain", "reaffirm"])
@pytest.mark.parametrize("source_command", [_CLASSIFY, _ADD], ids=["another-reason", "same-reason"])
def test_a_person_confirming_the_classification_a_row_already_has_takes_the_row_and_the_history_shows_it(
    ledger: _Ledger, party: str, reaffirm: bool, source_command: str
) -> None:
    """No value moves, and the write is neither skipped nor refused as changing nothing."""
    row = _row_decided_by(ledger, party)
    given = ledger.row(row)
    assert given.classification_origin is not ClassificationOrigin.PERSON
    events_before = set(ledger.events.load().events)

    confirmed = _write(
        ledger,
        row,
        {"business_classification": _BUSINESS},
        actor=_PERSON,
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
    assert {event.actor for event in recorded.values()} == {_PERSON}
    assert BucketEventType.LEDGER_TRANSACTION_CLASSIFIED in {event.event_type for event in recorded.values()}
    assert _every_agent_write_is_refused(ledger, row)


def test_a_person_restating_their_own_classification_writes_nothing(ledger: _Ledger) -> None:
    """The row is already theirs, so the confirmation stays the no-op it was."""
    row = _add(ledger, description="the person's row", classification=_BUSINESS)
    before = ledger.stored()

    restated = _write(ledger, row, {"business_classification": _BUSINESS}, actor=_PERSON, source_command=_ADD)

    assert restated.bucket_event_ids == ()
    assert ledger.stored() == before


def test_an_agents_label_restating_the_persons_classification_takes_nothing(ledger: _Ledger) -> None:
    """Otherwise submitting the value a row already has would be a way to take it."""
    row = _add(ledger, description="the person's row", classification=_BUSINESS)
    before = ledger.stored()

    restated = _write(ledger, row, {"business_classification": _BUSINESS}, actor=_AGENT, source_command=_ADD)

    assert restated.bucket_event_ids == ()
    assert ledger.stored() == before
    personal = _add(ledger, description="the person's personal row", classification=BusinessClassification.PERSONAL)
    _accept_proposal(ledger, personal, actor=_AGENT)
    assert ledger.row(personal).classification_origin is ClassificationOrigin.PERSON
    assert _every_agent_write_is_refused(ledger, row)


def test_a_person_running_the_derivation_an_agent_ran_or_accepting_the_proposal_an_agent_accepted_takes_the_row(
    ledger: _Ledger,
) -> None:
    derived = _by_a_rule(ledger, description="classified by a rule")
    _derive(ledger, derived, actor=_AGENT)
    figures = classification_facts(ledger.row(derived))
    assert ledger.row(derived).classification_origin is ClassificationOrigin.AGENT
    accepted = _add(ledger, description="accepted from a model")
    _accept_proposal(ledger, accepted, actor=_AGENT)
    assert ledger.row(accepted).classification_origin is ClassificationOrigin.AGENT

    _derive(ledger, derived, actor=_PERSON)
    _accept_proposal(ledger, accepted, actor=_PERSON)

    assert classification_facts(ledger.row(derived)) == figures
    for row in (derived, accepted):
        assert ledger.row(row).classification_origin is ClassificationOrigin.PERSON
        assert _refused(lambda row=row: _exclude(ledger, row, actor=_AGENT))


def _m210(_ledger_unused: _Ledger) -> M210IncomeClassification:
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


_FIELD_VALUES: dict[str, Callable[[_Ledger], object]] = {
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
    ledger: _Ledger, field: str, with_classification: bool
) -> None:
    """Through a classification that restates the class, and through an update that sets the fact alone."""
    row = _add(ledger, description="classified by an agent", actor=_AGENT, classification=_BUSINESS)
    values: dict[str, object] = {field: _FIELD_VALUES[field](ledger)}
    if with_classification:
        values["business_classification"] = _BUSINESS

    _write(ledger, row, values, actor=_PERSON)

    assert field in CLASSIFICATION_DECISION_FIELDS
    assert getattr(ledger.row(row), field) is not None
    assert ledger.row(row).classification_origin is ClassificationOrigin.PERSON
    before = ledger.stored()
    assert _refused(lambda: _exclude(ledger, row, actor=_AGENT))
    assert ledger.stored() == before


_CHANGES: dict[str, Callable[[_Ledger], object]] = {
    **_FIELD_VALUES,
    "source_jurisdiction": lambda ledger: "FR",
    "category_id": lambda ledger: "material_oficina",
    "amount": lambda ledger: Decimal("242.00"),
    "booked_date": lambda ledger: date(2025, 2, 21),
    "direction": lambda ledger: TransactionDirection.INCOMING,
}


@pytest.mark.parametrize("field", list(_CHANGES))
def test_a_write_under_an_agents_label_that_changes_a_tax_bearing_fact_of_the_persons_row_is_refused(
    ledger: _Ledger, field: str
) -> None:
    """Whichever fact it is: the writer compares the one set the origin is decided from."""
    row = _add(ledger, description="the person's row", classification=_BUSINESS)
    before = ledger.stored()

    assert field in CLASSIFICATION_DECISION_FIELDS
    assert _refused(lambda: _write(ledger, row, {field: _CHANGES[field](ledger)}, actor=_AGENT))
    assert ledger.stored() == before

    _write(ledger, row, {field: _CHANGES[field](ledger)}, actor=_PERSON)
    assert ledger.stored() != before


@pytest.mark.parametrize("values", [{"notes": "a note"}, {"group_label": "a label"}], ids=["note", "label"])
def test_an_edit_that_sets_no_tax_bearing_fact_neither_takes_a_row_nor_is_refused(
    ledger: _Ledger, values: dict[str, object]
) -> None:
    """A note or a label decides nothing about how the row is taxed, whoever writes it."""
    by_an_agent = _add(ledger, description="classified by an agent", actor=_AGENT, classification=_BUSINESS)
    by_the_person = _add(ledger, description="the person's row", classification=_BUSINESS)

    _write(ledger, by_an_agent, values, actor=_PERSON, source_command="aeat app ledger update")
    _write(ledger, by_the_person, values, actor=_AGENT, source_command="aeat app ledger update")

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


def _lifecycle(act: _SetAside, ledger: _Ledger, row: str, *, actor: str) -> None:
    act(bucket_id=_BUCKET_ID, transaction_id=row, actor=actor, reason="synthetic", ports=ledger.ports)


@_SET_ASIDES
def test_an_agents_label_sets_aside_and_restores_a_row_that_carries_none_of_the_persons_work(
    ledger: _Ledger, set_aside: _SetAside, state: TransactionLifecycleState
) -> None:
    for row in (
        _add(ledger, description="unprocessed"),
        _by_a_rule(ledger, description="classified by a rule"),
        _add(ledger, description="classified by an agent", actor=_AGENT, classification=_BUSINESS),
    ):
        _lifecycle(set_aside, ledger, row, actor=_AGENT)
        assert ledger.row(row).lifecycle_state is state
        assert ledger.row(row).lifecycle_lineage[-1].actor == _AGENT

        _lifecycle(restore_manual_transaction, ledger, row, actor=_AGENT)
        assert ledger.row(row).lifecycle_state is TransactionLifecycleState.ACTIVE


@_SET_ASIDES
def test_an_agents_label_does_not_set_aside_the_persons_row_nor_restore_what_the_person_set_aside(
    ledger: _Ledger, set_aside: _SetAside, state: TransactionLifecycleState
) -> None:
    """The row records who ran each archive, stash and restore, and the last one set the state it is in."""
    the_persons = _add(ledger, description="the person's row", classification=_BUSINESS)
    by_rule = _by_a_rule(ledger, description="classified by a rule")
    before = ledger.stored()

    assert _refused(lambda: _lifecycle(set_aside, ledger, the_persons, actor=_AGENT))
    assert ledger.stored() == before

    for row in (the_persons, by_rule):
        _lifecycle(set_aside, ledger, row, actor=_PERSON)
        assert ledger.row(row).lifecycle_state is state
    set_aside_by_the_person = ledger.stored()
    for row in (the_persons, by_rule):
        assert _refused(lambda row=row: _lifecycle(restore_manual_transaction, ledger, row, actor=_AGENT))
    assert ledger.stored() == set_aside_by_the_person

    for row in (the_persons, by_rule):
        _lifecycle(restore_manual_transaction, ledger, row, actor=_PERSON)
        assert ledger.row(row).lifecycle_state is TransactionLifecycleState.ACTIVE


def test_an_agents_label_does_not_archive_a_row_the_person_stashed_to_make_the_state_its_own(ledger: _Ledger) -> None:
    """Archiving it would record an agent as the last to set the row aside, and so let an agent restore it."""
    row = _by_a_rule(ledger, description="classified by a rule")
    _lifecycle(stash_manual_transaction, ledger, row, actor=_PERSON)
    before = ledger.stored()

    assert _refused(lambda: _lifecycle(archive_manual_transaction, ledger, row, actor=_AGENT))
    assert ledger.stored() == before

    own = _add(ledger, description="unprocessed")
    _lifecycle(stash_manual_transaction, ledger, own, actor=_AGENT)
    _lifecycle(archive_manual_transaction, ledger, own, actor=_AGENT)
    _lifecycle(restore_manual_transaction, ledger, own, actor=_AGENT)
    assert ledger.row(own).lifecycle_state is TransactionLifecycleState.ACTIVE
