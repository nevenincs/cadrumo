"""Exact-profile request schemas for the Modelo 232 related-party statements.

A statement request carries the operator's fields only. The worker gives the
new row its random identity and the instant it was stated, then builds the
domain payload, whose validation decides whether the fields form a statement
of their kind. Counterparty identifiers and names are sensitive inputs: the
models never echo them in a validation error.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.modelos.m232_related_party import (
    M232_STATEMENT_NOTE_MAX_LENGTH,
    Modelo232Direction,
    Modelo232Exclusion,
    Modelo232OperationKind,
    Modelo232TurnoverSource,
)
from ..operations.public_scalar import PublicDecimal

__all__ = [
    "Modelo232NoneStateRequest",
    "Modelo232NoneWithdrawRequest",
    "Modelo232OperationStateRequest",
    "Modelo232OperationWithdrawRequest",
    "Modelo232RelatedPartyListRequest",
    "Modelo232RelatedPartyProfileRequest",
    "Modelo232RelatedPartyWriteRequest",
    "Modelo232TurnoverStateRequest",
    "Modelo232TurnoverWithdrawRequest",
]

type _Revision = Annotated[str, Field(min_length=1, max_length=128)]
type _RowId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
type _Text = Annotated[str, Field(min_length=1, max_length=256)]
type _Code = Annotated[str, Field(min_length=1, max_length=8)]
type _Note = Annotated[str, Field(min_length=1, max_length=M232_STATEMENT_NOTE_MAX_LENGTH)]


class Modelo232RelatedPartyProfileRequest(BaseModel):
    """The exact profile and ejercicio a related-party operation addresses."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    ejercicio: FilingYear


class Modelo232RelatedPartyListRequest(Modelo232RelatedPartyProfileRequest):
    """Read everything stated for one ejercicio, active and withdrawn, and what it decides."""


class Modelo232RelatedPartyWriteRequest(Modelo232RelatedPartyProfileRequest):
    """A statement or withdrawal of one ejercicio."""


class Modelo232OperationStateRequest(Modelo232RelatedPartyWriteRequest):
    """State one related-party or tax-haven operation of the ejercicio.

    ``expected_guard_revision_id`` is the guard revision a listing showed;
    given, the statement is refused when the ejercicio changed since.
    """

    operation_kind: Modelo232OperationKind
    counterparty_tax_id: _Text | None = None
    counterparty_name: _Text
    counterparty_country: Annotated[str, Field(min_length=1, max_length=8)]
    tipo_vinculacion: _Code | None = None
    tipo_operacion: _Code | None = None
    valuation_method: _Code | None = None
    direction: Modelo232Direction | None = None
    specific_operation: bool = False
    amount_eur: PublicDecimal
    exclusion: Modelo232Exclusion | None = None
    description: _Text | None = None
    participation_percent: PublicDecimal | None = None
    parent_tax_id: _Text | None = None
    parent_name: _Text | None = None
    expected_guard_revision_id: _Revision | None = None


class Modelo232OperationWithdrawRequest(Modelo232RelatedPartyWriteRequest):
    """Withdraw one active operation, guarded by the revision its row was listed at."""

    operation_id: _RowId
    expected_revision_id: _Revision


class Modelo232NoneStateRequest(Modelo232RelatedPartyWriteRequest):
    """State that the ejercicio had no related-party and no tax-haven operations, and why."""

    note: _Note
    expected_guard_revision_id: _Revision | None = None


class Modelo232NoneWithdrawRequest(Modelo232RelatedPartyWriteRequest):
    """Withdraw the active "none" statement, guarded by the revision its row was listed at."""

    expected_revision_id: _Revision


class Modelo232TurnoverStateRequest(Modelo232RelatedPartyWriteRequest):
    """State the ejercicio's cifra de negocios and where it was taken from."""

    turnover_eur: PublicDecimal
    source: Modelo232TurnoverSource
    source_reference: _Note
    expected_guard_revision_id: _Revision | None = None


class Modelo232TurnoverWithdrawRequest(Modelo232RelatedPartyWriteRequest):
    """Withdraw the active turnover statement, guarded by the revision its row was listed at."""

    expected_revision_id: _Revision
