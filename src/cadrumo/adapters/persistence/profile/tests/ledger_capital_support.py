"""Synthetic ledger-paid movable-capital withholding shared by capture and calculation tests.

One synthetic June 2025 interest coupon: 1000.00 gross, 19% IRPF (190.00)
withheld, so the bank paid the holder 1000.00 - 190.00 = 810.00. The coupon
became exigible on 30 June and was paid on 2 July, so recognition falls on the
exigibility date and the withholding belongs to the 2025 second quarter.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .....application.aggregation.ledger_payment_withholding import LedgerPaymentWithholdingEvidenceRequest
from .....application.aggregation.retenciones import Modelo193NonpaymentCause, Modelo193PendingPaymentEvidence
from .....application.aggregation.tests.ledger_transaction_support import ledger_raw_transaction
from .....application.aggregation.withholding_observation_service import WithholdingObservationService
from .....application.aggregation.withholding_producer import WithholdingProducer
from .....application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from .....core.aggregation import RetencionClave, RetencionScheme
from .....domain.calculations.registry.withholding_bindings import WithholdingObservation
from .....domain.transactions.enums import TransactionDirection, TransactionLifecycleState
from .....domain.transactions.models import Transaction
from ...storage.sql.secure_objects import SecureObjectRepository
from ..percepciones_observations import PercepcionObservationRepositoryAdapter
from ..retencion_observations import RetencionObservationRepositoryAdapter
from ..withholding_observation_workflow import WithholdingObservationWorkflowAdapter

CAPITAL_GROSS = Decimal("1000.00")
CAPITAL_IRPF = Decimal("190.00")
CAPITAL_NET = CAPITAL_GROSS - CAPITAL_IRPF
CAPITAL_EXIGIBLE_ON = date(2025, 6, 30)
CAPITAL_PAID_ON = date(2025, 7, 2)
CAPITAL_HOLDER_NIF = "22222222J"
CAPITAL_HOLDER_NAME = "Titular Sintetico"


def capital_payment(
    *,
    provider_id: str = "coupon-2025-06",
    amount: Decimal = CAPITAL_NET,
    booked_date: date = CAPITAL_PAID_ON,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
) -> Transaction:
    """Return the active EUR ledger payment of one synthetic interest coupon."""
    return Transaction.model_validate(
        {
            "raw": ledger_raw_transaction(provider_id, booked_date=booked_date, amount=amount),
            "direction": direction,
            "source_jurisdiction": "ES",
            "group_label": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
        }
    )


def capital_request(transaction: Transaction, **update: object) -> LedgerPaymentWithholdingEvidenceRequest:
    """Return the declared coupon terms for ``transaction``, with any field overridden."""
    payload: dict[str, object] = {
        "transaction_id": transaction.transaction_id,
        "income_kind": WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL,
        "scheme": RetencionScheme("intereses"),
        "recipient_tax_status": WithholdingRecipientTaxStatus.RESIDENT,
        "recipient_tax_regime": WithholdingRecipientTaxRegime.IRPF,
        "payment_event_id": "coupon-payment-2025-07",
        "allocation_id": "coupon-allocation-2025-06",
        "gross_base": CAPITAL_GROSS,
        "withholding_amount": CAPITAL_IRPF,
        "net_settlement": CAPITAL_NET,
        "idempotency_key": "coupon-capture-2025-06",
        "perceptor_nif": CAPITAL_HOLDER_NIF,
        "perceptor_name": CAPITAL_HOLDER_NAME,
        "exigibility_event_id": "coupon-exigible-2025-06",
        "exigibility_occurred_on": CAPITAL_EXIGIBLE_ON,
    }
    return LedgerPaymentWithholdingEvidenceRequest.model_validate(payload | update)


def capital_pending_payment(transaction: Transaction, *, transaction_date: date) -> Modelo193PendingPaymentEvidence:
    """Return the actual-holder Modelo 193 facts behind a pending key B coupon."""
    return Modelo193PendingPaymentEvidence(
        perception_key="B",
        nonpayment_cause=Modelo193NonpaymentCause.HOLDER_NOT_PRESENTED_FOR_COLLECTION,
        actual_recipient_detail=WithholdingObservation(
            source_id=transaction.transaction_id,
            perceptor_tax_id=CAPITAL_HOLDER_NIF,
            perceptor_legal_name=CAPITAL_HOLDER_NAME,
            transaction_date=transaction_date,
            clave=RetencionClave.from_registry("B"),
            percibido_dinerario=CAPITAL_GROSS,
            retencion_practicada=CAPITAL_IRPF,
            incapacity_cash_perception=Decimal("0"),
            incapacity_cash_withholding=Decimal("0"),
            incapacity_kind_value=Decimal("0"),
            incapacity_kind_ingreso_a_cuenta=Decimal("0"),
            incapacity_kind_repercutido=Decimal("0"),
            foral_retention_estatal=Decimal("0"),
            foral_retention_navarra=Decimal("0"),
            foral_retention_araba=Decimal("0"),
            foral_retention_gipuzkoa=Decimal("0"),
            foral_retention_bizkaia=Decimal("0"),
            base_retenciones=CAPITAL_GROSS,
            porcentaje_retencion=Decimal("19"),
            clave_codigo=4,
            naturaleza="03",
            pago=1,
            tipo_codigo="C",
            tipo_percepcion=1,
            clave_mercado="A",
        ),
    )


def withholding_producer(objects: object) -> WithholdingProducer:
    """Return the shared producer over the encrypted workflow store of ``objects``."""
    assert isinstance(objects, SecureObjectRepository)
    return WithholdingProducer(
        service=WithholdingObservationService(
            WithholdingObservationWorkflowAdapter(
                objects=objects,
                retenciones=RetencionObservationRepositoryAdapter(objects=objects),
                percepciones=PercepcionObservationRepositoryAdapter(objects=objects),
            )
        )
    )


__all__ = [
    "CAPITAL_EXIGIBLE_ON",
    "CAPITAL_GROSS",
    "CAPITAL_HOLDER_NAME",
    "CAPITAL_HOLDER_NIF",
    "CAPITAL_IRPF",
    "CAPITAL_NET",
    "CAPITAL_PAID_ON",
    "capital_payment",
    "capital_pending_payment",
    "capital_request",
    "withholding_producer",
]
