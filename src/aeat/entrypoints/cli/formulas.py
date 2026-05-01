"""``aeat formulas`` sub-app — per-modelo calculation formula engine (#173).

Re-exports the Typer ``app`` constructed in :mod:`aeat.formulas._cli`,
mirroring the shim pattern used by :mod:`aeat.cli.modelos`.
"""

from __future__ import annotations

from ...domain.formulas._cli import app

__all__ = ["app"]
