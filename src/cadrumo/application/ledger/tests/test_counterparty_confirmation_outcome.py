"""A confirmation says whether THIS call recorded it, rather than leaving callers to infer.

The writer is idempotent on the whole record: a repeat carrying the same answer
returns the stored fact with its ORIGINAL ``asserted_at`` and ``asserted_by``,
so a second operator running the verb learns the question was already settled
and by whom. Every surface used to reconstruct that by generating its own
timestamp and comparing it against what came back — knowledge the writer
already had, re-derived at each caller.

Also pinned here: a confirmation answering neither axis is refused before any
write. Territory and identification are separate questions, and a record whose
only content is that someone ran the verb is not a fact a later document can be
classified against.
"""

from __future__ import annotations

import pytest

from ....domain.iva.classification import IvaTerritorialScope
from ....domain.iva.schema import EUMemberState
from ..counterparty_establishment import (
    ConfirmedCounterpartyFactsInputError,
    confirm_counterparty_establishment,
)
from ..counterparty_establishment_ports import CounterpartyEstablishmentRepositoryProtocol
from ._ledger_value_fixtures import repository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["repository"]

_BUCKET = "99999999-9999-4999-8999-999999999999"
_IDENTIFIER = "B12345674"


def test_a_first_confirmation_reports_that_it_recorded(
    repository: CounterpartyEstablishmentRepositoryProtocol,
) -> None:
    """The baseline the repeat case is measured against."""
    outcome = confirm_counterparty_establishment(
        bucket_id=_BUCKET,
        tax_identifier=_IDENTIFIER,
        asserted_by="operator-a",
        territorial_scope=IvaTerritorialScope.ES_MAINLAND,
        repository=repository,
    )

    assert outcome.recorded is True
    assert outcome.facts.territorial_scope is IvaTerritorialScope.ES_MAINLAND
    assert outcome.facts.asserted_by == "operator-a"


def test_a_repeat_of_the_same_answer_reports_that_it_did_not_record(
    repository: CounterpartyEstablishmentRepositoryProtocol,
) -> None:
    """The distinction the outcome exists for.

    A repeat must not read as a fresh confirmation: the stored provenance is
    what a second operator needs to see, and reporting ``recorded`` would claim
    an authorship this call does not have.
    """
    first = confirm_counterparty_establishment(
        bucket_id=_BUCKET,
        tax_identifier=_IDENTIFIER,
        asserted_by="operator-a",
        territorial_scope=IvaTerritorialScope.ES_MAINLAND,
        repository=repository,
    )
    second = confirm_counterparty_establishment(
        bucket_id=_BUCKET,
        tax_identifier=_IDENTIFIER,
        asserted_by="operator-b",
        territorial_scope=IvaTerritorialScope.ES_MAINLAND,
        repository=repository,
    )

    assert first.recorded is True
    assert second.recorded is False
    assert second.facts.asserted_by == "operator-a", "the original author must survive a repeat"
    assert second.facts.asserted_at == first.facts.asserted_at


def test_an_identification_only_confirmation_is_accepted(
    repository: CounterpartyEstablishmentRepositoryProtocol,
) -> None:
    """Identification is its own axis, answerable without a territory."""
    outcome = confirm_counterparty_establishment(
        bucket_id=_BUCKET,
        tax_identifier=_IDENTIFIER,
        asserted_by="operator-a",
        identification_state=EUMemberState.ES,
        repository=repository,
    )

    assert outcome.recorded is True
    assert outcome.facts.identification_state is EUMemberState.ES
    assert outcome.facts.territorial_scope is None


def test_answering_neither_axis_is_refused(
    repository: CounterpartyEstablishmentRepositoryProtocol,
) -> None:
    """A confirmation with no content is not a confirmation."""
    with pytest.raises(ConfirmedCounterpartyFactsInputError):
        confirm_counterparty_establishment(
            bucket_id=_BUCKET,
            tax_identifier=_IDENTIFIER,
            asserted_by="operator-a",
            repository=repository,
        )


def test_a_refused_confirmation_writes_nothing(
    repository: CounterpartyEstablishmentRepositoryProtocol,
) -> None:
    """The refusal fires before persistence, not after a partial write."""
    with pytest.raises(ConfirmedCounterpartyFactsInputError):
        confirm_counterparty_establishment(
            bucket_id=_BUCKET,
            tax_identifier=_IDENTIFIER,
            asserted_by="operator-a",
            repository=repository,
        )

    recorded = confirm_counterparty_establishment(
        bucket_id=_BUCKET,
        tax_identifier=_IDENTIFIER,
        asserted_by="operator-a",
        territorial_scope=IvaTerritorialScope.ES_MAINLAND,
        repository=repository,
    )

    # A confirmation landing as a first write proves the refused call stored
    # nothing; had it written, this would have come back as a repeat.
    assert recorded.recorded is True
