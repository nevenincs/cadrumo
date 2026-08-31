"""CLI discovery tests for the single-casilla describe verb.

Exercises ``aeat app modelo casilla <modelo> <casilla>`` end to end through
the cached Click runner against the real bundled registry: a known casilla
surfaces its label, legal / source grounding, and input kind sourced from the
authoritative ``CasillaDefinition`` on the resolved snapshot; a computed
casilla additionally carries its resolved formula id and expression; and an
unknown casilla is refused instructively, naming the ``casillas`` verb that
lists every valid id.
"""

from __future__ import annotations

import json

import pytest

from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _envelope_result(args: list[str]) -> dict[str, object]:
    invocation = invoke_cached_cli(["--format", "json", *args])
    assert invocation.exit_code == 0, invocation.output
    envelope = json.loads(invocation.output)
    assert envelope["command"] == "modelo.casilla"
    result = envelope["result"]
    assert isinstance(result, dict)
    return STR_KEYED_MAPPING_ADAPTER.validate_python(result)


def test_casilla_describe_surfaces_grounding_for_bound_casilla() -> None:
    """A bound casilla returns its label, input kind, and legal / source grounding."""

    result = _envelope_result(
        ["app", "modelo", "casilla", "130", "01", "--year", "2025", "--period", "1T"],
    )

    assert result["modelo"] == "130"
    assert result["casilla_id"] == "01"
    assert result["number"] == "01"
    assert result["input_kind"] == "bound"
    assert result["label"]
    # Grounding is carried at the operator boundary (aeat-calculation-grounding).
    assert result["legal_refs"], result
    assert result["source_refs"], result
    # A bound casilla is not computed: it carries no formula expression.
    assert result["formula_id"] is None
    assert result["formula_expression"] is None


def test_casilla_describe_carries_formula_expression_for_computed_casilla() -> None:
    """A computed casilla resolves its formula id and structured expression."""

    result = _envelope_result(
        ["app", "modelo", "casilla", "130", "03", "--year", "2025", "--period", "1T"],
    )

    assert result["casilla_id"] == "03"
    assert result["input_kind"] == "computed"
    assert result["formula_id"] == "modelo-130-rendimiento-neto"
    expression = result["formula_expression"]
    assert isinstance(expression, dict)
    # The registry formula expression carries its operator discriminator.
    assert "op" in expression, expression
    assert result["legal_refs"], result
    assert result["source_refs"], result


def test_casilla_describe_refuses_unknown_casilla_instructively() -> None:
    """An unknown casilla id is refused with guidance to the casillas verb."""

    invocation = invoke_cached_cli(
        ["app", "modelo", "casilla", "130", "ZZZ999", "--year", "2025", "--period", "1T"],
    )

    assert invocation.exit_code != 0, invocation.output
    message = invocation.output
    assert "ZZZ999" in message
    assert "casillas" in message
    assert "130" in message
