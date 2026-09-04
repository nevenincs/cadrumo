"""Typed, immutable filing producer inputs.

This module owns the filing-instance facts that export consumers need before
they translate them into a revision-specific registry vocabulary.  It does not
own export keys, layout offsets, or rendered record fragments.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Final, Literal

from pydantic import BaseModel, StringConstraints, model_validator

from ...core.identity import SubjectTaxId
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.payment_election import PaymentElection
from ...core.period import Period, StandardPeriodCode
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ...core.result_disposition import ResultDisposition, result_disposition_is_refund
from ...domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    RegistroRegularizacionResult,
    compute_registro_regularizacion,
)
from ...domain.bienes_inversion.regularizacion_parameters import (
    BienesInversionRegularizacionParameters,
)
from ...domain.deadlines.models import ChargeAccount, ModeloIVAProfile, RefundAccount, TaxpayerProfile
from ...domain.modelos.calculation_revision import CalculationRevisionAmendmentKind, FilingInstanceEvidence
from ...domain.modelos.calculation_revision_amendment import (
    M303RectificativaMotive,
    m303_rectificativa_motive_is_applicable,
)
from ...domain.modelos.calculation_revision_m303_evidence import (
    M303Exonerado390FilingEvidence,
    M303InsolvencyFilingFact,
    M303InsolvencyFilingSubtype,
    M303RegimenSimplificadoCalculationResult,
)
from ...domain.modelos.calculation_revision_m303_handoff import M303RegimenSimplificadoFilingEvidence
from ...domain.prorrata_register.register import ProrrataRegister
from ..aggregation import (
    IvaDifferentiatedDeductionContribution,
    M303ProrrataTransitionArrival,
    M303SupplierRegimeArrival,
)
from ._producer_snapshot_m200 import Modelo200ProfileFacts as _Modelo200ProfileFacts
from ._producer_snapshot_m390 import M390FilingFacts as _M390FilingFacts

_NonBlankName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
_AeatReceiptNumber = Annotated[str, StringConstraints(pattern=r"^\d{13}$")]
_CnaeCode = Annotated[str, StringConstraints(pattern=r"^\d{4}$")]
_M303_OFFICIAL_FILING_PERIODS: Final[frozenset[StandardPeriodCode]] = frozenset(
    {
        StandardPeriodCode.Q1,
        StandardPeriodCode.Q2,
        StandardPeriodCode.Q3,
        StandardPeriodCode.Q4,
        StandardPeriodCode.JAN,
        StandardPeriodCode.FEB,
        StandardPeriodCode.MAR,
        StandardPeriodCode.APR,
        StandardPeriodCode.MAY,
        StandardPeriodCode.JUN,
        StandardPeriodCode.JUL,
        StandardPeriodCode.AUG,
        StandardPeriodCode.SEP,
        StandardPeriodCode.OCT,
        StandardPeriodCode.NOV,
        StandardPeriodCode.DEC,
    },
)


class FilingProducerSnapshotError(ValueError):
    """Raised when filing facts cannot form a complete producer snapshot."""

    __bare_base_rationale__: ClassVar[str] = "internal-filing-producer-snapshot-validation-carrier"


def assert_m303_regularisation_result_matches_bienes_register(
    *,
    bienes_register: BienesInversionIvaRegister,
    regularisation_result: RegistroRegularizacionResult,
    parameters: BienesInversionRegularizacionParameters,
) -> None:
    """Refuse a result that is not the register's exact annual projection.

    The result rows carry the definitive prorrata facts used to produce them,
    so replay the canonical domain projection from those facts and compare the
    complete immutable result.  This admits no result-row omission, foreign
    register, substituted contribution, or invented pending state.

    The result also carries the registry declaration its figures came from, and
    that is checked against ``parameters`` FIRST and by identity rather than by
    replay.  A result produced under a different revision would otherwise be
    silently re-derived under this one and compared against itself, so the
    provenance check is what stops the replay from confirming the wrong law.
    """
    if regularisation_result.parameters_provenance != parameters.provenance:
        raise ValueError(
            "M303 regularisation result was produced from registry declaration "
            f"{regularisation_result.parameters_provenance.modelo_id}/"
            f"{regularisation_result.parameters_provenance.revision_id}"
            f"@{regularisation_result.parameters_provenance.resolved_on.isoformat()}, "
            "not from the supplied "
            f"{parameters.provenance.modelo_id}/{parameters.provenance.revision_id}"
            f"@{parameters.provenance.resolved_on.isoformat()}",
        )
    canonical = compute_registro_regularizacion(
        bienes_register,
        regularizacion_year=regularisation_result.regularizacion_year,
        prorrata_definitiva_by_identifier={
            row.identifier: row.prorrata_anio_pct
            for row in regularisation_result.rows
            if row.prorrata_anio_pct is not None
        },
        parameters=parameters,
    )
    if regularisation_result != canonical:
        raise ValueError("M303 regularisation result must be the canonical projection of the supplied Bienes register")


def _require_m303_official_filing_period(period: Period) -> None:
    """Refuse non-303 periods before they can reach DP30301's producer fields."""
    if period.standard_code not in _M303_OFFICIAL_FILING_PERIODS:
        raise ValueError(
            "Modelo 303 filing facts require an official quarterly or monthly period "
            f"(1T-4T or 01-12), got {period.registry_token!r}",
        )


class PresenterIdentity(BaseModel):
    """Identity of the presenter for this filing instance.

    Presenter identity is deliberately separate from taxpayer identity.  A
    caller must supply it; no taxpayer-to-presenter fallback exists here.
    """

    model_config = STRICT_FROZEN_CONFIG

    tax_id: SubjectTaxId
    full_name: _NonBlankName


class TaxpayerIdentityFacts(BaseModel):
    """Explicit taxpayer name facts for one filing instance.

    The four fields model distinct official producer meanings.  They are not
    interchangeable aliases: a revision requiring one of them must receive
    that exact fact, and an absent fact remains absent.
    """

    model_config = STRICT_FROZEN_CONFIG

    legal_name: _NonBlankName | None
    given_name: _NonBlankName | None
    surnames: _NonBlankName | None
    full_name: _NonBlankName | None


class DeclarationContactFacts(BaseModel):
    """The "persona con quien relacionarse" AEAT asks for on an informativa.

    Distinct from both :class:`TaxpayerIdentityFacts` and
    :class:`PresenterIdentity`: AEAT reserves this pair for whoever it should
    contact ABOUT the declaration, which under a gestor is routinely neither
    the taxpayer nor the transmitting presenter. Filling it from either would
    name the wrong person on a live filing, which is why it is its own fact.

    Both halves are optional and absent stays absent -- AEAT's global rule for
    the informativa header is that an alphanumeric field with no content is
    written to blancos, so an unsupplied contact is a legal filing rather than
    a defect.
    """

    model_config = STRICT_FROZEN_CONFIG

    phone: _NonBlankName | None = None
    full_name: _NonBlankName | None = None
    #: AEAT reserves a second telephone and an e-mail beside the pair above on the
    #: informativa header -- modelo 210 cites both. They were absent here, so the layout's
    #: fields resolved to nothing and rendered blank.
    secondary_phone: _NonBlankName | None = None
    email: _NonBlankName | None = None


class Modelo111ProfileFacts(BaseModel):
    """Stable Modelo 111 profile facts consumed by a filing producer."""

    model_config = STRICT_FROZEN_CONFIG

    colegio_concertado: bool | None


_GrupoNumber = Annotated[str, StringConstraints(min_length=1, max_length=7)]
_ForalTerritory = Annotated[str, StringConstraints(min_length=1, max_length=2)]


class Modelo222ProfileFacts(BaseModel):
    """Fiscal-group identity and régimen facts a Modelo 222 filing declares.

    Modelo 222 is the pago fraccionado of a *grupo fiscal*, so the group's own identity is
    not optional context -- it is what the return is about. AEAT's design prescribes a
    format for the número de grupo (``Nota 8``: ``----/--`` estatal, ``---/--A`` foral),
    which is a rule about content, not about an empty field.

    Before this type existed the twenty-three ``m222.*`` producer keys were declared in the
    vocabulary and resolved by nothing, so every one of them rendered blank on a
    non-required field and the return emitted with its group number and its entidad
    dominante empty.

    Every field below is optional EXCEPT the group identity, because AEAT's own design
    leaves the régimen marks blank when they do not apply, and a mark that does not apply
    is genuinely absent rather than unknown. The group number and the dominante are not in
    that category.
    """

    model_config = STRICT_FROZEN_CONFIG

    numero_grupo: _GrupoNumber
    entidad_dominante_identificacion: str
    entidad_dominante_razon_social: str
    #: "1" representante (entidad no dominante), "2" dominante incluida en el grupo fiscal.
    representante_o_dominante: str | None = None
    normativa_territorio_foral: str | None = None
    entidad_dominante_pais_territorio_foral: _ForalTerritory | None = None
    fecha_inicio_periodo_impositivo: str | None = None
    cnae_actividad_principal: _CnaeCode | None = None
    regimen_entidades_navieras_tonelaje: str | None = None
    regimen_reducida_dimension: str | None = None
    cifra_negocios_grupo_doce_meses: str | None = None
    cooperativa_fiscalmente_protegida: str | None = None
    regimen_entidades_capital_riesgo: str | None = None
    circunstancia_concurrente: str | None = None
    cifra_negocios_periodo_anterior_tramo: str | None = None
    multiples_tipos_impositivos: str | None = None
    tipo_gravamen_impuesto_sociedades: str | None = None
    importe_neto_cifra_negocios_tramo: str | None = None
    modalidad_liquidacion: str | None = None
    comunicacion_datos_adicionales: str | None = None
    numero_referencia_sociedades: str | None = None
    comunicacion_variacion_composicion_grupo: str | None = None
    numero_referencia_sociedades_variacion: str | None = None


_M353GrupoNumber = Annotated[str, StringConstraints(min_length=1, max_length=10)]
_SiNoMark = Annotated[str, StringConstraints(pattern=r"^[12]$")]
_XOrBlankMark = Annotated[str, StringConstraints(pattern=r"^X$")]


class Modelo353ProfileFacts(BaseModel):
    """Grupo de entidades IVA identity and régimen marks a Modelo 353 filing declares.

    Modelo 353 is the *autoliquidación agregada* of the régimen especial del grupo de
    entidades (LIVA art. 163 sexies), so the group's number is what the return is about
    rather than optional colour.

    Before this type existed the five ``m353.*`` producer keys were declared in the
    vocabulary and resolved by nothing, so the número de grupo and the two marks rendered
    from whatever the field's ``required`` flag allowed.

    ``numero_grupo`` is required here. The two régimen marks are required too, and that is
    a departure from the Modelo 222 shape for a grounded reason: AEAT's design gives them
    ``1 -Sí, 2 -No`` and the published layout marks both ``required = true``, so there is
    no blank state to represent -- a filer who is not inscrito declares ``"2"``, not
    nothing. ``sin_actividad`` and ``grupo_normativa_foral`` are the genuinely optional
    ones: the design reads ``X o blanco``.
    """

    model_config = STRICT_FROZEN_CONFIG

    #: Identificación. Nº Grupo -- design offset 109, length 10.
    numero_grupo: _M353GrupoNumber
    #: Tipo régimen especial aplicable, art. 163 sexies.cinco: "1" sí, "2" no.
    regimen_especial_avanzado_elected: _SiNoMark
    #: Inscrito en el Registro de devolución mensual (art. 30 RIVA): "1" sí, "2" no.
    regimen_especial_inscrito_redeme: _SiNoMark
    #: "X o blanco" in the design; absent means the group had activity.
    sin_actividad: _XOrBlankMark | None = None
    #: "X o blanco" in the design; absent means the group is not sometido a normativa foral.
    grupo_normativa_foral: _XOrBlankMark | None = None


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

    These rows are NOT yet fed from the withholding substrate. The values already exist in
    the registry as ``Withholding296Observation`` -- perceptor tax id, legal name, naturaleza,
    clave, subclave, base and retencion among them -- and the snapshot assembler should
    project them from there rather than take them as operator entry. Until it does, a caller
    that populates these by hand can state a figure the ledger disagrees with.
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


class Modelo210ContribuyenteFacts(BaseModel):
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


class Modelo210DeclaracionFacts(BaseModel):
    """Modelo 210 declaracion facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    tipo: str | None = None


class Modelo210DeclaranteFacts(BaseModel):
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


class Modelo210DevengoFacts(BaseModel):
    """Modelo 210 devengo facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    agrupacion: str | None = None
    fecha_devengo: str | None = None


class Modelo210DevolucionFacts(BaseModel):
    """Modelo 210 devolucion facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

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


class Modelo210GananciaInmobiliariaFacts(BaseModel):
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


class Modelo210IngresoFacts(BaseModel):
    """Modelo 210 ingreso facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

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


class Modelo210InmuebleFacts(BaseModel):
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


class Modelo210PagadorFacts(BaseModel):
    """Modelo 210 pagador facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    full_name: str | None = None
    person_type: str | None = None
    tax_id: str | None = None


class Modelo210RentaFacts(BaseModel):
    """Modelo 210 renta facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    clave_divisa: str | None = None


class Modelo210RepresentanteFacts(BaseModel):
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


class Modelo210SinIngresoNiDevolucionFacts(BaseModel):
    """Modelo 210 sin ingreso ni devolucion facts, flat members named from the AEAT component vocabulary."""

    model_config = STRICT_FROZEN_CONFIG

    cuota_cero: str | None = None


class Modelo210ProfileFacts(BaseModel):
    """The party, property and settlement facts modelo 210's export layout cites.

    Modelo 210 is the non-resident income tax return. Its layout cites 102 ``irnr.*``
    producer keys across twelve scopes; every one of them resolved to nothing, so the
    contribuyente, the representante, the inmueble and the refund account all rendered
    blank on a filed return.

    Each scope declares its own FLAT members rather than sharing one address or account
    model. That is the decision recorded in :mod:`cadrumo.core.address_components`:
    AEAT reuses one address GRAMMAR but not one address SHAPE -- modelo 210 identifies the
    municipio by INE code where modelo 360 writes its name -- so a shared type would assert
    two shapes are interchangeable when they are not. The vocabulary fixes what the leaves
    are CALLED; it does not merge them.

    Every field is optional and absent stays absent: AEAT writes an alphanumeric header
    field with no content to blancos, so an unsupplied scope is a legal filing rather than
    a defect. Which scopes a given filing must carry is the caller's decision, not this
    type's.
    """

    model_config = STRICT_FROZEN_CONFIG

    contribuyente: Modelo210ContribuyenteFacts | None = None
    declaracion: Modelo210DeclaracionFacts | None = None
    declarante: Modelo210DeclaranteFacts | None = None
    devengo: Modelo210DevengoFacts | None = None
    devolucion: Modelo210DevolucionFacts | None = None
    ganancia_inmobiliaria: Modelo210GananciaInmobiliariaFacts | None = None
    ingreso: Modelo210IngresoFacts | None = None
    inmueble: Modelo210InmuebleFacts | None = None
    pagador: Modelo210PagadorFacts | None = None
    renta: Modelo210RentaFacts | None = None
    representante: Modelo210RepresentanteFacts | None = None
    sin_ingreso_ni_devolucion: Modelo210SinIngresoNiDevolucionFacts | None = None


class GeneralFilingProfileFacts(BaseModel):
    """Explicit absence of modelo-specific producer facts for a layout."""

    model_config = STRICT_FROZEN_CONFIG


class Modelo202ActivityFacts(BaseModel):
    """One repeatable M202 activity fact, without claiming primacy."""

    model_config = STRICT_FROZEN_CONFIG

    cnae: _CnaeCode


class M202UnsupportedProducerId(StrEnum):
    """M202 producer facts that are not yet admitted to the typed substrate."""

    PRINCIPAL_CNAE = "m202.principal_cnae"
    OFFICIAL_OFFSET_122 = "m202.official_offset_122"
    OFFICIAL_OFFSET_123 = "m202.official_offset_123"
    OFFICIAL_OFFSET_124 = "m202.official_offset_124"
    OFFICIAL_OFFSET_125 = "m202.official_offset_125"
    OFFICIAL_OFFSET_126 = "m202.official_offset_126"
    OFFICIAL_OFFSET_127 = "m202.official_offset_127"
    OFFICIAL_OFFSET_128 = "m202.official_offset_128"
    OFFICIAL_OFFSET_129 = "m202.official_offset_129"
    OFFICIAL_OFFSET_130 = "m202.official_offset_130"
    OFFICIAL_OFFSET_131 = "m202.official_offset_131"
    OFFICIAL_OFFSET_132 = "m202.official_offset_132"
    OFFICIAL_OFFSET_147 = "m202.official_offset_147"


M202_UNSUPPORTED_PRODUCER_IDS: tuple[M202UnsupportedProducerId, ...] = tuple(M202UnsupportedProducerId)


class Modelo202ProducerProfile(BaseModel):
    """M202 producer view referencing the canonical taxpayer profile owner.

    The régimen marks and the principal CNAE below are what modelo 202's export layout
    cites as header producers. Before they existed the eighteen ``m202.*`` keys were
    declared in the vocabulary and resolved by nothing, so each one rendered blank on a
    filed pago fraccionado.

    ``principal_cnae`` is DECLARED, never inferred from ``activities``:
    :class:`Modelo202ActivityFacts` is documented as "one repeatable M202 activity fact,
    without claiming primacy", so picking the first or the largest would invent a primacy
    the substrate deliberately does not carry. AEAT asks which activity is principal, so
    the operator answers it.

    Every mark is optional and absent stays absent -- AEAT leaves a régimen mark blank when
    the régimen does not apply, and a mark that does not apply is genuinely absent rather
    than unknown.
    """

    model_config = STRICT_FROZEN_CONFIG

    taxpayer_profile: TaxpayerProfile
    activities: tuple[Modelo202ActivityFacts, ...]
    principal_cnae: _CnaeCode | None = None
    regimen_ley_49_2002_sin_fines_lucrativos: str | None = None
    regimen_ley_11_2009_socimi: str | None = None
    regimen_entidades_navieras_tonelaje: str | None = None
    regimen_articulo_101_lis_reducida_dimension: str | None = None
    regimen_entidad_capital_riesgo: str | None = None
    cifra_negocios_doce_meses_umbral: str | None = None
    cifra_negocios_periodo_anterior_bajo_umbral: str | None = None
    cooperativa_o_multiples_tipos: str | None = None
    cooperativa_fiscalmente_protegida: str | None = None
    multiples_tipos_impositivos: str | None = None
    tipo_gravamen_impuesto_sociedades: str | None = None
    importe_neto_cifra_negocios_tramo: str | None = None
    marca_instrumental: str | None = None
    discriminante_declaracion_negativa: str | None = None
    normativa_territorio_foral: str | None = None
    comunicacion_datos_adicionales: str | None = None
    numero_referencia_sociedades: str | None = None

    @property
    def unsupported_producer_ids(self) -> tuple[M202UnsupportedProducerId, ...]:
        """Return the exact immutable M202 producer-gap inventory."""
        return M202_UNSUPPORTED_PRODUCER_IDS


class FilingElectionFacts(BaseModel):
    """Immutable operator elections and their resolved result disposition."""

    model_config = STRICT_FROZEN_CONFIG

    result_disposition: ResultDisposition
    payment: PaymentElection
    refund: RefundElection
    prior_domiciliation: PriorDomiciliationElection


class M303FilingFacts(BaseModel):
    """DP30301 facts owned by one immutable Modelo 303 filing instance."""

    model_config = STRICT_FROZEN_CONFIG

    joint_return_elected: bool
    annual_volume_nonzero: bool
    insolvency: M303InsolvencyFilingFact | None
    exonerado_390: M303Exonerado390FilingEvidence
    regimen_simplificado: M303RegimenSimplificadoFilingEvidence
    regimen_simplificado_result: M303RegimenSimplificadoCalculationResult
    period: Period
    supplier_regime: M303SupplierRegimeArrival
    prorrata_transition: M303ProrrataTransitionArrival
    prorrata_register: ProrrataRegister
    differentiated_contributions: tuple[IvaDifferentiatedDeductionContribution, ...]
    bienes_register: BienesInversionIvaRegister
    regularisation_result: RegistroRegularizacionResult
    #: The registry-resolved figures the regularisation result was produced
    #: under. Carried on the facts rather than resolved here because this
    #: model holds no revision, and because the oracle's independence depends
    #: on comparing the result's own provenance against a bundle supplied
    #: from outside it.
    bienes_parameters: BienesInversionRegularizacionParameters

    @model_validator(mode="after")
    def _arrivals_share_one_filing_period(self) -> M303FilingFacts:
        _validate_m303_filing_periods(self)
        _validate_m303_calculation_results(self)
        _validate_m303_register_evidence(self)
        return self


def _validate_m303_filing_periods(facts: M303FilingFacts) -> None:
    _require_m303_official_filing_period(facts.period)
    if facts.period != facts.supplier_regime.period or facts.period != facts.prorrata_transition.period:
        raise ValueError("M303 filing facts and arrivals must share one filing period")
    if facts.regularisation_result.regularizacion_year != facts.period.filing_year:
        raise ValueError("M303 regularisation result must use the filing year")


def _validate_m303_calculation_results(facts: M303FilingFacts) -> None:
    if facts.regimen_simplificado_result != facts.regimen_simplificado.calculation_result:
        raise ValueError("M303 filing facts must retain the exact simplified-regime calculation result")
    if facts.regimen_simplificado_result.period != facts.period:
        raise ValueError("M303 filing facts and simplified-regime result must share one filing period")


def _validate_m303_register_evidence(facts: M303FilingFacts) -> None:
    assert_m303_regularisation_result_matches_bienes_register(
        bienes_register=facts.bienes_register,
        regularisation_result=facts.regularisation_result,
        parameters=facts.bienes_parameters,
    )
    if facts.prorrata_transition.is_applicable and not facts.prorrata_register.has_complete_current_entry_coverage(
        facts.period.filing_year
    ):
        raise ValueError("M303 final-period filing facts require complete current-year prorrata register coverage")
    for entry in facts.prorrata_transition.register_evidence:
        if facts.prorrata_register.entry_for(entry.ejercicio, sector_id=entry.sector_id) != entry:
            raise ValueError("M303 prorrata transition arrival evidence must belong to the supplied register")


def resolve_m303_filing_facts(
    *,
    evidence: FilingInstanceEvidence,
    supplier_regime: M303SupplierRegimeArrival,
    prorrata_transition: M303ProrrataTransitionArrival,
    prorrata_register: ProrrataRegister,
    differentiated_contributions: tuple[IvaDifferentiatedDeductionContribution, ...],
    bienes_register: BienesInversionIvaRegister,
    regularisation_result: RegistroRegularizacionResult,
    bienes_parameters: BienesInversionRegularizacionParameters,
) -> M303FilingFacts:
    """Project persisted M303 evidence together with canonical arrival facts."""
    m303 = evidence.m303
    _require_m303_official_filing_period(m303.period)
    return M303FilingFacts(
        joint_return_elected=m303.joint_return_elected,
        annual_volume_nonzero=m303.annual_volume_nonzero,
        insolvency=m303.insolvency,
        exonerado_390=m303.exonerado_390,
        regimen_simplificado=m303.regimen_simplificado,
        regimen_simplificado_result=m303.regimen_simplificado.calculation_result,
        period=m303.period,
        supplier_regime=supplier_regime,
        prorrata_transition=prorrata_transition,
        prorrata_register=prorrata_register,
        differentiated_contributions=differentiated_contributions,
        bienes_register=bienes_register,
        regularisation_result=regularisation_result,
        bienes_parameters=bienes_parameters,
    )


class AmendmentEvidence(BaseModel):
    """Typed evidence for an amendment of an AEAT-accepted filing."""

    model_config = STRICT_FROZEN_CONFIG

    kind: CalculationRevisionAmendmentKind
    m303_rectificativa_motive: M303RectificativaMotive | None
    original_aeat_receipt: _AeatReceiptNumber

    @model_validator(mode="after")
    def _motive_belongs_only_to_rectificativa(self) -> AmendmentEvidence:
        if (
            self.m303_rectificativa_motive is not None
            and self.kind is not CalculationRevisionAmendmentKind.RECTIFICATIVA
        ):
            raise ValueError("M303 rectificativa motive is valid only for rectificativa evidence")
        return self

    @property
    def is_complementaria(self) -> bool:
        """True when this evidence records a complementaria amendment."""
        return self.kind is CalculationRevisionAmendmentKind.COMPLEMENTARIA

    @property
    def is_sustitutiva(self) -> bool:
        """True when this evidence records a sustitutiva amendment."""
        return self.kind is CalculationRevisionAmendmentKind.SUSTITUTIVA

    @property
    def is_rectificativa(self) -> bool:
        """True when this evidence records a rectificativa amendment."""
        return self.kind is CalculationRevisionAmendmentKind.RECTIFICATIVA


class RefundAccountSelection(BaseModel):
    """Secure account selected for a refund disposition."""

    model_config = STRICT_FROZEN_CONFIG

    role: Literal["refund"]
    account: RefundAccount


class ChargeAccountSelection(BaseModel):
    """Secure account selected for a direct-debit disposition."""

    model_config = STRICT_FROZEN_CONFIG

    role: Literal["charge"]
    account: ChargeAccount


type SelectedFilingAccount = RefundAccountSelection | ChargeAccountSelection
type FilingModelProfileFacts = (
    GeneralFilingProfileFacts
    | Modelo111ProfileFacts
    | Modelo202ProducerProfile
    | _Modelo200ProfileFacts
    | Modelo210ProfileFacts
    | Modelo222ProfileFacts
    | Modelo296ProfileFacts
    | Modelo353ProfileFacts
    | ModeloIVAProfile
)


class FilingProducerSnapshot(BaseModel):
    """Complete immutable filing facts before registry-specific translation."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: Modelo
    taxpayer_tax_id: SubjectTaxId
    taxpayer_identity: TaxpayerIdentityFacts
    presenter: PresenterIdentity
    #: Defaulted rather than required: every existing caller predates this fact
    #: and none of them can supply it, so demanding it would refuse filings that
    #: are legal without it. An absent contact renders as blancos, which is what
    #: AEAT's own header rule prescribes.
    declaration_contact: DeclarationContactFacts = DeclarationContactFacts()
    model_profile: FilingModelProfileFacts
    elections: FilingElectionFacts
    amendment_evidence: AmendmentEvidence | None
    selected_account: SelectedFilingAccount | None
    m303_filing_facts: M303FilingFacts | None
    m390_filing_facts: _M390FilingFacts | None = None

    @model_validator(mode="after")
    def _validate_model_profile(self) -> FilingProducerSnapshot:
        _validate_snapshot_model_profile(self)
        _validate_snapshot_account_selection(self)
        _validate_snapshot_profile_secrecy(self)
        return self


def _validate_snapshot_model_profile(snapshot: FilingProducerSnapshot) -> None:
    if snapshot.modelo is not Modelo.M303 and snapshot.m303_filing_facts is not None:
        raise ValueError("M303FilingFacts are valid only for modelo 303")
    if snapshot.modelo is not Modelo.M390 and snapshot.m390_filing_facts is not None:
        raise ValueError("M390FilingFacts are valid only for modelo 390")
    if (
        snapshot.modelo is not Modelo.M303
        and snapshot.amendment_evidence is not None
        and snapshot.amendment_evidence.m303_rectificativa_motive is not None
    ):
        raise ValueError("M303 rectificativa motive is valid only for modelo 303")
    if snapshot.modelo is Modelo.M111:
        _validate_modelo_111_snapshot(snapshot)
        return
    if snapshot.modelo is Modelo.M202:
        _validate_modelo_202_snapshot(snapshot)
        return
    if snapshot.modelo is Modelo.M222:
        _validate_modelo_222_snapshot(snapshot)
        return
    if snapshot.modelo is Modelo.M303:
        _validate_modelo_303_snapshot(snapshot)
        return
    if snapshot.modelo is Modelo.M296:
        _validate_modelo_296_snapshot(snapshot)
        return
    if snapshot.modelo is Modelo.M353:
        _validate_modelo_353_snapshot(snapshot)
        return
    _validate_general_modelo_snapshot(snapshot)


def _validate_modelo_296_snapshot(snapshot: FilingProducerSnapshot) -> None:
    """Modelo 296 identifies a declarante and an ejercicio; it cannot be filed without them."""
    if not isinstance(snapshot.model_profile, Modelo296ProfileFacts):
        raise ValueError("modelo 296 requires Modelo296ProfileFacts")


def _validate_modelo_353_snapshot(snapshot: FilingProducerSnapshot) -> None:
    """Modelo 353 is the grupo de entidades aggregate; it cannot be filed without it."""
    if not isinstance(snapshot.model_profile, Modelo353ProfileFacts):
        raise ValueError("modelo 353 requires Modelo353ProfileFacts")


def _validate_modelo_222_snapshot(snapshot: FilingProducerSnapshot) -> None:
    """Modelo 222 is a grupo fiscal return; it cannot be filed without the group."""
    if not isinstance(snapshot.model_profile, Modelo222ProfileFacts):
        raise ValueError("modelo 222 requires Modelo222ProfileFacts")


def _validate_modelo_111_snapshot(snapshot: FilingProducerSnapshot) -> None:
    if not isinstance(snapshot.model_profile, Modelo111ProfileFacts):
        raise ValueError("modelo 111 requires Modelo111ProfileFacts")
    if snapshot.model_profile.colegio_concertado is None:
        raise ValueError("Modelo 111 colegio_concertado must be explicitly declared")


def _validate_modelo_202_snapshot(snapshot: FilingProducerSnapshot) -> None:
    if not isinstance(snapshot.model_profile, Modelo202ProducerProfile):
        raise ValueError("modelo 202 requires Modelo202ProducerProfile")
    unsupported = ", ".join(item.value for item in snapshot.model_profile.unsupported_producer_ids)
    raise ValueError(f"Modelo 202 producer snapshot is incomplete: {unsupported}")


def _validate_modelo_303_snapshot(snapshot: FilingProducerSnapshot) -> None:
    if not isinstance(snapshot.model_profile, ModeloIVAProfile):
        raise ValueError("modelo 303 requires the canonical ModeloIVAProfile")
    if snapshot.m303_filing_facts is None:
        raise ValueError("modelo 303 requires complete M303FilingFacts")
    amendment = snapshot.amendment_evidence
    motive_applicable = m303_rectificativa_motive_is_applicable(
        registry_revision_id=snapshot.m303_filing_facts.regimen_simplificado.regimen_snapshot.orden.registry_revision_id,
        record_design=snapshot.m303_filing_facts.regimen_simplificado.regimen_snapshot.record_design,
    )
    has_rectificativa = amendment is not None and amendment.is_rectificativa
    has_motive = amendment is not None and amendment.m303_rectificativa_motive is not None
    if motive_applicable and has_rectificativa != has_motive:
        raise ValueError("applicable M303 rectificativa evidence requires exactly one canonical motive")
    if not motive_applicable and has_motive:
        raise ValueError("M303 rectificativa motive is prohibited outside the admitted record-design sources")


def _validate_general_modelo_snapshot(snapshot: FilingProducerSnapshot) -> None:
    if not isinstance(snapshot.model_profile, GeneralFilingProfileFacts):
        raise ValueError(f"modelo {snapshot.modelo.value} requires GeneralFilingProfileFacts")


def _validate_snapshot_account_selection(snapshot: FilingProducerSnapshot) -> None:
    disposition = snapshot.elections.result_disposition
    if disposition is ResultDisposition.DOMICILIACION:
        if snapshot.elections.payment is not PaymentElection.DOMICILIACION:
            raise ValueError("domiciliacion disposition requires the matching payment election")
        if not isinstance(snapshot.selected_account, ChargeAccountSelection):
            raise ValueError("domiciliacion disposition requires a selected charge account")
    elif snapshot.elections.payment is PaymentElection.DOMICILIACION:
        raise ValueError("domiciliacion payment election requires the matching result disposition")
    elif result_disposition_is_refund(disposition):
        if not isinstance(snapshot.selected_account, RefundAccountSelection):
            raise ValueError("refund disposition requires a selected refund account")
    elif snapshot.selected_account is not None:
        raise ValueError("a result disposition without an account must not retain one")


def _validate_snapshot_profile_secrecy(snapshot: FilingProducerSnapshot) -> None:
    profile_iva = _profile_iva(snapshot.model_profile)
    if profile_iva is not None and (profile_iva.refund_account is not None or profile_iva.charge_account is not None):
        raise ValueError("model profile must not retain accounts outside selected_account")


def _profile_iva(model_profile: FilingModelProfileFacts) -> ModeloIVAProfile | None:
    if isinstance(model_profile, ModeloIVAProfile):
        return model_profile
    if isinstance(model_profile, Modelo202ProducerProfile):
        return model_profile.taxpayer_profile.iva
    return None


def build_filing_producer_snapshot(
    *,
    modelo: Modelo,
    taxpayer_tax_id: SubjectTaxId,
    taxpayer_identity: TaxpayerIdentityFacts,
    presenter: PresenterIdentity,
    model_profile: FilingModelProfileFacts,
    elections: FilingElectionFacts,
    amendment_evidence: AmendmentEvidence | None,
    refund_account: RefundAccount | None,
    charge_account: ChargeAccount | None,
    m303_filing_facts: M303FilingFacts | None,
    declaration_contact: DeclarationContactFacts | None = None,
) -> FilingProducerSnapshot:
    """Build a snapshot retaining only the account selected by disposition.

    ``declaration_contact`` is optional so every caller that predates the
    informativa contact fact keeps working unchanged; an absent contact renders
    as blancos, which is what AEAT's own header rule prescribes.
    """
    safe_model_profile = _without_embedded_accounts(model_profile)
    selected_account: SelectedFilingAccount | None
    if elections.result_disposition is ResultDisposition.DOMICILIACION:
        if charge_account is None:
            raise FilingProducerSnapshotError("domiciliacion requires a charge account")
        selected_account = ChargeAccountSelection(role="charge", account=charge_account)
    elif result_disposition_is_refund(elections.result_disposition):
        if refund_account is None or refund_account.iban is None:
            raise FilingProducerSnapshotError("refund disposition requires a refund account")
        selected_account = RefundAccountSelection(role="refund", account=refund_account)
    else:
        selected_account = None

    try:
        return FilingProducerSnapshot(
            modelo=modelo,
            taxpayer_tax_id=taxpayer_tax_id,
            taxpayer_identity=taxpayer_identity,
            presenter=presenter,
            model_profile=safe_model_profile,
            elections=elections,
            amendment_evidence=amendment_evidence,
            selected_account=selected_account,
            m303_filing_facts=m303_filing_facts,
            m390_filing_facts=None,
            declaration_contact=declaration_contact or DeclarationContactFacts(),
        )
    except ValueError as exc:
        raise FilingProducerSnapshotError(str(exc)) from exc


def _without_embedded_accounts(model_profile: FilingModelProfileFacts) -> FilingModelProfileFacts:
    if isinstance(model_profile, ModeloIVAProfile):
        return model_profile.model_copy(update={"refund_account": None, "charge_account": None})
    if isinstance(model_profile, Modelo202ProducerProfile):
        taxpayer_profile = model_profile.taxpayer_profile
        if taxpayer_profile.iva is None:
            return model_profile
        safe_iva = taxpayer_profile.iva.model_copy(update={"refund_account": None, "charge_account": None})
        safe_taxpayer = taxpayer_profile.model_copy(update={"iva": safe_iva})
        return model_profile.model_copy(update={"taxpayer_profile": safe_taxpayer})
    return model_profile


__all__ = [
    "M202_UNSUPPORTED_PRODUCER_IDS",
    "AmendmentEvidence",
    "ChargeAccountSelection",
    "FilingElectionFacts",
    "FilingModelProfileFacts",
    "FilingProducerSnapshot",
    "FilingProducerSnapshotError",
    "GeneralFilingProfileFacts",
    "M202UnsupportedProducerId",
    "M303FilingFacts",
    "M303InsolvencyFilingFact",
    "M303InsolvencyFilingSubtype",
    "Modelo111ProfileFacts",
    "Modelo202ActivityFacts",
    "Modelo202ProducerProfile",
    "PresenterIdentity",
    "RefundAccountSelection",
    "SelectedFilingAccount",
    "TaxpayerIdentityFacts",
    "assert_m303_regularisation_result_matches_bienes_register",
    "build_filing_producer_snapshot",
    "resolve_m303_filing_facts",
]
