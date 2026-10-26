"""Diagnostics for the subordinate import checker."""

from __future__ import annotations

import re


def has_architectural_warning(output: str) -> bool:
    """Return true when native Import Linter output names a warning/advisory."""
    for line in output.splitlines():
        lowered = line.strip().lower()
        if not lowered or lowered.startswith("no warning") or lowered.startswith("no advisory"):
            continue
        if re.search(r"\b(?:warnings?|advisories?)\s*[:=]\s*0\b", lowered):
            continue
        if re.search(r"\b(?:warning|warnings|advisory|advisories)\b", lowered):
            return True
    return False
