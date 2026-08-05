"""What survives around the Art. 81 LIRPF deducción maternidad (casilla 0611).

Covers the live arithmetic, the persistence boundary and the flag: the oracle and
anti-tautology cases for ``compute_deduccion_maternidad_0611``, the roundtrip of
``meses_madre_trabajo_2024`` through the fact index, and what the
``--descendiente`` flag accepts.

Art. 81 LIRPF: ``sum(min(meses_trabajados × 100, 1_200))`` per eligible hijo.
Oracle anchoring: two hijos at twelve months each gives 1200 + 1200 = 2400; at
six and twelve, 600 + 1200 = 1800. Anti-tautology: moving meses from zero to six
must move the result from 0 to 600.

A duplicate of that oracle used to run against a profile METHOD that recomputed
the same formula and had no production consumer. The method was retired and its
cases went with it, keeping the ones above, which drive the function the
calculate path actually calls.

Two of the retired cases asserted ELIGIBILITY -- that a child over three, or one
not cohabiting, contributes nothing. They are not replaced here because the live
path has no counterpart to replace them against: it consumes an
operator-supplied list of (hijo, meses) pairs and performs no filtering of its
own. That asymmetry is a real observation about the maternidad path rather than
a gap in this module, and it is recorded where design questions go.
"""

from __future__ import annotations

from datetime import date

import pytest

from .._descendant_facts import (
    descendant_facts_from_list,
    descendant_list_from_facts,
    parse_descendiente_flag,
)
from ..family import DescendantInfo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _hijo_menor_3(meses: int) -> DescendantInfo:
    """Child born 2022-06-01 → age 2 at 2024-12-31, eligible menor-3."""
    return DescendantInfo(
        birth_date=date(2022, 6, 1),
        meses_madre_trabajo_2024=meses,
    )


def _hijo_no_menor_3() -> DescendantInfo:
    """Child born 2020-01-01 → age 4 at 2024-12-31, NOT menor-3 eligible."""
    return DescendantInfo(
        birth_date=date(2020, 1, 1),
        meses_madre_trabajo_2024=12,
    )


# ---------------------------------------------------------------------------
# Roundtrip: meses_madre_trabajo stored and reloaded from facts
# ---------------------------------------------------------------------------


class TestMesesTornoFacts:
    """Verify meses_madre_trabajo_2024 survives descendant_facts roundtrip."""

    def test_roundtrip_meses_stored_and_reloaded(self) -> None:
        """Fact serialisation: meses=6 → stored as '6' → reloaded as 6."""
        original = _hijo_menor_3(6)
        facts = dict(descendant_facts_from_list((original,)))

        assert facts.get("renta_family.descendiente.0.meses_madre_trabajo") == "6"

        reloaded = descendant_list_from_facts(facts)
        assert len(reloaded) == 1
        assert reloaded[0].meses_madre_trabajo_2024 == 6

    def test_roundtrip_zero_meses_not_stored(self) -> None:
        """Fact serialisation: meses=0 is not stored (absent means 0)."""
        original = _hijo_menor_3(0)
        facts = dict(descendant_facts_from_list((original,)))

        assert "renta_family.descendiente.0.meses_madre_trabajo" not in facts

        reloaded = descendant_list_from_facts(facts)
        assert reloaded[0].meses_madre_trabajo_2024 == 0

    def test_roundtrip_preserves_other_fields(self) -> None:
        """Adding meses does not disturb other fields on roundtrip."""
        original = DescendantInfo(
            birth_date=date(2022, 6, 1),
            custodia_compartida=True,
            meses_madre_trabajo_2024=9,
        )
        facts = dict(descendant_facts_from_list((original,)))
        reloaded = descendant_list_from_facts(facts)
        assert reloaded[0] == original


# ---------------------------------------------------------------------------
# parse_descendiente_flag: MESES_TRABAJO= key acceptance
# ---------------------------------------------------------------------------


class TestParseDescendienteFlagMesesTrabajo:
    """parse_descendiente_flag must accept MESES_TRABAJO= and validate 0–12 range."""

    def test_meses_trabajo_parsed(self) -> None:
        cases = (
            ("twelve", "NACIMIENTO=2022-06-01,MESES_TRABAJO=12", 12),
            ("six", "NACIMIENTO=2022-06-01,MESES_TRABAJO=6", 6),
            ("zero", "NACIMIENTO=2022-06-01,MESES_TRABAJO=0", 0),
            ("absent", "NACIMIENTO=2022-06-01", 0),
        )
        for case_id, spec, expected in cases:
            d = parse_descendiente_flag(spec)
            assert d.meses_madre_trabajo_2024 == expected, case_id

    def test_meses_trabajo_out_of_range_raises(self) -> None:
        for case_id, spec in (
            ("above-range", "NACIMIENTO=2022-06-01,MESES_TRABAJO=13"),
            ("negative", "NACIMIENTO=2022-06-01,MESES_TRABAJO=-1"),
        ):
            try:
                with pytest.raises(ValueError, match="MESES_TRABAJO must be 0"):
                    parse_descendiente_flag(spec)
            except AssertionError as exc:
                raise AssertionError(f"out-of-range MESES_TRABAJO was accepted: {case_id}") from exc


# ---------------------------------------------------------------------------
# CLI helper functions
# ---------------------------------------------------------------------------


class TestCLIHelpers:
    """Unit tests for compute_deduccion_maternidad_0611 (domain arithmetic)."""

    def test_compute_oracle_examples(self) -> None:
        """Domain arithmetic matches the Art. 81 oracle examples."""
        from .._deduccion_maternidad import compute_deduccion_maternidad_0611

        cases = (
            ("two-hijos-full-year", [("0", 12), ("1", 12)], 2400),
            ("two-hijos-partial-and-full", [("0", 6), ("1", 12)], 1800),
            ("one-hijo-cap", [("laia", 12)], 1200),
            ("zero-months", [("0", 0)], 0),
        )
        for case_id, inputs, expected in cases:
            assert compute_deduccion_maternidad_0611(inputs) == expected, case_id

    def test_compute_anti_tautology_delta(self) -> None:
        """Incrementing meses from 6 to 12 must change result by exactly 600."""
        from .._deduccion_maternidad import compute_deduccion_maternidad_0611

        r6 = compute_deduccion_maternidad_0611([("0", 6)])
        r12 = compute_deduccion_maternidad_0611([("0", 12)])
        assert r12 - r6 == 600
