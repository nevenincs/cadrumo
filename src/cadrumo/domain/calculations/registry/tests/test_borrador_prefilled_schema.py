"""Registry schema contract for AEAT-prefilled Modelo 100 bindings."""

from __future__ import annotations

from functools import cache

import pytest

from ..authority import bundled_authority
from ..ids import BindingId
from ..schema import DataBindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _modelo_100_bindings() -> dict[BindingId, DataBindingDefinition]:
    authority = bundled_authority()
    snapshot = authority.snapshot("100", filing_year=2025, period="0A")
    return {binding.id: binding for binding in snapshot.revision.bindings}


def test_data_binding_definition_accepts_explicit_aeat_prefilled_marker() -> None:
    binding = _modelo_100_bindings()["renta-2025-modelo-111-retenciones-periodicas"]

    marked = DataBindingDefinition.model_validate(
        {
            **binding.model_dump(mode="python"),
            "aeat_prefilled": True,
        },
    )

    assert marked.aeat_prefilled is True


def test_data_binding_definition_defaults_aeat_prefilled_to_false() -> None:
    binding = _modelo_100_bindings()["renta-2025-ledger-expense-0186-deductible"]
    payload = binding.model_dump(mode="python")
    payload.pop("aeat_prefilled", None)

    unmarked = DataBindingDefinition.model_validate(payload)

    assert unmarked.aeat_prefilled is False


def test_committed_modelo_100_prefilled_bindings_are_schema_backed() -> None:
    bindings = _modelo_100_bindings()

    assert bindings["renta-2025-modelo-111-retenciones-periodicas"].aeat_prefilled is True
    assert bindings["renta-2025-profile-tax-residence-ccaa"].aeat_prefilled is True
    assert bindings["renta-2025-ledger-expense-0186-deductible"].aeat_prefilled is False
