"""A missing reader closes its own role, not the whole batch.

The inference lane used to ask one question -- is the VISION reader there --
after something had already refused. On a machine holding a text model and no
vision model that answer was wrong in both directions: text-readable PDFs were
paused although their reader was installed, and a machine missing the text
model refused documents one at a time instead of pausing them.

The lane now reads the role each document will reach off the same shape probe
the deterministic test uses, and probes that role before the first read. These
drive it against a REAL loopback runtime that reports an inventory -- no patched
module, no substituted probe -- so what is proven is the production path from
settings through the HTTP inventory read to the lane's decision.
"""

from __future__ import annotations

from collections.abc import Generator, Sequence
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

import pytest

from ....core.config import load_settings, override_settings
from ....core.model_catalogue import ModelRole
from ....tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from ...local_reader import configured_role_model
from ...provisioning_runtime import (
    AcceleratorDevice,
    AcceleratorKind,
    AcceleratorReading,
    HardwareProfile,
    SystemMemoryReading,
    probe_hardware_profile,
)
from ..batch_ingest import _InferenceLaneState, _reader_role_for

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_CORPUS = Path(__file__).parent / "_evidence_corpus"
_TEXT_LAYER_PDF = "com_2026_0005_layout_minimal.pdf"
_SCAN = "scanned_invoice_from_commons_1.pdf"
_STRUCTURED = "en16931_ubl_export_third_country_invoice.xml"
_GIB = 1024**3


class _InventoryOnlyHandler(SilentLoopbackHandler):
    """A runtime that answers its model inventory and nothing else."""

    installed: ClassVar[tuple[str, ...]] = ()

    @override
    def do_GET(self) -> None:
        write_json_response(
            self,
            {"models": [{"name": name, "model": name, "size": 0} for name in self.installed]},
            status=HTTPStatus.OK,
        )


def _serving_inventory(*installed: str) -> Generator[None]:
    _InventoryOnlyHandler.installed = installed
    with (
        serving_loopback(_InventoryOnlyHandler, path="/api/chat") as chat_url,
        override_settings(cadrumo_llm_ollama_chat_url=chat_url),
    ):
        yield


serving_inventory = pytest.helpers.register(_serving_inventory) if hasattr(pytest, "helpers") else None


def _uncontended() -> HardwareProfile:
    """A machine with ample headroom, so contention never decides these cases."""
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=64 * _GIB, free_bytes=48 * _GIB),
        accelerator=AcceleratorReading(
            kind=AcceleratorKind.NVIDIA_CUDA,
            devices=(AcceleratorDevice(index=0, name="card-0", total_vram_bytes=24 * _GIB, free_vram_bytes=20 * _GIB),),
        ),
    )


def _shape_probe():
    from ....adapters.inbound.einvoice.shape import probe_document_shape

    return probe_document_shape


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        (_TEXT_LAYER_PDF, ModelRole.TEXT_EXTRACTION),
        (_SCAN, ModelRole.VISION_TRANSCRIPTION),
        (_STRUCTURED, None),
    ],
)
def test_each_document_names_the_reader_role_it_will_reach(document: str, expected: ModelRole | None) -> None:
    """DISCRIMINATING: the role comes from the bytes, not from the file name."""
    data = (_CORPUS / document).read_bytes()

    assert _reader_role_for(data, document_shape_probe=_shape_probe()) is expected


def test_a_missing_vision_model_leaves_text_documents_readable(tmp_path: Path) -> None:
    """The property: one absent role closes its own lane and no other."""
    text_model = configured_role_model(ModelRole.TEXT_EXTRACTION, load_settings())
    assert text_model is not None
    generator = _serving_inventory(text_model)
    next(generator)
    try:
        lane = _InferenceLaneState(settings=load_settings(), profile=_uncontended())

        text_admitted = lane.admits(deterministic=False, role=ModelRole.TEXT_EXTRACTION)
        vision_admitted = lane.admits(deterministic=False, role=ModelRole.VISION_TRANSCRIPTION)
    finally:
        with pytest.raises(StopIteration):
            next(generator)

    assert text_admitted is True, "a text-layer document must read while only the vision model is missing"
    assert vision_admitted is False
    pause = lane.pause()
    assert pause is not None
    assert pause.facts["service"].endswith("vision_transcription")


def test_the_first_document_of_a_missing_role_is_paused_before_it_is_read() -> None:
    """ANTI-VACUITY: the refusal-first path is gone; nothing is attempted first.

    With an inventory holding neither reading model, the lane declines the very
    first model-bearing document, so no document is refused to discover what the
    machine was missing all along.
    """
    generator = _serving_inventory()
    next(generator)
    try:
        lane = _InferenceLaneState(settings=load_settings(), profile=_uncontended())

        admitted = lane.admits(deterministic=False, role=ModelRole.TEXT_EXTRACTION)
        deterministic_admitted = lane.admits(deterministic=True)
    finally:
        with pytest.raises(StopIteration):
            next(generator)

    assert admitted is False
    assert deterministic_admitted is True, "work that needs no model is never held back"
    assert lane.pause() is not None
