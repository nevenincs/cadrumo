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

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....application.provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    SystemMemoryReading,
    probe_hardware_profile,
)
from ....core import AcceleratorKind
from ....domain.iva.classification import InvoiceKind
from ....tests.secure_sql import TestRuntimeProfile
from ..batch_ingest import COMPLETED_BATCH_ITEM_STATUSES, BatchRunResult, run_evidence_batch
from ._loopback_reader import serving_a_loopback_reader

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "2c2c2c2c-2c2c-4c2c-8c2c-2c2c2c2c2c2c"
_CORPUS = Path(__file__).parent / "_evidence_corpus"

#: Read by a parser: this row never needs the inference lane.
_STRUCTURED = "facturae_32_series_and_parties_invoice.xml"

#: A scan with no text layer: reading it needs a model, so it is the row a
#: contended machine must park rather than attempt.
_SCAN = "scanned_invoice_from_commons_1.pdf"

_GIB = 1024**3


runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


@pytest.fixture
def mixed_batch(tmp_path: Path) -> Path:
    """A folder holding one deterministic document and one that needs a model."""
    folder = tmp_path / "batch"
    folder.mkdir()
    for name in (_STRUCTURED, _SCAN):
        (folder / name).write_bytes((_CORPUS / name).read_bytes())
    return folder


def _headroom(*, free_vram_bytes: int) -> HardwareProfile:
    """A machine whose free memory is readable, with the given device headroom.

    Injected rather than probed because the host running these tests reports no
    readable accelerator and its admission check therefore fails closed --
    correctly. Left to the host, the contended case would pass for the wrong
    reason and the control case could not exist at all.
    """
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=64 * _GIB, free_bytes=48 * _GIB),
        accelerator=AcceleratorReading(
            kind=AcceleratorKind.NVIDIA_CUDA,
            devices=(
                AcceleratorDevice(
                    index=0,
                    name="card-0",
                    total_vram_bytes=24 * _GIB,
                    free_vram_bytes=free_vram_bytes,
                ),
            ),
        ),
    )


def _run(
    profile: TestRuntimeProfile,
    folder: Path,
    *,
    free_vram_bytes: int,
    safety_margin_bytes: int | None = None,
) -> BatchRunResult:
    """Run the batch against injected headroom, optionally widening the margin.

    The margin is a real operator setting -- raised on a machine that also
    drives a display -- and it is what makes a contended run reachable here at
    all. Selection and admission read the same measured free figure, and their
    thresholds sit within tens of megabytes of each other on the shipped
    catalogue, so a headroom low enough to refuse admission is usually also low
    enough for selection to find no candidate, which is NOT a pause. Widening
    the margin separates the two thresholds without touching either decision.
    """
    settings = profile.settings
    if safety_margin_bytes is not None:
        settings = settings.model_copy(update={"cadrumo_llm_contention_safety_margin_bytes": safety_margin_bytes})
    return run_evidence_batch(
        bucket_id=_BUCKET_ID,
        sources=[folder],
        direction=InvoiceKind.RECEIVED,
        settings=settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
        profile=_headroom(free_vram_bytes=free_vram_bytes),
    )


def test_a_contended_machine_parks_the_model_work_and_completes_the_rest(
    runtime_profile: TestRuntimeProfile,
    mixed_batch: Path,
) -> None:
    """The property: deterministic progress continues while inference-bearing work parks."""
    result = _run(runtime_profile, mixed_batch, free_vram_bytes=3 * _GIB, safety_margin_bytes=4 * _GIB)

    assert result.deterministic_completed == 1
    assert result.paced == 1
    # Reported once on the run rather than stamped onto an innocent document.
    assert result.inference_pause is not None
    assert result.inference_pause.precondition_verdict.failed_condition_id == "provisioning.resident_set.readable"
    assert result.inference_pause.facts["resident_set_readable"] is False
    # Parked, not failed: a re-run costs nothing because completed items are
    # no-ops, so this must not read as a broken document.
    assert result.any_deferred is True
    assert result.any_failed is False

    parked = [item for item in result.items if item.status == "paused"]
    assert [item.source_name for item in parked] == [_SCAN]
    assert all(item.needed_inference for item in parked)


def test_with_headroom_the_same_batch_paces_nothing(
    runtime_profile: TestRuntimeProfile,
    mixed_batch: Path,
) -> None:
    """The positive control, and the proof that the parked item's window OPENS.

    Same folder, same documents, same run -- only the measured headroom differs.
    It says the parked row above genuinely WOULD have dispatched, which "it did
    not dispatch" cannot say on its own: an item that could never have been read
    would produce the same paced count.
    """
    with serving_a_loopback_reader(replies=()):
        result = _run(runtime_profile, mixed_batch, free_vram_bytes=12 * _GIB)

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
        with_headroom = _run(runtime_profile, mixed_batch, free_vram_bytes=12 * _GIB)

    assert with_headroom.deterministic_completed == 1, (
        "the scan was counted as deterministic progress; the split that makes pacing observable is gone"
    )
    assert len(with_headroom.items) == 2
