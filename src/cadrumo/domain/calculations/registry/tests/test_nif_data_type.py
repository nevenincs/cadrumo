"""Roundtrip tests for the `nif` data_type.

The `nif` variant on `CasillaDefinition.data_type` plus the
text-scalar validator in the schema module form the canonical
identifier-validation surface for the registry boundary. These tests
exercise the validator against valid Spanish NIF, NIE, and CIF inputs and
confirm that failure cases raise `RegistryValidationError` (not the
domain-layer `IdentityError`), preserving the registry boundary's
error-type contract.

The tests also confirm that a `CasillaDefinition` declaring
`data_type = "nif"` round-trips through pydantic strict validation
without losing the type tag.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core.identity.tests.tax_id_format_support import SPANISH_TAX_ID_FORMAT
from ..errors import RegistryValidationError
from ..schema_scalars import validate_registry_text_scalar
from ..schema_surfaces import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _validate_nif(raw: object) -> str:
    return validate_registry_text_scalar("nif", raw, tax_id_format=SPANISH_TAX_ID_FORMAT)


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
    """The nif scalar accepts canonically formatted Spanish identifiers."""

    def test_valid_input_returns_canonical_output(self) -> None:
        cases = (
            ("00000000T", "00000000T"),
            ("00001005Q", "00001005Q"),
            ("12345678Z", "12345678Z"),
            ("X0001004S", "X0001004S"),
            ("Y0001007D", "Y0001007D"),
            ("Z0001008R", "Z0001008R"),
            ("B00010157", "B00010157"),
            ("B00010181", "B00010181"),
            ("  00000000T  ", "00000000T"),
            ("00.000.000-T", "00000000T"),
            ("ES00000000T", "00000000T"),
            ("00000000t", "00000000T"),
            ("x0001004s", "X0001004S"),
        )

        for raw, canonical in cases:
            assert _validate_nif(raw) == canonical, raw


class TestNifStringRejects:
    """The nif scalar rejects malformed or checksum-failing identifiers.

    The registry's text-scalar entry point refuses with the registered
    `RegistryValidationError`.
    """

    def test_invalid_inputs_rejected(self) -> None:
        cases: tuple[object, ...] = (
            "",
            "12345678",
            "12345678A",
            "X0000000A",
            "B00000280",
            "@@@@@@@@@",
            "1234567890",
            12345678,
        )

        for raw in cases:
            with pytest.raises(RegistryValidationError):
                _validate_nif(raw)

    def test_direct_scalar_validation_requires_and_obeys_the_explicit_format(self) -> None:
        assert validate_registry_text_scalar("nif", "ES00000000T", tax_id_format=SPANISH_TAX_ID_FORMAT) == "00000000T"
        with pytest.raises(RegistryValidationError, match="explicit Spanish tax-ID format"):
            validate_registry_text_scalar("nif", "00000000T")


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
