"""Boolean-semantics Modelo 100 profile bindings travel the boolean channel.

Two Modelo 100 profile bindings carry a yes/no legal fact:

``renta-profile-anualidades-sin-minimo-descendientes``
    LIRPF art. 64 grants the anualidades por alimentos separate-escala régimen
    only to a payer "sin derecho a la aplicación por estos últimos del mínimo
    por descendientes previsto en el artículo 58". Whether the payer holds that
    right is a yes/no fact, not an amount.

``renta-profile-has-economic-activity``
    Whether the taxpayer declares rendimientos de actividades económicas at all
    (LIRPF arts. 27/30), gating the estimación directa rendimiento neto chain.

Both previously declared ``data_type = "money"`` on the Decimal channel and
their injectors emitted ``Decimal("1")``/``Decimal("0")``, so a truth value was
labelled as currency and a "zero euros" reading was indistinguishable from a
"no" reading. These tests pin the corrected contract against the real compiled
registry and the real resolver, and hold the consuming formulas to predicate
use rather than arithmetic on a truth value.
"""

from __future__ import annotations

from typing import Any

import pytest

from cadrumo.application.modelo.profile_binding import (
    inject_derived_anualidades_eligibility_facts,
    resolve_profile_binding_value,
)
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.binding_value_contract import (
    BindingDataType,
    BindingValueChannel,
)
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_ANUALIDADES_BINDING = "renta-profile-anualidades-sin-minimo-descendientes"
_ECONOMIC_ACTIVITY_BINDING = "renta-profile-has-economic-activity"
_MODELO_100_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)


def _snapshot(year: int) -> RegistrySnapshot:
    return bundled_authority().snapshot("100", filing_year=year, period="0A")


def _binding(year: int, binding_id: str) -> Any:
    revision = _snapshot(year).revision
    return next((b for b in revision.bindings if b.id == binding_id), None)


@pytest.mark.parametrize("year", _MODELO_100_YEARS)
@pytest.mark.parametrize("binding_id", [_ANUALIDADES_BINDING, _ECONOMIC_ACTIVITY_BINDING])
def test_declared_boolean_bindings_use_the_boolean_channel(year: int, binding_id: str) -> None:
    """Every revision declaring either binding declares it boolean on the boolean channel.

    A revision that does not declare the binding is not a failure -- the
    economic-activity predicate only exists from 2025 -- but a revision that
    declares it on the Decimal channel is the defect this pins.
    """
    binding = _binding(year, binding_id)
    if binding is None:
        pytest.skip(f"revision {year} does not declare {binding_id}")
    assert binding.value.data_type is BindingDataType.BOOLEAN
    assert binding.value.channel is BindingValueChannel.BOOLEAN


@pytest.mark.parametrize("year", _MODELO_100_YEARS)
def test_anualidades_injector_emits_a_real_bool_for_both_truth_values(year: int) -> None:
    """The real derivation writes ``bool``, not a Decimal standing in for one.

    ``Decimal("1") == True`` in Python, so an equality assertion could not tell
    the two encodings apart; identity can, which is why both branches assert
    ``is``.
    """
    snapshot = _snapshot(year)

    eligible: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": "2015-05-01",
        "renta_family.descendiente.0.custodia_compartida": "false",
    }
    shared: dict[str, object] = {
        "renta_family.descendiente.0.birth_date": "2015-05-01",
        "renta_family.descendiente.0.custodia_compartida": "true",
    }
    key = f"renta_family.anualidades_sin_minimo_descendientes_{year}"

    eligible_narrowed: Any = eligible
    shared_narrowed: Any = shared
    inject_derived_anualidades_eligibility_facts(eligible_narrowed, snapshot)
    inject_derived_anualidades_eligibility_facts(shared_narrowed, snapshot)

    assert eligible[key] is True
    assert shared[key] is False


def test_economic_activity_binding_resolves_to_a_real_bool_for_both_truth_values() -> None:
    """The real profile resolver returns ``bool`` for the activity predicate."""
    binding = _binding(2025, _ECONOMIC_ACTIVITY_BINDING)
    assert binding is not None

    present = resolve_profile_binding_value(
        binding,
        {"taxpayer_type.irpf_income_categories": "trabajo,actividad_economica"},
    )
    absent = resolve_profile_binding_value(
        binding,
        {"taxpayer_type.irpf_income_categories": "trabajo,capital_mobiliario"},
    )
    assert present is True
    assert absent is False


@pytest.mark.parametrize("year", _MODELO_100_YEARS)
@pytest.mark.parametrize("binding_id", [_ANUALIDADES_BINDING, _ECONOMIC_ACTIVITY_BINDING])
def test_no_consuming_formula_does_arithmetic_on_the_truth_value(year: int, binding_id: str) -> None:
    """A boolean may gate a branch; it may never be an arithmetic operand.

    Multiplying a régimen flag by an amount is arithmetic on a truth value: it
    reads "no" as the number zero and silently produces a filing-grade amount
    from a fact that carries no magnitude. This walks the real compiled
    expression trees and refuses the binding as an operand of any arithmetic
    op, leaving predicate positions (``if_then_else`` conditions, ``equal``)
    legal.
    """
    arithmetic_ops = {"add", "subtract", "multiply", "divide", "min", "max", "negate", "sum"}
    revision = _snapshot(year).revision

    def walk(node: object, *, under_arithmetic: bool) -> list[str]:
        violations: list[str] = []
        if isinstance(node, dict):
            if node.get("binding") == binding_id and under_arithmetic:
                violations.append(binding_id)
            op = node.get("op")
            nested = op in arithmetic_ops if isinstance(op, str) else under_arithmetic
            for key, value in node.items():
                if key in {"op", "binding"}:
                    continue
                violations.extend(walk(value, under_arithmetic=nested))
        elif isinstance(node, (list, tuple)):
            for item in node:
                violations.extend(walk(item, under_arithmetic=under_arithmetic))
        return violations

    for formula in revision.formulas:
        expression = formula.expression
        payload = expression.model_dump() if hasattr(expression, "model_dump") else expression
        assert not walk(payload, under_arithmetic=False), (
            f"formula {formula.id!r} in revision {year} uses boolean binding {binding_id!r} as an arithmetic operand"
        )
