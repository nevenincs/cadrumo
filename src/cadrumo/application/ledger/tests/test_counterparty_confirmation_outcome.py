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

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from ....domain.iva.classification import IvaTerritorialScope
from ....domain.iva.schema import EUMemberState
from ....tests.secure_sql import isolated_runtime_profile
from ..counterparty_establishment import (
    ConfirmedCounterpartyFactsInputError,
    ConfirmedCounterpartyFactsRepository,
    confirm_counterparty_establishment,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "99999999-9999-4999-8999-999999999999"
_IDENTIFIER = "B12345674"


@contextmanager
def _store() -> Iterator[ConfirmedCounterpartyFactsRepository]:
    """The real confirmed-facts repository over isolated encrypted storage.

    Idempotency is a property of the store, so a stand-in would be asserting
    the substitute's behaviour rather than the writer's.
    """
    with TemporaryDirectory() as tmp, isolated_runtime_profile(tmp_path=Path(tmp), bucket_id=_BUCKET):
        yield ConfirmedCounterpartyFactsRepository()


def test_a_first_confirmation_reports_that_it_recorded() -> None:
    """The baseline the repeat case is measured against."""
    with _store() as repository:
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


def test_a_repeat_of_the_same_answer_reports_that_it_did_not_record() -> None:
    """The distinction the outcome exists for.

    A repeat must not read as a fresh confirmation: the stored provenance is
    what a second operator needs to see, and reporting ``recorded`` would claim
    an authorship this call does not have.
    """
    with _store() as repository:
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


def test_an_identification_only_confirmation_is_accepted() -> None:
    """Identification is its own axis, answerable without a territory."""
    with _store() as repository:
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


def test_answering_neither_axis_is_refused() -> None:
    """A confirmation with no content is not a confirmation."""
    with _store() as repository, pytest.raises(ConfirmedCounterpartyFactsInputError):
        confirm_counterparty_establishment(
            bucket_id=_BUCKET,
            tax_identifier=_IDENTIFIER,
            asserted_by="operator-a",
            repository=repository,
        )


def test_a_refused_confirmation_writes_nothing() -> None:
    """The refusal fires before persistence, not after a partial write."""
    with _store() as repository:
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
