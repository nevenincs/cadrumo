"""Answer staged ledger work the way the writers would take it.

A frontend staging several cells needs to know, before anything is sent, which
registered write takes each cell, what the staged state of the row would refuse,
and what it would change about the row's identity. Those are the writers' and the
domain's rules, so every frontend asks here. Nothing is written or cached; a write
still checks itself against the row it finds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final
from uuid import UUID

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.external_constants import DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from ...core.hashing import content_hash_hex
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.categories.spending_category_catalogue import resolve_spending_category_catalogue
from ...domain.iva.schema import IvaCategory
from ...domain.transactions.classification_effects import (
    advises_purchase_evidence,
    fields_cleared_by_classification,
    lifecycle_actions_taken,
    takes_changes,
    takes_classification,
    takes_expense_category,
    takes_invoice,
)
from ...domain.transactions.enums import (
    BUSINESS_BEARING_STATES,
    BusinessClassification,
    TransactionDirection,
    is_classified,
    takes_business_share,
)
from ...domain.transactions.gross_validation import GrossReconstitutionFinding, gross_reconstitution_finding
from ...domain.transactions.models import Transaction
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
    StagedBlockerKind,
    StageFieldName,
    TaxSetSkip,
    WriteRoute,
)
from .staged_check_words import blocker_words, share_refusal_words
from .staged_identity import staged_identity_fields
from .update_contracts import LEDGER_UPDATE_FIELD_NAMES, LEDGER_UPDATE_REQUIRED_FIELD_NAMES

_BULK_COLUMN_OF_FIELD: Final = {"business_classification": "classification"}


@dataclass(frozen=True, slots=True)
class _Blocked:
    """What holds a movement back, before it is worded for a reader."""

    kind: StagedBlockerKind
    fields: tuple[str, ...] = ()


def _worded(blocked: _Blocked, language: OutputLanguage) -> LedgerStagedBlocker:
    """Say what holds a movement back, and what puts it right, in ``language``."""
    words, fix_words = blocker_words(blocked.kind, language)
    return LedgerStagedBlocker(
        kind=blocked.kind, fields=blocked.fields, words=words, fix_words=fix_words, words_language=language
    )


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
    "operation_date",
    "accrual_date",
)
"""What ``ManualLedgerTransactionCommand`` refuses on a transfer, of what a cell can stage."""

_TRANSFER_STORED_TAX_FIELDS: Final[tuple[str, ...]] = (
    "recargo_amount",
    "m210_income_classification",
    "prorrata_reference",
    "art_104_tres_exclusion",
    "input_classification",
    "prorrata_sector_id",
    "purchase_invoice_evidence_id",
    "attachment_ids",
)
"""What the same writer refuses on a transfer and no cell stages: only a stored row carries these."""

_DRAFT_TRANSFER_TAX_FIELDS: Final[tuple[str, ...]] = (*TRANSFER_TAX_FIELDS, *_TRANSFER_STORED_TAX_FIELDS)

TRANSFER_LOCKED_FIELDS: Final[tuple[StageFieldName, ...]] = TRANSFER_TAX_FIELDS
"""What cannot be edited on a transfer: the writer refuses every one of them there."""

_CLASSIFYING_FIELDS: Final[frozenset[str]] = frozenset(
    {*TRANSFER_TAX_FIELDS, "business_classification", "counterparty_country"} - {"operation_date", "accrual_date"}
)

DRAFT_REQUIRED_FIELDS: Final = ("booked_date", "amount", "currency", "direction", "description")

_SIGNS: Final = ("-", "+", "−")
"""What a sign written in front of an amount can be, including the typographic minus."""


def _signed_amount_blocker(staged_amount: str | None) -> _Blocked | None:
    """Block an amount written with a sign.

    A movement's amount is a magnitude and its direction carries the economic
    direction, so a signed amount is not a grammar accident a window can
    silently drop: it is a staged value the writer would refuse, and the person
    is told which of the two facts says what.
    """
    if staged_amount is None or not staged_amount.strip().startswith(_SIGNS):
        return None
    return _Blocked(kind="amount_signed", fields=("amount", "direction"))


def _decimal(value: str | None) -> Decimal | None:
    """Read one staged figure, or nothing when it is absent or not canonical."""
    return None if not _filled(value) else try_parse_canonical_decimal(str(value))


def _day(value: str | None) -> date | None:
    """Read one staged date, or nothing when it is absent or not an ISO day."""
    if not _filled(value):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _gross_blocker(
    facts: dict[str, str | None],
    *,
    recargo_amount: Decimal | None,
    direction: TransactionDirection | None,
    operation: PinnedAuthorityOperation | None,
) -> _Blocked | None:
    """Block a row whose declared base and IVA exceed the cash with no IRPF category.

    The identity is the domain's, read here rather than restated: the window
    asks before it saves so the person meets the missing fact in the review
    instead of a writer's arithmetic after the save.
    """
    amount = _decimal(facts.get("amount"))
    taxable_base = _decimal(facts.get("taxable_base"))
    iva_amount = _decimal(facts.get("iva_amount"))
    settlement_day = _day(facts.get("value_date")) or _day(facts.get("booked_date"))
    if amount is None or taxable_base is None or iva_amount is None or direction is None or settlement_day is None:
        return None
    iva_category = facts.get("iva_category")
    finding = gross_reconstitution_finding(
        raw_amount=amount,
        taxable_base=taxable_base,
        iva_amount=iva_amount,
        recargo_amount=recargo_amount,
        iva_category=None if not _filled(iva_category) else IvaCategory(str(iva_category)),
        direction=direction,
        category_id=facts.get("category_id"),
        irpf_category=facts.get("irpf_category"),
        effective_date=settlement_day,
        authority=operation,
    )
    if finding is not GrossReconstitutionFinding.NEEDS_IRPF_CATEGORY:
        return None
    return _Blocked(kind="needs_withholding_category", fields=("irpf_category",))


def route_for_cell(*, field: str, clear: bool, classified: bool) -> tuple[WriteRoute | None, RouteRefusal | None]:
    """Choose the write that takes one cell, from what each registered write accepts.

    A clear, a field only an update takes, and a tax figure on a row with no
    classification all go through the update's field mask. The bulk never carries
    a clear: a blank cell there means unchanged.
    """
    bulk = _BULK_COLUMN_OF_FIELD.get(field, field) in BULK_CLASSIFY_ALLOWED_COLUMNS
    classify = _classify_takes(field, clear)
    update = _update_takes(field, clear)
    if _update_route_taken(bulk=bulk, classify=classify, update=update, clear=clear, classified=classified):
        return "update", None
    # The bulk never carries a clear, so only a stated value reaches it.
    bulk_takes = not clear and bulk
    if bulk_takes and classified:
        return "bulk", None
    if classify and classified:
        return "classify", None
    if classify or bulk_takes:
        return None, "needs_classification"
    return None, "cannot_clear"


def _classify_takes(field: str, clear: bool) -> bool:
    """Return whether the classification write takes this cell."""
    return field in CLASSIFY_FIELD_NAMES and not (clear and field in CLASSIFY_UNCLEARABLE_FIELD_NAMES)


def _update_takes(field: str, clear: bool) -> bool:
    """Return whether the update's field mask takes this cell."""
    return field in LEDGER_UPDATE_FIELD_NAMES and not (clear and field in LEDGER_UPDATE_REQUIRED_FIELD_NAMES)


def _update_route_taken(*, bulk: bool, classify: bool, update: bool, clear: bool, classified: bool) -> bool:
    # A field only the update takes goes there whatever the classification.
    update_only = not bulk and not classify and update
    return update and (update_only or clear or not classified)


def _filled(value: str | None) -> bool:
    return value is not None and value != ""


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else display_decimal(value)


def _stored_facts(transaction: Transaction) -> dict[str, str | None]:
    raw = transaction.raw
    return {
        "booked_date": raw.booked_date.isoformat(),
        "value_date": None if raw.value_date is None else raw.value_date.isoformat(),
        "operation_date": None if transaction.operation_date is None else transaction.operation_date.isoformat(),
        "accrual_date": None if transaction.accrual_date is None else transaction.accrual_date.isoformat(),
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
        "deduction_fact_kind": None
        if transaction.deduction_fact_kind is None
        else str(transaction.deduction_fact_kind),
        "investment_asset_id": transaction.investment_asset_id,
        "counterparty_country": transaction.counterparty_country,
        "counterparty_identification_state": (
            None
            if transaction.counterparty_identification_state is None
            else str(transaction.counterparty_identification_state)
        ),
    }


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
    return None


def _classification_carrier(row: LedgerStagedRow, classified: bool) -> tuple[WriteRoute | None, frozenset[str]]:
    """Find the write that carries the staged classification and the clears it performs."""
    chosen = next((cell for cell in row.cells if cell.field == "business_classification"), None)
    carrier: WriteRoute | None = None
    carried = frozenset[str]()
    if chosen is not None and chosen.value is not None:
        carrier, _ = route_for_cell(field=chosen.field, clear=False, classified=classified)
        chosen_state = _classification(chosen.value)
        if carrier is not None and chosen_state is not None:
            carried = fields_cleared_by_classification(chosen_state)
    return carrier, carried


def _routes_of_row(
    row: LedgerStagedRow, classified: bool
) -> tuple[tuple[LedgerStagedRoute, ...], WriteRoute | None, list[str], list[str]]:
    """Route each cell; a clear the classification's own write performs travels with that write."""
    carrier, carried = _classification_carrier(row, classified)
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


def _shares_business(classification: BusinessClassification | None) -> bool:
    """Return whether the classification takes a business share."""
    return classification is not None and takes_business_share(classification)


def _unroutable_blockers(cannot_clear: list[str], needs_classification: list[str]) -> list[_Blocked]:
    """Block on the cells no write takes: those that cannot be cleared and those that need a classification."""
    blockers: list[_Blocked] = []
    if cannot_clear:
        blockers.append(_Blocked(kind="cannot_clear", fields=tuple(cannot_clear)))
    if needs_classification:
        blockers.append(_Blocked(kind="needs_classification", fields=tuple(needs_classification)))
    return blockers


def _share_staged_without_mixed(row: LedgerStagedRow, shares: bool) -> bool:
    """Return whether a share is staged to a value on a row whose classification takes none."""
    share_cell = next((cell for cell in row.cells if cell.field == "business_pct"), None)
    return share_cell is not None and share_cell.value is not None and not shares


def _share_findings(
    row: LedgerStagedRow,
    classification: BusinessClassification | None,
    after: dict[str, str | None],
    routed: set[WriteRoute | None],
    sends_classification: bool,
) -> tuple[list[_Blocked], list[LedgerStagedNote]]:
    """What the staged state says about the business share and the classification a write resends."""
    staged_fields = {cell.field for cell in row.cells}
    shares = _shares_business(classification)
    blockers: list[_Blocked] = []
    notes: list[LedgerStagedNote] = []
    if sends_classification and shares:
        if not _filled(after["business_pct"]):
            blockers.append(_Blocked(kind="mixed_needs_share"))
        elif "business_pct" not in staged_fields:
            notes.append(LedgerStagedNote(kind="sends_current_share", value=after["business_pct"]))
    if _share_staged_without_mixed(row, shares):
        blockers.append(_Blocked(kind="share_needs_mixed"))
    if "bulk" in routed and "business_classification" not in staged_fields:
        notes.append(LedgerStagedNote(kind="sends_current_classification", value=after["business_classification"]))
    return blockers, notes


def _transfer_with_tax(found: list[str], classification: BusinessClassification | None) -> _Blocked | None:
    """Block a transfer the writer would refuse; a classification it refuses counts, listed first."""
    if classification is not None and not takes_classification(TransactionDirection.INTERNAL_TRANSFER, classification):
        found.insert(0, "business_classification")
    if not found:
        return None
    return _Blocked(kind="transfer_with_tax", fields=tuple(found))


def _stored_transfer_tax_fields(row: LedgerStagedRow, transaction: Transaction) -> list[str]:
    """Name what the writer refuses on a transfer and only the stored row, or staged evidence, carries."""
    found = [field for field in _TRANSFER_STORED_TAX_FIELDS if getattr(transaction, field) not in (None, ())]
    if row.m210_staged and "m210_income_classification" not in found:
        found.append("m210_income_classification")
    if row.evidence_staged and "purchase_invoice_evidence_id" not in found:
        found.append("purchase_invoice_evidence_id")
    return found


def _transfer_blocker(
    row: LedgerStagedRow,
    transaction: Transaction,
    classification: BusinessClassification | None,
    after: dict[str, str | None],
) -> _Blocked | None:
    # Any write revalidates the whole row, so a cell far from the tax fields is refused for them too.
    if not row.cells and not row.m210_staged and not row.evidence_staged:
        return None
    found: list[str] = [field for field in TRANSFER_TAX_FIELDS if after.get(field) is not None]
    found.extend(_stored_transfer_tax_fields(row, transaction))
    return _transfer_with_tax(found, classification)


def _category_on_income(
    classification: BusinessClassification | None, after: dict[str, str | None], takes_category: bool
) -> bool:
    """Return whether a business row that takes no category still holds one."""
    return (classification in BUSINESS_BEARING_STATES) and bool(after["category_id"]) and not takes_category


def _category_askable(transaction: Transaction, classification: BusinessClassification | None) -> bool:
    # The classification staged travels in the same write, so the row is judged as it will be saved.
    return takes_changes(transaction.lifecycle_state) and classification in BUSINESS_BEARING_STATES


def _category_settable(
    transaction: Transaction, classification: BusinessClassification | None, takes_category: bool
) -> bool:
    return _category_askable(transaction, classification) and takes_category


@dataclass(frozen=True, slots=True)
class _StagedState:
    """The stored facts, the facts once the staged cells are applied, and what they classify as."""

    before: dict[str, str | None]
    after: dict[str, str | None]
    classification: BusinessClassification | None
    direction: TransactionDirection | None
    classified: bool


def _staged_state(row: LedgerStagedRow, transaction: Transaction) -> _StagedState:
    """Apply the staged cells to the stored facts of the movement."""
    before = _stored_facts(transaction)
    after = dict(before)
    for cell in row.cells:
        after[cell.field] = cell.value
    classification = _classification(after["business_classification"])
    return _StagedState(
        before=before,
        after=after,
        classification=classification,
        direction=_direction(after["direction"]),
        classified=classification is not None and is_classified(classification),
    )


def _row_findings(
    row: LedgerStagedRow,
    transaction: Transaction,
    state: _StagedState,
    routes: tuple[LedgerStagedRoute, ...],
    cannot_clear: list[str],
    needs_classification: list[str],
    operation: PinnedAuthorityOperation | None,
) -> tuple[list[_Blocked], list[LedgerStagedNote], tuple[StageFieldName, ...]]:
    """Gather what the staged state of the row would refuse, note, and change about its identity."""
    if row.m210_staged and not state.classified:
        needs_classification.append("m210_income_classification")
    # Blockers keep this order: unroutable cells, the share, then a transfer.
    blockers = _unroutable_blockers(cannot_clear, needs_classification)

    # A classification write resends the share, so a missing one refuses the whole row.
    routed: set[WriteRoute | None] = {route.route for route in routes}
    sends_classification = bool(routed & {"bulk", "classify"}) or (row.m210_staged and state.classified)
    share_blockers, notes = _share_findings(row, state.classification, state.after, routed, sends_classification)
    blockers.extend(share_blockers)

    # Notes keep the order of the share notes, then the new identity.
    transfer = state.direction is TransactionDirection.INTERNAL_TRANSFER
    transfer_blocker = _transfer_blocker(row, transaction, state.classification, state.after) if transfer else None
    if transfer_blocker is not None:
        blockers.append(transfer_blocker)

    # A signed amount is read from the STAGED cell, never from the stored
    # facts: what a store holds is the writer's business, and a row already
    # kept there is not held back by a cell nobody touched.
    staged_amount = next((cell.value for cell in row.cells if cell.field == "amount"), None)
    signed = _signed_amount_blocker(staged_amount)
    if signed is not None:
        blockers.append(signed)
    elif row.cells:
        gross = _gross_blocker(
            state.after,
            recargo_amount=transaction.recargo_amount,
            direction=state.direction,
            operation=operation,
        )
        if gross is not None:
            blockers.append(gross)

    identity = staged_identity_fields(row, state.before, state.after)
    if identity:
        notes.append(LedgerStagedNote(kind="new_identity", fields=identity))
    return blockers, notes, identity


def check_stored_row(
    row: LedgerStagedRow,
    transaction: Transaction,
    *,
    language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE,
    operation: PinnedAuthorityOperation | None = None,
) -> LedgerStagedRowAnswer:
    """Answer one stored movement as it would be once its staged work is saved, in ``language``.

    ``operation`` is the pinned authority the registry-reading checks resolve
    their facts from; omitted, they resolve from the generation the validation
    in progress pinned, and refuse when there is none.
    """
    state = _staged_state(row, transaction)
    classification = state.classification
    has_evidence = transaction.purchase_invoice_evidence_id is not None or row.evidence_staged
    direction = state.direction
    takes_category = direction is not None and takes_expense_category(direction, has_purchase_evidence=has_evidence)

    routes, _, cannot_clear, needs_classification = _routes_of_row(row, state.classified)
    blockers, notes, identity = _row_findings(
        row, transaction, state, routes, cannot_clear, needs_classification, operation
    )
    return LedgerStagedRowAnswer(
        transaction_id=row.transaction_id,
        found=True,
        classified=state.classified,
        takes_expense_category=takes_category,
        takes_share=_shares_business(classification),
        category_askable=_category_askable(transaction, classification),
        category_settable=_category_settable(transaction, classification, takes_category),
        takes_changes=takes_changes(transaction.lifecycle_state),
        takes_invoice=takes_invoice(transaction.direction),
        evidence_advised=advises_purchase_evidence(
            transaction.lifecycle_state,
            transaction.direction,
            transaction.business_classification,
            has_evidence=transaction.purchase_invoice_evidence_id is not None,
        ),
        lifecycle_actions=lifecycle_actions_taken(transaction.lifecycle_state, transaction.business_classification),
        category_on_income=_category_on_income(classification, state.after, takes_category),
        tax_set_skip=_tax_set_skip(state.direction, classification),
        transfer_locked_fields=TRANSFER_LOCKED_FIELDS
        if state.direction is TransactionDirection.INTERNAL_TRANSFER
        else (),
        classifying_fields=tuple(cell.field for cell in row.cells if cell.field in _CLASSIFYING_FIELDS),
        identity_fields=identity,
        routes=routes,
        blockers=tuple(_worded(blocked, language) for blocked in blockers),
        notes=tuple(notes),
    )


def _draft_share_blockers(
    fields: dict[str, str | None], classification: BusinessClassification | None
) -> list[_Blocked]:
    """Block a draft whose business share and classification disagree."""
    share_bearing = _shares_business(classification)
    blockers: list[_Blocked] = []
    if share_bearing and not _filled(fields.get("business_pct")):
        blockers.append(_Blocked(kind="mixed_needs_share"))
    if not share_bearing and _filled(fields.get("business_pct")):
        blockers.append(_Blocked(kind="share_needs_mixed"))
    return blockers


def _draft_transfer_blocker(
    fields: dict[str, str | None], classification: BusinessClassification | None
) -> _Blocked | None:
    """Block a draft transfer that names tax fields."""
    found = [field for field in _DRAFT_TRANSFER_TAX_FIELDS if _filled(fields.get(field))]
    return _transfer_with_tax(found, classification)


def check_draft(
    draft: LedgerStagedDraft,
    *,
    language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE,
    operation: PinnedAuthorityOperation | None = None,
) -> LedgerStagedDraftAnswer:
    """Answer one new movement, in ``language``.

    ``operation`` is the pinned authority the registry-reading checks resolve
    their facts from, as for a stored movement.
    """
    fields: dict[str, str | None] = {item.field: item.value for item in draft.fields}
    missing = tuple(field for field in DRAFT_REQUIRED_FIELDS if not _filled(fields.get(field)))
    blockers: list[_Blocked] = []
    if missing:
        blockers.append(_Blocked(kind="draft_incomplete", fields=missing))
    classification = _classification(fields.get("business_classification"))
    direction = _direction(fields.get("direction"))
    blockers.extend(_draft_share_blockers(fields, classification))
    if direction is TransactionDirection.INTERNAL_TRANSFER:
        transfer_blocker = _draft_transfer_blocker(fields, classification)
        if transfer_blocker is not None:
            blockers.append(transfer_blocker)
    signed = _signed_amount_blocker(fields.get("amount"))
    if signed is not None:
        blockers.append(signed)
    else:
        gross = _gross_blocker(
            fields,
            recargo_amount=_decimal(fields.get("recargo_amount")),
            direction=direction,
            operation=operation,
        )
        if gross is not None:
            blockers.append(gross)
    return LedgerStagedDraftAnswer(
        key=draft.key,
        takes_expense_category=direction is not None and takes_expense_category(direction, has_purchase_evidence=False),
        blockers=tuple(_worded(blocked, language) for blocked in blockers),
    )


def _category_fit(category: str, *, operation: PinnedAuthorityOperation) -> LedgerStagedCategoryFit:
    """The writer takes any spending category the registry declares on a Business or Mixed row.

    What a category is worth on a Mixed row is the aggregation's answer, and the
    readiness check holds one without a usage ratio.
    """
    known = category in {str(item) for item in resolve_spending_category_catalogue(authority=operation).categories}
    return LedgerStagedCategoryFit(category=category, business=known, mixed=known)


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
    """Answer every row, draft and category of ``request`` against the stored rows, in the request's language."""
    language = request.output_language
    rows = tuple(
        check_stored_row(row, transactions[row.transaction_id], language=language, operation=operation)
        if row.transaction_id in transactions
        else LedgerStagedRowAnswer(transaction_id=row.transaction_id, found=False)
        for row in request.rows
    )
    return LedgerStagedCheckResult(
        profile_id=profile_id,
        input_digest=request_digest(request),
        rows=rows,
        drafts=tuple(check_draft(draft, language=language, operation=operation) for draft in request.drafts),
        categories=tuple(_category_fit(category, operation=operation) for category in request.categories),
        share_refusal_words=share_refusal_words(language),
        share_refusal_words_language=language,
    )


__all__ = [
    "DRAFT_REQUIRED_FIELDS",
    "TRANSFER_LOCKED_FIELDS",
    "TRANSFER_TAX_FIELDS",
    "check_draft",
    "check_staged_work",
    "check_stored_row",
    "request_digest",
    "route_for_cell",
]
