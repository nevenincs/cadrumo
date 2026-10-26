"""Write value-free installed journey stage observations inside the caller-owned scratch root."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def _record_stage(scratch: Path, stage: str) -> None:
    """Leave a value-free progress marker inside the isolated temporary run."""
    (scratch / "tui-stage.txt").write_text(stage + "\n", encoding="ascii")
