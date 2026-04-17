"""``aeat portals`` sub-app — AEAT portal catalogue helpers (#7).

Re-exports the Typer ``app`` constructed in :mod:`aeat.portals._cli`.
Kept as a thin shim so the CLI wiring matches the pattern used by
other sub-apps (e.g. :mod:`aeat.cli.modelos`).
"""

from __future__ import annotations

from aeat.portals._cli import app

__all__ = ["app"]
