"""Authority-grade contract for the calculation-time Modelo 349 ledger guard."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import NoReturn

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.errors.hierarchy import CadrumoError
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from .. import _calculation_helpers
from .._m349_ledger_guard import _selected_registry_ledger_declarations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _work_unit() -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    bucket_id = "m349-ledger-guard-authority"
    modelo = ModeloCode("349")
    revision_id = "test-revision"
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=period.filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=period.filing_year,
        period=period,
        revision_id=revision_id,
        name="349-2026-1T",
        created_at=_T0,
        updated_at=_T0,
    )


def test_ledger_guard_requests_calculation_grade(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inspecting calculation inputs must not strengthen authority to filing grade."""
    observed: list[RegistryAuthorityGrade] = []

    def _capture_grade(_work_unit: object, *, grade: RegistryAuthorityGrade) -> NoReturn:
        observed.append(grade)
        raise CadrumoError("stop after observing the requested grade")

    monkeypatch.setattr(_calculation_helpers, "resolve_registry_snapshot_for_work_unit", _capture_grade)

    with pytest.raises(CadrumoError, match="stop after observing"):
        _selected_registry_ledger_declarations(_work_unit())
    assert observed == [RegistryAuthorityGrade.CALCULATION]
