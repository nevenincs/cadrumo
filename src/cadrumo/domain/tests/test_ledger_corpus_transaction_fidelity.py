"""Strict domain transaction fidelity for the shared ledger corpus."""

import pytest

from ...tests.test_ledger_corpus_fidelity import _BUILT
from ..transactions.models import Transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_every_row_classified_and_builds_strict_transaction() -> None:
    # Building _BUILT validates every corpus row through Transaction.model_validate.
    assert all(isinstance(tx, Transaction) for tx, _, _ in _BUILT)
