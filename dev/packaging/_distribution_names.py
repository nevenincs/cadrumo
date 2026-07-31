"""Import-light PEP 503 distribution-name identity helpers."""

from __future__ import annotations

import re
from typing import Final

_SEPARATOR_RUN: Final[re.Pattern[str]] = re.compile(r"[-_.]+")


def normalise_distribution_name(name: str) -> str:
    """Return ``name`` under PEP 503 comparison normalisation."""
    return _SEPARATOR_RUN.sub("-", name.strip().lower())


__all__ = ["normalise_distribution_name"]
