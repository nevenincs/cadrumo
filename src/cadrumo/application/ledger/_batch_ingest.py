"""Per-item truth for a bounded batch ingestion run.

A batch is a bounded run over a known set of documents, not a queue and not a
background job. What makes it safe to point at a folder is that **one bad
document cannot end the run**: every item finishes in a typed row of its own —
ingested, a no-op, refused with its reason, or held for review — and the run
reports the list plus a summary. The exit status reflects "any item failed",
never "the first item failed".

That distinction is not theoretical here. The adjacent statement-import folder
path runs its per-file imports in a bare comprehension with no per-item guard,
so the first file that raises discards every result already produced. This
module exists so the evidence batch cannot acquire the same shape.

Two properties make a re-run safe rather than merely tolerable:

**Ordering is by content address**, so two runs over the same documents report
in the same order no matter how the filesystem enumerated them. A report whose
row order depended on directory iteration could not be diffed against the
previous run, which is the first thing an operator does after a partial batch.

**Identity is content address plus declared direction.** The same bytes filed as
issued and as received are genuinely two records — one is a sale, the other a
purchase — so the direction has to be in the key. The address alone would
collapse them; a clock or a filename would make a re-run mint duplicates.
Because the key is derived rather than stored, resume after a crash *is*
re-run: there is no journal format to invent, and no progress file to leave on
disk.

See Also:
    :class:`~domain.iva.InvoiceKind`
        The declared direction that, with the content address, forms identity.
    :class:`~domain.attachments.Attachment`
        Where the content address comes from: the SHA-256 of the stored bytes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...domain.iva import InvoiceKind

if TYPE_CHECKING:
    from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ...core.config import Settings
    from ._evidence import PurchaseInvoiceEvidenceService
    from ._evidence_draft import InvoiceDraft
    from ._extraction_draft_store import StoredExtractionDraft

__all__ = [
    "BATCH_ITEM_STATUSES",
    "BatchItemResult",
    "BatchRunResult",
    "UnresolvedBatchSource",
    "batch_item_identity",
    "order_batch_items",
    "order_batch_sources",
    "run_evidence_batch",
    "summarise_batch",
]

BatchItemStatus = Literal["ingested", "no_op", "refused", "pending_review"]
"""How one batch item ended.

``no_op`` is a success: the item was already ingested under this identity and
was neither re-read nor re-written. ``pending_review`` is neither a success nor
a failure — the item produced a draft an operator must adjudicate — so it does
not fail the run while still being visible in the summary.
"""

#: Every status a batch item can end in. Derived from the type rather than
#: restated, so a status added to the alias cannot go unreported in the summary.
BATCH_ITEM_STATUSES: frozenset[str] = frozenset(BatchItemStatus.__args__)

#: The statuses that make a run "any item failed". Deliberately narrow: an item
#: awaiting review has not failed, and a no-op is the idempotent success.
FAILING_BATCH_ITEM_STATUSES: frozenset[str] = frozenset({"refused"})


class BatchItemResult(BaseModel):
    """What happened to exactly one document in the run.

    Attributes:
        content_address: SHA-256 of the document's bytes, lowercase hex. The
            item's position in the report and half of its identity.
        identity: Content address plus declared direction. Two runs over the
            same document with the same direction derive the same value, which
            is what makes a re-run a no-op rather than a duplicate.
        direction: The direction the operator declared for the run.
        source_name: The document's own name, carried for the operator's benefit
            only — never for identity, because a rename must not mint a second
            record.
        status: How the item ended.
        refusal_code: Machine-readable reason, present exactly when the item was
            refused.
        refusal_detail: The same reason in operator-facing terms, naming what
            was seen rather than only that something failed.
    """

    model_config = STRICT_FROZEN_CONFIG

    content_address: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    identity: str = Field(min_length=1)
    direction: InvoiceKind
    source_name: str = ""
    status: BatchItemStatus
    refusal_code: str | None = None
    refusal_detail: str | None = None

    def model_post_init(self, _context: object) -> None:
        """Tie a refusal to the reason that justifies it, in both directions.

        A refused row with no code claims a failure it cannot explain, and a
        code under any other status marks an item as failed while reporting it
        as something else. Either way the summary and the rows would disagree.
        """
        refused = self.status == "refused"
        if refused and not self.refusal_code:
            raise ValueError("a refused batch item must carry the reason it was refused")
        if not refused and self.refusal_code:
            raise ValueError(f"refusal_code is only meaningful for a refused item; got status={self.status!r}")


class UnresolvedBatchSource(BaseModel):
    """A submitted source whose bytes could not be read at all.

    Deliberately not a :class:`BatchItemResult`. An item's identity IS its
    content address, and a file that cannot be read has no content address to
    derive one from — giving it a placeholder would put a value into the field
    that ordering and idempotency both key on, and a second unreadable file
    would then collide with the first. Reporting it in its own channel keeps
    the item rows identity-bearing while still putting the failure in front of
    the operator, which dropping it silently would not.

    Attributes:
        source_name: The source as the operator named it.
        refusal_code: Machine-readable reason the bytes could not be read.
        refusal_detail: The same reason in operator-facing terms.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_name: str = Field(min_length=1)
    refusal_code: str = Field(min_length=1)
    refusal_detail: str = Field(min_length=1)


class BatchRunResult(BaseModel):
    """The whole run: every item's row, plus what they add up to.

    Attributes:
        items: One row per document, ordered by content address.
        unresolved: Sources whose bytes could not be read, so they never became
            items. Counted as failures.
        any_failed: Whether any item was refused. The exit status reads this,
            so a run that refused its first document and ingested the rest is a
            failed run that nonetheless did its work.
    """

    model_config = STRICT_FROZEN_CONFIG

    items: tuple[BatchItemResult, ...] = ()
    unresolved: tuple[UnresolvedBatchSource, ...] = ()

    @property
    def any_failed(self) -> bool:
        """Return whether any item was refused or any source was unreadable."""
        return bool(self.unresolved) or any(item.status in FAILING_BATCH_ITEM_STATUSES for item in self.items)

    def count_of(self, status: BatchItemStatus) -> int:
        """Return how many items ended in ``status``."""
        return sum(1 for item in self.items if item.status == status)

    @property
    def summary(self) -> dict[str, int]:
        """Return the per-status tally, every status present even at zero.

        A status missing from the summary reads as "not applicable" rather than
        "none occurred", and the two are different things to an operator looking
        for the refusals.
        """
        return {status: self.count_of(status) for status in sorted(BATCH_ITEM_STATUSES)}  # type: ignore[arg-type]  # CAST-RATIONALE-LITERAL-ITERATION: BATCH_ITEM_STATUSES is derived from the BatchItemStatus alias, so every member is a valid argument.


def batch_item_identity(*, content_address: str, direction: InvoiceKind) -> str:
    """Return the identity of one batch item.

    Derived from the document's bytes and the direction declared for it, and
    from nothing else. No clock, no filename, no run identifier: each of those
    would differ between two runs over the same document and turn an idempotent
    re-run into a duplicate write.

    The direction is part of the key rather than an attribute beside it because
    the same bytes filed as issued and as received are two genuinely different
    records — a sale and a purchase — and collapsing them would silently drop
    one.

    Args:
        content_address: Lowercase hex SHA-256 of the document's bytes.
        direction: The direction declared for this run.

    Returns:
        The identity string.
    """
    return f"{direction.value}:{content_address}"


def order_batch_items(items: Iterable[BatchItemResult]) -> tuple[BatchItemResult, ...]:
    """Return ``items`` ordered by content address.

    Deterministic by construction, so two runs over the same documents report in
    the same order regardless of how the filesystem enumerated them. Direction
    breaks a tie, which can only arise when the same bytes were submitted under
    both directions in one run.
    """
    return tuple(sorted(items, key=lambda item: (item.content_address, item.direction.value)))


def order_batch_sources(sources: Iterable[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    """Return ``(content_address, source_name)`` pairs ordered by content address.

    The same ordering rule applied before any work happens, so the run PROCESSES
    in report order too. Ordering only the finished rows would still leave the
    processing order — and therefore which items a interrupted run completed —
    dependent on directory enumeration.
    """
    return tuple(sorted(sources, key=lambda pair: (pair[0], pair[1])))


def summarise_batch(
    items: Sequence[BatchItemResult],
    unresolved: Sequence[UnresolvedBatchSource] = (),
) -> BatchRunResult:
    """Return the run result for ``items``, ordered by content address."""
    return BatchRunResult(
        items=order_batch_items(items),
        unresolved=tuple(sorted(unresolved, key=lambda source: source.source_name)),
    )


#: Names the function that produced a batch draft, not the reader that read it.
#: Which reader ran is a PER-FIELD fact and is already carried by the draft's
#: own ``provenance`` envelopes (``FieldOrigin``); a document-level extractor
#: label claiming one reader for a draft assembled from several would be the
#: laundering those envelopes exist to prevent.
BATCH_DRAFT_EXTRACTOR = "extract_invoice_draft_from_evidence"


def _batch_sources(sources: Iterable[Path | str]) -> tuple[Path, ...]:
    """Expand each submitted source to the files it names.

    A directory contributes the files directly inside it. Enumeration order is
    irrelevant and deliberately not relied on: every caller downstream sorts by
    content address, so this only has to be complete.
    """
    resolved: list[Path] = []
    for source in sources:
        path = Path(source).expanduser()
        if path.is_dir():
            resolved.extend(child for child in path.iterdir() if child.is_file())
        else:
            resolved.append(path)
    return tuple(resolved)


def run_evidence_batch(
    *,
    bucket_id: str,
    sources: Iterable[Path | str],
    direction: InvoiceKind,
    settings: Settings | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    on_item: Callable[[BatchItemResult], None] | None = None,
) -> BatchRunResult:
    """Run the ingestion pipeline over every source, one typed row each.

    **No item can end the run.** Every per-item failure is caught and becomes
    that item's refusal row, because the alternative — the shape the adjacent
    statement-import folder path still has — discards every result already
    produced when the first document raises.

    **A re-run is the resume.** Each item's identity is its content address plus
    the declared direction, handed to the evidence store's idempotency guard, so
    a second run over the same folder re-attaches nothing and emits no second
    lifecycle event. An item counts as complete only when its evidence AND its
    draft are both present: evidence-without-draft is exactly the state an
    interrupted or environment-refused first run leaves behind, and treating it
    as done would strand that document permanently, never retried and reported
    as an untroubled no-op.

    **Nothing is written outside secure storage.** The two writes are the
    encrypted evidence record and the encrypted draft. There is no spool, no
    journal and no progress file — which is what makes "resume is re-run" a
    property rather than a slogan, since there is no local state to go stale
    (``sensitive-financial-data-secure-storage-only``).

    Args:
        bucket_id: Ledger bucket every record is written into.
        sources: Files and directories to ingest.
        direction: The direction declared for the whole run. Part of each
            item's identity, so the same document filed both ways is two
            records rather than one.
        settings: Resolved ``Settings``; ``load_settings()`` when omitted, so
            ``override_settings()`` is honoured.
        bucket_event_repository: Repository the evidence lifecycle events are
            appended to.
        on_item: Called with each row as it completes, for progress reporting.
            A raising callback must not lose the run, so it is guarded like any
            other per-item failure.

    Returns:
        :class:`BatchRunResult`: Every row, ordered by content address.
    """
    from ...core.config import load_settings as _load_settings
    from ...core.hashing import sha256_hex
    from ._evidence import PurchaseInvoiceEvidenceService
    from ._evidence_draft import extract_invoice_draft_from_evidence
    from ._extraction_draft_store import read_extraction_draft, write_extraction_draft

    resolved_settings = settings or _load_settings()
    service = PurchaseInvoiceEvidenceService(
        settings=resolved_settings,
        bucket_event_repository=bucket_event_repository,
    )

    addressed: dict[tuple[str, str], Path] = {}
    unresolved: list[UnresolvedBatchSource] = []
    for path in _batch_sources(sources):
        try:
            # Read to hash, then released. The bytes are re-read per item at
            # work time rather than held: a folder of documents held in memory
            # at once is unbounded, and spilling them anywhere would be the
            # spool file this design exists without.
            content_address = sha256_hex(path.read_bytes())
        except OSError as exc:
            unresolved.append(
                UnresolvedBatchSource(
                    source_name=str(path),
                    refusal_code="unreadable_source",
                    refusal_detail=f"could not read {path.name}: {exc.strerror or exc}",
                ),
            )
            continue
        addressed[(content_address, str(path))] = path

    rows: list[BatchItemResult] = []
    for content_address, source_name in order_batch_sources(addressed):
        path = addressed[(content_address, source_name)]
        row = _ingest_one_batch_item(
            bucket_id=bucket_id,
            path=path,
            content_address=content_address,
            direction=direction,
            settings=resolved_settings,
            service=service,
            extract=extract_invoice_draft_from_evidence,
            read_draft=read_extraction_draft,
            write_draft=write_extraction_draft,
        )
        rows.append(row)
        if on_item is not None:
            try:
                on_item(row)
            except Exception:  # noqa: BLE001, S110  # reason: progress reporting must never cost the run its results.
                pass

    return summarise_batch(rows, unresolved)


def _ingest_one_batch_item(  # noqa: PLR0913  # reason: every collaborator is an explicit seam; binding them ambiently is what makes a batch untestable.
    *,
    bucket_id: str,
    path: Path,
    content_address: str,
    direction: InvoiceKind,
    settings: Settings,
    service: PurchaseInvoiceEvidenceService,
    extract: Callable[..., InvoiceDraft],
    read_draft: Callable[..., StoredExtractionDraft | None],
    write_draft: Callable[..., object],
) -> BatchItemResult:
    """Run one document all the way through, returning its row and never raising."""
    identity = batch_item_identity(content_address=content_address, direction=direction)

    def refused(code: str, detail: str) -> BatchItemResult:
        return BatchItemResult(
            content_address=content_address,
            identity=identity,
            direction=direction,
            source_name=path.name,
            status="refused",
            refusal_code=code,
            refusal_detail=detail,
        )

    try:
        attached = service.add(bucket_id=bucket_id, source_path=path, idempotency_key=identity)
    except Exception as exc:  # noqa: BLE001  # reason: one document's failure is its own row, never the run's end.
        return refused("evidence_refused", str(exc))

    evidence_id = attached.record.evidence_id
    # An empty event tuple is the store's guarded-no-op signal. It alone is not
    # completion: a first run that attached the evidence and then failed to read
    # it leaves exactly this state, and calling it done would strand the
    # document forever behind a row that reports no trouble.
    already_drafted = read_draft(bucket_id=bucket_id, evidence_reference=evidence_id, settings=settings) is not None
    if not attached.bucket_event_ids and already_drafted:
        return BatchItemResult(
            content_address=content_address,
            identity=identity,
            direction=direction,
            source_name=path.name,
            status="no_op",
        )

    try:
        draft = extract(bucket_id=bucket_id, evidence_id=evidence_id, settings=settings)
    except Exception as exc:  # noqa: BLE001  # reason: an unreadable document is a refusal row, not a dead run.
        return refused("not_readable", str(exc))

    try:
        write_draft(
            bucket_id=bucket_id,
            evidence_reference=evidence_id,
            draft=draft,
            extractor=BATCH_DRAFT_EXTRACTOR,
            settings=settings,
        )
    except Exception as exc:  # noqa: BLE001  # reason: a draft that could not be stored is this item's refusal.
        return refused("draft_not_stored", str(exc))

    # A draft carrying an unresolved finding is held rather than reported clean.
    # Batch never confirms anything either way; the distinction tells the
    # operator which documents need their attention first.
    held = bool(draft.discrepancies) or any(envelope.candidates for envelope in draft.provenance)
    return BatchItemResult(
        content_address=content_address,
        identity=identity,
        direction=direction,
        source_name=path.name,
        status="pending_review" if held else "ingested",
    )
