"""Tests for CensoStaleRefusedError shape and registry binding."""

from __future__ import annotations

import pytest

from ....core.errors import AeatError
from ....core.errors._registry import get_registered_error_code
from .._errors import CensoStaleRefusedError, ModeloError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_censo_stale_refused_is_a_modelo_error() -> None:
    assert issubclass(CensoStaleRefusedError, ModeloError)
    assert issubclass(CensoStaleRefusedError, AeatError)


def test_censo_stale_refused_carries_registered_error_code() -> None:
    code = get_registered_error_code(CensoStaleRefusedError)

    assert code.code == "REFUSED_MODELO_CENSO_STALE"
    assert code.category.value == "REFUSED"
    assert code.default_suggestion == "aeat app modelo work calculate"


def test_censo_stale_refused_carries_context_through_init() -> None:
    error = CensoStaleRefusedError(
        "work unit wu-1 was produced before the latest censo apply",
        context={"work_unit_id": "wu-1", "censo_snapshot_id": "snap-xyz"},
    )

    assert error.context is not None
    assert error.context["work_unit_id"] == "wu-1"
    assert error.context["censo_snapshot_id"] == "snap-xyz"
