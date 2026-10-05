"""Lossless official detail-row wire mirrors with canonical domain conversion."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...core.country_code import CountryCodeAlpha2
from ...domain.modelos.row_models import (
    M184Clave,
    M184ClaveDeclarado,
    M184NaturalezaInmueble,
    M184SituacionInmueble,
    M184Subclave,
    Modelo184MemberRow,
    Modelo210AgrupacionRentaRow,
    Modelo232VinculadaRow,
    Modelo349ClaveOperacionValue,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
)
from ...domain.transactions.m210_income_classification import resolve_m210_payer_mode

EDIT_WIRE_DECIMAL_PATTERN = re.compile(r"^-?\d+(\.\d+)?$")


EDIT_WIRE_MODEL_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


type _WireAmount = Annotated[str, Field(min_length=1, max_length=40)]
"""One decimal amount as the exact characters submitted.

``Decimal`` validates from a number or a string but always serializes to a
string, so a ``Decimal`` field fails the operations payload-graph gate's
validation/serialization schema-identity check. Carrying the characters
verbatim also keeps translation honest: the real row type parses them with the
same code the CLI path uses, so an amount the CLI would refuse is refused here
too rather than being pre-normalised into acceptability.
"""


type _WireOptionalAmount = _WireAmount | None


type _WireCode = Annotated[str, Field(max_length=40)]
"""One registry code exactly as supplied, left unhydrated on purpose.

The M232 row type hydrates its own codes through ``BeforeValidator`` metadata.
Mirroring a hydrated enum here would put a second hydration on the wire path,
free to drift until the wire accepts a code the CLI refuses. Carrying the raw
characters instead means translation hands them to the row type's own
constructor and the existing hydration runs unchanged - not a delegating copy,
no copy at all.
"""


def _optional_decimal(value: str | None) -> Decimal | None:
    """Parse one optional wire amount, leaving an absent value absent."""
    return None if value is None else Decimal(value)


class _WireDetailRowMirror(BaseModel):
    """Shared inverse for the per-modelo detail-row wire mirrors.

    Each of the six mirrors hand-writes its own ``to_row``, because the
    domain constructors differ. The direction BACK does not differ: every
    field crosses unchanged except a ``Decimal``, which becomes the exact
    characters it already serializes to. Written once here rather than six
    times, so the mirrors cannot drift into disagreeing about what a total
    translation means.

    Total by construction rather than by inspection. The row is dumped whole,
    so a field added to the domain row is carried automatically; and because
    every mirror forbids extras, a field the wire type does NOT declare raises
    here instead of being silently dropped on its way to the payload.
    """

    model_config = EDIT_WIRE_MODEL_CONFIG


class Modelo184MemberRowWireV1(_WireDetailRowMirror):
    """Wire mirror of Modelo184MemberRow with decimal amounts as characters."""

    model_config = EDIT_WIRE_MODEL_CONFIG

    row_type: Literal["miembro"] = "miembro"
    nif: Annotated[str, Field(min_length=1, max_length=20)]
    nombre: Annotated[str, Field(max_length=200)] = ""
    pais: CountryCodeAlpha2 | None = None
    porcentaje: _WireAmount
    importe: _WireAmount
    clave: M184Clave
    subclave: M184Subclave | None = None
    codigo_provincia: Annotated[str, Field(max_length=2)] | None = None
    miembro_a_31_diciembre: bool | None = None
    dias_miembro: Annotated[int, Field(ge=0, le=366)] | None = None
    domicilio_fiscal: Annotated[str, Field(max_length=40)] | None = None
    naturaleza_inmueble: M184NaturalezaInmueble | None = None
    situacion_inmueble: M184SituacionInmueble | None = None
    referencia_catastral: Annotated[str, Field(max_length=20)] | None = None
    clave_declarado: M184ClaveDeclarado | None = None
    porcentaje_titularidad_inmueble: _WireOptionalAmount = None
    dias_arrendamiento: Annotated[int, Field(ge=0, le=366)] | None = None
    reduccion: _WireOptionalAmount = None
    rendimiento_neto_previo_eo: _WireOptionalAmount = None
    rendimiento_neto_minorado_agricola_eo: _WireOptionalAmount = None

    def to_row(self) -> Modelo184MemberRow:
        """Translate back to the real, fully re-validated domain row."""
        return Modelo184MemberRow(
            nif=self.nif,
            nombre=self.nombre,
            pais=self.pais,
            porcentaje=Decimal(self.porcentaje),
            importe=Decimal(self.importe),
            clave=self.clave,
            subclave=self.subclave,
            codigo_provincia=self.codigo_provincia,
            miembro_a_31_diciembre=self.miembro_a_31_diciembre,
            dias_miembro=self.dias_miembro,
            domicilio_fiscal=self.domicilio_fiscal,
            naturaleza_inmueble=self.naturaleza_inmueble,
            situacion_inmueble=self.situacion_inmueble,
            referencia_catastral=self.referencia_catastral,
            clave_declarado=self.clave_declarado,
            porcentaje_titularidad_inmueble=_optional_decimal(self.porcentaje_titularidad_inmueble),
            dias_arrendamiento=self.dias_arrendamiento,
            reduccion=_optional_decimal(self.reduccion),
            rendimiento_neto_previo_eo=_optional_decimal(self.rendimiento_neto_previo_eo),
            rendimiento_neto_minorado_agricola_eo=_optional_decimal(self.rendimiento_neto_minorado_agricola_eo),
        )


class Modelo232VinculadaRowWireV1(_WireDetailRowMirror):
    """Wire mirror of Modelo232VinculadaRow carrying its codes unhydrated."""

    model_config = EDIT_WIRE_MODEL_CONFIG

    row_type: Literal["vinculada"] = "vinculada"
    nif: Annotated[str, Field(min_length=1, max_length=20)]
    nombre: Annotated[str, Field(max_length=200)] = ""
    pais: CountryCodeAlpha2
    tipo_vinculacion: _WireCode = ""
    tipo_operacion: _WireCode = ""
    metodo: _WireCode = ""
    importe: _WireAmount

    def to_row(self) -> Modelo232VinculadaRow:
        """Translate back through the row type's own code hydration."""
        return Modelo232VinculadaRow(
            nif=self.nif,
            nombre=self.nombre,
            pais=self.pais,
            tipo_vinculacion=self.tipo_vinculacion,
            tipo_operacion=self.tipo_operacion,
            metodo=self.metodo,
            importe=Decimal(self.importe),
        )


class Modelo349OperadorRowWireV1(_WireDetailRowMirror):
    """Wire mirror of Modelo349OperadorRow with its importe as characters."""

    model_config = EDIT_WIRE_MODEL_CONFIG

    row_type: Literal["operador"] = "operador"
    codigo_pais: CountryCodeAlpha2
    nif_comunitario: Annotated[str, Field(min_length=1, max_length=20)]
    razon_social: Annotated[str, Field(min_length=1, max_length=200)]
    clave_operacion: Modelo349ClaveOperacionValue
    importe: _WireAmount

    def to_row(self) -> Modelo349OperadorRow:
        """Translate back to the real, fully re-validated domain row."""
        return Modelo349OperadorRow(
            codigo_pais=self.codigo_pais,
            nif_comunitario=self.nif_comunitario,
            razon_social=self.razon_social,
            clave_operacion=self.clave_operacion,
            importe=Decimal(self.importe),
        )


class Modelo349RectificacionRowWireV1(_WireDetailRowMirror):
    """Wire mirror of Modelo349RectificacionRow with its bases as characters."""

    model_config = EDIT_WIRE_MODEL_CONFIG

    row_type: Literal["rectificacion"] = "rectificacion"
    codigo_pais: CountryCodeAlpha2
    nif_comunitario: Annotated[str, Field(min_length=1, max_length=20)]
    razon_social: Annotated[str, Field(min_length=1, max_length=200)]
    clave_operacion: Modelo349ClaveOperacionValue
    ejercicio: Annotated[str, Field(min_length=4, max_length=4)]
    periodo: Annotated[str, Field(min_length=1, max_length=2)]
    base_rectificada: _WireAmount
    base_anterior: _WireAmount

    def to_row(self) -> Modelo349RectificacionRow:
        """Translate back through the row type's own periodo normalisation."""
        return Modelo349RectificacionRow(
            codigo_pais=self.codigo_pais,
            nif_comunitario=self.nif_comunitario,
            razon_social=self.razon_social,
            clave_operacion=self.clave_operacion,
            ejercicio=self.ejercicio,
            periodo=self.periodo,
            base_rectificada=Decimal(self.base_rectificada),
            base_anterior=Decimal(self.base_anterior),
        )


class Modelo210AgrupacionRentaRowWireV1(_WireDetailRowMirror):
    """Wire mirror of Modelo210AgrupacionRentaRow with its rates as characters."""

    model_config = EDIT_WIRE_MODEL_CONFIG

    row_type: Literal["agrupacion_renta"] = "agrupacion_renta"
    source_id: Annotated[str, Field(min_length=1, max_length=200)]
    tipo_renta_code: Annotated[str, Field(min_length=2, max_length=2)]
    importe: _WireAmount
    tipo_gravamen: _WireAmount
    pagador_mode: str
    pagador_id: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    deriva_de_bien_derecho: bool
    bien_derecho_id: Annotated[str, Field(min_length=1, max_length=200)] | None = None

    def to_row(self) -> Modelo210AgrupacionRentaRow:
        """Translate back to the real, fully re-validated domain row."""
        return Modelo210AgrupacionRentaRow(
            source_id=self.source_id,
            tipo_renta_code=self.tipo_renta_code,
            importe=Decimal(self.importe),
            tipo_gravamen=Decimal(self.tipo_gravamen),
            pagador_mode=resolve_m210_payer_mode(self.pagador_mode),
            pagador_id=self.pagador_id,
            deriva_de_bien_derecho=self.deriva_de_bien_derecho,
            bien_derecho_id=self.bien_derecho_id,
        )


type ModeloDetailRowWireV1 = Annotated[
    Modelo184MemberRowWireV1
    | Modelo232VinculadaRowWireV1
    | Modelo349OperadorRowWireV1
    | Modelo349RectificacionRowWireV1
    | Modelo210AgrupacionRentaRowWireV1,
    Field(discriminator="row_type"),
]
"""The wire mirror of the per-modelo detail-row union, discriminated as it is."""


type DetailRowKindToken = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")]
"""Lower-case registry token naming a detail-row family."""
