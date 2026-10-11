"""Whose decision a row's classification is survives every write that does not change it.

``classified_by`` is stamped again by each write to a classified row, so it
names the last writer's mechanism. The origin is decided by one function for
every writer: it changes when a write changes the classification, its share or
a tax figure, and stands otherwise. A row stored before the origin was
recorded is read from its stamp, on the side that protects the person.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ..classification_origin import (
    CLASSIFICATION_DECISION_FIELDS,
    ClassificationOrigin,
    classification_facts,
    classification_is_the_persons,
    resolved_classification_origin,
    with_classification_origin,
    written_classification_origin,
)
from ..enums import BusinessClassification, TransactionDirection
from ..models import Transaction, TransactionCatalogue
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..service import set_classification

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("authority_operation")]

_PERSON = ClassificationOrigin.PERSON
_AGENT = ClassificationOrigin.AGENT
_AUTOMATIC = ClassificationOrigin.AUTOMATIC


def _row(
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
    *,
    classified_by: str = "auto",
    origin: ClassificationOrigin | None = None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="synthetic-origin-row",
                booked_date=date(2026, 4, 10),
                amount=Decimal("121.00"),
                currency="EUR",
                description="synthetic row",
                provenance=RawProvenance(
                    source_path=Path("synthetic-origin.csv"),
                    source_sha256="b" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(2026, 4, 14, 9, 30, tzinfo=UTC),
                    provider_name="csv",
                ),
                raw_fields={"source": "synthetic"},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": classification,
            "classified_by": classified_by,
            "classification_origin": origin,
        },
    )


@pytest.mark.parametrize(
    ("classified_by", "by_agent", "origin"),
    [
        ("manual", False, _PERSON),
        ("llm:local-text:model", False, _PERSON),
        ("derived:iva-category", False, _PERSON),
        ("manual", True, _AGENT),
        ("llm:local-text:model", True, _AGENT),
        ("derived:iva-category", True, _AGENT),
        ("rule:vendor-map", False, _AUTOMATIC),
        ("rule:vendor-map", True, _AUTOMATIC),
        ("auto", False, _AUTOMATIC),
    ],
)
def test_a_write_is_the_decision_of_whoever_ran_it_unless_a_rule_decided(
    classified_by: str, by_agent: bool, origin: ClassificationOrigin
) -> None:
    """Typing, accepting a proposal and deriving figures are the runner's act; a rule's output is nobody's."""
    assert written_classification_origin(by_agent=by_agent, classified_by=classified_by) is origin


@pytest.mark.parametrize(
    ("classified_by", "origin"),
    [
        ("manual", _PERSON),
        ("llm:local-text:model", _PERSON),
        ("derived:iva-category", _PERSON),
        ("rule:vendor-map", _AUTOMATIC),
        ("auto", _AUTOMATIC),
    ],
)
def test_a_classified_row_stored_without_an_origin_is_the_persons_unless_a_rule_or_the_pipeline_stamped_it(
    classified_by: str, origin: ClassificationOrigin
) -> None:
    """No agent could classify a row before the origin was recorded, so the stamp alone settles it."""
    stored = _row(BusinessClassification.BUSINESS, classified_by=classified_by)

    assert stored.classification_origin is None
    assert resolved_classification_origin(stored) is origin
    assert classification_is_the_persons(stored) is (origin is _PERSON)


def test_a_row_stored_before_the_origin_was_recorded_still_loads() -> None:
    """The stored form of an older row has no such member, and reads as the person's when classified by hand."""
    older = json.loads(_row(BusinessClassification.PERSONAL, classified_by="manual").model_dump_json())
    del older["classification_origin"]

    loaded = Transaction.model_validate_json(json.dumps(older))

    assert loaded.classification_origin is None
    assert classification_is_the_persons(loaded)


def test_the_recorded_origin_round_trips_through_the_stored_form() -> None:
    recorded = _row(BusinessClassification.BUSINESS, classified_by="manual", origin=_AGENT)

    assert Transaction.model_validate_json(recorded.model_dump_json()) == recorded
    assert Transaction.model_validate(recorded.model_dump(mode="python")) == recorded
    assert not classification_is_the_persons(recorded)


def test_an_unprocessed_row_is_nobodys_whatever_it_records() -> None:
    assert resolved_classification_origin(_row()) is None
    assert resolved_classification_origin(_row(origin=_PERSON)) is None
    assert not classification_is_the_persons(_row(classified_by="manual"))


def test_the_recorded_origin_wins_over_the_last_writers_stamp() -> None:
    """A later write that changes nothing of the classification leaves the hand stamp on a rule's row."""
    restamped = _row(BusinessClassification.BUSINESS, classified_by="manual", origin=_AUTOMATIC)

    assert resolved_classification_origin(restamped) is _AUTOMATIC
    assert not classification_is_the_persons(restamped)


@pytest.mark.parametrize("current_origin", [_PERSON, _AGENT, _AUTOMATIC])
@pytest.mark.parametrize("written", [_PERSON, _AGENT, _AUTOMATIC])
def test_a_write_that_sets_no_tax_bearing_fact_keeps_the_origin_it_found(
    current_origin: ClassificationOrigin, written: ClassificationOrigin
) -> None:
    """A note or a description edited by anyone decides nothing about how the row is taxed."""
    current = _row(BusinessClassification.BUSINESS, classified_by="rule:vendor-map", origin=current_origin)
    replacement = current.model_copy(update={"classified_by": "manual", "notes": "an unrelated edit"})

    stamped = with_classification_origin(replacement, replaces=current, written=written, decided=False)

    assert classification_facts(stamped) == classification_facts(current)
    assert stamped.classification_origin is current_origin


@pytest.mark.parametrize("current_origin", [_PERSON, _AGENT, _AUTOMATIC])
def test_a_person_restating_what_the_row_carries_accepts_it_and_the_row_becomes_theirs(
    current_origin: ClassificationOrigin,
) -> None:
    current = _row(BusinessClassification.BUSINESS, classified_by="rule:vendor-map", origin=current_origin)
    restated = current.model_copy(update={"classified_by": "manual"})

    stamped = with_classification_origin(restated, replaces=current, written=_PERSON, decided=True)

    assert classification_facts(stamped) == classification_facts(current)
    assert stamped.classification_origin is _PERSON


@pytest.mark.parametrize("current_origin", [_PERSON, _AGENT, _AUTOMATIC])
@pytest.mark.parametrize("written", [_AGENT, _AUTOMATIC])
def test_an_agent_or_a_rule_restating_what_the_row_carries_takes_nothing(
    current_origin: ClassificationOrigin, written: ClassificationOrigin
) -> None:
    """Otherwise an agent would take the person's row by submitting the classification it already has."""
    current = _row(BusinessClassification.BUSINESS, classified_by="manual", origin=current_origin)

    stamped = with_classification_origin(current, replaces=current, written=written, decided=True)

    assert stamped.classification_origin is current_origin


def test_a_write_that_changes_nothing_records_the_origin_an_older_row_was_read_as() -> None:
    """The stamp is about to be replaced, so the reading it gave is recorded while it can still be made."""
    older = _row(BusinessClassification.BUSINESS, classified_by="rule:vendor-map")
    replacement = older.model_copy(update={"classified_by": "manual"})

    stamped = with_classification_origin(replacement, replaces=older, written=_AGENT, decided=True)

    assert stamped.classification_origin is _AUTOMATIC


@pytest.mark.parametrize(
    "change",
    [
        {"business_classification": BusinessClassification.PERSONAL},
        {"category_id": "material_oficina"},
        {"iva_rate": Decimal("0.21"), "taxable_base": Decimal("100.00"), "iva_amount": Decimal("21.00")},
        {"recargo_amount": Decimal("5.20")},
        {"irpf_category": "synthetic-category"},
        {"counterparty_country": "DE"},
        {"counterparty_identification_state": "DE"},
        {"deduction_fact_kind": "synthetic-kind"},
        {"investment_asset_id": "synthetic-asset"},
        {"m210_income_classification": "synthetic-m210"},
        {"source_jurisdiction": "FR"},
        {"direction": TransactionDirection.INCOMING},
        {"prorrata_sector_id": "synthetic-sector"},
    ],
    ids=[
        "classification",
        "category",
        "iva-figures",
        "recargo",
        "irpf-category",
        "counterparty-country",
        "identification-state",
        "deduction-kind",
        "investment-asset",
        "m210",
        "source-jurisdiction",
        "direction",
        "prorrata-sector",
    ],
)
@pytest.mark.parametrize("written", [_PERSON, _AGENT, _AUTOMATIC])
@pytest.mark.parametrize("decided", [False, True])
def test_a_write_that_changes_a_tax_bearing_fact_records_who_wrote_it(
    change: dict[str, object], written: ClassificationOrigin, decided: bool
) -> None:
    current = _row(BusinessClassification.BUSINESS, classified_by="rule:vendor-map", origin=_AUTOMATIC)
    replacement = current.model_copy(update=change)

    stamped = with_classification_origin(replacement, replaces=current, written=written, decided=decided)

    assert set(change) <= CLASSIFICATION_DECISION_FIELDS
    assert stamped.classification_origin is written


def test_a_change_to_the_movements_money_or_date_is_a_change_to_a_tax_bearing_fact() -> None:
    """The amount and the dates live on the raw movement, and decide the base and the period all the same."""
    current = _row(BusinessClassification.BUSINESS, classified_by="rule:vendor-map", origin=_AUTOMATIC)
    for change in ({"amount": Decimal("242.00")}, {"booked_date": date(2026, 7, 1)}, {"currency": "USD"}):
        moved = current.model_copy(update={"raw": current.raw.model_copy(update=change)})
        stamped = with_classification_origin(moved, replaces=current, written=_PERSON, decided=False)
        assert set(change) <= CLASSIFICATION_DECISION_FIELDS
        assert stamped.classification_origin is _PERSON, change


def test_every_decision_field_is_read_from_the_row() -> None:
    """A name the row does not carry would compare nothing and let a change through unseen."""
    row = _row(BusinessClassification.BUSINESS)

    assert len(classification_facts(row)) == len(CLASSIFICATION_DECISION_FIELDS)
    for field in CLASSIFICATION_DECISION_FIELDS:
        assert field in Transaction.model_fields or field in type(row.raw).model_fields, field


def test_a_first_classification_records_who_wrote_it_and_a_row_left_unprocessed_records_nobody() -> None:
    unprocessed = _row()
    classified = unprocessed.model_copy(update={"business_classification": BusinessClassification.BUSINESS})

    def origin(
        replacement: Transaction, replaces: Transaction | None, written: ClassificationOrigin
    ) -> ClassificationOrigin | None:
        stamped = with_classification_origin(replacement, replaces=replaces, written=written, decided=True)
        return stamped.classification_origin

    assert origin(classified, unprocessed, _AGENT) is _AGENT
    assert origin(classified, None, _PERSON) is _PERSON
    assert origin(unprocessed, None, _PERSON) is None
    returned = _row(BusinessClassification.BUSINESS, classified_by="manual", origin=_PERSON).model_copy(
        update={"business_classification": BusinessClassification.NOT_YET_PROCESSED}
    )
    assert origin(returned, classified, _AGENT) is None


def test_the_domain_write_records_who_accepted_and_only_a_person_takes_a_row_by_restating_it() -> None:
    """The one caller of this write applies an accepted proposal, and names who accepted it."""
    row = _row()
    catalogue = TransactionCatalogue.from_transactions((row,))

    accepted = set_classification(
        catalogue,
        row.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="llm:local-text:model",
        origin=_PERSON,
        confidence=Decimal("0.9"),
    )
    again = set_classification(
        accepted,
        row.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="llm:local-text:model",
        origin=_AGENT,
        confidence=Decimal("0.9"),
    )
    changed = set_classification(
        again,
        row.transaction_id,
        classification=BusinessClassification.PERSONAL,
        classified_by="llm:local-text:model",
        origin=_AGENT,
        confidence=Decimal("0.9"),
    )

    confirmed = set_classification(
        changed,
        row.transaction_id,
        classification=BusinessClassification.PERSONAL,
        classified_by="llm:local-text:model",
        origin=_PERSON,
        confidence=Decimal("0.9"),
    )

    assert accepted.transactions[row.transaction_id].classification_origin is _PERSON
    assert again.transactions[row.transaction_id].classification_origin is _PERSON
    assert changed.transactions[row.transaction_id].classification_origin is _AGENT
    assert confirmed.transactions[row.transaction_id].classification_origin is _PERSON
