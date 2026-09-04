"""Roundtrip tests for the `nif` data_type and `NifString` alias.

The `nif` variant on `CasillaDefinition.data_type` plus the
`NifString` `Annotated` alias on the schema module form the canonical
identifier-validation surface for the registry boundary. These tests
exercise the alias against valid Spanish NIF, NIE, and CIF inputs and
confirm that failure cases raise `RegistryValidationError` (not the
domain-layer `IdentityError`), preserving the registry boundary's
error-type contract.

The tests also confirm that a `CasillaDefinition` declaring
`data_type = "nif"` round-trips through pydantic strict validation
without losing the type tag.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from ..errors import RegistryValidationError
from ..schema import NifString
from ..schema_scalars import _validate_nif_string
from ..schema_surfaces import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_NIF_ADAPTER: TypeAdapter[str] = TypeAdapter(NifString)


def _casilla_with(data_type: str) -> CasillaDefinition:
    return CasillaDefinition.model_validate(
        {
            "id": "nif_test_casilla",
            "number": "01",
            "localization_keys": ("test.schema.casilla.label",),
            "section": ("identificacion",),
            "data_type": data_type,
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual-nif",),
        },
    )


class TestNifStringAccepts:
    """`NifString` accepts canonically formatted Spanish identifiers."""

    def test_valid_input_returns_canonical_output(self) -> None:
        cases = (
            ("00000000T", "00000000T"),
            ("00000001R", "00000001R"),
            ("12345678Z", "12345678Z"),
            ("X0000000T", "X0000000T"),
            ("Y0000000Z", "Y0000000Z"),
            ("Z0000000M", "Z0000000M"),
            ("A58818501", "A58818501"),
            ("B58818501", "B58818501"),
            ("  00000000T  ", "00000000T"),
            ("00.000.000-T", "00000000T"),
            ("ES00000000T", "00000000T"),
            ("00000000t", "00000000T"),
            ("x0000000t", "X0000000T"),
        )

        for raw, canonical in cases:
            assert _NIF_ADAPTER.validate_python(raw) == canonical, raw


class TestNifStringRejects:
    """`NifString` rejects malformed or checksum-failing identifiers.

    Pydantic v2 wraps `RegistryValidationError` (a `ValueError`)
    raised inside a `BeforeValidator` into `ValidationError`. The
    tests below assert through `ValidationError` at the pydantic
    boundary, and separately exercise `_validate_nif_string`
    directly to confirm the raw schema-error surface.
    """

    def test_invalid_inputs_rejected_through_adapter(self) -> None:
        cases: tuple[object, ...] = (
            "",
            "12345678",
            "12345678A",
            "X0000000A",
            "A58818500",
            "@@@@@@@@@",
            "1234567890",
            12345678,
        )

        for raw in cases:
            with pytest.raises(ValidationError):
                _NIF_ADAPTER.validate_python(raw)

    def test_invalid_inputs_raise_registry_validation_error_at_validator(self) -> None:
        cases: tuple[object, ...] = (
            "",
            "12345678",
            "12345678A",
            "X0000000A",
            "A58818500",
            12345678,
        )

        for raw in cases:
            with pytest.raises(RegistryValidationError):
                _validate_nif_string(raw)


class TestCasillaDefinitionDataType:
    """`CasillaDefinition` accepts the new `nif` data_type tag."""

    def test_nif_data_type_round_trips_through_strict_validation(self) -> None:
        casilla = _casilla_with("nif")
        # Strict frozen pydantic v2: round-trip through model_dump / model_validate
        # without losing the `nif` tag.
        round_tripped = CasillaDefinition.model_validate(
            {**casilla.model_dump(), "localization_keys": casilla.localization_keys},
        )
        assert round_tripped.data_type == "nif"
        assert round_tripped == casilla

    def test_unknown_data_type_rejected(self) -> None:
        # Defensive coverage: pydantic v2 strict literal must reject a
        # value outside the declared Literal set.
        with pytest.raises(ValidationError):
            _casilla_with("not_a_real_data_type")
