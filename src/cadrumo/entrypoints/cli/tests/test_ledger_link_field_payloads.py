"""The CLI payload schemas take the link fields the registered projections serve, through the real conversions."""

from __future__ import annotations

from uuid import UUID

import pytest

from ....application.ledger.entry_options_operation import ledger_entry_options
from ....application.ledger.list_operation import ledger_list_row
from ....application.ledger.manual_read import ledger_transaction_payload
from ....application.ledger.transaction_projection import LedgerTransactionProjection
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.tests.rental_link_rows import rental_row
from ..ledger_results import LedgerEntryOptionsResult, LedgerListRowPayload, TransactionPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = "31313131-3131-4131-8131-313131313131"


def test_the_entry_options_result_carries_the_link_fields_in_form_order_with_family_and_words(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    options = ledger_entry_options(UUID(_PROFILE), operation=authority_operation, language=OutputLanguage.EN)

    served = LedgerEntryOptionsResult.model_validate(options.model_dump(mode="json", exclude={"profile_id"}))

    assert [(item.field, item.family, item.field_words, item.field_words_language) for item in served.link_fields] == [
        ("arrendamiento_ref", "rental_lease", "Linked lease", "en"),
        ("inmueble_ref", "rental_property", "Linked property", "en"),
        ("gasto_capital_inmobiliario", "gasto_capital_inmobiliario", "Rental expense concept", "en"),
    ]


def test_the_transaction_payload_carries_each_link_field_with_the_value_the_row_stores(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    projection = LedgerTransactionProjection.from_payload(
        ledger_transaction_payload(rental_row(provider_id="expense", inmueble_ref="finca-1")),
        language=OutputLanguage.ES,
    )

    served = TransactionPayload.model_validate_json(projection.model_dump_json())

    assert [(item.field, item.family, item.value) for item in served.link_fields] == [
        ("arrendamiento_ref", "rental_lease", None),
        ("inmueble_ref", "rental_property", "finca-1"),
        ("gasto_capital_inmobiliario", "gasto_capital_inmobiliario", None),
    ]
    assert served.link_fields[1].field_words == "Inmueble vinculado"
    assert served.inmueble_ref == "finca-1"


def test_the_list_row_payload_carries_the_link_fields_of_the_listed_row(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    row = ledger_list_row(rental_row(provider_id="income", arrendamiento_ref="lease-1"), language=OutputLanguage.EN)

    served = LedgerListRowPayload.model_validate(
        {
            **row.transaction.model_dump(mode="json"),
            "review_status": row.review_status,
            "full_id": row.transaction.transaction_id,
            "display_id": row.transaction.transaction_id[:12],
            "group_label": row.group_label,
        }
    )

    assert [(item.field, item.value, item.field_words) for item in served.link_fields] == [
        ("arrendamiento_ref", "lease-1", "Linked lease"),
        ("inmueble_ref", None, "Linked property"),
        ("gasto_capital_inmobiliario", None, "Rental expense concept"),
    ]
