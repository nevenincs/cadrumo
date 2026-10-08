"""Pure no-op confirmation presentation checks over the closed public DTO."""

from __future__ import annotations

import pytest

from ....core.json_contract import NoticeSeverity
from .._ledger_evidence_cli import _evidence_confirm_notices, _evidence_confirm_payload
from ..ledger_business_payloads import EvidenceConfirmResult
from .test_ledger_evidence_confirm_cli import _projection as _confirm_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_an_existing_confirmation_is_presented_as_an_informational_no_op() -> None:
    original = _confirm_projection()
    confirmation = original.confirmation.model_copy(update={"created": False})
    replay = original.model_copy(update={"confirmation": confirmation})

    result = EvidenceConfirmResult.model_validate(
        _evidence_confirm_payload(bucket_id=str(replay.profile_id), projection=replay),
    )
    notices = _evidence_confirm_notices(confirmation)
    already_exists = next(notice for notice in notices if notice.code == "ledger.evidence.confirm.already_exists")

    assert result.created is False
    assert result.invoice_id == confirmation.invoice.invoice_id
    assert already_exists.severity is NoticeSeverity.INFO
    assert already_exists.context == {"invoice_id": result.invoice_id}
    assert all(notice.code != "ledger.evidence.confirm.linked_transaction_hint" for notice in notices)
