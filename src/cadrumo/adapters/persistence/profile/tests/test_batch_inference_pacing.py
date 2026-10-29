"""Batch pacing: a closed inference lane must not stop the run.

On this class of machine contention is the NORMAL state, not the exception, so
a batch that halts entirely when the lane closes converts a recoverable
condition into a failed run. The property is narrower and more useful: the
inference-bearing items park while every deterministic item keeps completing.

Each case reports the two counts SEPARATELY, because pooled into one "N
completed" figure a run that paced everything and a run that paced nothing read
identically -- and a paced count that has never been shown able to rise is not a
measurement.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from .....application.ledger import tests as ledger_application_tests
from .....application.ledger.batch_ingest import COMPLETED_BATCH_ITEM_STATUSES, BatchRunResult, run_evidence_batch
from .....application.ledger.evidence_ports import LedgerEvidencePorts
from .....application.ledger.invoice_extraction_authority import default_invoice_extraction_period
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.iva.regime_legend import resolve_regime_legends
from .....domain.iva.schema import InvoiceKind
from ...storage.attachment import AttachmentStore
from ...storage.tests.secure_sql import TestRuntimeProfile
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..buckets import BucketEventHistoryRepository
from ..purchase_invoice_evidence import (
    LedgerEvidenceAttachmentIngestor,
    LedgerEvidenceRepositoryAdapter,
)
from ._invoice_confirmation_test_support import _invoice_draft_extraction_ports, serving_a_loopback_reader

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "2c2c2c2c-2c2c-4c2c-8c2c-2c2c2c2c2c2c"
#: The evidence corpus belongs to the ledger application tests; resolved through
#: that package so the location follows its owner rather than this file's depth.
_CORPUS = Path(ledger_application_tests.__file__).parent / "_evidence_corpus"

#: Read by a parser: this row never needs the inference lane.
_STRUCTURED = "facturae_32_series_and_parties_invoice.xml"

#: A scan with no text layer: reading it needs a model, so it is the row a
#: contended machine must park rather than attempt.
_SCAN = "scanned_invoice_from_commons_1.pdf"

#: A text-layer invoice whose labels print every required field, so the label
#: rules read it completely and no model is ever needed.
_LABELLED_TEXT_LAYER = "labelled_text_layer_invoice.pdf"
_LABELLED_LINES = (
    "FACTURA",
    "Proveedor: Hardware Profesional Sur SL",
    "NIF: B92000090",
    "Numero de factura: A-0003",
    "Fecha de expedicion: 2026-03-27",
    "Destinatario: Javier Ortega Llorens NIF: 12345678Z",
    "Base imponible: 1200.00 EUR",
    "Tipo IVA: 21%",
    "Cuota IVA: 252.00 EUR",
    "Total factura: 1452.00 EUR",
)


runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


@pytest.fixture
def mixed_batch(tmp_path: Path) -> Path:
    """A folder holding one deterministic document and one that needs a model."""
    folder = tmp_path / "batch"
    folder.mkdir()
    for name in (_STRUCTURED, _SCAN):
        (folder / name).write_bytes((_CORPUS / name).read_bytes())
    return folder


@pytest.fixture
def labelled_batch(mixed_batch: Path) -> Path:
    """The mixed folder plus one fully labelled text-layer invoice."""
    page = canvas.Canvas(str(mixed_batch / _LABELLED_TEXT_LAYER))
    for index, line in enumerate(_LABELLED_LINES):
        page.drawString(50, 800 - 18 * index, line)
    page.save()
    return mixed_batch


#: The agent owns load admission and refuses a run at its start when the
#: selected model does not fit this computer's free memory.
_DOES_NOT_FIT = ModelRunRefusalCode.MODEL_DOES_NOT_FIT
_LOAD_CAPACITY = "probe.load_capacity.available"


def _run(profile: TestRuntimeProfile, folder: Path) -> BatchRunResult:
    """Run the batch through the production extraction ports, under whatever lane the bound agent resolves."""
    evidence_ports = LedgerEvidencePorts(
        evidence_repository=LedgerEvidenceRepositoryAdapter(objects=profile.repository),
        attachment_ingestor=LedgerEvidenceAttachmentIngestor(store=AttachmentStore(objects=profile.repository)),
        bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
    )
    period = default_invoice_extraction_period()
    with bundled_indexed_authority().operation() as operation:
        legends = resolve_regime_legends(operation=operation, effective_date=period.end_date)
        return run_evidence_batch(
            bucket_id=_BUCKET_ID,
            sources=[folder],
            direction=InvoiceKind.RECEIVED,
            settings=profile.settings,
            evidence_ports=evidence_ports,
            extraction_ports=_invoice_draft_extraction_ports(evidence_ports=evidence_ports, operation=operation),
            operation=operation,
            legends=legends,
        )


def test_a_contended_machine_parks_the_model_work_and_completes_the_rest(
    runtime_profile: TestRuntimeProfile,
    mixed_batch: Path,
) -> None:
    """The property: deterministic progress continues while inference-bearing work parks.

    The agent refuses the scan's read at its start because the selected model
    does not fit the free memory, before anything loads.
    """
    with serving_a_loopback_reader(replies=(), run_refusal=_DOES_NOT_FIT):
        result = _run(runtime_profile, mixed_batch)

    assert result.deterministic_completed == 1
    assert result.paced == 1
    # Reported once on the run rather than stamped onto an innocent document.
    assert result.inference_pause is not None
    assert result.inference_pause.precondition_verdict.failed_condition_id == _LOAD_CAPACITY
    # Parked, not failed: a re-run costs nothing because completed items are
    # no-ops, so this must not read as a broken document.
    assert result.any_deferred is True
    assert result.any_failed is False

    parked = [item for item in result.items if item.status == "paused"]
    assert [item.source_name for item in parked] == [_SCAN]
    assert all(item.needed_inference for item in parked)
    assert all(item.refusal_verdict is None for item in parked)


def test_with_headroom_the_same_batch_paces_nothing(
    runtime_profile: TestRuntimeProfile,
    mixed_batch: Path,
) -> None:
    """The positive control, and the proof that the parked item's window OPENS.

    Same folder, same documents, same run -- only the agent's load answer differs.
    It says the parked row above genuinely WOULD have dispatched, which "it did
    not dispatch" cannot say on its own: an item that could never have been read
    would produce the same paced count.
    """
    with serving_a_loopback_reader(replies=()):
        result = _run(runtime_profile, mixed_batch)

    assert result.paced == 0
    assert result.inference_pause is None
    assert result.any_deferred is False
    # Every item reached a status in which the work actually happened.
    assert {item.status for item in result.items} <= COMPLETED_BATCH_ITEM_STATUSES
    assert len(result.items) == 2


def test_the_deterministic_count_does_not_absorb_model_read_items(
    runtime_profile: TestRuntimeProfile,
    mixed_batch: Path,
) -> None:
    """The two counts must stay separable, or neither reports anything.

    A deterministic count that rose for a model-read item would report the
    control run above as two deterministic completions and make the contended
    run indistinguishable from it.
    """
    with serving_a_loopback_reader(replies=()):
        with_headroom = _run(runtime_profile, mixed_batch)

    assert with_headroom.deterministic_completed == 1, (
        "the scan was counted as deterministic progress; the split that makes pacing observable is gone"
    )
    assert len(with_headroom.items) == 2


def test_a_fully_labelled_text_layer_invoice_completes_while_the_lane_is_closed(
    runtime_profile: TestRuntimeProfile,
    labelled_batch: Path,
) -> None:
    """The label rules read it completely, so a closed inference lane does not park it."""
    with serving_a_loopback_reader(replies=(), run_refusal=_DOES_NOT_FIT):
        result = _run(runtime_profile, labelled_batch)

    by_name = {item.source_name: item for item in result.items}
    assert by_name[_LABELLED_TEXT_LAYER].status in COMPLETED_BATCH_ITEM_STATUSES
    assert by_name[_LABELLED_TEXT_LAYER].needed_inference is False
    assert by_name[_SCAN].status == "paused"
    assert result.deterministic_completed == 2
