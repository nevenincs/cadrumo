"""Whose decision a ledger row's current classification is.

``classified_by`` names the mechanism of the last write, and every write to a
classified row stamps it again, so it cannot say whose decision the
classification is: attaching a document to a row a rule classified leaves the
stamp a hand classification leaves. The origin recorded beside it answers that
one question, and one function here decides it for every writer.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from ...core.external_constants import CLASSIFIED_BY_AUTO
from .enums import BusinessClassification

if TYPE_CHECKING:
    from .models import Transaction

_RULE_STAMP_PREFIX = "rule:"

_CLASSIFICATION_FACT_FIELDS = (
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
)
"""The classification, its share and the tax figures a write is judged to have decided."""


class ClassificationOrigin(StrEnum):
    """Who decided the classification and tax figures a row carries now."""

    PERSON = "person"
    """The person set it, or accepted a proposal or ran a derivation on their own frontend."""
    AGENT = "agent"
    """An agent's execution set it, or accepted the proposal that set it."""
    AUTOMATIC = "automatic"
    """A stored rule or the pipeline set it, with nobody deciding the row."""


def classification_facts(transaction: Transaction) -> tuple[object, ...]:
    """Return the classification, share and tax figures of ``transaction`` as one comparable value."""
    return tuple(getattr(transaction, field) for field in _CLASSIFICATION_FACT_FIELDS)


def written_classification_origin(*, by_agent: bool, classified_by: str) -> ClassificationOrigin:
    """Return the origin of a classification that a write carrying this stamp decides.

    A rule's output is automatic whoever ran the rules. Anything else is the
    decision of whoever ran the write: typing it, accepting a model's proposal
    and deriving figures from a chosen category are all that party's act.
    """
    stamp = classified_by.strip()
    if stamp == CLASSIFIED_BY_AUTO or stamp.startswith(_RULE_STAMP_PREFIX):
        return ClassificationOrigin.AUTOMATIC
    return ClassificationOrigin.AGENT if by_agent else ClassificationOrigin.PERSON


def resolved_classification_origin(transaction: Transaction) -> ClassificationOrigin | None:
    """Return whose decision the row's current classification is, or ``None`` for an unprocessed row.

    A row stored before the origin was recorded is read from its stamp: a
    rule's or the pipeline's stamp is automatic, and every other classified row
    is the person's, because no agent could classify a row then.
    """
    if transaction.business_classification is BusinessClassification.NOT_YET_PROCESSED:
        return None
    if transaction.classification_origin is not None:
        return transaction.classification_origin
    return written_classification_origin(by_agent=False, classified_by=transaction.classified_by)


def classification_is_the_persons(transaction: Transaction) -> bool:
    """Return whether the person decided the classification and tax figures the row carries now."""
    return resolved_classification_origin(transaction) is ClassificationOrigin.PERSON


def with_classification_origin(
    replacement: Transaction,
    *,
    replaces: Transaction | None,
    written: ClassificationOrigin,
) -> Transaction:
    """Return ``replacement`` recording whose decision its classification is.

    A write that leaves the classification, share and tax figures of the row it
    replaces as they were decided nothing, so the origin already recorded
    stands whoever ran the write. A write that sets or changes any of them
    records ``written``. An unprocessed row records none.
    """
    origin: ClassificationOrigin | None
    if replacement.business_classification is BusinessClassification.NOT_YET_PROCESSED:
        origin = None
    else:
        kept = None if replaces is None else resolved_classification_origin(replaces)
        unchanged = replaces is not None and classification_facts(replaces) == classification_facts(replacement)
        origin = kept if kept is not None and unchanged else written
    if replacement.classification_origin is origin:
        return replacement
    return replacement.model_copy(update={"classification_origin": origin})


__all__ = [
    "ClassificationOrigin",
    "classification_facts",
    "classification_is_the_persons",
    "resolved_classification_origin",
    "with_classification_origin",
    "written_classification_origin",
]
