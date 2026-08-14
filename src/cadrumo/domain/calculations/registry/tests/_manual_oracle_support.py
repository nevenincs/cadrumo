"""Shared reader for bundled manual worked-example oracle payloads.

Every AEAT manual worked-example test reads a payload from the same bundled
corpus directory through the same strict payload model; only the filename
varies per module. This is deliberately narrower than
:mod:`domain.calculations.registry._external_grounding`'s
``_read_oracle_payload``, which dispatches across every :class:`ExternalOracleCorpus`
member, cross-validates and returns the richer ``ExternalOracleEvidence`` the
grounding fold consumes -- a production contract these tests neither need nor
should couple to for a plain bundled-file read.
"""

from __future__ import annotations

from pathlib import Path

from .....core.resources import bundled_path
from .. import ManualWorkedExamplePayload

__all__ = ["read_manual_worked_example"]


def read_manual_worked_example(name: str) -> ManualWorkedExamplePayload:
    """Read a bundled manual worked-example oracle through the registry's strict payload model."""
    path = Path(bundled_path("corpus", "manual_oracles")) / name
    return ManualWorkedExamplePayload.model_validate_json(path.read_text(encoding="utf-8"))
