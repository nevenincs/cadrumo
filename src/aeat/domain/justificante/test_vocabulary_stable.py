"""Public-surface stability guard for :mod:`aeat.justificante` (#305).

The rehoming of :class:`JustificanteError` under
:class:`aeat._pdf_import.PdfFilingImportError` must not accidentally prune
any of the module's ``__all__`` exports. This test pins the frozen minimum
surface so future refactors trip this check instead of silently breaking
downstream callers (notably the amendment-baseline flow and the shipped
``aeat filing import --from-justificante`` command).
"""

from __future__ import annotations

import pytest

from . import __all__ as justificante_all

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


_FROZEN_PUBLIC_SURFACE: frozenset[str] = frozenset(
    {
        "Justificante",
        "JustificanteCsvNotFoundError",
        "JustificanteError",
        "JustificanteParseError",
        "JustificanteParserBackend",
        "JustificanteVerificationError",
        "parse_justificante",
        "verify_csv",
    }
)


def test_justificante_public_surface_has_every_frozen_symbol() -> None:
    """Every symbol in the frozen set must remain in ``__all__``."""
    missing = _FROZEN_PUBLIC_SURFACE - set(justificante_all)
    assert not missing, f"aeat.domain.justificante.__all__ is missing frozen symbols: {sorted(missing)}"
