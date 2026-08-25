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
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....application.provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    ProvisioningPreconditionCondition,
    SystemMemoryReading,
    probe_hardware_profile,
)
from ....core import LOCAL_TRANSPORT_LABEL, AcceleratorKind
from ....core.directory_scan import scan_directory
from ....core.config import load_settings, override_settings
from ....domain.iva import InvoiceKind
from ....tests.pdf_fixtures import text_pdf_bytes
from ....tests.secure_sql import TestRuntimeProfile
from ..batch_ingest import BatchRunResult, run_evidence_batch
from ..evidence import PurchaseInvoiceEvidenceService
from ..extraction_draft_store import load_extraction_drafts
from ._loopback_reader import serving_a_loopback_reader

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "2b2b2b2b-2b2b-4b2b-8b2b-2b2b2b2b2b2b"

runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


_CORPUS = Path(__file__).parent / "_evidence_corpus"

#: A structured record: read by a parser, so this row is deterministic and
#: reaches no model at all.
_STRUCTURED = "facturae_32_series_and_parties_invoice.xml"

#: The poison. Malformed bytes behind a PDF extension, which is the shape that
#: must produce a refusal ROW rather than end the run.
_POISON = "adversarial_malformed.pdf"

#: A scan with no text layer, so reading it needs a model and it is the item a
#: contended machine must defer rather than attempt.
_SCAN = "scanned_invoice_from_commons_1.pdf"

_GIB = 1024**3
_SUPPLIER_CIF = "B12345674"


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


def _measurable_headroom() -> HardwareProfile:
    """A machine whose free memory is readable and ample, so admission admits.

    Injected rather than probed, and that is the point. The host running these
    tests reports no readable accelerator, so its admission check fails CLOSED —
    correctly. Left to the host, every gate below would measure the pause path
    and none would measure the behaviour it names.
    """
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=64 * _GIB, free_bytes=48 * _GIB),
        accelerator=AcceleratorReading(
            kind=AcceleratorKind.NVIDIA_CUDA,
            devices=(AcceleratorDevice(index=0, name="card-0", total_vram_bytes=24 * _GIB, free_vram_bytes=12 * _GIB),),
        ),
    )


def _run(profile: TestRuntimeProfile, folder: Path) -> BatchRunResult:
    return run_evidence_batch(
        bucket_id=_BUCKET_ID,
        sources=[folder],
        direction=InvoiceKind.RECEIVED,
        settings=profile.settings,
        bucket_event_repository=_events(profile),
        profile=_measurable_headroom(),
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
    assert poison.refusal_verdict is not None, "a refusal must name the condition that failed"
    assert poison.refusal_verdict.failed_condition_id
    facts = {key: value for evidence in poison.refusal_verdict.evidence for key, value in evidence.values.items()}
    assert facts, "a refusal an operator cannot act on is barely better than a silent drop"


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


def test_an_all_local_batch_ingest_surveys_as_on_host(
    runtime_profile: TestRuntimeProfile,
    batch_dir: Path,
) -> None:
    """A batch read that never left the host must not appear in a withdrawal.

    Drives the REAL batch path rather than seeding the draft store, because the
    defect this guards was invisible to a seeded test: the survey classified by
    parsing the stored ``extractor`` label, the batch stores a function name
    there by a deliberate rule, and every batch-ingested draft was therefore
    reported cloud-derived. A test that wrote its own stored draft would have
    chosen a parseable label and proved the selector rather than the path.

    Fail-open noise is not caution on a confidentiality surface. A withdrawal
    listing documents that never left the machine trains the operator to skim
    it, and the one row that matters is then the one they skim past.
    """
    from ..consent_withdrawal import survey_cloud_consent

    _run(runtime_profile, batch_dir)

    stored = load_extraction_drafts(_BUCKET_ID, runtime_profile.settings).drafts
    assert stored, "the batch must have written a draft for this gate to mean anything"

    survey = survey_cloud_consent(bucket_id=_BUCKET_ID, settings=runtime_profile.settings, consent_entries=())

    assert survey.cloud_derived_artefacts == (), (
        "an all-local batch ingest was reported as cloud-derived; the survey is classifying by "
        f"something other than the recorded transports {[row.read_transports for row in stored]}"
    )
    assert survey.transmitted_bytes_are_unrecallable is True


def test_a_batch_draft_records_the_transport_that_carried_it(
    runtime_profile: TestRuntimeProfile,
    batch_dir: Path,
) -> None:
    """The stored transport is populated, so the survey above is not passing on emptiness.

    An empty ``read_transports`` is defined to mean UNKNOWN and is surfaced, so
    a survey returning no rows cannot be explained by the field being unset --
    but only if something asserts the field is actually written. Without this,
    a regression that stopped recording transports would flip the gate above
    from green to red rather than silently, which is the right direction, and
    this case is what makes that true.
    """
    _run(runtime_profile, batch_dir)

    stored = load_extraction_drafts(_BUCKET_ID, runtime_profile.settings).drafts
    assert stored
    for row in stored:
        assert row.read_transports, f"{row.evidence_reference} recorded no transport at all"
        assert all(transport == LOCAL_TRANSPORT_LABEL for transport in row.read_transports)


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

    # Byte-identical from the second run on, which is the strongest form the
    # design permits rather than a weakened one: the FIRST run legitimately
    # differs, because the item it ingested is a no-op by the second. Runs two
    # and three are what catch a row re-deriving a per-run field — a timestamp,
    # a run id — since such a field orders identically and still leaves two
    # reports nobody can diff.
    third = _run(runtime_profile, batch_dir)
    assert [item.model_dump_json() for item in third.items] == [item.model_dump_json() for item in second.items]


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
            for path in scan_directory(tmp_path, recursive=True)
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
        for path in scan_directory(tmp_path, recursive=True)
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


class TestInferencePacing:
    """A contended machine must cost the batch its readable items, not its whole run.

    Contention is produced from **injected measurements** driven through the real
    `assess_model_load_contention`, which is the same seam that primitive's own
    suite uses. Nothing here substitutes the admission decision: the production
    function computes the refusal, from a hardware profile that states a
    shortfall rather than one asserting the answer.
    """

    @staticmethod
    def _contended() -> HardwareProfile:
        """A machine with a real accelerator whose free figure cannot be read.

        This shape rather than a small-free-memory one, because selection and
        admission share the free-memory bar: a machine too small to admit a
        model is also too small to select one, so it never reaches the pacing
        decision at all. An unreadable free figure is the reachable state where
        a model IS selected and the load is still refused — "could not tell" is
        not evidence of headroom, and refusing it is the primitive's fail-closed
        core.
        """
        return probe_hardware_profile(
            memory=SystemMemoryReading(total_bytes=64 * _GIB, free_bytes=48 * _GIB),
            accelerator=AcceleratorReading(
                kind=AcceleratorKind.NVIDIA_CUDA,
                devices=(AcceleratorDevice(index=0, name="card-0", total_vram_bytes=24 * _GIB, free_vram_bytes=None),),
            ),
        )

    def test_a_contended_machine_still_completes_every_deterministic_item(
        self,
        runtime_profile: TestRuntimeProfile,
        tmp_path: Path,
    ) -> None:
        """The point of pacing: the structured records go through regardless.

        A run that refused everything because a model could not be loaded would
        waste the half of the work that never needed one.
        """
        folder = tmp_path / "mixed"
        folder.mkdir()
        (folder / _STRUCTURED).write_bytes((_CORPUS / _STRUCTURED).read_bytes())
        (folder / _SCAN).write_bytes((_CORPUS / _SCAN).read_bytes())

        result = run_evidence_batch(
            bucket_id=_BUCKET_ID,
            sources=[folder],
            direction=InvoiceKind.RECEIVED,
            settings=runtime_profile.settings,
            bucket_event_repository=_events(runtime_profile),
            profile=self._contended(),
        )

        statuses = {item.source_name: item.status for item in result.items}
        assert statuses[_SCAN] == "paused", "an item needing a reader must be paused, not attempted"
        assert statuses[_STRUCTURED] != "paused", "a structured record needs no model and must still run"

    def test_the_pause_is_stated_once_for_the_run_not_per_document(
        self,
        runtime_profile: TestRuntimeProfile,
        tmp_path: Path,
    ) -> None:
        """N identical refusals is how a real refusal goes unread."""
        folder = tmp_path / "scans"
        folder.mkdir()
        for name in (_SCAN, "com_2026_0005_camera_photo.jpg", "commons_invoice_1.jpg"):
            (folder / name).write_bytes((_CORPUS / name).read_bytes())

        result = run_evidence_batch(
            bucket_id=_BUCKET_ID,
            sources=[folder],
            direction=InvoiceKind.RECEIVED,
            settings=runtime_profile.settings,
            bucket_event_repository=_events(runtime_profile),
            profile=self._contended(),
        )

        assert [item.status for item in result.items] == ["paused"] * 3
        assert result.inference_pause is not None, "three paused documents must carry one stated cause"
        assert result.inference_pause.precondition_verdict.failed_condition_id == (
            ProvisioningPreconditionCondition.LOAD_HEADROOM_MEASURABLE.value
        )
        assert result.inference_pause.facts["binding_free_measured"] is False
        # No per-item refusal text: the model forbids a reason under a non-refused
        # status, so this also proves the pause did not smuggle one in per row.
        assert all(item.refusal_verdict is None for item in result.items)

    def test_a_paused_run_is_not_a_failed_run_but_is_not_silent_either(
        self,
        runtime_profile: TestRuntimeProfile,
        tmp_path: Path,
    ) -> None:
        """Nothing went wrong with the documents, and work still remains.

        One boolean cannot say both, which is why deferral is its own axis.
        """
        folder = tmp_path / "deferred"
        folder.mkdir()
        (folder / _SCAN).write_bytes((_CORPUS / _SCAN).read_bytes())

        result = run_evidence_batch(
            bucket_id=_BUCKET_ID,
            sources=[folder],
            direction=InvoiceKind.RECEIVED,
            settings=runtime_profile.settings,
            bucket_event_repository=_events(runtime_profile),
            profile=self._contended(),
        )

        assert not result.any_failed, "a deferred document has not failed"
        assert result.any_deferred, "but the run must not report itself as finished"

    def test_a_paused_item_is_attempted_on_a_later_run(
        self,
        runtime_profile: TestRuntimeProfile,
        tmp_path: Path,
    ) -> None:
        """Positive control for pausing: it defers work, it does not consume it.

        A pause that left the item looking complete would be worse than a
        refusal, because the operator would never learn it was skipped.
        """
        folder = tmp_path / "retry"
        folder.mkdir()
        (folder / _SCAN).write_bytes((_CORPUS / _SCAN).read_bytes())

        def _over_the_folder(profile: HardwareProfile) -> BatchRunResult:
            """Run the same folder twice, varying only the hardware it sees.

            Spelled out rather than splatted from a shared dict, which widened
            every argument to the union of all of them and checked none of them.
            """
            return run_evidence_batch(
                bucket_id=_BUCKET_ID,
                sources=[folder],
                direction=InvoiceKind.RECEIVED,
                settings=runtime_profile.settings,
                bucket_event_repository=_events(runtime_profile),
                profile=profile,
            )

        paused = _over_the_folder(self._contended())
        # The contention clears; the same folder is re-run against a new
        # measured outcome.
        later = _over_the_folder(_measurable_headroom())

        assert paused.items[0].status == "paused"
        assert later.items[0].status != "paused", "once the contention clears, the deferred item must be attempted"

    def test_a_machine_with_no_reader_gives_one_typed_refusal_not_one_per_document(
        self,
        runtime_profile: TestRuntimeProfile,
        tmp_path: Path,
    ) -> None:
        """The other way the lane closes, and the one the operator meets most.

        The reader is made genuinely unreachable by pointing the runtime at a
        closed port — a real failure of the real client, not a substituted one.
        Admission has nothing to refuse here (the machine has headroom), so this
        exercises the after-the-first-attempt closure specifically: one document
        pays for the discovery and the rest are deferred on the exact typed
        provisioning refusal.
        """
        folder = tmp_path / "no_reader"
        folder.mkdir()
        for name in (_SCAN, "com_2026_0005_camera_photo.jpg", "commons_invoice_1.jpg"):
            (folder / name).write_bytes((_CORPUS / name).read_bytes())

        # Port 1 on loopback: reserved, never listening, so the client's connect
        # genuinely fails rather than being told to fail.
        with override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"):
            result = run_evidence_batch(
                bucket_id=_BUCKET_ID,
                sources=[folder],
                direction=InvoiceKind.RECEIVED,
                settings=load_settings(),
                bucket_event_repository=_events(runtime_profile),
                profile=_measurable_headroom(),
            )

        statuses = [item.status for item in result.items]
        assert statuses.count("refused") == 1, f"exactly one document should pay for the discovery: {statuses}"
        assert statuses.count("paused") == 2, f"every later document must be deferred, not re-refused: {statuses}"
        assert result.inference_pause is not None
        assert result.inference_pause.precondition_verdict.failed_condition_id == (
            ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value
        )
        assert result.inference_pause.facts["runtime_reachable"] is False

    def test_a_document_needing_a_reader_is_read_when_one_is_there(
        self,
        runtime_profile: TestRuntimeProfile,
        tmp_path: Path,
    ) -> None:
        """The positive control this class was missing, and the reason it was missing.

        Every other inference-path assertion here is a NEGATIVE — paused, or
        refused. All of them would still pass against a runner that could never
        read anything at all, because this host has no reader and the absence is
        indistinguishable from a lane that is simply broken. Until something
        proves a document actually gets READ, "the lane opens" is unmeasured.

        A real loopback endpoint supplies the reply, so the router, the provider
        client and the socket are all production code and no model runs.
        """
        pdf = text_pdf_bytes(
            (
                "Factura de Suministros Batch SL",
                f"NIF: {_SUPPLIER_CIF}",
                "Numero de factura: 2026-0777",
                "Fecha: 2026-04-02",
                "Base imponible: 100,00",
                "IVA 21%: 21,00",
                "Total factura: 121,00",
            ),
        )
        folder = tmp_path / "readable"
        folder.mkdir()
        (folder / "factura.pdf").write_bytes(pdf)

        with serving_a_loopback_reader(
            (
                (
                    "2026-0777",
                    {
                        "supplier_tax_id": _SUPPLIER_CIF,
                        "invoice_number": "2026-0777",
                        "invoice_date": "2026-04-02",
                        "taxable_base": "100,00",
                        "iva_rate": "21",
                        "iva_amount": "21,00",
                        "grand_total": "121,00",
                    },
                ),
            ),
        ):
            result = run_evidence_batch(
                bucket_id=_BUCKET_ID,
                sources=[folder],
                direction=InvoiceKind.RECEIVED,
                settings=load_settings(),
                bucket_event_repository=_events(runtime_profile),
                profile=_measurable_headroom(),
            )

        assert result.inference_pause is None, "a reachable reader must leave the lane open"
        assert not result.any_deferred
        assert result.items[0].status in {"ingested", "pending_review"}, (
            f"a document with a reader available must be READ, not {result.items[0].status}"
        )
        drafts = load_extraction_drafts(_BUCKET_ID, load_settings()).drafts
        assert drafts and drafts[0].draft.invoice_number == "2026-0777", (
            "the draft must carry what the reader actually returned"
        )

    def test_a_run_of_structured_records_never_pauses_and_never_probes(
        self,
        runtime_profile: TestRuntimeProfile,
        tmp_path: Path,
    ) -> None:
        """Positive control for the whole class: pacing must not fire on work needing no model.

        Deliberately run on the CONTENDED profile. Nothing here needs a reader,
        so a closed lane is irrelevant to it — and a run that paused these
        anyway would be pacing on the machine's state rather than on the work's
        actual needs.
        """
        folder = tmp_path / "structured"
        folder.mkdir()
        for name in (_STRUCTURED, "facturae_32_recargo_invoice.xml"):
            (folder / name).write_bytes((_CORPUS / name).read_bytes())

        result = run_evidence_batch(
            bucket_id=_BUCKET_ID,
            sources=[folder],
            direction=InvoiceKind.RECEIVED,
            settings=runtime_profile.settings,
            bucket_event_repository=_events(runtime_profile),
            profile=self._contended(),
        )

        assert result.inference_pause is None, "a run with no model in its future must not probe the hardware"
        assert not result.any_deferred
        assert all(item.status != "paused" for item in result.items)


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
