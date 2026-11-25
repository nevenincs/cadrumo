"""Which subject a ledger row is linked to, and what each link's concept needs.

A row belongs to at most one subject: a lease, a property or a savings position.
A concept names what the row is within its subject, so it is meaningless
without that subject and a savings link is incomplete without its concept.
Which concepts exist, and which position kinds admit them, is registry data.
"""

from __future__ import annotations

from .errors import TransactionValidationError


def validate_ledger_links(
    *,
    arrendamiento_ref: str | None,
    inmueble_ref: str | None,
    gasto_capital_inmobiliario: object | None,
    posicion_ref: str | None,
    concepto_capital_mobiliario: object | None,
) -> None:
    """Refuse a row that links to two subjects or carries a concept without its subject.

    Raises:
        TransactionValidationError: When the links are not consistent.
    """
    if sum(ref is not None for ref in (arrendamiento_ref, inmueble_ref, posicion_ref)) > 1:
        raise TransactionValidationError(
            "arrendamiento_ref, inmueble_ref and posicion_ref are mutually exclusive: "
            "a row links to one lease, one property or one savings position",
        )
    if gasto_capital_inmobiliario is not None and inmueble_ref is None:
        raise TransactionValidationError("gasto_capital_inmobiliario requires inmueble_ref")
    if concepto_capital_mobiliario is not None and posicion_ref is None:
        raise TransactionValidationError("concepto_capital_mobiliario requires posicion_ref")
    if posicion_ref is not None and concepto_capital_mobiliario is None:
        raise TransactionValidationError("posicion_ref requires concepto_capital_mobiliario")


__all__ = ["validate_ledger_links"]
