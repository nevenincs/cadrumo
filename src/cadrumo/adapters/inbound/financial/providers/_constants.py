"""Shared file-extension constants for financial-provider detection.

Single authoritative source for the extension sets that route
``_ordered_candidates`` and the concrete providers, and for the
``FinancialProvider.supported_extensions`` declarations on each concrete
provider class.

Keeping these constants in one place ensures that the detection
router and the provider contract never drift: adding a new alias (e.g.
``.tsv`` for CSV-shaped input) requires one edit here rather than one
edit in every dispatch branch.
"""

from __future__ import annotations

CSV_EXTENSIONS: frozenset[str] = frozenset({".csv", ".txt"})
"""File extensions treated as CSV-compatible input by the CSV provider."""

OFX_EXTENSIONS: frozenset[str] = frozenset({".ofx", ".qfx"})
"""File extensions treated as OFX-compatible input by the OFX provider.

``.qfx`` is the Quicken-flavoured OFX variant; both route to the same
:class:`~adapters.inbound.financial.providers.OfxProvider`.
"""

__all__ = ["CSV_EXTENSIONS", "OFX_EXTENSIONS"]
