"""Real filing-boundary refusals for revisions without filing-grade authority."""

from __future__ import annotations

import pytest

from ....core import Period
from ....domain.filing.errors import ModeloBuilderError
from .._draft_construction import _load_registry_snapshot
from ..runtime import build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "038"
_PERIOD = Period.from_year_and_code(2025, "01")


def test_non_filing_grade_snapshot_is_typed_at_build_draft_boundary() -> None:
    """The filing resolver refuses M038 without exposing RegistryValidationError."""
    with pytest.raises(ModeloBuilderError) as exc_info:
        _load_registry_snapshot(modelo=_MODELO, period=_PERIOD)

    assert exc_info.value.translated_message == "application.filing.build_draft.errors.registry_snapshot_unavailable"
    assert exc_info.value.context == {
        "modelo": _MODELO,
        "filing_year": _PERIOD.filing_year,
        "period": _PERIOD.registry_token,
        "registry_error_type": "RegistryValidationError",
    }


def test_non_filing_grade_default_runtime_provider_refusal_is_typed() -> None:
    """An unscoped provider request also refuses M038 through filing errors."""
    with pytest.raises(ModeloBuilderError) as exc_info:
        build_runtime_schema_provider(modelos=(_MODELO,))

    assert exc_info.value.translated_message == "application.filing.build_draft.errors.registry_snapshot_unavailable"
    assert exc_info.value.context == {
        "modelo": _MODELO,
        "filing_year": None,
        "period": None,
        "registry_error_type": "RegistryValidationError",
    }


def test_non_filing_grade_period_provider_refusal_remains_typed() -> None:
    """A period-scoped provider must not admit a rejected M038 snapshot."""
    with pytest.raises(ModeloBuilderError) as exc_info:
        build_runtime_schema_provider(
            modelos=(_MODELO,),
            filing_year=_PERIOD.filing_year,
            period=_PERIOD,
        )

    assert exc_info.value.translated_message == "application.filing.runtime.errors.registry_empty_for_period"
    assert exc_info.value.context == {
        "filing_year": str(_PERIOD.filing_year),
        "period": str(_PERIOD),
    }
