"""Closed value set for the income concept a receipt carries.

Some calculation bases are not "everything that came in". RD 439/2007 art. 110.1.c)
fixes the agrarian pago fraccionado at *el 2 por ciento del volumen de ingresos del
trimestre, excluidas las subvenciones de capital y las indemnizaciones*, and the AEAT
Modelo 131 instrucciones say the same thing from the other side, naming what stays in:

    Consignaremos en esta casilla el volumen de ingresos del trimestre por el que se
    realiza el pago fraccionado, incluidas las subvenciones corrientes y excluidas las
    subvenciones de capital y las indemnizaciones.

That sentence is the whole reason this typed axis exists. The distinction it draws is not
between subsidies and other income — it is *inside* subsidies: a subvención corriente
counts and a subvención de capital does not. No amount, category, counterparty or date
on a ledger row can tell those two apart, so the concept has to be declared, and
nothing else in the taxonomy carries it. :class:`OperationKind347` has a ``SUBSIDY``
member, but that is a Modelo 347 clave describing an operation with a counterparty,
not a statement about whether a receipt belongs in a base.

Absence means ordinary income, deliberately. The overwhelming majority of receipts are
ordinary trading income, and a taxpayer who never touches the field must still have a
correct base; defaulting the other way would drop real income out of a declared volume,
which is the silent under-declaration this project treats as the worst failure mode.
The cost of that choice is stated rather than hidden: a subvención de capital that the
operator never marks is included and over-declares. That is the direction the error has
to point, because an unmarked receipt is far more likely to be ordinary than exceptional.

See Also:
    :func:`~domain.transactions.counts_toward_volumen_de_ingresos`
        The predicate consumers use; do not re-derive the membership test.
"""

from __future__ import annotations

from typing import Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from .errors.hierarchy import CoreValidationError

__all__ = ["ConceptoIngreso"]


class ConceptoIngreso(str):
    """Opaque receipt-concept token projected from the governed facts registry.

    The dated facts catalogue owns the income-concept vocabulary and the
    provision-specific exclusion sets. This core type carries only the typed
    wire token; callers must obtain instances through the registry projection.
    """

    __slots__ = ()

    def __new__(cls, value: str, *, _registry_validated: bool = False) -> Self:
        """Create a validated income-concept token."""
        if not _registry_validated:
            raise TypeError("ConceptoIngreso tokens must be projected from the facts registry")
        if not isinstance(value, str) or not value:
            raise ValueError("ConceptoIngreso token must be a non-empty string")
        return str.__new__(cls, value)

    @classmethod
    def from_registry(cls, value: str) -> Self:
        """Construct the typed value from its canonical registry token."""
        return cls(value, _registry_validated=True)

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise CoreValidationError("ConceptoIngreso must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: object,
        _handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Expose the projected income-concept token to Pydantic."""
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def value(self) -> str:
        """Return the canonical registry token for serialization."""
        return str(self)

    @property
    def name(self) -> str:
        """Return the canonical registry token for diagnostics."""
        return str(self)
