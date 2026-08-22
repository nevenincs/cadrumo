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

from .....core import CasillaId, validated_casilla_id
from .._bindings import CasillaObservation
from .._ids import LegalRefId, SourceRefId

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_MINIMAL_CASILLA: CasillaId = validated_casilla_id("0511")
_FULL_PROVENANCE_CASILLA: CasillaId = validated_casilla_id("0519")
_VALUE_TYPE_TEST_CASILLA: CasillaId = validated_casilla_id("0001")
_ABSENT_BY_DESIGN_CASILLA: CasillaId = validated_casilla_id("15")
_ROUNDTRIP_CASILLA: CasillaId = validated_casilla_id("01")
_TEXT_CASILLA: CasillaId = validated_casilla_id("decl.periodo")
_EMPTY_CASILLA_ID = ""
_LEGAL_REFS: tuple[LegalRefId, ...] = ("ley-35-2006:art-56",)
_SOURCE_REFS: tuple[SourceRefId, ...] = ("aeat-renta-2025-manual-parte1",)
_OPERAND_CASILLAS: tuple[CasillaId, ...] = (
    validated_casilla_id("0511"),
    validated_casilla_id("0513"),
    validated_casilla_id("0515"),
    validated_casilla_id("0517"),
)


def test_casilla_observation_minimal_construction() -> None:
    obs = CasillaObservation(
        casilla_id=_MINIMAL_CASILLA,
        value=Decimal("5550"),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )

    assert obs.casilla_id == _MINIMAL_CASILLA
    assert obs.value == Decimal("5550")
    assert obs.formula_id is None
    assert obs.operand_refs == ()
    assert obs.operand_values == ()
    assert obs.legal_refs == _LEGAL_REFS
    assert obs.source_refs == _SOURCE_REFS


def test_casilla_observation_full_provenance() -> None:
    obs = CasillaObservation(
        casilla_id=_FULL_PROVENANCE_CASILLA,
        value=Decimal("5550"),
        formula_id="renta-2025-minimo-personal-y-familiar-estatal",
        operand_refs=_OPERAND_CASILLAS,
        operand_casilla_refs=_OPERAND_CASILLAS,
        operand_values=(Decimal("5550"), Decimal("0"), Decimal("0"), Decimal("0")),
        legal_refs=("ley-35-2006:art-56", "orden-hac-277-2026:art-3"),
        source_refs=("aeat-renta-2025-manual-parte1",),
    )

    assert obs.formula_id == "renta-2025-minimo-personal-y-familiar-estatal"
    assert len(obs.operand_refs) == 4
    assert obs.operand_values[0] == Decimal("5550")


def test_casilla_observation_rejects_untraced_operand_casilla_refs() -> None:
    with pytest.raises(ValidationError, match="declares operand_casilla_refs"):
        CasillaObservation(
            casilla_id=_FULL_PROVENANCE_CASILLA,
            value=Decimal("5550"),
            formula_id="renta-2025-minimo-personal-y-familiar-estatal",
            operand_refs=("irpf.urban_rental_withholding_rate",),
            operand_casilla_refs=(_MINIMAL_CASILLA,),
            operand_values=(Decimal("0.19"),),
            legal_refs=("ley-35-2006:art-56",),
            source_refs=("aeat-renta-2025-manual-parte1",),
        )


def test_casilla_observation_value_must_be_decimal_not_bool() -> None:
    with pytest.raises(ValidationError, match="Input should be an instance of Decimal"):
        CasillaObservation(
            casilla_id=_VALUE_TYPE_TEST_CASILLA,
            value=cast(Decimal, True),
            legal_refs=_LEGAL_REFS,
            source_refs=_SOURCE_REFS,
        )


def test_casilla_observation_casilla_id_must_be_non_empty() -> None:
    with pytest.raises(ValidationError):
        CasillaObservation(
            casilla_id=_EMPTY_CASILLA_ID,
            value=Decimal("0"),
            legal_refs=_LEGAL_REFS,
            source_refs=_SOURCE_REFS,
        )


def test_casilla_observation_is_frozen() -> None:
    obs = CasillaObservation(
        casilla_id=_MINIMAL_CASILLA,
        value=Decimal("0"),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    field_name = "value"
    with pytest.raises(ValidationError):
        setattr(obs, field_name, Decimal("100"))


def test_casilla_observation_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CasillaObservation.model_validate(
            {
                "casilla_id": _MINIMAL_CASILLA,
                "value": Decimal("0"),
                "legal_refs": _LEGAL_REFS,
                "source_refs": _SOURCE_REFS,
                "unknown_field": "x",
            },
        )


def test_casilla_observation_absent_by_design_defaults_to_false() -> None:
    """The absent_by_design provenance marker is opt-in.

    The flag distinguishes structural zeros
    (binding had no anchor for the target period) from value-bearing
    observations. The default is False so ordinary value-bearing
    observations can omit the marker; absent-by-design zeros must set
    it explicitly.
    """
    obs = CasillaObservation(
        casilla_id=_ABSENT_BY_DESIGN_CASILLA,
        value=Decimal("0"),
        legal_refs=("rd-439-2007:art-110",),
        source_refs=("aeat-modelo-130-instructions",),
    )
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
        casilla_id=_ABSENT_BY_DESIGN_CASILLA,
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

    This pins the current value-bearing contract: an observation that
    omits the marker serialises and reloads identically with
    absent_by_design still false.
    """
    original = CasillaObservation(
        casilla_id=_ROUNDTRIP_CASILLA,
        value=Decimal("1000"),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    payload = original.model_dump_json()
    restored = CasillaObservation.model_validate_json(payload)

    assert restored == original
    assert restored.absent_by_design is False


@pytest.mark.parametrize("text_value", ("1T", "28001"))
def test_text_casilla_observation_roundtrips_without_becoming_a_structural_zero(text_value: str) -> None:
    original = CasillaObservation(
        casilla_id=_TEXT_CASILLA,
        value_kind="text",
        value=text_value,
        legal_refs=("rd-1624-1992:art-71",),
        source_refs=("aeat-modelo-303-procedure",),
    )

    restored = CasillaObservation.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.value == text_value
    assert restored.value != Decimal("0")
