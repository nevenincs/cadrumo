"""Staged ledger work answered through the real writers' contracts and domain owners."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.classification_effects import fields_cleared_by_classification, takes_expense_category
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import Transaction, derive_transaction_id
from ..actions_manual import transaction_from_command
from ..classify_requests import LedgerClassifyPatch, LedgerClassifyRequest
from ..manual_update import command_from_patch
from ..models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from ..staged_check import check_draft, check_staged_work, check_stored_row, route_for_cell
from ..staged_check_contracts import (
    LedgerStagedCell,
    LedgerStagedCheckRequest,
    LedgerStagedDraft,
    LedgerStagedDraftField,
    LedgerStagedRow,
    LedgerStagedRowAnswer,
)
from ..update_contracts import LedgerUpdatePatch, LedgerUpdateRequest

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_NOW = datetime(_YEAR, 3, 2, 10, tzinfo=UTC)


def _stored(
    *,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
    business_pct: Decimal | None = None,
    category_id: str | None = None,
    evidence: str | None = None,
) -> Transaction:
    built = transaction_from_command(
        ManualLedgerTransactionCommand(
            bucket_id=str(uuid4()),
            booked_date=date(_YEAR, 3, 2),
            amount=Decimal("36.30"),
            currency="EUR",
            direction=direction,
            description="SUMINISTRO",
            business_classification=classification,
            business_pct=business_pct,
            category_id=category_id,
            actor="operator",
            source_command="test",
        ),
        occurred_at=_NOW,
    )
    return built if evidence is None else built.model_copy(update={"purchase_invoice_evidence_id": evidence})


def _row(*cells: tuple[str, str | None], evidence_staged: bool = False, m210: bool = False) -> LedgerStagedRow:
    return LedgerStagedRow(
        transaction_id="a" * 64,
        cells=tuple(LedgerStagedCell.model_validate({"field": field, "value": value}) for field, value in cells),
        evidence_staged=evidence_staged,
        m210_staged=m210,
    )


def _route_of(field: str, *, clear: bool = False, classified: bool = True) -> str | None:
    route, refused = route_for_cell(field=field, clear=clear, classified=classified)
    return route or refused


@pytest.mark.parametrize(
    ("field", "clear", "classified", "expected"),
    [
        # Only an update takes a booked date; it replaces it and never blanks it.
        ("booked_date", False, True, "update"),
        ("booked_date", True, True, "cannot_clear"),
        ("value_date", True, True, "update"),
        # A devengo date is an update's alone, and a blank clears it back to the fallback.
        ("operation_date", False, True, "update"),
        ("operation_date", True, True, "update"),
        ("operation_date", False, False, "update"),
        # A stated Renta accrual date is an update's alone, and a blank clears it.
        ("accrual_date", False, True, "update"),
        ("accrual_date", True, True, "update"),
        ("accrual_date", False, False, "update"),
        # The bulk takes a set on a classified row and never carries a clear.
        ("category_id", False, True, "bulk"),
        ("category_id", True, True, "classify"),
        ("category_id", False, False, "needs_classification"),
        # A tax figure on a row with no classification goes through the update.
        ("taxable_base", False, False, "update"),
        ("taxable_base", True, True, "update"),
        # Nothing clears a usage ratio or a classification.
        ("usage_ratio_id", True, True, "cannot_clear"),
        ("usage_ratio_id", False, True, "bulk"),
        ("business_classification", True, True, "cannot_clear"),
        ("notes", True, True, "cannot_clear"),
        ("notes", False, False, "update"),
        ("deduction_fact_kind", False, True, "classify"),
        ("deduction_fact_kind", True, True, "classify"),
        ("deduction_fact_kind", False, False, "needs_classification"),
    ],
)
def test_a_cell_goes_to_the_write_that_accepts_it(field: str, clear: bool, classified: bool, expected: str) -> None:
    assert _route_of(field, clear=clear, classified=classified) == expected


def test_what_the_routes_say_a_write_cannot_clear_is_what_that_write_refuses() -> None:
    profile = uuid4()
    with pytest.raises(ValidationError):
        LedgerUpdateRequest.model_validate(
            {
                "profile_id": profile,
                "transaction_id": "a",
                "patch": LedgerUpdatePatch(),
                "patch_fields": ("booked_date",),
            }
        )
    with pytest.raises(ValidationError):
        LedgerClassifyRequest.model_validate(
            {
                "profile_id": profile,
                "transaction_id": "a",
                "patch": LedgerClassifyPatch(),
                "patch_fields": ("business_classification",),
            }
        )
    with pytest.raises(TransactionValidationError):
        command_from_patch(
            bucket_id=str(profile),
            current=_stored(),
            patch=ManualLedgerTransactionPatch.model_validate({"notes": None}),
            actor="operator",
            source_command="test",
        )


@pytest.mark.parametrize(
    ("classification", "expected"),
    [
        (BusinessClassification.MIXED, frozenset()),
        (BusinessClassification.BUSINESS, frozenset({"business_pct", "usage_ratio_id"})),
    ],
)
def test_what_a_classification_clears_on_a_bearing_row(
    classification: BusinessClassification, expected: frozenset[str]
) -> None:
    assert fields_cleared_by_classification(classification) == expected


def test_the_writer_drops_what_the_owner_says_a_personal_classification_clears() -> None:
    stored = _stored(
        classification=BusinessClassification.MIXED, business_pct=Decimal("0.5"), category_id="office_supplies"
    )
    command = command_from_patch(
        bucket_id=str(uuid4()),
        current=stored,
        patch=ManualLedgerTransactionPatch.model_validate({"business_classification": BusinessClassification.PERSONAL}),
        actor="operator",
        source_command="test",
    )
    cleared = fields_cleared_by_classification(BusinessClassification.PERSONAL)
    assert {"business_pct", "category_id", "taxable_base", "iva_amount", "recargo_amount"} <= cleared
    assert command.business_pct is None
    assert command.category_id is None


def test_a_clear_the_classification_performs_travels_with_its_write() -> None:
    stored = _stored(
        classification=BusinessClassification.MIXED, business_pct=Decimal("0.5"), category_id="office_supplies"
    )
    answer = check_stored_row(
        _row(("business_classification", "PERSONAL"), ("business_pct", None), ("usage_ratio_id", None)), stored
    )
    assert {route.field: route.route for route in answer.routes} == {
        "business_classification": "bulk",
        "business_pct": "bulk",
        "usage_ratio_id": "bulk",
    }
    assert answer.blockers == ()


@pytest.mark.parametrize(
    ("direction", "evidence", "evidence_staged", "expected"),
    [
        (TransactionDirection.OUTGOING, None, False, True),
        (TransactionDirection.INCOMING, None, False, False),
        (TransactionDirection.INCOMING, "e" * 64, False, True),
        (TransactionDirection.INCOMING, None, True, True),
        (TransactionDirection.INTERNAL_TRANSFER, None, False, False),
    ],
)
def test_who_takes_a_spending_category(
    direction: TransactionDirection, evidence: str | None, evidence_staged: bool, expected: bool
) -> None:
    answer = check_stored_row(_row(evidence_staged=evidence_staged), _stored(direction=direction, evidence=evidence))
    assert answer.takes_expense_category is expected
    assert takes_expense_category(direction, has_purchase_evidence=bool(evidence) or evidence_staged) is expected


def test_a_staged_direction_decides_who_takes_a_category() -> None:
    income = _stored(direction=TransactionDirection.INCOMING)
    assert check_stored_row(_row(("direction", "OUTGOING")), income).takes_expense_category is True


@pytest.mark.parametrize(
    ("direction", "expected", "missing"),
    [
        ("INCOMING", False, ("description",)),
        ("OUTGOING", True, ("description",)),
        ("INTERNAL_TRANSFER", False, ("description",)),
        (None, False, ("direction", "description")),
        ("UNKNOWN", False, ("description",)),
    ],
)
def test_draft_category_projection_uses_direction_and_preserves_blockers(
    direction: str | None, expected: bool, missing: tuple[str, ...]
) -> None:
    fields = {"booked_date": date(_YEAR, 3, 2).isoformat(), "amount": "10", "currency": "EUR"}
    if direction is not None:
        fields["direction"] = direction
    draft = LedgerStagedDraft(
        key="draft",
        fields=tuple(
            LedgerStagedDraftField.model_validate({"field": key, "value": value}) for key, value in fields.items()
        ),
    )
    answer = check_draft(draft)
    assert answer.key == "draft"
    assert answer.takes_expense_category is expected
    assert [(blocker.kind, blocker.fields) for blocker in answer.blockers] == [("draft_incomplete", missing)]


def test_mixed_needs_its_share_and_only_mixed_takes_one() -> None:
    plain = _stored(classification=BusinessClassification.BUSINESS)
    needs = check_stored_row(_row(("business_classification", "MIXED")), plain)
    assert [blocker.kind for blocker in needs.blockers] == ["mixed_needs_share"]
    stray = check_stored_row(_row(("business_pct", "0.5")), plain)
    assert "share_needs_mixed" in [blocker.kind for blocker in stray.blockers]
    mixed = _stored(classification=BusinessClassification.MIXED, business_pct=Decimal("0.5"))
    sends = check_stored_row(_row(("category_id", "office_supplies")), mixed)
    assert sends.blockers == ()
    assert [(note.kind, note.value) for note in sends.notes] == [
        ("sends_current_share", "0.5"),
        ("sends_current_classification", "MIXED"),
    ]


def test_a_transfer_is_held_back_for_each_tax_field_it_carries() -> None:
    answer = check_stored_row(
        _row(("direction", "INTERNAL_TRANSFER")),
        _stored(classification=BusinessClassification.BUSINESS, category_id="office_supplies"),
    )
    held = next(blocker for blocker in answer.blockers if blocker.kind == "transfer_with_tax")
    assert held.fields == ("business_classification", "category_id")
    plain = check_stored_row(_row(("direction", "INTERNAL_TRANSFER")), _stored())
    assert [blocker.kind for blocker in plain.blockers] == []
    assert "category_id" in plain.transfer_locked_fields
    assert "business_pct" in plain.transfer_locked_fields
    assert plain.tax_set_skip == "transfer"


def test_an_accrual_date_is_read_back_held_back_on_a_transfer_and_needs_no_classification() -> None:
    staged = check_stored_row(_row(("accrual_date", date(_YEAR, 3, 30).isoformat())), _stored())
    assert staged.blockers == ()
    assert staged.classifying_fields == ()
    held = check_stored_row(
        _row(("direction", "INTERNAL_TRANSFER"), ("accrual_date", date(_YEAR, 3, 30).isoformat())),
        _stored(),
    )
    assert next(blocker for blocker in held.blockers if blocker.kind == "transfer_with_tax").fields == ("accrual_date",)
    assert "accrual_date" in held.transfer_locked_fields


def test_an_operation_date_is_read_back_held_back_on_a_transfer_and_needs_no_classification() -> None:
    staged = check_stored_row(_row(("operation_date", date(_YEAR, 3, 30).isoformat())), _stored())
    assert staged.blockers == ()
    assert staged.classifying_fields == ()
    held = check_stored_row(
        _row(("direction", "INTERNAL_TRANSFER"), ("operation_date", date(_YEAR, 3, 30).isoformat())),
        _stored(),
    )
    assert next(blocker for blocker in held.blockers if blocker.kind == "transfer_with_tax").fields == (
        "operation_date",
    )
    assert "operation_date" in held.transfer_locked_fields


def test_the_writer_refuses_the_core_of_what_a_transfer_is_held_back_for() -> None:
    bucket = str(uuid4())
    base = {
        "bucket_id": bucket,
        "booked_date": date(_YEAR, 3, 2),
        "amount": Decimal("10"),
        "currency": "EUR",
        "direction": TransactionDirection.INTERNAL_TRANSFER,
        "description": "TRASPASO",
        "business_classification": BusinessClassification.NOT_YET_PROCESSED,
        "actor": "operator",
        "source_command": "test",
    }
    with pytest.raises(ValidationError, match="must not carry tax"):
        ManualLedgerTransactionCommand.model_validate({**base, "category_id": "office_supplies"})
    with pytest.raises(ValidationError, match="must not be classified"):
        ManualLedgerTransactionCommand.model_validate(
            {**base, "business_classification": BusinessClassification.BUSINESS}
        )


@pytest.mark.parametrize(
    ("cells", "expected"),
    [
        ((("amount", "36.3"),), ()),
        ((("amount", "40"),), ("amount",)),
        ((("description", "OTRA"),), ("description",)),
        ((("value_date", date(_YEAR, 3, 2).isoformat()),), ()),
        ((("value_date", date(_YEAR, 3, 3).isoformat()),), ("value_date",)),
        ((("booked_date", date(_YEAR, 3, 9).isoformat()),), ("booked_date",)),
        ((("own_account_id", "acc-02"),), ("own_account_id",)),
        ((("notes", "x"),), ()),
    ],
)
def test_what_gives_a_movement_a_new_id(cells: tuple[tuple[str, str], ...], expected: tuple[str, ...]) -> None:
    assert check_stored_row(_row(*cells), _stored()).identity_fields == expected


def test_each_identity_verdict_matches_the_id_the_owner_derives() -> None:
    raw = _stored().raw
    before = derive_transaction_id(raw)
    changed = raw.model_copy(update={"amount": Decimal("40")})
    assert derive_transaction_id(changed) != before
    same = raw.model_copy(update={"amount": Decimal("36.3")})
    assert derive_transaction_id(same) == before
    dated = raw.model_copy(update={"value_date": date(_YEAR, 3, 2)})
    assert derive_transaction_id(dated) == before


def test_a_draft_names_what_it_lacks_and_what_a_transfer_cannot_carry() -> None:
    bare = check_draft(LedgerStagedDraft(key="d"))
    assert bare.blockers[0].kind == "draft_incomplete"
    assert bare.blockers[0].fields == ("booked_date", "amount", "currency", "direction", "description")
    fields = {
        "booked_date": date(_YEAR, 3, 2).isoformat(),
        "amount": "10",
        "currency": "EUR",
        "direction": "INTERNAL_TRANSFER",
        "description": "T",
        "business_classification": "BUSINESS",
        "recargo_amount": "1",
    }
    draft = LedgerStagedDraft(
        key="d",
        fields=tuple(LedgerStagedDraftField.model_validate({"field": k, "value": v}) for k, v in fields.items()),
    )
    answer = check_draft(draft)
    assert [(blocker.kind, blocker.fields) for blocker in answer.blockers] == [
        ("transfer_with_tax", ("business_classification", "recargo_amount"))
    ]


def test_an_unknown_movement_is_answered_as_not_found_and_categories_fit_by_the_registry(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    profile = uuid4()
    request = LedgerStagedCheckRequest(profile_id=profile, rows=(_row(),), categories=("no-such-category",))
    result = check_staged_work(request, {}, operation=authority_operation, profile_id=profile)
    assert result.rows[0].found is False
    assert (result.categories[0].business, result.categories[0].mixed) == (False, False)
    assert len(result.input_digest) == 64


def test_a_stored_row_says_what_it_takes_from_its_own_codes() -> None:
    profile_row = _row()
    plain = check_stored_row(profile_row, _stored(classification=BusinessClassification.BUSINESS, category_id="x"))
    assert (plain.takes_changes, plain.takes_invoice, plain.evidence_advised) == (True, True, True)
    assert plain.lifecycle_actions == ("archive", "stash", "exclude")

    held = check_stored_row(
        profile_row, _stored(classification=BusinessClassification.BUSINESS, category_id="x", evidence="e" * 64)
    )
    assert held.evidence_advised is False

    archived = _stored().model_copy(update={"lifecycle_state": TransactionLifecycleState.ARCHIVED})
    answer = check_stored_row(profile_row, archived)
    assert (answer.takes_changes, answer.evidence_advised) == (False, False)
    assert answer.lifecycle_actions == ("restore",)

    transfer = check_stored_row(profile_row, _stored(direction=TransactionDirection.INTERNAL_TRANSFER))
    assert transfer.takes_invoice is False


def test_an_unknown_movement_takes_nothing_until_the_ledger_finds_it() -> None:
    absent = LedgerStagedRowAnswer(transaction_id="a" * 64, found=False)
    assert (absent.takes_changes, absent.takes_invoice, absent.evidence_advised) == (False, False, False)
    assert absent.lifecycle_actions == ()
