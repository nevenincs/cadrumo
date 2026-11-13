"""A listed ledger row serves the rental links it stores, through the real read projection."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.transactions.tests.rental_link_rows import rental_row
from ..list_operation import ledger_list_row
from ..manual_read import ledger_transaction_payload
from ..transaction_projection import LedgerTransactionProjection

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
