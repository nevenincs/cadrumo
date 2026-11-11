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

from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_targets import revision_bindings_by_id
from ....domain.calculations.registry.binding_value_contract import BindingValueChannel, BindingValueContract
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.calculations.registry.schema import BindingDefinition, RegistrySnapshot
from ....domain.filing.errors import ModeloBuilderError
from ..draft_construction import binding_input, draft_input_channels, snapshot_bound_casilla_binding_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _authority_scope(operation: PinnedAuthorityOperation) -> Iterator[None]:
    """Exercise NIF coercion under the same pinned fact scope as the filing door."""
    with validating_governed_facts(operation):
        yield


def _binding(data_type: str | None = None, row_field: str | None = None) -> BindingDefinition:
    """Build the nominal registry shape while isolating the value contract under test."""
    del row_field
    value = BindingValueContract.model_construct(data_type=data_type or "decimal")
    return BindingDefinition.model_construct(value=value)


class TestFamiliesTheLiteralChainHandled:
    """The five previously-hardcoded data types keep their channels."""

    def test_text_returns_a_string(self) -> None:
        assert binding_input("b", "hola", _binding("text")) == "hola"

    def test_text_still_coerces_a_non_string_scalar(self) -> None:
        """``rectified_year`` is declared text but carries an int year."""
        assert binding_input("b", 2024, _binding("text")) == "2024"

    def test_integer_returns_an_int(self) -> None:
        assert binding_input("b", "7", _binding("integer")) == 7

    def test_integer_refuses_a_fractional_value(self) -> None:
        with pytest.raises(ModeloBuilderError):
            binding_input("b", "7.5", _binding("integer"))

    @pytest.mark.parametrize("data_type", ("integer", "decimal", "money"))
    @pytest.mark.parametrize("token", ("Infinity", "-Infinity", "NaN", "sNaN"))
    @pytest.mark.parametrize("as_decimal", (False, True))
    def test_non_finite_numeric_value_is_refused(self, data_type: str, token: str, as_decimal: bool) -> None:
        value: object = Decimal(token) if as_decimal else token
        with pytest.raises(ModeloBuilderError):
            binding_input("b", value, _binding(data_type))

    def test_boolean_returns_a_bool(self) -> None:
        assert binding_input("b", "si", _binding("boolean")) is True

    @pytest.mark.parametrize("data_type", ["decimal", "money"])
    def test_decimal_families_parse(self, data_type: str) -> None:
        assert str(binding_input("b", "12.34", _binding(data_type))) == "12.34"

    @pytest.mark.parametrize("data_type", ("integer", "decimal", "money"))
    @pytest.mark.parametrize("value", (None, ""))
    def test_empty_numeric_binding_preserves_absence(self, data_type: str, value: object) -> None:
        assert binding_input("b", value, _binding(data_type)) is None

    @pytest.mark.parametrize("data_type", ("integer", "decimal", "money"))
    def test_whitespace_is_not_a_canonical_empty_numeric_binding(self, data_type: str) -> None:
        with pytest.raises(ModeloBuilderError):
            binding_input("b", " ", _binding(data_type))


class TestFamiliesTheLiteralChainRejected:
    """Specific text families the registry declares but filing refused."""

    def test_nif_is_routed_and_canonicalised(self) -> None:
        """A valid NIF was previously refused as an unsupported data type."""
        assert binding_input("b", "12345678z", _binding("nif")) == "12345678Z"

    def test_nif_is_validated_not_merely_passed_through(self) -> None:
        with pytest.raises(ModeloBuilderError):
            binding_input("b", "not-a-nif", _binding("nif"))

    def test_period_code_is_routed(self) -> None:
        assert binding_input("b", "1T", _binding("period_code")) == "1T"

    def test_country_code_is_routed(self) -> None:
        assert binding_input("b", "ES", _binding("country_code")) == "ES"

    def test_blank_text_family_value_is_refused(self) -> None:
        with pytest.raises(ModeloBuilderError):
            binding_input("b", "   ", _binding("nif"))


class TestUnknownDataType:
    """An undeclared data type is refused by the registry, not by a literal chain."""

    def test_unknown_data_type_is_refused(self) -> None:
        with pytest.raises(ModeloBuilderError) as excinfo:
            binding_input("b", "x", _binding("bogus"))
        # Pinned to the translation key, which is the contract, rather than to
        # English prose: the refusal is localised, so any rendered wording is a
        # per-locale artefact that this assertion has no business fixing.
        assert excinfo.value.translated_message == (
            "application.filing.build_draft.errors.binding_data_type_unsupported"
        )

    def test_fixture_default_exercises_the_decimal_channel(self) -> None:
        """Keep the helper fixture's omitted argument on its explicit decimal case."""
        assert str(binding_input("b", "5", _binding())) == "5"


class TestCalendarDateBindings:
    """Calendar dates survive filing values and reject ambiguous scalar inputs."""

    @pytest.mark.parametrize("value", (date(2024, 2, 29), "2024-02-29", "20240229"))
    def test_calendar_date_round_trips(self, value: date | str) -> None:
        assert binding_input("b", value, _binding("date")) == date(2024, 2, 29)

    def test_absence_remains_absent(self) -> None:
        assert binding_input("b", None, _binding("date")) is None

    @pytest.mark.parametrize("value", ("2023-02-29", "", 20240229, True, datetime(2024, 2, 29)))
    def test_invalid_dates_and_non_calendar_types_refuse(self, value: object) -> None:
        with pytest.raises(ModeloBuilderError) as excinfo:
            binding_input("b", value, _binding("date"))
        assert excinfo.value.translated_message == "application.filing.build_draft.errors.date_binding_not_iso"


def _edition_binding_a_row_set_and_a_decimal_to_casillas(
    operation: PinnedAuthorityOperation,
) -> tuple[RegistrySnapshot, str, str]:
    """The first supported annual Modelo 100 edition binding both a row-set money value and a decimal to casillas."""
    for year in operation.supported_filing_years().years:
        snapshot = operation.snapshot("100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION)
        bindings = revision_bindings_by_id(snapshot.revision)
        bound = sorted(snapshot_bound_casilla_binding_ids(snapshot))
        row_set = [
            binding
            for binding in bound
            if bindings[binding].value.channel is BindingValueChannel.ROW_SET
            and bindings[binding].value.data_type == "money"
        ]
        decimal = [binding for binding in bound if bindings[binding].value.channel is BindingValueChannel.DECIMAL]
        if row_set and decimal:
            return snapshot, row_set[0], decimal[0]
    raise AssertionError("no supported annual Modelo 100 edition binds a row-set value to a casilla")


class TestReplayedBoundCasillaChannels:
    """A replayed bound casilla reaches the channel its binding declares, never one its value happens to fit."""

    def test_a_row_set_binding_replayed_as_rows_stays_out_of_the_decimal_channel(
        self, operation: PinnedAuthorityOperation
    ) -> None:
        snapshot, row_set_binding, _ = _edition_binding_a_row_set_and_a_decimal_to_casillas(operation)

        for replayed, expected in (
            ({"1": "0"}, [(1, Decimal("0"))]),
            ({"1": "125.40", "2": "0"}, [(1, Decimal("125.40")), (2, Decimal("0"))]),
        ):
            channels = draft_input_channels(snapshot, {row_set_binding: replayed})

            assert row_set_binding not in channels.binding_inputs
            rows = [value for value in channels.filing_binding_values if value.binding_id == row_set_binding]
            assert [(value.row_index, value.value) for value in rows] == expected

    def test_a_decimal_binding_replayed_as_a_scalar_still_reaches_the_decimal_channel(
        self, operation: PinnedAuthorityOperation
    ) -> None:
        snapshot, _, decimal_binding = _edition_binding_a_row_set_and_a_decimal_to_casillas(operation)

        channels = draft_input_channels(snapshot, {decimal_binding: "12.50"})

        assert channels.binding_inputs[decimal_binding] == Decimal("12.50")
