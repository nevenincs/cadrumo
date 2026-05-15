"""Schema + resolver contract tests for ``source_period_offset_from_target``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ._errors import RegistryValidationError
from ._relations import _derive_offset_source_period
from ._schema import RelationDefinition

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _relation(**overrides: object) -> RelationDefinition:
    defaults: dict[str, object] = {
        "id": "test-rel",
        "kind": "previous_period",
        "dependency_role": "direct_calculation",
        "source_modelo": "303",
        "source_revision_selector": {"filing_year_delta": 0},
        "source_output": "iva.resultado",
        "target_binding": "iva.previo",
        "period_alignment": {"mode": "previous_quarter"},
        "legal_refs": ("ley-37-1992:art-99",),
        "source_refs": ("aeat-modelo-303-procedure",),
    }
    defaults.update(overrides)
    return RelationDefinition.model_validate(defaults)


def test_quarterly_offset_resolves_previous_quarter() -> None:
    relation = _relation(target_periods=("2T", "3T", "4T"), source_period_offset_from_target=-1)
    assert _derive_offset_source_period(relation, target_period="2T") == "1T"
    assert _derive_offset_source_period(relation, target_period="3T") == "2T"
    assert _derive_offset_source_period(relation, target_period="4T") == "3T"


def test_quarterly_offset_returns_none_when_outside_year() -> None:
    relation = _relation(target_periods=("1T", "2T", "3T", "4T"), source_period_offset_from_target=-1)
    assert _derive_offset_source_period(relation, target_period="1T") is None


def test_pago_fraccionado_offset_resolves_previous_period() -> None:
    relation = _relation(target_periods=("2P", "3P"), source_period_offset_from_target=-1)
    assert _derive_offset_source_period(relation, target_period="2P") == "1P"
    assert _derive_offset_source_period(relation, target_period="3P") == "2P"
    assert _derive_offset_source_period(relation, target_period="1P") is None


def test_monthly_offset_resolves_previous_month() -> None:
    relation = _relation(target_periods=("02", "12"), source_period_offset_from_target=-1)
    assert _derive_offset_source_period(relation, target_period="02") == "01"
    assert _derive_offset_source_period(relation, target_period="12") == "11"


def test_monthly_offset_returns_none_when_outside_year() -> None:
    relation = _relation(target_periods=("01",), source_period_offset_from_target=-1)
    assert _derive_offset_source_period(relation, target_period="01") is None


def test_source_periods_and_offset_mutually_exclusive() -> None:
    with pytest.raises(ValidationError, match="cannot declare source_periods"):
        _relation(source_periods=("1T",), source_period_offset_from_target=-1)


def test_zero_offset_rejected() -> None:
    with pytest.raises(ValidationError, match="must be non-zero"):
        _relation(source_period_offset_from_target=0)


def test_unknown_period_format_rejected_at_resolution() -> None:
    relation = _relation(target_periods=("ANUAL",), source_period_offset_from_target=-1)
    with pytest.raises(RegistryValidationError, match="cannot interpret target period"):
        _derive_offset_source_period(relation, target_period="ANUAL")
