"""Operator-facing projections for the read-only review queue.

Projects :class:`ReviewQueue` items into :class:`ReviewQueueRow` records grouped
in a :class:`ReviewQueueReport`, carrying the active :class:`BucketId` and the
public :class:`BindingSourceKind` selector vocabulary for CLI rendering.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from types import MappingProxyType

from pydantic import BaseModel, Field

from ...core.aggregation import COUNTERPART_SOURCE_KINDS, BindingSourceKind
from ...core.config import Settings
from ...core.i18n import tr
from ...core.identity import BucketId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time.utc import UtcInstant
from ...domain.calculations.registry.ids import LegalRefId
from ._aggregator import ReviewQueue
from .enums import ReviewItemKind, ReviewSeverity, ReviewState
from .errors import ReviewError
from .models import InvoiceReviewItem, ReviewItem, TransactionReviewItem


class ReviewQueueRow(BaseModel):
    """CLI-ready read-only review queue row."""

    model_config = _STRICT_FROZEN

    item_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    source_kind: str | None = None
    affected_object_id: str = Field(min_length=1)
    bucket_id: BucketId
    modelo: str | None = None
    period: str | None = None
    severity: ReviewSeverity
    state: ReviewState
    blocking: bool
    reason: str = ""
    current_owner_surface: str = Field(min_length=1)
    canonical_next_command: str = Field(min_length=1)
    since: UtcInstant
    """The originating review item's instant, carried under the same contract.

    Every :class:`~cadrumo.application.review.ReviewItem` validates ``since``
    as UTC-aware, and this projection is the only thing between that record
    and the wire. Declared as a bare ``datetime`` it re-admitted the naive and
    non-UTC values the canonical queue refuses, and cross-source sorting is
    only deterministic while every row's instant is comparable.
    """
    summary: str = Field(min_length=1)
    legal_refs: tuple[LegalRefId, ...] = Field(default_factory=tuple)
    """Legal references (BOE permalinks or canonical IDs) justifying the finding.

    Populated for ``modelo_finding`` items from the underlying
    :attr:`~cadrumo.domain.filing.ModeloValidationFinding.references_rules`.
    Empty for transaction / invoice items where the obligation is not
    directly grounded in a registry legal reference.
    """


class ReviewQueueReport(BaseModel):
    """Read-only review queue report."""

    model_config = _STRICT_FROZEN

    rows: tuple[ReviewQueueRow, ...]


_ACCEPTED_KIND_TO_INTERNAL: Mapping[str, frozenset[ReviewItemKind]] = MappingProxyType(
    {
        BindingSourceKind.LEDGER_TRANSACTION: frozenset({ReviewItemKind.TRANSACTION}),
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE: frozenset({ReviewItemKind.INVOICE}),
        BindingSourceKind.PAYABLE_INVOICE: frozenset({ReviewItemKind.INVOICE}),
        BindingSourceKind.COLLECTIBLE_INVOICE: frozenset({ReviewItemKind.INVOICE}),
        "modelo_finding": frozenset({ReviewItemKind.FINDING}),
        "live_notification": frozenset[ReviewItemKind](),
        "sync_divergence": frozenset[ReviewItemKind](),
    },
)
assert frozenset(key for key in _ACCEPTED_KIND_TO_INTERNAL if isinstance(key, BindingSourceKind)) == (
    COUNTERPART_SOURCE_KINDS
), "review queue's BindingSourceKind keys must match the canonical counterpart source-kind set"

# The operator-facing ``--kind`` vocabulary: only the source kinds that map to an
# emitted review item, in the order documented in
# ``docs/how-to/review-queue.md``. ``live_notification`` / ``sync_divergence`` are
# parseable but emit nothing, so they are not advertised in the instructive
# refusal — surfacing them would invite an operator to filter on a kind that can
# never produce a row.
ACCEPTED_KINDS: tuple[str, ...] = tuple(str(kind) for kind, internal in _ACCEPTED_KIND_TO_INTERNAL.items() if internal)


def project_review_queue(
    *,
    settings: Settings | None = None,
    kinds: Iterable[str] = (),
    source_kinds: Iterable[str] = (),
    state: ReviewState = ReviewState.PENDING,
    modelo: str | None = None,
    confidence_below: Decimal | None = None,
) -> ReviewQueueReport:
    """Return a :class:`ReviewQueueReport` using accepted source-kind vocabulary.

    When ``confidence_below`` is set, the queue narrows to classified
    transactions whose ``classification_confidence`` is non-None and
    strictly below the threshold, so the operator can triage the
    lowest-confidence classifications first (see
    :meth:`~cadrumo.application.review.ReviewQueue.collect`). Invoice and
    finding rows carry no decision-confidence and are excluded while the
    filter is active.
    """
    selected = _resolve_internal_kinds((*tuple(kinds), *tuple(source_kinds)))
    bucket_id = _active_bucket_id()
    from ...core.config import load_settings as _load_settings

    items = ReviewQueue.collect(
        settings or _load_settings(),
        bucket_id=bucket_id,
        kinds=selected,
        state=state,
        modelo=modelo,
        confidence_below=confidence_below,
    )
    accepted_kinds = frozenset(kind.strip() for kind in kinds if kind.strip())
    accepted_source_kinds = frozenset(kind.strip() for kind in source_kinds if kind.strip())
    rows = tuple(
        row
        for item in items
        for row in (_to_row(item, state=state, bucket_id=bucket_id),)
        if _row_matches(row, accepted_kinds, accepted_source_kinds)
    )
    return ReviewQueueReport(rows=rows)


def project_review_item(item_id: str, *, settings: Settings | None = None) -> ReviewQueueRow:
    """Return one review row by id.

    Returns a :class:`ReviewQueueRow` matching ``item_id``.
    """
    report = project_review_queue(settings=settings, state=ReviewState.ALL)
    for row in report.rows:
        if row.item_id == item_id:
            return row
    raise ReviewError(
        message="review item not found",
        translated_message="review.operator.errors.item_not_found",
    )


def _resolve_internal_kinds(kinds: Iterable[str]) -> frozenset[ReviewItemKind] | None:
    internal: set[ReviewItemKind] = set()
    accepted = tuple(kind.strip() for kind in kinds if kind.strip())
    if not accepted:
        return None
    for kind in accepted:
        mapped = _ACCEPTED_KIND_TO_INTERNAL.get(kind)
        if mapped is None:
            raise ReviewError(
                message="unknown review kind",
                translated_message="review.operator.errors.unknown_kind",
                # Surface the accepted set in the refusal (CLI-instructive-gate
                # mandate) without echoing the raw selector, which may carry
                # operator-private text. ``accepted_kinds`` is a pre-joined
                # string because the i18n interpolation renders the value with
                # ``str(...)`` and a bare tuple would print as a Python repr.
                context={"accepted_kinds": ", ".join(ACCEPTED_KINDS)},
            )
        internal.update(mapped)
    return frozenset(internal)


def _row_matches(
    row: ReviewQueueRow,
    accepted_kinds: frozenset[str],
    accepted_source_kinds: frozenset[str],
) -> bool:
    kind_matches = not accepted_kinds or row.kind in accepted_kinds
    source_matches = not accepted_source_kinds or (
        row.source_kind is not None and row.source_kind in accepted_source_kinds
    )
    return kind_matches and source_matches


def _to_row(item: ReviewItem, *, state: ReviewState, bucket_id: str) -> ReviewQueueRow:
    if isinstance(item, TransactionReviewItem):
        return ReviewQueueRow(
            item_id=item.item_id,
            kind=BindingSourceKind.LEDGER_TRANSACTION,
            source_kind=BindingSourceKind.LEDGER_TRANSACTION,
            affected_object_id=item.source.transaction_id,
            bucket_id=bucket_id,
            modelo=item.modelo,
            period=_year_period(item.source.raw.booked_date.isoformat()),
            severity=item.severity,
            state=state,
            blocking=item.severity in {ReviewSeverity.CRITICAL, ReviewSeverity.HIGH},
            reason=_render_summary(item.summary),
            current_owner_surface="app ledger",
            canonical_next_command=item.drill_command,
            since=item.since,
            summary=_render_summary(item.summary),
        )
    if isinstance(item, InvoiceReviewItem):
        source_kind = (
            BindingSourceKind.COLLECTIBLE_INVOICE
            if item.source.kind.value == "issued"
            else BindingSourceKind.PAYABLE_INVOICE
        )
        return ReviewQueueRow(
            item_id=item.item_id,
            kind=source_kind,
            source_kind=source_kind,
            affected_object_id=item.source.invoice_id,
            bucket_id=bucket_id,
            modelo=item.modelo,
            period=_year_period(item.source.issued_at.isoformat()),
            severity=item.severity,
            state=state,
            blocking=item.severity in {ReviewSeverity.CRITICAL, ReviewSeverity.HIGH},
            reason=_render_summary(item.summary),
            current_owner_surface="app modelo",
            canonical_next_command=item.drill_command,
            since=item.since,
            summary=_render_summary(item.summary),
        )
    else:
        legal_refs = item.source.references_rules if item.source is not None else ()
        return ReviewQueueRow(
            item_id=item.item_id,
            kind="modelo_finding",
            # Carries the same token as ``kind``, exactly as the transaction and
            # invoice branches do. ``modelo_finding`` is advertised in
            # ``ACCEPTED_KINDS`` for both ``--kind`` and ``--source-kind``, and
            # ``_row_matches`` requires a non-None ``source_kind`` for a source
            # filter, so leaving it unset made a valid finding appear under
            # ``--kind modelo_finding`` and vanish under ``--source-kind
            # modelo_finding`` with no refusal or diagnostic.
            source_kind="modelo_finding",
            affected_object_id=item.draft_id,
            bucket_id=bucket_id,
            modelo=item.modelo,
            period=None,
            severity=item.severity,
            state=state,
            blocking=item.severity in {ReviewSeverity.CRITICAL, ReviewSeverity.HIGH},
            reason=_render_summary(item.summary),
            current_owner_surface="app modelo",
            canonical_next_command=item.drill_command,
            since=item.since,
            summary=_render_summary(item.summary),
            legal_refs=tuple(legal_refs),
        )


def _render_summary(value: str) -> str:
    rendered = tr(value)
    return rendered or value


def _active_bucket_id() -> str:
    from ...core.bucket_pointer import require_active_bucket_id

    return require_active_bucket_id()


def _year_period(value: str) -> str:
    return value[:7]
