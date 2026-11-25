"""Inward fakes for application text-layer use-case tests."""

from __future__ import annotations

from ..evidence_errors import PurchaseInvoiceEvidenceInputError
from ..evidence_textlayer_ports import EvidenceTextLayerPorts


def text_layer_ports_for_pages(pages: tuple[str, ...]) -> EvidenceTextLayerPorts:
    """Return an inward fake with a deterministic ordered page projection."""

    def extract_pages_text(data: bytes) -> tuple[str, ...]:
        del data
        return pages

    return EvidenceTextLayerPorts(extract_pages_text=extract_pages_text)


def refusing_text_layer_ports() -> EvidenceTextLayerPorts:
    """Return an inward fake for a document without usable text-layer content."""

    def refuse(data: bytes) -> tuple[str, ...]:
        del data
        raise PurchaseInvoiceEvidenceInputError("evidence has no usable text layer")

    return EvidenceTextLayerPorts(extract_pages_text=refuse)


__all__ = ["refusing_text_layer_ports", "text_layer_ports_for_pages"]
