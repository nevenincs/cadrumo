"""Payer-fact predicates for modelo applicability rules.

Each :class:`TaxpayerProfile` boolean answers one payer or trade fact used by
the modelo applicability rule table.
"""

from __future__ import annotations

from enum import StrEnum

from ...deadlines.taxpayer_model import TaxpayerProfile

__all__ = ["PayerFact", "payer_fact_holds"]


class PayerFact(StrEnum):
    """A withholding-payer / trade fact a modelo's applicability needs."""

    PAYS_WITHHELD_INCOME = "pays_withheld_income"
    PAYS_RENT_WITH_RETENCION = "pays_rent_with_retencion"
    TRADES_INTRACOMMUNITY = "trades_intracommunity"
    EXCEEDS_THIRD_PARTY_THRESHOLD = "exceeds_third_party_threshold"
    BIENES_EXTRANJERO_ABOVE_THRESHOLD = "bienes_extranjero_above_threshold"
    MONEDAS_VIRTUALES_EXTRANJERO_ABOVE_THRESHOLD = "monedas_virtuales_extranjero_above_threshold"
    PAYS_NON_RESIDENT_INCOME = "pays_non_resident_income"
    PAYS_CAPITAL_INCOME_WITH_RETENCION = "pays_capital_income_with_retencion"
    IVA_GROUP_MEMBER = "iva_group_member"
    IVA_GROUP_DOMINANT_ENTITY = "iva_group_dominant_entity"
    MEMBER_OF_LARGE_MULTINATIONAL_GROUP = "member_of_large_multinational_group"
    EU_BUSINESS_SEEKING_SPANISH_VAT_REFUND = "eu_business_seeking_spanish_vat_refund"
    REPORTS_CLIENT_SECURITIES_INSURANCE_ANNUITIES = "reports_client_securities_insurance_annuities"
    MARKETS_LONG_TERM_SAVINGS_PLANS = "markets_long_term_savings_plans"
    CRS_REPORTING_FINANCIAL_INSTITUTION = "crs_reporting_financial_institution"
    MANAGES_PENSION_PLAN_CONTRIBUTIONS = "manages_pension_plan_contributions"
    PAYMENT_SERVICE_PROVIDER_CESOP = "payment_service_provider_cesop"
    SUBJECT_TO_LOTTERY_PRIZE_SPECIAL_LEVY = "subject_to_lottery_prize_special_levy"
    ISSUES_NEW_ENTITY_INVESTOR_CERTIFICATIONS = "issues_new_entity_investor_certifications"
    INTERMEDIATES_TOURIST_HOUSING_RENTAL = "intermediates_tourist_housing_rental"
    CREDIT_INSTITUTION_REPORTING_PROPERTY_LOANS = "credit_institution_reporting_property_loans"
    RECEIVES_DEDUCTIBLE_DONATIONS = "receives_deductible_donations"
    AUTHORIZED_CHILDCARE_CENTER = "authorized_childcare_center"
    REPORTING_PLATFORM_OPERATOR = "reporting_platform_operator"
    PAYS_LOTTERY_PRIZES_SPECIAL_LEVY = "pays_lottery_prizes_special_levy"
    MEMBER_OF_FISCAL_CONSOLIDATION_GROUP = "member_of_fiscal_consolidation_group"
    DAC6_REPORTABLE_ARRANGEMENT_PARTY = "dac6_reportable_arrangement_party"
    FILES_PUBLIC_REGISTRY_OPERATIONS = "files_public_registry_operations"
    OPTS_MATERNITY_DEDUCTION_ADVANCE_PAYMENT = "opts_maternity_deduction_advance_payment"
    REAGP_COMPENSATION_REINTEGRO = "reagp_compensation_reintegro"
    PERFORMS_IVA_IMPORT_EQUIVALENT_OPERATIONS = "performs_iva_import_equivalent_operations"


def payer_fact_holds(profile: TaxpayerProfile, fact: PayerFact) -> bool:
    """Return whether ``profile`` positively declares the payer ``fact``.

    The supplied :class:`TaxpayerProfile` provides the boolean field backing the
    requested :class:`PayerFact`.
    """
    match fact:
        case PayerFact.PAYS_WITHHELD_INCOME:
            return profile.has_employees or profile.pays_professionals_with_retencion
        case PayerFact.PAYS_RENT_WITH_RETENCION:
            return profile.pays_rent_with_retencion
        case PayerFact.TRADES_INTRACOMMUNITY:
            return profile.does_intracomunitario
        case PayerFact.EXCEEDS_THIRD_PARTY_THRESHOLD:
            return profile.third_party_transactions_above_347_threshold
        case PayerFact.BIENES_EXTRANJERO_ABOVE_THRESHOLD:
            return profile.bienes_extranjero_above_threshold
        case PayerFact.MONEDAS_VIRTUALES_EXTRANJERO_ABOVE_THRESHOLD:
            return profile.monedas_virtuales_extranjero_above_threshold
        case PayerFact.PAYS_NON_RESIDENT_INCOME:
            return profile.pays_non_resident_income
        case PayerFact.PAYS_CAPITAL_INCOME_WITH_RETENCION:
            return profile.pays_capital_income_with_retencion
        case PayerFact.IVA_GROUP_MEMBER:
            return profile.iva.group_member_enrolled
        case PayerFact.IVA_GROUP_DOMINANT_ENTITY:
            return profile.iva.group_dominant_entity_enrolled
        case PayerFact.MEMBER_OF_LARGE_MULTINATIONAL_GROUP:
            return profile.member_of_large_multinational_group
        case PayerFact.EU_BUSINESS_SEEKING_SPANISH_VAT_REFUND:
            return profile.eu_business_seeking_spanish_vat_refund
        case PayerFact.REPORTS_CLIENT_SECURITIES_INSURANCE_ANNUITIES:
            return profile.reports_client_securities_insurance_annuities
        case PayerFact.MARKETS_LONG_TERM_SAVINGS_PLANS:
            return profile.markets_long_term_savings_plans
        case PayerFact.CRS_REPORTING_FINANCIAL_INSTITUTION:
            return profile.crs_reporting_financial_institution
        case PayerFact.MANAGES_PENSION_PLAN_CONTRIBUTIONS:
            return profile.manages_pension_plan_contributions
        case PayerFact.PAYMENT_SERVICE_PROVIDER_CESOP:
            return profile.payment_service_provider_cesop
        case PayerFact.SUBJECT_TO_LOTTERY_PRIZE_SPECIAL_LEVY:
            return profile.subject_to_lottery_prize_special_levy
        case PayerFact.ISSUES_NEW_ENTITY_INVESTOR_CERTIFICATIONS:
            return profile.issues_new_entity_investor_certifications
        case PayerFact.INTERMEDIATES_TOURIST_HOUSING_RENTAL:
            return profile.intermediates_tourist_housing_rental
        case PayerFact.CREDIT_INSTITUTION_REPORTING_PROPERTY_LOANS:
            return profile.credit_institution_reporting_property_loans
        case PayerFact.RECEIVES_DEDUCTIBLE_DONATIONS:
            return profile.receives_deductible_donations
        case PayerFact.AUTHORIZED_CHILDCARE_CENTER:
            return profile.authorized_childcare_center
        case PayerFact.REPORTING_PLATFORM_OPERATOR:
            return profile.reporting_platform_operator
        case PayerFact.PAYS_LOTTERY_PRIZES_SPECIAL_LEVY:
            return profile.pays_lottery_prizes_special_levy
        case PayerFact.MEMBER_OF_FISCAL_CONSOLIDATION_GROUP:
            return profile.member_of_fiscal_consolidation_group
        case PayerFact.DAC6_REPORTABLE_ARRANGEMENT_PARTY:
            return profile.dac6_reportable_arrangement_party
        case PayerFact.FILES_PUBLIC_REGISTRY_OPERATIONS:
            return profile.files_public_registry_operations
        case PayerFact.OPTS_MATERNITY_DEDUCTION_ADVANCE_PAYMENT:
            return profile.opts_maternity_deduction_advance_payment
        case PayerFact.REAGP_COMPENSATION_REINTEGRO:
            return profile.reagp_compensation_reintegro
        case PayerFact.PERFORMS_IVA_IMPORT_EQUIVALENT_OPERATIONS:
            return profile.performs_iva_import_equivalent_operations
