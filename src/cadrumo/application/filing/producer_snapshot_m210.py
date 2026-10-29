"""Typed filing facts for m210."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class Modelo210ContribuyenteFactSet(BaseModel):
    """Modelo 210 contribuyente facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    birth_city: str | None = None
    birth_country_code: str | None = None
    birth_date: str | None = None
    foreign_address_city: str | None = None
    foreign_address_complement: str | None = None
    foreign_address_country_code: str | None = None
    foreign_address_email: str | None = None
    foreign_address_fax: str | None = None
    foreign_address_mobile_phone: str | None = None
    foreign_address_phone: str | None = None
    foreign_address_postal_code: str | None = None
    foreign_address_region: str | None = None
    foreign_address_street: str | None = None
    foreign_tax_id: str | None = None
    full_name: str | None = None
    person_type: str | None = None
    tax_id: str | None = None
    tax_residence_country_code: str | None = None


class Modelo210DeclaracionFactSet(BaseModel):
    """Modelo 210 declaracion facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    tipo: str | None = None


class Modelo210DeclaranteFactSet(BaseModel):
    """Modelo 210 declarante facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    capacity_contribuyente: str | None = None
    capacity_depositario: str | None = None
    capacity_gestor: str | None = None
    capacity_pagador: str | None = None
    capacity_representante: str | None = None
    capacity_retenedor: str | None = None
    full_name: str | None = None
    tax_id: str | None = None


class Modelo210DevengoFactSet(BaseModel):
    """Modelo 210 devengo facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    agrupacion: str | None = None
    fecha_devengo: str | None = None


class Modelo210DevolucionFactSet(BaseModel):
    """Modelo 210 devolucion facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    cuenta_resto_banco: str | None = None
    cuenta_resto_ciudad: str | None = None
    cuenta_resto_codigo_pais: str | None = None
    cuenta_resto_direccion_banco: str | None = None
    cuenta_resto_numero_cuenta: str | None = None
    cuenta_resto_swift_bic: str | None = None
    cuenta_sepa_iban: str | None = None
    cuenta_sepa_swift_bic: str | None = None
    cuenta_titular_full_name: str | None = None
    cuenta_titular_tax_id: str | None = None
    renuncia_a_favor_del_tesoro: str | None = None


class Modelo210GananciaInmobiliariaFactSet(BaseModel):
    """Modelo 210 ganancia inmobiliaria facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    conyuge_full_name: str | None = None
    conyuge_tax_id: str | None = None
    cuota_participacion_contribuyente: str | None = None
    cuota_participacion_conyuge: str | None = None
    fecha_adquisicion: str | None = None
    fecha_mejora: str | None = None
    justificante_modelo_211: str | None = None
    titularidad: str | None = None


class Modelo210IngresoFactSet(BaseModel):
    """Modelo 210 ingreso facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    cuenta_resto_banco: str | None = None
    cuenta_resto_ciudad: str | None = None
    cuenta_resto_codigo_pais: str | None = None
    cuenta_resto_direccion_banco: str | None = None
    cuenta_resto_numero_cuenta: str | None = None
    cuenta_resto_swift_bic: str | None = None
    cuenta_sepa_iban: str | None = None
    cuenta_sepa_swift_bic: str | None = None
    cuenta_titular_full_name: str | None = None
    cuenta_titular_tax_id: str | None = None
    forma_pago: str | None = None


class Modelo210InmuebleFactSet(BaseModel):
    """Modelo 210 inmueble facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    referencia_catastral: str | None = None
    situacion_bloque: str | None = None
    situacion_calificador_numero: str | None = None
    situacion_codigo_ine_municipio: str | None = None
    situacion_codigo_postal: str | None = None
    situacion_codigo_provincia: str | None = None
    situacion_datos_complementarios: str | None = None
    situacion_escalera: str | None = None
    situacion_localidad: str | None = None
    situacion_nombre_via: str | None = None
    situacion_numero_casa: str | None = None
    situacion_planta: str | None = None
    situacion_portal: str | None = None
    situacion_puerta: str | None = None
    situacion_tipo_numeracion: str | None = None
    situacion_tipo_via: str | None = None


class Modelo210PagadorFactSet(BaseModel):
    """Modelo 210 pagador facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    full_name: str | None = None
    person_type: str | None = None
    tax_id: str | None = None


class Modelo210RentaFactSet(BaseModel):
    """Modelo 210 renta facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    clave_divisa: str | None = None


class Modelo210RepresentanteFactSet(BaseModel):
    """Modelo 210 representante facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    appointment_kind: str | None = None
    domicilio_bloque: str | None = None
    domicilio_calificador_numero: str | None = None
    domicilio_codigo_ine_municipio: str | None = None
    domicilio_codigo_postal: str | None = None
    domicilio_codigo_provincia: str | None = None
    domicilio_datos_complementarios: str | None = None
    domicilio_escalera: str | None = None
    domicilio_localidad: str | None = None
    domicilio_nombre_via: str | None = None
    domicilio_numero_casa: str | None = None
    domicilio_planta: str | None = None
    domicilio_portal: str | None = None
    domicilio_puerta: str | None = None
    domicilio_tipo_numeracion: str | None = None
    domicilio_tipo_via: str | None = None
    fax: str | None = None
    full_name: str | None = None
    mobile_phone: str | None = None
    person_type: str | None = None
    phone: str | None = None
    tax_id: str | None = None


class Modelo210SinIngresoNiDevolucionFactSet(BaseModel):
    """Modelo 210 sin ingreso ni devolucion facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    cuota_cero: str | None = None


class Modelo210ProfileFacts(BaseModel):
    """The party, property and settlement facts modelo 210's export layout cites.

    Modelo 210 is the non-resident income tax return. Its layout cites 102 ``irnr.*``
    producer keys across twelve scopes; every one of them resolved to nothing, so the
    contribuyente, the representante, the inmueble and the refund account all rendered
    blank on a filed return.

    Each scope declares its own flat members rather than sharing one address or account
    model. AEAT reuses one address grammar but not one address shape: modelo 210 identifies
    the municipio by INE code where modelo 360 writes its name, so a shared type would assert
    two shapes are interchangeable when they are not.

    Every field is optional and absent stays absent: AEAT writes an alphanumeric header
    field with no content to blancos, so an unsupplied scope is a legal filing rather than
    a defect. Which scopes a given filing must carry is the caller's decision, not this
    type's.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    contribuyente: Modelo210ContribuyenteFactSet | None = None
    declaracion: Modelo210DeclaracionFactSet | None = None
    declarante: Modelo210DeclaranteFactSet | None = None
    devengo: Modelo210DevengoFactSet | None = None
    devolucion: Modelo210DevolucionFactSet | None = None
    ganancia_inmobiliaria: Modelo210GananciaInmobiliariaFactSet | None = None
    ingreso: Modelo210IngresoFactSet | None = None
    inmueble: Modelo210InmuebleFactSet | None = None
    pagador: Modelo210PagadorFactSet | None = None
    renta: Modelo210RentaFactSet | None = None
    representante: Modelo210RepresentanteFactSet | None = None
    sin_ingreso_ni_devolucion: Modelo210SinIngresoNiDevolucionFactSet | None = None
