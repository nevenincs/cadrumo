"""Registry schema contract for AEAT-prefilled Modelo 100 bindings."""

from __future__ import annotations

from functools import cache

import pytest

from ..binding_borrador_participation import BorradorParticipation
from ..ids import BindingId
from ..schema import BindingDefinition
from .authored_editions import newest_authored_edition
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _modelo_100_bindings() -> dict[BindingId, BindingDefinition]:
    snapshot = published_snapshot("100", filing_year=newest_authored_edition("100"), period="0A")
    return {binding.id: binding for binding in snapshot.revision.bindings}


def test_data_binding_definition_accepts_explicit_aeat_prefilled_marker() -> None:
    binding = _modelo_100_bindings()["renta-ledger-expense-0186-deductible"]
    assert binding.aeat_prefilled is False

    marked = BindingDefinition.model_validate(
        {
            **binding.model_dump(mode="python"),
            "aeat_prefilled": True,
        },
    )

    assert marked.aeat_prefilled is True


def test_data_binding_definition_defaults_aeat_prefilled_to_false() -> None:
    binding = _modelo_100_bindings()["renta-ledger-expense-0186-deductible"]
    payload = binding.model_dump(mode="python")
    payload.pop("aeat_prefilled", None)

    unmarked = BindingDefinition.model_validate(payload)

    assert unmarked.aeat_prefilled is False


def test_committed_modelo_100_prefilled_bindings_are_schema_backed() -> None:
    bindings = _modelo_100_bindings()

    assert bindings["renta-profile-tax-residence-ccaa"].aeat_prefilled is True
    assert bindings["renta-profile-tax-residence-ccaa"].borrador_supplies_value is True
    assert bindings["renta-ledger-expense-0186-deductible"].aeat_prefilled is False


@pytest.mark.parametrize(
    "binding_id",
    [
        "renta-retencion-soportada-trabajo",
        "renta-retencion-soportada-capital-mobiliario",
        "renta-retencion-soportada-ganancia-patrimonial",
    ],
)
def test_committed_modelo_100_credit_bindings_are_held_by_the_borrador_only_for_comparison(binding_id: str) -> None:
    binding = _modelo_100_bindings()[binding_id]

    assert binding.aeat_prefilled is True
    assert binding.borrador_participation is BorradorParticipation.CROSS_CHECK_ONLY
    assert binding.borrador_supplies_value is False
    assert "renta-certificado-trabajo-retenciones" not in _modelo_100_bindings()
