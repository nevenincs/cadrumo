"""The one projection from an operator filter spec onto a Ledger review query.

Two verbs resolve the same ``--filter`` clauses -- the review listing and the
transaction listing that narrows by review state -- and if each mapped the spec
onto its own query, the identical clauses could select different rows on the two
surfaces. The mapping therefore has one home.

It sits in the Ledger package rather than beside the spec because the direction
of the dependency is already fixed: ``models`` imports the spec's status enum,
so the spec's module cannot import the query type back without a cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import LedgerReviewQuery

if TYPE_CHECKING:
    from ..review.filter import LedgerReviewFilterSpec


def ledger_review_query_for_spec(
    spec: LedgerReviewFilterSpec,
    *,
    bucket_id: str,
    transaction_id: str | None = None,
) -> LedgerReviewQuery:
    """Project one parsed operator filter spec onto its :class:`LedgerReviewQuery`.

    The single home for the spec-to-query field mapping, shared by ``ledger
    list``'s review-spec narrowing and the ``ledger review`` verb, so the two
    surfaces cannot resolve the same ``--filter`` clauses differently.
    """
    return LedgerReviewQuery(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        period=spec.period,
        status=spec.status.value if spec.status is not None else None,
        issue=spec.issue.value if spec.issue is not None else None,
        import_id=spec.import_id,
        classification=spec.classification.value if spec.classification is not None else None,
        text=spec.text,
        direction=spec.direction.value if spec.direction is not None else None,
    )


__all__ = ["ledger_review_query_for_spec"]
