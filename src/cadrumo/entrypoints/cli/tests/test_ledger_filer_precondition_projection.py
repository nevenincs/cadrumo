"""CLI projection of the ledger filer's typed setup refusal.

The claim under test belongs to the CLI boundary alone: whatever ledger refusal
arrives carrying a terminal precondition verdict, the shared projection reads its
condition, evidence and closed outcome back out unrecast. The refusal is
therefore raised through the ledger's own public resolver, because the producer
is immaterial to that claim -- the projection reads the verdict off the
exception and never asks which function raised it.

The neighbouring property -- that the confirm path does not flatten this
refusal into review-item prose on its way past -- is a fact about the ledger
package's internals, and is gated there, beside the private function that would
break it.
"""

from __future__ import annotations

import pytest

from ....application.ledger.evidence import PurchaseInvoiceEvidenceInputError
from ....application.ledger.filer_establishment import FILER_TAX_ID_FACT_PATH, resolve_filer_territorial_scope
from ....application.ledger.preconditions import LedgerPreconditionCondition
from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from .._common import cli_policy_refusal_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_filer_setup_refusal_reaches_the_shared_cli_projection_intact() -> None:
    """The shared boundary sees the original condition, facts, and outcome."""
    profile = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(UserProfileFact(path=FILER_TAX_ID_FACT_PATH, value="X1234567L"),),
    )

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        resolve_filer_territorial_scope(profile_record=profile)

    projection = cli_policy_refusal_projection(raised.value)
    assert projection is not None
    action = projection.precondition_action
    assert action.failed_condition_id == LedgerPreconditionCondition.FILER_POSTCODE_VALID.value
    assert action.evidence[0].values == {"filer_postcode_present": False}
    assert action.action is None
    assert action.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
