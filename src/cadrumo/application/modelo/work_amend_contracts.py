"""Exact filing baselines and explicit scalar/detail overrides for amendments."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind, M303RectificativaMotive
from .edit_apply_row_contracts import ModeloDetailRowWireV1


class ModeloWorkAmendBaseline(BaseModel):
    """The externally filed return an amendment corrects.

    An amendment is only meaningful against a specific filed baseline, so the
    request names that record rather than a work unit: the baseline supplies
    the full casilla map, and the overrides replace only what changed.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    from_filing_record_id: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkAmendOverride(BaseModel):
    """One corrected casilla and the value that replaces it.

    The value crosses as an exact decimal STRING rather than a number. A public
    operation schema must validate and serialize to the same shape, and a bare
    Decimal does not: it accepts number-or-string and emits string. Carrying the
    digits avoids that asymmetry and any float coercion on the way.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    casilla_id: Annotated[str, Field(min_length=1, max_length=64)]
    value: Annotated[str, Field(pattern=r"^-?\d{1,15}(?:\.\d{1,6})?$")]

    def as_decimal(self) -> Decimal:
        """Return the exact value this override carries."""
        return Decimal(self.value)


#: How many detail rows one amendment may carry.
#:
#: An engineering bound on a journalled request, not a legal cardinality: no
#: official record design caps the counterparties an M347 declares, so a limit
#: near the override cap would refuse a lawful return from a busy gestoria.
_MAX_AMENDMENT_DETAIL_ROWS: Final = 20_000


class ModeloWorkAmendRequest(BaseModel):
    """One amendment: which baseline, which corrections, and why.

    ``reason`` is required because an amendment is a declaration to the tax
    authority that a previously filed figure was wrong; a correction with no
    stated reason is not something the operator should be able to file.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    baseline: ModeloWorkAmendBaseline
    amendment_kind: CalculationRevisionAmendmentKind
    overrides: Annotated[tuple[ModeloWorkAmendOverride, ...], Field(min_length=1, max_length=500)]
    reason: Annotated[str, Field(min_length=1, max_length=500)]
    m303_rectificativa_motive: M303RectificativaMotive | None = None

    #: The rows this amendment declares, or ``None`` where it declares none.
    #:
    #: THREE STATES, NOT TWO, and the authority reads all three. For M184,
    #: M232, M347 and M349 the per-counterpart rows ARE the declaration, so
    #: ``None`` -- the caller having said nothing -- is refused rather than
    #: guessed: a complementaria COMPLETES a return while a sustitutiva
    #: REPLACES it (LGT art. 122.2 para. 2), and silence would be read
    #: differently by each. An empty tuple is not that silence; it is the
    #: positive statement that the period had no rows, and is accepted as one.
    #: Every other modelo has no rows to declare, so ``None`` there is simply
    #: its ordinary shape.
    #:
    #: Optional here rather than required because those other modelos are the
    #: majority of this operation's traffic; the refusal that makes the
    #: distinction binding lives with the authority that knows which modelo the
    #: baseline belongs to, which this request does not carry.
    #:
    #: The rows cross as their payload-safe wire mirror rather than the domain
    #: ``ModeloDetailRow``: two of those six hydrate registry codes through
    #: before-validators, which the payload-graph gate refuses because a
    #: published schema would then not describe what validation accepts. The
    #: mirror already exists for the edit operation, and reusing it keeps one
    #: translation rather than a second free to drift.
    detail_rows: Annotated[tuple[ModeloDetailRowWireV1, ...], Field(max_length=_MAX_AMENDMENT_DETAIL_ROWS)] | None = (
        None
    )

    #: The operator this invocation acts as. The platform binds an actor at
    #: submission, never at composition, so baking one into a definition would
    #: make the production registry per-actor.
    actor: Annotated[str, Field(min_length=1, max_length=128)]

    @model_validator(mode="after")
    def _distinct_amendment_overrides(self) -> Self:
        if len({item.casilla_id for item in self.overrides}) != len(self.overrides):
            raise ValueError("amendment overrides must address distinct casillas")
        return self
