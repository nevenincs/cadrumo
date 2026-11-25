"""A personal row stored with business figures still reads, counts for nothing, and loses them on its next write.

Rows written before personal rows were refused business figures can hold a
spending category, a taxable base, IVA or an activity IRPF category. These
tests store such a row in the real encrypted catalogue, as only a key holder
could, and read it back through the repository and the calculations that
consume it: every read admits it without the figures, the quarterly expense
and IVA aggregations take nothing from it, saving an untouched catalogue keeps
its bytes, and the row's next write persists the figures' absence.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from .....application.aggregation.iva_ledger import aggregate_iva_ledger_observations_from_repositories
from .....application.aggregation.renta_gasto_ledger import aggregate_renta_gasto_ledger_from_repositories
from .....application.aggregation.tests.ledger_transaction_support import iva_transaction
from .....application.aggregation.tests.renta_gasto_aggregation_support import gasto_transaction
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.period import Period
from .....domain.bienes_inversion.register import BienesInversionIvaRegister
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.transactions.classification_effects import fields_refused_by_classification
from .....domain.transactions.enums import BusinessClassification, TransactionDirection
from .....domain.transactions.errors import TransactionFiguresWithoutBusinessError
from .....domain.transactions.models import Transaction, TransactionCatalogue
from .....domain.transactions.repository import transaction_object_key
from ...storage.secure_object_namespaces import TRANSACTION_CATALOGUE_NAMESPACE
from ...storage.sql.secure_objects import SecureObjectRepository
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..invoices import InvoiceCatalogueRepository
from ..prorrata_register import ProrrataRegisterRepository
from ..transactions import TransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]
_JSON_OBJECT = TypeAdapter(dict[str, object])

_BUCKET_ID = "3c9e2f41-6a0b-4d7e-9f15-8b2a4c6d0e71"
_PERSONAL = BusinessClassification.PERSONAL
_M130_GASTOS: CasillaId = validated_casilla_id("02")
_EXERCISE = filing_year_envelope().horizon
_Q1 = Period.from_year_and_code(_EXERCISE, "1T")


@pytest.fixture
def objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _repository(objects: SecureObjectRepository) -> TransactionCatalogueRepository:
    return TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)


def _stored_payload(objects: SecureObjectRepository, transaction_id: str) -> bytes:
    record = objects.load(
        TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        transaction_object_key(_BUCKET_ID, transaction_id),
        expected_class=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
        max_supported_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
    )
    assert record is not None
    return record.payload


def _stored_row(objects: SecureObjectRepository, transaction_id: str) -> dict[str, object]:
    envelope = _JSON_OBJECT.validate_json(_stored_payload(objects, transaction_id))
    return _JSON_OBJECT.validate_python(envelope["payload"])


def _relabel_as_personal(objects: SecureObjectRepository, transaction_id: str) -> None:
    """Re-encrypt a stored business row as personal, keeping every figure it carries."""
    object_key = transaction_object_key(_BUCKET_ID, transaction_id)
    record = objects.load(
        TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        object_key,
        expected_class=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
        max_supported_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
    )
    assert record is not None
    envelope = json.loads(record.payload)
    envelope["payload"]["business_classification"] = _PERSONAL.value
    objects.save(
        namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        object_key=object_key,
        classification=record.classification,
        schema_version=record.schema_version,
        written_at=record.written_at,
        payload=json.dumps(envelope).encode("utf-8"),
    )


def _activity_expense(provider_id: str, classification: BusinessClassification, base: str) -> Transaction:
    return gasto_transaction(
        provider_id,
        value_date=date(_EXERCISE, 2, 1),
        amount=Decimal(base),
        taxable_base=Decimal(base),
        irpf_category="actividad_economica",
        business_classification=classification,
    )


def _store_legacy_personal_expense(objects: SecureObjectRepository) -> tuple[Transaction, Transaction]:
    """Store an activity-marked expense, relabel it personal, and store an undecided marked control row."""
    legacy = _activity_expense("legacy-personal", BusinessClassification.BUSINESS, "180.00")
    undecided = _activity_expense("still-undecided", BusinessClassification.NOT_YET_PROCESSED, "120.00")
    _repository(objects).save(TransactionCatalogue.from_transactions((legacy, undecided)))
    _relabel_as_personal(objects, legacy.transaction_id)
    return legacy, undecided


def _assert_read_without_figures(row: Transaction, stored: Transaction) -> None:
    assert row.business_classification is _PERSONAL
    assert all(getattr(row, name) is None for name in fields_refused_by_classification(_PERSONAL))
    assert row.transaction_id == stored.transaction_id
    assert row.raw == stored.raw
    assert row.direction is stored.direction


def test_every_read_admits_a_stored_personal_row_without_its_business_figures(
    objects: SecureObjectRepository,
) -> None:
    legacy, _ = _store_legacy_personal_expense(objects)
    assert _stored_row(objects, legacy.transaction_id)["category_id"] == "asesoria_fiscal"

    loaded = _repository(objects).load().transactions[legacy.transaction_id]
    validated = _repository(objects).load_fully_validated().transactions[legacy.transaction_id]
    targeted = _repository(objects).load_by_ids([legacy.transaction_id]).transactions[legacy.transaction_id]

    for row in (loaded, validated, targeted):
        _assert_read_without_figures(row, legacy)
    assert loaded == validated == targeted


def test_saving_an_untouched_catalogue_keeps_the_stored_bytes(objects: SecureObjectRepository) -> None:
    """Reading withholds the figures; it does not rewrite the row that holds them."""
    legacy, _ = _store_legacy_personal_expense(objects)
    before = _stored_payload(objects, legacy.transaction_id)

    repository = _repository(objects)
    repository.save(repository.load())

    assert _stored_payload(objects, legacy.transaction_id) == before


def test_the_rows_next_write_persists_the_absence_of_its_business_figures(objects: SecureObjectRepository) -> None:
    legacy, _ = _store_legacy_personal_expense(objects)
    repository = _repository(objects)
    current = repository.load().transactions[legacy.transaction_id]

    edited = current.model_copy(update={"notes": "reviewed"})
    repository.replace_if_current_with_secure_object_writes(current, edited, ())

    stored = _stored_row(objects, legacy.transaction_id)
    assert stored["business_classification"] == _PERSONAL.value
    assert stored["notes"] == "reviewed"
    assert all(stored[name] is None for name in fields_refused_by_classification(_PERSONAL))
    assert _repository(objects).load_fully_validated().transactions[legacy.transaction_id] == edited


def test_a_copied_personal_row_with_a_business_figure_is_refused_before_any_byte_is_written(
    objects: SecureObjectRepository,
) -> None:
    legacy, _ = _store_legacy_personal_expense(objects)
    repository = _repository(objects)
    current = repository.load().transactions[legacy.transaction_id]
    before = _stored_payload(objects, legacy.transaction_id)

    with pytest.raises(TransactionFiguresWithoutBusinessError):
        repository.replace_if_current_with_secure_object_writes(
            current, current.model_copy(update={"category_id": "asesoria_fiscal"}), ()
        )

    assert _stored_payload(objects, legacy.transaction_id) == before


def _m130_expenses(objects: SecureObjectRepository):
    return aggregate_renta_gasto_ledger_from_repositories(
        bucket_id=_BUCKET_ID,
        period=_Q1,
        modelo="130",
        target_casilla_id=_M130_GASTOS,
        accept_activity_marker=True,
        transaction_repository=_repository(objects),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=objects),
    )


def test_a_stored_personal_row_contributes_no_quarterly_expense(objects: SecureObjectRepository) -> None:
    """The activity marker would make the row a pago fraccionado expense; withheld, it counts for nothing."""
    legacy = _activity_expense("legacy-personal", BusinessClassification.BUSINESS, "180.00")
    undecided = _activity_expense("still-undecided", BusinessClassification.NOT_YET_PROCESSED, "120.00")
    _repository(objects).save(TransactionCatalogue.from_transactions((legacy, undecided)))
    as_business = _m130_expenses(objects)
    assert {item.transaction_id for item in as_business.observations} == {
        legacy.transaction_id,
        undecided.transaction_id,
    }

    _relabel_as_personal(objects, legacy.transaction_id)
    as_personal = _m130_expenses(objects)

    assert {item.transaction_id for item in as_personal.observations} == {undecided.transaction_id}
    assert as_personal.casilla_aggregation.casilla_values[_M130_GASTOS] == Decimal("120.00")
    assert as_personal.issues == ()


def test_a_stored_personal_row_contributes_no_iva_observation(
    objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    legacy = iva_transaction(
        "legacy-personal-iva",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    business = iva_transaction(
        "business-iva",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("242.00"),
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
    )
    _repository(objects).save(TransactionCatalogue.from_transactions((legacy, business)))
    _relabel_as_personal(objects, legacy.transaction_id)

    aggregation = aggregate_iva_ledger_observations_from_repositories(
        bucket_id=_BUCKET_ID,
        period=Period.from_year_and_code(legacy.raw.booked_date.year, "1T"),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=objects),
        transaction_repository=_repository(objects),
        invoice_reader=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=_BUCKET_ID,
        operation=operation,
    )

    assert {observation.ledger_id for observation in aggregation.observations} == {business.transaction_id}
    assert sum((observation.base_amount for observation in aggregation.observations), Decimal("0")) == Decimal("200.00")
