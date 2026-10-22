"""Art. 109 coverage refuses an income concept the pinned vocabulary does not declare.

The net-of-subvenciones base asked only whether a concept was excluded, so a
stored concept a later authority retired stayed in the denominator as ordinary
income. That moved the 70 per cent ratio on a receipt no authority classifies.
The coverage now refuses with the row named, and an admitted concept still
lands where art. 109.3/109.4 puts it.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.concepto_ingreso import ConceptoIngreso
from ....core.period import Period
from ....core.tipos_actividad import TipoActividad
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.irpf_categories import ledger_irpf_category_catalogue
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.tipo_actividad_partitions import tipo_actividad_code_set
from ...aggregation.errors import UnacceptedLedgerRegistryValueError
from ...aggregation.tests.renta_income_aggregation_support import raw_transaction
from .._art109_activity_income import (
    Art109ActivityIncomeCoverage,
    Art109ActivityIncomeCoverageStatus,
    derive_art109_activity_income_coverage,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ART_109_EXEMPT = "rd-439-2007-art-109:selector-m036-actividades-exencion-pago-fraccionado"
_ART_109_NET_BASE = "rd-439-2007-art-109:selector-m036-actividades-base-neta-de-subvenciones"
_PERIOD = Period.from_year_and_code(2025, "1T")
_IN_WINDOW = datetime(2025, 2, 10, 12, 0, tzinfo=UTC).date()
_RETIRED = ConceptoIngreso.from_registry("retired_concept")


@pytest.fixture
def pinned() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _activity_irpf_category() -> str:
    return next(
        descriptor.id
        for descriptor in ledger_irpf_category_catalogue()
        if descriptor.purpose == "activity_income_withholding"
    )


def _withheld_receipt(provider_id: str, *, tipo_actividad: TipoActividad, concepto_ingreso: str) -> Transaction:
    """One activity receipt whose invoice gross exceeds the cash, so its retención is proved."""
    amount = Decimal("1000.00")
    return Transaction.model_validate(
        {
            "raw": raw_transaction(
                provider_id,
                booked_date=_IN_WINDOW,
                value_date=_IN_WINDOW,
                amount=amount - Decimal("20.00"),
                currency="EUR",
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": _activity_irpf_category(),
            "taxable_base": amount,
            "iva_amount": Decimal("0.00"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2025, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
            "tipo_actividad": tipo_actividad,
            "concepto_ingreso": ConceptoIngreso.from_registry(concepto_ingreso),
        },
    )


def _stale(row: Transaction) -> Transaction:
    """Hand the row back carrying a concept no admission re-checked, as a stale stored row arrives."""
    values = {name: getattr(row, name) for name in Transaction.model_fields} | {"concepto_ingreso": _RETIRED}
    return Transaction.model_construct(_fields_set=row.model_fields_set | {"concepto_ingreso"}, **values)


def _coverage(row: Transaction, operation: PinnedAuthorityOperation) -> Art109ActivityIncomeCoverage:
    catalogue = TransactionCatalogue.model_construct(transactions={row.transaction_id: row})
    return derive_art109_activity_income_coverage(catalogue, period=_PERIOD, operation=operation)


def test_an_undeclared_concept_in_the_net_of_subvenciones_base_is_refused(pinned: PinnedAuthorityOperation) -> None:
    admitted = _withheld_receipt("agricola", tipo_actividad=TipoActividad.B01_AGRICOLA, concepto_ingreso="ordinario")
    accepted = _coverage(admitted, pinned)
    assert accepted.status is Art109ActivityIncomeCoverageStatus.PROVEN
    assert accepted.denominator == Decimal("1000.00")
    assert accepted.numerator == Decimal("1000.00")

    stale = _stale(admitted)
    with pytest.raises(UnacceptedLedgerRegistryValueError) as refusal:
        _coverage(stale, pinned)

    assert refusal.value.context == {
        "field": "concepto_ingreso",
        "value": "retired_concept",
        "transaction_id": stale.transaction_id,
        "effective_date": _PERIOD.end_date.isoformat(),
    }


def test_an_admitted_subvencion_still_leaves_the_base(pinned: PinnedAuthorityOperation) -> None:
    corriente = _withheld_receipt(
        "agricola-corriente",
        tipo_actividad=TipoActividad.B01_AGRICOLA,
        concepto_ingreso="subvencion_corriente",
    )

    coverage = _coverage(corriente, pinned)

    assert coverage.status is Art109ActivityIncomeCoverageStatus.INSUFFICIENT
    assert coverage.reason == "current_period_activity_income_absent"


def test_an_activity_whose_base_ignores_the_concept_is_not_refused(pinned: PinnedAuthorityOperation) -> None:
    """Only the net-of-subvenciones classes read the concept, so another exempt class is untouched."""
    exempt = tipo_actividad_code_set(_ART_109_EXEMPT, effective_date=_PERIOD.end_date, authority=pinned)
    net_base = tipo_actividad_code_set(_ART_109_NET_BASE, effective_date=_PERIOD.end_date, authority=pinned)
    gross_base_activity = TipoActividad(sorted(exempt - net_base)[0])
    admitted = _withheld_receipt("gross-base", tipo_actividad=gross_base_activity, concepto_ingreso="ordinario")

    assert _coverage(_stale(admitted), pinned) == _coverage(admitted, pinned)
