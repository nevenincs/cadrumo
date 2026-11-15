"""Modelo 840 producer values for declaration export.

Each value is read from :class:`Modelo840ProfileFacts`, the stored facts of the one
activity the declaration covers. DR840 (Orden HAC/2572/2003) fixes what each position
holds:

* positions 11-12 "Delegación. Tabla" and 13-35 "Administración. Tabla. (3 Cod+20
  Descrip)": the Administración prints its three-digit code followed by its name;
* positions 220-249, 588-617 and 1025-1054 "Municipio": the names that pair with the
  coded municipio casillas of Apartados I, IV and V;
* position 531-532 "Apart. IV: Datos de la act. Provincial (provincia) Tabla": the
  provincia of a cuota provincial;
* página 2 Apartado VI A lines 1-4 "2Cod + 30Descrip" and "Número 7ent + 2dec";
* página 2 Apartado VI B "Máquinas recreativas Tipo A/B" and "Expositores para
  autoventa" "Número";
* página 2 Apartado VI C "Elem. Trib. Local (Cuota municipal)" Total, Rectificada and
  Computable for each Regla 14 class.

An absent fact resolves to ``None`` and the renderer decides, from the layout's own
``required`` flag, whether that blank is legal; nothing is defaulted or zeroed.
"""

from __future__ import annotations

from decimal import Decimal

from ...core.filing_producer_key import FilingProducerKey
from ...domain.contribuyente.iae_local_record import SuperficieRegla14Clase
from .producer_snapshot import FilingModelProfileFacts
from .producer_snapshot_m840 import Modelo840ElementoLinea, Modelo840ProfileFacts, Modelo840SuperficieClase

_SCALAR_KEYS: tuple[FilingProducerKey, ...] = (
    FilingProducerKey.M840_DELEGACION_CODIGO,
    FilingProducerKey.M840_ADMINISTRACION_CODIGO,
    FilingProducerKey.M840_SUJETO_PASIVO_MUNICIPIO,
    FilingProducerKey.M840_ACTIVIDAD_PROVINCIA_CODIGO,
    FilingProducerKey.M840_ACTIVIDAD_MUNICIPIO,
    FilingProducerKey.M840_LOCAL_INDIRECTO_MUNICIPIO,
    FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_MAQUINAS_TIPO_A_NUMERO,
    FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_MAQUINAS_TIPO_B_NUMERO,
    FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_EXPOSITORES_AUTOVENTA_NUMERO,
)
#: Apartado VI A line -> (code and description key, number of units key).
_ELEMENTO_KEYS: dict[int, tuple[FilingProducerKey, FilingProducerKey]] = {
    1: (
        FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A1_CODIGO,
        FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A1_NUMERO,
    ),
    2: (
        FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A2_CODIGO,
        FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A2_NUMERO,
    ),
    3: (
        FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A3_CODIGO,
        FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A3_NUMERO,
    ),
    4: (
        FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A4_CODIGO,
        FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A4_NUMERO,
    ),
}
_SURFACE_FIGURES = ("total", "rectificada", "computable")


def _superficie_keys(clase: SuperficieRegla14Clase) -> tuple[FilingProducerKey, ...]:
    """The Total, Rectificada and Computable keys of one class, named by its Regla 14 number."""
    stem = f"m840.elementos_tributarios.local.c{clase.value.replace('.', '_')}"
    return tuple(FilingProducerKey(f"{stem}.{figure}") for figure in _SURFACE_FIGURES)


#: Derived from the class vocabulary so a class and the keys that print it cannot drift apart.
_SUPERFICIE_KEYS: dict[SuperficieRegla14Clase, tuple[FilingProducerKey, ...]] = {
    clase: _superficie_keys(clase) for clase in SuperficieRegla14Clase
}

M840_PRODUCER_KEYS: frozenset[FilingProducerKey] = frozenset(
    {
        *_SCALAR_KEYS,
        *(key for pair in _ELEMENTO_KEYS.values() for key in pair),
        *(key for keys in _SUPERFICIE_KEYS.values() for key in keys),
    }
)


def _code_and_description(code: str | None, description: str | None) -> str | None:
    """A "Cod + Descrip" field: the code, then its description; no code prints nothing."""
    if code is None:
        return None
    return f"{code}{description or ''}"


def _whole_number(value: int | None) -> Decimal | None:
    """A DR840 "Num" quantity (a count of units or square metres), printed right-aligned."""
    return None if value is None else Decimal(value)


def _scalar_values(profile: Modelo840ProfileFacts) -> dict[FilingProducerKey, object]:
    return {
        FilingProducerKey.M840_DELEGACION_CODIGO: profile.delegacion_codigo,
        FilingProducerKey.M840_ADMINISTRACION_CODIGO: _code_and_description(
            profile.administracion_codigo, profile.administracion_nombre
        ),
        FilingProducerKey.M840_SUJETO_PASIVO_MUNICIPIO: profile.sujeto_pasivo_municipio,
        FilingProducerKey.M840_ACTIVIDAD_PROVINCIA_CODIGO: profile.actividad_provincia_codigo,
        FilingProducerKey.M840_ACTIVIDAD_MUNICIPIO: profile.actividad_municipio,
        FilingProducerKey.M840_LOCAL_INDIRECTO_MUNICIPIO: profile.local_indirecto_municipio,
        FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_MAQUINAS_TIPO_A_NUMERO: _whole_number(profile.maquinas_tipo_a),
        FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_MAQUINAS_TIPO_B_NUMERO: _whole_number(profile.maquinas_tipo_b),
        FilingProducerKey.M840_ELEMENTOS_TRIBUTARIOS_EXPOSITORES_AUTOVENTA_NUMERO: _whole_number(
            profile.expositores_autoventa
        ),
    }


def _elemento_values(elementos: tuple[Modelo840ElementoLinea, ...]) -> dict[FilingProducerKey, object]:
    values: dict[FilingProducerKey, object] = {}
    for elemento in elementos:
        codigo_key, numero_key = _ELEMENTO_KEYS[elemento.linea]
        values[codigo_key] = _code_and_description(elemento.codigo, elemento.descripcion)
        values[numero_key] = elemento.numero
    return values


def _superficie_values(superficies: tuple[Modelo840SuperficieClase, ...]) -> dict[FilingProducerKey, object]:
    values: dict[FilingProducerKey, object] = {}
    for superficie in superficies:
        total_key, rectificada_key, computable_key = _SUPERFICIE_KEYS[superficie.clase]
        values[total_key] = _whole_number(superficie.total)
        values[rectificada_key] = _whole_number(superficie.rectificada)
        values[computable_key] = _whole_number(superficie.computable)
    return values


def m840_producer_values(model_profile: FilingModelProfileFacts) -> dict[FilingProducerKey, object]:
    """Resolve every producer identity the Modelo 840 pages cite from the stored facts.

    A profile of the wrong type yields every key as ``None`` rather than raising: this
    resolver runs for every modelo, and only Modelo 840's own profile reader may decide
    that an 840 filing's facts are inadmissible.
    """
    values: dict[FilingProducerKey, object] = {key: None for key in M840_PRODUCER_KEYS}
    if not isinstance(model_profile, Modelo840ProfileFacts):
        return values
    values.update(_scalar_values(model_profile))
    values.update(_elemento_values(model_profile.elementos))
    values.update(_superficie_values(model_profile.superficies))
    return values


__all__ = ["M840_PRODUCER_KEYS", "m840_producer_values"]
