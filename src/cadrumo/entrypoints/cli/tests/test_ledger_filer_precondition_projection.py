"""CLI projection of the ledger filer's typed setup refusal."""

from __future__ import annotations

import pytest

from ....application.ledger import PurchaseInvoiceEvidenceInputError
from ....application.ledger._confirm_establishment import _filer_scope
from ....application.ledger._filer_establishment import FILER_TAX_ID_FACT_PATH
from ....application.ledger._preconditions import LedgerPreconditionCondition
from ....core import NoRecoveryOutcome
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from .._common import cli_policy_refusal_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_filer_setup_refusal_reaches_the_shared_cli_projection_intact() -> None:
    """The shared boundary sees the original condition, facts, and outcome."""
    profile = UserProfileRecord(
        profile_id="11111111-1111-4111-8111-111111111111",
        display_name="Territory projection",
        facts=(UserProfileFact(path=FILER_TAX_ID_FACT_PATH, value="X1234567L"),),
    )

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        _filer_scope(profile)

    projection = cli_policy_refusal_projection(raised.value)
    assert projection is not None
    action = projection.precondition_action
    assert action.failed_condition_id == LedgerPreconditionCondition.FILER_POSTCODE_VALID.value
    assert action.evidence[0].values == {"filer_postcode_present": False}
    assert action.action is None
    assert action.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
