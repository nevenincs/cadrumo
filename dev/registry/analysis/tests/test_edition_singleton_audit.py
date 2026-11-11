"""The edition-singleton gate catches a declaration authored in one edition without a cited difference."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue

from ..edition_singleton_audit import (
    DeclarationView,
    EditionSingletonFinding,
    EditionView,
    LegalWindow,
    render_edition_findings,
    singleton_findings,
    with_paths,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

SUPPORT = SupportedFilingYearsCatalogue(horizon=date.today().year, floor=date.today().year - 3)
YEARS = SUPPORT.years


def _declaration(
    declaration_id: str,
    *,
    family: str = "formulas",
    windows: tuple[LegalWindow, ...] = (),
    **flags: bool,
) -> DeclarationView:
    return DeclarationView(family, declaration_id, windows, **flags)


def _edition(year: int, *declarations: DeclarationView, track: tuple[str, ...] = ()) -> EditionView:
    return EditionView(str(year), date(year, 1, 1), date(year, 12, 31), declarations, track)


def _editions(per_year: dict[int, tuple[DeclarationView, ...]]) -> list[EditionView]:
    return [_edition(year, *per_year.get(year, ())) for year in YEARS]


def _in_force_from(year: int) -> LegalWindow:
    return LegalWindow("provision", date(year, 1, 1), None)


def test_formula_in_a_middle_edition_only_is_flagged() -> None:
    formula = _declaration("incremento", windows=(_in_force_from(YEARS[0]),))
    findings = singleton_findings("100", _editions({YEARS[1]: (formula,)}))
    assert [(f.declaration_id, f.edition) for f in findings] == [("incremento", str(YEARS[1]))]
    assert not findings[0].appearing_cited
    assert not findings[0].disappearing_cited
    assert findings[0].reason == "uncited appearing and disappearing boundary"


def test_formula_in_every_edition_is_clean() -> None:
    formula = _declaration("incremento")
    assert singleton_findings("100", _editions(dict.fromkeys(YEARS, (formula,)))) == ()


def test_newest_edition_formula_cited_by_a_provision_entering_force_in_it_is_clean() -> None:
    formula = _declaration("nuevo", windows=(_in_force_from(YEARS[-1]),))
    assert singleton_findings("100", _editions({YEARS[-1]: (formula,)})) == ()


def test_newest_edition_formula_whose_provision_predates_the_previous_edition_is_flagged() -> None:
    formula = _declaration("nuevo", windows=(_in_force_from(YEARS[-2]),))
    findings = singleton_findings("100", _editions({YEARS[-1]: (formula,)}))
    assert [f.reason for f in findings] == ["uncited appearing boundary"]


def test_oldest_edition_formula_needs_a_provision_that_expired_within_it() -> None:
    expiring = LegalWindow("expired", date(YEARS[0] - 5, 1, 1), date(YEARS[0], 12, 31))
    cited = _declaration("viejo", windows=(expiring,))
    uncited = _declaration("olvidado")
    assert singleton_findings("100", _editions({YEARS[0]: (cited,)})) == ()
    findings = singleton_findings("100", _editions({YEARS[0]: (uncited,)}))
    assert [f.reason for f in findings] == ["uncited disappearing boundary"]


def test_printed_input_casilla_is_form_design_but_a_calculating_casilla_is_audited() -> None:
    input_box = _declaration("1001", family="casillas", calculated=False)
    calculated = _declaration("1002", family="casillas")
    findings = singleton_findings("100", _editions({YEARS[1]: (input_box, calculated)}))
    assert [f.declaration_id for f in findings] == ["1002"]


def test_casilla_stating_it_is_new_on_the_form_and_removed_next_edition_is_clean() -> None:
    casilla = _declaration("1002", family="casillas", states_new_on_form=True, removed_by_next_edition=True)
    assert singleton_findings("100", _editions({YEARS[1]: (casilla,)})) == ()


def _casilla(
    declaration_id: str, *, continuidad: str | None = None, windows: tuple[LegalWindow, ...] = ()
) -> DeclarationView:
    return DeclarationView("casillas", declaration_id, windows, grounded_continuidad_id=continuidad)


def test_casilla_renumbered_by_the_form_is_one_declaration_not_a_singleton() -> None:
    old, new = _casilla("alfa", continuidad="linea"), _casilla("beta", continuidad="linea")
    renumbered = {YEARS[0]: (old,), **dict.fromkeys(YEARS[1:], (new,))}
    assert singleton_findings("100", _editions(renumbered)) == ()
    vanished = {YEARS[0]: (old,), **dict.fromkeys(YEARS[1:], (_casilla("beta", continuidad="otra"),))}
    assert [f.declaration_id for f in singleton_findings("100", _editions(vanished))] == ["alfa"]


def test_casilla_citing_a_provision_entering_force_in_its_edition_is_not_flagged() -> None:
    casilla = _casilla("gamma", windows=(_in_force_from(YEARS[-1]),))
    assert singleton_findings("100", _editions({YEARS[-1]: (casilla,)})) == ()


def test_casilla_in_one_edition_with_neither_continuation_nor_provision_is_flagged() -> None:
    other = _casilla("delta", continuidad="otra")
    stray = _casilla("gamma", windows=(_in_force_from(YEARS[0]),))
    findings = singleton_findings("100", _editions({YEARS[1]: (stray,), YEARS[2]: (other,)}))
    assert [(f.declaration_id, f.reason) for f in findings if f.declaration_id == "gamma"] == [
        ("gamma", "uncited appearing and disappearing boundary")
    ]


def test_editions_of_different_period_tracks_are_not_compared() -> None:
    formula = _declaration("trimestral")
    editions = [_edition(YEARS[0], formula, track=("1T",)), _edition(YEARS[1], track=("01",))]
    assert singleton_findings("369", editions) == ()


def test_single_edition_modelo_has_nothing_to_compare() -> None:
    assert singleton_findings("036", [_edition(YEARS[0], _declaration("solo"))]) == ()


def test_findings_carry_the_authored_file_and_render(tmp_path: Path) -> None:
    formulas = tmp_path / "100" / "revisions" / str(YEARS[1]) / "formulas"
    formulas.mkdir(parents=True)
    authored = formulas / "0001-declarations.toml"
    authored.write_text('[[formulas]]\nid = "incremento"\n', encoding="utf-8")
    finding = EditionSingletonFinding("100", "formulas", "incremento", str(YEARS[1]), False, False)
    (located,) = with_paths([finding], tmp_path)
    assert located.path == authored.as_posix()
    lines = render_edition_findings([located])
    assert lines[0].endswith(": 1")
    assert any(authored.as_posix() in line and "edition=" + str(YEARS[1]) in line for line in lines)
