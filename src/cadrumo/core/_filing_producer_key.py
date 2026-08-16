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
    #: `core._address_components`, which is what stops a second spelling of an
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
