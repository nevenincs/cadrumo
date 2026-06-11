"""Oracle + anti-tautology tests for Art. 81 LIRPF deducción maternidad (casilla 0611).

Art. 81 LIRPF formula: sum(min(meses_trabajados × 100, 1_200)) per eligible hijo menor de 3.
Eligibility: is_eligible_menor_tres(filing_year) must be True (age < 3 at year-end AND
cohabiting). Only descendants with meses_madre_trabajo_2024 > 0 contribute.

Oracle anchoring:
  - 2 hijos, each 12 months → min(12×100,1200) + min(12×100,1200) = 1200 + 1200 = 2400
  - 2 hijos, 6 and 12 months → min(6×100,1200) + min(12×100,1200) = 600 + 1200 = 1800

Anti-tautology: change meses from 0 to 6 → 0611 must change from 0 to 600 (non-trivially).

Helper function tests (CLI layer, no profile needed):
  _compute_deduccion_maternidad_0611: same oracle + anti-tautology
  _parse_meses_trabajo_hijo_spec: valid + invalid inputs
  descendant_facts roundtrip: meses_madre_trabajo stored and reloaded
"""

from __future__ import annotations

from datetime import date

import pytest

from .._descendant_facts import (
    descendant_facts_from_list,
    descendant_list_from_facts,
    parse_descendiente_flag,
)
from ..family import DescendantInfo, RentaFamilyProfile

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
# RentaFamilyProfile.deduccion_maternidad_0611 — oracle tests
# ---------------------------------------------------------------------------


class TestDeduccionMaternidad0611Oracle:
    """Oracle values derived from Art. 81 LIRPF: sum(min(meses×100, 1200)) per hijo menor 3."""

    def test_two_hijos_12_months_each_gives_2400(self) -> None:
        """2 hijos × 12 meses each → 1200 + 1200 = 2400."""
        profile = RentaFamilyProfile(
            descendientes=(
                _hijo_menor_3(12),
                _hijo_menor_3(12),
            ),
        )
        assert profile.deduccion_maternidad_0611(2024) == 2400

    def test_two_hijos_6_and_12_months_gives_1800(self) -> None:
        """2 hijos, 6 and 12 meses → 600 + 1200 = 1800."""
        profile = RentaFamilyProfile(
            descendientes=(
                _hijo_menor_3(6),
                _hijo_menor_3(12),
            ),
        )
        assert profile.deduccion_maternidad_0611(2024) == 1800

    def test_one_hijo_6_months_gives_600(self) -> None:
        """1 hijo × 6 meses → min(600, 1200) = 600."""
        profile = RentaFamilyProfile(descendientes=(_hijo_menor_3(6),))
        assert profile.deduccion_maternidad_0611(2024) == 600

    def test_one_hijo_12_months_gives_1200(self) -> None:
        """Cap: 12 meses × 100 = 1200, which hits the 1200 ceiling."""
        profile = RentaFamilyProfile(descendientes=(_hijo_menor_3(12),))
        assert profile.deduccion_maternidad_0611(2024) == 1200

    def test_zero_meses_gives_zero(self) -> None:
        """A hijo menor-3 with meses=0 does not contribute."""
        profile = RentaFamilyProfile(descendientes=(_hijo_menor_3(0),))
        assert profile.deduccion_maternidad_0611(2024) == 0


# ---------------------------------------------------------------------------
# Anti-tautology: incrementing meses must change the result non-trivially
# ---------------------------------------------------------------------------


class TestDeduccionMaternidadAntiTautology:
    """Verify the formula is actually exercised, not trivially returning a constant."""

    def test_zero_vs_six_meses_differs_by_600(self) -> None:
        """Changing meses from 0 to 6 must increase 0611 by exactly 600."""
        p_zero = RentaFamilyProfile(descendientes=(_hijo_menor_3(0),))
        p_six = RentaFamilyProfile(descendientes=(_hijo_menor_3(6),))
        result_zero = p_zero.deduccion_maternidad_0611(2024)
        result_six = p_six.deduccion_maternidad_0611(2024)
        # If formula were broken and always returned a constant, these would match.
        assert result_six - result_zero == 600

    def test_hijo_no_menor_3_excluded(self) -> None:
        """A 4-year-old with meses=12 must NOT contribute to 0611."""
        profile_with_older = RentaFamilyProfile(descendientes=(_hijo_no_menor_3(),))
        profile_empty = RentaFamilyProfile()
        # Both must be 0; the older child's meses_madre_trabajo_2024 must be ignored.
        assert profile_with_older.deduccion_maternidad_0611(2024) == 0
        assert profile_empty.deduccion_maternidad_0611(2024) == 0
        # Anti-tautology proof: adding a qualified younger child makes it non-zero.
        profile_mixed = RentaFamilyProfile(descendientes=(_hijo_no_menor_3(), _hijo_menor_3(6)))
        assert profile_mixed.deduccion_maternidad_0611(2024) == 600

    def test_non_cohabiting_hijo_excluded(self) -> None:
        """A hijo menor-3 not cohabiting with taxpayer must not contribute."""
        non_cohabiting = DescendantInfo(
            birth_date=date(2022, 6, 1),
            convive_con_contribuyente=False,
            meses_madre_trabajo_2024=12,
        )
        profile = RentaFamilyProfile(descendientes=(non_cohabiting,))
        assert profile.deduccion_maternidad_0611(2024) == 0


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

    def test_meses_trabajo_12_parsed(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2022-06-01,MESES_TRABAJO=12")
        assert d.meses_madre_trabajo_2024 == 12

    def test_meses_trabajo_6_parsed(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2022-06-01,MESES_TRABAJO=6")
        assert d.meses_madre_trabajo_2024 == 6

    def test_meses_trabajo_absent_defaults_zero(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2022-06-01")
        assert d.meses_madre_trabajo_2024 == 0

    def test_meses_trabajo_zero_accepted(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2022-06-01,MESES_TRABAJO=0")
        assert d.meses_madre_trabajo_2024 == 0

    def test_meses_trabajo_13_raises(self) -> None:
        with pytest.raises(ValueError, match="MESES_TRABAJO must be 0"):
            parse_descendiente_flag("NACIMIENTO=2022-06-01,MESES_TRABAJO=13")

    def test_meses_trabajo_negative_raises(self) -> None:
        with pytest.raises((ValueError, Exception)):
            parse_descendiente_flag("NACIMIENTO=2022-06-01,MESES_TRABAJO=-1")


# ---------------------------------------------------------------------------
# CLI helper functions
# ---------------------------------------------------------------------------


class TestCLIHelpers:
    """Unit tests for compute_deduccion_maternidad_0611 (domain arithmetic)."""

    def test_compute_two_hijos_12_12_gives_2400(self) -> None:
        """Oracle: 2 × 12 meses → 2400."""
        from .._deduccion_maternidad import compute_deduccion_maternidad_0611

        result = compute_deduccion_maternidad_0611([("0", 12), ("1", 12)])
        assert result == 2400

    def test_compute_6_and_12_gives_1800(self) -> None:
        """Oracle: 6 + 12 meses → 1800."""
        from .._deduccion_maternidad import compute_deduccion_maternidad_0611

        result = compute_deduccion_maternidad_0611([("0", 6), ("1", 12)])
        assert result == 1800

    def test_compute_cap_at_1200(self) -> None:
        """Single hijo 12 meses → capped at 1200."""
        from .._deduccion_maternidad import compute_deduccion_maternidad_0611

        assert compute_deduccion_maternidad_0611([("laia", 12)]) == 1200

    def test_compute_zero_meses_gives_zero(self) -> None:
        """Passing 0 meses must return 0, not a non-zero constant."""
        from .._deduccion_maternidad import compute_deduccion_maternidad_0611

        assert compute_deduccion_maternidad_0611([("0", 0)]) == 0

    def test_compute_anti_tautology_delta(self) -> None:
        """Incrementing meses from 6 to 12 must change result by exactly 600."""
        from .._deduccion_maternidad import compute_deduccion_maternidad_0611

        r6 = compute_deduccion_maternidad_0611([("0", 6)])
        r12 = compute_deduccion_maternidad_0611([("0", 12)])
        assert r12 - r6 == 600
