"""A listed ledger row serves the rental links it stores, through the real read projection."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....core.external_constants import DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.transactions.tests.rental_link_rows import rental_row
from ..list_operation import ledger_list_row
from ..manual_read import ledger_transaction_payload
from ..transaction_projection import LedgerTransactionProjection, LedgerTransactionReviewProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


def test_a_row_linked_to_a_lease_serves_the_lease_key_and_no_concept() -> None:
    row = ledger_list_row(rental_row(provider_id="income", arrendamiento_ref="lease-2025-a"))

    assert row.transaction.arrendamiento_ref == "lease-2025-a"
    assert row.transaction.inmueble_ref is None
    assert row.transaction.gasto_capital_inmobiliario is None
    assert row.gasto_capital_inmobiliario_words is None
    assert row.gasto_capital_inmobiliario_words_language is None


def test_a_row_linked_to_a_property_serves_its_key_and_the_concept_with_its_words() -> None:
    transaction = rental_row(provider_id="expense", inmueble_ref="finca-1", gasto_capital_inmobiliario="comunidad")

    spanish = ledger_list_row(transaction, language=OutputLanguage.ES)
    english = ledger_list_row(transaction, language=OutputLanguage.EN)

    for row in (spanish, english):
        assert row.transaction.arrendamiento_ref is None
        assert row.transaction.inmueble_ref == "finca-1"
        assert row.transaction.gasto_capital_inmobiliario == "comunidad"
    assert spanish.gasto_capital_inmobiliario_words == "Cuotas de la comunidad de propietarios"
    assert spanish.gasto_capital_inmobiliario_words_language is OutputLanguage.ES
    assert english.gasto_capital_inmobiliario_words == "Owners' association fees"
    assert english.gasto_capital_inmobiliario_words_language is OutputLanguage.EN


def test_a_property_row_without_a_concept_serves_no_words() -> None:
    row = ledger_list_row(rental_row(provider_id="no-concept", inmueble_ref="finca-1"))

    assert row.transaction.inmueble_ref == "finca-1"
    assert row.transaction.gasto_capital_inmobiliario is None
    assert row.gasto_capital_inmobiliario_words is None
    assert row.gasto_capital_inmobiliario_words_language is None


def test_an_unlinked_row_serves_no_rental_fields() -> None:
    row = ledger_list_row(rental_row(provider_id="plain"))

    assert row.transaction.arrendamiento_ref is None
    assert row.transaction.inmueble_ref is None
    assert row.transaction.gasto_capital_inmobiliario is None
    assert row.gasto_capital_inmobiliario_words is None


def test_the_canonical_payload_carries_the_links_and_the_projection_keeps_them() -> None:
    transaction = rental_row(provider_id="expense", inmueble_ref="finca-7", gasto_capital_inmobiliario="suministros")

    payload = ledger_transaction_payload(transaction)
    projection = LedgerTransactionProjection.from_payload(payload)

    assert (payload.arrendamiento_ref, payload.inmueble_ref, payload.gasto_capital_inmobiliario) == (
        None,
        "finca-7",
        "suministros",
    )
    assert projection.model_dump(mode="json")["inmueble_ref"] == "finca-7"
    assert projection.model_dump(mode="json")["gasto_capital_inmobiliario"] == "suministros"


_FORM_ORDER = ["arrendamiento_ref", "inmueble_ref", "gasto_capital_inmobiliario"]
_FAMILY_BY_FIELD = {
    "arrendamiento_ref": "rental_lease",
    "inmueble_ref": "rental_property",
    "gasto_capital_inmobiliario": "gasto_capital_inmobiliario",
}


def _served(row: LedgerTransactionReviewProjection) -> dict[str, tuple[str, str | None, str, OutputLanguage]]:
    return {
        item.field: (item.family, item.value, item.field_words, item.field_words_language)
        for item in row.transaction.link_fields
    }


def test_a_listed_row_serves_every_link_field_in_form_order_with_its_family() -> None:
    row = ledger_list_row(
        rental_row(provider_id="expense", inmueble_ref="finca-1", gasto_capital_inmobiliario="comunidad")
    )

    assert [item.field for item in row.transaction.link_fields] == _FORM_ORDER
    assert {item.field: item.family for item in row.transaction.link_fields} == _FAMILY_BY_FIELD


def test_each_link_field_carries_the_value_the_row_stores_and_none_for_the_rest() -> None:
    row = ledger_list_row(
        rental_row(provider_id="expense", inmueble_ref="finca-1", gasto_capital_inmobiliario="comunidad")
    )

    assert {item.field: item.value for item in row.transaction.link_fields} == {
        "arrendamiento_ref": None,
        "inmueble_ref": "finca-1",
        "gasto_capital_inmobiliario": "comunidad",
    }
    assert row.transaction.inmueble_ref == "finca-1"


def test_a_lease_row_serves_the_lease_key_on_its_own_item() -> None:
    row = ledger_list_row(rental_row(provider_id="income", arrendamiento_ref="lease-2025-a"))

    assert {item.field: item.value for item in row.transaction.link_fields} == {
        "arrendamiento_ref": "lease-2025-a",
        "inmueble_ref": None,
        "gasto_capital_inmobiliario": None,
    }


def test_an_unlinked_row_serves_all_three_items_without_a_value() -> None:
    row = ledger_list_row(rental_row(provider_id="plain"))

    assert [item.field for item in row.transaction.link_fields] == _FORM_ORDER
    assert [item.value for item in row.transaction.link_fields] == [None, None, None]


def test_the_field_words_are_said_in_the_asked_language() -> None:
    transaction = rental_row(provider_id="expense", inmueble_ref="finca-1")

    spanish = _served(ledger_list_row(transaction, language=OutputLanguage.ES))
    english = _served(ledger_list_row(transaction, language=OutputLanguage.EN))

    assert {field: item[2] for field, item in spanish.items()} == {
        "arrendamiento_ref": "Arrendamiento vinculado",
        "inmueble_ref": "Inmueble vinculado",
        "gasto_capital_inmobiliario": "Concepto de gasto del inmueble",
    }
    assert {field: item[2] for field, item in english.items()} == {
        "arrendamiento_ref": "Linked lease",
        "inmueble_ref": "Linked property",
        "gasto_capital_inmobiliario": "Rental expense concept",
    }
    assert {item[3] for item in spanish.values()} == {OutputLanguage.ES}
    assert {item[3] for item in english.values()} == {OutputLanguage.EN}


def test_a_projection_built_without_a_language_names_the_fields_in_the_default_language() -> None:
    projection = LedgerTransactionProjection.from_payload(ledger_transaction_payload(rental_row(provider_id="plain")))

    assert {item.field_words_language for item in projection.link_fields} == {DEFAULT_OUTPUT_LANGUAGE}
    assert projection.link_fields[0].field_words == "Arrendamiento vinculado"


def test_the_link_fields_survive_the_json_round_trip_the_operation_result_takes() -> None:
    row = ledger_list_row(rental_row(provider_id="expense", inmueble_ref="finca-9"), language=OutputLanguage.EN)

    restored = LedgerTransactionReviewProjection.model_validate_json(row.model_dump_json())

    assert restored == row
