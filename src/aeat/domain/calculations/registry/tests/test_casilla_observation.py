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

from .._bindings import CasillaObservation

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
            },
        )


def test_casilla_observation_absent_by_design_defaults_to_false() -> None:
    """The absent_by_design provenance marker is opt-in.

    The flag distinguishes structural zeros
    (binding had no anchor for the target period) from value-bearing
    observations. Default False so legacy persisted observations
    deserialise as "value-bearing" — the historical contract — until
    the campaign-level migration is run.
    """
    obs = CasillaObservation(casilla_id="15", value=Decimal("0"))
    assert obs.absent_by_design is False


def test_casilla_observation_absent_by_design_roundtrips_through_json() -> None:
    """absent_by_design survives JSON serialise-then-parse.

    A real-behaviour roundtrip: construct an observation with the
    flag set, dump to JSON via model_dump_json, parse back via
    model_validate_json, assert the flag preserved verbatim. Pins
    the persistence contract so a future schema refactor cannot
    silently drop the field without breaking this test.
    """
    original = CasillaObservation(
        casilla_id="15",
        value=Decimal("0"),
        absent_by_design=True,
        legal_refs=("rd-439-2007:art-110",),
        source_refs=("aeat-modelo-130-instructions",),
    )

    payload = original.model_dump_json()
    restored = CasillaObservation.model_validate_json(payload)

    assert restored == original
    assert restored.absent_by_design is True
    assert restored.legal_refs == ("rd-439-2007:art-110",)


def test_casilla_observation_absent_by_design_default_roundtrips_through_json() -> None:
    """The False default also survives the JSON roundtrip.

    Migration concern: legacy persisted observations deserialise
    with the default False. This test pins that the default ALSO
    roundtrips cleanly — so an observation persisted today with
    the field implicit will load back identically.
    """
    original = CasillaObservation(casilla_id="01", value=Decimal("1000"))
    payload = original.model_dump_json()
    restored = CasillaObservation.model_validate_json(payload)

    assert restored == original
    assert restored.absent_by_design is False
