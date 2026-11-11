"""The staged answer about a movement is what its real writer does with the same facts.

Each case runs ``command_from_patch``, the merge every update goes through, or the
writer behind the door, next to ``check_stored_row``: the window is told a row is
held back exactly when the writer would refuse it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ....core.iva_deduction_fact import IvaDeductionFactKind
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.classification_effects import lifecycle_actions_taken
from ....domain.transactions.classification_rule import require_new_rule_decision
from ....domain.transactions.enums import (
    RULE_CATEGORY_STATES,
    RULE_DECIDED_STATES,
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....domain.transactions.errors import ClassificationRuleError
from ....domain.transactions.models import Transaction
from ..actions_manual import transaction_from_command
from ..manual_update import command_from_patch
from ..models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from ..staged_check import TRANSFER_LOCKED_FIELDS, check_draft, check_stored_row
from ..staged_check_contracts import LedgerStagedCell, LedgerStagedDraft, LedgerStagedDraftField, LedgerStagedRow

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_NOW = datetime(_YEAR, 3, 2, 10, tzinfo=UTC)
_BUCKET = str(uuid4())


def _stored(
    *,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
    **facts: object,
) -> Transaction:
    built = transaction_from_command(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET,
            booked_date=date(_YEAR, 3, 2),
            amount=Decimal("36.30"),
            currency="EUR",
            direction=direction,
            description="SUMINISTRO",
            business_classification=classification,
            actor="operator",
            source_command="test",
        ),
        occurred_at=_NOW,
    )
    return built.model_copy(update=facts)


def _row(*cells: tuple[str, str | None], **flags: bool) -> LedgerStagedRow:
    return LedgerStagedRow(
        transaction_id="a" * 64,
        cells=tuple(LedgerStagedCell.model_validate({"field": field, "value": value}) for field, value in cells),
        **flags,
    )


def _writer_takes(current: Transaction, **patch: object) -> bool:
    try:
        command_from_patch(
            bucket_id=_BUCKET,
            current=current,
            patch=ManualLedgerTransactionPatch.model_validate(patch),
            actor="operator",
            source_command="test",
        )
    except ValidationError:
        return False
    return True


def _transfer_held(answer_row: LedgerStagedRow, stored: Transaction) -> tuple[str, ...] | None:
    answer = check_stored_row(answer_row, stored)
    held = next((blocker for blocker in answer.blockers if blocker.kind == "transfer_with_tax"), None)
    return None if held is None else held.fields


_TRANSFER = TransactionDirection.INTERNAL_TRANSFER


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("iva_category", IvaCategory("domestic_general")),
        ("deduction_fact_kind", IvaDeductionFactKind.from_registry("domestic_investment")),
        ("investment_asset_id", "asset-1"),
    ],
)
def test_the_writer_refuses_a_tax_claim_on_a_transfer(field: str, value: object) -> None:
    assert _writer_takes(_stored(direction=_TRANSFER), **{field: value}) is False
    assert _writer_takes(_stored(direction=TransactionDirection.OUTGOING), **{field: value}) is True


def test_the_writer_keeps_the_counterparty_state_a_transfer_may_carry_and_the_window_follows() -> None:
    stored = _stored(direction=_TRANSFER)
    assert _writer_takes(stored, counterparty_identification_state="DE") is True
    assert _transfer_held(_row(("counterparty_identification_state", "DE")), stored) is None
    assert "counterparty_identification_state" not in TRANSFER_LOCKED_FIELDS


def test_a_stored_transfer_claim_stays_readable_and_the_next_edit_is_refused_until_it_is_cleared() -> None:
    stored = _stored(direction=_TRANSFER, investment_asset_id="asset-1")
    assert Transaction.model_validate(stored.model_dump()).investment_asset_id == "asset-1"
    assert _writer_takes(stored, notes="x") is False
    assert _transfer_held(_row(("notes", "x")), stored) == ("investment_asset_id",)
    assert _writer_takes(stored, notes="x", investment_asset_id=None) is True
    assert _transfer_held(_row(("notes", "x"), ("investment_asset_id", None)), stored) is None


@pytest.mark.parametrize(
    "facts",
    [
        {"recargo_amount": Decimal("1.00")},
        {"m210_income_classification": "dividendos"},
        {"prorrata_reference": "ref"},
        {"prorrata_sector_id": "sector-a"},
        {"purchase_invoice_evidence_id": "e" * 64},
        {"attachment_ids": ("f" * 64,)},
    ],
)
def test_what_only_a_stored_transfer_carries_holds_back_what_the_writer_would_refuse(
    facts: dict[str, object],
) -> None:
    stored = _stored(direction=_TRANSFER).model_copy(update=facts)
    assert _writer_takes(stored, notes="x") is False
    assert _transfer_held(_row(("notes", "x")), stored) == tuple(facts)
    assert _transfer_held(_row(), stored) is None


@pytest.mark.parametrize("flag", ["evidence_staged", "m210_staged"])
def test_evidence_or_m210_staged_on_a_transfer_is_held_back(flag: str) -> None:
    assert _transfer_held(_row(**{flag: True}), _stored(direction=_TRANSFER)) is not None


@pytest.mark.parametrize("classification", list(BusinessClassification))
def test_each_classification_is_held_back_on_a_transfer_exactly_when_the_writer_refuses_it(
    classification: BusinessClassification,
) -> None:
    patch: dict[str, object] = {"business_classification": classification}
    cells = [("business_classification", classification.value)]
    if classification is BusinessClassification.MIXED:
        patch["business_pct"] = Decimal("0.5")
        cells.append(("business_pct", "0.5"))
    takes = _writer_takes(_stored(direction=_TRANSFER), **patch)
    held = _transfer_held(_row(*cells), _stored(direction=_TRANSFER))
    assert (held is None) is takes


@pytest.mark.parametrize(("field", "value"), [("business_pct", "0.5"), ("usage_ratio_id", "internet")])
def test_the_share_and_its_ratio_are_locked_on_a_transfer_because_the_writer_refuses_them(
    field: str, value: str
) -> None:
    stored = _stored(direction=_TRANSFER)
    assert field in check_stored_row(_row(), stored).transfer_locked_fields
    assert _writer_takes(stored, **{field: Decimal(value) if field == "business_pct" else value}) is False


def test_stored_investment_facts_reach_the_window() -> None:
    stored = _stored(
        classification=BusinessClassification.BUSINESS,
        deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_investment"),
        investment_asset_id="asset-1",
    )
    answer = check_stored_row(_row(("direction", _TRANSFER.value)), stored)
    held = next(blocker for blocker in answer.blockers if blocker.kind == "transfer_with_tax")
    assert held.fields == ("business_classification", "deduction_fact_kind", "investment_asset_id")


def test_restating_the_account_or_padding_the_description_gives_no_new_identity() -> None:
    stored = _stored(own_account_id="acc-1")
    assert check_stored_row(_row(("own_account_id", "acc-1")), stored).identity_fields == ()
    assert check_stored_row(_row(("own_account_id", "acc-2")), stored).identity_fields == ("own_account_id",)
    assert check_stored_row(_row(("own_account_id", None)), stored).identity_fields == ("own_account_id",)
    assert check_stored_row(_row(("description", "  SUMINISTRO ")), stored).identity_fields == ()
    padded = command_from_patch(
        bucket_id=_BUCKET,
        current=stored,
        patch=ManualLedgerTransactionPatch.model_validate({"description": "  SUMINISTRO "}),
        actor="operator",
        source_command="test",
    )
    assert padded.description == "SUMINISTRO"


def test_a_category_is_settable_on_the_classification_staged_not_the_one_stored() -> None:
    unclassified = _stored()
    assert check_stored_row(_row(), unclassified).category_settable is False
    assert check_stored_row(_row(("business_classification", "BUSINESS")), unclassified).category_settable is True
    business = _stored(classification=BusinessClassification.BUSINESS)
    assert check_stored_row(_row(), business).category_settable is True
    assert check_stored_row(_row(("business_classification", "PERSONAL")), business).category_settable is False
    archived = business.model_copy(update={"lifecycle_state": TransactionLifecycleState.ARCHIVED})
    assert check_stored_row(_row(), archived).category_settable is False


def test_a_row_is_asked_for_a_category_as_it_will_be_saved_and_income_is_asked_but_not_set() -> None:
    unclassified = _stored()
    assert check_stored_row(_row(), unclassified).category_askable is False
    assert check_stored_row(_row(("business_classification", "BUSINESS")), unclassified).category_askable is True
    business = _stored(classification=BusinessClassification.BUSINESS)
    assert check_stored_row(_row(("business_classification", "PERSONAL")), business).category_askable is False
    archived = business.model_copy(update={"lifecycle_state": TransactionLifecycleState.ARCHIVED})
    assert check_stored_row(_row(), archived).category_askable is False
    income = _stored(direction=TransactionDirection.INCOMING, classification=BusinessClassification.BUSINESS)
    answer = check_stored_row(_row(), income)
    assert (answer.category_askable, answer.category_settable) == (True, False)


def test_a_set_for_all_skips_personal_for_what_its_write_drops_and_no_longer_skips_the_unclassified() -> None:
    personal = _stored(classification=BusinessClassification.PERSONAL)
    assert check_stored_row(_row(), personal).tax_set_skip == "personal"
    assert check_stored_row(_row(), _stored()).tax_set_skip is None
    assert _writer_takes(_stored(), category_id="office_supplies", iva_category=IvaCategory("domestic_general"))
    dropped = command_from_patch(
        bucket_id=_BUCKET,
        current=personal,
        patch=ManualLedgerTransactionPatch.model_validate(
            {
                "business_classification": BusinessClassification.PERSONAL,
                "category_id": "office_supplies",
                "iva_category": IvaCategory("domestic_general"),
            }
        ),
        actor="operator",
        source_command="test",
    )
    assert dropped.category_id is None
    assert dropped.iva_category == IvaCategory("domestic_general")


def test_a_draft_transfer_is_held_for_what_the_writer_refuses_and_not_for_the_counterparty_state() -> None:
    def blockers(**fields: str) -> list[tuple[str, tuple[str, ...]]]:
        base = {
            "booked_date": date(_YEAR, 3, 2).isoformat(),
            "amount": "10",
            "currency": "EUR",
            "direction": _TRANSFER.value,
            "description": "T",
            "business_classification": "NOT_YET_PROCESSED",
        }
        items = tuple(
            LedgerStagedDraftField.model_validate({"field": k, "value": v}) for k, v in {**base, **fields}.items()
        )
        return [(b.kind, b.fields) for b in check_draft(LedgerStagedDraft(key="d", fields=items)).blockers]

    assert blockers(counterparty_identification_state="DE") == []
    assert blockers(investment_asset_id="a") == [("transfer_with_tax", ("investment_asset_id",))]
    assert blockers(business_classification="REVIEWED_EXCLUDED") == [
        ("transfer_with_tax", ("business_classification",))
    ]


def test_a_stashed_row_is_offered_archive_because_the_lifecycle_writer_takes_it() -> None:
    assert lifecycle_actions_taken(TransactionLifecycleState.STASHED, BusinessClassification.BUSINESS) == (
        "restore",
        "archive",
    )
    assert lifecycle_actions_taken(TransactionLifecycleState.ARCHIVED, BusinessClassification.BUSINESS) == ("restore",)


@pytest.mark.parametrize("classification", list(BusinessClassification))
def test_a_new_rule_decides_only_what_a_classification_write_can_carry_out(
    classification: BusinessClassification,
) -> None:
    if classification in RULE_DECIDED_STATES:
        require_new_rule_decision(classification, None)
    else:
        with pytest.raises(ClassificationRuleError):
            require_new_rule_decision(classification, None)
    if classification in RULE_CATEGORY_STATES:
        require_new_rule_decision(classification, "office_supplies")
    else:
        with pytest.raises(ClassificationRuleError):
            require_new_rule_decision(classification, "office_supplies")
