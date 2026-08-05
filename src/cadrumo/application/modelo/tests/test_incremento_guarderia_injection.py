"""The Art. 81.2 increment reaches the calculate path as a resolved fact.

The domain aggregate is proven against the manual's oracles in its own module.
What this covers is the WIRING: that the injector is reached with a real
registry snapshot, resolves its cap from the registry rather than a literal, and
lands the value at the key the binding declares.

Nothing here asserts a casilla value, because the 0613 formula still consumes
its old terms. That is the point of landing the injector separately — the fact
is produced and available, and no computed figure moves until the formula is
rewritten to read it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import RegistrySnapshot
from ....domain.contribuyente import DescendantInfo, descendant_facts_from_list
from ....domain.contribuyente._guarderia_mensual import parse_guarderia_mensual
from .._profile_binding import (
    _declared_profile_selectors,
    _guarderia_cap_anual,
    _inject_derived_incremento_guarderia_facts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = 2024
_KEY = f"renta_family.incremento_guarderia_{_YEAR}"


def _snapshot(year: int = _YEAR) -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("100", filing_year=year, period="0A")


def _facts(child: DescendantInfo) -> dict[str, object]:
    return dict(descendant_facts_from_list((child,)))


def _manual_worked_child() -> DescendantInfo:
    """The manual's hijo mayor: four Art. 81.1 months, two complete spend months."""
    return DescendantInfo(
        birth_date=date(2022, 3, 1),
        meses_madre_trabajo_2024=4,
        gastos_guarderia_mensuales=parse_guarderia_mensual("5:1145;6:1145", field="test"),
    )


def test_the_binding_declares_the_selector_the_injector_writes() -> None:
    """Without this the injector is inert and every other assertion is vacuous.

    The derived path is gated on a declared consuming selector, so a binding
    that named a different key would leave the fact unwritten and the casilla
    silently unresolved — with no failure anywhere to say so.
    """
    assert _KEY in _declared_profile_selectors(_snapshot().revision)


def test_the_cap_resolves_from_the_registry_parameter() -> None:
    """The 1.000 figure comes from the parameter, not from a literal in code.

    It previously existed only inside the formula expression, which the
    application layer cannot read.
    """
    assert _guarderia_cap_anual(_snapshot()) == Decimal("1000")


def test_the_injector_lands_the_manual_worked_figure() -> None:
    """End of the wiring: a real snapshot in, the manual's 166,67 out."""
    index = _facts(_manual_worked_child())

    _inject_derived_incremento_guarderia_facts(index, _snapshot(), _declared_profile_selectors(_snapshot().revision))

    assert index[_KEY] == Decimal("166.67")


def test_the_injector_is_inert_where_no_consumer_is_declared() -> None:
    """The gate must gate. A revision declaring no binding gets no fact.

    Positive control for the assertion above: without it, an injector that
    ignored the gate entirely would pass every other test here.
    """
    index = _facts(_manual_worked_child())

    _inject_derived_incremento_guarderia_facts(index, _snapshot(), frozenset())

    assert _KEY not in index


def test_a_stored_value_at_the_derived_key_is_overwritten() -> None:
    """The path is derived, so a stored fact there can only be stale or planted.

    Deferring to it would substitute an operator's number for the law's — the
    same defect the sibling guardería injector documents.
    """
    index = _facts(_manual_worked_child())
    index[_KEY] = Decimal("999999")

    _inject_derived_incremento_guarderia_facts(index, _snapshot(), _declared_profile_selectors(_snapshot().revision))

    assert index[_KEY] == Decimal("166.67")


def test_a_childless_profile_resolves_to_zero_rather_than_absent() -> None:
    """Zero is the computed answer for a filer with no descendants.

    Distinct from the unresolvable cases, which leave the fact ABSENT so the
    casilla stays visibly unresolved instead of reading as a computed nil.
    """
    index: dict[str, object] = {}

    _inject_derived_incremento_guarderia_facts(index, _snapshot(), _declared_profile_selectors(_snapshot().revision))

    assert index[_KEY] == Decimal("0")
