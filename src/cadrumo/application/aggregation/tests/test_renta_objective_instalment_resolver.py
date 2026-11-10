"""The Modelo 131 resolver reads the agrarian activity set into its volumen de ingresos.

The resolver routes the objective-estimation instalment through its own aggregation:
only a row declaring an agrarian tipo de actividad contributes, and no imputation
criterion is consulted. These tests drive the real resolver over a real ledger.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition

from ....core.tipos_actividad import TipoActividad
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from .renta_income_aggregation_support import raw_transaction
from .test_renta_imputation_criterion import DEVENGO
from .test_renta_rectificativa_income import resolve

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = newest_authored_edition("131")
_ON = date(_YEAR, 5, 14)
_AMOUNT = Decimal("1000.00")


def _receipt(provider_id: str, tipo_actividad: TipoActividad | None) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": raw_transaction(provider_id, booked_date=_ON, value_date=_ON, amount=_AMOUNT, currency="EUR"),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_YEAR, 7, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
            "tipo_actividad": tipo_actividad,
        },
    )


def _volumen(operation: PinnedAuthorityOperation, *rows: Transaction) -> Decimal:
    resolution = resolve(operation, ((_YEAR, DEVENGO),), rows=rows, modelo="131", period="2T", year=_YEAR)
    (value,) = resolution.binding_values.values()
    return value


def test_an_agrarian_receipt_reaches_the_resolved_volumen(operation: PinnedAuthorityOperation) -> None:
    assert _volumen(operation, _receipt("agri-1", TipoActividad.B01_AGRICOLA)) == _AMOUNT


def test_a_non_agrarian_receipt_stays_out_of_the_resolved_volumen(operation: PinnedAuthorityOperation) -> None:
    assert _volumen(operation, _receipt("prof-1", TipoActividad.A05_PROFESIONALES)) == Decimal("0")


def test_an_untagged_receipt_stays_out_of_the_resolved_volumen(operation: PinnedAuthorityOperation) -> None:
    assert _volumen(operation, _receipt("untagged-1", None)) == Decimal("0")
