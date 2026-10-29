"""Typed filing facts for m296."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, StringConstraints

from ...core.models import STRICT_FROZEN_CONFIG

_NonBlankName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
_AeatReceiptNumber = Annotated[str, StringConstraints(pattern=r"^\d{13}$")]


_M296SupportType = Annotated[str, StringConstraints(pattern=r"^[TC]$")]
_M296AmendmentMark = Annotated[str, StringConstraints(min_length=1, max_length=2)]
_FourDigitYear = Annotated[str, StringConstraints(pattern=r"^\d{4}$")]
_DigitString9 = Annotated[str, StringConstraints(pattern=r"^\d{1,9}$")]


class Modelo296PerceptorRow(BaseModel):
    """One Modelo 296 perceptor: the payee, the renta and the retencion practicada.

    The Tipo 2 record is emitted once per payee, so this row is the unit AEAT repeats.
    Members are ``M296PerceptorField``'s values verbatim and are generated from that enum,
    which keeps the projection reference and the row that answers it in lock-step: a field
    the reference can name is a field this row has.

    Every member is optional and rendered as text. The record design's own per-field width,
    padding, justification and data type are what shape the bytes, and they live in the
    published layout; duplicating them as constraints here would be a second copy of the
    design that is free to disagree with it.

    These are operator-supplied filing detail rows held by the typed producer snapshot.
    The projection plan reads them by render occurrence. No automatic feed from a ledger
    or withholding observation store is enrolled, so this row does not certify that its
    supplied figures agree with ledger evidence.
    """

    model_config = STRICT_FROZEN_CONFIG

    apellidos_y_nombre_razon_social_o_deno: str | None = None
    base_retenciones_e_ingresos_a_cuenta: str | None = None
    ciudad: str | None = None
    clave: str | None = None
    clave_de_mercado: str | None = None
    codigo: str | None = None
    codigo_bic_del_perceptor_mediador: str | None = None
    codigo_cuenta_valores: str | None = None
    codigo_emisor: str | None = None
    codigo_lei_del_perceptor: str | None = None
    codigo_pais: str | None = None
    decimal: str | None = None
    decimal_numerico_parte_decimal: str | None = None
    decimal_numerico_parte_decimal_2: str | None = None
    decimal_numerico_parte_decimal_3: str | None = None
    declarante: str | None = None
    direccion_del_perceptor: str | None = None
    ejercicio: str | None = None
    ejercicio_devengo: str | None = None
    entero: str | None = None
    entero_numerico_parte_entera: str | None = None
    entero_numerico_parte_entera_2: str | None = None
    entero_numerico_parte_entera_3: str | None = None
    f_j: str | None = None
    fecha_de_devengo: str | None = None
    fecha_de_inicio_del_prestamo: str | None = None
    fecha_de_nacimiento: str | None = None
    fecha_de_vencimiento_del_prestamo: str | None = None
    identificador_de_registro_o_numero_de: str | None = None
    ingresos_a_cuenta_repercutidos: str | None = None
    naturaleza: str | None = None
    nif_del_declarante: str | None = None
    nif_del_pagador_anterior: str | None = None
    nif_del_perceptor: str | None = None
    nif_del_representante_legal: str | None = None
    nif_en_el_pais_de_residencia_fiscal: str | None = None
    pais_o_territorio_de_residencia_fiscal: str | None = None
    parte_decimal_del_importe_de_las_reten: str | None = None
    parte_entera_del_importe_de_las_retenc: str | None = None
    pendiente: str | None = None
    perceptor_mediador: str | None = None
    procedimiento_especial_de_retenciones: str | None = None
    subclave: str | None = None
    tipo_codigo: str | None = None


class Modelo296PerceptorInteresesRow(BaseModel):
    """One Modelo 296 perceptor of the intereses hoja.

    Members are ``M296PerceptorInteresesField``'s values verbatim and are generated from that
    enum, so a field the projection reference can name is a field this row has. Every member
    is optional and rendered as text: the per-field width, padding, justification and data
    type belong to the published layout, and a second copy of them here would be free to
    disagree with the design.
    """

    model_config = STRICT_FROZEN_CONFIG

    apellidos_y_nombre_razon_social_o_deno: str | None = None
    ejercicio: str | None = None
    f_j: str | None = None
    identificador_de_registro_o_numero_de: str | None = None
    nif_del_declarante: str | None = None
    nif_del_perceptor: str | None = None
    nif_del_representante_legal: str | None = None
    retenciones_e_ingresos_a_cuenta_ingres: str | None = None


class Modelo296AnexoPagoRow(BaseModel):
    """One Modelo 296 pago a contribuyente.

    Members are ``M296AnexoPagoField``'s values verbatim and are generated from that
    enum, so a field the projection reference can name is a field this row has. Every member
    is optional and rendered as text: the per-field width, padding, justification and data
    type belong to the published layout, and a second copy of them here would be free to
    disagree with the design.
    """

    model_config = STRICT_FROZEN_CONFIG

    apellidos_y_nombre_razon_social_o_deno: str | None = None
    apellidos_y_nombre_razon_social_o_deno_2: str | None = None
    ciudad: str | None = None
    clave_de_personalidad_del_contribuyent: str | None = None
    codigo_isin: str | None = None
    codigo_lei_del_contribuyente: str | None = None
    codigo_pais: str | None = None
    direccion_del_contribuyente: str | None = None
    ejercicio: str | None = None
    f_j: str | None = None
    fecha_de_devengo: str | None = None
    fecha_de_nacimiento_del_contribuyente: str | None = None
    identificador_de_registro_o_numero_de: str | None = None
    importe_del_pago_al_contribuyente: str | None = None
    nif_del_contribuyente: str | None = None
    nif_del_declarante: str | None = None
    nif_del_perceptor: str | None = None
    nif_del_representante_legal: str | None = None
    nif_en_el_pais_de_residencia_fiscal_de: str | None = None
    numero_de_justificante_del_modelo_210: str | None = None
    pais_o_territorio_de_residencia_fiscal: str | None = None
    porcentaje_de_retencion: str | None = None
    retenciones: str | None = None


class Modelo296AnexoCertificadoRow(BaseModel):
    """One Modelo 296 certificado de pago.

    Members are ``M296AnexoCertificadoField``'s values verbatim and are generated from that
    enum, so a field the projection reference can name is a field this row has. Every member
    is optional and rendered as text: the per-field width, padding, justification and data
    type belong to the published layout, and a second copy of them here would be free to
    disagree with the design.
    """

    model_config = STRICT_FROZEN_CONFIG

    apellidos_y_nombre_razon_social_o_deno: str | None = None
    apellidos_y_nombre_razon_social_o_deno_2: str | None = None
    codigo_cuenta_valores_del_certificado: str | None = None
    codigo_isin_del_certificado: str | None = None
    codigo_lei_del_titular_registral: str | None = None
    decimal: str | None = None
    decimal_2: str | None = None
    decimal_3: str | None = None
    ejercicio: str | None = None
    entero: str | None = None
    entero_2: str | None = None
    entero_3: str | None = None
    f_j: str | None = None
    fecha_de_pago: str | None = None
    fecha_de_presentacion_del_modelo_210: str | None = None
    identificador_de_registro_o_numero_de: str | None = None
    nif_del_declarante: str | None = None
    nif_del_perceptor: str | None = None
    nif_del_representante_legal: str | None = None
    numero_de_justificante_del_modelo_210: str | None = None
    parte_decimal_del_numero_de_titulos: str | None = None
    parte_decimal_del_numero_de_titulos_2: str | None = None
    parte_entera_del_numero_de_titulos: str | None = None
    parte_entera_del_numero_de_titulos_2: str | None = None
    titular_registral_de_la_cuenta_de_valo: str | None = None


class Modelo296ProfileFacts(BaseModel):
    """Declarant identity the Modelo 296 tipo-1 record declares.

    Modelo 296 is the IRNR annual summary of retenciones e ingresos a cuenta on rentas
    obtained by non-residents without permanent establishment (TRLIRNR art. 24, Orden
    EHA/3290/2008 art. 6). Its first record identifies who is declaring, for which
    ejercicio, and how many perceptores the file carries.

    All twelve ``m296.dec.*`` keys were declared in the vocabulary and produced by nothing,
    so every one of them rendered blank: the ejercicio at offset 5, the declarante NIF at
    offset 9 and the razon social at offset 18 among them. A 296 emitted that way names
    nobody.

    Field names are the AEAT key tails verbatim, including two the source design truncated:
    ``apellidos_y_nombre`` is *persona con quien relacionarse* (design ordinal 7, the
    49-byte contact block AEAT splits into a 9-byte telefono and a 40-byte name), and ``n``
    is ``N.I.F. DEL REPRESENTANTE LEGAL.`` (design ordinal 16, offset 391) -- the slug
    stopped at the first period in the label. Renaming either would change a published
    layout, so the name stays and the meaning is recorded here.

    ``ejercicio`` restates a year the draft already knows. The structurally better home is
    a ``draft`` field carrying ``ExportDraftAttribute.FILING_YEAR``, which cannot disagree
    with the draft; that is a layout change and is not made here. Until it is, a snapshot
    builder must populate this from the draft's own filing year rather than from an
    independently entered value.
    """

    model_config = STRICT_FROZEN_CONFIG

    #: Ejercicio -- design offset 5, length 4, four-digit year.
    ejercicio: _FourDigitYear
    #: NIF del declarante -- design offset 9, length 9.
    nif_del_declarante: _NonBlankName
    #: Apellidos y nombre o razon social del declarante -- design offset 18, length 40.
    apellidos_y_nombre_o_razon_social_del: _NonBlankName
    #: Tipo de soporte -- design offset 58, length 1, alfabetico.
    tipo_de_soporte: _M296SupportType | None = None
    #: Persona con quien relacionarse, telefono -- design offset 59, length 9.
    telefono: _DigitString9 | None = None
    #: Persona con quien relacionarse, apellidos y nombre -- design offset 68, length 40.
    apellidos_y_nombre: _NonBlankName | None = None
    #: Numero identificativo de la declaracion -- design offset 108, length 13.
    numero_identificativo_de_la_declaracio: _AeatReceiptNumber | None = None
    #: Declaracion complementaria o sustitutiva -- design offset 121, length 2.
    declaracion_complementaria_o_sustituti: _M296AmendmentMark | None = None
    #: Numero identificativo de la declaracion anterior -- design offset 123, length 13.
    numero_identificativo_de_la_declaracio_2: _AeatReceiptNumber | None = None
    #: Numero total de perceptores -- design offset 136, length 9.
    #:
    #: An operator-supplied count that the perceptor rows themselves determine. It is
    #: optional here deliberately: once the perceptor record repeats its rows, the count is
    #: derived from them, and a value stated here that disagrees with the rows is a defect
    #: rather than a fact.
    numero_total_de_perceptores: _DigitString9 | None = None
    #: N.I.F. del representante legal -- design offset 391, length 9. See the class note on
    #: why the key tail is ``n``.
    n: _NonBlankName | None = None
    #: Sello electronico -- design offset 488, length 13.
    sello_electronico: str | None = None
    #: One entry per payee. Empty emits no perceptor record at all, which is what AEAT
    #: expects of a declaration with nothing to report; whether that absence is admissible
    #: is the record's own required flag, checked by the renderer.
    perceptor_rows: tuple[Modelo296PerceptorRow, ...] = ()
    #: One entry per perceptor of the intereses hoja. Empty emits no row of this record at all.
    perceptor_intereses_rows: tuple[Modelo296PerceptorInteresesRow, ...] = ()
    #: One entry per pago a contribuyente. Empty emits no row of this record at all.
    anexo_pago_rows: tuple[Modelo296AnexoPagoRow, ...] = ()
    #: One entry per certificado de pago. Empty emits no row of this record at all.
    anexo_certificado_rows: tuple[Modelo296AnexoCertificadoRow, ...] = ()
