"""``aeat doctor`` — Google Workspace + GCP health check (skeleton).

Real implementation lands in Phase 4 of the gsuite-bootstrap plan.
"""

from __future__ import annotations

import typer


def doctor() -> None:
    """Stub for the doctor command. Real check matrix lands in Phase 4."""
    typer.secho("doctor not yet implemented", fg=typer.colors.YELLOW)
    raise typer.Exit(code=1)
