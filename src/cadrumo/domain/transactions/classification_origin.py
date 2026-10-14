"""Whose decision a ledger row's current classification is.

``classified_by`` names the mechanism of the last write, and every write to a
classified row stamps it again, so it cannot say whose decision the
classification is: attaching a document to a row a rule classified leaves the
stamp a hand classification leaves. The origin recorded beside it answers that
one question, and one function here decides it for every writer.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Final, Self, override

from ...core.external_constants import CLASSIFIED_BY_AUTO
from .enums import BusinessClassification

if TYPE_CHECKING:
    from .models import Transaction

_RULE_STAMP_PREFIX = "rule:"

_MOVEMENT_FIELDS: Final = frozenset({"booked_date", "value_date", "amount", "currency"})
"""The decision fields a row keeps on its raw movement rather than on itself."""

CLASSIFICATION_DECISION_FIELDS: Final[frozenset[str]] = _MOVEMENT_FIELDS | {
    "direction",
    "source_jurisdiction",
    "business_classification",
    "business_pct",
    "category_id",
    "usage_ratio_id",
    "prorrata_reference",
    "iva_category",
    "iva_rate",
    "taxable_base",
    "iva_amount",
    "recargo_amount",
    "irpf_category",
    "m210_income_classification",
    "deduction_fact_kind",
    "investment_asset_id",
    "counterparty_country",
    "counterparty_identification_state",
    "art_104_tres_exclusion",
    "input_classification",
    "prorrata_sector_id",
    "purchase_invoice_evidence_id",
}
"""Every fact a ledger write can set that bears on how the row is taxed.

The movement's money, dates and direction, the classification and its share,
the tax figures and declarations, and the link to purchase-invoice evidence:
a calculation takes a linked row's figures from the invoice, counts an
incoming row as a refund, and admits its input IVA deduction on that
evidence. A write that sets one of them decides the row's tax treatment; a
write that sets only what is left (a note, a description, a label, a
supplementary attachment) does not. A test holds the set equal to what the
ledger's command can carry less the members that test declares as bearing on
no tax, so a field added later is placed in one or the other.
"""


class ClassificationOrigin(StrEnum):
    """Who decided the classification and tax figures a row carries now."""

    PERSON = "person"
    """The person set it, or accepted a proposal or ran a derivation on their own frontend."""
    AUTOMATION = "automation"
    """An authenticated delegated execution set or accepted the classification."""
    AUTOMATIC = "automatic"
    """A stored rule or the pipeline set it, with nobody deciding the row."""

    @classmethod
    @override
    def _missing_(cls, value: object) -> Self | None:
        """Preserve historical provenance tags without deriving authority from them."""
        if not isinstance(value, str) or not value or len(value) > 64:
            return None
        historical = str.__new__(cls, value)
        historical._name_ = "HISTORICAL"
        historical._value_ = value
        return historical


def classification_facts(transaction: Transaction) -> tuple[object, ...]:
    """Return every tax-bearing fact of ``transaction`` as one comparable value."""
    return tuple(
        getattr(transaction.raw if field in _MOVEMENT_FIELDS else transaction, field)
        for field in sorted(CLASSIFICATION_DECISION_FIELDS)
    )


def written_classification_origin(*, by_automation: bool, classified_by: str) -> ClassificationOrigin:
    """Return the origin of a classification that a write carrying this stamp decides.

    A rule's output is automatic whoever ran the rules. Anything else is the
    decision of whoever ran the write: typing it, accepting a model's proposal
    and deriving figures from a chosen category are all that party's act.
    """
    stamp = classified_by.strip()
    if stamp == CLASSIFIED_BY_AUTO or stamp.startswith(_RULE_STAMP_PREFIX):
        return ClassificationOrigin.AUTOMATIC
    return ClassificationOrigin.AUTOMATION if by_automation else ClassificationOrigin.PERSON


def resolved_classification_origin(transaction: Transaction) -> ClassificationOrigin | None:
    """Return whose decision the row's current classification is, or ``None`` for an unprocessed row.

    A row stored before the origin was recorded is read from its stamp: a
    rule's or the pipeline's stamp is automatic, and every other classified row
    is the person's, when no recorded decision provenance exists.
    """
    if transaction.business_classification is BusinessClassification.NOT_YET_PROCESSED:
        return None
    if transaction.classification_origin is not None:
        return transaction.classification_origin
    return written_classification_origin(by_automation=False, classified_by=transaction.classified_by)


def with_classification_origin(
    replacement: Transaction,
    *,
    replaces: Transaction | None,
    written: ClassificationOrigin,
    decided: bool,
) -> Transaction:
    """Return ``replacement`` recording whose decision its classification is.

    A write that changes a tax-bearing fact of the row it replaces records
    ``written``. ``decided`` says the write set such a fact, whether or not the
    value moved: a person who submits the classification a rule, a model or an
    automation already gave the row has accepted it, so the row becomes theirs. No
    other party takes a row by restating it, so a rule's or an automation's
    unchanged write leaves the recorded origin standing, as does any write that
    set no such fact. An unprocessed row records none.
    """
    origin: ClassificationOrigin | None
    if replacement.business_classification is BusinessClassification.NOT_YET_PROCESSED:
        origin = None
    else:
        kept = None if replaces is None else resolved_classification_origin(replaces)
        if kept is None or replaces is None or classification_facts(replaces) != classification_facts(replacement):
            origin = written
        elif decided and written is ClassificationOrigin.PERSON:
            origin = ClassificationOrigin.PERSON
        else:
            origin = kept
    if replacement.classification_origin is origin:
        return replacement
    return replacement.model_copy(update={"classification_origin": origin})


__all__ = [
    "CLASSIFICATION_DECISION_FIELDS",
    "ClassificationOrigin",
    "classification_facts",
    "resolved_classification_origin",
    "with_classification_origin",
    "written_classification_origin",
]
