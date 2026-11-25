"""Modelo 145 service contract selects the revision for the requested communication period."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_year_envelope,
    open_ended_revision,
)
from ..m145_communication import build_m145_communication_service_contract
from ..m145_communication_period import M145CommunicationPeriod

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ENVELOPE = filing_year_envelope()
_REVISION_ID = str(open_ended_revision("145").id)
_BEFORE_INCEPTION = authored_revisions("145")[0].valid_from.year - 1


@pytest.mark.parametrize("period_token", tuple(M145CommunicationPeriod))
def test_contract_carries_the_requested_declared_period(
    authority_operation: PinnedAuthorityOperation,
    period_token: M145CommunicationPeriod,
) -> None:
    contract = build_m145_communication_service_contract(
        period_token=period_token,
        filing_year=_ENVELOPE.horizon,
        operation=authority_operation,
    )

    assert contract.period_token == period_token.value
    assert contract.revision_id == _REVISION_ID


def test_contract_refuses_a_year_no_modelo_145_revision_declares(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    # The year before the first authored edition is refused by the envelope, and the refusal reports that the corpus
    # has nothing for it either -- a strictly stronger claim than the message
    # match this replaces, which could not tell the two causes apart.
    with pytest.raises(FilingYearOutsideSupportEnvelopeError) as excinfo:
        build_m145_communication_service_contract(
            period_token=M145CommunicationPeriod.COMMUNICATION,
            filing_year=_BEFORE_INCEPTION,
            operation=authority_operation,
        )

    assert excinfo.value.filing_year == _BEFORE_INCEPTION
    assert excinfo.value.covering_revision_ids == ()
    assert "no modelo 145 revision covers it either" in str(excinfo.value)
