"""The profile fact grammar of the position record.

The record is a repeatable profile section: a row is a set of facts at
``inversiones_posicion.{n}.{leaf}``, where ``{n}`` is the position of the row.
The profile never reuses a position, so ``{n}`` is the stable row key a ledger
row names.

Every leaf is one flat value with one canonical stored form: the kind and the
dates as typed tokens, the payer identifier and the source state upper-cased,
the ownership share with exactly two decimals.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Final

from pydantic import ValidationError

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.parsing.dates import parse_iso8601_date
from .inmueble_facts import rows_from_facts
from .posicion_record import PosicionRecord

POSICION_SECTION: Final = "inversiones_posicion"

_CENTS: Final = Decimal("0.01")
_REQUIRED_LEAVES: Final = (
    "tipo",
    "pagador_nif",
    "pagador_nombre",
    "pais_origen",
    "porcentaje_titularidad",
    "fecha_inicio",
)
type RowValues = Mapping[str, str]


def _refuse(message: str, *, leaf: str) -> ProfileAnswerTypeError:
    return ProfileAnswerTypeError(message, context={"key": leaf})


def _error_leaf(error: ValidationError) -> str:
    for item in error.errors():
        context = getattr(getattr(item.get("ctx", {}).get("error"), "__cause__", None), "context", None) or {}
        key = context.get("key")
        if isinstance(key, str):
            return key
        if item["loc"]:
            return str(item["loc"][-1])
    return "row"


def _date(raw: str, *, leaf: str) -> date:
    try:
        parsed = parse_iso8601_date(raw)
    except ValueError:
        parsed = None
    if parsed is None:
        raise _refuse("write a calendar date as YYYY-MM-DD", leaf=leaf)
    return parsed


def _share(raw: str) -> Decimal:
    value = try_parse_canonical_decimal(raw)
    if value is None:
        raise _refuse("write a percentage as a decimal number", leaf="porcentaje_titularidad")
    return value


def posicion_from_row(clave: int, row: RowValues) -> PosicionRecord:
    """Build one position from the facts of its row, refusing what does not cohere."""
    for leaf in _REQUIRED_LEAVES:
        if leaf not in row:
            raise _refuse(
                "a position states its kind, its payer, its source state, the share held and since when",
                leaf=leaf,
            )
    data = {
        "clave": clave,
        "tipo": row["tipo"],
        "pagador_nif": row["pagador_nif"],
        "pagador_nombre": row["pagador_nombre"],
        "pais_origen": row["pais_origen"],
        "porcentaje_titularidad": _share(row["porcentaje_titularidad"]),
        "fecha_inicio": _date(row["fecha_inicio"], leaf="fecha_inicio"),
        "fecha_fin": _date(row["fecha_fin"], leaf="fecha_fin") if "fecha_fin" in row else None,
        "identificador": row.get("identificador"),
    }
    try:
        return PosicionRecord.model_validate(data, strict=False)
    except ValidationError as error:
        raise _refuse("the stated facts do not cohere", leaf=_error_leaf(error)) from error


def posicion_row_values(record: PosicionRecord) -> dict[str, str]:
    """Project a position to the facts of its row; a fact never stated has no entry."""
    values = {
        "tipo": record.tipo.value,
        "pagador_nif": record.pagador_nif,
        "pagador_nombre": record.pagador_nombre,
        "pais_origen": record.pais_origen,
        "porcentaje_titularidad": format(record.porcentaje_titularidad.quantize(_CENTS), "f"),
        "fecha_inicio": record.fecha_inicio.isoformat(),
    }
    if record.fecha_fin is not None:
        values["fecha_fin"] = record.fecha_fin.isoformat()
    if record.identificador is not None:
        values["identificador"] = record.identificador
    return values


def posiciones_from_facts(path_values: Mapping[str, object]) -> tuple[PosicionRecord, ...]:
    """Read every stored position, ascending by row key; a cleared row is absent."""
    return tuple(
        posicion_from_row(clave, row) for clave, row in sorted(rows_from_facts(POSICION_SECTION, path_values).items())
    )


__all__ = ["POSICION_SECTION", "posicion_from_row", "posicion_row_values", "posiciones_from_facts"]
