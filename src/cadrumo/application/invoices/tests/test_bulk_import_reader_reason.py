"""A book whose column model could not be asked refuses with the same sentence as a bank file.

The verdict comes from the real reader probe asking a closed runtime port; the
book is a real fixture whose column names only the mapping lane reads. Both
import lanes word the refusal through one translated reason.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from cadrumo.tests.english_locale_fixture import english_locale_fixture

from ....core.config import Settings
from ....core.errors.error_codes import resolve_error_message
from ....core.field_role import FieldRole
from ....core.model_roles import ModelRole
from ....tests.inventory import FIXTURES_DIR
from ...dependency_wording import column_reader_refusal_reason
from ...ledger.column_roles import ColumnRoleReaderUnavailable
from ...ledger.import_ports import LedgerImportReaderUnavailableError
from ...local_reader import probe_local_ai_program
from ...provisioning_contracts import ProvisioningPreconditionCondition, provisioning_no_recovery_verdict
from ..bulk_import import read_bulk_invoice_import_source

__all__ = ["english_locale_fixture"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LIBRO = FIXTURES_DIR / "financial" / "tabular-dialects" / "libro_facturas_expedidas_2025_2026.csv"
_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"


def _unanswering_reader() -> ColumnRoleReaderUnavailable:
    status = probe_local_ai_program(Settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT))
    assert status.precondition_verdict is not None
    return ColumnRoleReaderUnavailable(precondition_verdict=status.precondition_verdict)


def test_the_book_refusal_names_local_ai_and_its_setup() -> None:
    unavailable = _unanswering_reader()

    def mapper(headers: Sequence[str]) -> Sequence[FieldRole] | ColumnRoleReaderUnavailable | None:
        del headers
        return unavailable

    with pytest.raises(LedgerImportReaderUnavailableError) as raised:
        read_bulk_invoice_import_source(_LIBRO, mapper=mapper)

    reason = column_reader_refusal_reason(unavailable.precondition_verdict, locale="en")
    assert raised.value.context == {"reason": reason}
    assert resolve_error_message(raised.value, locale="en") == f"The ledger file cannot be imported: {reason}"
    assert reason.startswith("Local AI")
    assert reason.endswith("Set it up in the Cadrumo desktop app, then try again.")


def test_a_role_this_computer_cannot_run_offers_no_setup() -> None:
    verdict = provisioning_no_recovery_verdict(
        ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE,
        facts={"role": ModelRole.COLUMN_ROLE_MAPPING.value, "runtime_reachable": True, "role_model_selected": False},
    )

    reason = column_reader_refusal_reason(verdict, locale="en")

    assert reason.startswith("Local AI")
    assert "set it up" not in reason.lower()
    assert reason != column_reader_refusal_reason(_unanswering_reader().precondition_verdict, locale="en")
