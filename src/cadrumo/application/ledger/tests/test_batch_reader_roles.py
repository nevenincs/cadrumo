"""A missing reader closes its own role, not the whole batch.

The inference lane used to ask one question -- is the VISION reader there --
and only after something had already refused. On a machine holding a text model
and no vision model that answer was wrong in both directions: text-readable
PDFs were paused although their reader was installed, and a machine missing the
text model refused documents one at a time instead of pausing them.

The lane now reads the role each document will reach off the same shape probe
the deterministic test uses, and probes that role before the first read. The
lane cases drive it against a REAL loopback runtime reporting a real inventory
-- no patched module -- so the proven path runs from settings through the HTTP
inventory read into the lane's decision. Which shape a document's bytes carry
is the inbound shape probe's answer and is proven against the evidence corpus
in that adapter's own suite; here each shape is supplied through the
application-owned probe port.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from typing import ClassVar, override

import pytest

from ....core.config import load_settings, override_settings
from ....core.document_shape import DocumentShape
from ....core.hardware import AcceleratorKind
from ....core.model_catalogue import ModelRole
from ....tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from ...local_reader import configured_role_model
from ...provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    SystemMemoryReading,
    probe_hardware_profile,
)
from ..batch_ingest import _InferenceLaneState, _reader_role_for
from ..evidence_input_ports import EvidenceDocumentShapeProbe

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_GIB = 1024**3

#: Every shape the probe can answer, with the reader role it must reach. Spelled
#: out rather than derived from the shape sets, so a new shape fails here until
#: someone decides which reader it belongs to.
_ROLE_BY_SHAPE: dict[DocumentShape, ModelRole | None] = {
    DocumentShape.XML_CII: None,
    DocumentShape.XML_UBL: None,
    DocumentShape.XML_FACTURAE: None,
    DocumentShape.PDF_EMBEDDED_XML: None,
    DocumentShape.XML_AEAT_SII: None,
    DocumentShape.XML_AEAT_VERIFACTU: None,
    DocumentShape.PDF_TEXT_LAYER: ModelRole.TEXT_EXTRACTION,
    DocumentShape.PDF_SCAN: ModelRole.VISION_TRANSCRIPTION,
    DocumentShape.IMAGE: ModelRole.VISION_TRANSCRIPTION,
    DocumentShape.UNKNOWN: None,
}


class _InventoryOnlyHandler(SilentLoopbackHandler):
    """A runtime that answers its model inventory and serves nothing else."""

    installed: ClassVar[tuple[str, ...]] = ()

    @override
    def do_GET(self) -> None:
        write_json_response(
            self,
            {"models": [{"name": name, "model": name, "size": 0} for name in self.installed]},
            status=HTTPStatus.OK,
        )


@contextmanager
def _serving_inventory(*installed: str) -> Iterator[None]:
    """Point settings at a real runtime reporting exactly ``installed``."""
    _InventoryOnlyHandler.installed = installed
    with (
        serving_loopback(_InventoryOnlyHandler, path="/api/chat") as chat_url,
        override_settings(cadrumo_llm_ollama_chat_url=chat_url),
    ):
        yield


def _uncontended() -> HardwareProfile:
    """A machine with ample headroom, so contention never decides these cases."""
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=64 * _GIB, free_bytes=48 * _GIB),
        accelerator=AcceleratorReading(
            kind=AcceleratorKind.NVIDIA_CUDA,
            devices=(AcceleratorDevice(index=0, name="card-0", total_vram_bytes=24 * _GIB, free_vram_bytes=20 * _GIB),),
        ),
    )


def _probe_answering(shape: DocumentShape, *, expected_data: bytes) -> EvidenceDocumentShapeProbe:
    """Return a shape probe that answers ``shape`` for exactly the bytes it is handed."""

    def probe(data: bytes) -> DocumentShape:
        assert data == expected_data, "the role must be read off the document's own bytes"
        return shape

    return probe


def test_every_shape_has_a_declared_reader_role() -> None:
    """ANCHOR: the table below covers the whole shape vocabulary, so no shape is untested."""
    assert set(_ROLE_BY_SHAPE) == set(DocumentShape)


@pytest.mark.parametrize(("shape", "expected"), list(_ROLE_BY_SHAPE.items()))
def test_each_document_names_the_reader_role_it_will_reach(shape: DocumentShape, expected: ModelRole | None) -> None:
    """DISCRIMINATING: the role follows the probed shape of the bytes, never a file name."""
    data = f"document probed as {shape.value}".encode()

    assert _reader_role_for(data, document_shape_probe=_probe_answering(shape, expected_data=data)) is expected


def test_a_missing_vision_model_leaves_text_documents_readable() -> None:
    """The property: an absent role closes its own lane and no other."""
    text_model = configured_role_model(ModelRole.TEXT_EXTRACTION, load_settings())
    assert text_model is not None, "the text reading role must name a model for this case to exist"

    with _serving_inventory(text_model):
        lane = _InferenceLaneState(settings=load_settings(), profile=_uncontended())

        text_admitted = lane.admits(deterministic=False, role=ModelRole.TEXT_EXTRACTION)
        vision_admitted = lane.admits(deterministic=False, role=ModelRole.VISION_TRANSCRIPTION)
        pause = lane.pause()

    assert text_admitted is True, "a text-layer document must read while only the vision model is missing"
    assert vision_admitted is False
    assert pause is not None
    assert pause.facts["role"] == ModelRole.VISION_TRANSCRIPTION.value


def test_the_first_document_of_a_missing_role_is_paused_rather_than_refused() -> None:
    """ANTI-VACUITY: with neither model installed nothing is attempted first.

    The lane declines the very first model-bearing document, so no innocent
    document is refused to discover what the machine was missing all along --
    and work that needs no model is still admitted.
    """
    with _serving_inventory():
        lane = _InferenceLaneState(settings=load_settings(), profile=_uncontended())

        admitted = lane.admits(deterministic=False, role=ModelRole.TEXT_EXTRACTION)
        deterministic_admitted = lane.admits(deterministic=True)
        pause = lane.pause()

    assert admitted is False
    assert deterministic_admitted is True, "work that needs no model is never held back"
    assert pause is not None
