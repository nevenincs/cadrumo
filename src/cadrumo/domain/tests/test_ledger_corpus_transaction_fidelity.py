"""Strict domain transaction fidelity for the shared ledger corpus."""

import pytest

from ...tests import test_ledger_corpus_fidelity as ledger_corpus_fidelity
from ..transactions.models import Transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_every_row_classified_and_builds_strict_transaction() -> None:
    # Building the private corpus fixture validates every row through
    # Transaction.model_validate. Read it through the support module because
    # this test intentionally verifies that fixture rather than publishing it.
    built = vars(ledger_corpus_fidelity)["_BUILT"]
    assert all(isinstance(tx, Transaction) for tx, _, _ in built)
