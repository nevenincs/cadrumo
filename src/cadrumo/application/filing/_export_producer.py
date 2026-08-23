"""Producer-value projection for the declaration export renderer."""

from __future__ import annotations

from dataclasses import dataclass

from ...core import FilingProducerKey, Period, PriorDomiciliationElection, ProrrataEspecialTransitionKind
from ...domain.deadlines import M303RegimeComposition, M303TaxTerritory, ModeloIVAProfile
from ...domain.filing import FilingExportValidationError
from ...domain.iva import is_last_filing_period_of_year
from ...domain.modelos import M303RectificativaMotive
from ._producer_snapshot import (
    AmendmentEvidence,
    ChargeAccountSelection,
    FilingModelProfileFacts,
    FilingProducerSnapshot,
    M303FilingFacts,
    M303InsolvencyFilingSubtype,
    Modelo111ProfileFacts,
    Modelo222ProfileFacts,
    Modelo353ProfileFacts,
    RefundAccountSelection,
)


@dataclass(frozen=True)
class SelectedAccountLexicals:
    iban: str | None = None
    swift_bic: str | None = None
    bank_name: str | None = None
    bank_address: str | None = None
    bank_city: str | None = None
    bank_country_code: str | None = None


@dataclass(frozen=True)
class M303ProfileLexicals:
    redeme_enrolled: str | None = None
    exclusively_foral: str | None = None
    regime_composition_code: str | None = None
    cash_accounting_regime_enrolled: str | None = None
    voluntary_sii_enrolled: str | None = None
    hydrocarbon_deposit_advance_payment_deduction_entitled: str | None = None
    is_foral: bool = False


@dataclass(frozen=True)
class M303FilingLexicals:
    joint_return_elected: str | None = None
    annual_volume_nonzero: str | None = None
    recipient_of_cash_accounting_operations: str | None = None
    prorrata_special_option: str | None = None
    prorrata_special_revocation: str | None = None
    insolvency_declared: str | None = None
    insolvency_judicial_order_date: str | None = None
    insolvency_filing_subtype: str | None = None
    exonerado_390_applicable: str | None = None
    prorrata_transition_applicable: bool = False


@dataclass(frozen=True)
class M303ForalLexicals:
    prorrata_special_option: str | None
    prorrata_special_revocation: str | None


_MODELO_PRODUCER_NAMESPACE_OWNERS = {
    "amendment_evidence": "modelo_specific_amendment",
    "contact_person": "modelo_specific_contact",
    "entidad_desarrolladora": "product_software_identity",
    "irnr": "modelo_210",
    "m111": "modelo_111",
    "m200": "modelo_200",
    "m202": "modelo_202",
    "m222": "modelo_222",
    "m296": "modelo_296",
    "m303": "modelo_303",
    "m353": "modelo_353",
    "m360": "modelo_360",
    "m840": "modelo_840",
    "presenter": "modelo_specific_presenter",
    "filing": "modelo_specific_filing",
    "prior_domiciliation": "modelo_specific_domiciliation",
    "selected_account": "modelo_specific_account",
    "taxpayer": "modelo_specific_taxpayer",
}


def filing_producer_ownership() -> dict[FilingProducerKey, str]:
    """Return the exhaustive owner dispatch for the closed producer vocabulary."""
    shared = {
        FilingProducerKey.PRESENTER_TAX_ID,
        FilingProducerKey.FILING_RESULT_DISPOSITION,
        FilingProducerKey.TAXPAYER_TAX_ID,
        FilingProducerKey.TAXPAYER_LEGAL_NAME,
        FilingProducerKey.TAXPAYER_GIVEN_NAME,
        FilingProducerKey.TAXPAYER_SURNAMES,
        FilingProducerKey.TAXPAYER_FULL_NAME,
        FilingProducerKey.TAXPAYER_SURNAMES_OR_LEGAL_NAME,
        FilingProducerKey.CONTACT_PERSON_PHONE,
        FilingProducerKey.CONTACT_PERSON_NAME,
        FilingProducerKey.AMENDMENT_IS_RECTIFICATIVA,
        FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA,
        FilingProducerKey.AMENDMENT_ORIGINAL_AEAT_RECEIPT,
        FilingProducerKey.AMENDMENT_SUSTITUTIVA_OR_COMPLEMENTARIA_MARKER,
        FilingProducerKey.AMENDMENT_M303_MOTIVE_RECTIFICACIONES,
        FilingProducerKey.AMENDMENT_M303_MOTIVE_DISCREPANCIA_CRITERIO_ADMINISTRATIVO,
        FilingProducerKey.SELECTED_ACCOUNT_IBAN,
        FilingProducerKey.SELECTED_ACCOUNT_SWIFT_BIC,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_NAME,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_ADDRESS,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_CITY,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_COUNTRY_CODE,
        FilingProducerKey.PRIOR_DOMICILIATION_ACTION,
        FilingProducerKey.M303_REDEME_ENROLLED,
        FilingProducerKey.M303_EXCLUSIVELY_FORAL,
        FilingProducerKey.M303_REGIME_COMPOSITION_CODE,
        FilingProducerKey.M303_ANNUAL_VOLUME_NONZERO,
        FilingProducerKey.M303_JOINT_RETURN_ELECTED,
        FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED,
        FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS,
        FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION,
        FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION,
        FilingProducerKey.M303_INSOLVENCY_DECLARED,
        FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE,
        FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE,
        FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED,
        FilingProducerKey.M303_EXONERADO_390_APPLICABLE,
        FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED,
        FilingProducerKey.M111_COLEGIO_CONCERTADO,
        FilingProducerKey.M222_NUMERO_GRUPO,
        FilingProducerKey.M222_REPRESENTANTE_O_DOMINANTE,
        FilingProducerKey.M222_NORMATIVA_TERRITORIO_FORAL,
        FilingProducerKey.M222_ENTIDAD_DOMINANTE_IDENTIFICACION,
        FilingProducerKey.M222_ENTIDAD_DOMINANTE_PAIS_TERRITORIO_FORAL,
        FilingProducerKey.M222_ENTIDAD_DOMINANTE_RAZON_SOCIAL,
        FilingProducerKey.M222_FECHA_INICIO_PERIODO_IMPOSITIVO,
        FilingProducerKey.M222_CNAE_ACTIVIDAD_PRINCIPAL,
        FilingProducerKey.M222_REGIMEN_ENTIDADES_NAVIERAS_TONELAJE,
        FilingProducerKey.M222_REGIMEN_REDUCIDA_DIMENSION,
        FilingProducerKey.M222_CIFRA_NEGOCIOS_GRUPO_DOCE_MESES,
        FilingProducerKey.M222_COOPERATIVA_FISCALMENTE_PROTEGIDA,
        FilingProducerKey.M222_REGIMEN_ENTIDADES_CAPITAL_RIESGO,
        FilingProducerKey.M222_CIRCUNSTANCIA_CONCURRENTE,
        FilingProducerKey.M222_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_TRAMO,
        FilingProducerKey.M222_MULTIPLES_TIPOS_IMPOSITIVOS,
        FilingProducerKey.M222_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES,
        FilingProducerKey.M222_IMPORTE_NETO_CIFRA_NEGOCIOS_TRAMO,
        FilingProducerKey.M222_MODALIDAD_LIQUIDACION,
        FilingProducerKey.M222_COMUNICACION_DATOS_ADICIONALES,
        FilingProducerKey.M222_NUMERO_REFERENCIA_SOCIEDADES,
        FilingProducerKey.M222_COMUNICACION_VARIACION_COMPOSICION_GRUPO,
        FilingProducerKey.M222_NUMERO_REFERENCIA_SOCIEDADES_VARIACION,
        FilingProducerKey.M353_NUMERO_GRUPO,
        FilingProducerKey.M353_REGIMEN_ESPECIAL_AVANZADO_ELECTED,
        FilingProducerKey.M353_REGIMEN_ESPECIAL_INSCRITO_REDEME,
        FilingProducerKey.M353_SIN_ACTIVIDAD,
        FilingProducerKey.M353_GRUPO_NORMATIVA_FORAL,
    }
    owners = {key: "shared_snapshot" for key in shared}
    for key in FilingProducerKey:
        if key in owners:
            continue
        namespace = key.value.partition(".")[0]
        owner = _MODELO_PRODUCER_NAMESPACE_OWNERS.get(namespace)
        if owner is None:
            raise FilingExportValidationError(f"filing producer key {key.value!r} has no declared owner")
        owners[key] = owner
    return owners


_M222_FIELD_BY_KEY: dict[FilingProducerKey, str] = {
    FilingProducerKey.M222_NUMERO_GRUPO: "numero_grupo",
    FilingProducerKey.M222_REPRESENTANTE_O_DOMINANTE: "representante_o_dominante",
    FilingProducerKey.M222_NORMATIVA_TERRITORIO_FORAL: "normativa_territorio_foral",
    FilingProducerKey.M222_ENTIDAD_DOMINANTE_IDENTIFICACION: "entidad_dominante_identificacion",
    FilingProducerKey.M222_ENTIDAD_DOMINANTE_PAIS_TERRITORIO_FORAL: "entidad_dominante_pais_territorio_foral",
    FilingProducerKey.M222_ENTIDAD_DOMINANTE_RAZON_SOCIAL: "entidad_dominante_razon_social",
    FilingProducerKey.M222_FECHA_INICIO_PERIODO_IMPOSITIVO: "fecha_inicio_periodo_impositivo",
    FilingProducerKey.M222_CNAE_ACTIVIDAD_PRINCIPAL: "cnae_actividad_principal",
    FilingProducerKey.M222_REGIMEN_ENTIDADES_NAVIERAS_TONELAJE: "regimen_entidades_navieras_tonelaje",
    FilingProducerKey.M222_REGIMEN_REDUCIDA_DIMENSION: "regimen_reducida_dimension",
    FilingProducerKey.M222_CIFRA_NEGOCIOS_GRUPO_DOCE_MESES: "cifra_negocios_grupo_doce_meses",
    FilingProducerKey.M222_COOPERATIVA_FISCALMENTE_PROTEGIDA: "cooperativa_fiscalmente_protegida",
    FilingProducerKey.M222_REGIMEN_ENTIDADES_CAPITAL_RIESGO: "regimen_entidades_capital_riesgo",
    FilingProducerKey.M222_CIRCUNSTANCIA_CONCURRENTE: "circunstancia_concurrente",
    FilingProducerKey.M222_CIFRA_NEGOCIOS_PERIODO_ANTERIOR_TRAMO: "cifra_negocios_periodo_anterior_tramo",
    FilingProducerKey.M222_MULTIPLES_TIPOS_IMPOSITIVOS: "multiples_tipos_impositivos",
    FilingProducerKey.M222_TIPO_GRAVAMEN_IMPUESTO_SOCIEDADES: "tipo_gravamen_impuesto_sociedades",
    FilingProducerKey.M222_IMPORTE_NETO_CIFRA_NEGOCIOS_TRAMO: "importe_neto_cifra_negocios_tramo",
    FilingProducerKey.M222_MODALIDAD_LIQUIDACION: "modalidad_liquidacion",
    FilingProducerKey.M222_COMUNICACION_DATOS_ADICIONALES: "comunicacion_datos_adicionales",
    FilingProducerKey.M222_NUMERO_REFERENCIA_SOCIEDADES: "numero_referencia_sociedades",
    FilingProducerKey.M222_COMUNICACION_VARIACION_COMPOSICION_GRUPO: "comunicacion_variacion_composicion_grupo",
    FilingProducerKey.M222_NUMERO_REFERENCIA_SOCIEDADES_VARIACION: "numero_referencia_sociedades_variacion",
}


def m222_producer_values(model_profile: FilingModelProfileFacts) -> dict[FilingProducerKey, object]:
    """Resolve the grupo-fiscal producer identities Modelo 222's layout cites.

    Every one of these keys was declared in the vocabulary and produced by nothing, so the
    layout's twenty-three header fields -- numero de grupo and entidad dominante among
    them -- rendered blank on a return that exists to identify a fiscal group.

    A profile of the wrong type yields every key as ``None`` rather than raising: this
    resolver runs for every modelo, and only Modelo 222's snapshot validator may decide
    that a 222 filing without group facts is invalid.
    """
    profile = model_profile if isinstance(model_profile, Modelo222ProfileFacts) else None
    return {
        key: (getattr(profile, field) if profile is not None else None) for key, field in _M222_FIELD_BY_KEY.items()
    }


_M353_FIELD_BY_KEY: dict[FilingProducerKey, str] = {
    FilingProducerKey.M353_NUMERO_GRUPO: "numero_grupo",
    FilingProducerKey.M353_REGIMEN_ESPECIAL_AVANZADO_ELECTED: "regimen_especial_avanzado_elected",
    FilingProducerKey.M353_REGIMEN_ESPECIAL_INSCRITO_REDEME: "regimen_especial_inscrito_redeme",
    FilingProducerKey.M353_SIN_ACTIVIDAD: "sin_actividad",
    FilingProducerKey.M353_GRUPO_NORMATIVA_FORAL: "grupo_normativa_foral",
}


def m353_producer_values(model_profile: FilingModelProfileFacts) -> dict[FilingProducerKey, object]:
    """Resolve the grupo de entidades producer identities Modelo 353's layout cites.

    All five ``m353.*`` keys were declared in the vocabulary and produced by nothing, so
    the número de grupo at offset 109 and the sin-actividad and normativa-foral marks
    rendered blank on the aggregate return of a régimen especial del grupo de entidades.

    A profile of the wrong type yields every key as ``None`` rather than raising: this
    resolver runs for every modelo, and only Modelo 353's snapshot validator may decide
    that a 353 filing without group facts is invalid.
    """
    profile = model_profile if isinstance(model_profile, Modelo353ProfileFacts) else None
    return {
        key: (getattr(profile, field) if profile is not None else None) for key, field in _M353_FIELD_BY_KEY.items()
    }


def filing_producer_values(snapshot: FilingProducerSnapshot) -> dict[FilingProducerKey, object]:
    """Resolve every canonical producer identity from one immutable snapshot."""
    identity = snapshot.taxpayer_identity
    amendment = snapshot.amendment_evidence
    account = selected_account_lexicals(snapshot)
    iva_profile = snapshot.model_profile if isinstance(snapshot.model_profile, ModeloIVAProfile) else None
    m303_profile = m303_profile_lexicals(iva_profile, snapshot.m303_filing_facts)
    m303_filing = m303_filing_lexicals(snapshot.m303_filing_facts)
    m303_motive = m303_rectificativa_motive_producer_values(amendment)
    values: dict[FilingProducerKey, object] = {
        FilingProducerKey.PRESENTER_TAX_ID: str(snapshot.presenter.tax_id),
        FilingProducerKey.FILING_RESULT_DISPOSITION: snapshot.elections.result_disposition.value,
        FilingProducerKey.TAXPAYER_TAX_ID: str(snapshot.taxpayer_tax_id),
        FilingProducerKey.TAXPAYER_LEGAL_NAME: identity.legal_name,
        FilingProducerKey.TAXPAYER_GIVEN_NAME: identity.given_name,
        FilingProducerKey.TAXPAYER_SURNAMES: identity.surnames,
        FilingProducerKey.TAXPAYER_FULL_NAME: identity.full_name,
        # "Apellidos o Razon Social": the two are mutually exclusive by
        # construction -- a natural person carries surnames and no legal_name,
        # an entity carries legal_name and no surnames -- so this resolves to
        # whichever the filer actually has, and stays absent only when both are.
        FilingProducerKey.TAXPAYER_SURNAMES_OR_LEGAL_NAME: identity.surnames or identity.legal_name,
        # Read from the declaration's own contact fact, never from the taxpayer
        # or the presenter: under a gestor the persona con quien relacionarse is
        # routinely neither, and substituting either would name the wrong person
        # in AEAT's informativa header.
        FilingProducerKey.CONTACT_PERSON_PHONE: snapshot.declaration_contact.phone,
        FilingProducerKey.CONTACT_PERSON_NAME: snapshot.declaration_contact.full_name,
        FilingProducerKey.AMENDMENT_IS_RECTIFICATIVA: amendment.is_rectificativa if amendment else None,
        FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA: amendment.is_complementaria if amendment else None,
        FilingProducerKey.AMENDMENT_ORIGINAL_AEAT_RECEIPT: amendment.original_aeat_receipt if amendment else None,
        # ONE official slot holding "S", "C" or blank. Derived from the amendment KIND,
        # never from the boolean pair: rendering "S" because is_complementaria is false
        # would assert a substitution nobody declared, which is why this is its own key.
        FilingProducerKey.AMENDMENT_SUSTITUTIVA_OR_COMPLEMENTARIA_MARKER: (
            None
            if amendment is None
            else "S"
            if amendment.is_sustitutiva
            else "C"
            if amendment.is_complementaria
            else None
        ),
        FilingProducerKey.AMENDMENT_M303_MOTIVE_RECTIFICACIONES: m303_motive[
            FilingProducerKey.AMENDMENT_M303_MOTIVE_RECTIFICACIONES
        ],
        FilingProducerKey.AMENDMENT_M303_MOTIVE_DISCREPANCIA_CRITERIO_ADMINISTRATIVO: m303_motive[
            FilingProducerKey.AMENDMENT_M303_MOTIVE_DISCREPANCIA_CRITERIO_ADMINISTRATIVO
        ],
        FilingProducerKey.SELECTED_ACCOUNT_IBAN: account.iban,
        FilingProducerKey.SELECTED_ACCOUNT_SWIFT_BIC: account.swift_bic,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_NAME: account.bank_name,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_ADDRESS: account.bank_address,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_CITY: account.bank_city,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_COUNTRY_CODE: account.bank_country_code,
        FilingProducerKey.PRIOR_DOMICILIATION_ACTION: (
            "X" if snapshot.elections.prior_domiciliation is PriorDomiciliationElection.CANCEL_OR_MODIFY else None
        ),
        FilingProducerKey.M303_REDEME_ENROLLED: m303_profile.redeme_enrolled,
        FilingProducerKey.M303_EXCLUSIVELY_FORAL: m303_profile.exclusively_foral,
        FilingProducerKey.M303_REGIME_COMPOSITION_CODE: m303_profile.regime_composition_code,
        FilingProducerKey.M303_ANNUAL_VOLUME_NONZERO: m303_filing.annual_volume_nonzero,
        FilingProducerKey.M303_JOINT_RETURN_ELECTED: m303_filing.joint_return_elected,
        FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED: m303_profile.cash_accounting_regime_enrolled,
        FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS: (
            m303_filing.recipient_of_cash_accounting_operations
        ),
        FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION: m303_filing.prorrata_special_option,
        FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION: m303_filing.prorrata_special_revocation,
        FilingProducerKey.M303_INSOLVENCY_DECLARED: m303_filing.insolvency_declared,
        FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE: m303_filing.insolvency_judicial_order_date,
        FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE: m303_filing.insolvency_filing_subtype,
        FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED: m303_profile.voluntary_sii_enrolled,
        FilingProducerKey.M303_EXONERADO_390_APPLICABLE: m303_filing.exonerado_390_applicable,
        FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED: (
            m303_profile.hydrocarbon_deposit_advance_payment_deduction_entitled
        ),
        FilingProducerKey.M111_COLEGIO_CONCERTADO: (
            snapshot.model_profile.colegio_concertado
            if isinstance(snapshot.model_profile, Modelo111ProfileFacts)
            else None
        ),
    }
    if m303_profile.is_foral:
        foral = m303_foral_lexicals(m303_filing)
        values.update(
            {
                FilingProducerKey.M303_REDEME_ENROLLED: "2",
                FilingProducerKey.M303_EXCLUSIVELY_FORAL: "1",
                FilingProducerKey.M303_REGIME_COMPOSITION_CODE: "3",
                FilingProducerKey.M303_JOINT_RETURN_ELECTED: "2",
                FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED: "2",
                FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS: "2",
                FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION: foral.prorrata_special_option,
                FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION: foral.prorrata_special_revocation,
                FilingProducerKey.M303_INSOLVENCY_DECLARED: None,
                FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE: None,
                FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE: None,
                FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED: "2",
                FilingProducerKey.M303_EXONERADO_390_APPLICABLE: "2",
                FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED: "2",
            },
        )
    values.update(m222_producer_values(snapshot.model_profile))
    values.update(m353_producer_values(snapshot.model_profile))
    shared_owned = {key for key, owner in filing_producer_ownership().items() if owner == "shared_snapshot"}
    if set(values) != shared_owned:
        raise FilingExportValidationError("shared filing producer resolver is not exhaustive over its owned keys")
    return values


def m303_rectificativa_motive_producer_values(
    amendment: AmendmentEvidence | None,
) -> dict[FilingProducerKey, bool | None]:
    """Project the closed two-checkbox truth table from one persisted motive."""
    motive = amendment.m303_rectificativa_motive if amendment is not None else None
    return {
        FilingProducerKey.AMENDMENT_M303_MOTIVE_RECTIFICACIONES: (
            motive is M303RectificativaMotive.RECTIFICACIONES if motive is not None else None
        ),
        FilingProducerKey.AMENDMENT_M303_MOTIVE_DISCREPANCIA_CRITERIO_ADMINISTRATIVO: (
            motive is M303RectificativaMotive.DISCREPANCIA_CRITERIO_ADMINISTRATIVO if motive is not None else None
        ),
    }


def selected_account_lexicals(snapshot: FilingProducerSnapshot) -> SelectedAccountLexicals:
    selected = snapshot.selected_account
    if isinstance(selected, RefundAccountSelection):
        return SelectedAccountLexicals(
            iban=selected.account.iban,
            swift_bic=selected.account.swift_bic,
            bank_name=selected.account.bank_name,
            bank_address=selected.account.bank_address,
            bank_city=selected.account.bank_city,
            bank_country_code=selected.account.bank_country_code,
        )
    if isinstance(selected, ChargeAccountSelection):
        return SelectedAccountLexicals(iban=selected.account.iban)
    return SelectedAccountLexicals()


def m303_profile_lexicals(
    iva_profile: ModeloIVAProfile | None,
    m303_facts: M303FilingFacts | None,
) -> M303ProfileLexicals:
    if iva_profile is None:
        return M303ProfileLexicals()
    period = m303_facts.period if m303_facts is not None else None
    a30 = (
        yes_no(iva_profile.hydrocarbon_deposit_advance_payment_deduction_entitled)
        if period is not None and m303_a30_entitlement_applicable(period)
        else "0"
        if period is not None
        else None
    )
    return M303ProfileLexicals(
        redeme_enrolled=yes_no(iva_profile.redeme_enrolled),
        exclusively_foral="1" if iva_profile.tax_territory is M303TaxTerritory.FORAL else "2",
        regime_composition_code={
            M303RegimeComposition.SIMPLIFIED: "1",
            M303RegimeComposition.MIXED: "2",
            M303RegimeComposition.GENERAL: "3",
        }[iva_profile.regime_composition],
        cash_accounting_regime_enrolled=yes_no(iva_profile.cash_accounting_regime_enrolled),
        voluntary_sii_enrolled=yes_no(iva_profile.voluntary_sii_enrolled),
        hydrocarbon_deposit_advance_payment_deduction_entitled=a30,
        is_foral=iva_profile.tax_territory is M303TaxTerritory.FORAL,
    )


def m303_filing_lexicals(m303_facts: M303FilingFacts | None) -> M303FilingLexicals:
    if m303_facts is None:
        return M303FilingLexicals()
    transition = m303_facts.prorrata_transition
    insolvency = m303_facts.insolvency
    transition_applicable = transition.is_applicable
    return M303FilingLexicals(
        joint_return_elected=yes_no(m303_facts.joint_return_elected),
        annual_volume_nonzero="1" if m303_facts.annual_volume_nonzero else None,
        recipient_of_cash_accounting_operations=yes_no(
            m303_facts.supplier_regime.recipient_of_cash_accounting_operations,
        ),
        prorrata_special_option=(
            yes_no(transition.transition is ProrrataEspecialTransitionKind.OPCION) if transition_applicable else None
        ),
        prorrata_special_revocation=(
            yes_no(transition.transition is ProrrataEspecialTransitionKind.REVOCACION)
            if transition_applicable
            else None
        ),
        insolvency_declared="1" if insolvency is not None else "2",
        insolvency_judicial_order_date=(
            insolvency.judicial_order_date.strftime("%d%m%Y") if insolvency is not None else None
        ),
        insolvency_filing_subtype=(
            {
                M303InsolvencyFilingSubtype.PRE_ORDER: "1",
                M303InsolvencyFilingSubtype.POST_ORDER: "2",
            }[insolvency.subtype]
            if insolvency is not None
            else None
        ),
        exonerado_390_applicable=(
            yes_no(m303_facts.exonerado_390.applicable) if is_last_filing_period_of_year(m303_facts.period) else "0"
        ),
        prorrata_transition_applicable=transition_applicable,
    )


def m303_foral_lexicals(m303_filing: M303FilingLexicals) -> M303ForalLexicals:
    value = "2" if m303_filing.prorrata_transition_applicable else None
    return M303ForalLexicals(prorrata_special_option=value, prorrata_special_revocation=value)


def yes_no(value: bool) -> str:
    return "1" if value else "2"


def m303_a30_entitlement_applicable(period: Period) -> bool:
    return period.registry_token.isdigit() and int(period.registry_token) >= 2


__all__ = [
    "M303FilingLexicals",
    "M303ForalLexicals",
    "M303ProfileLexicals",
    "SelectedAccountLexicals",
    "filing_producer_ownership",
    "filing_producer_values",
    "m303_filing_lexicals",
    "m303_foral_lexicals",
    "m303_profile_lexicals",
    "m303_rectificativa_motive_producer_values",
    "selected_account_lexicals",
]
