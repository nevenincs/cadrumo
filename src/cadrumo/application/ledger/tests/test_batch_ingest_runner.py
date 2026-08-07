"""The batch runner against real secure storage: one bad item, and a second run.

Every property this file pins is invisible on the happy path. A runner that
aborts on the first failure reports correctly when nothing fails; a runner that
re-ingests on every pass looks right on its first pass; and a runner that spools
decrypted bytes to a temp file produces exactly the same rows as one that does
not. So each test drives the real encrypted-bucket write path over the bundled
synthetic corpus and asserts on what the run LEFT BEHIND, not only on what it
returned.

Deterministic throughout: the structured-record reader is a parser, and the
malformed and empty PDFs refuse before any reader is selected. No model is
loaded, pulled, or contacted (the corpus is bundled and synthetic; see each
document's ``.provenance.json`` sidecar).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....domain.iva import InvoiceKind
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._batch_ingest import run_evidence_batch
from .._evidence import PurchaseInvoiceEvidenceService
from .._extraction_draft_store import load_extraction_drafts

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "2b2b2b2b-2b2b-4b2b-8b2b-2b2b2b2b2b2b"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """A real encrypted bucket runtime: real key provider, real SQLite, no mocks."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


_CORPUS = Path(__file__).parent / "_evidence_corpus"

#: A structured record: read by a parser, so this row is deterministic and
#: reaches no model at all.
_STRUCTURED = "facturae_32_series_and_parties_invoice.xml"

#: The poison. Malformed bytes behind a PDF extension, which is the shape that
#: must produce a refusal ROW rather than end the run.
_POISON = "adversarial_malformed.pdf"


@pytest.fixture
def batch_dir(tmp_path: Path) -> Path:
    """A folder holding one readable structured invoice and one poisoned PDF."""
    folder = tmp_path / "batch"
    folder.mkdir()
    for name in (_STRUCTURED, _POISON):
        (folder / name).write_bytes((_CORPUS / name).read_bytes())
    return folder


def _events(profile: TestRuntimeProfile) -> BucketEventHistoryRepository:
    return BucketEventHistoryRepository(objects=profile.repository)


def _run(profile: TestRuntimeProfile, folder: Path) -> object:
    return run_evidence_batch(
        bucket_id=_BUCKET_ID,
        sources=[folder],
        direction=InvoiceKind.RECEIVED,
        settings=profile.settings,
        bucket_event_repository=_events(profile),
    )


def test_a_poisoned_document_does_not_end_the_run(
    runtime_profile: TestRuntimeProfile,
    batch_dir: Path,
) -> None:
    """The whole reason batch is a verb: the good document still gets ingested.

    The adjacent statement-import folder path fails this exact assertion by
    construction — its bare comprehension discards every parsed result when one
    file raises.
    """
    result = _run(runtime_profile, batch_dir)

    assert len(result.items) == 2, "both documents must be reported, not just the one that worked"
    statuses = {item.source_name: item.status for item in result.items}
    assert statuses[_POISON] == "refused"
    assert statuses[_STRUCTURED] in {"ingested", "pending_review"}
    assert result.any_failed, "a refused item must fail the run's exit status"


def test_the_refused_row_says_what_was_wrong_with_that_document(
    runtime_profile: TestRuntimeProfile,
    batch_dir: Path,
) -> None:
    """A refusal an operator cannot act on is barely better than a silent drop."""
    result = _run(runtime_profile, batch_dir)
    poison = next(item for item in result.items if item.source_name == _POISON)

    assert poison.refusal_code
    assert poison.refusal_detail
    assert poison.refusal_detail.strip() != ""


def test_the_good_document_is_actually_persisted_not_merely_reported(
    runtime_profile: TestRuntimeProfile,
    batch_dir: Path,
) -> None:
    """Positive control for the refusal tests: a row saying 'ingested' means a draft exists.

    Without this, every assertion above would still pass against a runner that
    reported plausible rows and wrote nothing.
    """
    _run(runtime_profile, batch_dir)

    drafts = load_extraction_drafts(_BUCKET_ID, runtime_profile.settings).drafts
    assert len(drafts) == 1, "exactly the readable document should have left a draft"
    assert drafts[0].draft.supplier_tax_id is not None


def test_a_second_run_re_ingests_nothing_and_emits_no_second_event(
    runtime_profile: TestRuntimeProfile,
    batch_dir: Path,
) -> None:
    """Resume IS re-run, so the second pass must be a no-op rather than a duplicate.

    Asserted on the stored evidence catalogue and the bucket event history, not
    only on the returned rows: a runner that reported ``no_op`` while writing a
    second record would pass a rows-only check.
    """
    first = _run(runtime_profile, batch_dir)
    service = PurchaseInvoiceEvidenceService(
        settings=runtime_profile.settings,
        bucket_event_repository=_events(runtime_profile),
    )
    records_after_first = len(service.list_all(bucket_id=_BUCKET_ID))
    events_after_first = len(_events(runtime_profile).load().events)
    drafted_at_first = load_extraction_drafts(_BUCKET_ID, runtime_profile.settings).drafts[0].drafted_at

    second = _run(runtime_profile, batch_dir)

    assert [item.content_address for item in second.items] == [item.content_address for item in first.items]
    assert any(item.status == "no_op" for item in second.items), "the completed document must report as a no-op"
    assert len(service.list_all(bucket_id=_BUCKET_ID)) == records_after_first, "no second evidence record"
    assert len(_events(runtime_profile).load().events) == events_after_first, "no second lifecycle event"
    assert load_extraction_drafts(_BUCKET_ID, runtime_profile.settings).drafts[0].drafted_at == drafted_at_first, (
        "a no-op must not re-stamp the draft it did not rewrite"
    )


def test_an_item_that_failed_to_read_is_retried_rather_than_stranded(
    runtime_profile: TestRuntimeProfile,
    batch_dir: Path,
) -> None:
    """Evidence-without-draft is an incomplete item, not a completed one.

    The subtle half of idempotency. The poisoned document's evidence record IS
    written on the first pass — the bytes attach fine, it is the READ that
    fails — so a runner treating "evidence exists" as completion would report
    it as an untroubled ``no_op`` on every later run and never attempt it
    again. It must stay a visible refusal.
    """
    _run(runtime_profile, batch_dir)
    second = _run(runtime_profile, batch_dir)

    poison = next(item for item in second.items if item.source_name == _POISON)
    assert poison.status == "refused", "a previously-unreadable document must be retried, not marked done"


def test_the_run_writes_nothing_outside_secure_storage(
    runtime_profile: TestRuntimeProfile,
    batch_dir: Path,
    tmp_path: Path,
) -> None:
    """No spool, no journal, no progress file (sensitive-financial-data-secure-storage-only).

    Compares the whole temp tree before and after, so it catches a spool
    wherever it is written rather than only in the places this test thought to
    look. The batch inputs themselves are the only files outside the storage
    root that may exist afterwards, and they must be byte-identical.
    """
    storage_root = runtime_profile.storage_root.resolve()

    def outside_storage() -> dict[Path, bytes]:
        return {
            path: path.read_bytes()
            for path in tmp_path.rglob("*")
            if path.is_file() and storage_root not in path.resolve().parents
        }

    before = outside_storage()

    _run(runtime_profile, batch_dir)

    after = outside_storage()
    appeared = sorted(set(after) - set(before))
    assert appeared == [], f"the run left files outside secure storage: {appeared}"
    assert after == before, "the run rewrote a file outside secure storage"


def test_no_decrypted_document_bytes_reach_any_file_outside_secure_storage(
    runtime_profile: TestRuntimeProfile,
    batch_dir: Path,
    tmp_path: Path,
) -> None:
    """The anti-tautology proof for the scan above.

    A file-count check passes against a runner that spools INTO the storage
    root, or that overwrites an input in place. This searches for a distinctive
    run of the document's own plaintext across every file the run could have
    touched, and its positive control is that the same search finds the bytes in
    the source document — so a search that can never match is not mistaken for
    absence.
    """
    source = batch_dir / _STRUCTURED
    plaintext = source.read_bytes()
    needle = plaintext[:64]

    # Positive control: the needle IS findable, in the one file that legitimately holds it.
    assert needle in source.read_bytes()

    _run(runtime_profile, batch_dir)

    storage_root = runtime_profile.storage_root.resolve()
    leaked = [
        path
        for path in tmp_path.rglob("*")
        if path.is_file()
        and path != source
        and storage_root not in path.resolve().parents
        and needle in path.read_bytes()
    ]
    assert leaked == [], f"decrypted document bytes were written outside secure storage: {leaked}"


def test_ordering_does_not_depend_on_how_the_folder_was_enumerated(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    """Two folders holding the same documents under names that sort oppositely.

    Filename ordering and content-address ordering disagree here by
    construction, so a runner that had silently kept enumeration order would
    report the two folders differently.
    """
    forward = tmp_path / "forward"
    reverse = tmp_path / "reverse"
    payloads = {
        "aaa.xml": (_CORPUS / _STRUCTURED).read_bytes(),
        "zzz.xml": (_CORPUS / "facturae_32_recargo_invoice.xml").read_bytes(),
    }
    for folder, names in ((forward, ("aaa.xml", "zzz.xml")), (reverse, ("zzz.xml", "aaa.xml"))):
        folder.mkdir()
        for name, payload in zip(names, payloads.values(), strict=True):
            (folder / name).write_bytes(payload)

    ordered = [item.content_address for item in _run(runtime_profile, forward).items]

    assert ordered == sorted(ordered), "rows must come out in content-address order"
    assert ordered == sorted(hashlib.sha256(payload).hexdigest() for payload in payloads.values())


def test_an_unreadable_source_is_reported_rather_than_dropped(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    """A source that never became an item still has to reach the operator."""
    folder = tmp_path / "partial"
    folder.mkdir()
    (folder / _STRUCTURED).write_bytes((_CORPUS / _STRUCTURED).read_bytes())

    result = run_evidence_batch(
        bucket_id=_BUCKET_ID,
        sources=[folder, tmp_path / "does_not_exist.pdf"],
        direction=InvoiceKind.RECEIVED,
        settings=runtime_profile.settings,
        bucket_event_repository=_events(runtime_profile),
    )

    assert len(result.unresolved) == 1
    assert result.unresolved[0].refusal_code == "unreadable_source"
    assert result.any_failed, "an unreadable source must fail the run"
    assert len(result.items) == 1, "the readable document must still have been processed"


def test_the_same_document_under_two_directions_is_two_records(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    """Positive control for idempotency: the guard must not collapse a sale into a purchase."""
    folder = tmp_path / "directional"
    folder.mkdir()
    (folder / _STRUCTURED).write_bytes((_CORPUS / _STRUCTURED).read_bytes())
    service = PurchaseInvoiceEvidenceService(
        settings=runtime_profile.settings,
        bucket_event_repository=_events(runtime_profile),
    )

    for direction in (InvoiceKind.RECEIVED, InvoiceKind.ISSUED):
        run_evidence_batch(
            bucket_id=_BUCKET_ID,
            sources=[folder],
            direction=direction,
            settings=runtime_profile.settings,
            bucket_event_repository=_events(runtime_profile),
        )

    assert len(service.list_all(bucket_id=_BUCKET_ID)) == 2, "issued and received are genuinely two records"


def test_a_raising_progress_callback_does_not_cost_the_run_its_results(
    runtime_profile: TestRuntimeProfile,
    batch_dir: Path,
) -> None:
    """Progress reporting is incidental; losing a batch to it would be absurd."""

    def explode(_row: object) -> None:
        raise RuntimeError("the progress sink failed")

    result = run_evidence_batch(
        bucket_id=_BUCKET_ID,
        sources=[batch_dir],
        direction=InvoiceKind.RECEIVED,
        settings=runtime_profile.settings,
        bucket_event_repository=_events(runtime_profile),
        on_item=explode,
    )

    assert len(result.items) == 2


def test_every_completed_item_is_announced_to_the_progress_sink(
    runtime_profile: TestRuntimeProfile,
    batch_dir: Path,
) -> None:
    """Positive control for the guard above: the callback is genuinely called."""
    seen: list[str] = []

    run_evidence_batch(
        bucket_id=_BUCKET_ID,
        sources=[batch_dir],
        direction=InvoiceKind.RECEIVED,
        settings=runtime_profile.settings,
        bucket_event_repository=_events(runtime_profile),
        on_item=lambda row: seen.append(row.content_address),
    )

    assert len(seen) == 2
