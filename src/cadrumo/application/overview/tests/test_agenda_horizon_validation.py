from datetime import date
from typing import cast

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ....domain.deadlines.engine import DeadlineEngine
from ....domain.deadlines.models import TaxpayerProfile
from ..agenda import build_overview_agenda
from ..errors import OverviewAgendaError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_overview_agenda_error_raised_for_non_positive_horizon() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with pytest.raises(OverviewAgendaError):
            build_overview_agenda(
                profile=cast(TaxpayerProfile, None),
                as_of=date.today(),
                horizon_days=0,
                engine=cast(DeadlineEngine, None),
                raw_values={},
                operation=_authority_operation_for_test,
            )
