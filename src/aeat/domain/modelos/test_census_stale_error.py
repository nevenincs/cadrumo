"""Tests for CensusStaleRefusedError shape and registry binding."""

from __future__ import annotations

import pytest

from aeat.core.errors import AeatError
from aeat.core.errors._registry import get_registered_error_code
from aeat.domain.modelos._errors import CensusStaleRefusedError, ModeloError


pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_census_stale_refused_is_a_modelo_error() -> None:
    assert issubclass(CensusStaleRefusedError, ModeloError)
    assert issubclass(CensusStaleRefusedError, AeatError)


def test_census_stale_refused_carries_registered_error_code() -> None:
    code = get_registered_error_code(CensusStaleRefusedError)

    assert code.code == "REFUSED_MODELO_CENSUS_STALE"
    assert code.category.value == "REFUSED"
    assert code.default_suggestion == "aeat app modelo work calculate"


def test_census_stale_refused_carries_context_through_init() -> None:
    error = CensusStaleRefusedError(
        "work unit wu-1 was produced before the latest census apply",
        context={"work_unit_id": "wu-1", "census_snapshot_id": "snap-xyz"},
    )

    assert error.context["work_unit_id"] == "wu-1"
    assert error.context["census_snapshot_id"] == "snap-xyz"
