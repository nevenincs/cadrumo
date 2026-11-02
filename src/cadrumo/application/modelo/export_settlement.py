"""How an XML-dictionary declaration's result is paid or refunded, as the official record states it.

The Modelo 100 dictionary and XSD carry the settlement in
``DatosIngresoDevolucion``: ``TIPODECLARACION`` (the result disposition), then
exactly one of ``AINGRESAR`` (a result to pay, at once in ``PAGONOFRACC`` or in
two instalments in ``PAGOFRACC``), ``ADEVOLVER`` (a refund, into a Spanish
account, a SEPA account abroad in ``DEVSEPA`` or another account abroad in
``DEVNOSEPA``) or ``NEGATIVA``. Every row is addressed here by the field id
the official dictionary declares for it, which is the address the XML
renderer writes a non-casilla value at; a dictionary that declares none of
them writes none of them.

The amounts come from the declaration's own result; the accounts are the
charge and refund own accounts the export resolved; the disposition is the
one the shared resolver determined. A ``NEGATIVA`` block is written only by
a corrective declaration, which this export does not compose, so a zero
result states its disposition alone.

Account numbers pass through here in memory only, into the exported file.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from ...core.casilla_id import CasillaId
from ...core.payment_instalment_election import PaymentInstalmentElection, instalment_amounts
from ...core.result_disposition import ResultDisposition
from ...domain.calculations.registry.result_casillas import result_disposition_casilla_ids
from ...domain.deadlines.models import ChargeAccount, RefundAccount
from ...domain.iva.sepa_marca import SepaMarca, derive_sepa_marca
from ...domain.modelos.errors import ModeloExportError

DISPOSITION_FIELD: Final = "TIPODECLARACION"
_SINGLE_AMOUNT_FIELD: Final = "ING_IMPORTE"
_SINGLE_ACCOUNT_FIELD: Final = "ING_CUENTACORRIENTE"
_FIRST_AMOUNT_FIELD: Final = "ING_IMPORTE_PF1"
_SECOND_AMOUNT_FIELD: Final = "ING_IMPORTE_PF2"
_SECOND_DEBITED_FIELD: Final = "ING_DOMICILIA_PF2"
_FIRST_ACCOUNT_FIELD: Final = "ING_CUENTACORRIENTE_PF1"
_SECOND_ACCOUNT_FIELD: Final = "ING_CUENTACORRIENTE_PF2"
_REFUND_AMOUNT_FIELD: Final = "DEV_IMPORTE"
_REFUND_ACCOUNT_FIELD: Final = "DEV_CUENTACORRIENTE"
_SEPA_ACCOUNT_FIELD: Final = "DEV_CUENTACORRIENTESEPA"
_SEPA_SWIFT_FIELD: Final = "DEV_SWIFT"
_FOREIGN_ACCOUNT_FIELD: Final = "DEV_CUENTACORRIENTE_OTROS"
_FOREIGN_SWIFT_FIELD: Final = "DEV_SWIFT_OTROS"
_FOREIGN_BANK_FIELDS: Final = ("DEV_NOMBRE_BANCO", "DEV_DIR_BANCO", "DEV_CIUDAD_BANCO", "DEV_PAIS_BANCO")

_TO_PAY: Final = frozenset({ResultDisposition.INGRESO, ResultDisposition.DOMICILIACION})
_TO_REFUND: Final = frozenset(
    {ResultDisposition.DEVOLUCION, ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO},
)
_STATED_ALONE: Final = frozenset({ResultDisposition.NEGATIVA})


def declared_result_amount(modelo: str, casilla_values: Mapping[CasillaId, object]) -> Decimal | None:
    """The declaration's result, read from the casilla its "tipo de declaración" rule names.

    ``None`` when the modelo names no single result casilla or the draft
    carries no amount there.
    """
    result_ids = result_disposition_casilla_ids(modelo)
    if result_ids is None or len(result_ids) != 1:
        return None
    value = casilla_values.get(result_ids[0])
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    return None


def settlement_dictionary_values(
    *,
    disposition: ResultDisposition | None,
    result_amount: Decimal | None,
    instalment: PaymentInstalmentElection,
    charge_account: ChargeAccount | None,
    refund_account: RefundAccount | None,
) -> dict[str, object]:
    """Compose the settlement rows of the official record, keyed by dictionary field id.

    Args:
        disposition: The resolved result disposition; ``None`` writes nothing.
        result_amount: The declaration's signed result.
        instalment: Whether a result to pay is paid at once or in two instalments.
        charge_account: The account AEAT debits, when a payment is direct-debited.
        refund_account: The account AEAT pays a refund into.

    Raises:
        ModeloExportError: When the disposition needs an amount or an account
            the export does not hold, or is one this export never composes.
    """
    if disposition is None:
        return {}
    values: dict[str, object] = {DISPOSITION_FIELD: disposition.value}
    if disposition in _STATED_ALONE:
        return values
    amount = _required_amount(disposition, result_amount)
    if disposition in _TO_PAY:
        values.update(_payment_values(disposition, amount, instalment, charge_account))
        return values
    if disposition in _TO_REFUND:
        values.update(_refund_values(-amount, refund_account))
        return values
    raise _uncomposed(disposition, cause="disposition_not_composed")


def _required_amount(disposition: ResultDisposition, result_amount: Decimal | None) -> Decimal:
    if result_amount is None or result_amount.is_zero():
        raise _uncomposed(disposition, cause="result_amount_missing")
    return result_amount


def _payment_values(
    disposition: ResultDisposition,
    amount: Decimal,
    instalment: PaymentInstalmentElection,
    charge_account: ChargeAccount | None,
) -> dict[str, object]:
    debits_first = disposition is ResultDisposition.DOMICILIACION
    debits_any = debits_first or instalment.debits_second
    iban = None
    if debits_any:
        if charge_account is None:
            raise _uncomposed(disposition, cause="charge_account_missing")
        iban = charge_account.iban
    if not instalment.splits:
        return {_SINGLE_AMOUNT_FIELD: amount, _SINGLE_ACCOUNT_FIELD: iban if debits_first else None}
    first, second = instalment_amounts(amount)
    # The manual requires the second instalment to be debited from the same
    # account as the first when both are, so one charge account serves both.
    return {
        _FIRST_AMOUNT_FIELD: first,
        _SECOND_AMOUNT_FIELD: second,
        _SECOND_DEBITED_FIELD: instalment.debits_second,
        _FIRST_ACCOUNT_FIELD: iban if debits_first else None,
        _SECOND_ACCOUNT_FIELD: iban if instalment.debits_second else None,
    }


def _refund_values(amount: Decimal, refund_account: RefundAccount | None) -> dict[str, object]:
    if refund_account is None or refund_account.iban is None:
        raise _uncomposed(ResultDisposition.DEVOLUCION, cause="refund_account_missing")
    values: dict[str, object] = {_REFUND_AMOUNT_FIELD: amount}
    marca = derive_sepa_marca(iban=refund_account.iban, bank_country_code=refund_account.bank_country_code)
    if marca is SepaMarca.ESPANA:
        values[_REFUND_ACCOUNT_FIELD] = refund_account.iban
    elif marca is SepaMarca.UE_SEPA:
        values[_SEPA_ACCOUNT_FIELD] = refund_account.iban
        values[_SEPA_SWIFT_FIELD] = refund_account.swift_bic or None
    else:
        values[_FOREIGN_ACCOUNT_FIELD] = refund_account.iban
        values[_FOREIGN_SWIFT_FIELD] = refund_account.swift_bic or None
        bank = (
            refund_account.bank_name,
            refund_account.bank_address,
            refund_account.bank_city,
            refund_account.bank_country_code,
        )
        values.update({field: text or None for field, text in zip(_FOREIGN_BANK_FIELDS, bank, strict=True)})
    return values


def _uncomposed(disposition: ResultDisposition, *, cause: str) -> ModeloExportError:
    return ModeloExportError(
        translated_message="application.modelo.errors.export_draft_write_failed",
        context={"cause": cause, "result_disposition": disposition.value},
    )


__all__ = [
    "DISPOSITION_FIELD",
    "declared_result_amount",
    "settlement_dictionary_values",
]
