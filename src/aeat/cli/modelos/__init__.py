"""``aeat modelos`` sub-app — AEAT modelo inventory helpers (#108).

Re-exports the Typer ``app`` constructed in :mod:`aeat.models._cli`.
Kept as a thin shim so the CLI wiring matches the pattern used by
other sub-apps (e.g. :mod:`aeat.cli.deadlines`).
"""

from __future__ import annotations

from aeat.models._cli import app

__all__ = ["app"]
