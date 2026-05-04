"""Runtime schema provider backed by committed registry definitions."""

from __future__ import annotations

import pytest

from ...domain.filing import FilingBuilderError
from .runtime import build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_runtime_schema_provider_reads_modelo_130_registry_schema() -> None:
    provider = build_runtime_schema_provider()

    collection = provider.get_collection("130")

    assert collection.schema_version == "registry:130:2019-y-siguientes"
    assert len(collection.all()) == 19
    casilla_01 = collection.get("01")
    casilla_04 = collection.get("04")
    casilla_07 = collection.get("07")
    assert casilla_01 is not None
    assert casilla_04 is not None
    assert casilla_07 is not None
    assert casilla_04.formula_inputs == ("03",)
    assert casilla_07.formula_inputs == ("04", "05", "06")


def test_runtime_schema_provider_rejects_unknown_modelo() -> None:
    provider = build_runtime_schema_provider()

    with pytest.raises(FilingBuilderError, match="not present in the calculation registry"):
        provider.get_collection("999")
