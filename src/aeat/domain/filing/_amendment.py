"""Strict amendment domain records for :mod:`aeat.domain.filing`.

Houses the immutable records that describe a filing amendment — the
:class:`FilingAmendment` aggregate, its :class:`CasillaChange` delta
entries, and the :class:`AmendmentKind` enum. The orchestration use
case (``build_complementaria``) lives at
:mod:`aeat.application.filing._complementaria`; this module contains
only the typed shapes and the deterministic
:func:`make_amendment_id` helper so the repository (also under
:mod:`aeat.domain.filing`) can persist amendments without depending
on the application layer.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ._schema import FilingDraft

type ModeloCode = str
type CasillaInputs = Mapping[str, object]

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class AmendmentKind(StrEnum):
    """Legally distinct amendment kinds supported by the engine."""

    COMPLEMENTARIA = "complementaria"
    SUSTITUTIVA = "sustitutiva"


class CasillaChange(BaseModel):
    """One changed casilla in an amendment delta."""

    model_config = _STRICT_FROZEN

    casilla_code: str = Field(min_length=1)
    old_value: Decimal | None = None
    new_value: Decimal
    reason: str = Field(min_length=1)


type CasillaDelta = tuple[CasillaChange, ...]


class FilingAmendment(BaseModel):
    """Immutable amendment record derived from a previously submitted filing."""

    model_config = _STRICT_FROZEN

    amendment_id: str = Field(min_length=1)
    submission_id: str = Field(min_length=1)
    original_csv: str = Field(min_length=1)
    original_model: ModeloCode = Field(min_length=1)
    original_period: str = Field(min_length=1)
    amendment_kind: AmendmentKind
    delta: CasillaDelta = Field(min_length=1)
    amended_draft: FilingDraft
    created_at: datetime


def make_amendment_id(
    *,
    submission_id: str,
    amendment_kind: AmendmentKind,
    delta: CasillaDelta,
) -> str:
    """Compute a stable amendment identifier."""
    payload = {
        "submission_id": submission_id,
        "amendment_kind": amendment_kind.value,
        "delta": [change.model_dump(mode="json") for change in delta],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


__all__ = [
    "AmendmentKind",
    "CasillaChange",
    "CasillaDelta",
    "CasillaInputs",
    "FilingAmendment",
    "ModeloCode",
    "make_amendment_id",
]
