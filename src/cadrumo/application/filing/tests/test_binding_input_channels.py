"""Binding input channels are derived from the registry scalar classifier.

``_binding_input`` used to compare the declared data type against five literal
names (``"text"``, ``"integer"``, ``"boolean"``, ``"decimal"``, ``"money"``)
and refuse everything else. That restated a taxonomy the registry owns: the
classifier declares nineteen data types across five runtime families,
including eleven specific text families (``nif``, ``iban``, ``period_code``,
country/province/municipality/postal codes) that the literal chain rejected as
"unsupported" even though the registry classifies them as strings.

Routing through :func:`registry_scalar_value_type` means a family the registry
adds is handled without editing filing, and each specific text family is
canonicalised by its own validator instead of being passed through untouched.

The generic ``text`` channel deliberately keeps accepting a non-string scalar:
``rectified_year`` is declared ``text`` on the binding surface while the
invoice row model types it ``int``, so refusing coercion there would reject a
valid year.
"""

from __future__ import annotations

import pytest

from ....domain.filing import ModeloBuilderError
from ...filing._draft_construction import _binding_input

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Selector:
    """Minimal binding selector carrying only a declared data type."""

    def __init__(self, data_type: str | None = None, row_field: str | None = None) -> None:
        self.data_type = data_type
        self.row_field = row_field


class _Binding:
    def __init__(self, selector: _Selector) -> None:
        self.selector = selector


def _binding(data_type: str | None = None, row_field: str | None = None) -> _Binding:
    return _Binding(_Selector(data_type=data_type, row_field=row_field))


class TestFamiliesTheLiteralChainHandled:
    """The five previously-hardcoded data types keep their channels."""

    def test_text_returns_a_string(self) -> None:
        assert _binding_input("b", "hola", _binding("text")) == "hola"

    def test_text_still_coerces_a_non_string_scalar(self) -> None:
        """``rectified_year`` is declared text but carries an int year."""
        assert _binding_input("b", 2024, _binding("text")) == "2024"

    def test_integer_returns_an_int(self) -> None:
        assert _binding_input("b", "7", _binding("integer")) == 7

    def test_integer_refuses_a_fractional_value(self) -> None:
        with pytest.raises(ModeloBuilderError):
            _binding_input("b", "7.5", _binding("integer"))

    def test_boolean_returns_a_bool(self) -> None:
        assert _binding_input("b", "si", _binding("boolean")) is True

    @pytest.mark.parametrize("data_type", ["decimal", "money"])
    def test_decimal_families_parse(self, data_type: str) -> None:
        assert str(_binding_input("b", "12.34", _binding(data_type))) == "12.34"


class TestFamiliesTheLiteralChainRejected:
    """Specific text families the registry declares but filing refused."""

    def test_nif_is_routed_and_canonicalised(self) -> None:
        """A valid NIF was previously refused as an unsupported data type."""
        assert _binding_input("b", "12345678z", _binding("nif")) == "12345678Z"

    def test_nif_is_validated_not_merely_passed_through(self) -> None:
        with pytest.raises(ModeloBuilderError):
            _binding_input("b", "not-a-nif", _binding("nif"))

    def test_period_code_is_routed(self) -> None:
        assert _binding_input("b", "1T", _binding("period_code")) == "1T"

    def test_country_code_is_routed(self) -> None:
        assert _binding_input("b", "ES", _binding("country_code")) == "ES"

    def test_blank_text_family_value_is_refused(self) -> None:
        with pytest.raises(ModeloBuilderError):
            _binding_input("b", "   ", _binding("nif"))


class TestUnknownDataType:
    """An undeclared data type is refused by the registry, not by a literal chain."""

    def test_unknown_data_type_is_refused(self) -> None:
        with pytest.raises(ModeloBuilderError) as excinfo:
            _binding_input("b", "x", _binding("bogus"))
        # Pinned to the translation key, which is the contract, rather than to
        # English prose: the refusal is localised, so any rendered wording is a
        # per-locale artefact that this assertion has no business fixing.
        assert excinfo.value.translated_message == (
            "application.filing.build_draft.errors.binding_data_type_unsupported"
        )

    def test_undeclared_selector_defaults_to_the_decimal_channel(self) -> None:
        """Documents the surviving default; the row-field gap is tracked separately."""
        assert str(_binding_input("b", "5", _binding())) == "5"
