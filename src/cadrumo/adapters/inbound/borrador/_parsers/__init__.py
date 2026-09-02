"""PDF backend facade for the borrador parser.

Re-exports ``extract_pages_text`` from the active backend
implementation. Today the only backend is the pdfplumber-based
``_pdfplumber_backend``. Keeping the backend behind this facade lets
extractors depend on one local text-extraction primitive instead of on
``pdfplumber`` directly.

See Also:
    :func:`extract_pages_text`
        Active per-page text extraction primitive re-exported by this facade.
    :mod:`adapters.inbound.pdf`
        Shared inbound-PDF helper package used by this backend.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
