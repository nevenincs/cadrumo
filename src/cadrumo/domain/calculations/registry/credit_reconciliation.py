"""The credit reconciliation a Modelo 100 revision declares for each casilla of withholding suffered.

A credit casilla takes its value from one declared source and is compared with
every other source that states the same figure. The comparison is declared in
the registry, one entry per credit casilla, so no resolver, gate or modelo name
decides which sources corroborate a credit::

    [[revisions."2022".credit_reconciliation]]
    casilla_id = "0596"
    value_source = { binding = "renta-retencion-soportada-trabajo" }
    cross_checks = [{ kind = "borrador", binding = "renta-retencion-soportada-trabajo" }]

``value_source`` names the binding bound to the casilla, or the formula that
computes it. Each cross-check is one closed member: the payer records of an
income class, the value a borrador snapshot holds for a binding, or a ledger
binding's value. A cross-check may name one operand of the value source's
formula instead of the whole casilla, so a casilla summing two independently
evidenced parts compares each part with the source that states that part.

Every member is closed and hydrated at the loader boundary. The rules that need
the rest of the revision run at registry build (:mod:`.credit_reconciliation_checks`).

A casilla may also say which side of a withholding it records. Payer-side
returns and the perceptor's own pago fraccionado share a semantic role for
their withholding boxes, so a role cannot tell a credit source from a figure the
taxpayer practised on others; ``withholding_side`` can, and an undeclared side is
never read as suffered.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BeforeValidator, Field, model_validator

from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.retencion_soportada import RetencionSoportadaClase
from .errors import RegistryValidationError
from .ids import BindingId, FormulaId
from .schema_base import RegistryModel, coerce_enum_member

__all__ = [
    "BorradorCrossCheck",
    "CreditCrossCheck",
    "CreditCrossCheckKind",
    "CreditReconciliationEntry",
    "CreditReconciliationOperand",
    "CreditReconciliationValueSource",
    "LedgerCrossCheck",
    "RetencionSoportadaCrossCheck",
    "WithholdingSide",
    "WithholdingSideField",
]


class WithholdingSide(StrEnum):
    """Whose withholding a casilla records: the declarant's own credit, or what the declarant practised."""

    SUFFERED = "suffered"
    """Withholding borne by the declarant, which the declarant credits."""
    PRACTISED = "practised"
    """Withholding the declarant practised on others as a withholding agent."""


WithholdingSideField = Annotated[WithholdingSide, BeforeValidator(coerce_enum_member(WithholdingSide))]
"""Registry token hydrated into a :class:`WithholdingSide` member."""


class CreditCrossCheckKind(StrEnum):
    """The closed set of sources a credit casilla may be compared with."""

    RETENCION_SOPORTADA = "retencion_soportada"
    BORRADOR = "borrador"
    LEDGER = "ledger"


class _ExactlyOneReference(RegistryModel):
    """A reference to exactly one of a binding and a second kind of registry member."""

    def _require_exactly_one(self, *references: object) -> None:
        if sum(reference is not None for reference in references) != 1:
            raise RegistryValidationError(f"{type(self).__name__} names exactly one reference")


class CreditReconciliationValueSource(_ExactlyOneReference):
    """The binding bound to a credit casilla, or the formula that computes it."""

    binding: BindingId | None = None
    formula: FormulaId | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _names_one(self) -> Self:
        self._require_exactly_one(self.binding, self.formula)
        return self


class CreditReconciliationOperand(_ExactlyOneReference):
    """One operand of the value source's formula: a casilla it reads or a binding it reads."""

    casilla_id: CasillaId | None = None
    binding: BindingId | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _names_one(self) -> Self:
        self._require_exactly_one(self.casilla_id, self.binding)
        return self


class RetencionSoportadaCrossCheck(RegistryModel):
    """The payer records of one income class, the credit evidenced by each payer's certificate."""

    kind: Literal[CreditCrossCheckKind.RETENCION_SOPORTADA] = CreditCrossCheckKind.RETENCION_SOPORTADA
    income_class: Annotated[RetencionSoportadaClase, BeforeValidator(coerce_enum_member(RetencionSoportadaClase))]
    operand: CreditReconciliationOperand | None = None


class BorradorCrossCheck(RegistryModel):
    """The value an active borrador snapshot holds for one binding, compared and never supplied."""

    kind: Literal[CreditCrossCheckKind.BORRADOR] = CreditCrossCheckKind.BORRADOR
    binding: BindingId
    operand: CreditReconciliationOperand | None = None


class LedgerCrossCheck(RegistryModel):
    """The value one ledger binding resolves to over the same ejercicio."""

    kind: Literal[CreditCrossCheckKind.LEDGER] = CreditCrossCheckKind.LEDGER
    binding: BindingId
    operand: CreditReconciliationOperand | None = None


CreditCrossCheck = Annotated[
    RetencionSoportadaCrossCheck | BorradorCrossCheck | LedgerCrossCheck,
    Field(discriminator="kind"),
]
"""Every source a credit casilla may be cross-checked against, discriminated on ``kind``."""


class CreditReconciliationEntry(RegistryModel):
    """How one credit casilla is sourced and what it is compared with."""

    casilla_id: CasillaId
    value_source: CreditReconciliationValueSource
    cross_checks: tuple[CreditCrossCheck, ...] = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _distinct_cross_checks(self) -> Self:
        if len(set(self.cross_checks)) != len(self.cross_checks):
            raise RegistryValidationError(
                f"credit reconciliation of casilla {self.casilla_id!r} declares the same cross-check twice"
            )
        return self
