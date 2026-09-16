"""Modelo 145 service contract selects the revision for the requested communication period."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.errors import NoRevisionForPeriodError
from ..m145_communication import build_m145_communication_service_contract
from ..m145_communication_period import M145CommunicationPeriod

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


@pytest.mark.parametrize("period_token", tuple(M145CommunicationPeriod))
def test_contract_carries_the_requested_declared_period(
    authority_operation: PinnedAuthorityOperation,
    period_token: M145CommunicationPeriod,
) -> None:
    contract = build_m145_communication_service_contract(
        period_token=period_token,
        filing_year=2026,
        operation=authority_operation,
    )

    assert contract.period_token == period_token.value
    assert contract.revision_id == "2012-01-31-y-siguientes"


def test_contract_refuses_a_year_no_modelo_145_revision_declares(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with pytest.raises(NoRevisionForPeriodError, match="year=2011"):
        build_m145_communication_service_contract(
            period_token=M145CommunicationPeriod.COMMUNICATION,
            filing_year=2011,
            operation=authority_operation,
        )
