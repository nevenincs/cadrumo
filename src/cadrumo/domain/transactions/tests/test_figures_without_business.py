"""A personal row never carries business figures; a stored one that does is read without them.

A row classified as personal has no business component, so a spending category,
a taxable base, IVA or any other business figure on it states something the
classification denies. Building such a row is refused with a registered,
worded refusal. A row stored before the refusal existed still reads: the stored
decode admits it and every reader sees the refused figures as absent.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.errors.error_codes import get_registered_error_code, resolve_error_message
from ....core.external_constants import OutputLanguage
from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.governed_fact_scope import validating_governed_facts
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ...iva.vehicle_use import IvaVehicleUse
from ..classification_effects import fields_refused_by_classification
from ..classification_origin import ClassificationOrigin
from ..enums import BusinessClassification, TransactionDirection
from ..errors import TransactionFiguresWithoutBusinessError, TransactionValidationError
from ..m210_income_classification import M210IncomeClassification
from ..models import (
    Transaction,
    TransactionCatalogue,
    require_no_figures_without_business,
    validate_authenticated_stored_transaction_json,
    validate_stored_transaction_json,
    withhold_figures_without_business,
)
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..service import set_classification

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("authority_operation")]

_PERSONAL = BusinessClassification.PERSONAL
_BOOKED = date(filing_year_envelope().horizon, 4, 10)

#: The operator's rule, stated independently of the code that enforces it: a
#: personal row carries no spending category, no IVA or IRPF figure, no Modelo
#: 210 income, no prorrata reference, no vehicle use and no business share.
_PERSONAL_REFUSES = frozenset(
    {
        "business_pct",
        "category_id",
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "recargo_amount",
        "irpf_category",
        "m210_income_classification",
        "prorrata_reference",
        "iva_vehicle_use",
        "usage_ratio_id",
    }
)


def _row(classification: BusinessClassification, **fields: object) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="synthetic-personal-row",
                booked_date=_BOOKED,
                amount=Decimal("121.00"),
                currency="EUR",
                description="synthetic row",
                provenance=RawProvenance(
                    source_path=Path("synthetic-personal.csv"),
                    source_sha256="d" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(_BOOKED.year, 4, 14, 9, 30, tzinfo=UTC),
                    provider_name="csv",
                ),
                raw_fields={"source": "synthetic"},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": classification,
            "classified_by": "manual",
            "classification_origin": ClassificationOrigin.PERSON,
            **fields,
        },
    )


def _figure(name: str, operation: PinnedAuthorityOperation) -> object:
    """A value each refused field validly takes on a business row."""
    if name == "m210_income_classification":
        with validating_governed_facts(operation):
            return M210IncomeClassification(
                official_tipo_renta_code="01",
                gross_income_amount=Decimal("1000.00"),
                applicable_rate=Decimal("0.19"),
            )
    return {
        "category_id": "material_oficina",
        "taxable_base": Decimal("100.00"),
        "iva_rate": Decimal("0.21"),
        "iva_amount": Decimal("21.00"),
        "recargo_amount": Decimal("5.20"),
        "irpf_category": "actividad_economica",
        "prorrata_reference": "synthetic-prorrata",
        "iva_vehicle_use": IvaVehicleUse.SURVEILLANCE,
        "usage_ratio_id": "synthetic-ratio",
    }[name]


def _refusal(error: ValidationError) -> BaseException | None:
    """The registered failure the validator translated for Pydantic."""
    translated = error.errors()[0].get("ctx", {}).get("error")
    return translated.__cause__ if isinstance(translated, BaseException) else None


def test_a_personal_row_refuses_exactly_the_figures_a_personal_classification_drops() -> None:
    assert fields_refused_by_classification(_PERSONAL) == _PERSONAL_REFUSES


@pytest.mark.parametrize("name", sorted(_PERSONAL_REFUSES - {"business_pct"}))
def test_building_a_personal_row_with_a_business_figure_is_refused_by_name(
    name: str, authority_operation: PinnedAuthorityOperation
) -> None:
    with pytest.raises(ValidationError) as caught:
        _row(_PERSONAL, **{name: _figure(name, authority_operation)})

    refusal = _refusal(caught.value)
    assert isinstance(refusal, TransactionFiguresWithoutBusinessError)
    assert refusal.context is not None
    assert refusal.context["fields"] == name
    assert get_registered_error_code(refusal).code == "REFUSED_TRANSACTION_FIGURES_WITHOUT_BUSINESS"


def test_a_business_share_on_a_personal_row_stays_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        _row(_PERSONAL, business_pct=Decimal("0.5"))

    assert isinstance(_refusal(caught.value), TransactionValidationError)


@pytest.mark.parametrize(
    "classification",
    [BusinessClassification.BUSINESS, BusinessClassification.NOT_YET_PROCESSED],
)
def test_a_business_row_and_a_row_nobody_decided_keep_their_figures(
    classification: BusinessClassification,
) -> None:
    """Only a decision that the row has no business part refuses figures; staged figures await it."""
    row = _row(
        classification,
        category_id="material_oficina",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
    )

    assert row.category_id == "material_oficina"
    assert row.taxable_base == Decimal("100.00")
    assert fields_refused_by_classification(classification) == frozenset()


def test_the_refusal_is_worded_in_every_language_the_backend_serves() -> None:
    refusal = TransactionFiguresWithoutBusinessError(
        "a PERSONAL row carries no business figures; refused: category_id",
        context={"business_classification": "PERSONAL", "fields": "category_id"},
    )
    key = get_registered_error_code(refusal).message_key
    sentences = {language: resolve_error_message(refusal, locale=language.value) for language in OutputLanguage}

    assert all(sentence and sentence != key for sentence in sentences.values())
    assert len(set(sentences.values())) == len(sentences)
    assert all("category_id" not in sentence for sentence in sentences.values())


def _legacy_payload(classification: BusinessClassification = _PERSONAL) -> tuple[Transaction, bytes]:
    """A business row's stored bytes relabelled as personal, as rows written before the refusal were."""
    business = _row(
        BusinessClassification.BUSINESS,
        category_id="material_oficina",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
        irpf_category="actividad_economica",
        notes="kept",
    )
    payload = business.model_dump_json().replace('"BUSINESS"', f'"{classification.value}"', 1).encode("utf-8")
    return business, payload


def test_a_stored_personal_row_with_business_figures_still_decodes() -> None:
    business, payload = _legacy_payload()

    with pytest.raises(ValidationError):
        Transaction.model_validate_json(payload)
    stored = validate_stored_transaction_json(Transaction, payload)
    authenticated = validate_authenticated_stored_transaction_json(Transaction, payload)

    assert stored == authenticated
    assert stored.business_classification is _PERSONAL
    assert stored.category_id == business.category_id


def test_a_reader_sees_a_stored_personal_row_without_its_business_figures() -> None:
    business, payload = _legacy_payload()
    stored = validate_stored_transaction_json(Transaction, payload)

    read = withhold_figures_without_business(stored)

    assert all(getattr(read, name) is None for name in _PERSONAL_REFUSES)
    assert read.transaction_id == business.transaction_id
    assert read.raw == business.raw
    assert read.notes == "kept"
    assert read.direction is business.direction
    # What remains is a row any write of its classification would accept.
    assert Transaction.model_validate(read.model_dump(mode="python")) == read
    require_no_figures_without_business(read)


def test_a_row_with_nothing_withheld_is_read_as_the_same_instance() -> None:
    row = _row(BusinessClassification.BUSINESS, category_id="material_oficina")

    assert withhold_figures_without_business(row) is row


def test_the_write_boundary_refuses_a_copied_personal_row_with_a_figure() -> None:
    copied = _row(_PERSONAL).model_copy(update={"category_id": "material_oficina"})

    with pytest.raises(TransactionFiguresWithoutBusinessError):
        require_no_figures_without_business(copied)


def test_classifying_a_business_row_as_personal_drops_its_figures_and_keeps_the_history() -> None:
    business = _row(
        BusinessClassification.BUSINESS,
        category_id="material_oficina",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
    )
    catalogue = TransactionCatalogue.from_transactions([business])

    updated = set_classification(
        catalogue,
        business.transaction_id,
        classification=_PERSONAL,
        classified_by="manual",
        origin=ClassificationOrigin.PERSON,
    )
    personal = updated.transactions[business.transaction_id]

    assert personal.business_classification is _PERSONAL
    assert all(getattr(personal, name) is None for name in _PERSONAL_REFUSES)
    assert personal.classification_history[-1].category_id == "material_oficina"


def test_naming_a_category_with_a_personal_classification_is_refused_not_dropped() -> None:
    catalogue = TransactionCatalogue.from_transactions([_row(BusinessClassification.NOT_YET_PROCESSED)])
    transaction_id = next(iter(catalogue.transactions))

    with pytest.raises(TransactionFiguresWithoutBusinessError):
        set_classification(
            catalogue,
            transaction_id,
            classification=_PERSONAL,
            category_id="material_oficina",
            classified_by="manual",
            origin=ClassificationOrigin.PERSON,
        )
