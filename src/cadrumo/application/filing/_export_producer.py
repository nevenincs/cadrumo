"""Producer-value projection for the declaration export renderer."""

from __future__ import annotations

from dataclasses import dataclass

from ...core import FilingProducerKey, Period, PriorDomiciliationElection, ProrrataEspecialTransitionKind
from ...domain.deadlines import M303RegimeComposition, M303TaxTerritory, ModeloIVAProfile
from ...domain.iva import is_last_filing_period_of_year
from ...domain.modelos import M303RectificativaMotive
from ._producer_snapshot import (
    AmendmentEvidence,
    ChargeAccountSelection,
    FilingProducerSnapshot,
    M303FilingFacts,
    M303InsolvencyFilingSubtype,
    Modelo111ProfileFacts,
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
    # Registry-derived producer keys are intentionally broader than this shared
    # profile projection.  Layout preflight resolves every field by key and
    # refuses a missing required value; demanding an entry for every key in the
    # global enum would make unrelated modelo-specific producers block M369.
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
    "filing_producer_values",
    "m303_filing_lexicals",
    "m303_foral_lexicals",
    "m303_profile_lexicals",
    "m303_rectificativa_motive_producer_values",
    "selected_account_lexicals",
]
