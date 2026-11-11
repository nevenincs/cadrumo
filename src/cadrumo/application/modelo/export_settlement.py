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

The amount comes from the box the declaration settles
(:func:`~.settlement_casilla.declaration_settlement_casilla_id`): for the
Modelo 100 its computed "Resultado a ingresar o a devolver" (``RESINGDEV``),
which is the remainder still to pay once the spouse compensation suspends part
of the result, otherwise the result itself. A revision that computes no such
box settles from the result only while nothing is suspended and no refund
is waived (LIRPF art. 97.6): a positive suspended or waived part leaves a
remainder it does not compute, so that settlement is refused as unsupported.
A part left blank is nothing, as the calculation reads it. The disposition is the one the shared resolver derived
from the result, and the settled amount must agree with it: the official
design gives no settlement block for a result to pay of which nothing remains
to pay, so such a settlement, like one whose amount is unknown, is refused
rather than guessed. The accounts are the charge and
refund own accounts the export resolved. A ``NEGATIVA`` block is written only
by a corrective declaration, which this export does not compose, so a zero
result states its disposition alone.

A split in two instalments takes the first instalment's share from the
registry; the cent it rounds to is Cadrumo's own, as no official source states
one, and an amount whose second instalment would round to nothing is not split.

Account numbers pass through here in memory only, into the exported file;
:class:`ModeloRevision`, the registry revision a modelo is calculated against.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from ...core.casilla_id import CasillaId
from ...core.payment_instalment_election import (
    PaymentInstalmentElection,
    instalment_amounts,
    second_instalment_is_payable,
)
from ...core.result_disposition import ResultDisposition
from ...domain.deadlines.models import ChargeAccount, RefundAccount
from ...domain.iva.sepa_marca import SepaMarca, derive_sepa_marca
from ...domain.modelos.errors import ModeloExportError
from .action_errors import instalment_election_refusal, own_account_missing_error
from .settlement_casilla import declaration_settlement_casilla_id, declaration_settlement_remainder_casilla_ids

if TYPE_CHECKING:
    from ...domain.calculations.registry.schema import ModeloRevision

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


class SettlementRefusal(StrEnum):
    """Why a declaration's settlement cannot be composed."""

    #: The box the declaration settles holds no value: it is unresolved or not calculated.
    RESULT_UNKNOWN = "result_unknown"
    #: The settled amount does not go the way the result does, and the official design gives no block for that.
    SETTLEMENT_UNSUPPORTED = "settlement_unsupported"


@dataclass(frozen=True, slots=True)
class DeclaredSettlement:
    """The amount a declaration settles, signed as its result is, or why it has none.

    Exactly one of ``amount`` and ``refusal`` is set.
    """

    amount: Decimal | None
    refusal: SettlementRefusal | None

    def __post_init__(self) -> None:
        """Refuse a settlement that carries both an amount and a refusal, or neither."""
        if (self.amount is None) is (self.refusal is None):
            raise ValueError("a settlement carries its amount or its refusal, never both or neither")


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    return None


def _agrees(disposition: ResultDisposition | None, amount: Decimal) -> bool:
    """Whether ``amount`` settles the way ``disposition`` says the result does."""
    if disposition in _TO_PAY:
        return amount > 0
    if disposition in _TO_REFUND:
        return amount < 0
    if disposition in _STATED_ALONE:
        return amount <= 0
    return True


def declared_settlement(
    modelo: str,
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, object],
    *,
    disposition: ResultDisposition | None,
) -> DeclaredSettlement:
    """The amount ``revision`` settles, read from the box it settles and checked against ``disposition``.

    Args:
        modelo: The modelo number.
        revision: The registry revision the values belong to.
        casilla_values: The declaration's values by casilla id; an absent box holds no value.
        disposition: The disposition derived from the result, before any filing election.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    casilla_id = declaration_settlement_casilla_id(modelo, revision)
    amount = None if casilla_id is None else _decimal(casilla_values.get(casilla_id))
    if amount is None:
        return DeclaredSettlement(amount=None, refusal=SettlementRefusal.RESULT_UNKNOWN)
    for part_casilla_id in declaration_settlement_remainder_casilla_ids(modelo, revision):
        # A box the filer left blank is read as the calculation reads it: nothing suspended or waived.
        part = _decimal(casilla_values.get(part_casilla_id))
        if part is not None and part > 0:
            return DeclaredSettlement(amount=None, refusal=SettlementRefusal.SETTLEMENT_UNSUPPORTED)
    if not _agrees(disposition, amount):
        return DeclaredSettlement(amount=None, refusal=SettlementRefusal.SETTLEMENT_UNSUPPORTED)
    return DeclaredSettlement(amount=amount, refusal=None)


def settlement_dictionary_values(
    *,
    disposition: ResultDisposition | None,
    settlement: DeclaredSettlement,
    instalment: PaymentInstalmentElection,
    first_instalment_share: Decimal | None,
    charge_account: ChargeAccount | None,
    refund_account: RefundAccount | None,
) -> dict[str, object]:
    """Compose the settlement rows of the official record, keyed by dictionary field id.

    Args:
        disposition: The resolved result disposition; ``None`` writes nothing.
        settlement: The amount the declaration settles, signed as its result is.
        instalment: Whether a result to pay is paid at once or in two instalments.
        first_instalment_share: The registry's share of the first instalment,
            ``None`` where the modelo declares no split.
        charge_account: The account AEAT debits, when a payment is direct-debited.
        refund_account: The account AEAT pays a refund into.

    Raises:
        ModeloExportError: When the settled amount is unknown or disagrees
            with the disposition, or is one this export never composes.
        ModeloChargeAccountMissingError: When a debit needs a charge account
            the export does not hold.
        ModeloRefundAccountMissingError: When a refund needs a refund account
            the export does not hold.
        ModeloInstalmentElectionRefusedError: When the elected split cannot be
            written.
    """
    if disposition is None:
        return {}
    if settlement.refusal is not None:
        raise _settlement_refused(disposition, settlement.refusal)
    values: dict[str, object] = {DISPOSITION_FIELD: disposition.value}
    if disposition in _STATED_ALONE:
        return values
    amount = _required_amount(disposition, settlement.amount)
    if disposition in _TO_PAY:
        values.update(_payment_values(disposition, amount, instalment, first_instalment_share, charge_account))
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
    first_share: Decimal | None,
    charge_account: ChargeAccount | None,
) -> dict[str, object]:
    debits_first = disposition is ResultDisposition.DOMICILIACION
    debits_any = debits_first or instalment.debits_second
    iban = None
    if debits_any:
        if charge_account is None:
            raise own_account_missing_error("charge", context={"result_disposition": disposition.value})
        iban = charge_account.iban
    if not instalment.splits:
        return {_SINGLE_AMOUNT_FIELD: amount, _SINGLE_ACCOUNT_FIELD: iban if debits_first else None}
    if first_share is None:
        raise instalment_election_refusal("not_declared", context={"result_disposition": disposition.value})
    if not second_instalment_is_payable(amount, first_share=first_share):
        raise instalment_election_refusal(
            "second_instalment_nothing", context={"result_disposition": disposition.value}
        )
    first, second = instalment_amounts(amount, first_share=first_share)
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
        raise own_account_missing_error("refund", context={"result_disposition": ResultDisposition.DEVOLUCION.value})
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


_REFUSAL_LOCALE_KEYS: Final = {
    SettlementRefusal.RESULT_UNKNOWN: "application.modelo.errors.export_settlement_unknown",
    SettlementRefusal.SETTLEMENT_UNSUPPORTED: "application.modelo.errors.export_settlement_unsupported",
}


def _settlement_refused(disposition: ResultDisposition, refusal: SettlementRefusal) -> ModeloExportError:
    """Refuse with the settlement's own message: the generic write failure would read as a disk problem."""
    return ModeloExportError(
        translated_message=_REFUSAL_LOCALE_KEYS[refusal],
        context={"cause": refusal.value, "result_disposition": disposition.value},
    )


def _uncomposed(disposition: ResultDisposition, *, cause: str) -> ModeloExportError:
    return ModeloExportError(
        translated_message="application.modelo.errors.export_draft_write_failed",
        context={"cause": cause, "result_disposition": disposition.value},
    )


__all__ = [
    "DISPOSITION_FIELD",
    "DeclaredSettlement",
    "SettlementRefusal",
    "declared_settlement",
    "settlement_dictionary_values",
]
