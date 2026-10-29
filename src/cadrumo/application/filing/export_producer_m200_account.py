"""Modelo 200 account producer values."""

from __future__ import annotations

from ...core.filing_producer_key import FilingProducerKey
from ...domain.iva.sepa_marca import derive_sepa_marca
from .producer_snapshot import ChargeAccountSelection, RefundAccountSelection, SelectedFilingAccount


def m200_account_values(selected: SelectedFilingAccount | None) -> dict[FilingProducerKey, object]:
    """Feed modelo 200's DID page by role from the one selected account.

    DR200 page DID carries the devolución account block (Marca SEPA at 242, IBAN
    at 243, SWIFT-BIC and the foreign-bank block after it) and, separately, the
    ingreso domiciliación IBAN at 443. A refund selection fills the first, a
    charge selection the second; the account is never copied into the profile.
    """
    values = _m200_refund_account_values(selected)
    charge = selected.account if isinstance(selected, ChargeAccountSelection) else None
    values[FilingProducerKey.M200_NUMERO_DE_CUENTA_IBAN_2] = None if charge is None else charge.iban
    return values


def _m200_refund_account_values(selected: SelectedFilingAccount | None) -> dict[FilingProducerKey, object]:
    refund = selected.account if isinstance(selected, RefundAccountSelection) else None
    return {
        FilingProducerKey.M200_CUENTA_BANCARIA_MARCA_SEPA: (
            None
            if refund is None
            else derive_sepa_marca(iban=refund.iban, bank_country_code=refund.bank_country_code).value
        ),
        FilingProducerKey.M200_NUMERO_DE_CUENTA_IBAN: None if refund is None else refund.iban,
        FilingProducerKey.M200_CUENTA_BANCARIA_CODIGO_SWIFT_BIC: None if refund is None else refund.swift_bic,
        FilingProducerKey.M200_CUENTA_BANCARIA_BANCO_BANK_NAME: None if refund is None else refund.bank_name,
        FilingProducerKey.M200_DIRECCION_DEL_BANCO_BANK_ADDRESS: None if refund is None else refund.bank_address,
        FilingProducerKey.M200_CUENTA_BANCARIA_CIUDAD_CITY: None if refund is None else refund.bank_city,
        FilingProducerKey.M200_CODIGO_PAIS_COUNTRY_CODE: None if refund is None else refund.bank_country_code,
    }
