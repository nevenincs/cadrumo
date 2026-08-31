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

from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, get_args, override

from pydantic import BaseModel, Field, TypeAdapter

from ...core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.directory_scan import scan_directory
from ...core.identity import ContentDigest
from ...domain.iva.classification import InvoiceKind
from ..operator_actions import PreconditionVerdict
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

if TYPE_CHECKING:
    from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ...core.config import Settings
    from ..provisioning import HardwareProfile
    from .evidence import PurchaseInvoiceEvidenceService
    from .evidence_draft import InvoiceDraft
    from .extraction_draft_store import StoredExtractionDraft

__all__ = [
    "BATCH_ITEM_STATUSES",
    "BatchItemResult",
    "BatchRunResult",
    "InferencePause",
    "UnresolvedBatchSource",
    "batch_item_identity",
    "order_batch_items",
    "order_batch_sources",
    "run_evidence_batch",
    "summarise_batch",
]

BatchItemStatus = Literal["ingested", "no_op", "refused", "pending_review", "paused"]
"""How one batch item ended.

``no_op`` is a success: the item was already ingested under this identity and
was neither re-read nor re-written. ``pending_review`` is neither a success nor
a failure — the item produced a draft an operator must adjudicate — so it does
not fail the run while still being visible in the summary.

``paused`` is the one status that means the work did NOT happen: the document
needs a reading model and the machine could not admit one. It is not a failure
of the document and carries no per-item refusal, because every paused item in a
run shares one cause; that cause is stated once on the run.
"""

_BATCH_ITEM_STATUS_ADAPTER: TypeAdapter[BatchItemStatus] = TypeAdapter(BatchItemStatus)

#: Every status a batch item can end in. Derived from the type rather than
#: restated, so a status added to the alias cannot go unreported in the summary.
#: Typed as the alias rather than as bare ``str`` so iterating it yields the
#: literal the consumers expect; each raw ``get_args`` member is revalidated
#: through the alias's own adapter rather than trusted as already-narrowed,
#: since ``get_args`` itself only returns ``tuple[Any, ...]``.
BATCH_ITEM_STATUSES: frozenset[BatchItemStatus] = frozenset(
    _BATCH_ITEM_STATUS_ADAPTER.validate_python(status) for status in get_args(BatchItemStatus)
)

#: The statuses that make a run "any item failed". Deliberately narrow: an item
#: awaiting review has not failed, and a no-op is the idempotent success.
FAILING_BATCH_ITEM_STATUSES: frozenset[BatchItemStatus] = frozenset({"refused"})

#: The statuses in which the document's work actually happened. Derived by
#: SUBTRACTION from the full set rather than listed, so a status added to the
#: alias must be classified as failing or paused to stay out of it -- a new
#: success-shaped status is counted as progress by construction rather than
#: silently omitted from the deterministic-progress figure.
COMPLETED_BATCH_ITEM_STATUSES: frozenset[BatchItemStatus] = (
    BATCH_ITEM_STATUSES - FAILING_BATCH_ITEM_STATUSES - {"paused"}
)


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
        refusal_verdict: The application-owned failed condition and its machine
            facts, present exactly when the item was refused. Carries what was
            seen rather than only that something failed, without retaining the
            producer's exception text.
        needed_inference: Whether this document required the inference lane at
            all. Carried per item because the run-level counts cannot be
            reconstructed afterwards: a completed row looks identical whether it
            was read deterministically or through a model, so a pooled "N
            completed" cannot say whether pacing worked or whether nothing was
            ever paced. Defaults to True, the conservative direction -- a row
            built without stating it is not counted as deterministic progress.
    """

    model_config = STRICT_FROZEN_CONFIG

    content_address: ContentDigest
    identity: str = Field(min_length=1)
    direction: InvoiceKind
    source_name: str = ""
    status: BatchItemStatus
    refusal_code: str | None = None
    refusal_verdict: PreconditionVerdict | None = None
    needed_inference: bool = True

    @override
    def model_post_init(self, _context: object) -> None:
        """Tie a refusal to the reason that justifies it, in both directions.

        A refused row with no code claims a failure it cannot explain, and a
        code under any other status marks an item as failed while reporting it
        as something else. Either way the summary and the rows would disagree.
        """
        refused = self.status == "refused"
        if refused and not self.refusal_code:
            raise ValueError("a refused batch item must carry the reason it was refused")
        if refused and self.refusal_verdict is None:
            raise ValueError("a refused batch item must carry the typed verdict explaining what was seen")
        if not refused and self.refusal_code:
            raise ValueError(f"refusal_code is only meaningful for a refused item; got status={self.status!r}")
        if not refused and self.refusal_verdict is not None:
            raise ValueError(f"refusal_verdict is only meaningful for a refused item; got status={self.status!r}")


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
        refusal_verdict: The application-owned failed condition and its machine
            facts for that same reason.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_name: str = Field(min_length=1)
    refusal_code: str = Field(min_length=1)
    refusal_verdict: PreconditionVerdict


class InferencePause(BaseModel):
    """The typed refusal that closed the run's inference lane.

    One record rather than a refusal stamped on every affected document. Every
    paused item in a run shares one cause — the machine could not admit a model —
    so N copies of it would be N identical messages an operator learns to scroll
    past, which is how a real refusal goes unread.

    ``facts`` and ``precondition_verdict`` are the application-owned provisioning
    outcome. This record deliberately does not restate a reason, rendered
    explanation, or recovery command: its consumer must resolve the exact verdict
    against the live operator surface.
    """

    model_config = STRICT_FROZEN_CONFIG

    facts: Mapping[str, str | int | bool] = Field(default_factory=dict)
    precondition_verdict: PreconditionVerdict


class BatchRunResult(BaseModel):
    """The whole run: every item's row, plus what they add up to.

    Attributes:
        items: One row per document, ordered by content address.
        unresolved: Sources whose bytes could not be read, so they never became
            items. Counted as failures.
        inference_pause: Present exactly when the inference lane closed.
        any_failed: Whether any item was refused. The exit status reads this,
            so a run that refused its first document and ingested the rest is a
            failed run that nonetheless did its work.
        any_deferred: Whether work remains that this run did not attempt.
    """

    model_config = STRICT_FROZEN_CONFIG

    items: tuple[BatchItemResult, ...] = ()
    unresolved: tuple[UnresolvedBatchSource, ...] = ()
    inference_pause: InferencePause | None = None

    @property
    def any_failed(self) -> bool:
        """Return whether any item was refused or any source was unreadable."""
        return bool(self.unresolved) or any(item.status in FAILING_BATCH_ITEM_STATUSES for item in self.items)

    @property
    def any_deferred(self) -> bool:
        """Return whether the run left work it did not attempt.

        Kept off :attr:`any_failed` rather than folded into it. A paused item is
        not a failure — nothing went wrong with the document and a re-run costs
        nothing, because completed items are no-ops. But it is not success
        either, and a caller automating this needs to tell "everything is done"
        from "the deterministic half is done", which one boolean cannot say.
        """
        return any(item.status == "paused" for item in self.items)

    def count_of(self, status: BatchItemStatus) -> int:
        """Return how many items ended in ``status``."""
        return sum(1 for item in self.items if item.status == status)

    @property
    def deterministic_completed(self) -> int:
        """Return how many items completed WITHOUT needing the inference lane.

        Reported separately from the paced count because together they are the
        evidence that pacing worked: deterministic progress continuing while
        inference-bearing work parks is the whole property. Pooled into one
        "completed" figure, a run that paced everything and a run that paced
        nothing read identically.

        "Completed" here is every ending that DID the work -- newly ingested,
        held for review, or already present from an earlier run. A held item
        was read; it is the finding that needs attention, not the reading.
        """
        return sum(
            1 for item in self.items if not item.needed_inference and item.status in COMPLETED_BATCH_ITEM_STATUSES
        )

    @property
    def paced(self) -> int:
        """Return how many items were parked because the inference lane closed.

        A zero here is only meaningful beside a non-zero elsewhere: a count that
        has never been shown able to rise is not a measurement.
        """
        return self.count_of("paused")

    @property
    def summary(self) -> dict[str, int]:
        """Return the per-status tally, every status present even at zero.

        A status missing from the summary reads as "not applicable" rather than
        "none occurred", and the two are different things to an operator looking
        for the refusals.
        """
        return {status: self.count_of(status) for status in sorted(BATCH_ITEM_STATUSES)}


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
    inference_pause: InferencePause | None = None,
) -> BatchRunResult:
    """Return the run result for ``items``, ordered by content address."""
    return BatchRunResult(
        items=order_batch_items(items),
        unresolved=tuple(sorted(unresolved, key=lambda source: source.source_name)),
        inference_pause=inference_pause,
    )


def _reads_without_a_model(data: bytes) -> bool:
    """Return whether these bytes carry a machine-readable record needing no model.

    Derived from the bytes through the one shared shape probe, never from the
    filename or the stored MIME type — a ZUGFeRD invoice and a photograph of a
    receipt are both ``application/pdf``, and the label cannot tell them apart.

    This deliberately does NOT reproduce the extractor's routing. It asks one
    question the shape probe already answers, and every other document is
    treated as possibly needing a model. A structured record whose payload turns
    out to be malformed falls through to a reading path inside the extractor and
    may then need one after all; that is the conservative direction, because the
    cost is a refusal the operator sees rather than a model load nobody admitted.
    """
    from ...adapters.inbound.einvoice import probe_document_shape
    from ...core import STRUCTURED_DOCUMENT_SHAPES

    return probe_document_shape(data) in STRUCTURED_DOCUMENT_SHAPES


class _InferenceLaneState:
    """Whether inference-bearing items may still be attempted in this run.

    Batch-wide rather than per item because both conditions that close it are
    batch-wide: memory pressure is a property of the machine and a missing
    reader is a property of the installation. Neither changes between two
    documents, so re-asking per item would re-derive one answer while the
    operator watched N identical refusals accumulate.

    The lane closes two ways, and the asymmetry is deliberate.

    **Measured contention closes it BEFORE any attempt.** Admission control
    exists precisely so an unsafe load is not attempted, so learning about it by
    attempting would defeat it.

    **A missing reader closes it AFTER the first attempt.** There is nothing
    unsafe about trying, no model is selected for admission to judge, and
    predicting which documents need a reader would mean reproducing the
    extractor's routing here — a second copy that would drift. One document pays
    for the discovery and every later one is paused on it.
    """

    __slots__ = ("_assessed", "_pause", "_profile", "_reader_probed", "_settings")

    def __init__(self, *, settings: Settings, profile: HardwareProfile | None = None) -> None:
        self._settings = settings
        self._profile = profile
        self._assessed = False
        self._reader_probed = False
        self._pause: InferencePause | None = None

    def admits(self, *, deterministic: bool) -> bool:
        """Return whether this item may be attempted, measuring contention once.

        A document that reads without a model is always attempted: a closed lane
        says nothing about work that never needed the lane.
        """
        if deterministic:
            return True
        if not self._assessed:
            self._assessed = True
            self._pause = _assess_model_load_contention_once(self._settings, profile=self._profile)
        return self._pause is None

    def close_if_no_reader_is_available(self) -> None:
        """Close the lane when a refusal turns out to be the environment's, not the document's.

        Asks the runtime whether a reader is actually there, rather than reading
        an error string. A measurement answers the question the same way for
        every reader path and hands the exact provisioning outcome downstream.

        Probed at most once, and only after something has already refused, so a
        healthy run never pays for it.
        """
        if self._pause is not None or self._reader_probed:
            return
        self._reader_probed = True
        from ...application.provisioning import probe_ollama_vision

        status = probe_ollama_vision(self._settings)
        if status.available:
            return
        self._pause = _inference_pause(
            facts=status.facts,
            precondition_verdict=status.precondition_verdict,
        )

    def pause(self) -> InferencePause | None:
        """Return the pause record, or ``None`` when the lane never closed."""
        return self._pause


def _assess_model_load_contention_once(
    settings: Settings,
    *,
    profile: HardwareProfile | None = None,
) -> InferencePause | None:
    """Return the contention pause, or ``None`` when a load may be attempted.

    Provisioning never raises; it returns a snapshot with exact facts and a
    failed-condition verdict. This module forwards that typed outcome unchanged
    instead of constructing an instruction from a contention cause.

    A role with no selectable model is deliberately NOT a pause. Nothing is
    unsafe about attempting it, and the extractor's own refusal names the
    provisioning verb far more precisely than a guess made here could.
    """
    from ...application.provisioning import assess_model_load_contention, select_model_for_role
    from ...core.model_catalogue import ModelRole

    for role in (ModelRole.TEXT_EXTRACTION, ModelRole.VISION_TRANSCRIPTION):
        assessable = select_model_for_role(role, profile=profile).assessable_load
        if assessable is None:
            continue
        runtime_id, required_bytes = assessable
        snapshot = assess_model_load_contention(
            runtime_id,
            required_bytes,
            profile=profile,
            settings=settings,
        )
        if not snapshot.admitted:
            return _inference_pause(
                facts=snapshot.facts,
                precondition_verdict=snapshot.precondition_verdict,
            )
    return None


def _inference_pause(
    *,
    facts: Mapping[str, str | int | bool],
    precondition_verdict: PreconditionVerdict | None,
) -> InferencePause:
    """Build a pause only from a producer-owned refusal outcome."""
    if precondition_verdict is None:
        raise ValueError("inference_pause_requires_precondition_verdict")
    return InferencePause(facts=facts, precondition_verdict=precondition_verdict)


#: Names the function that produced a batch draft, not the reader that read it.
#: Which reader ran is a PER-FIELD fact and is already carried by the draft's
#: own ``provenance`` envelopes (``FieldOrigin``); a document-level extractor
#: label claiming one reader for a draft assembled from several would be the
#: laundering those envelopes exist to prevent.
BATCH_DRAFT_EXTRACTOR = "extract_invoice_draft_from_evidence"

#: Transports that carried a batch reading, recorded beside the draft.
#: On-host is not assumed here, it is DERIVED from an enforced refusal: an
#: evidence-derived request may only reach an off-host provider carrying a
#: per-invocation consent token, the dispatch refuses without one, and this
#: path mints none and accepts none. So no batch read can have left the host,
#: and recording that is an observation about the gate rather than a guess
#: about configuration.
#:
#: The moment this path gains a consent token, this constant stops being the
#: right answer and must become a function of that token -- which is why it is
#: named for what it asserts rather than inlined at the write site.
BATCH_READ_TRANSPORTS: Final[tuple[str, ...]] = (LOCAL_TRANSPORT_LABEL,)


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
            resolved.extend(child for child in scan_directory(path) if child.is_file())
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
    profile: HardwareProfile | None = None,
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
        profile: Measured hardware the admission check judges against; probed
            when omitted. The same injection point the admission primitive
            itself exposes, so a contended machine can be exercised from real
            measurements rather than by substituting the decision.

    Returns:
        :class:`BatchRunResult`: Every row, ordered by content address.
    """
    from ...core.config import load_settings as _load_settings
    from ...core.hashing import sha256_hex
    from .evidence import PurchaseInvoiceEvidenceService
    from .evidence_draft import extract_invoice_draft_from_evidence
    from .extraction_draft_store import read_extraction_draft, write_extraction_draft

    resolved_settings = settings or _load_settings()
    service = PurchaseInvoiceEvidenceService(
        settings=resolved_settings,
        bucket_event_repository=bucket_event_repository,
    )

    addressed: dict[tuple[str, str], Path] = {}
    deterministic: set[str] = set()
    unresolved: list[UnresolvedBatchSource] = []
    for path in _batch_sources(sources):
        try:
            # Read to hash and to probe the shape, then released. The bytes are
            # re-read per item at work time rather than held: a folder of
            # documents held in memory at once is unbounded, and spilling them
            # anywhere would be the spool file this design exists without.
            data = path.read_bytes()
        except OSError as exc:
            unresolved.append(
                UnresolvedBatchSource(
                    source_name=str(path),
                    refusal_code="unreadable_source",
                    refusal_verdict=ledger_no_recovery_verdict(
                        LedgerPreconditionCondition.EVIDENCE_FILE_READABLE,
                        facts={
                            "source_name": path.name,
                            "file_readable": False,
                            "read_error_type": exc.__class__.__name__,
                        },
                    ),
                ),
            )
            continue
        content_address = sha256_hex(data)
        if _reads_without_a_model(data):
            deterministic.add(content_address)
        addressed[(content_address, str(path))] = path

    lane = _InferenceLaneState(settings=resolved_settings, profile=profile)
    rows: list[BatchItemResult] = []
    for content_address, source_name in order_batch_sources(addressed):
        path = addressed[(content_address, source_name)]
        reads_without_a_model = content_address in deterministic
        if not lane.admits(deterministic=reads_without_a_model):
            # Paused, not refused: the document is fine and the work simply has
            # not happened. One run-level explanation carries the reason, rather
            # than stamping N identical refusals onto N innocent documents.
            row = BatchItemResult(
                content_address=content_address,
                identity=batch_item_identity(content_address=content_address, direction=direction),
                direction=direction,
                source_name=path.name,
                status="paused",
                needed_inference=True,
            )
        else:
            row = _ingest_one_batch_item(
                needed_inference=not reads_without_a_model,
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
            if row.status == "refused":
                lane.close_if_no_reader_is_available()
        rows.append(row)
        if on_item is not None:
            # Progress reporting is incidental to the run; a sink that fails
            # must not cost the operator results already produced.
            with suppress(Exception):
                on_item(row)

    return summarise_batch(rows, unresolved, lane.pause())


def _refusal_verdict(
    exc: Exception,
    *,
    code: str,
    condition: LedgerPreconditionCondition,
) -> PreconditionVerdict:
    """Return the typed refusal for one failed document, never its exception text.

    A producer that already owns a typed verdict keeps it verbatim, so the row
    carries the exact failed condition the reader established rather than this
    runner's re-reading of it. Only a producer with no verdict falls back to the
    stage's own condition, and then the error's registered type -- not its
    message -- is the fact that survives.
    """
    owned = getattr(exc, "terminal_precondition_verdict", None)
    if isinstance(owned, PreconditionVerdict):
        return owned
    return ledger_no_recovery_verdict(
        condition,
        facts={
            "refusal_code": code,
            "producer_error_type": exc.__class__.__name__,
        },
    )


# reason: every collaborator is an explicit seam; binding them ambiently is what
# makes a batch runner untestable without reaching into module globals.
def _ingest_one_batch_item(
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
    needed_inference: bool = True,
) -> BatchItemResult:
    """Run one document all the way through, returning its row and never raising.

    ``needed_inference`` is passed in rather than re-derived here: the shape
    probe already ran once over the bytes at planning time, and asking again
    would re-read the document and risk the two answers disagreeing.
    """
    identity = batch_item_identity(content_address=content_address, direction=direction)

    def refused(code: str, exc: Exception, *, condition: LedgerPreconditionCondition) -> BatchItemResult:
        return BatchItemResult(
            content_address=content_address,
            identity=identity,
            direction=direction,
            source_name=path.name,
            status="refused",
            refusal_code=code,
            refusal_verdict=_refusal_verdict(exc, code=code, condition=condition),
            needed_inference=needed_inference,
        )

    try:
        attached = service.add(bucket_id=bucket_id, source_path=path, idempotency_key=identity)
    except Exception as exc:  # reason: one document's failure is its own row, never the run's end.
        return refused(
            "evidence_refused",
            exc,
            condition=LedgerPreconditionCondition.EVIDENCE_DOCUMENT_BYTES_AVAILABLE,
        )

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
            needed_inference=needed_inference,
        )

    try:
        draft = extract(bucket_id=bucket_id, evidence_id=evidence_id, settings=settings)
    except Exception as exc:  # reason: an unreadable document is a refusal row, not a dead run.
        return refused(
            "not_readable",
            exc,
            condition=LedgerPreconditionCondition.EVIDENCE_BYTES_READABLE,
        )

    try:
        write_draft(
            bucket_id=bucket_id,
            evidence_reference=evidence_id,
            draft=draft,
            extractor=BATCH_DRAFT_EXTRACTOR,
            read_transports=BATCH_READ_TRANSPORTS,
            settings=settings,
        )
    except Exception as exc:  # reason: a draft that could not be stored is this item's refusal.
        return refused(
            "draft_not_stored",
            exc,
            condition=LedgerPreconditionCondition.EVIDENCE_DOCUMENT_BYTES_AVAILABLE,
        )

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
        needed_inference=needed_inference,
    )
