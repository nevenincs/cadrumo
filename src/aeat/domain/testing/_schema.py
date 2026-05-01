"""Pydantic v2 schema for :mod:`aeat.domain.testing` synthetic filing fixtures.

Every type in this module is a strict, frozen pydantic v2 model or a
closed :class:`enum.StrEnum`. The :class:`FilingRecord` shape is the
boundary-crossing record persisted to
``tests/fixtures/filing_history/<modelo>/<period>-<scenario>.json``
and re-loaded by :func:`aeat.domain.testing.load_filing_history`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...application.filing import FilingDraftStatus

SYNTHETIC_COMMENT_REQUIRED_SUBSTRING = "SYNTHETIC"


class FilingRecordPeriodKind(StrEnum):
    """Cadence of a synthetic filing record's period."""

    ANNUAL = "ANNUAL"
    QUARTERLY = "QUARTERLY"
    MONTHLY = "MONTHLY"


class FilingRecordScenario(StrEnum):
    """The edge-case scenario a synthetic record exercises.

    Values mirror the spread mandated by issue #14: a clean filing,
    a correction (``COMPLEMENTARIA``), a filing with errors, an
    amended filing, a cancelled filing, and a borderline rounding
    case.
    """

    CLEAN = "CLEAN"
    COMPLEMENTARIA = "COMPLEMENTARIA"
    WITH_ERRORS = "WITH_ERRORS"
    AMENDED = "AMENDED"
    CANCELLED = "CANCELLED"
    ROUNDING = "ROUNDING"


FixtureScalar = Decimal | int | str | bool | None


class FixtureCasilla(BaseModel):
    """One casilla on a :class:`FilingRecord`.

    Attributes:
        casilla_id: Stable casilla ID (e.g. ``"03"``). Loose string
            until #23 ships the casilla DB.
        label: Short human label for the casilla — kept in the
            fixture file so a human reading it sees what the number
            means without cross-referencing the modelo schema.
        value: The scalar value carried by this casilla. ``None``
            means "casilla present on the form but left blank".
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    casilla_id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    value: FixtureScalar


class FilingRecord(BaseModel):
    """One synthetic historical filing record.

    Every instance carries the synthetic-only invariant: the
    ``synthetic`` field is a :class:`Literal` ``True`` and the
    ``_comment`` field is a non-empty warning string. Both are
    enforced by pydantic strict validation — no code path can
    construct a :class:`FilingRecord` without them.

    The ``record_id`` is a stable 16-character SHA-256 prefix over
    ``(modelo, period, profile_tax_id, sorted casillas)``. It is
    persisted to the fixture file for diff stability and verified
    for uniqueness across the corpus by the colocated tests.
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        populate_by_name=True,
    )

    synthetic: Literal[True]
    comment: str = Field(..., alias="_comment", min_length=1)
    record_id: str = Field(..., min_length=1)
    modelo: str = Field(..., min_length=1)
    period: str = Field(..., min_length=1)
    period_kind: FilingRecordPeriodKind
    profile_tax_id: str = Field(..., min_length=1)
    status: FilingDraftStatus
    scenario: FilingRecordScenario
    casillas: tuple[FixtureCasilla, ...]
    totals: dict[str, Decimal]
    created_at: datetime
    submitted_at: datetime | None = None
    acknowledged_at: datetime | None = None
    source: Literal["synthetic"]
    complementaria_of: str | None = None
    notes: str = ""


def compute_record_id(
    *,
    modelo: str,
    period: str,
    profile_tax_id: str,
    casillas: tuple[FixtureCasilla, ...],
) -> str:
    """Compute the stable, content-addressed ``record_id``.

    Args:
        modelo: Modelo string ID.
        period: Period string (e.g. ``"2024Q1"``).
        profile_tax_id: Synthetic taxpayer tax ID.
        casillas: The casillas to hash, any order.

    Returns:
        A 16-character lowercase hex SHA-256 prefix.
    """
    sorted_casillas = sorted(casillas, key=lambda c: c.casilla_id)
    payload = {
        "modelo": modelo,
        "period": period,
        "profile_tax_id": profile_tax_id,
        "casillas": [c.model_dump(mode="json") for c in sorted_casillas],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


__all__ = [
    "SYNTHETIC_COMMENT_REQUIRED_SUBSTRING",
    "FilingRecord",
    "FilingRecordPeriodKind",
    "FilingRecordScenario",
    "FixtureCasilla",
    "FixtureScalar",
    "compute_record_id",
]
