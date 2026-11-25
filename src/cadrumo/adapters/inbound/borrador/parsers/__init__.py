"""Inert namespace for borrador PDF parser backends.

The active implementation is ``pdfplumber_backend``. Consumers import
``extract_pages_text`` directly from that defining module.

See Also:
    :func:`pdfplumber_backend.extract_pages_text`
        Active per-page text extraction primitive.
    :mod:`adapters.inbound.pdf`
        Shared inbound-PDF helper package used by this backend.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
