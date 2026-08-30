"""What the WRITE side owes the Art. 81.2 guardería increase (casilla 0613).

The module name predates its contents and is kept, because the stem is what a
reader greps for when they want the guardería write path. What it covers is the
persistence boundary: which facts the projection emits, which it must never
emit, and what the ``--descendiente`` flag accepts.

It used to also carry oracle and anti-tautology cases for a domain-layer method
that recomputed the whole cap formula in Python. That method had no production
consumer -- the live 0613 comes from the registry formula over injected facts --
so it was retired, and its cases went with it rather than being left to assert a
duplicate of the law that nothing evaluated.

One of those cases was load-bearing and did NOT simply go: the proof that the
cotizaciones term actually binds the ``min``. That behaviour now has its
assertion against the live registry path, driven through the real CLI, and it
landed in the same change that removed this one. A term whose behaviour is
asserted nowhere is how a gap ships with every gate green.
"""

from __future__ import annotations

from datetime import date

import pytest

from ..descendant import DescendantInfo
from ..descendant_facts import (
    descendant_facts_from_list,
    descendant_list_from_facts,
    parse_descendiente_flag,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _hijo_guarderia(gastos: int) -> DescendantInfo:
    """Child born 2022-06-01 → age 2 at 2024-12-31, eligible menor-3."""
    return DescendantInfo(
        birth_date=date(2022, 6, 1),
        gastos_guarderia_euros=gastos,
    )


def _hijo_no_menor_3(gastos: int) -> DescendantInfo:
    """Child born 2020-01-01 → age 4 at 2024-12-31, NOT eligible for Art. 81.2."""
    return DescendantInfo(
        birth_date=date(2020, 1, 1),
        gastos_guarderia_euros=gastos,
    )


# ---------------------------------------------------------------------------
# Persistence: gastos_guarderia aggregate stored in descendant_facts_from_list
# ---------------------------------------------------------------------------


class TestGastosGuarderiaFactPersistence:
    """The projection stores per-child gastos and never the engine-owned aggregate.

    The aggregate was previously materialised here at write time, and only when
    the sum was positive. It is now injected at calculate time from these same
    per-child facts, unconditionally, so a filer with no childcare spend gets a
    zero rather than an absent binding. Two consequences this class pins:

    the projection must NOT emit the aggregate -- the write door refuses that
    path outright, so an emission would refuse every legitimate childcare save
    in the same batch; and the per-child figures it does emit must still carry
    everything the injector needs to recompute the sum.
    """

    def test_aggregate_is_not_emitted_even_when_eligible_hijos_have_gastos(self) -> None:
        """The engine-owned aggregate never reaches the write door.

        Inverted: this previously asserted the summed aggregate was stored. The
        positive case is the one that matters, because the old emission was
        conditional on a positive sum and so was invisible in the zero case.
        """
        hijos = (
            _hijo_guarderia(2500),
            _hijo_guarderia(4000),
        )
        facts = dict(descendant_facts_from_list(hijos))
        assert "renta_family.gastos_guarderia_reales_2024" not in facts

    def test_per_child_gastos_survive_for_the_injector_to_sum(self) -> None:
        """Each eligible child's own figure is stored, which is what the injector reads."""
        hijos = (
            _hijo_guarderia(2500),
            _hijo_guarderia(4000),
        )
        facts = dict(descendant_facts_from_list(hijos))
        assert facts["renta_family.descendiente.0.gastos_guarderia"] == "2500"
        assert facts["renta_family.descendiente.1.gastos_guarderia"] == "4000"

    def test_a_non_eligible_child_still_stores_its_own_gastos(self) -> None:
        """Eligibility filtering is the injector's job, not the projection's.

        The projection is a faithful record of what the operator declared. Which
        children count toward the Art. 81.2 sum is an Art. 58.3 question the
        injector answers at calculate time, against the filing year it is
        computing rather than a year baked into the stored facts.
        """
        facts = dict(descendant_facts_from_list((_hijo_guarderia(2000), _hijo_no_menor_3(9999))))
        assert facts["renta_family.descendiente.0.gastos_guarderia"] == "2000"
        assert facts["renta_family.descendiente.1.gastos_guarderia"] == "9999"

    def test_roundtrip_gastos_via_facts(self) -> None:
        """gastos_guarderia_euros survives descendant_facts_from_list → descendant_list_from_facts roundtrip."""
        original = (
            DescendantInfo(
                birth_date=date(2022, 6, 1),
                gastos_guarderia_euros=1500,
            ),
        )
        facts = dict(descendant_facts_from_list(original))
        assert facts["renta_family.descendiente.0.gastos_guarderia"] == "1500"
        reloaded = descendant_list_from_facts(facts)
        assert len(reloaded) == 1
        assert reloaded[0].gastos_guarderia_euros == 1500


# ---------------------------------------------------------------------------
# parse_descendiente_flag: GASTOS_GUARDERIA= key acceptance
# ---------------------------------------------------------------------------


class TestParseDescendienteFlagGastosGuarderia:
    """parse_descendiente_flag must accept GASTOS_GUARDERIA= and validate >= 0."""

    def test_gastos_accepted(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2022-06-01,GASTOS_GUARDERIA=1500")
        assert d.gastos_guarderia_euros == 1500

    def test_gastos_zero_accepted(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2022-06-01,GASTOS_GUARDERIA=0")
        assert d.gastos_guarderia_euros == 0

    def test_gastos_absent_defaults_to_zero(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2022-06-01")
        assert d.gastos_guarderia_euros == 0

    def test_gastos_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="GASTOS_GUARDERIA"):
            parse_descendiente_flag("NACIMIENTO=2022-06-01,GASTOS_GUARDERIA=-1")
