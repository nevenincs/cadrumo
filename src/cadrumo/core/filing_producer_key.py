"""Closed cross-layer identities for values supplied by a filing producer."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["FilingProducerKey"]


class FilingProducerKey(StrEnum):
    """Every non-derived value the filing export boundary may supply.

    The dotted values are semantic identities, not historical AEAT column
    spellings.  Registry TOML selects one of these identities; the application
    producer snapshot is the only runtime source of their values.
    """

    PRESENTER_TAX_ID = "presenter.tax_id"
    FILING_RESULT_DISPOSITION = "filing.result_disposition"
    TAXPAYER_TAX_ID = "taxpayer.tax_id"
    TAXPAYER_LEGAL_NAME = "taxpayer.legal_name"
    TAXPAYER_GIVEN_NAME = "taxpayer.given_name"
    TAXPAYER_SURNAMES = "taxpayer.surnames"
    TAXPAYER_FULL_NAME = "taxpayer.full_name"
    #: The "persona con quien relacionarse" AEAT reserves in the declarante
    #: header of every informativa (Modelo 180/190/270/349 positions 59-107,
    #: subdivided 59-67 telefono and 68-107 apellidos y nombre). This is the
    #: contact for the DECLARATION, which AEAT models separately from both the
    #: taxpayer and the presenter, so it is its own pair of identities rather
    #: than a reuse of either.
    CONTACT_PERSON_PHONE = "contact_person.phone"
    CONTACT_PERSON_NAME = "contact_person.full_name"
    #: Modelo 210 gives the contact block two phone slots and an email where the
    #: informativas give one phone, so the generic family gains the two it lacks
    #: rather than growing an `irnr.`-scoped duplicate of a cross-modelo concept.
    CONTACT_PERSON_SECONDARY_PHONE = "contact_person.secondary_phone"
    CONTACT_PERSON_EMAIL = "contact_person.email"
    #: Apellidos for a persona fisica, razon social for an entidad -- the ONE
    #: slot of a two-slot identity design. AEAT labels it "Apellidos o Razon
    #: Social" and pairs it with a separate "Nombre (solo personas fisicas)"
    #: slot, so neither existing key fits: `taxpayer.surnames` is None for an
    #: entity (Modelo 390 filed a blank OBLIGATORIO field for every company),
    #: `taxpayer.legal_name` is None for a natural person, and
    #: `taxpayer.full_name` would put "APELLIDOS NOMBRE" in a surnames-only slot
    #: and then repeat the nombre in the companion slot.
    TAXPAYER_SURNAMES_OR_LEGAL_NAME = "taxpayer.surnames_or_legal_name"
    AMENDMENT_IS_RECTIFICATIVA = "amendment_evidence.is_rectificativa"
    AMENDMENT_IS_COMPLEMENTARIA = "amendment_evidence.is_complementaria"
    #: One official slot holding "S" (sustitutiva), "C" (complementaria) or blank.
    #: It is ONE anchor deciding between two amendment kinds, so it cannot be the
    #: pair of booleans above: an export field resolves exactly one owner, and
    #: rendering "S" from `is_complementaria` being false would assert a
    #: substitution nobody declared.
    AMENDMENT_SUSTITUTIVA_OR_COMPLEMENTARIA_MARKER = "amendment_evidence.sustitutiva_or_complementaria_marker"
    #: The entidad desarrolladora (EEDD) identity block AEAT reserves at @93+4 and
    #: @101+9 of the auxiliary header, footnoted "A cumplimentar por las entidades
    #: desarrolladoras". Cadrumo IS the entidad desarrolladora, so these carry
    #: Cadrumo's own identity and no AEAT document can supply their values --
    #: which is why they are producer keys (the slot is named here; the value
    #: arrives from product identity at render time) rather than literals.
    ENTIDAD_DESARROLLADORA_VERSION_PROGRAMA = "entidad_desarrolladora.version_programa"
    ENTIDAD_DESARROLLADORA_TAX_ID = "entidad_desarrolladora.tax_id"
    AMENDMENT_ORIGINAL_AEAT_RECEIPT = "amendment_evidence.original_aeat_receipt"
    AMENDMENT_M303_MOTIVE_RECTIFICACIONES = "amendment_evidence.m303_motive.rectificaciones"
    AMENDMENT_M303_MOTIVE_DISCREPANCIA_CRITERIO_ADMINISTRATIVO = (
        "amendment_evidence.m303_motive.discrepancia_criterio_administrativo"
    )
    SELECTED_ACCOUNT_IBAN = "selected_account.iban"
    SELECTED_ACCOUNT_SWIFT_BIC = "selected_account.swift_bic"
    SELECTED_ACCOUNT_BANK_NAME = "selected_account.bank_name"
    SELECTED_ACCOUNT_BANK_ADDRESS = "selected_account.bank_address"
    SELECTED_ACCOUNT_BANK_CITY = "selected_account.bank_city"
    SELECTED_ACCOUNT_BANK_COUNTRY_CODE = "selected_account.bank_country_code"
    PRIOR_DOMICILIATION_ACTION = "prior_domiciliation.action"
    M303_REDEME_ENROLLED = "m303.redeme_enrolled"
    M303_EXCLUSIVELY_FORAL = "m303.tax_territory.exclusively_foral"
    M303_REGIME_COMPOSITION_CODE = "m303.regime_composition.official_code"
    M303_ANNUAL_VOLUME_NONZERO = "m303.annual_volume_nonzero"
    M303_JOINT_RETURN_ELECTED = "m303.joint_return_elected"
    M303_CASH_ACCOUNTING_REGIME_ENROLLED = "m303.cash_accounting_regime_enrolled"
    M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS = "m303.recipient_of_cash_accounting_operations"
    M303_PRORRATA_SPECIAL_OPTION = "m303.prorrata_special_option"
    M303_PRORRATA_SPECIAL_REVOCATION = "m303.prorrata_special_revocation"
    M303_INSOLVENCY_DECLARED = "m303.insolvency.declared"
    M303_INSOLVENCY_JUDICIAL_ORDER_DATE = "m303.insolvency.judicial_order_date"
    M303_INSOLVENCY_FILING_SUBTYPE = "m303.insolvency.filing_subtype"
    M303_VOLUNTARY_SII_ENROLLED = "m303.voluntary_sii_enrolled"
    M303_EXONERADO_390_APPLICABLE = "m303.exonerado_390_applicable"
    M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED = (
        "m303.hydrocarbon_deposit_advance_payment_deduction_entitled"
    )
    M111_COLEGIO_CONCERTADO = "m111.colegio_concertado"
    #: Modelo 360's solicitante: an empresario not established in the territory
    #: of application of the tax, asking to recover Spanish input VAT. Its address
    #: components are named from the ONE canonical vocabulary in
    #: `core.address_components`, which is what stops a second spelling of an
    #: AEAT component appearing beside the IRNR one.
    #:
    #: Deliberately NOT merged with `irnr.representante.domicilio.*`. AEAT asks
    #: Modelo 210 for the municipio's five-digit INE CODE and the provincia's
    #: two-digit code; it asks Modelo 360 for the municipio's NAME in thirty
    #: characters and the provincia as text. Thirteen components agree and two do
    #: not, so one shape's constraints are not a superset of the other's and a
    #: shared family would let a name reach a numeric slot.
    #: Modelo 360 datos bancarios. The IBAN and BIC reuse the generic
    #: `selected_account` family; only the account HOLDER facts, which that
    #: family has no member for, are minted here.
    M360_CUENTA_TITULAR_NOMBRE = "m360.cuenta.titular_nombre"
    M360_CUENTA_TITULAR_EN_CALIDAD_DE = "m360.cuenta.titular_en_calidad_de"
    M360_CUENTA_DIVISA = "m360.cuenta.divisa"
    M360_SOLICITANTE_TAX_ID = "m360.solicitante.tax_id"
    M360_SOLICITANTE_FULL_NAME = "m360.solicitante.full_name"
    M360_SOLICITANTE_EMAIL = "m360.solicitante.email"
    M360_SOLICITANTE_PHONE = "m360.solicitante.phone"
    M360_SOLICITANTE_DOMICILIO_TIPO_VIA = "m360.solicitante.domicilio.tipo_via"
    M360_SOLICITANTE_DOMICILIO_NOMBRE_VIA = "m360.solicitante.domicilio.nombre_via"
    M360_SOLICITANTE_DOMICILIO_TIPO_NUMERACION = "m360.solicitante.domicilio.tipo_numeracion"
    M360_SOLICITANTE_DOMICILIO_NUMERO_CASA = "m360.solicitante.domicilio.numero_casa"
    M360_SOLICITANTE_DOMICILIO_CALIFICADOR_NUMERO = "m360.solicitante.domicilio.calificador_numero"
    M360_SOLICITANTE_DOMICILIO_BLOQUE = "m360.solicitante.domicilio.bloque"
    M360_SOLICITANTE_DOMICILIO_PORTAL = "m360.solicitante.domicilio.portal"
    M360_SOLICITANTE_DOMICILIO_ESCALERA = "m360.solicitante.domicilio.escalera"
    M360_SOLICITANTE_DOMICILIO_PLANTA = "m360.solicitante.domicilio.planta"
    M360_SOLICITANTE_DOMICILIO_PUERTA = "m360.solicitante.domicilio.puerta"
    M360_SOLICITANTE_DOMICILIO_DATOS_COMPLEMENTARIOS = "m360.solicitante.domicilio.datos_complementarios"
    M360_SOLICITANTE_DOMICILIO_LOCALIDAD = "m360.solicitante.domicilio.localidad"
    M360_SOLICITANTE_DOMICILIO_CODIGO_POSTAL = "m360.solicitante.domicilio.codigo_postal"
    #: The NAME, not the INE code -- this is the axis on which Modelo 360 and
    #: Modelo 210 genuinely differ.
    M360_SOLICITANTE_DOMICILIO_NOMBRE_MUNICIPIO = "m360.solicitante.domicilio.nombre_municipio"
    M360_SOLICITANTE_DOMICILIO_PROVINCIA = "m360.solicitante.domicilio.provincia"
    M360_SOLICITANTE_FOREIGN_ADDRESS_STREET = "m360.solicitante.foreign_address.street"
    M360_SOLICITANTE_FOREIGN_ADDRESS_CITY = "m360.solicitante.foreign_address.city"
    M360_SOLICITANTE_FOREIGN_ADDRESS_POSTAL_CODE = "m360.solicitante.foreign_address.postal_code"
    M360_SOLICITANTE_FOREIGN_ADDRESS_REGION = "m360.solicitante.foreign_address.region"
    M360_SOLICITANTE_FOREIGN_ADDRESS_COUNTRY_CODE = "m360.solicitante.foreign_address.country_code"
    M360_REPRESENTANTE_FOREIGN_ADDRESS_STREET = "m360.representante.foreign_address.street"
    M360_REPRESENTANTE_FOREIGN_ADDRESS_CITY = "m360.representante.foreign_address.city"
    M360_REPRESENTANTE_FOREIGN_ADDRESS_POSTAL_CODE = "m360.representante.foreign_address.postal_code"
    M360_REPRESENTANTE_FOREIGN_ADDRESS_REGION = "m360.representante.foreign_address.region"
    M360_REPRESENTANTE_FOREIGN_ADDRESS_COUNTRY_CODE = "m360.representante.foreign_address.country_code"
    M360_REPRESENTANTE_APARTADO_CORREOS_NUMERO = "m360.representante.apartado_correos.numero"
    M360_REPRESENTANTE_APARTADO_CORREOS_LOCALIDAD = "m360.representante.apartado_correos.localidad"
    M360_REPRESENTANTE_APARTADO_CORREOS_CODIGO_POSTAL = "m360.representante.apartado_correos.codigo_postal"
    M360_REPRESENTANTE_APARTADO_CORREOS_NOMBRE_MUNICIPIO = "m360.representante.apartado_correos.nombre_municipio"
    M360_REPRESENTANTE_APARTADO_CORREOS_PROVINCIA = "m360.representante.apartado_correos.provincia"
    #: The representante the solicitante may appoint. Same party shape as the
    #: solicitante above and named from the same canonical vocabulary, because
    #: AEAT prints the two blocks identically -- identity, contact, Spanish
    #: address -- rather than because one was copied from the other.
    M360_REPRESENTANTE_TAX_ID = "m360.representante.tax_id"
    M360_REPRESENTANTE_FULL_NAME = "m360.representante.full_name"
    M360_REPRESENTANTE_EMAIL = "m360.representante.email"
    M360_REPRESENTANTE_PHONE = "m360.representante.phone"
    M360_REPRESENTANTE_DOMICILIO_TIPO_VIA = "m360.representante.domicilio.tipo_via"
    M360_REPRESENTANTE_DOMICILIO_NOMBRE_VIA = "m360.representante.domicilio.nombre_via"
    M360_REPRESENTANTE_DOMICILIO_TIPO_NUMERACION = "m360.representante.domicilio.tipo_numeracion"
    M360_REPRESENTANTE_DOMICILIO_NUMERO_CASA = "m360.representante.domicilio.numero_casa"
    M360_REPRESENTANTE_DOMICILIO_CALIFICADOR_NUMERO = "m360.representante.domicilio.calificador_numero"
    M360_REPRESENTANTE_DOMICILIO_BLOQUE = "m360.representante.domicilio.bloque"
    M360_REPRESENTANTE_DOMICILIO_PORTAL = "m360.representante.domicilio.portal"
    M360_REPRESENTANTE_DOMICILIO_ESCALERA = "m360.representante.domicilio.escalera"
    M360_REPRESENTANTE_DOMICILIO_PLANTA = "m360.representante.domicilio.planta"
    M360_REPRESENTANTE_DOMICILIO_PUERTA = "m360.representante.domicilio.puerta"
    M360_REPRESENTANTE_DOMICILIO_DATOS_COMPLEMENTARIOS = "m360.representante.domicilio.datos_complementarios"
    M360_REPRESENTANTE_DOMICILIO_LOCALIDAD = "m360.representante.domicilio.localidad"
    M360_REPRESENTANTE_DOMICILIO_CODIGO_POSTAL = "m360.representante.domicilio.codigo_postal"
    M360_REPRESENTANTE_DOMICILIO_NOMBRE_MUNICIPIO = "m360.representante.domicilio.nombre_municipio"
    M360_REPRESENTANTE_DOMICILIO_PROVINCIA = "m360.representante.domicilio.provincia"
    #: The apartado de correos AEAT offers as an ALTERNATIVE to the street
    #: address, not a component of it: it carries its own localidad, codigo
    #: postal, municipio and provincia, so it is its own scope rather than four
    #: more members inside `domicilio`.
    M360_SOLICITANTE_APARTADO_CORREOS_NUMERO = "m360.solicitante.apartado_correos.numero"
    M360_SOLICITANTE_APARTADO_CORREOS_LOCALIDAD = "m360.solicitante.apartado_correos.localidad"
    M360_SOLICITANTE_APARTADO_CORREOS_CODIGO_POSTAL = "m360.solicitante.apartado_correos.codigo_postal"
    M360_SOLICITANTE_APARTADO_CORREOS_NOMBRE_MUNICIPIO = "m360.solicitante.apartado_correos.nombre_municipio"
    M360_SOLICITANTE_APARTADO_CORREOS_PROVINCIA = "m360.solicitante.apartado_correos.provincia"
    #: Establishment facts that decide which administration handles the refund.
    M360_SOLICITANTE_ESTABLECIDO_EN_TAI = "m360.solicitante.establecido_en_tai"
    M360_SOLICITANTE_HACIENDA_FORAL = "m360.solicitante.hacienda_foral"
    M360_SOLICITANTE_DELEGACION_CANARIAS_CEUTA_MELILLA = "m360.solicitante.delegacion_canarias_ceuta_melilla"
    #: Header facts of the solicitud itself.
    M360_PAIS_DESTINO_SOLICITUD = "m360.solicitud.pais_destino"
    M360_CAUSA_PRESENTACION = "m360.solicitud.causa_presentacion"
    M360_COMUNICACION_PRORRATA_DEFINITIVA = "m360.solicitud.comunicacion_prorrata_definitiva"
    M360_NUMERO_REGISTRO_DECLARACION_ANTERIOR = "m360.solicitud.numero_registro_declaracion_anterior"
    M360_PRESENTACION_EN_PRUEBAS = "m360.solicitud.presentacion_en_pruebas"
    M360_NIVEL_CALIDAD_DATOS = "m360.solicitud.nivel_calidad_datos"
    #: Modelo 353 is the IVA group's aggregated autoliquidación, so its
    #: identification block asks facts about the GROUP that no per-taxpayer key
    #: can answer: which grupo the entidad dominante files for, whether the
    #: advanced regime of LIVA art. 163 sexies.cinco is elected, whether the
    #: group is enrolled in the monthly-refund register, and whether it is taxed
    #: under foral rules. `m303.*` counterparts exist for the single-filer forms
    #: and deliberately are not reused: the answers are group-scoped facts.
    M353_NUMERO_GRUPO = "m353.numero_grupo"
    M353_REGIMEN_ESPECIAL_AVANZADO_ELECTED = "m353.regimen_especial.avanzado_elected"
    M353_REGIMEN_ESPECIAL_INSCRITO_REDEME = "m353.regimen_especial.inscrito_redeme"
    M353_GRUPO_NORMATIVA_FORAL = "m353.grupo_normativa_foral"
    M353_SIN_ACTIVIDAD = "m353.sin_actividad"
    #: Modelo 202's identification block asks which Impuesto sobre Sociedades
    #: regime the entity files under, and the answer decides which of the form's
    #: two liquidation modalities applies and at what rate. None is a casilla:
    #: they are facts ABOUT the filer, carried in one-character slots AEAT marks
    #: "X o blanco" or with its own small enumerations, and no box number is
    #: printed beside any of them on the diseño.
    M202_CNAE_ACTIVIDAD_PRINCIPAL = "m202.cnae_actividad_principal"
    M202_REGIMEN_LEY_11_2009_SOCIMI = "m202.regimen.ley_11_2009_socimi"
    M202_REGIMEN_LEY_49_2002_SIN_FINES_LUCRATIVOS = "m202.regimen.ley_49_2002_sin_fines_lucrativos"
    M202_REGIMEN_ENTIDADES_NAVIERAS_TONELAJE = "m202.regimen.entidades_navieras_tonelaje"
    M202_REGIMEN_ARTICULO_101_LIS_REDUCIDA_DIMENSION = "m202.regimen.articulo_101_lis_reducida_dimension"
    M202_REGIMEN_ENTIDAD_CAPITAL_RIESGO = "m202.regimen.entidad_capital_riesgo"
    M202_CIFRA_NEGOCIOS_DOCE_MESES_UMBRAL = "m202.cifra_negocios_doce_meses_umbral"
    #: AEAT's own slot is "Cooperativa fiscalmente protegida u Otras entidades con
    #: posibilidad de aplicar dos tipos impositivos", one enumeration answering
    #: both. Naming it for the cooperativa alone would drop the half of the slot
    #: that decides whether a second tipo applies at all.
    M202_COOPERATIVA_O_MULTIPLES_TIPOS = "m202.cooperativa_o_multiples_tipos"
    #: The 2025 edition splits that one slot in two and adds a third: a low-cifra
    #: marker and a separate multiple-tipos marker beside the cooperativa flag.
    M202_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_BAJO_UMBRAL = "m202.cifra_negocios_periodo_anterior_bajo_umbral"
    M202_MULTIPLES_TIPOS_IMPOSITIVOS = "m202.multiples_tipos_impositivos"
    M202_COOPERATIVA_FISCALMENTE_PROTEGIDA = "m202.cooperativa_fiscalmente_protegida"
    M202_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES = "m202.tipo_gravamen_impuesto_sociedades"
    M202_IMPORTE_NETO_CIFRA_NEGOCIOS_TRAMO = "m202.importe_neto_cifra_negocios_tramo"
    M202_MARCA_INSTRUMENTAL = "m202.marca_instrumental"
    #: The slot AEAT prints for "Liquidación de modalidad A ó B", which selects
    #: which of the form's two liquidation blocks the filer completed. It is a
    #: discriminant, not a declared amount, and a negative filing depends on it.
    M202_DISCRIMINANTE_DECLARACION_NEGATIVA = "m202.discriminante_declaracion_negativa"
    M202_NORMATIVA_TERRITORIO_FORAL = "m202.normativa_territorio_foral"
    M202_COMUNICACION_DATOS_ADICIONALES = "m202.comunicacion_datos_adicionales"
    M202_NUMERO_REFERENCIA_SOCIEDADES = "m202.numero_referencia_sociedades"

    #: Modelo 222 is the CONSOLIDACION twin of modelo 202 -- same orden
    #: (HFP/227/2017), same liquidacion blocks -- so the facts its diseno declares
    #: are the group-level versions of 202's own and are named on that pattern.
    #: The dominante entity's identity and the group number have no 202
    #: counterpart because an individual filer has no dominante and no group.
    M222_NUMERO_GRUPO = "m222.numero_grupo"
    M222_REPRESENTANTE_O_DOMINANTE = "m222.representante_o_dominante"
    M222_NORMATIVA_TERRITORIO_FORAL = "m222.normativa_territorio_foral"
    M222_ENTIDAD_DOMINANTE_IDENTIFICACION = "m222.entidad_dominante_identificacion"
    M222_ENTIDAD_DOMINANTE_PAIS_TERRITORIO_FORAL = "m222.entidad_dominante_pais_territorio_foral"
    M222_ENTIDAD_DOMINANTE_RAZON_SOCIAL = "m222.entidad_dominante_razon_social"
    M222_FECHA_INICIO_PERIODO_IMPOSITIVO = "m222.fecha_inicio_periodo_impositivo"
    M222_CNAE_ACTIVIDAD_PRINCIPAL = "m222.cnae_actividad_principal"
    M222_REGIMEN_ENTIDADES_NAVIERAS_TONELAJE = "m222.regimen_entidades_navieras_tonelaje"
    M222_REGIMEN_REDUCIDA_DIMENSION = "m222.regimen_reducida_dimension"
    M222_CIFRA_NEGOCIOS_GRUPO_DOCE_MESES = "m222.cifra_negocios_grupo_doce_meses"
    M222_COOPERATIVA_FISCALMENTE_PROTEGIDA = "m222.cooperativa_fiscalmente_protegida"
    M222_REGIMEN_ENTIDADES_CAPITAL_RIESGO = "m222.regimen_entidades_capital_riesgo"
    M222_CIRCUNSTANCIA_CONCURRENTE = "m222.circunstancia_concurrente"
    M222_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_TRAMO = "m222.cifra_negocios_periodo_anterior_tramo"
    M222_MULTIPLES_TIPOS_IMPOSITIVOS = "m222.multiples_tipos_impositivos"
    M222_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES = "m222.tipo_gravamen_impuesto_sociedades"
    M222_IMPORTE_NETO_CIFRA_NEGOCIOS_TRAMO = "m222.importe_neto_cifra_negocios_tramo"
    M222_MODALIDAD_LIQUIDACION = "m222.modalidad_liquidacion"
    M222_COMUNICACION_DATOS_ADICIONALES = "m222.comunicacion_datos_adicionales"
    M222_NUMERO_REFERENCIA_SOCIEDADES = "m222.numero_referencia_sociedades"
    M222_COMUNICACION_VARIACION_COMPOSICION_GRUPO = "m222.comunicacion_variacion_composicion_grupo"
    M222_NUMERO_REFERENCIA_SOCIEDADES_VARIACION = "m222.numero_referencia_sociedades_variacion"
    #: IRNR party identities. Modelo 210 separates the person who FILES from the
    #: person the income belongs to, and records in which of six capacities the
    #: filer acts, so neither `taxpayer.*` nor `presenter.*` can carry these:
    #: collapsing them renders the wrong party's NIF with nothing able to refuse.
    #: Shared with the rest of the non-resident family (211/213/216), which uses
    #: the same party structure.
    IRNR_DECLARANTE_TAX_ID = "irnr.declarante.tax_id"
    IRNR_DECLARANTE_FULL_NAME = "irnr.declarante.full_name"
    #: Six INDEPENDENT one-character positions, not a coded axis -- AEAT publishes
    #: no code vocabulary for them, so each is its own flag.
    IRNR_DECLARANTE_CAPACITY_CONTRIBUYENTE = "irnr.declarante.capacity.contribuyente"
    IRNR_DECLARANTE_CAPACITY_REPRESENTANTE = "irnr.declarante.capacity.representante"
    IRNR_DECLARANTE_CAPACITY_PAGADOR = "irnr.declarante.capacity.pagador"
    IRNR_DECLARANTE_CAPACITY_DEPOSITARIO = "irnr.declarante.capacity.depositario"
    IRNR_DECLARANTE_CAPACITY_GESTOR = "irnr.declarante.capacity.gestor"
    IRNR_DECLARANTE_CAPACITY_RETENEDOR = "irnr.declarante.capacity.retenedor"
    IRNR_CONTRIBUYENTE_TAX_ID = "irnr.contribuyente.tax_id"
    IRNR_CONTRIBUYENTE_PERSON_TYPE = "irnr.contribuyente.person_type"
    IRNR_CONTRIBUYENTE_FULL_NAME = "irnr.contribuyente.full_name"
    IRNR_CONTRIBUYENTE_BIRTH_DATE = "irnr.contribuyente.birth_date"
    IRNR_CONTRIBUYENTE_BIRTH_CITY = "irnr.contribuyente.birth_city"
    IRNR_CONTRIBUYENTE_BIRTH_COUNTRY_CODE = "irnr.contribuyente.birth_country_code"
    IRNR_CONTRIBUYENTE_TAX_RESIDENCE_COUNTRY_CODE = "irnr.contribuyente.tax_residence_country_code"
    IRNR_CONTRIBUYENTE_FOREIGN_TAX_ID = "irnr.contribuyente.foreign_tax_id"
    #: FOREIGN residence, deliberately its own component vocabulary. It carries a
    #: free-text ZIP and a province/region/state NAME where the Spanish-coded
    #: `domicilio`/`situacion` vocabulary below carries a five-digit codigo postal,
    #: a two-digit codigo provincia and an INE municipal code. The Spanish shape's
    #: constraints are not a superset of this one's, so the two must not merge.
    IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_STREET = "irnr.contribuyente.foreign_address.street"
    IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_COMPLEMENT = "irnr.contribuyente.foreign_address.complement"
    IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_CITY = "irnr.contribuyente.foreign_address.city"
    IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_EMAIL = "irnr.contribuyente.foreign_address.email"
    IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_POSTAL_CODE = "irnr.contribuyente.foreign_address.postal_code"
    IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_REGION = "irnr.contribuyente.foreign_address.region"
    IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_COUNTRY_CODE = "irnr.contribuyente.foreign_address.country_code"
    IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_PHONE = "irnr.contribuyente.foreign_address.phone"
    IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_MOBILE_PHONE = "irnr.contribuyente.foreign_address.mobile_phone"
    IRNR_CONTRIBUYENTE_FOREIGN_ADDRESS_FAX = "irnr.contribuyente.foreign_address.fax"
    IRNR_REPRESENTANTE_TAX_ID = "irnr.representante.tax_id"
    IRNR_REPRESENTANTE_PERSON_TYPE = "irnr.representante.person_type"
    IRNR_REPRESENTANTE_FULL_NAME = "irnr.representante.full_name"
    IRNR_REPRESENTANTE_APPOINTMENT_KIND = "irnr.representante.appointment_kind"
    IRNR_REPRESENTANTE_PHONE = "irnr.representante.phone"
    IRNR_REPRESENTANTE_MOBILE_PHONE = "irnr.representante.mobile_phone"
    IRNR_REPRESENTANTE_FAX = "irnr.representante.fax"
    #: Spanish-coded address vocabulary, declared once per party that uses it.
    #: Component names are AEAT's own, not invented. The same fifteen components
    #: recur under `irnr.inmueble.situacion.*`; they are NOT shared members,
    #: because one addresses a person and the other a property, and the semantic
    #: map's anchor-to-owner bijection is what proves each anchor reached the
    #: right one.
    IRNR_REPRESENTANTE_DOMICILIO_TIPO_VIA = "irnr.representante.domicilio.tipo_via"
    IRNR_REPRESENTANTE_DOMICILIO_NOMBRE_VIA = "irnr.representante.domicilio.nombre_via"
    IRNR_REPRESENTANTE_DOMICILIO_TIPO_NUMERACION = "irnr.representante.domicilio.tipo_numeracion"
    IRNR_REPRESENTANTE_DOMICILIO_NUMERO_CASA = "irnr.representante.domicilio.numero_casa"
    IRNR_REPRESENTANTE_DOMICILIO_CALIFICADOR_NUMERO = "irnr.representante.domicilio.calificador_numero"
    IRNR_REPRESENTANTE_DOMICILIO_BLOQUE = "irnr.representante.domicilio.bloque"
    IRNR_REPRESENTANTE_DOMICILIO_PORTAL = "irnr.representante.domicilio.portal"
    IRNR_REPRESENTANTE_DOMICILIO_ESCALERA = "irnr.representante.domicilio.escalera"
    IRNR_REPRESENTANTE_DOMICILIO_PLANTA = "irnr.representante.domicilio.planta"
    IRNR_REPRESENTANTE_DOMICILIO_PUERTA = "irnr.representante.domicilio.puerta"
    IRNR_REPRESENTANTE_DOMICILIO_DATOS_COMPLEMENTARIOS = "irnr.representante.domicilio.datos_complementarios"
    IRNR_REPRESENTANTE_DOMICILIO_LOCALIDAD = "irnr.representante.domicilio.localidad"
    IRNR_REPRESENTANTE_DOMICILIO_CODIGO_POSTAL = "irnr.representante.domicilio.codigo_postal"
    IRNR_REPRESENTANTE_DOMICILIO_CODIGO_INE_MUNICIPIO = "irnr.representante.domicilio.codigo_ine_municipio"
    IRNR_REPRESENTANTE_DOMICILIO_CODIGO_PROVINCIA = "irnr.representante.domicilio.codigo_provincia"
    #: One party in the official design ("Pagador/Retenedor/Emisor/Adquiriente del
    #: inmueble"), which AEAT selects by renta type rather than splitting into
    #: four slots, so it is one scope here too.
    IRNR_PAGADOR_TAX_ID = "irnr.pagador.tax_id"
    IRNR_PAGADOR_PERSON_TYPE = "irnr.pagador.person_type"
    IRNR_PAGADOR_FULL_NAME = "irnr.pagador.full_name"
    IRNR_INMUEBLE_SITUACION_TIPO_VIA = "irnr.inmueble.situacion.tipo_via"
    IRNR_INMUEBLE_SITUACION_NOMBRE_VIA = "irnr.inmueble.situacion.nombre_via"
    IRNR_INMUEBLE_SITUACION_TIPO_NUMERACION = "irnr.inmueble.situacion.tipo_numeracion"
    IRNR_INMUEBLE_SITUACION_NUMERO_CASA = "irnr.inmueble.situacion.numero_casa"
    IRNR_INMUEBLE_SITUACION_CALIFICADOR_NUMERO = "irnr.inmueble.situacion.calificador_numero"
    IRNR_INMUEBLE_SITUACION_BLOQUE = "irnr.inmueble.situacion.bloque"
    IRNR_INMUEBLE_SITUACION_PORTAL = "irnr.inmueble.situacion.portal"
    IRNR_INMUEBLE_SITUACION_ESCALERA = "irnr.inmueble.situacion.escalera"
    IRNR_INMUEBLE_SITUACION_PLANTA = "irnr.inmueble.situacion.planta"
    IRNR_INMUEBLE_SITUACION_PUERTA = "irnr.inmueble.situacion.puerta"
    IRNR_INMUEBLE_SITUACION_DATOS_COMPLEMENTARIOS = "irnr.inmueble.situacion.datos_complementarios"
    IRNR_INMUEBLE_SITUACION_LOCALIDAD = "irnr.inmueble.situacion.localidad"
    IRNR_INMUEBLE_SITUACION_CODIGO_POSTAL = "irnr.inmueble.situacion.codigo_postal"
    IRNR_INMUEBLE_SITUACION_CODIGO_INE_MUNICIPIO = "irnr.inmueble.situacion.codigo_ine_municipio"
    IRNR_INMUEBLE_SITUACION_CODIGO_PROVINCIA = "irnr.inmueble.situacion.codigo_provincia"
    IRNR_INMUEBLE_REFERENCIA_CATASTRAL = "irnr.inmueble.referencia_catastral"
    #: Form-level facts that are not party data and not a casilla.
    IRNR_DECLARACION_TIPO = "irnr.declaracion.tipo"
    IRNR_DEVENGO_AGRUPACION = "irnr.devengo.agrupacion"
    IRNR_DEVENGO_FECHA_DEVENGO = "irnr.devengo.fecha_devengo"
    IRNR_RENTA_CLAVE_DIVISA = "irnr.renta.clave_divisa"
    #: Modelo 210 H (ganancias patrimoniales derivadas de inmuebles). These sit
    #: inside the Determinación de la base imponible block but carry no printed
    #: casilla number, so they are operator facts rather than casilla values.
    IRNR_GANANCIA_INMOBILIARIA_TITULARIDAD = "irnr.ganancia_inmobiliaria.titularidad"
    IRNR_GANANCIA_INMOBILIARIA_CUOTA_PARTICIPACION_CONTRIBUYENTE = (
        "irnr.ganancia_inmobiliaria.cuota_participacion_contribuyente"
    )
    IRNR_GANANCIA_INMOBILIARIA_CUOTA_PARTICIPACION_CONYUGE = "irnr.ganancia_inmobiliaria.cuota_participacion_conyuge"
    IRNR_GANANCIA_INMOBILIARIA_CONYUGE_TAX_ID = "irnr.ganancia_inmobiliaria.conyuge_tax_id"
    IRNR_GANANCIA_INMOBILIARIA_CONYUGE_FULL_NAME = "irnr.ganancia_inmobiliaria.conyuge_full_name"
    IRNR_GANANCIA_INMOBILIARIA_FECHA_ADQUISICION = "irnr.ganancia_inmobiliaria.fecha_adquisicion"
    IRNR_GANANCIA_INMOBILIARIA_FECHA_MEJORA = "irnr.ganancia_inmobiliaria.fecha_mejora"
    IRNR_GANANCIA_INMOBILIARIA_JUSTIFICANTE_MODELO_211 = "irnr.ganancia_inmobiliaria.justificante_modelo_211"
    #: The ingreso/devolución document (Página 02) carries TWO independent
    #: accounts. They are separate scopes, not one reused account, because the
    #: design declares each with its own holder and its own UE/SEPA versus
    #: resto-países branch, and merging them would let a refund be paid to the
    #: account a charge was taken from with nothing able to refuse.
    IRNR_INGRESO_FORMA_PAGO = "irnr.ingreso.forma_pago"
    IRNR_INGRESO_CUENTA_TITULAR_TAX_ID = "irnr.ingreso.cuenta.titular_tax_id"
    IRNR_INGRESO_CUENTA_TITULAR_FULL_NAME = "irnr.ingreso.cuenta.titular_full_name"
    IRNR_INGRESO_CUENTA_SEPA_IBAN = "irnr.ingreso.cuenta.sepa_iban"
    IRNR_INGRESO_CUENTA_SEPA_SWIFT_BIC = "irnr.ingreso.cuenta.sepa_swift_bic"
    IRNR_INGRESO_CUENTA_RESTO_SWIFT_BIC = "irnr.ingreso.cuenta.resto_swift_bic"
    IRNR_INGRESO_CUENTA_RESTO_NUMERO_CUENTA = "irnr.ingreso.cuenta.resto_numero_cuenta"
    IRNR_INGRESO_CUENTA_RESTO_BANCO = "irnr.ingreso.cuenta.resto_banco"
    IRNR_INGRESO_CUENTA_RESTO_DIRECCION_BANCO = "irnr.ingreso.cuenta.resto_direccion_banco"
    IRNR_INGRESO_CUENTA_RESTO_CIUDAD = "irnr.ingreso.cuenta.resto_ciudad"
    IRNR_INGRESO_CUENTA_RESTO_CODIGO_PAIS = "irnr.ingreso.cuenta.resto_codigo_pais"
    IRNR_DEVOLUCION_RENUNCIA_A_FAVOR_DEL_TESORO = "irnr.devolucion.renuncia_a_favor_del_tesoro"
    IRNR_DEVOLUCION_CUENTA_TITULAR_TAX_ID = "irnr.devolucion.cuenta.titular_tax_id"
    IRNR_DEVOLUCION_CUENTA_TITULAR_FULL_NAME = "irnr.devolucion.cuenta.titular_full_name"
    IRNR_DEVOLUCION_CUENTA_SEPA_IBAN = "irnr.devolucion.cuenta.sepa_iban"
    IRNR_DEVOLUCION_CUENTA_SEPA_SWIFT_BIC = "irnr.devolucion.cuenta.sepa_swift_bic"
    IRNR_DEVOLUCION_CUENTA_RESTO_SWIFT_BIC = "irnr.devolucion.cuenta.resto_swift_bic"
    IRNR_DEVOLUCION_CUENTA_RESTO_NUMERO_CUENTA = "irnr.devolucion.cuenta.resto_numero_cuenta"
    IRNR_DEVOLUCION_CUENTA_RESTO_BANCO = "irnr.devolucion.cuenta.resto_banco"
    IRNR_DEVOLUCION_CUENTA_RESTO_DIRECCION_BANCO = "irnr.devolucion.cuenta.resto_direccion_banco"
    IRNR_DEVOLUCION_CUENTA_RESTO_CIUDAD = "irnr.devolucion.cuenta.resto_ciudad"
    IRNR_DEVOLUCION_CUENTA_RESTO_CODIGO_PAIS = "irnr.devolucion.cuenta.resto_codigo_pais"
    IRNR_SIN_INGRESO_NI_DEVOLUCION_CUOTA_CERO = "irnr.sin_ingreso_ni_devolucion.cuota_cero"
    #: Modelo 200 header facts. Each is a field the 2025 diseño prints in its
    #: own right -- the ejercicio and periodo it repeats outside the envelope
    #: tag, the periodo impositivo start and end components, the regime and
    #: comunicacion markers -- and each name derives from AEAT's printed
    #: description rather than being invented. Declared here and referenced from
    #: the modelo's map exactly as the m202., m360. and irnr. families are: 200
    #: of the 238 keys this enum already carried are resolved by no runtime
    #: producer, so declaring a key is the registry half of the contract and
    #: wiring its supply is a separate, later concern.
    M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO = "m200.6_deduc_evitar_doble_imposicion_participacio"
    M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_2 = "m200.6_deduc_evitar_doble_imposicion_participacio_2"
    M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_3 = "m200.6_deduc_evitar_doble_imposicion_participacio_3"
    M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_4 = "m200.6_deduc_evitar_doble_imposicion_participacio_4"
    M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_5 = "m200.6_deduc_evitar_doble_imposicion_participacio_5"
    M200_6_DEDUC_EVITAR_DOBLE_IMPOSICION_PARTICIPACIO_6 = "m200.6_deduc_evitar_doble_imposicion_participacio_6"
    M200_ABONO_COMPENSACION_ABONO_POR_CONVERSION_DE_A = "m200.abono_compensacion_abono_por_conversion_de_a"
    M200_ABONO_COMPENSACION_COMPENSACION_POR_CONVERSI = "m200.abono_compensacion_compensacion_por_conversi"
    M200_APELLIDOS_Y_NOMBRE = "m200.apellidos_y_nombre"
    M200_B_2_SUMA_DE_PORCENTAJES_DE_PARTICIPACION_DE = "m200.b_2_suma_de_porcentajes_de_participacion_de"
    M200_B_2_SUMA_DE_PORCENTAJES_DE_PARTICIPACIONES_E = "m200.b_2_suma_de_porcentajes_de_participaciones_e"
    M200_BALANCE_0_NO_CONSTA_1_MOD_NORMAL_2_MOD_ABREV = "m200.balance_0_no_consta_1_mod_normal_2_mod_abrev"
    M200_CODIGO_CNAE_2025_ACTIVIDAD_PRINCIPAL = "m200.codigo_cnae_2025_actividad_principal"
    M200_CODIGO_PAIS_COUNTRY_CODE = "m200.codigo_pais_country_code"
    M200_COMO_CONSECUENCIA_DE_LA_PRESENTACION_DE_LA_A = "m200.como_consecuencia_de_la_presentacion_de_la_a"
    M200_CUENTA_BANCARIA_BANCO_BANK_NAME = "m200.cuenta_bancaria_banco_bank_name"
    M200_CUENTA_BANCARIA_CIUDAD_CITY = "m200.cuenta_bancaria_ciudad_city"
    M200_CUENTA_BANCARIA_CODIGO_SWIFT_BIC = "m200.cuenta_bancaria_codigo_swift_bic"
    M200_CUENTA_BANCARIA_MARCA_SEPA = "m200.cuenta_bancaria_marca_sepa"
    M200_CUENTA_CORRIENTE_TRIBUTARIA = "m200.cuenta_corriente_tributaria"
    M200_DATOS_DE_LA_SOCIEDAD_MATRIZ_ULTIMA_NIF = "m200.datos_de_la_sociedad_matriz_ultima_nif"
    M200_DATOS_DE_LA_SOCIEDAD_MATRIZ_ULTIMA_NOMBRE_DE = "m200.datos_de_la_sociedad_matriz_ultima_nombre_de"
    M200_DATOS_DE_LA_SOCIEDAD_MATRIZ_ULTIMA_RAZON_SOC = "m200.datos_de_la_sociedad_matriz_ultima_razon_soc"
    M200_DEDUCCION_RESTO_DEL_GRUPO = "m200.deduccion_resto_del_grupo"
    M200_DEDUCCION_RESTO_DEL_GRUPO_10 = "m200.deduccion_resto_del_grupo_10"
    M200_DEDUCCION_RESTO_DEL_GRUPO_11 = "m200.deduccion_resto_del_grupo_11"
    M200_DEDUCCION_RESTO_DEL_GRUPO_12 = "m200.deduccion_resto_del_grupo_12"
    M200_DEDUCCION_RESTO_DEL_GRUPO_13 = "m200.deduccion_resto_del_grupo_13"
    M200_DEDUCCION_RESTO_DEL_GRUPO_14 = "m200.deduccion_resto_del_grupo_14"
    M200_DEDUCCION_RESTO_DEL_GRUPO_15 = "m200.deduccion_resto_del_grupo_15"
    M200_DEDUCCION_RESTO_DEL_GRUPO_16 = "m200.deduccion_resto_del_grupo_16"
    M200_DEDUCCION_RESTO_DEL_GRUPO_17 = "m200.deduccion_resto_del_grupo_17"
    M200_DEDUCCION_RESTO_DEL_GRUPO_18 = "m200.deduccion_resto_del_grupo_18"
    M200_DEDUCCION_RESTO_DEL_GRUPO_19 = "m200.deduccion_resto_del_grupo_19"
    M200_DEDUCCION_RESTO_DEL_GRUPO_2 = "m200.deduccion_resto_del_grupo_2"
    M200_DEDUCCION_RESTO_DEL_GRUPO_20 = "m200.deduccion_resto_del_grupo_20"
    M200_DEDUCCION_RESTO_DEL_GRUPO_21 = "m200.deduccion_resto_del_grupo_21"
    M200_DEDUCCION_RESTO_DEL_GRUPO_22 = "m200.deduccion_resto_del_grupo_22"
    M200_DEDUCCION_RESTO_DEL_GRUPO_23 = "m200.deduccion_resto_del_grupo_23"
    M200_DEDUCCION_RESTO_DEL_GRUPO_24 = "m200.deduccion_resto_del_grupo_24"
    M200_DEDUCCION_RESTO_DEL_GRUPO_25 = "m200.deduccion_resto_del_grupo_25"
    M200_DEDUCCION_RESTO_DEL_GRUPO_26 = "m200.deduccion_resto_del_grupo_26"
    M200_DEDUCCION_RESTO_DEL_GRUPO_3 = "m200.deduccion_resto_del_grupo_3"
    M200_DEDUCCION_RESTO_DEL_GRUPO_4 = "m200.deduccion_resto_del_grupo_4"
    M200_DEDUCCION_RESTO_DEL_GRUPO_5 = "m200.deduccion_resto_del_grupo_5"
    M200_DEDUCCION_RESTO_DEL_GRUPO_6 = "m200.deduccion_resto_del_grupo_6"
    M200_DEDUCCION_RESTO_DEL_GRUPO_7 = "m200.deduccion_resto_del_grupo_7"
    M200_DEDUCCION_RESTO_DEL_GRUPO_8 = "m200.deduccion_resto_del_grupo_8"
    M200_DEDUCCION_RESTO_DEL_GRUPO_9 = "m200.deduccion_resto_del_grupo_9"
    M200_DIRECCION_DE_CORREO_ELECTRONICO_PARA_INCIDEN = "m200.direccion_de_correo_electronico_para_inciden"
    M200_DIRECCION_DEL_BANCO_BANK_ADDRESS = "m200.direccion_del_banco_bank_address"
    M200_ECPN_0_NO_CONSTA_1_MOD_NORMAL_2_MOD_ABREVIAD = "m200.ecpn_0_no_consta_1_mod_normal_2_mod_abreviad"
    M200_EJERCICIO = "m200.ejercicio"
    M200_ENTIDAD_CUYO_IMPORTE_NETO_DE_LA_CIFRA_DE_NEG = "m200.entidad_cuyo_importe_neto_de_la_cifra_de_neg"
    M200_ENTIDAD_SIN_OBLIGACION_DE_IDENTIFICAR_EL_TIT = "m200.entidad_sin_obligacion_de_identificar_el_tit"
    M200_F_IDENTIFICACION_DEL_TITULAR_REAL_DE_LA_ENTI = "m200.f_identificacion_del_titular_real_de_la_enti"
    M200_FECHA_DE_NACIMIENTO = "m200.fecha_de_nacimiento"
    M200_IDENTIFICACION_EJERCICIO = "m200.identificacion_ejercicio"
    M200_IDENTIFICACION_TIPO_DE_EJERCICIO = "m200.identificacion_tipo_de_ejercicio"
    M200_IDENTIFICADOR_CLIENTE_EEDD_RESERVADO_PARA_LA = "m200.identificador_cliente_eedd_reservado_para_la"
    M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO = "m200.identificador_de_fin_de_registro"
    M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_2 = "m200.identificador_de_fin_de_registro_2"
    M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_3 = "m200.identificador_de_fin_de_registro_3"
    M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_4 = "m200.identificador_de_fin_de_registro_4"
    M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_5 = "m200.identificador_de_fin_de_registro_5"
    M200_IDENTIFICADOR_DE_FIN_DE_REGISTRO_6 = "m200.identificador_de_fin_de_registro_6"
    M200_IMPORTE_A_DEVOLVER = "m200.importe_a_devolver"
    M200_IMPORTE_A_INGRESAR = "m200.importe_a_ingresar"
    M200_IMPORTE_NETO_DE_LA_CIFRA_DE_NEGOCIOS_DE_LOS = "m200.importe_neto_de_la_cifra_de_negocios_de_los"
    M200_IMPORTE_NETO_DE_LA_CIFRA_DE_NEGOCIOS_DE_LOS_2 = "m200.importe_neto_de_la_cifra_de_negocios_de_los_2"
    M200_IMPORTE_NETO_DE_LA_CIFRA_DE_NEGOCIOS_DE_LOS_3 = "m200.importe_neto_de_la_cifra_de_negocios_de_los_3"
    M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG = "m200.informacion_adicional_producciones_cinematog"
    M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_2 = "m200.informacion_adicional_producciones_cinematog_2"
    M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_3 = "m200.informacion_adicional_producciones_cinematog_3"
    M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_4 = "m200.informacion_adicional_producciones_cinematog_4"
    M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_5 = "m200.informacion_adicional_producciones_cinematog_5"
    M200_INFORMACION_ADICIONAL_PRODUCCIONES_CINEMATOG_6 = "m200.informacion_adicional_producciones_cinematog_6"
    M200_INOPERATIVIDAD_DEL_ORDEN_DE_CUMPLIMENTACION = "m200.inoperatividad_del_orden_de_cumplimentacion"
    M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS = "m200.inversiones_en_producciones_cinematograficas"
    M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_2 = "m200.inversiones_en_producciones_cinematograficas_2"
    M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_3 = "m200.inversiones_en_producciones_cinematograficas_3"
    M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_4 = "m200.inversiones_en_producciones_cinematograficas_4"
    M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_5 = "m200.inversiones_en_producciones_cinematograficas_5"
    M200_INVERSIONES_EN_PRODUCCIONES_CINEMATOGRAFICAS_6 = "m200.inversiones_en_producciones_cinematograficas_6"
    M200_MODALIDAD_DE_INGRESO_UNO_DE_LOS_SIGUIENTES_V = "m200.modalidad_de_ingreso_uno_de_los_siguientes_v"
    M200_MODELO_DE_ESTADOS_CONTABLES_QUE_SE_VA_A_CUMP = "m200.modelo_de_estados_contables_que_se_va_a_cump"
    M200_N_I_F_DE_LA_SOCIEDAD_REPRESENTANTE_DOMINANTE = "m200.n_i_f_de_la_sociedad_representante_dominante"
    M200_NIF_CODIGO_DE_IDENTIFICACION_EXTRANJERO = "m200.nif_codigo_de_identificacion_extranjero"
    M200_NIF_EN_EL_PAIS_DE_RESIDENCIA_TIN = "m200.nif_en_el_pais_de_residencia_tin"
    M200_NO_IDENTIFICACION_DE_LA_SOCIEDAD_DOMINANTE_E = "m200.no_identificacion_de_la_sociedad_dominante_e"
    M200_NO_RESIDENTES_MAS_DE_UN_ESTABLECIMIENTO_PERM = "m200.no_residentes_mas_de_un_establecimiento_perm"
    M200_NOMBRE_Y_APELLIDOS_DE_LA_PERSONA_DE_CONTACTO = "m200.nombre_y_apellidos_de_la_persona_de_contacto"
    M200_NUMERO_DE_CUENTA_IBAN = "m200.numero_de_cuenta_iban"
    M200_NUMERO_DE_CUENTA_IBAN_2 = "m200.numero_de_cuenta_iban_2"
    M200_NUMERO_DE_PERIODO_IMPOSITIVO = "m200.numero_de_periodo_impositivo"
    M200_PAIS_DE_EXPEDICION_DEL_DOCUMENTO_DE_IDENTIFI = "m200.pais_de_expedicion_del_documento_de_identifi"
    M200_PAIS_DE_RESIDENCIA = "m200.pais_de_residencia"
    M200_PAIS_DE_RESIDENCIA_2 = "m200.pais_de_residencia_2"
    M200_PARTE_DE_LA_BASE_IMPONIBLE_DEL_PERIODO_IMPOS = "m200.parte_de_la_base_imponible_del_periodo_impos"
    M200_PARTE_DE_LA_BASE_IMPONIBLE_DEL_PERIODO_IMPOS_2 = "m200.parte_de_la_base_imponible_del_periodo_impos_2"
    M200_PERDIDAS_Y_GANANCIAS_0_NO_CONSTA_1_MOD_NORMA = "m200.perdidas_y_ganancias_0_no_consta_1_mod_norma"
    M200_PERIODO = "m200.periodo"
    M200_PERIODO_IMPOSITIVO = "m200.periodo_impositivo"
    M200_PERIODO_IMPOSITIVO_ANO_FINAL = "m200.periodo_impositivo_ano_final"
    M200_PERIODO_IMPOSITIVO_ANO_INICIO = "m200.periodo_impositivo_ano_inicio"
    M200_PERIODO_IMPOSITIVO_DIA_FINAL = "m200.periodo_impositivo_dia_final"
    M200_PERIODO_IMPOSITIVO_DIA_INICIO = "m200.periodo_impositivo_dia_inicio"
    M200_PERIODO_IMPOSITIVO_FIN_ANO = "m200.periodo_impositivo_fin_ano"
    M200_PERIODO_IMPOSITIVO_FIN_DIA = "m200.periodo_impositivo_fin_dia"
    M200_PERIODO_IMPOSITIVO_FIN_MES = "m200.periodo_impositivo_fin_mes"
    M200_PERIODO_IMPOSITIVO_INICIO_ANO = "m200.periodo_impositivo_inicio_ano"
    M200_PERIODO_IMPOSITIVO_INICIO_DIA = "m200.periodo_impositivo_inicio_dia"
    M200_PERIODO_IMPOSITIVO_INICIO_MES = "m200.periodo_impositivo_inicio_mes"
    M200_PERIODO_IMPOSITIVO_MES_FINAL = "m200.periodo_impositivo_mes_final"
    M200_PERIODO_IMPOSITIVO_MES_INICIO = "m200.periodo_impositivo_mes_inicio"
    M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S = "m200.presentacion_de_documentacion_previa_en_la_s"
    M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_2 = "m200.presentacion_de_documentacion_previa_en_la_s_2"
    M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_3 = "m200.presentacion_de_documentacion_previa_en_la_s_3"
    M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_4 = "m200.presentacion_de_documentacion_previa_en_la_s_4"
    M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_5 = "m200.presentacion_de_documentacion_previa_en_la_s_5"
    M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_6 = "m200.presentacion_de_documentacion_previa_en_la_s_6"
    M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_7 = "m200.presentacion_de_documentacion_previa_en_la_s_7"
    M200_PRESENTACION_DE_DOCUMENTACION_PREVIA_EN_LA_S_8 = "m200.presentacion_de_documentacion_previa_en_la_s_8"
    M200_REALIZA_ACTIVIDADES_AGRICOLAS_Y_O_GANADERAS = "m200.realiza_actividades_agricolas_y_o_ganaderas"
    M200_REG_ENTIDADES_NAVIERAS_EN_FUNCION_DEL_TONELA = "m200.reg_entidades_navieras_en_funcion_del_tonela"
    M200_RENUNCIA_O_POR_TRANSFERENCIA = "m200.renuncia_o_por_transferencia"
    M200_RESERVADO_PARA_LA_A_E_A_T_DEJAR_EN_BLANCO_IN = "m200.reservado_para_la_a_e_a_t_dejar_en_blanco_in"
    M200_RESULTADO_A_INGRESAR_CORRESPONDIENTE_A_LA_AN = "m200.resultado_a_ingresar_correspondiente_a_la_an"
    M200_RESULTADO_A_INGRESAR_CORRESPONDIENTE_A_LA_AN_2 = "m200.resultado_a_ingresar_correspondiente_a_la_an_2"
    M200_RESULTADO_CERO = "m200.resultado_cero"
    M200_SELLO_ELECTRONICO_RESERVADO_PARA_LA_A_E_A_T = "m200.sello_electronico_reservado_para_la_a_e_a_t"
    M200_SOCIMIS_REGIMEN_FISCAL_DE_ENTRADA_SALIDA_REN = "m200.socimis_regimen_fiscal_de_entrada_salida_ren"
    M200_TIPO_DE_DECLARACION_VER_NOTA = "m200.tipo_de_declaracion_ver_nota"
    M200_TIPO_DE_EJERCICIO = "m200.tipo_de_ejercicio"
    M200_TIPO_DOCUMENTO_IDENTIFICATIVO = "m200.tipo_documento_identificativo"

    # Modelo 296's IRNR retenciones design. Its revision declares three casillas
    # -- the resumen base, retenciones and total -- so nearly every wire slot is a
    # header fact rather than a casilla reference, which is why this family is
    # large next to the modelo's casilla count.
    M296_ANA_APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO = "m296.ana.apellidos_y_nombre_razon_social_o_deno"
    M296_ANA_APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO_2 = "m296.ana.apellidos_y_nombre_razon_social_o_deno_2"
    M296_ANA_CIUDAD = "m296.ana.ciudad"
    M296_ANA_CLAVE_DE_PERSONALIDAD_DEL_CONTRIBUYENT = "m296.ana.clave_de_personalidad_del_contribuyent"
    M296_ANA_CODIGO_ISIN = "m296.ana.codigo_isin"
    M296_ANA_CODIGO_LEI_DEL_CONTRIBUYENTE = "m296.ana.codigo_lei_del_contribuyente"
    M296_ANA_CODIGO_PAIS = "m296.ana.codigo_pais"
    M296_ANA_DIRECCION_DEL_CONTRIBUYENTE = "m296.ana.direccion_del_contribuyente"
    M296_ANA_EJERCICIO = "m296.ana.ejercicio"
    M296_ANA_F_J = "m296.ana.f_j"
    M296_ANA_FECHA_DE_DEVENGO = "m296.ana.fecha_de_devengo"
    M296_ANA_FECHA_DE_NACIMIENTO_DEL_CONTRIBUYENTE = "m296.ana.fecha_de_nacimiento_del_contribuyente"
    M296_ANA_IDENTIFICADOR_DE_REGISTRO_O_NUMERO_DE = "m296.ana.identificador_de_registro_o_numero_de"
    M296_ANA_IMPORTE_DEL_PAGO_AL_CONTRIBUYENTE = "m296.ana.importe_del_pago_al_contribuyente"
    M296_ANA_NIF_DEL_CONTRIBUYENTE = "m296.ana.nif_del_contribuyente"
    M296_ANA_NIF_DEL_DECLARANTE = "m296.ana.nif_del_declarante"
    M296_ANA_NIF_DEL_PERCEPTOR = "m296.ana.nif_del_perceptor"
    M296_ANA_NIF_DEL_REPRESENTANTE_LEGAL = "m296.ana.nif_del_representante_legal"
    M296_ANA_NIF_EN_EL_PAIS_DE_RESIDENCIA_FISCAL_DE = "m296.ana.nif_en_el_pais_de_residencia_fiscal_de"
    M296_ANA_NUMERO_DE_JUSTIFICANTE_DEL_MODELO_210 = "m296.ana.numero_de_justificante_del_modelo_210"
    M296_ANA_PAIS_O_TERRITORIO_DE_RESIDENCIA_FISCAL = "m296.ana.pais_o_territorio_de_residencia_fiscal"
    M296_ANA_PORCENTAJE_DE_RETENCION = "m296.ana.porcentaje_de_retencion"
    M296_ANA_RETENCIONES = "m296.ana.retenciones"
    M296_ANB_APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO = "m296.anb.apellidos_y_nombre_razon_social_o_deno"
    M296_ANB_APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO_2 = "m296.anb.apellidos_y_nombre_razon_social_o_deno_2"
    M296_ANB_CODIGO_CUENTA_VALORES_DEL_CERTIFICADO = "m296.anb.codigo_cuenta_valores_del_certificado"
    M296_ANB_CODIGO_ISIN_DEL_CERTIFICADO = "m296.anb.codigo_isin_del_certificado"
    M296_ANB_CODIGO_LEI_DEL_TITULAR_REGISTRAL = "m296.anb.codigo_lei_del_titular_registral"
    M296_ANB_DECIMAL = "m296.anb.decimal"
    M296_ANB_DECIMAL_2 = "m296.anb.decimal_2"
    M296_ANB_DECIMAL_3 = "m296.anb.decimal_3"
    M296_ANB_EJERCICIO = "m296.anb.ejercicio"
    M296_ANB_ENTERO = "m296.anb.entero"
    M296_ANB_ENTERO_2 = "m296.anb.entero_2"
    M296_ANB_ENTERO_3 = "m296.anb.entero_3"
    M296_ANB_F_J = "m296.anb.f_j"
    M296_ANB_FECHA_DE_PAGO = "m296.anb.fecha_de_pago"
    M296_ANB_FECHA_DE_PRESENTACION_DEL_MODELO_210 = "m296.anb.fecha_de_presentacion_del_modelo_210"
    M296_ANB_IDENTIFICADOR_DE_REGISTRO_O_NUMERO_DE = "m296.anb.identificador_de_registro_o_numero_de"
    M296_ANB_NIF_DEL_DECLARANTE = "m296.anb.nif_del_declarante"
    M296_ANB_NIF_DEL_PERCEPTOR = "m296.anb.nif_del_perceptor"
    M296_ANB_NIF_DEL_REPRESENTANTE_LEGAL = "m296.anb.nif_del_representante_legal"
    M296_ANB_NUMERO_DE_JUSTIFICANTE_DEL_MODELO_210 = "m296.anb.numero_de_justificante_del_modelo_210"
    M296_ANB_PARTE_DECIMAL_DEL_NUMERO_DE_TITULOS = "m296.anb.parte_decimal_del_numero_de_titulos"
    M296_ANB_PARTE_DECIMAL_DEL_NUMERO_DE_TITULOS_2 = "m296.anb.parte_decimal_del_numero_de_titulos_2"
    M296_ANB_PARTE_ENTERA_DEL_NUMERO_DE_TITULOS = "m296.anb.parte_entera_del_numero_de_titulos"
    M296_ANB_PARTE_ENTERA_DEL_NUMERO_DE_TITULOS_2 = "m296.anb.parte_entera_del_numero_de_titulos_2"
    M296_ANB_TITULAR_REGISTRAL_DE_LA_CUENTA_DE_VALO = "m296.anb.titular_registral_de_la_cuenta_de_valo"
    M296_DEC_APELLIDOS_Y_NOMBRE = "m296.dec.apellidos_y_nombre"
    M296_DEC_APELLIDOS_Y_NOMBRE_O_RAZON_SOCIAL_DEL = "m296.dec.apellidos_y_nombre_o_razon_social_del"
    M296_DEC_DECLARACION_COMPLEMENTARIA_O_SUSTITUTI = "m296.dec.declaracion_complementaria_o_sustituti"
    M296_DEC_EJERCICIO = "m296.dec.ejercicio"
    M296_DEC_N = "m296.dec.n"
    M296_DEC_NIF_DEL_DECLARANTE = "m296.dec.nif_del_declarante"
    M296_DEC_NUMERO_IDENTIFICATIVO_DE_LA_DECLARACIO = "m296.dec.numero_identificativo_de_la_declaracio"
    M296_DEC_NUMERO_IDENTIFICATIVO_DE_LA_DECLARACIO_2 = "m296.dec.numero_identificativo_de_la_declaracio_2"
    M296_DEC_NUMERO_TOTAL_DE_PERCEPTORES = "m296.dec.numero_total_de_perceptores"
    M296_DEC_SELLO_ELECTRONICO = "m296.dec.sello_electronico"
    M296_DEC_TELEFONO = "m296.dec.telefono"
    M296_DEC_TIPO_DE_SOPORTE = "m296.dec.tipo_de_soporte"
    M296_PER_APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO = "m296.per.apellidos_y_nombre_razon_social_o_deno"
    M296_PER_BASE_RETENCIONES_E_INGRESOS_A_CUENTA = "m296.per.base_retenciones_e_ingresos_a_cuenta"
    M296_PER_CIUDAD = "m296.per.ciudad"
    M296_PER_CLAVE = "m296.per.clave"
    M296_PER_CLAVE_DE_MERCADO = "m296.per.clave_de_mercado"
    M296_PER_CODIGO = "m296.per.codigo"
    M296_PER_CODIGO_BIC_DEL_PERCEPTOR_MEDIADOR = "m296.per.codigo_bic_del_perceptor_mediador"
    M296_PER_CODIGO_CUENTA_VALORES = "m296.per.codigo_cuenta_valores"
    M296_PER_CODIGO_EMISOR = "m296.per.codigo_emisor"
    M296_PER_CODIGO_LEI_DEL_PERCEPTOR = "m296.per.codigo_lei_del_perceptor"
    M296_PER_CODIGO_PAIS = "m296.per.codigo_pais"
    M296_PER_DECIMAL = "m296.per.decimal"
    M296_PER_DECIMAL_NUMERICO_PARTE_DECIMAL = "m296.per.decimal_numerico_parte_decimal"
    M296_PER_DECIMAL_NUMERICO_PARTE_DECIMAL_2 = "m296.per.decimal_numerico_parte_decimal_2"
    M296_PER_DECIMAL_NUMERICO_PARTE_DECIMAL_3 = "m296.per.decimal_numerico_parte_decimal_3"
    M296_PER_DECLARANTE = "m296.per.declarante"
    M296_PER_DIRECCION_DEL_PERCEPTOR = "m296.per.direccion_del_perceptor"
    M296_PER_EJERCICIO = "m296.per.ejercicio"
    M296_PER_EJERCICIO_DEVENGO = "m296.per.ejercicio_devengo"
    M296_PER_ENTERO = "m296.per.entero"
    M296_PER_ENTERO_NUMERICO_PARTE_ENTERA = "m296.per.entero_numerico_parte_entera"
    M296_PER_ENTERO_NUMERICO_PARTE_ENTERA_2 = "m296.per.entero_numerico_parte_entera_2"
    M296_PER_ENTERO_NUMERICO_PARTE_ENTERA_3 = "m296.per.entero_numerico_parte_entera_3"
    M296_PER_F_J = "m296.per.f_j"
    M296_PER_FECHA_DE_DEVENGO = "m296.per.fecha_de_devengo"
    M296_PER_FECHA_DE_INICIO_DEL_PRESTAMO = "m296.per.fecha_de_inicio_del_prestamo"
    M296_PER_FECHA_DE_NACIMIENTO = "m296.per.fecha_de_nacimiento"
    M296_PER_FECHA_DE_VENCIMIENTO_DEL_PRESTAMO = "m296.per.fecha_de_vencimiento_del_prestamo"
    M296_PER_IDENTIFICADOR_DE_REGISTRO_O_NUMERO_DE = "m296.per.identificador_de_registro_o_numero_de"
    M296_PER_INGRESOS_A_CUENTA_REPERCUTIDOS = "m296.per.ingresos_a_cuenta_repercutidos"
    M296_PER_NATURALEZA = "m296.per.naturaleza"
    M296_PER_NIF_DEL_DECLARANTE = "m296.per.nif_del_declarante"
    M296_PER_NIF_DEL_PAGADOR_ANTERIOR = "m296.per.nif_del_pagador_anterior"
    M296_PER_NIF_DEL_PERCEPTOR = "m296.per.nif_del_perceptor"
    M296_PER_NIF_DEL_REPRESENTANTE_LEGAL = "m296.per.nif_del_representante_legal"
    M296_PER_NIF_EN_EL_PAIS_DE_RESIDENCIA_FISCAL = "m296.per.nif_en_el_pais_de_residencia_fiscal"
    M296_PER_PAIS_O_TERRITORIO_DE_RESIDENCIA_FISCAL = "m296.per.pais_o_territorio_de_residencia_fiscal"
    M296_PER_PARTE_DECIMAL_DEL_IMPORTE_DE_LAS_RETEN = "m296.per.parte_decimal_del_importe_de_las_reten"
    M296_PER_PARTE_ENTERA_DEL_IMPORTE_DE_LAS_RETENC = "m296.per.parte_entera_del_importe_de_las_retenc"
    M296_PER_PENDIENTE = "m296.per.pendiente"
    M296_PER_PERCEPTOR_MEDIADOR = "m296.per.perceptor_mediador"
    M296_PER_PROCEDIMIENTO_ESPECIAL_DE_RETENCIONES = "m296.per.procedimiento_especial_de_retenciones"
    M296_PER_SUBCLAVE = "m296.per.subclave"
    M296_PER_TIPO_CODIGO = "m296.per.tipo_codigo"
    M296_PIN_APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO = "m296.pin.apellidos_y_nombre_razon_social_o_deno"
    M296_PIN_EJERCICIO = "m296.pin.ejercicio"
    M296_PIN_F_J = "m296.pin.f_j"
    M296_PIN_IDENTIFICADOR_DE_REGISTRO_O_NUMERO_DE = "m296.pin.identificador_de_registro_o_numero_de"
    M296_PIN_NIF_DEL_DECLARANTE = "m296.pin.nif_del_declarante"
    M296_PIN_NIF_DEL_PERCEPTOR = "m296.pin.nif_del_perceptor"
    M296_PIN_NIF_DEL_REPRESENTANTE_LEGAL = "m296.pin.nif_del_representante_legal"
    M296_PIN_RETENCIONES_E_INGRESOS_A_CUENTA_INGRES = "m296.pin.retenciones_e_ingresos_a_cuenta_ingres"

    # Modelo 840 (IAE). Every identity below is TRANSCRIBED from the field text of
    # the bundled diseño (Orden HAC/2572/2003), apartado and block included. AEAT's
    # own labels for the local grid say only Total / Rectificada / Computable without
    # naming the magnitude, so these keys say the same rather than asserting a
    # surface figure the document does not state. The relación de locales repeats
    # nine times in the Anexo record; nine repeats of one local are one identity.
    #: Delegación. Tabla.
    M840_DELEGACION_CODIGO = "m840.delegacion_codigo"
    #: Administración. Tabla.
    M840_ADMINISTRACION_CODIGO = "m840.administracion_codigo"
    #: Apart. I: Datos ident. del sujeto pasivo. Municipio
    M840_SUJETO_PASIVO_MUNICIPIO = "m840.sujeto_pasivo.municipio"
    #: Apart. III: Representante. Municipio.
    M840_REPRESENTANTE_MUNICIPIO = "m840.representante.municipio"
    #: Apart. IV: Datos de la act. Provincial (provincia) Tabla
    M840_ACTIVIDAD_PROVINCIA_CODIGO = "m840.actividad.provincia_codigo"
    #: Apart. IV: Datos de la act. Municipio
    M840_ACTIVIDAD_MUNICIPIO = "m840.actividad.municipio"
    #: Apart. V: Local afecto indirectamente a la act. Municipio
    M840_LOCAL_INDIRECTO_MUNICIPIO = "m840.local_indirecto.municipio"
    #: Apartado II: Relación de locales. SG Tabla
    M840_LOCALES_SG_TABLA = "m840.locales.sg_tabla"
    #: Apartado II: Relación de locales. Nombre de la vía pública
    M840_LOCALES_NOMBRE_VIA = "m840.locales.nombre_via"
    #: Apartado II: Relación de locales. Núm.
    M840_LOCALES_NUMERO = "m840.locales.numero"
    #: Apartado II: Relación de locales. Km.
    M840_LOCALES_KM = "m840.locales.km"
    #: Apartado II: Relación de locales. Esc.
    M840_LOCALES_ESCALERA = "m840.locales.escalera"
    #: Apartado II: Relación de locales. Piso
    M840_LOCALES_PISO = "m840.locales.piso"
    #: Apartado II: Relación de locales. Pta.
    M840_LOCALES_PUERTA = "m840.locales.puerta"
    #: Apartado II: Relación de locales. Cód. Postal
    M840_LOCALES_CODIGO_POSTAL = "m840.locales.codigo_postal"
    #: Apartado II: Relación de locales. Provincia Tabla
    M840_LOCALES_PROVINCIA_CODIGO = "m840.locales.provincia_codigo"
    #: Apartado II: Relación de locales. Municipio Tabla
    M840_LOCALES_MUNICIPIO_CODIGO = "m840.locales.municipio_codigo"
    #: Apartado II: Relación de locales. Municipio
    M840_LOCALES_MUNICIPIO_NOMBRE = "m840.locales.municipio_nombre"
    #: Apartado II: Relación de locales. Total
    M840_LOCALES_TOTAL = "m840.locales.total"
    #: Apartado II: Relación de locales. Rectificada
    M840_LOCALES_RECTIFICADA = "m840.locales.rectificada"
    #: Apartado II: Relación de locales. Computable
    M840_LOCALES_COMPUTABLE = "m840.locales.computable"
    #: Apartado VI: Elem. Trib. del grupo o epígrafe. A) 1. Código
    M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A1_CODIGO = "m840.elementos_tributarios.grupo.a1.codigo"
    #: Apartado VI: Elem. Trib. del grupo o epígrafe. A) 1. Número
    M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A1_NUMERO = "m840.elementos_tributarios.grupo.a1.numero"
    #: Apartado VI: Elem. Trib. del grupo o epígrafe. A) 2. Código
    M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A2_CODIGO = "m840.elementos_tributarios.grupo.a2.codigo"
    #: Apartado VI: Elem. Trib. del grupo o epígrafe. A) 2. Número
    M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A2_NUMERO = "m840.elementos_tributarios.grupo.a2.numero"
    #: Apartado VI: Elem. Trib. del grupo o epígrafe. A) 3. Código
    M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A3_CODIGO = "m840.elementos_tributarios.grupo.a3.codigo"
    #: Apartado VI: Elem. Trib. del grupo o epígrafe. A) 3. Número
    M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A3_NUMERO = "m840.elementos_tributarios.grupo.a3.numero"
    #: Apartado VI: Elem. Trib. del grupo o epígrafe. A) 4. Código
    M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A4_CODIGO = "m840.elementos_tributarios.grupo.a4.codigo"
    #: Apartado VI: Elem. Trib. del grupo o epígrafe. A) 4. Número
    M840_ELEMENTOS_TRIBUTARIOS_GRUPO_A4_NUMERO = "m840.elementos_tributarios.grupo.a4.numero"
    #: Apartado VI: Máquinas recreativas Tipo A. Número
    M840_ELEMENTOS_TRIBUTARIOS_MAQUINAS_TIPO_A_NUMERO = "m840.elementos_tributarios.maquinas_tipo_a.numero"
    #: Apartado VI: Máquinas recreativas Tipo B. Número
    M840_ELEMENTOS_TRIBUTARIOS_MAQUINAS_TIPO_B_NUMERO = "m840.elementos_tributarios.maquinas_tipo_b.numero"
    #: Apartado VI: Expositores para autoventa. Número
    M840_ELEMENTOS_TRIBUTARIOS_EXPOSITORES_AUTOVENTA_NUMERO = "m840.elementos_tributarios.expositores_autoventa.numero"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 0.1. Total
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C0_1_TOTAL = "m840.elementos_tributarios.local.c0_1.total"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 0.1. Rectificada
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C0_1_RECTIFICADA = "m840.elementos_tributarios.local.c0_1.rectificada"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 0.1. Computable
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C0_1_COMPUTABLE = "m840.elementos_tributarios.local.c0_1.computable"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 0.2. Total
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C0_2_TOTAL = "m840.elementos_tributarios.local.c0_2.total"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 0.2. Rectificada
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C0_2_RECTIFICADA = "m840.elementos_tributarios.local.c0_2.rectificada"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 0.2. Computable
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C0_2_COMPUTABLE = "m840.elementos_tributarios.local.c0_2.computable"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 1.1. Total
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C1_1_TOTAL = "m840.elementos_tributarios.local.c1_1.total"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 1.1. Rectificada
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C1_1_RECTIFICADA = "m840.elementos_tributarios.local.c1_1.rectificada"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 1.1. Computable
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C1_1_COMPUTABLE = "m840.elementos_tributarios.local.c1_1.computable"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 1.2. Total
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C1_2_TOTAL = "m840.elementos_tributarios.local.c1_2.total"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 1.2. Rectificada
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C1_2_RECTIFICADA = "m840.elementos_tributarios.local.c1_2.rectificada"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 1.2. Computable
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C1_2_COMPUTABLE = "m840.elementos_tributarios.local.c1_2.computable"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 1.3. Total
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C1_3_TOTAL = "m840.elementos_tributarios.local.c1_3.total"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 1.3. Rectificada
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C1_3_RECTIFICADA = "m840.elementos_tributarios.local.c1_3.rectificada"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 1.3. Computable
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C1_3_COMPUTABLE = "m840.elementos_tributarios.local.c1_3.computable"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 2.0. Total
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C2_0_TOTAL = "m840.elementos_tributarios.local.c2_0.total"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 2.0. Rectificada
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C2_0_RECTIFICADA = "m840.elementos_tributarios.local.c2_0.rectificada"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 2.0. Computable
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C2_0_COMPUTABLE = "m840.elementos_tributarios.local.c2_0.computable"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 3.1. Total
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C3_1_TOTAL = "m840.elementos_tributarios.local.c3_1.total"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 3.1. Rectificada
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C3_1_RECTIFICADA = "m840.elementos_tributarios.local.c3_1.rectificada"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 3.1. Computable
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C3_1_COMPUTABLE = "m840.elementos_tributarios.local.c3_1.computable"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 3.2. Total
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C3_2_TOTAL = "m840.elementos_tributarios.local.c3_2.total"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 3.2. Rectificada
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C3_2_RECTIFICADA = "m840.elementos_tributarios.local.c3_2.rectificada"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 3.2. Computable
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C3_2_COMPUTABLE = "m840.elementos_tributarios.local.c3_2.computable"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 4.0. Total
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C4_0_TOTAL = "m840.elementos_tributarios.local.c4_0.total"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 4.0. Rectificada
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C4_0_RECTIFICADA = "m840.elementos_tributarios.local.c4_0.rectificada"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 4.0. Computable
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C4_0_COMPUTABLE = "m840.elementos_tributarios.local.c4_0.computable"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 5.0. Total
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C5_0_TOTAL = "m840.elementos_tributarios.local.c5_0.total"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 5.0. Rectificada
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C5_0_RECTIFICADA = "m840.elementos_tributarios.local.c5_0.rectificada"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 5.0. Computable
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C5_0_COMPUTABLE = "m840.elementos_tributarios.local.c5_0.computable"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 6.0. Total
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C6_0_TOTAL = "m840.elementos_tributarios.local.c6_0.total"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 6.0. Rectificada
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C6_0_RECTIFICADA = "m840.elementos_tributarios.local.c6_0.rectificada"
    #: Apartado VI: Elem. Trib. Local (Cuota municipal). C) 6.0. Computable
    M840_ELEMENTOS_TRIBUTARIOS_LOCAL_C6_0_COMPUTABLE = "m840.elementos_tributarios.local.c6_0.computable"
