"""Answer staged ledger work the way the writers would take it.

A frontend staging several cells needs to know, before anything is sent, which
registered write takes each cell, what the staged state of the row would refuse,
and what it would change about the row's identity. Those are the writers' and the
domain's rules, so every frontend asks here. Nothing is written or cached; a write
still checks itself against the row it finds.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Final
from uuid import UUID

from ...core.hashing import content_hash_hex
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.categories.spending_category_catalogue import resolve_spending_category_catalogue
from ...domain.transactions.classification_effects import fields_cleared_by_classification, takes_expense_category
from ...domain.transactions.enums import (
    BUSINESS_BEARING_STATES,
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
    is_classified,
    takes_business_share,
)
from ...domain.transactions.models import Transaction
from ...domain.usage_ratios.model import eligible_usage_ratio_categories
from .actions_common import display_decimal
from .classify_requests import CLASSIFY_FIELD_NAMES, CLASSIFY_UNCLEARABLE_FIELD_NAMES
from .models import BULK_CLASSIFY_ALLOWED_COLUMNS
from .staged_check_contracts import (
    LedgerStagedBlocker,
    LedgerStagedCategoryFit,
    LedgerStagedCheckRequest,
    LedgerStagedCheckResult,
    LedgerStagedDraft,
    LedgerStagedDraftAnswer,
    LedgerStagedNote,
    LedgerStagedRoute,
    LedgerStagedRow,
    LedgerStagedRowAnswer,
    RouteRefusal,
    StageFieldName,
    TaxSetSkip,
    WriteRoute,
)
from .update_contracts import LEDGER_UPDATE_FIELD_NAMES, LEDGER_UPDATE_REQUIRED_FIELD_NAMES

_BULK_COLUMN_OF_FIELD: Final = {"business_classification": "classification"}

TRANSFER_TAX_FIELDS: Final[tuple[StageFieldName, ...]] = (
    "business_pct",
    "category_id",
    "usage_ratio_id",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "iva_category",
    "irpf_category",
    "deduction_fact_kind",
    "investment_asset_id",
    "counterparty_identification_state",
)
"""What a transfer's staged work is held back for carrying.

Wider than the writer's own refusal: ``iva_category``, ``deduction_fact_kind``,
``investment_asset_id`` and ``counterparty_identification_state`` are accepted on
a transfer by ``ManualLedgerTransactionCommand``. This check keeps them held back.
"""

_DRAFT_TRANSFER_TAX_FIELDS: Final[tuple[str, ...]] = (
    "business_pct",
    "category_id",
    "usage_ratio_id",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "iva_category",
    "irpf_category",
    "recargo_amount",
    "deduction_fact_kind",
    "investment_asset_id",
    "counterparty_identification_state",
)

_TRANSFER_LOCKED_FIELDS: Final[tuple[StageFieldName, ...]] = (
    "category_id",
    "iva_category",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "irpf_category",
    "deduction_fact_kind",
    "investment_asset_id",
    "counterparty_identification_state",
)
"""What cannot be edited on a transfer: the transfer's tax fields, less the share and its ratio."""

_CLASSIFYING_FIELDS: Final[frozenset[str]] = frozenset(
    {*TRANSFER_TAX_FIELDS, "business_classification", "counterparty_country"}
)

_DRAFT_REQUIRED_FIELDS: Final = ("booked_date", "amount", "currency", "direction", "description")

# The read of a movement does not carry these two, so only a staged one is judged.
_STAGE_ONLY_FIELDS: Final = frozenset({"deduction_fact_kind", "investment_asset_id"})


def route_for_cell(*, field: str, clear: bool, classified: bool) -> tuple[WriteRoute | None, RouteRefusal | None]:
    """Choose the write that takes one cell, from what each registered write accepts.

    A clear, a field only an update takes, and a tax figure on a row with no
    classification all go through the update's field mask. The bulk never carries
    a clear: a blank cell there means unchanged.
    """
    bulk = _BULK_COLUMN_OF_FIELD.get(field, field) in BULK_CLASSIFY_ALLOWED_COLUMNS
    classify = field in CLASSIFY_FIELD_NAMES and not (clear and field in CLASSIFY_UNCLEARABLE_FIELD_NAMES)
    update = field in LEDGER_UPDATE_FIELD_NAMES and not (clear and field in LEDGER_UPDATE_REQUIRED_FIELD_NAMES)
    update_only = not bulk and not classify and update
    if update and (update_only or clear or not classified):
        return "update", None
    if not clear and bulk and classified:
        return "bulk", None
    if classify and classified:
        return "classify", None
    if classify or (not clear and bulk):
        return None, "needs_classification"
    return None, "cannot_clear"


def _filled(value: str | None) -> bool:
    return value is not None and value != ""


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else display_decimal(value)


def _stored_facts(transaction: Transaction) -> dict[str, str | None]:
    raw = transaction.raw
    return {
        "booked_date": raw.booked_date.isoformat(),
        "value_date": None if raw.value_date is None else raw.value_date.isoformat(),
        "amount": display_decimal(raw.amount),
        "direction": transaction.direction.value,
        "currency": raw.currency,
        "counterparty": raw.counterparty or None,
        "description": raw.description,
        "group_label": transaction.group_label,
        "own_account_id": transaction.own_account_id,
        "business_classification": transaction.business_classification.value,
        "business_pct": _decimal_text(transaction.business_pct),
        "category_id": transaction.category_id,
        "usage_ratio_id": transaction.usage_ratio_id,
        "taxable_base": _decimal_text(transaction.taxable_base),
        "iva_rate": _decimal_text(transaction.iva_rate),
        "iva_amount": _decimal_text(transaction.iva_amount),
        "iva_category": None if transaction.iva_category is None else str(transaction.iva_category),
        "irpf_category": transaction.irpf_category,
        "notes": transaction.notes or None,
        "deduction_fact_kind": None,
        "investment_asset_id": None,
        "counterparty_country": transaction.counterparty_country,
        "counterparty_identification_state": (
            None
            if transaction.counterparty_identification_state is None
            else str(transaction.counterparty_identification_state)
        ),
    }


def _same_amount(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return left is right
    try:
        return Decimal(left) == Decimal(right)
    except InvalidOperation:
        return left == right


def _identity_fields(
    row: LedgerStagedRow, before: dict[str, str | None], after: dict[str, str | None]
) -> tuple[StageFieldName, ...]:
    """Name the staged fields that give the row a new id: what ``derive_transaction_id`` hashes."""
    staged = {cell.field for cell in row.cells}
    found: list[StageFieldName] = []
    if "amount" in staged and not _same_amount(after["amount"], before["amount"]):
        found.append("amount")
    if "description" in staged and after["description"] != before["description"]:
        found.append("description")
    effective_before = before["value_date"] or before["booked_date"]
    effective_after = after["value_date"] or after["booked_date"]
    if staged & {"booked_date", "value_date"} and effective_after != effective_before:
        found.append("value_date" if "value_date" in staged else "booked_date")
    if "own_account_id" in staged:
        found.append("own_account_id")
    return tuple(found)


def _classification(value: str | None) -> BusinessClassification | None:
    if value is None:
        return None
    try:
        return BusinessClassification(value)
    except ValueError:
        return None


def _direction(value: str | None) -> TransactionDirection | None:
    if value is None:
        return None
    try:
        return TransactionDirection(value)
    except ValueError:
        return None


def _tax_set_skip(
    direction: TransactionDirection | None, classification: BusinessClassification | None
) -> TaxSetSkip | None:
    if direction is TransactionDirection.INTERNAL_TRANSFER:
        return "transfer"
    if classification is BusinessClassification.PERSONAL:
        return "personal"
    if classification not in BUSINESS_BEARING_STATES:
        return "unclassified"
    return None


def _routes_of_row(
    row: LedgerStagedRow, classified: bool
) -> tuple[tuple[LedgerStagedRoute, ...], WriteRoute | None, list[str], list[str]]:
    """Route each cell; a clear the classification's own write performs travels with that write."""
    chosen = next((cell for cell in row.cells if cell.field == "business_classification"), None)
    carrier: WriteRoute | None = None
    carried = frozenset[str]()
    if chosen is not None and chosen.value is not None:
        carrier, _ = route_for_cell(field=chosen.field, clear=False, classified=classified)
        chosen_state = _classification(chosen.value)
        if carrier is not None and chosen_state is not None:
            carried = fields_cleared_by_classification(chosen_state)
    routes: list[LedgerStagedRoute] = []
    cannot_clear: list[str] = []
    needs_classification: list[str] = []
    for cell in row.cells:
        clear = cell.value is None
        if clear and cell.field in carried:
            routes.append(LedgerStagedRoute(field=cell.field, route=carrier, refused=None))
            continue
        route, refused = route_for_cell(field=cell.field, clear=clear, classified=classified)
        routes.append(LedgerStagedRoute(field=cell.field, route=route, refused=refused))
        if refused == "cannot_clear":
            cannot_clear.append(cell.field)
        elif refused == "needs_classification":
            needs_classification.append(cell.field)
    return tuple(routes), carrier, cannot_clear, needs_classification


def check_stored_row(row: LedgerStagedRow, transaction: Transaction) -> LedgerStagedRowAnswer:
    """Answer one stored movement as it would be once its staged work is saved."""
    before = _stored_facts(transaction)
    after = dict(before)
    for cell in row.cells:
        after[cell.field] = cell.value
    classification = _classification(after["business_classification"])
    direction = _direction(after["direction"])
    classified = classification is not None and is_classified(classification)
    has_evidence = transaction.purchase_invoice_evidence_id is not None or row.evidence_staged
    takes_category = direction is not None and takes_expense_category(direction, has_purchase_evidence=has_evidence)

    routes, _, cannot_clear, needs_classification = _routes_of_row(row, classified)
    if row.m210_staged and not classified:
        needs_classification.append("m210_income_classification")
    blockers: list[LedgerStagedBlocker] = []
    notes: list[LedgerStagedNote] = []
    if cannot_clear:
        blockers.append(LedgerStagedBlocker(kind="cannot_clear", fields=tuple(cannot_clear)))
    if needs_classification:
        blockers.append(LedgerStagedBlocker(kind="needs_classification", fields=tuple(needs_classification)))

    staged_fields = {cell.field for cell in row.cells}
    routed = {route.route for route in routes}
    sends_classification = bool(routed & {"bulk", "classify"}) or (row.m210_staged and classified)
    if sends_classification and classification is not None and takes_business_share(classification):
        if not _filled(after["business_pct"]):
            blockers.append(LedgerStagedBlocker(kind="mixed_needs_share"))
        elif "business_pct" not in staged_fields:
            notes.append(LedgerStagedNote(kind="sends_current_share", value=after["business_pct"]))
    share_cell = next((cell for cell in row.cells if cell.field == "business_pct"), None)
    if (
        share_cell is not None
        and share_cell.value is not None
        and not (classification is not None and takes_business_share(classification))
    ):
        blockers.append(LedgerStagedBlocker(kind="share_needs_mixed"))
    if "bulk" in routed and "business_classification" not in staged_fields:
        notes.append(LedgerStagedNote(kind="sends_current_classification", value=after["business_classification"]))

    transfer = direction is TransactionDirection.INTERNAL_TRANSFER
    if transfer and staged_fields & (_CLASSIFYING_FIELDS | {"direction"}):
        found: list[str] = [field for field in TRANSFER_TAX_FIELDS if after.get(field) is not None]
        if classification in BUSINESS_BEARING_STATES:
            found.insert(0, "business_classification")
        if found:
            blockers.append(LedgerStagedBlocker(kind="transfer_with_tax", fields=tuple(found)))

    identity = _identity_fields(row, before, after)
    if identity:
        notes.append(LedgerStagedNote(kind="new_identity", fields=identity))
    # A category is set on what the row is now, not on a classification still staged.
    settable = (
        transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
        and transaction.business_classification in BUSINESS_BEARING_STATES
        and takes_category
    )
    return LedgerStagedRowAnswer(
        transaction_id=row.transaction_id,
        found=True,
        classified=classified,
        takes_expense_category=takes_category,
        takes_share=classification is not None and takes_business_share(classification),
        category_settable=settable,
        category_on_income=(classification in BUSINESS_BEARING_STATES)
        and bool(after["category_id"])
        and not takes_category,
        tax_set_skip=_tax_set_skip(direction, classification),
        transfer_locked_fields=_TRANSFER_LOCKED_FIELDS if transfer else (),
        classifying_fields=tuple(cell.field for cell in row.cells if cell.field in _CLASSIFYING_FIELDS),
        identity_fields=identity,
        routes=routes,
        blockers=tuple(blockers),
        notes=tuple(notes),
    )


def check_draft(draft: LedgerStagedDraft) -> LedgerStagedDraftAnswer:
    """Answer one new movement."""
    fields: dict[str, str | None] = {item.field: item.value for item in draft.fields}
    missing = tuple(field for field in _DRAFT_REQUIRED_FIELDS if not _filled(fields.get(field)))
    blockers: list[LedgerStagedBlocker] = []
    if missing:
        blockers.append(LedgerStagedBlocker(kind="draft_incomplete", fields=missing))
    classification = _classification(fields.get("business_classification"))
    share_bearing = classification is not None and takes_business_share(classification)
    if share_bearing and not _filled(fields.get("business_pct")):
        blockers.append(LedgerStagedBlocker(kind="mixed_needs_share"))
    if not share_bearing and _filled(fields.get("business_pct")):
        blockers.append(LedgerStagedBlocker(kind="share_needs_mixed"))
    if _direction(fields.get("direction")) is TransactionDirection.INTERNAL_TRANSFER:
        found: list[str] = [field for field in _DRAFT_TRANSFER_TAX_FIELDS if _filled(fields.get(field))]
        if classification in BUSINESS_BEARING_STATES:
            found.insert(0, "business_classification")
        if found:
            blockers.append(LedgerStagedBlocker(kind="transfer_with_tax", fields=tuple(found)))
    return LedgerStagedDraftAnswer(key=draft.key, blockers=tuple(blockers))


def _category_fit(category: str, *, operation: PinnedAuthorityOperation) -> LedgerStagedCategoryFit:
    """Business takes any spending category; Mixed only one a share applies to."""
    known = {str(item) for item in resolve_spending_category_catalogue(authority=operation).categories}
    eligible = {str(item) for item in eligible_usage_ratio_categories()}
    return LedgerStagedCategoryFit(
        category=category, business=category in known, mixed=category in known and category in eligible
    )


def request_digest(request: LedgerStagedCheckRequest) -> str:
    """Return the digest of the request's canonical form."""
    return content_hash_hex(request.model_dump(mode="json"))


def check_staged_work(
    request: LedgerStagedCheckRequest,
    transactions: dict[str, Transaction],
    *,
    operation: PinnedAuthorityOperation,
    profile_id: UUID,
) -> LedgerStagedCheckResult:
    """Answer every row, draft and category of ``request`` against the stored rows."""
    rows = tuple(
        check_stored_row(row, transactions[row.transaction_id])
        if row.transaction_id in transactions
        else LedgerStagedRowAnswer(transaction_id=row.transaction_id, found=False)
        for row in request.rows
    )
    return LedgerStagedCheckResult(
        profile_id=profile_id,
        input_digest=request_digest(request),
        rows=rows,
        drafts=tuple(check_draft(draft) for draft in request.drafts),
        categories=tuple(_category_fit(category, operation=operation) for category in request.categories),
    )


__all__ = [
    "TRANSFER_TAX_FIELDS",
    "check_draft",
    "check_staged_work",
    "check_stored_row",
    "request_digest",
    "route_for_cell",
]
