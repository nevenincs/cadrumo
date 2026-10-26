"""Maritime exemption inputs resolve only for a worker the profile does not classify as maritime."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.user_profile.values import UserProfileFactValue
from ..profile_binding import inject_ordinary_work_maritime_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ORDINARY_WORK = {
    "maritime_worker.exemption_path_rebeca": False,
    "maritime_worker.gross_navigation_income": Decimal("0"),
    "maritime_worker.annual_salary": Decimal("0"),
    "maritime_worker.qualifying_days": Decimal("0"),
}


def test_unclassified_worker_takes_the_ordinary_treatment() -> None:
    fact_index: dict[str, UserProfileFactValue] = {"renta_taxpayer.marital_status": "soltero"}

    inject_ordinary_work_maritime_facts(fact_index)

    assert fact_index == {"renta_taxpayer.marital_status": "soltero", **_ORDINARY_WORK}
    assert fact_index["maritime_worker.exemption_path_rebeca"] is False


def test_classified_maritime_worker_keeps_missing_inputs_unresolved() -> None:
    fact_index: dict[str, UserProfileFactValue] = {"maritime_worker.worker_class": "trabajador_del_mar"}

    inject_ordinary_work_maritime_facts(fact_index)

    assert fact_index == {"maritime_worker.worker_class": "trabajador_del_mar"}


def test_stated_maritime_inputs_are_never_replaced() -> None:
    fact_index: dict[str, UserProfileFactValue] = {"maritime_worker.annual_salary": Decimal("41000")}

    inject_ordinary_work_maritime_facts(fact_index)

    assert fact_index["maritime_worker.annual_salary"] == Decimal("41000")
    assert fact_index["maritime_worker.gross_navigation_income"] == Decimal("0")
