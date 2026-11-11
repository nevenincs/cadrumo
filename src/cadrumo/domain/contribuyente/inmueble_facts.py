"""The profile fact grammar of the property and lease records.

Both records are repeatable profile sections: a row is a set of facts at
``renta_inmueble.{n}.{leaf}`` or ``renta_arrendamiento.{n}.{leaf}``, where ``{n}``
is the position of the row. The profile never reuses a position, so ``{n}`` is
the stable row key a lease and a ledger row name.

Four leaves carry a short list in one string, because a profile fact is flat
text. The grammar is one for every door and one canonical stored form::

    valores_catastrales   ANO:TOTAL:CONSTRUCCION[;...]      ascending by year
    mejoras               FECHA:IMPORTE[;...]               ascending by date
    usos                  TIPO:DESDE:HASTA[;...]            HASTA empty means it continues
    inquilinos            NIF:FRANJA:EXTRANJERO[;...]       EXTRANJERO is ``si`` or ``no``

Every malformed entry refuses and names the leaf; none is dropped, because a
dropped cadastral value or use changes the amortisation without any trace.
Amounts carry at most two decimals and are stored with exactly two.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, ValidationError

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.parsing.dates import parse_iso8601_date
from .arrendamiento_record import ArrendamientoRecord, Inquilino
from .inmueble_record import (
    AnejoInmueble,
    InmuebleRecord,
    InmuebleTitularidad,
    MejoraInmueble,
    UsoInmueble,
    ValorCatastral,
)

INMUEBLE_SECTION: Final = "renta_inmueble"
ARRENDAMIENTO_SECTION: Final = "renta_arrendamiento"

ENTRY_SEPARATOR: Final = ";"
_PART_SEPARATOR: Final = ":"
_CENTS: Final = Decimal("0.01")
_YEAR: Final = re.compile(r"^\d{4}$")
_ROW_PATH: Final = re.compile(r"^(?P<section>[a-z_]+)\.(?P<row>\d+)\.(?P<leaf>[a-z0-9_]+)$")

_TITULARIDAD_LEAVES: Final = (
    "titularidad_regimen",
    "titular",
    "titular_hijo_ordinal",
    "porcentaje_propiedad",
    "porcentaje_usufructo",
)
_ANEJO_LEAVES: Final = (
    "anejo_referencia_catastral",
    "anejo_adquisicion_titulo",
    "anejo_fecha_adquisicion",
    "anejo_importe_adquisicion",
    "anejo_gastos_tributos_adquisicion",
    "anejo_valor_suelo",
    "anejo_valores_catastrales",
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


def _validated[ModelT: BaseModel](model: type[ModelT], data: Mapping[str, object]) -> ModelT:
    """Validate one record, turning a model refusal into the typed refusal that names its leaf."""
    try:
        return model.model_validate(data, strict=False)
    except ValidationError as error:
        raise _refuse("the stated facts do not cohere", leaf=_error_leaf(error)) from error


def _text(raw: object) -> str:
    if isinstance(raw, bool):
        return "true" if raw else "false"
    if isinstance(raw, date):
        return raw.isoformat()
    return str(raw).strip()


def _date(raw: str, *, leaf: str) -> date:
    try:
        parsed = parse_iso8601_date(raw)
    except ValueError:
        parsed = None
    if parsed is None:
        raise _refuse("write a calendar date as YYYY-MM-DD", leaf=leaf)
    return parsed


def _money(raw: str, *, leaf: str) -> Decimal:
    value = try_parse_canonical_decimal(raw)
    if value is None or value != value.quantize(_CENTS):
        raise _refuse("write an amount with at most two decimals", leaf=leaf)
    return value


def money_text(value: Decimal) -> str:
    """Render an amount in its one stored form: exactly two decimals."""
    return format(value.quantize(_CENTS), "f")


def _boolean(raw: str, *, leaf: str) -> bool:
    if raw not in ("true", "false"):
        raise _refuse("write true or false", leaf=leaf)
    return raw == "true"


def _entries(raw: str, *, leaf: str, parts: int) -> list[list[str]]:
    entries: list[list[str]] = []
    for chunk in raw.split(ENTRY_SEPARATOR):
        pieces = [piece.strip() for piece in chunk.split(_PART_SEPARATOR)]
        if len(pieces) != parts:
            raise _refuse(f"each entry has {parts} parts separated by ':'", leaf=leaf)
        entries.append(pieces)
    return entries


def parse_valores_catastrales(raw: str, *, leaf: str) -> tuple[ValorCatastral, ...]:
    """Read ``ANO:TOTAL:CONSTRUCCION`` entries into values ascending by IBI year."""
    values: list[ValorCatastral] = []
    for year, total, construccion in _entries(raw, leaf=leaf, parts=3):
        if not _YEAR.fullmatch(year):
            raise _refuse("an IBI year has four digits", leaf=leaf)
        values.append(
            _validated(
                ValorCatastral,
                {"year": int(year), "total": _money(total, leaf=leaf), "construccion": _money(construccion, leaf=leaf)},
            )
        )
    return tuple(sorted(values, key=lambda valor: valor.year))


def serialise_valores_catastrales(values: tuple[ValorCatastral, ...]) -> str:
    """Render cadastral values in the stored form, ascending by IBI year."""
    return ENTRY_SEPARATOR.join(
        f"{valor.year}:{money_text(valor.total)}:{money_text(valor.construccion)}"
        for valor in sorted(values, key=lambda item: item.year)
    )


def parse_mejoras(raw: str, *, leaf: str) -> tuple[MejoraInmueble, ...]:
    """Read ``FECHA:IMPORTE`` entries into improvements ascending by date."""
    mejoras = [
        _validated(MejoraInmueble, {"fecha": _date(fecha, leaf=leaf), "importe": _money(importe, leaf=leaf)})
        for fecha, importe in _entries(raw, leaf=leaf, parts=2)
    ]
    return tuple(sorted(mejoras, key=lambda mejora: (mejora.fecha, mejora.importe)))


def serialise_mejoras(mejoras: tuple[MejoraInmueble, ...]) -> str:
    """Render improvements in the stored form, ascending by date."""
    return ENTRY_SEPARATOR.join(
        f"{mejora.fecha.isoformat()}:{money_text(mejora.importe)}"
        for mejora in sorted(mejoras, key=lambda item: (item.fecha, item.importe))
    )


def parse_usos(raw: str, *, leaf: str) -> tuple[UsoInmueble, ...]:
    """Read ``TIPO:DESDE:HASTA`` entries into uses ascending by start date."""
    usos = [
        _validated(
            UsoInmueble,
            {
                "tipo": tipo,
                "desde": _date(desde, leaf=leaf),
                "hasta": _date(hasta, leaf=leaf) if hasta else None,
            },
        )
        for tipo, desde, hasta in _entries(raw, leaf=leaf, parts=3)
    ]
    return tuple(sorted(usos, key=lambda uso: (uso.desde, uso.tipo.value)))


def serialise_usos(usos: tuple[UsoInmueble, ...]) -> str:
    """Render uses in the stored form, ascending by start date."""
    return ENTRY_SEPARATOR.join(
        f"{uso.tipo.value}:{uso.desde.isoformat()}:{uso.hasta.isoformat() if uso.hasta else ''}"
        for uso in sorted(usos, key=lambda item: (item.desde, item.tipo.value))
    )


def parse_inquilinos(raw: str, *, leaf: str) -> tuple[Inquilino, ...]:
    """Read ``NIF:FRANJA:EXTRANJERO`` entries into tenants in the order stated."""
    inquilinos: list[Inquilino] = []
    for nif, franja, extranjero in _entries(raw, leaf=leaf, parts=3):
        if extranjero not in ("si", "no"):
            raise _refuse("the foreign-identifier flag is si or no", leaf=leaf)
        inquilinos.append(_validated(Inquilino, {"nif": nif, "franja_edad": franja, "extranjero": extranjero == "si"}))
    return tuple(inquilinos)


def serialise_inquilinos(inquilinos: tuple[Inquilino, ...]) -> str:
    """Render tenants in the stored form, in the order stated."""
    return ENTRY_SEPARATOR.join(
        f"{inquilino.nif}:{inquilino.franja_edad.value}:{'si' if inquilino.extranjero else 'no'}"
        for inquilino in inquilinos
    )


def _optional[T](row: RowValues, leaf: str, read: Callable[[str], T]) -> T | None:
    return read(row[leaf]) if leaf in row else None


def _titularidad(row: RowValues) -> InmuebleTitularidad | None:
    if not any(leaf in row for leaf in _TITULARIDAD_LEAVES):
        return None
    for leaf in ("titularidad_regimen", "titular"):
        if leaf not in row:
            raise _refuse("a titularidad states its regime and its titular together", leaf=leaf)
    return _validated(
        InmuebleTitularidad,
        {
            "regimen": row["titularidad_regimen"],
            "titular": row["titular"],
            "hijo_ordinal": _optional(row, "titular_hijo_ordinal", int),
            "porcentaje_propiedad": _optional(row, "porcentaje_propiedad", _percentage("porcentaje_propiedad")),
            "porcentaje_usufructo": _optional(row, "porcentaje_usufructo", _percentage("porcentaje_usufructo")),
        },
    )


def _percentage(leaf: str) -> Callable[[str], Decimal]:
    def read(raw: str) -> Decimal:
        value = try_parse_canonical_decimal(raw)
        if value is None:
            raise _refuse("write a percentage as a decimal number", leaf=leaf)
        return value

    return read


def _anejo(row: RowValues) -> AnejoInmueble | None:
    if not any(leaf in row for leaf in _ANEJO_LEAVES):
        return None
    if "anejo_referencia_catastral" not in row:
        raise _refuse("an accessory property states its cadastral reference", leaf="anejo_referencia_catastral")
    return _validated(
        AnejoInmueble,
        {
            "referencia_catastral": row["anejo_referencia_catastral"],
            "adquisicion_titulo": row.get("anejo_adquisicion_titulo"),
            "fecha_adquisicion": _optional(
                row, "anejo_fecha_adquisicion", lambda raw: _date(raw, leaf="anejo_fecha_adquisicion")
            ),
            "importe_adquisicion": _optional(
                row, "anejo_importe_adquisicion", lambda raw: _money(raw, leaf="anejo_importe_adquisicion")
            ),
            "gastos_tributos_adquisicion": _optional(
                row,
                "anejo_gastos_tributos_adquisicion",
                lambda raw: _money(raw, leaf="anejo_gastos_tributos_adquisicion"),
            ),
            "valor_suelo": _optional(row, "anejo_valor_suelo", lambda raw: _money(raw, leaf="anejo_valor_suelo")),
            "valores_catastrales": _optional(
                row,
                "anejo_valores_catastrales",
                lambda raw: parse_valores_catastrales(raw, leaf="anejo_valores_catastrales"),
            )
            or (),
        },
    )


def inmueble_from_row(clave: int, row: RowValues) -> InmuebleRecord:
    """Build one property from the facts of its row, refusing what does not cohere."""
    if "situacion" not in row:
        raise _refuse("a property states its situacion", leaf="situacion")

    def date_of(leaf: str) -> date | None:
        return _optional(row, leaf, lambda raw: _date(raw, leaf=leaf))

    def money_of(leaf: str) -> Decimal | None:
        return _optional(row, leaf, lambda raw: _money(raw, leaf=leaf))

    return _validated(
        InmuebleRecord,
        {
            "clave": clave,
            "situacion": row["situacion"],
            "referencia_catastral": row.get("referencia_catastral"),
            "naturaleza": row.get("naturaleza"),
            "direccion": row.get("direccion"),
            "titularidad": _titularidad(row),
            "adquisicion_titulo": row.get("adquisicion_titulo"),
            "fecha_adquisicion": date_of("fecha_adquisicion"),
            "fecha_transmision": date_of("fecha_transmision"),
            "importe_adquisicion": money_of("importe_adquisicion"),
            "gastos_tributos_adquisicion": money_of("gastos_tributos_adquisicion"),
            "valor_suelo": money_of("valor_suelo"),
            "mejoras": _optional(row, "mejoras", lambda raw: parse_mejoras(raw, leaf="mejoras")) or (),
            "valores_catastrales": _optional(
                row, "valores_catastrales", lambda raw: parse_valores_catastrales(raw, leaf="valores_catastrales")
            )
            or (),
            "usos": _optional(row, "usos", lambda raw: parse_usos(raw, leaf="usos")) or (),
            "anejo": _anejo(row),
            "amortizacion_acumulada": money_of("amortizacion_acumulada"),
            "amortizacion_acumulada_desde": date_of("amortizacion_acumulada_desde"),
        },
    )


def arrendamiento_from_row(clave: int, row: RowValues) -> ArrendamientoRecord:
    """Build one lease from the facts of its row, refusing what does not cohere."""
    for leaf in ("inmueble", "fecha_contrato", "fecha_inicio"):
        if leaf not in row:
            raise _refuse("a lease states its property, its contract date and its start", leaf=leaf)

    def date_of(leaf: str) -> date | None:
        return _optional(row, leaf, lambda raw: _date(raw, leaf=leaf))

    def money_of(leaf: str) -> Decimal | None:
        return _optional(row, leaf, lambda raw: _money(raw, leaf=leaf))

    def flag_of(leaf: str) -> bool | None:
        return _optional(row, leaf, lambda raw: _boolean(raw, leaf=leaf))

    return _validated(
        ArrendamientoRecord,
        {
            "clave": clave,
            "inmueble": int(row["inmueble"]),
            "fecha_contrato": date_of("fecha_contrato"),
            "fecha_inicio": date_of("fecha_inicio"),
            "fecha_fin": date_of("fecha_fin"),
            "uso_vivienda": flag_of("uso_vivienda"),
            "inquilinos": _optional(row, "inquilinos", lambda raw: parse_inquilinos(raw, leaf="inquilinos")) or (),
            "zona_tensionada": flag_of("zona_tensionada"),
            "primer_arrendamiento_vivienda": flag_of("primer_arrendamiento_vivienda"),
            "arrendatario_entidad_tipo": row.get("arrendatario_entidad_tipo"),
            "arrendatario_entidad_finalidad": row.get("arrendatario_entidad_finalidad"),
            "rehabilitacion_fecha": date_of("rehabilitacion_fecha"),
            "renta_inicial": money_of("renta_inicial"),
            "renta_ultima_contrato_anterior": money_of("renta_ultima_contrato_anterior"),
            "arrendatario_pariente_art24": flag_of("arrendatario_pariente_art24"),
        },
    )


def inmueble_row_values(record: InmuebleRecord) -> dict[str, str]:
    """Project a property to the facts of its row; a fact never stated has no entry."""
    values: dict[str, str] = {"situacion": record.situacion.value}
    optional: dict[str, object | None] = {
        "referencia_catastral": record.referencia_catastral,
        "naturaleza": record.naturaleza,
        "direccion": record.direccion,
        "adquisicion_titulo": record.adquisicion_titulo,
        "fecha_adquisicion": record.fecha_adquisicion,
        "fecha_transmision": record.fecha_transmision,
        "importe_adquisicion": _amount(record.importe_adquisicion),
        "gastos_tributos_adquisicion": _amount(record.gastos_tributos_adquisicion),
        "valor_suelo": _amount(record.valor_suelo),
        "mejoras": serialise_mejoras(record.mejoras) or None,
        "valores_catastrales": serialise_valores_catastrales(record.valores_catastrales) or None,
        "usos": serialise_usos(record.usos) or None,
        "amortizacion_acumulada": _amount(record.amortizacion_acumulada),
        "amortizacion_acumulada_desde": record.amortizacion_acumulada_desde,
    }
    if record.titularidad is not None:
        titularidad = record.titularidad
        optional |= {
            "titularidad_regimen": titularidad.regimen,
            "titular": titularidad.titular,
            "titular_hijo_ordinal": titularidad.hijo_ordinal,
            "porcentaje_propiedad": titularidad.porcentaje_propiedad,
            "porcentaje_usufructo": titularidad.porcentaje_usufructo,
        }
    if record.anejo is not None:
        anejo = record.anejo
        optional |= {
            "anejo_referencia_catastral": anejo.referencia_catastral,
            "anejo_adquisicion_titulo": anejo.adquisicion_titulo,
            "anejo_fecha_adquisicion": anejo.fecha_adquisicion,
            "anejo_importe_adquisicion": _amount(anejo.importe_adquisicion),
            "anejo_gastos_tributos_adquisicion": _amount(anejo.gastos_tributos_adquisicion),
            "anejo_valor_suelo": _amount(anejo.valor_suelo),
            "anejo_valores_catastrales": serialise_valores_catastrales(anejo.valores_catastrales) or None,
        }
    values.update({leaf: _enum_text(value) for leaf, value in optional.items() if value is not None})
    return values


def arrendamiento_row_values(record: ArrendamientoRecord) -> dict[str, str]:
    """Project a lease to the facts of its row; a fact never stated has no entry."""
    optional: dict[str, object | None] = {
        "fecha_fin": record.fecha_fin,
        "uso_vivienda": record.uso_vivienda,
        "inquilinos": serialise_inquilinos(record.inquilinos) or None,
        "zona_tensionada": record.zona_tensionada,
        "primer_arrendamiento_vivienda": record.primer_arrendamiento_vivienda,
        "arrendatario_entidad_tipo": record.arrendatario_entidad_tipo,
        "arrendatario_entidad_finalidad": record.arrendatario_entidad_finalidad,
        "rehabilitacion_fecha": record.rehabilitacion_fecha,
        "renta_inicial": _amount(record.renta_inicial),
        "renta_ultima_contrato_anterior": _amount(record.renta_ultima_contrato_anterior),
        "arrendatario_pariente_art24": record.arrendatario_pariente_art24,
    }
    values = {
        "inmueble": str(record.inmueble),
        "fecha_contrato": record.fecha_contrato.isoformat(),
        "fecha_inicio": record.fecha_inicio.isoformat(),
    }
    values.update({leaf: _enum_text(value) for leaf, value in optional.items() if value is not None})
    return values


def _amount(value: Decimal | None) -> str | None:
    return None if value is None else money_text(value)


def _enum_text(value: object) -> str:
    inner = getattr(value, "value", value)
    return _text(inner)


def rows_from_facts(section: str, path_values: Mapping[str, object]) -> dict[int, dict[str, str]]:
    """Group a section's stated facts by row position; a cleared fact states nothing."""
    rows: dict[int, dict[str, str]] = {}
    for path, raw in path_values.items():
        if not path.startswith(f"{section}."):
            continue
        match = _ROW_PATH.fullmatch(path)
        text = "" if raw is None else _text(raw)
        if match is None or match["section"] != section:
            if text:
                raise _refuse("a row fact is addressed by its row position", leaf=path.removeprefix(f"{section}."))
            continue
        if text:
            rows.setdefault(int(match["row"]), {})[match["leaf"]] = text
    return rows


def inmuebles_from_facts(path_values: Mapping[str, object]) -> tuple[InmuebleRecord, ...]:
    """Read every stored property, ascending by row key; a cleared row is absent."""
    return tuple(
        inmueble_from_row(clave, row) for clave, row in sorted(rows_from_facts(INMUEBLE_SECTION, path_values).items())
    )


def arrendamientos_from_facts(path_values: Mapping[str, object]) -> tuple[ArrendamientoRecord, ...]:
    """Read every stored lease, ascending by row key; a cleared row is absent."""
    return tuple(
        arrendamiento_from_row(clave, row)
        for clave, row in sorted(rows_from_facts(ARRENDAMIENTO_SECTION, path_values).items())
    )


def facts_for_row(section: str, clave: int, values: RowValues) -> dict[str, str]:
    """Address a row's leaves as profile fact paths."""
    return {f"{section}.{clave}.{leaf}": value for leaf, value in values.items()}


__all__ = [
    "ARRENDAMIENTO_SECTION",
    "ENTRY_SEPARATOR",
    "INMUEBLE_SECTION",
    "arrendamiento_from_row",
    "arrendamiento_row_values",
    "arrendamientos_from_facts",
    "facts_for_row",
    "inmueble_from_row",
    "inmueble_row_values",
    "inmuebles_from_facts",
    "money_text",
    "parse_inquilinos",
    "parse_mejoras",
    "parse_usos",
    "parse_valores_catastrales",
    "rows_from_facts",
    "serialise_inquilinos",
    "serialise_mejoras",
    "serialise_usos",
    "serialise_valores_catastrales",
]
