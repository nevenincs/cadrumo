"""The profile fact grammar of the IAE premises, surface-class and tax-element records.

Each record is a repeatable profile section: a row is a set of facts at
``iae_local.{n}.{leaf}``, ``iae_local_superficie.{n}.{leaf}`` or
``iae_elemento_tributario.{n}.{leaf}``, where ``{n}`` is the position of the
row. The profile never reuses a position, so ``{n}`` is the durable identity of
a row: a local's is the key the Anexo Relacion de locales repeats by and the
key its surface-class rows name.

Every leaf is one typed value; a malformed value refuses and names its leaf,
and a value never stated has no fact rather than a zero.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, ValidationError

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.hierarchy import ProfileAnswerTypeError
from .iae_local_record import IaeElementoTributarioRecord, IaeLocalRecord, IaeLocalSuperficieRecord
from .inmueble_facts import rows_from_facts

IAE_LOCAL_SECTION: Final = "iae_local"
IAE_LOCAL_SUPERFICIE_SECTION: Final = "iae_local_superficie"
IAE_ELEMENTO_TRIBUTARIO_SECTION: Final = "iae_elemento_tributario"

_WHOLE_NUMBER: Final = re.compile(r"^\d{1,5}$")
_LOCAL_INTEGER_LEAVES: Final = (
    "numero",
    "superficie_total",
    "superficie_rectificada",
    "superficie_computable",
)
_SURFACE_LEAVES: Final = ("total", "rectificada", "computable")
_LOCAL_TEXT_LEAVES: Final = (
    "via_sg",
    "via_nombre",
    "km",
    "portal",
    "escalera",
    "piso",
    "puerta",
    "postcode",
    "province_code",
    "municipality_code",
    "municipality_name",
    "telefono",
    "uso_destino_code",
    "uso_destino_description",
)

type RowValues = Mapping[str, str]


def _refuse(message: str, *, leaf: str) -> ProfileAnswerTypeError:
    return ProfileAnswerTypeError(message, context={"key": leaf})


def _whole_number(raw: str, *, leaf: str) -> int:
    if not _WHOLE_NUMBER.fullmatch(raw):
        raise _refuse("write a whole number of at most five digits", leaf=leaf)
    return int(raw)


def _row_key(raw: str | None, *, leaf: str) -> int:
    if raw is None:
        raise _refuse("name the row this row belongs to", leaf=leaf)
    if not raw.isdigit():
        raise _refuse("a row key is a whole number", leaf=leaf)
    return int(raw)


def _error_leaf(error: ValidationError) -> str:
    for item in error.errors():
        context = getattr(getattr(item.get("ctx", {}).get("error"), "__cause__", None), "context", None) or {}
        key = context.get("key")
        if isinstance(key, str):
            return key
        if item["loc"]:
            return str(item["loc"][-1])
    return "row"


def _validated[ModelT: BaseModel](model: type[ModelT], data: Mapping[str, object]) -> ModelT:
    try:
        return model.model_validate(data, strict=False)
    except ValidationError as error:
        raise _refuse("the stated facts do not cohere", leaf=_error_leaf(error)) from error


def _stated(record: BaseModel, leaves: tuple[str, ...]) -> dict[str, str]:
    """The leaves of ``record`` that hold a value, as their stored text."""
    values: dict[str, str] = {}
    for leaf in leaves:
        value = getattr(record, leaf)
        if value is not None:
            values[leaf] = str(value)
    return values


def iae_local_from_row(clave: int, row: RowValues) -> IaeLocalRecord:
    """Read one local from the facts of its row."""
    data: dict[str, object] = {
        "clave": clave,
        "actividad": _row_key(row.get("actividad"), leaf="actividad"),
        "afectacion": row.get("afectacion"),
    }
    data.update({leaf: row[leaf] for leaf in _LOCAL_TEXT_LEAVES if leaf in row})
    data.update({leaf: _whole_number(row[leaf], leaf=leaf) for leaf in _LOCAL_INTEGER_LEAVES if leaf in row})
    return _validated(IaeLocalRecord, data)


def iae_local_row_values(record: IaeLocalRecord) -> dict[str, str]:
    """Project a local to the facts of its row; a fact never stated has no entry."""
    return {
        "actividad": str(record.actividad),
        "afectacion": record.afectacion.value,
        **_stated(record, _LOCAL_TEXT_LEAVES),
        **_stated(record, _LOCAL_INTEGER_LEAVES),
    }


def iae_superficie_from_row(clave: int, row: RowValues) -> IaeLocalSuperficieRecord:
    """Read one surface class of a local from the facts of its row."""
    data: dict[str, object] = {
        "clave": clave,
        "local": _row_key(row.get("local"), leaf="local"),
        "clase": row.get("clase"),
    }
    data.update({leaf: _whole_number(row[leaf], leaf=leaf) for leaf in _SURFACE_LEAVES if leaf in row})
    return _validated(IaeLocalSuperficieRecord, data)


def iae_superficie_row_values(record: IaeLocalSuperficieRecord) -> dict[str, str]:
    """Project a surface class to the facts of its row; an unstated figure has no entry."""
    return {"local": str(record.local), "clase": record.clase.value, **_stated(record, _SURFACE_LEAVES)}


def iae_elemento_from_row(clave: int, row: RowValues) -> IaeElementoTributarioRecord:
    """Read one Apartado VI A line from the facts of its row."""
    numero = row.get("numero")
    parsed = None if numero is None else try_parse_canonical_decimal(numero)
    if numero is not None and parsed is None:
        raise _refuse("write a number of units with at most two decimals", leaf="numero")
    data: dict[str, object] = {
        "clave": clave,
        "actividad": _row_key(row.get("actividad"), leaf="actividad"),
        "linea": _row_key(row.get("linea"), leaf="linea"),
        "code": row.get("code"),
        "description": row.get("description"),
        "numero": parsed,
    }
    return _validated(IaeElementoTributarioRecord, data)


def _units_text(value: Decimal) -> str:
    return format(value, "f")


def iae_elemento_row_values(record: IaeElementoTributarioRecord) -> dict[str, str]:
    """Project an Apartado VI A line to the facts of its row."""
    values = {
        "actividad": str(record.actividad),
        "linea": str(record.linea),
        "code": record.code,
        "numero": _units_text(record.numero),
    }
    if record.description is not None:
        values["description"] = record.description
    return values


def iae_locales_from_facts(path_values: Mapping[str, object]) -> tuple[IaeLocalRecord, ...]:
    """Read every stored local, ascending by row key; a cleared row is absent."""
    return tuple(
        iae_local_from_row(clave, row) for clave, row in sorted(rows_from_facts(IAE_LOCAL_SECTION, path_values).items())
    )


def iae_superficies_from_facts(path_values: Mapping[str, object]) -> tuple[IaeLocalSuperficieRecord, ...]:
    """Read every stored surface class, ascending by row key; a local states each class once."""
    records = tuple(
        iae_superficie_from_row(clave, row)
        for clave, row in sorted(rows_from_facts(IAE_LOCAL_SUPERFICIE_SECTION, path_values).items())
    )
    pairs = [(record.local, record.clase) for record in records]
    if len(set(pairs)) != len(pairs):
        raise _refuse("a local states each surface class once", leaf="clase")
    return records


def iae_elementos_from_facts(path_values: Mapping[str, object]) -> tuple[IaeElementoTributarioRecord, ...]:
    """Read every stored Apartado VI A line; one activity states each line once."""
    records = tuple(
        iae_elemento_from_row(clave, row)
        for clave, row in sorted(rows_from_facts(IAE_ELEMENTO_TRIBUTARIO_SECTION, path_values).items())
    )
    lines = [(record.actividad, record.linea) for record in records]
    if len(set(lines)) != len(lines):
        raise _refuse("an activity states each Apartado VI A line once", leaf="linea")
    return records


__all__ = [
    "IAE_ELEMENTO_TRIBUTARIO_SECTION",
    "IAE_LOCAL_SECTION",
    "IAE_LOCAL_SUPERFICIE_SECTION",
    "iae_elemento_from_row",
    "iae_elemento_row_values",
    "iae_elementos_from_facts",
    "iae_local_from_row",
    "iae_local_row_values",
    "iae_locales_from_facts",
    "iae_superficie_from_row",
    "iae_superficie_row_values",
    "iae_superficies_from_facts",
]
