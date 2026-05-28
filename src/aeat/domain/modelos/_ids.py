"""Shared typed-ID aliases for the modelo persistence boundary.

Centralises the four identity types previously redeclared independently
across ``_work_unit.py``, ``_calculation_revision.py``, ``_filing_record.py``,
and the per-bucket binding modules. Single-sourced here so every domain
record (and every application-layer record that crosses the modelo
boundary) imports the same constraint shape.

Per the persistence-identity inventory swarm finding
(`.vault/audit/2026-05-28-typed-id-enrollment-audit.md` — task #567):

- ``_filing_record.py`` previously declared ``_WorkUnitId =
  _FilingRecordId`` and ``_CalculationRevisionId = _FilingRecordId``,
  structurally collapsing three distinct domain identities to the same
  alias. They share the same string shape (SHA-256 hex) but carry
  different semantic roles; the type-system should be able to tell them
  apart for downstream callers.
- ``_calculation_revision.py`` declared its own ``_WorkUnitId`` with
  the identical constraint, independent of ``_work_unit.py``.

The four aliases here are the canonical declarations; the per-file
underscore-prefixed names remain as backward-compatible aliases via
``from ._ids import ... as _Xxx`` in the consuming modules until those
modules are migrated to import the public names directly.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

_HEX_64_PATTERN = r"^[0-9a-f]{64}$"

WorkUnitId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
"""Hex-64 identity of a modelo work unit. Minted via ``new_work_unit_id()``."""

CalculationRevisionId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
"""Hex-64 identity of one calculation revision under a work unit."""

FilingRecordId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
"""Hex-64 identity of one filing record bound to a calculation revision."""

BucketId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
"""Bucket identity (profile UUID or a system-scoped sentinel)."""

__all__ = (
    "BucketId",
    "CalculationRevisionId",
    "FilingRecordId",
    "WorkUnitId",
)
