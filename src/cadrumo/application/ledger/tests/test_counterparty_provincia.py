"""A counterparty's provincia is stated once, by its INE code, and never guessed.

Modelo 347 declares a Spanish declarado's CÓDIGO PROVINCIA from its domicilio
fiscal, which no invoice holds as a fact. The person states it for the
counterparty, keyed by its NIF like the establishment facts beside it; it is an
answer of its own, so stating it neither needs nor implies a territory, and a
later statement is a correction of the domicilio, not a conflict. Only a code
the INE catalogue declares is taken.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.ine_provincia_catalogue import ine_provincia_names

from ....domain.iva.schema import IvaTerritorialScope
from ..counterparty_establishment import (
    ConfirmedCounterpartyFacts,
    ConfirmedCounterpartyFactsInputError,
    confirmed_counterparty_facts_key,
    record_confirmed_counterparty_facts,
    record_counterparty_provincia,
)
from ..counterparty_establishment_ports import CounterpartyEstablishmentRepositoryProtocol
from ..counterparty_operation import LedgerCounterpartyRequest
from .ledger_value_fixtures import repository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["repository"]

_BUCKET_ID = "36363636-3636-4636-8636-363636363636"
_SUPPLIER_CIF = "B00015016"
_ASSERTED_AT = datetime(2026, 4, 17, 11, 5, tzinfo=UTC)


def _stored(repository: CounterpartyEstablishmentRepositoryProtocol) -> ConfirmedCounterpartyFacts | None:
    key = confirmed_counterparty_facts_key(_SUPPLIER_CIF)
    assert key is not None
    return repository.load(key)


def test_the_catalogue_names_every_province_and_autonomous_city_by_its_ine_code(
    *, operation: PinnedAuthorityOperation
) -> None:
    names = ine_provincia_names(authority=operation)

    assert list(names) == [f"{code:02d}" for code in range(1, 53)]
    assert names["08"] == "Barcelona"
    assert names["01"] == "Araba/Álava"
    assert names["15"] == "Coruña, A"
    assert names["52"] == "Melilla"
    assert "99" not in names


def test_a_provincia_is_remembered_for_the_counterparty_without_any_territory(
    repository: CounterpartyEstablishmentRepositoryProtocol,
) -> None:
    recorded = record_counterparty_provincia(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        provincia_code="08",
        asserted_by="operator",
        asserted_at=_ASSERTED_AT,
        repository=repository,
    )

    assert recorded.provincia_code == "08"
    assert _stored(repository) == recorded
    # Stating where the domicilio fiscal is answers no establishment question.
    assert recorded.declared_fact is None
    assert recorded.declared_identification is None


@pytest.mark.parametrize("code", ["99", "53", "00", "8", "BCN"])
def test_a_code_the_catalogue_does_not_declare_is_refused(
    repository: CounterpartyEstablishmentRepositoryProtocol, code: str
) -> None:
    with pytest.raises(ConfirmedCounterpartyFactsInputError) as refused:
        record_counterparty_provincia(
            bucket_id=_BUCKET_ID,
            tax_identifier=_SUPPLIER_CIF,
            provincia_code=code,
            asserted_by="operator",
            repository=repository,
        )

    assert refused.value.translated_message == "errors.refused.refused_ledger_counterparty_provincia_input"
    assert _stored(repository) is None


def test_a_provincia_keeps_the_confirmed_territory_and_a_new_one_corrects_it(
    repository: CounterpartyEstablishmentRepositoryProtocol,
) -> None:
    canarias = IvaTerritorialScope.from_registry("es_canarias")
    record_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        asserted_by="operator",
        territorial_scope=canarias,
        asserted_at=_ASSERTED_AT,
        repository=repository,
    )

    first = record_counterparty_provincia(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        provincia_code="35",
        asserted_by="operator",
        repository=repository,
    )
    corrected = record_counterparty_provincia(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        provincia_code="38",
        asserted_by="operator",
        repository=repository,
    )

    assert first.territorial_scope == canarias
    assert first.provincia_code == "35"
    assert corrected.territorial_scope == canarias
    assert corrected.provincia_code == "38"
    assert corrected.asserted_at == _ASSERTED_AT
    assert _stored(repository) == corrected


def test_an_establishment_confirmation_keeps_a_stated_provincia(
    repository: CounterpartyEstablishmentRepositoryProtocol,
) -> None:
    record_counterparty_provincia(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        provincia_code="28",
        asserted_by="operator",
        repository=repository,
    )

    confirmed = record_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        asserted_by="operator",
        territorial_scope=IvaTerritorialScope.from_registry("es_mainland"),
        repository=repository,
    )

    assert confirmed.provincia_code == "28"
    assert confirmed.territorial_scope == IvaTerritorialScope.from_registry("es_mainland")


def test_the_provincia_request_carries_only_its_own_answer() -> None:
    profile_id = uuid4()
    request = LedgerCounterpartyRequest(
        profile_id=profile_id,
        action="provincia",
        tax_identifier=_SUPPLIER_CIF,
        provincia_code="08",
        asserted_by="operator",
    )
    assert LedgerCounterpartyRequest.model_validate_json(request.model_dump_json()) == request

    with pytest.raises(ValidationError):
        LedgerCounterpartyRequest(
            profile_id=profile_id, action="provincia", tax_identifier=_SUPPLIER_CIF, asserted_by="operator"
        )
    with pytest.raises(ValidationError):
        LedgerCounterpartyRequest(
            profile_id=profile_id,
            action="provincia",
            tax_identifier=_SUPPLIER_CIF,
            provincia_code="08",
            territorial_scope="es_mainland",
            asserted_by="operator",
        )
    with pytest.raises(ValidationError):
        LedgerCounterpartyRequest(
            profile_id=profile_id,
            action="confirm",
            tax_identifier=_SUPPLIER_CIF,
            territorial_scope="es_mainland",
            provincia_code="08",
            asserted_by="operator",
        )
