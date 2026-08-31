"""Session-local cache for expensive committed justificante fixture parses."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from ..adapters.inbound.justificante.parser import parse_justificante
from ..domain.justificante.schema import Justificante


@cache
def parse_committed_justificante_fixture(pdf_path: Path) -> Justificante:
    """Parse an immutable committed fixture once per pytest process."""
    return parse_justificante(pdf_path)
