"""Public-surface stability guard for :mod:`aeat.domain.justificante`.

The rehoming of :class:`JustificanteError` under
:class:`aeat.adapters.inbound.pdf.PdfModeloImportError` must not accidentally prune
any of the module's ``__all__`` exports. This test pins the frozen minimum
surface so future refactors trip this check instead of silently breaking
downstream callers.

Note: ``verify_csv`` was intentionally removed from the domain public surface.
The function now lives in :mod:`aeat.adapters.outbound.aeat.verify` because
Playwright/browser automation belongs in the adapter layer, not the domain.
"""

from __future__ import annotations

import pytest

from .. import __all__ as justificante_all

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_FROZEN_PUBLIC_SURFACE: frozenset[str] = frozenset(
    {
        "Justificante",
        "JustificanteCsvNotFoundError",
        "JustificanteError",
        "JustificanteParseError",
        "JustificanteParserBackend",
        "JustificanteVerificationError",
    },
)


def test_justificante_public_surface_has_every_frozen_symbol() -> None:
    """Every symbol in the frozen set must remain in ``__all__``."""
    missing = _FROZEN_PUBLIC_SURFACE - set(justificante_all)
    assert not missing, f"aeat.domain.justificante.__all__ is missing frozen symbols: {sorted(missing)}"


def test_justificante_domain_surface_does_not_reexport_parser_pipeline() -> None:
    """The parser entry point belongs to the inbound adapter surface."""
    assert "parse_justificante" not in justificante_all
