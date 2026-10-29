"""A book whose column model could not be asked refuses with the same sentence as a bank file.

The book is a real fixture whose column names only the mapping lane reads. Both
import lanes word the refusal through one translated reason.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from cadrumo.tests.english_locale_fixture import english_locale_fixture

from ....core.errors.error_codes import resolve_error_message
from ....core.field_role import FieldRole
from ....core.model_roles import ModelRole
from ....tests.inventory import FIXTURES_DIR
from ...ledger.column_roles import ColumnRoleReaderUnavailable
from ...ledger.import_ports import LedgerImportReaderUnavailableError
from ...probe_outcomes import ProbePreconditionCondition, probe_no_recovery_verdict
from ...reader_refusal_wording import column_reader_refusal_reason
from ..bulk_import import read_bulk_invoice_import_source

__all__ = ["english_locale_fixture"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LIBRO = FIXTURES_DIR / "financial" / "tabular-dialects" / "libro_facturas_expedidas_2025_2026.csv"


def _unavailable_reader() -> ColumnRoleReaderUnavailable:
    verdict = probe_no_recovery_verdict(
        ProbePreconditionCondition.ROLE_MODEL_INSTALLED,
        facts={"role": ModelRole.COLUMN_ROLE_MAPPING.value, "runtime_reachable": True, "role_model_installed": False},
    )
    return ColumnRoleReaderUnavailable(precondition_verdict=verdict)


def test_the_book_refusal_states_that_the_column_model_is_unavailable() -> None:
    unavailable = _unavailable_reader()

    def mapper(headers: Sequence[str]) -> Sequence[FieldRole] | ColumnRoleReaderUnavailable | None:
        del headers
        return unavailable

    with pytest.raises(LedgerImportReaderUnavailableError) as raised:
        read_bulk_invoice_import_source(_LIBRO, mapper=mapper)

    reason = column_reader_refusal_reason(locale="en")
    assert raised.value.context == {"reason": reason}
    assert resolve_error_message(raised.value, locale="en") == f"The ledger file cannot be imported: {reason}"
    assert "not available" in reason
