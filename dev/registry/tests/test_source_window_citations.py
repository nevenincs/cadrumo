"""Detector teeth for the source-window citation screen.

A `[sources.*]` window is overlap-checked against a revision's span, but nothing
checks it at load time, so a source whose window excludes the revision citing it
is silent. Modelo 345 carried two: its base order declared a window opening
2023-01-01 while the 2022 revision cited it in five files, because the window
recorded the January of PRESENTATION rather than the ejercicio governed.

The screen's value is not the count but the CLASSIFICATION. Two citing roles sit
outside their own span correctly -- a continuity evolution names the design a
concept came FROM, and a deadline window names the calendar of the year the
return is PRESENTED -- and reporting those as defects would bury the population
that matters under a pile of correct declarations. So there is one tooth per
role: each test plants a citation of one role and asserts it lands in that role
and not another.

The registries here are constructed and hydrated through the real loader. A
screen only reachable through the live corpus cannot be handed a planted defect,
and the live corpus changes under a test that asserts counts against it. They
are hydrated, not read raw, because a revision authored as a delta cites through
inheritance what none of its own files state.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..analysis.source_window_citations import (
    ROLES,
    classify,
    family_stem,
    has_current_sibling,
    scan,
    screen_line,
    tally,
    trailing_year,
)
from ..compiler.loader import load_catalogue_file, load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF: Final = "ley-58-2003:art-29"

#: Four consecutive synthetic exercises the planted registries are written over.
Y1: Final = filing_year_envelope().floor
Y2: Final = Y1 + 1
Y3: Final = Y2 + 1
Y4: Final = Y3 + 1


def _jan_1(year: int) -> str:
    return date(year, 1, 1).isoformat()


def _dec_31(year: int) -> str:
    return date(year, 12, 31).isoformat()


#: When an orden published after the third exercise took effect.
_EFFECTIVE_AFTER_Y3: Final = date(Y4, 7, 1).isoformat()

#: ``(applies_from, applies_to)`` per planted source; ``None`` leaves that side open.
type SourceWindows = dict[str, tuple[str | None, str | None]]


def build_catalogue(
    root: Path,
    sources: SourceWindows | None = None,
    legal: dict[str, dict[str, str]] | None = None,
) -> RegistryCatalogues:
    """Plant one catalogue file and compile it through the real catalogue loader."""
    blocks = []
    for source_id, (applies_from, applies_to) in (sources or {}).items():
        lines = [
            f'[sources."{source_id}"]',
            'evidence_tier = "layout_authority"',
            'authority = "boe"',
            'kind = "form_spec"',
            'corpus_path = "corpus/normatives/pdf/planted.pdf"',
            f'sha256 = "{"ab" * 32}"',
            "bytes = 10",
            "retrieved_at = 2026-06-28",
            'source_url = "https://www.boe.es/planted.pdf"',
            'review_status = "pending_review"',
        ]
        if applies_from is not None:
            lines.append(f"applies_from = {applies_from}")
        if applies_to is not None:
            lines.append(f"applies_to = {applies_to}")
        blocks.append("\n".join(lines))
    for ref_id, fields in (legal or {}).items():
        lines = [
            f'[legal."{ref_id}"]',
            'evidence_tier = "legal_authority"',
            'authority = "boe"',
            'kind = "orden"',
            'corpus_ref = "corpus/normatives/html/planted.html#a1"',
            'document_id = "BOE-A-2023-17429"',
            'permalink = "https://www.boe.es/buscar/act.php?id=BOE-A-2023-17429#a1"',
            'review_status = "agent_reviewed"',
            "reviewed_at = 2026-06-28",
            'reviewed_by = "agent-review"',
            'required_text = ["planted"]',
        ]
        lines += [f"{key} = {value}" for key, value in fields.items()]
        blocks.append("\n".join(lines))
    root.mkdir(parents=True, exist_ok=True)
    path = root / "planted.toml"
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return load_catalogue_file(path)


def _listed(refs: list[str]) -> str:
    return "[" + ", ".join(f'"{ref}"' for ref in refs) + "]"


def write_revision(
    modelo_dir: Path,
    revision: str,
    *,
    valid_from: str,
    valid_to: str | None,
    source_refs: list[str] | None = None,
    legal_refs: list[str] | None = None,
    predecessor: str | None = None,
    deadline_source_refs: list[str] | None = None,
    deadline_legal_refs: list[str] | None = None,
    casilla_source_refs: list[str] | None = None,
    formula_source_refs: list[str] | None = None,
) -> None:
    """Write one authored revision; only what it states is in its files, the rest inherits."""
    root = modelo_dir / "revisions" / revision
    root.mkdir(parents=True)
    first, last = int(valid_from[:4]), int((valid_to or valid_from)[:4])
    years = ", ".join(str(year) for year in range(first, last + 1))
    lines = [f'[revisions."{revision}"]', f"valid_from = {valid_from}"]
    if valid_to is not None:
        lines.append(f"valid_to = {valid_to}")
    lines.append(f'period_selector = {{ years = [{years}], periods = ["0A"] }}')
    lines.append(f"legal_refs = {_listed(legal_refs or [_LEGAL_REF])}")
    lines.append(f"source_refs = {_listed(source_refs or ['aeat-manual'])}")
    if predecessor is not None:
        lines.append(f'predecessor = "{predecessor}"')
    (root / "revision.toml").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    sections: dict[str, str] = {}
    if casilla_source_refs is not None:
        sections["casillas"] = (
            f'[[revisions."{revision}".casillas]]\nid = "0001"\nnumber = "1"\nsection = ["liquidacion"]\n'
            f'data_type = "money"\ncontinuidad_id = "linaje-1"\nlegal_refs = ["{_LEGAL_REF}"]\n'
            f"source_refs = {_listed(casilla_source_refs)}\n"
        )
    if formula_source_refs is not None:
        sections["formulas"] = (
            f'[[revisions."{revision}".formulas]]\nid = "modelo-999-a"\ntarget_casilla_id = "0001"\n'
            f'expression = {{ literal = "0" }}\nlegal_refs = ["{_LEGAL_REF}"]\n'
            f"source_refs = {_listed(formula_source_refs)}\n"
        )
    if deadline_source_refs is not None or deadline_legal_refs is not None:
        sections["deadline_windows"] = (
            f'[[revisions."{revision}".deadline_windows]]\nid = "modelo-999-{first}-0a"\nfiling_year = {first}\n'
            f'period = "{first} 0A"\nperiod_kind = "annual"\nopens_on = {first + 1}-01-01\n'
            f"closes_on = {first + 1}-01-31\nlegal_refs = {_listed(deadline_legal_refs or [_LEGAL_REF])}\n"
            f"source_refs = {_listed(deadline_source_refs or ['aeat-manual'])}\n"
        )
    for section, text in sections.items():
        (root / section).mkdir()
        (root / section / "0001-declarations.toml").write_text(text, encoding="utf-8", newline="\n")


def hydrate(modelo_dir: Path) -> ModeloDefinition:
    """Hydrate the written modelo through the real directory loader."""
    return load_modelo_directory(modelo_dir)


@pytest.fixture
def modelo_dir(tmp_path: Path) -> Path:
    path = tmp_path / "modelos" / "999"
    path.mkdir(parents=True)
    write_standard_manifest(path, "Planted")
    return path


class TestOneToothPerRole:
    """Each role is planted on its own and must classify as itself."""

    def test_a_governing_citation_outside_its_window_is_flagged(self, tmp_path: Path, modelo_dir: Path) -> None:
        catalogues = build_catalogue(tmp_path / "legal", {"planted-base-order": (_jan_1(Y2), None)})
        write_revision(
            modelo_dir, str(Y1), valid_from=_jan_1(Y1), valid_to=_dec_31(Y1), source_refs=["planted-base-order"]
        )
        findings, revisions, citations = scan([hydrate(modelo_dir)], catalogues)
        assert revisions == 1
        assert citations == 1
        assert [f["role"] for f in findings] == ["governing_non_overlap"]
        assert findings[0]["source"] == "planted-base-order"
        assert findings[0]["cited_in"] == ["revision#source_refs"]

    def test_an_evolution_record_citing_the_prior_design_is_not_a_defect(self) -> None:
        assert classify(["casilla_continuidad_evolutions#source_refs"]) == "evolution_origin"
        assert classify(["identifier_evolutions#source_refs"]) == "evolution_origin"

    def test_the_families_a_role_names_are_families_of_the_hydrated_revision(self) -> None:
        # A citation's role is read from the revision attribute that holds it, so
        # every family a role names must still be one the hydrated revision has.
        for family in (
            "casilla_continuidad_evolutions",
            "identifier_evolutions",
            "deadline_windows",
            "filing_schedules",
            "constructs",
            "application_links",
        ):
            assert family in ModeloRevision.model_fields

    def test_a_deadline_window_citing_the_filing_year_calendar_is_not_a_defect(
        self, tmp_path: Path, modelo_dir: Path
    ) -> None:
        catalogues = build_catalogue(tmp_path / "legal", {f"planted-calendario-{Y2}": (_jan_1(Y2), _dec_31(Y2))})
        write_revision(
            modelo_dir,
            str(Y1),
            valid_from=_jan_1(Y1),
            valid_to=_dec_31(Y1),
            deadline_source_refs=[f"planted-calendario-{Y2}"],
        )
        findings, _, _ = scan([hydrate(modelo_dir)], catalogues)
        assert [f["role"] for f in findings] == ["presentation_calendar"]
        assert findings[0]["cited_in"] == ["deadline_windows#source_refs"]


class TestGoverningWins:
    """A source cited in several roles is judged by the strictest one."""

    def test_a_source_cited_both_in_a_deadline_window_and_in_a_casilla_is_governing(
        self, tmp_path: Path, modelo_dir: Path
    ) -> None:
        catalogues = build_catalogue(tmp_path / "legal", {"planted-dr": (_jan_1(Y3), _dec_31(Y3))})
        write_revision(
            modelo_dir,
            str(Y2),
            valid_from=_jan_1(Y2),
            valid_to=_dec_31(Y2),
            deadline_source_refs=["planted-dr"],
            casilla_source_refs=["planted-dr"],
        )
        findings, _, _ = scan([hydrate(modelo_dir)], catalogues)
        assert [f["role"] for f in findings] == ["governing_non_overlap"]
        assert sorted(findings[0]["cited_in"]) == ["casillas#source_refs", "deadline_windows#source_refs"]

    def test_classify_prefers_governing_over_either_by_design_role(self) -> None:
        assert classify(["casilla_continuidad_evolutions#source_refs", "casillas#source_refs"]) == (
            "governing_non_overlap"
        )
        assert classify(["deadline_windows#source_refs", "revision#source_refs"]) == "governing_non_overlap"


class TestNoFalsePositives:
    """A window that covers its citing revision produces nothing."""

    def test_an_overlapping_window_is_silent(self, tmp_path: Path, modelo_dir: Path) -> None:
        catalogues = build_catalogue(tmp_path / "legal", {"planted-ok": (_jan_1(Y1), None)})
        write_revision(modelo_dir, str(Y1), valid_from=_jan_1(Y1), valid_to=_dec_31(Y1), source_refs=["planted-ok"])
        findings, _, citations = scan([hydrate(modelo_dir)], catalogues)
        assert citations == 1
        assert findings == []

    def test_an_undeclared_window_makes_no_claim_to_contradict(self, tmp_path: Path, modelo_dir: Path) -> None:
        catalogues = build_catalogue(tmp_path / "legal", {"planted-unwindowed": (None, None)})
        write_revision(
            modelo_dir, str(Y1), valid_from=_jan_1(Y1), valid_to=_dec_31(Y1), source_refs=["planted-unwindowed"]
        )
        findings, _, citations = scan([hydrate(modelo_dir)], catalogues)
        assert citations == 0, "a source with no window must not be counted as checked"
        assert findings == []

    def test_an_open_ended_revision_is_covered_by_an_open_ended_source(self, tmp_path: Path, modelo_dir: Path) -> None:
        catalogues = build_catalogue(tmp_path / "legal", {"planted-open": (_jan_1(Y1), None)})
        write_revision(modelo_dir, str(Y4), valid_from=_jan_1(Y4), valid_to=None, source_refs=["planted-open"])
        findings, _, _ = scan([hydrate(modelo_dir)], catalogues)
        assert findings == []


class TestInheritedCitations:
    """A revision authored as a delta still stands on what it inherits."""

    def test_a_citation_only_on_the_base_is_judged_against_the_inheriting_revisions_own_window(
        self, tmp_path: Path, modelo_dir: Path
    ) -> None:
        # The base cites a design that covers 2024 and the successor's files say
        # nothing: it inherits the casilla, and with it the citation.
        catalogues = build_catalogue(tmp_path / "legal", {f"planted-design-{Y3}": (_jan_1(Y3), _dec_31(Y3))})
        write_revision(
            modelo_dir,
            str(Y3),
            valid_from=_jan_1(Y3),
            valid_to=_dec_31(Y3),
            casilla_source_refs=[f"planted-design-{Y3}"],
        )
        write_revision(modelo_dir, str(Y4), valid_from=_jan_1(Y4), valid_to=_dec_31(Y4), predecessor=str(Y3))
        modelo = hydrate(modelo_dir)
        assert modelo.revisions[str(Y4)].casillas[0].source_refs == (f"planted-design-{Y3}",)

        findings, revisions, citations = scan([modelo], catalogues)

        assert revisions == 2
        assert citations == 2, "the base's own citation and the successor's inherited one are both measured"
        assert [(f["revision"], f["source"], f["role"]) for f in findings] == [
            (str(Y4), f"planted-design-{Y3}", "governing_non_overlap")
        ]
        assert findings[0]["revision_span"] == [_jan_1(Y4), _dec_31(Y4)]
        assert findings[0]["cited_in"] == ["casillas#source_refs"]

    def test_an_inherited_citation_whose_window_covers_the_inheritor_is_silent(
        self, tmp_path: Path, modelo_dir: Path
    ) -> None:
        catalogues = build_catalogue(tmp_path / "legal", {"planted-design": (_jan_1(Y3), None)})
        write_revision(
            modelo_dir, str(Y3), valid_from=_jan_1(Y3), valid_to=_dec_31(Y3), casilla_source_refs=["planted-design"]
        )
        write_revision(modelo_dir, str(Y4), valid_from=_jan_1(Y4), valid_to=_dec_31(Y4), predecessor=str(Y3))

        findings, revisions, citations = scan([hydrate(modelo_dir)], catalogues)

        assert (revisions, citations) == (2, 2)
        assert findings == []

    def test_one_physical_declaration_is_one_finding_per_revision_holding_it(
        self, tmp_path: Path, modelo_dir: Path
    ) -> None:
        # The same casilla row is inherited by two later editions. Each edition
        # has its own span to cover, so each is reported once; a source also
        # cited from a second family in one edition is still one finding there,
        # listing both families.
        catalogues = build_catalogue(tmp_path / "legal", {f"planted-design-{Y1}": (_jan_1(Y1), _dec_31(Y1))})
        write_revision(
            modelo_dir,
            str(Y1),
            valid_from=_jan_1(Y1),
            valid_to=_dec_31(Y1),
            casilla_source_refs=[f"planted-design-{Y1}"],
        )
        write_revision(
            modelo_dir,
            str(Y2),
            valid_from=_jan_1(Y2),
            valid_to=_dec_31(Y2),
            predecessor=str(Y1),
            formula_source_refs=[f"planted-design-{Y1}"],
        )
        write_revision(modelo_dir, str(Y3), valid_from=_jan_1(Y3), valid_to=_dec_31(Y3), predecessor=str(Y2))

        findings, _, _ = scan([hydrate(modelo_dir)], catalogues)

        assert [f["revision"] for f in findings] == [str(Y2), str(Y3)]
        by_revision = {f["revision"]: sorted(f["cited_in"]) for f in findings}
        assert by_revision[str(Y2)] == ["casillas#source_refs", "formulas#source_refs"]
        assert by_revision[str(Y3)] == ["casillas#source_refs", "formulas#source_refs"]

    def test_only_modelo_selects_by_modelo_id(self, tmp_path: Path, modelo_dir: Path) -> None:
        catalogues = build_catalogue(tmp_path / "legal", {"planted-base-order": (_jan_1(Y2), None)})
        write_revision(
            modelo_dir, str(Y1), valid_from=_jan_1(Y1), valid_to=_dec_31(Y1), source_refs=["planted-base-order"]
        )
        modelo = hydrate(modelo_dir)
        assert scan([modelo], catalogues, only_modelo="123")[1:] == (0, 0)
        assert len(scan([modelo], catalogues, only_modelo="999")[0]) == 1


class TestScreenLine:
    """The grammar other registry screens are read with."""

    def test_every_role_is_named_even_at_zero(self) -> None:
        line = screen_line([], revisions=7, citations=9)
        for role in ROLES:
            assert f"{role}=0" in line, "a role absent from the line reads as not measured"
        assert line.startswith("source_windows ")
        assert "revisions=7" in line
        assert "citations=9" in line

    def test_counts_are_per_role(self, tmp_path: Path, modelo_dir: Path) -> None:
        catalogues = build_catalogue(
            tmp_path / "legal",
            {
                "planted-governing": (_jan_1(Y3), None),
                "planted-calendar": (_jan_1(Y2), _dec_31(Y2)),
            },
        )
        write_revision(
            modelo_dir,
            str(Y1),
            valid_from=_jan_1(Y1),
            valid_to=_dec_31(Y1),
            source_refs=["planted-governing"],
            deadline_source_refs=["planted-calendar"],
        )
        findings, revisions, citations = scan([hydrate(modelo_dir)], catalogues)
        assert tally(findings) == {
            "governing_non_overlap": 1,
            "legal_window_non_overlap": 0,
            "superseded_alongside_current": 0,
            "evolution_origin": 0,
            "presentation_calendar": 1,
        }
        assert screen_line(findings, revisions, citations) == (
            "source_windows governing_non_overlap=1 legal_window_non_overlap=0 "
            "superseded_alongside_current=0 evolution_origin=0 presentation_calendar=1 "
            "revisions=1 citations=2"
        )


class TestSupersededAlongsideCurrent:
    """An earlier source cited beside the current one is a hand-off, not a defect."""

    def test_an_earlier_design_cited_beside_a_covering_sibling_is_reclassified(
        self, tmp_path: Path, modelo_dir: Path
    ) -> None:
        catalogues = build_catalogue(
            tmp_path / "legal",
            {f"aeat-dr-190-{Y3}": (_jan_1(Y3), _dec_31(Y3)), f"aeat-dr-190-{Y4}": (_jan_1(Y4), None)},
        )
        write_revision(
            modelo_dir,
            str(Y4),
            valid_from=_jan_1(Y4),
            valid_to=None,
            source_refs=[f"aeat-dr-190-{Y3}", f"aeat-dr-190-{Y4}"],
        )
        findings, _, _ = scan([hydrate(modelo_dir)], catalogues)
        assert [f["role"] for f in findings] == ["superseded_alongside_current"]

    def test_an_earlier_design_cited_alone_stays_a_governing_defect(self, tmp_path: Path, modelo_dir: Path) -> None:
        catalogues = build_catalogue(tmp_path / "legal", {f"aeat-dr-190-{Y3}": (_jan_1(Y3), _dec_31(Y3))})
        write_revision(modelo_dir, str(Y4), valid_from=_jan_1(Y4), valid_to=None, source_refs=[f"aeat-dr-190-{Y3}"])
        findings, _, _ = scan([hydrate(modelo_dir)], catalogues)
        assert [f["role"] for f in findings] == ["governing_non_overlap"], (
            "with no covering sibling the revision really does rest on a stale design"
        )

    def test_a_different_family_is_not_treated_as_a_sibling(self) -> None:
        assert family_stem(f"aeat-dr-190-{Y3}") == family_stem(f"aeat-dr-190-{Y4}")
        assert family_stem(f"aeat-dr-190-{Y3}") != family_stem(f"aeat-dr-193-{Y3}")
        assert not has_current_sibling(f"aeat-dr-190-{Y3}", {f"aeat-dr-193-{Y4}"})
        assert has_current_sibling(f"aeat-dr-190-{Y3}", {f"aeat-dr-190-{Y4}"})


class TestSupersessionHasADirection:
    """Only an EARLIER source beside a covering one is superseded."""

    def test_a_later_sibling_beside_covering_earlier_ones_is_not_supersession(
        self, tmp_path: Path, modelo_dir: Path
    ) -> None:
        # Modelo 280's deadline windows cite the calendario of each filing
        # year's PRESENTATION year, so the newest of the three sits outside the
        # revision's span on purpose. Reading that as a hand-off would hide a
        # whole class of forward citation behind a role that means the opposite.
        catalogues = build_catalogue(
            tmp_path / "legal",
            {
                f"aeat-calendario-contribuyente-{Y2}": (_jan_1(Y2), _dec_31(Y2)),
                f"aeat-calendario-contribuyente-{Y3}": (_jan_1(Y3), _dec_31(Y3)),
                f"aeat-calendario-contribuyente-{Y4}": (_jan_1(Y4), _dec_31(Y4)),
            },
        )
        write_revision(
            modelo_dir,
            str(Y1),
            valid_from=_jan_1(Y1),
            valid_to=_dec_31(Y3),
            deadline_source_refs=[
                f"aeat-calendario-contribuyente-{Y2}",
                f"aeat-calendario-contribuyente-{Y3}",
                f"aeat-calendario-contribuyente-{Y4}",
            ],
        )
        findings, _, _ = scan([hydrate(modelo_dir)], catalogues)
        assert [f["role"] for f in findings] == ["presentation_calendar"]
        assert findings[0]["source"] == f"aeat-calendario-contribuyente-{Y4}"

    def test_an_earlier_sibling_beside_a_covering_later_one_still_is(self) -> None:
        assert has_current_sibling(f"aeat-dr-190-{Y3}", {f"aeat-dr-190-{Y4}"})
        assert not has_current_sibling(f"aeat-dr-190-{Y4}", {f"aeat-dr-190-{Y3}"})

    def test_a_family_with_no_trailing_year_is_left_to_the_role_logic(self) -> None:
        assert trailing_year(f"aeat-dr-190-{Y3}") == Y3
        assert trailing_year("aeat-modelo-190-procedure") is None


class TestLegalWindowRole:
    """Legal references carry a period window too, and it was never checked."""

    _GOVERNS_Y3: Final = {"effective_from": _EFFECTIVE_AFTER_Y3, "governs_periods_from": _jan_1(Y3)}

    def test_a_legal_ref_governing_other_periods_is_flagged(self, tmp_path: Path, modelo_dir: Path) -> None:
        catalogues = build_catalogue(
            tmp_path / "legal",
            legal={"orden-planted:art-1": {**self._GOVERNS_Y3, "governs_periods_to": _dec_31(Y3)}},
        )
        write_revision(modelo_dir, str(Y4), valid_from=_jan_1(Y4), valid_to=None, legal_refs=["orden-planted:art-1"])
        findings, _, _ = scan([hydrate(modelo_dir)], catalogues)
        assert [f["role"] for f in findings] == ["legal_window_non_overlap"]
        assert findings[0]["source_window"] == [_jan_1(Y3), _dec_31(Y3)]

    def test_an_entry_declaring_only_effectiveness_makes_no_period_claim(
        self, tmp_path: Path, modelo_dir: Path
    ) -> None:
        # Most legal entries are in this state. effective_from says when the text
        # came into force; an orden published after the ejercicio it governs is
        # effective LATER than the periods it reaches.
        catalogues = build_catalogue(
            tmp_path / "legal", legal={"orden-planted:art-1": {"effective_from": _EFFECTIVE_AFTER_Y3}}
        )
        write_revision(
            modelo_dir, str(Y3), valid_from=_jan_1(Y3), valid_to=_dec_31(Y3), legal_refs=["orden-planted:art-1"]
        )
        findings, _, citations = scan([hydrate(modelo_dir)], catalogues)
        assert findings == []
        assert citations == 0, "an entry with no period claim is not even counted as checked"

    def test_a_legal_ref_whose_periods_cover_the_revision_is_silent(self, tmp_path: Path, modelo_dir: Path) -> None:
        catalogues = build_catalogue(
            tmp_path / "legal",
            legal={"orden-planted:art-1": {**self._GOVERNS_Y3, "governs_periods_to": _dec_31(Y3)}},
        )
        write_revision(
            modelo_dir, str(Y3), valid_from=_jan_1(Y3), valid_to=_dec_31(Y3), legal_refs=["orden-planted:art-1"]
        )
        findings, _, _ = scan([hydrate(modelo_dir)], catalogues)
        assert findings == []

    def test_a_legal_role_is_never_reclassified_as_a_source_role(self, tmp_path: Path, modelo_dir: Path) -> None:
        # The superseded/evolution/calendar roles describe SOURCE citations; a
        # legal reference outside its period window is its own finding, whichever
        # family cites it.
        catalogues = build_catalogue(
            tmp_path / "legal",
            legal={"orden-planted:art-1": {**self._GOVERNS_Y3, "governs_periods_to": _dec_31(Y3)}},
        )
        write_revision(
            modelo_dir,
            str(Y4),
            valid_from=_jan_1(Y4),
            valid_to=_dec_31(Y4),
            deadline_legal_refs=["orden-planted:art-1"],
        )
        findings, _, _ = scan([hydrate(modelo_dir)], catalogues)
        assert [f["role"] for f in findings] == ["legal_window_non_overlap"]

    def test_the_governed_window_comes_from_the_hydrated_catalogue_entry(self, tmp_path: Path) -> None:
        catalogues = build_catalogue(tmp_path / "legal", legal={"orden-planted:art-1": {**self._GOVERNS_Y3}})
        entry = catalogues.legal["orden-planted:art-1"]
        assert (entry.governs_periods_from, entry.governs_periods_to) == (date(Y3, 1, 1), None)


class TestConstructsNeedCalendarCorroboration:
    """A construct is an aggregate, not a filing calendar."""

    def test_a_construct_citing_a_source_no_deadline_window_cites_is_governing(self) -> None:
        # Modelo 131's 2024 and 2025 editions name a Sede help page only from
        # constructs. Treating constructs as calendar evidence classified the SAME
        # source two different ways on two editions of one modelo, depending on
        # which other families happened to cite it.
        assert classify(["constructs#source_refs"], calendar_evidence=False) == "governing_non_overlap"

    def test_a_construct_citing_what_a_deadline_window_also_cites_is_calendar(self) -> None:
        assert (
            classify(["deadline_windows#source_refs", "constructs#source_refs"], calendar_evidence=True)
            == "presentation_calendar"
        ), "the construct references the deadline window's own evidence"
