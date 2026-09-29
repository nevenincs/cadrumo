"""A text casilla with no text stays absent through the registry calculation.

Zero is a numeric state only. The Modelo 190 2022 declarante record carries
operator-supplied text slots -- contact telephone, contact name, e-mail and the
declaration's identifying numbers -- that the record design lets a filer leave
empty. Those casillas must come out of the calculation carrying no value at
all, never a numeric placeholder that later surfaces as a plausible ``0`` in a
preview, a report or the filing file. Numeric casillas keep their contract: an
absent numeric input still calculates as zero.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from ..bindings import CasillaObservation, CasillaObservationValueKind
from ..casilla_membership import casillas_by_id, text_family_casilla_ids
from ..errors import RegistryValidationError
from ..formula_initial_values import materialise_observations
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot, evaluate_expression
from ..runtime_graph import expression_binding_refs
from ..schema import RegistrySnapshot
from ..schema_formula import FormulaExpression
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_TELEFONO: CasillaId = validated_casilla_id("decl.persona-contacto-telefono")
_NOMBRE: CasillaId = validated_casilla_id("decl.persona-contacto-nombre")
_CORREO: CasillaId = validated_casilla_id("decl.correo-electronico")
_NUMERO_IDENTIFICATIVO: CasillaId = validated_casilla_id("decl.numero-identificativo")
_NUMERO_IDENTIFICATIVO_ANTERIOR: CasillaId = validated_casilla_id("decl.numero-identificativo-anterior")
_CONTACT_AND_IDENTITY_TEXT: tuple[CasillaId, ...] = (
    _TELEFONO,
    _NOMBRE,
    _CORREO,
    _NUMERO_IDENTIFICATIVO,
    _NUMERO_IDENTIFICATIVO_ANTERIOR,
)
# A numeric manual casilla of the same revision, left empty by the caller.
_NUMERIC_MANUAL: CasillaId = validated_casilla_id("perc.descendientes-menores-3-total")


def _snapshot_190_2022() -> RegistrySnapshot:
    return published_snapshot("190", filing_year=2022, period="0A")


def _calculate(
    snapshot: RegistrySnapshot,
    *,
    inputs: dict[CasillaId, Decimal] | None = None,
    text_inputs: dict[CasillaId, str] | None = None,
) -> RegistryCalculationResult:
    """Run the real engine with every formula-read binding supplied."""
    formula_bindings = {
        binding_id
        for formula in snapshot.revision.formulas
        for binding_id in expression_binding_refs(formula.expression)
    }
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs or {},
        date_context={"filing_period": date(2022, 12, 31)},
        binding_values={binding_id: Decimal("100") for binding_id in formula_bindings},
        text_inputs=text_inputs,
    )


def _observations_by_id(result: RegistryCalculationResult) -> dict[CasillaId, CasillaObservation]:
    return {observation.casilla_id: observation for observation in result.observations}


def test_the_190_2022_contact_and_identity_casillas_are_text_casillas() -> None:
    """The cases below exercise text casillas, as the registry itself declares them."""
    snapshot = _snapshot_190_2022()

    text_ids = text_family_casilla_ids(snapshot.revision.casillas)

    assert set(_CONTACT_AND_IDENTITY_TEXT) <= text_ids
    assert _NUMERIC_MANUAL not in text_ids


def test_absent_190_2022_text_casillas_carry_no_observation() -> None:
    result = _calculate(_snapshot_190_2022())
    observations = _observations_by_id(result)

    for casilla_id in _CONTACT_AND_IDENTITY_TEXT:
        assert casilla_id not in observations, f"{casilla_id} materialised a value it was never given"
        assert casilla_id not in result.values


def test_an_absent_numeric_casilla_still_calculates_as_zero() -> None:
    result = _calculate(_snapshot_190_2022())
    observation = _observations_by_id(result)[_NUMERIC_MANUAL]

    assert observation.value_kind == CasillaObservationValueKind.DECIMAL
    assert observation.value == Decimal("0")
    assert result.values[_NUMERIC_MANUAL] == Decimal("0")


def test_populated_190_2022_text_casillas_materialise_as_text() -> None:
    supplied = {
        _TELEFONO: "600123456",
        _NOMBRE: "PERSONA DE CONTACTO",
        _CORREO: "contacto@example.org",
        _NUMERO_IDENTIFICATIVO: "1901234567890",
    }

    result = _calculate(_snapshot_190_2022(), text_inputs=dict(supplied))
    observations = _observations_by_id(result)

    for casilla_id, text in supplied.items():
        assert observations[casilla_id].value_kind == CasillaObservationValueKind.TEXT
        assert observations[casilla_id].value == text
        assert casilla_id not in result.values
    assert _NUMERO_IDENTIFICATIVO_ANTERIOR not in observations


def test_a_number_supplied_for_a_text_casilla_is_refused() -> None:
    with pytest.raises(RegistryValidationError, match="text casillas cannot be supplied as numeric inputs"):
        _calculate(_snapshot_190_2022(), inputs={_TELEFONO: Decimal("0")})


def test_materialising_a_zero_for_an_absent_text_casilla_is_caught() -> None:
    """Detector: the old structural zero for a text casilla cannot become an observation."""
    snapshot = _snapshot_190_2022()

    with pytest.raises(RegistryValidationError, match="cannot carry a numeric observation"):
        materialise_observations(
            values={_TELEFONO: Decimal("0")},
            computed_provenance={},
            casillas_by_id=casillas_by_id(snapshot.revision),
        )


def test_a_formula_figure_written_into_a_text_casilla_is_caught() -> None:
    snapshot = _snapshot_190_2022()
    telefono = casillas_by_id(snapshot.revision)[_TELEFONO]
    computed = CasillaObservation(
        casilla_id=_TELEFONO,
        value=Decimal("0"),
        formula_id="synthetic-text-target",
        op="value",
        legal_refs=telefono.legal_refs,
        source_refs=telefono.source_refs,
    )

    with pytest.raises(RegistryValidationError, match="cannot carry a numeric observation"):
        materialise_observations(
            values={_TELEFONO: Decimal("0")},
            computed_provenance={_TELEFONO: computed},
            casillas_by_id=casillas_by_id(snapshot.revision),
        )


def test_a_populated_text_casilla_still_materialises_as_text() -> None:
    """The detector does not refuse the text channel it protects."""
    snapshot = _snapshot_190_2022()

    observations = materialise_observations(
        values={},
        text_values={_TELEFONO: "600123456"},
        computed_provenance={},
        casillas_by_id=casillas_by_id(snapshot.revision),
    )

    assert [(item.casilla_id, item.value_kind, item.value) for item in observations] == [
        (_TELEFONO, CasillaObservationValueKind.TEXT, "600123456"),
    ]


def test_a_formula_reading_a_text_casilla_as_a_number_is_refused() -> None:
    snapshot = _snapshot_190_2022()

    with pytest.raises(RegistryValidationError, match="cannot be read as a numeric formula operand"):
        evaluate_expression(
            FormulaExpression.model_validate({"casilla_id": _TELEFONO}),
            values={},
            binding_values={},
            parameters={},
            date_context={"filing_period": date(2022, 12, 31)},
            relation_values={},
            unresolved_relation_ids=frozenset(),
            unresolved_casilla_ids=set(),
            operand_refs=[],
            operand_casilla_refs=[],
            operand_values=[],
            text_casilla_ids=text_family_casilla_ids(snapshot.revision.casillas),
        )
