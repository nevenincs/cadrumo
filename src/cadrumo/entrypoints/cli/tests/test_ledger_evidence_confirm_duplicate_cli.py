"""Pure no-op confirmation presentation checks over the closed public DTO."""

from __future__ import annotations

import pytest

from ....core.json_contract import NoticeSeverity
from ..ledger_business_payloads import EvidenceConfirmResult
from ..ledger_evidence_commands import evidence_confirm_notices, evidence_confirm_payload
from .test_ledger_evidence_confirm_cli import ledger_evidence_confirm_cli_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_an_existing_confirmation_is_presented_as_an_informational_no_op() -> None:
    original = ledger_evidence_confirm_cli_projection()
    confirmation = original.confirmation.model_copy(update={"created": False})
    replay = original.model_copy(update={"confirmation": confirmation})

    result = EvidenceConfirmResult.model_validate(
        evidence_confirm_payload(bucket_id=str(replay.profile_id), projection=replay),
    )
    notices = evidence_confirm_notices(confirmation)
    already_exists = next(notice for notice in notices if notice.code == "ledger.evidence.confirm.already_exists")

    assert result.created is False
    assert result.invoice_id == confirmation.invoice.invoice_id
    assert already_exists.severity is NoticeSeverity.INFO
    assert already_exists.context == {"invoice_id": result.invoice_id}
    assert all(notice.code != "ledger.evidence.confirm.linked_transaction_hint" for notice in notices)
