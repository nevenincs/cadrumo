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
    TAXPAYER_LEGAL_NAME = "taxpayer.legal_name"
    TAXPAYER_GIVEN_NAME = "taxpayer.given_name"
    TAXPAYER_SURNAMES = "taxpayer.surnames"
    TAXPAYER_FULL_NAME = "taxpayer.full_name"
    AMENDMENT_IS_RECTIFICATIVA = "amendment_evidence.is_rectificativa"
    AMENDMENT_IS_COMPLEMENTARIA = "amendment_evidence.is_complementaria"
    AMENDMENT_ORIGINAL_AEAT_RECEIPT = "amendment_evidence.original_aeat_receipt"
    SELECTED_ACCOUNT_IBAN = "selected_account.iban"
    SELECTED_ACCOUNT_SWIFT_BIC = "selected_account.swift_bic"
    SELECTED_ACCOUNT_BANK_NAME = "selected_account.bank_name"
    SELECTED_ACCOUNT_BANK_ADDRESS = "selected_account.bank_address"
    SELECTED_ACCOUNT_BANK_CITY = "selected_account.bank_city"
    SELECTED_ACCOUNT_BANK_COUNTRY_CODE = "selected_account.bank_country_code"
    PRIOR_DOMICILIATION_ACTION = "prior_domiciliation.action"
    M303_REDEME_ENROLLED = "m303.redeme_enrolled"
    M111_COLEGIO_CONCERTADO = "m111.colegio_concertado"
