"""Contract tests for the typed `CasillaObservation` record.

Guards the pydantic field invariants on the observation type the
formula runtime emits as primary storage of
:class:`RegistryCalculationResult`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from ._bindings import CasillaObservation

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_casilla_observation_minimal_construction() -> None:
    obs = CasillaObservation(casilla_id="0511", value=Decimal("5550"))

    assert obs.casilla_id == "0511"
    assert obs.value == Decimal("5550")
    assert obs.formula_id is None
    assert obs.operand_refs == ()
    assert obs.operand_values == ()
    assert obs.legal_refs == ()
    assert obs.source_refs == ()


def test_casilla_observation_full_provenance() -> None:
    obs = CasillaObservation(
        casilla_id="0519",
        value=Decimal("5550"),
        formula_id="renta-2025-minimo-personal-y-familiar-estatal",
        operand_refs=("0511", "0513", "0515", "0517"),
        operand_values=(Decimal("5550"), Decimal("0"), Decimal("0"), Decimal("0")),
        legal_refs=("ley-35-2006:art-56", "orden-hac-277-2026:art-3"),
        source_refs=("aeat-renta-2025-manual-parte1",),
    )

    assert obs.formula_id == "renta-2025-minimo-personal-y-familiar-estatal"
    assert len(obs.operand_refs) == 4
    assert obs.operand_values[0] == Decimal("5550")


def test_casilla_observation_value_must_be_decimal_not_bool() -> None:
    with pytest.raises(ValidationError, match="Input should be an instance of Decimal"):
        CasillaObservation(casilla_id="0001", value=cast(Decimal, True))


def test_casilla_observation_casilla_id_must_be_non_empty() -> None:
    with pytest.raises(ValidationError):
        CasillaObservation(casilla_id="", value=Decimal("0"))


def test_casilla_observation_is_frozen() -> None:
    obs = CasillaObservation(casilla_id="0511", value=Decimal("0"))
    with pytest.raises(ValidationError):
        obs.value = Decimal("100")  # type: ignore[misc]


def test_casilla_observation_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CasillaObservation.model_validate(
            {
                "casilla_id": "0511",
                "value": Decimal("0"),
                "unknown_field": "x",
            }
        )
