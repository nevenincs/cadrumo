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
