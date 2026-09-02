"""Strict amendment domain records for :mod:`domain.filing`.

Houses the immutable records that describe an AEAT amendment. The
``amended_draft`` field on each amendment record holds the originating
:class:`ModeloDraft` that the amendment modifies, keeping the draft's
casilla arithmetic and tax due values bound to the amendment for
audit purposes.

Concrete variants are :class:`ModeloComplementaria` (LGT Art. 122.2)
and :class:`ModeloSustitutiva` (LGT Art. 122.1), the
:class:`CasillaChange` delta entries, and the :class:`AmendmentKind`
enum. The orchestration use case
:func:`application.filing.build_complementaria` lives at
:mod:`application.filing._complementaria`; this module contains
only the typed shapes and the deterministic
:func:`make_amendment_id` helper so the repository (also under
:mod:`domain.filing`) can persist amendments without depending
on the application layer.

Callers operate on the discriminated union ``ModeloComplementaria |
ModeloSustitutiva``. There is no umbrella alias - pick the variant
that matches the LGT Art. 122 article you're filing under.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from ...core.casilla_id import CasillaId
from ...core.hashing import content_hash_hex
from ...core.identity import AeatCsv
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period
from ...core.time.utc import UtcInstant
from ..modelos.codes import ModeloCode
from .protocols import ModeloInputs
from .schema import ModeloDraft

type CasillaInputs = ModeloInputs
"""Updated casilla inputs supplied to an amendment build.

An amendment restates casilla values, so its input contract is the
same canonical :data:`domain.filing.ModeloInputs` mapping the
filing builder consumes."""


class AmendmentKind(StrEnum):
    """Legally distinct amendment kinds supported by the engine."""

    COMPLEMENTARIA = "complementaria"
    SUSTITUTIVA = "sustitutiva"


class CasillaChange(BaseModel):
    """One changed casilla in an amendment delta."""

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    old_value: Decimal | None = None
    new_value: Decimal
    reason: str = Field(min_length=1)


type CasillaDelta = tuple[CasillaChange, ...]


class BaseAmendment(BaseModel):
    """Shared shape across the two LGT Art. 122 amendment variants.

    Concrete subclasses fix the ``amendment_kind`` discriminator to a
    single :class:`AmendmentKind` literal so callers select the variant
    by class, not by enum value.
    """

    model_config = _STRICT_FROZEN

    amendment_id: str = Field(min_length=1)
    submission_id: str = Field(min_length=1)
    original_csv: AeatCsv
    original_model: ModeloCode = Field(min_length=1)
    original_period: Period
    delta: CasillaDelta = Field(min_length=1)
    amended_draft: ModeloDraft
    # An amendment's audit instant must obey the same persisted UTC contract
    # as its embedded draft.  A naive or offset-aware value makes the legal
    # correction chronology ambiguous after encrypted rehydration.
    created_at: UtcInstant


class ModeloComplementaria(BaseAmendment):
    """LGT Art. 122.2 complementaria: corrects an already-presented filing."""

    amendment_kind: Literal[AmendmentKind.COMPLEMENTARIA] = AmendmentKind.COMPLEMENTARIA


class ModeloSustitutiva(BaseAmendment):
    """LGT Art. 122.1 sustitutiva: replaces an already-presented filing in full."""

    amendment_kind: Literal[AmendmentKind.SUSTITUTIVA] = AmendmentKind.SUSTITUTIVA


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
    return content_hash_hex(payload)[:16]


__all__ = [
    "AmendmentKind",
    "BaseAmendment",
    "CasillaChange",
    "CasillaDelta",
    "CasillaInputs",
    "ModeloComplementaria",
    "ModeloSustitutiva",
    "make_amendment_id",
]
