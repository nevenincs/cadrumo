"""Authority-grade contract for the calculation-time Modelo 349 ledger guard."""

from __future__ import annotations

from typing import NoReturn

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.errors.hierarchy import CadrumoError
from .. import _calculation_helpers
from .._m349_ledger_guard import _selected_registry_ledger_declarations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_ledger_guard_requests_calculation_grade(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inspecting calculation inputs must not strengthen authority to filing grade."""
    observed: list[RegistryAuthorityGrade] = []

    def _capture_grade(_work_unit: object, *, grade: RegistryAuthorityGrade) -> NoReturn:
        observed.append(grade)
        raise CadrumoError("stop after observing the requested grade")

    monkeypatch.setattr(_calculation_helpers, "resolve_registry_snapshot_for_work_unit", _capture_grade)

    with pytest.raises(CadrumoError, match="stop after observing"):
        _selected_registry_ledger_declarations(object())  # type: ignore[arg-type]
    assert observed == [RegistryAuthorityGrade.CALCULATION]
