"""The taxpayer's own statement of its Modelo 232 operations for one ejercicio.

Orden HFP/816/2017 art. 2 makes Modelo 232 depend on facts only the taxpayer
holds: whom it dealt with, of which type, under which valuation method and for
how much. Being related (LIS art. 18.2) is a relationship no ledger records, so
these facts are stated here and nothing infers them.

Four payload kinds share one encrypted namespace, each tagged with ``kind``:

* :class:`Modelo232Operation`, one stated operation or holding;
* :class:`Modelo232NoneStatement`, that the ejercicio had no related-party and
  no tax-haven operations;
* :class:`Modelo232TurnoverStatement`, the cifra de negocios the art. 2.3 ground
  compares against, with the source it was taken from;
* :class:`Modelo232YearGuard`, a counter every write of an ejercicio advances in
  the same batch, so two writes that each read the other's absence cannot both
  commit.

Every payload hides rejected input from its validation errors and is an
operator assertion. An operation keeps the art. 2.2 exclusion it states and is
never dropped for it, so the totals can leave it out and still show it.
Withdrawing a payload is a revision-guarded state change that keeps the row,
with when the assertion was made and when it was taken back. A statement that is
restated is a new row beside the withdrawn one.

The coded fields (tipo de vinculación, tipo de operación, método de valoración)
carry the record design's Tablas A, C and B. These models bound only their
shape, so a stored row never fails a read because of a catalogue; the write path
checks each code against the authority pinned for the row's ejercicio.
Nothing here puts a tax identifier, name or amount into an exception.
"""

from __future__ import annotations

import re
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, Field, PositiveInt, StringConstraints, model_validator

from ...core.country_code import COUNTRY_CODE_ALPHA2_PATTERN, CountryCodeAlpha2
from ...core.filing_year import FilingYear
from ...core.identity.tax_id import TaxIdIdentityToken
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import UtcInstant

__all__ = [
    "M232_GUARD_KIND",
    "M232_NONE_KIND",
    "M232_OPERATION_KIND",
    "M232_STATEMENT_NOTE_MAX_LENGTH",
    "M232_TURNOVER_KIND",
    "Modelo232Direction",
    "Modelo232Exclusion",
    "Modelo232NoneStatement",
    "Modelo232Operation",
    "Modelo232OperationKind",
    "Modelo232StatementState",
    "Modelo232TurnoverSource",
    "Modelo232TurnoverStatement",
    "Modelo232YearGuard",
]

M232_OPERATION_KIND: Final = "m232_operation"
M232_NONE_KIND: Final = "m232_none_statement"
M232_TURNOVER_KIND: Final = "m232_turnover_statement"
M232_GUARD_KIND: Final = "m232_year_guard"
"""The payload markers that tell the row types apart in the shared namespace."""

M232_STATEMENT_NOTE_MAX_LENGTH: Final[int] = 512
"""The longest operator note or source reference a payload keeps."""

_NAME_MAX_LENGTH: Final[int] = 60
"""The width of the design's name field (apellidos y nombre o razón social)."""

_TAX_ID_MAX_LENGTH: Final[int] = 15
"""The width of the design's identification field for the related person or entity."""

_DESCRIPTION_MAX_LENGTH: Final[int] = 50
"""The width of the design's description of a tax-haven operation."""

type _Importe = Annotated[Decimal, Field(ge=Decimal("0"), decimal_places=2)]
"""A non-negative euro amount with at most two decimals; a third decimal is refused, never rounded."""

type _Participation = Annotated[Decimal, Field(ge=Decimal("0"), le=Decimal("100"), decimal_places=2)]
"""A share of capital in percent, as the design's three integer and two decimal places hold it."""

type _RowId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
"""A random identity that names a row without naming its counterparty."""

type _Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=_NAME_MAX_LENGTH)]
type _TaxId = Annotated[TaxIdIdentityToken, Field(min_length=1, max_length=_TAX_ID_MAX_LENGTH)]

type _TipoVinculacion = Annotated[str, StringConstraints(pattern=r"^[0-9A-Z]{1}$")]
type _TipoOperacion = Annotated[str, StringConstraints(pattern=r"^[0-9A-Z]{2}$")]
type _MetodoValoracion = Annotated[str, StringConstraints(pattern=r"^[0-9A-Z]{2}$")]
"""The widths of Tablas A, C and B in the record design; the registry owns which codes they hold."""


class Modelo232StatementState(StrEnum):
    """Whether a payload currently stands as the operator's statement."""

    ACTIVE = "active"
    WITHDRAWN = "withdrawn"


class Modelo232OperationKind(StrEnum):
    """Which part of the Modelo 232 record design an operation belongs to."""

    RELATED_PARTY = "related_party"
    """An operation with a related person or entity (design section 3; arts. 2.1 and 2.3)."""
    INTANGIBLES_REDUCTION = "intangibles_reduction"
    """Income from a related person under the LIS art. 23 reduction (design section 4; art. 2.4)."""
    TAX_HAVEN_OPERATION = "tax_haven_operation"
    """An operation with a person or entity in a tax haven (design section 5; art. 2.5)."""
    TAX_HAVEN_HOLDING = "tax_haven_holding"
    """A holding of securities in a tax haven (design section 6; art. 2.5)."""


class Modelo232Direction(StrEnum):
    """Whether the taxpayer received or paid the consideration (the design's Ingreso / Pago indicator)."""

    INGRESO = "I"
    PAGO = "P"


class Modelo232Exclusion(StrEnum):
    """The art. 2.2 ground that removes an operation from the related-party information."""

    CONSOLIDATION_GROUP = "consolidation_group"
    """Operations between entities of one tax consolidation group (art. 2.2.a)."""
    AIE_OR_REGISTERED_UTE = "aie_or_registered_ute"
    """Operations of an AIE, or of a UTE entered in the special register, with its members or with other
    entities of the same tax consolidation group (art. 2.2.b). A UTE or analogous formula under LIS art. 22
    is not excluded: the Orden says those must file."""
    PUBLIC_OFFER = "public_offer"
    """Operations within a public offer of sale or acquisition of securities (art. 2.2.c)."""


class Modelo232TurnoverSource(StrEnum):
    """Where the stated turnover was taken from."""

    ANNUAL_ACCOUNTS = "annual_accounts"
    CORPORATION_TAX_RETURN = "corporation_tax_return"
    VAT_RETURNS = "vat_returns"
    OPERATOR_ESTIMATE = "operator_estimate"


def _check_withdrawal(
    *, state: Modelo232StatementState, withdrawn_at: UtcInstant | None, made_at: UtcInstant, subject: str
) -> None:
    withdrawn = state is Modelo232StatementState.WITHDRAWN
    if withdrawn != (withdrawn_at is not None):
        raise ValueError(f"{subject} carries a withdrawal instant exactly when withdrawn")
    if withdrawn_at is not None and withdrawn_at < made_at:
        raise ValueError(f"{subject} cannot be withdrawn before it was made")


class Modelo232YearGuard(BaseModel):
    """The counter that serialises every write of one ejercicio (payload schema v1).

    It holds no statement. Each operation, "none" or turnover write of the
    ejercicio advances it in the same revision-guarded batch, so a second write
    that read the ejercicio before the first committed is refused.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["m232_year_guard"] = M232_GUARD_KIND
    ejercicio: FilingYear
    counter: PositiveInt

    @property
    def identity(self) -> int:
        """Return the ejercicio this guard is stored under."""
        return self.ejercicio

    def advanced(self) -> Modelo232YearGuard:
        """Return the guard after one more write."""
        return self.model_copy(update={"counter": self.counter + 1})


class Modelo232Operation(BaseModel):
    """One related-party or tax-haven operation the taxpayer states for an ejercicio (payload schema v1)."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["m232_operation"] = M232_OPERATION_KIND
    operation_id: _RowId
    ejercicio: FilingYear
    operation_kind: Modelo232OperationKind
    counterparty_tax_id: _TaxId | None = None
    """The counterparty's identifier, foreign ones included; stated for the two related-person kinds."""
    counterparty_name: _Name
    counterparty_country: CountryCodeAlpha2
    """The counterparty's country, so a foreign counterparty is never read as Spanish."""
    tipo_vinculacion: _TipoVinculacion | None = None
    """The LIS art. 18.2 relationship (Tabla A); stated for the two related-person kinds."""
    tipo_operacion: _TipoOperacion | None = None
    """The operation type (Tabla C); stated for ``related_party`` only."""
    valuation_method: _MetodoValoracion | None = None
    """The valuation method (Tabla B); stated for ``related_party`` only."""
    direction: Modelo232Direction | None = None
    """Whether the taxpayer received or paid; stated for ``related_party`` only."""
    specific_operation: bool = False
    """Whether the operation is a specific one under art. 2.1.b; stated for ``related_party`` only."""
    amount_eur: _Importe
    """The consideration at market value; for a holding, its acquisition value."""
    exclusion: Modelo232Exclusion | None = None
    """The art. 2.2 ground that excludes the operation, when one applies; ``related_party`` only."""
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=_DESCRIPTION_MAX_LENGTH)]
        | None
    ) = None
    """What the operation was, as section 5 of the design asks; ``tax_haven_operation`` only."""
    participation_percent: _Participation | None = None
    """The share of the issuer held, as section 6 of the design asks; ``tax_haven_holding`` only."""
    parent_tax_id: _TaxId | None = None
    """The parent's identifier, as section 4 of the design asks; ``intangibles_reduction`` only."""
    parent_name: _Name | None = None
    """The parent's name; stated with :attr:`parent_tax_id`."""
    stated_at: UtcInstant
    state: Modelo232StatementState = Modelo232StatementState.ACTIVE
    withdrawn_at: UtcInstant | None = None

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if not re.fullmatch(COUNTRY_CODE_ALPHA2_PATTERN, self.counterparty_country):
            raise ValueError("a Modelo 232 operation needs an uppercase two-letter counterparty country")
        kind = self.operation_kind
        related_person = kind in (Modelo232OperationKind.RELATED_PARTY, Modelo232OperationKind.INTANGIBLES_REDUCTION)
        general = kind is Modelo232OperationKind.RELATED_PARTY
        for stated, needed, words in (
            (self.counterparty_tax_id, related_person, "a counterparty identifier"),
            (self.tipo_vinculacion, related_person, "a relationship type"),
            (self.tipo_operacion, general, "an operation type"),
            (self.valuation_method, general, "a valuation method"),
            (self.direction, general, "a direction"),
        ):
            if needed and stated is None:
                raise ValueError(f"this kind of Modelo 232 operation states {words}")
            if not needed and stated is not None:
                raise ValueError(f"this kind of Modelo 232 operation does not state {words}")
        if not general and (self.specific_operation or self.exclusion is not None):
            raise ValueError("only a related-party operation states art. 2.1.b or 2.2")
        for stated, allowed, words in (
            (self.description, kind is Modelo232OperationKind.TAX_HAVEN_OPERATION, "a description"),
            (self.participation_percent, kind is Modelo232OperationKind.TAX_HAVEN_HOLDING, "a participation"),
            (self.parent_tax_id, kind is Modelo232OperationKind.INTANGIBLES_REDUCTION, "a parent"),
            (self.parent_name, kind is Modelo232OperationKind.INTANGIBLES_REDUCTION, "a parent"),
        ):
            if stated is not None and not allowed:
                raise ValueError(f"this kind of Modelo 232 operation does not state {words}")
        if (self.parent_tax_id is None) != (self.parent_name is None):
            raise ValueError("a Modelo 232 parent is stated with both its identifier and its name")
        _check_withdrawal(
            state=self.state, withdrawn_at=self.withdrawn_at, made_at=self.stated_at, subject="a Modelo 232 operation"
        )
        return self

    @property
    def identity(self) -> tuple[int, str]:
        """Return the ``(ejercicio, operation_id)`` this operation is stored under."""
        return (self.ejercicio, self.operation_id)

    @property
    def active(self) -> bool:
        """Return whether the operation currently stands."""
        return self.state is Modelo232StatementState.ACTIVE

    @property
    def excluded(self) -> bool:
        """Return whether an art. 2.2 ground removes the operation from the totals."""
        return self.exclusion is not None

    def withdrawn(self, at: UtcInstant) -> Modelo232Operation:
        """Return this operation taken back at ``at``."""
        return self.model_copy(update={"state": Modelo232StatementState.WITHDRAWN, "withdrawn_at": at})


class Modelo232NoneStatement(BaseModel):
    """The taxpayer's statement that an ejercicio had no related-party and no tax-haven operations (schema v1)."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["m232_none_statement"] = M232_NONE_KIND
    statement_id: _RowId
    ejercicio: FilingYear
    note: Annotated[str, Field(min_length=1, max_length=M232_STATEMENT_NOTE_MAX_LENGTH)]
    """Why the taxpayer states it; required, because the statement must be answerable."""
    stated_at: UtcInstant
    state: Modelo232StatementState = Modelo232StatementState.ACTIVE
    withdrawn_at: UtcInstant | None = None

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if not self.note.strip():
            raise ValueError("a Modelo 232 none statement needs a non-blank note")
        _check_withdrawal(
            state=self.state,
            withdrawn_at=self.withdrawn_at,
            made_at=self.stated_at,
            subject="a Modelo 232 none statement",
        )
        return self

    @property
    def identity(self) -> tuple[int, str]:
        """Return the ``(ejercicio, statement_id)`` this statement is stored under."""
        return (self.ejercicio, self.statement_id)

    @property
    def active(self) -> bool:
        """Return whether the statement currently stands."""
        return self.state is Modelo232StatementState.ACTIVE

    def withdrawn(self, at: UtcInstant) -> Modelo232NoneStatement:
        """Return this statement taken back at ``at``."""
        return self.model_copy(update={"state": Modelo232StatementState.WITHDRAWN, "withdrawn_at": at})


class Modelo232TurnoverStatement(BaseModel):
    """The cifra de negocios of an ejercicio, with where it came from (schema v1)."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["m232_turnover_statement"] = M232_TURNOVER_KIND
    statement_id: _RowId
    ejercicio: FilingYear
    turnover_eur: _Importe
    source: Modelo232TurnoverSource
    source_reference: Annotated[str, Field(min_length=1, max_length=M232_STATEMENT_NOTE_MAX_LENGTH)]
    """A free reference to the document or return the figure was taken from."""
    stated_at: UtcInstant
    state: Modelo232StatementState = Modelo232StatementState.ACTIVE
    withdrawn_at: UtcInstant | None = None

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if not self.source_reference.strip():
            raise ValueError("a Modelo 232 turnover statement needs a non-blank source reference")
        _check_withdrawal(
            state=self.state,
            withdrawn_at=self.withdrawn_at,
            made_at=self.stated_at,
            subject="a Modelo 232 turnover statement",
        )
        return self

    @property
    def identity(self) -> tuple[int, str]:
        """Return the ``(ejercicio, statement_id)`` this statement is stored under."""
        return (self.ejercicio, self.statement_id)

    @property
    def active(self) -> bool:
        """Return whether the statement currently stands."""
        return self.state is Modelo232StatementState.ACTIVE

    def withdrawn(self, at: UtcInstant) -> Modelo232TurnoverStatement:
        """Return this statement taken back at ``at``."""
        return self.model_copy(update={"state": Modelo232StatementState.WITHDRAWN, "withdrawn_at": at})
