"""``aeat bootstrap`` — provision scratch resources (skeleton).

Real implementation lands in Phase 5 of the gsuite-bootstrap plan.
"""

from __future__ import annotations

import typer


def bootstrap() -> None:
    """Stub for the bootstrap command. Real provisioning lands in Phase 5."""
    typer.secho("bootstrap not yet implemented", fg=typer.colors.YELLOW)
    raise typer.Exit(code=1)
