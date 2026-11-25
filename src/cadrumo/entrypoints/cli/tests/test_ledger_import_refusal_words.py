"""The import command names why a statement was refused, not only that it was.

A statement in a format whose reader this installation lacks, and one that
names no account to register, each read in their own words; any other refusal
keeps the generic wording.
"""

from __future__ import annotations

from typing import Literal

import pytest

from ....application.ledger.import_operation import LedgerImportFileRefusal
from ....core.i18n.render import tr
from .. import ledger_import_commands

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FILE = "statement.ofx"


@pytest.mark.parametrize(
    ("reason_code", "key"),
    [
        ("format_not_installed", "cli.ledger.import.file_refused_format_not_installed"),
        ("statement_account_missing", "cli.ledger.import.file_refused_statement_account_missing"),
        ("own_account_mismatch", "cli.ledger.import.file_refused_account_mismatch"),
        ("transaction_validation", "cli.ledger.import.file_refused"),
    ],
)
def test_a_refused_statement_is_worded_by_its_cause(
    reason_code: Literal[
        "format_not_installed", "statement_account_missing", "own_account_mismatch", "transaction_validation"
    ],
    key: str,
) -> None:
    refusal = LedgerImportFileRefusal(file_name=_FILE, reason_code=reason_code)

    worded = ledger_import_commands._refusal_message(refusal)

    assert worded == tr(key, file=_FILE)
    assert _FILE in worded
