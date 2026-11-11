"""The year-independence audits catch their defects and the baseline only shrinks."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue

from ..edition_member_continuity import CasillaFact, dropped_member_findings
from ..edition_singleton_audit import EditionView
from ..year_in_declaration_audit import years_named_in
from ..year_independence_gate import compare_with_baseline, read_baseline, render_baseline

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

SUPPORT = SupportedFilingYearsCatalogue(horizon=date.today().year, floor=date.today().year - 3)
YEARS = SUPPORT.years


def _edition(year: int, **casillas: CasillaFact) -> EditionView:
    return EditionView(str(year), date(year, 1, 1), date(year, 12, 31), (), (), casillas)


def _fact(*, formula: bool = False, binding: bool = False, role: str = "role", cites: bool = False) -> CasillaFact:
    return CasillaFact(role, formula, binding, cites)


def test_formula_present_in_one_adjacent_edition_and_absent_in_the_next_is_flagged() -> None:
    editions = [_edition(YEARS[0], c0613=_fact()), _edition(YEARS[1], c0613=_fact(formula=True))]
    (finding,) = dropped_member_findings("100", editions)
    assert (finding.casilla_id, finding.member) == ("c0613", "formula")
    assert (finding.present_in, finding.absent_in) == (str(YEARS[1]), str(YEARS[0]))


def test_binding_dropped_going_forward_is_flagged_with_the_direction() -> None:
    editions = [_edition(YEARS[1], c0150=_fact(binding=True)), _edition(YEARS[2], c0150=_fact())]
    (finding,) = dropped_member_findings("100", editions)
    assert (finding.member, finding.present_in, finding.absent_in) == ("binding", str(YEARS[1]), str(YEARS[2]))


def test_difference_cited_by_the_changed_edition_or_with_a_different_role_is_not_flagged() -> None:
    cited = [_edition(YEARS[0], c1=_fact(formula=True)), _edition(YEARS[1], c1=_fact(cites=True))]
    other_role = [_edition(YEARS[0], c1=_fact(formula=True)), _edition(YEARS[1], c1=_fact(role="other"))]
    assert dropped_member_findings("100", cited) == ()
    assert dropped_member_findings("100", other_role) == ()


def test_identical_adjacent_editions_are_clean() -> None:
    editions = [_edition(year, c1=_fact(formula=True, binding=True)) for year in YEARS]
    assert dropped_member_findings("100", editions) == ()


def test_year_named_in_a_profile_key_is_found_only_inside_the_envelope() -> None:
    year = YEARS[-1]
    assert years_named_in(f"renta.incremento_guarderia_{year}", YEARS) == (year,)
    assert years_named_in("renta.incremento_guarderia", YEARS) == ()
    assert years_named_in(f"renta.codigo_{year}9", YEARS) == ()
    assert years_named_in(f"renta.tier_{YEARS[0] - 50}", YEARS) == ()


def test_ratchet_fails_on_a_new_finding_and_on_a_stale_baseline_entry() -> None:
    held = compare_with_baseline(["a", "b"], ["a", "b"])
    assert held.holds
    grown = compare_with_baseline(["a", "b", "c"], ["a", "b"])
    assert grown.new == ("c",)
    assert not grown.holds
    shrunk = compare_with_baseline(["a"], ["a", "b"])
    assert shrunk.stale == ("b",)
    assert not shrunk.holds


def test_baseline_round_trips_sorted_without_comments(tmp_path: Path) -> None:
    path = tmp_path / "baseline.txt"
    path.write_text(render_baseline(["b|2", "a|1", "a|1"]), encoding="utf-8")
    assert read_baseline(path) == ("a|1", "b|2")
    assert read_baseline(tmp_path / "missing.txt") == ()
