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

The registry trees here are constructed. A screen only reachable through the
live corpus cannot be handed a planted defect, and the live corpus changes under
a test that asserts counts against it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.registry.analysis.source_window_citations import (
    ROLES,
    classify,
    family_stem,
    has_current_sibling,
    scan,
    screen_line,
    tally,
    trailing_year,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def build_catalogue(legal: Path, entries: dict[str, tuple[str | None, str | None]]) -> None:
    """Write one legal catalogue declaring each source's window."""
    legal.mkdir(parents=True, exist_ok=True)
    blocks = []
    for source_id, (applies_from, applies_to) in entries.items():
        lines = [f'[sources."{source_id}"]', 'evidence_tier = "layout_authority"']
        if applies_from:
            lines.append(f"applies_from = {applies_from}")
        if applies_to:
            lines.append(f"applies_to = {applies_to}")
        blocks.append("\n".join(lines))
    (legal / "planted.toml").write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def build_revision(
    modelos: Path,
    *,
    modelo: str,
    revision: str,
    valid_from: str,
    valid_to: str | None,
    citations: dict[str, str],
) -> None:
    """Write one revision citing each source from the file path given."""
    root = modelos / modelo / "revisions" / revision
    root.mkdir(parents=True, exist_ok=True)
    body = [f'[revisions."{revision}"]', f"valid_from = {valid_from}"]
    if valid_to:
        body.append(f"valid_to = {valid_to}")
    (root / "revision.toml").write_text("\n".join(body) + "\n", encoding="utf-8")
    by_file: dict[str, list[str]] = {}
    for source_id, relative in citations.items():
        by_file.setdefault(relative, []).append(source_id)
    for relative, source_ids in by_file.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        listed = ", ".join(f'"{source_id}"' for source_id in source_ids)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(existing + f"source_refs = [{listed}]\n", encoding="utf-8")


@pytest.fixture
def tree(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "legal", tmp_path / "modelos"


class TestOneToothPerRole:
    """Each role is planted on its own and must classify as itself."""

    def test_a_governing_citation_outside_its_window_is_flagged(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-base-order": ("2023-01-01", None)})
        build_revision(
            modelos,
            modelo="999",
            revision="2022",
            valid_from="2022-01-01",
            valid_to="2022-12-31",
            citations={"planted-base-order": "revision.toml"},
        )
        findings, revisions, citations = scan(legal, modelos)
        assert revisions == 1
        assert citations == 1
        assert [f["role"] for f in findings] == ["governing_non_overlap"]
        assert findings[0]["source"] == "planted-base-order"

    def test_an_evolution_record_citing_the_prior_design_is_not_a_defect(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-dr-2022": ("2022-01-01", "2022-12-31")})
        build_revision(
            modelos,
            modelo="999",
            revision="2023",
            valid_from="2023-01-01",
            valid_to="2023-12-31",
            citations={"planted-dr-2022": "casilla_continuidad_evolutions/0001-carried.toml"},
        )
        findings, _, _ = scan(legal, modelos)
        assert [f["role"] for f in findings] == ["evolution_origin"]

    def test_a_deadline_window_citing_the_filing_year_calendar_is_not_a_defect(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-calendario-2023": ("2023-01-01", "2023-12-31")})
        build_revision(
            modelos,
            modelo="999",
            revision="2022",
            valid_from="2022-01-01",
            valid_to="2022-12-31",
            citations={"planted-calendario-2023": "deadline_windows/0001-windows.toml"},
        )
        findings, _, _ = scan(legal, modelos)
        assert [f["role"] for f in findings] == ["presentation_calendar"]


class TestGoverningWins:
    """A source cited in several roles is judged by the strictest one."""

    def test_a_source_cited_both_in_an_evolution_and_in_a_casilla_is_governing(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-dr": ("2024-01-01", "2024-12-31")})
        root = modelos / "999" / "revisions" / "2023"
        build_revision(
            modelos,
            modelo="999",
            revision="2023",
            valid_from="2023-01-01",
            valid_to="2023-12-31",
            citations={"planted-dr": "casilla_continuidad_evolutions/0001-carried.toml"},
        )
        (root / "casillas").mkdir(parents=True, exist_ok=True)
        (root / "casillas" / "c01.toml").write_text('source_refs = ["planted-dr"]\n', encoding="utf-8")
        findings, _, _ = scan(legal, modelos)
        assert [f["role"] for f in findings] == ["governing_non_overlap"]

    def test_classify_prefers_governing_over_either_by_design_role(self) -> None:
        assert classify(["casilla_continuidad_evolutions/x.toml", "casillas/c01.toml"]) == ("governing_non_overlap")
        assert classify(["deadline_windows/x.toml", "revision.toml"]) == "governing_non_overlap"


class TestNoFalsePositives:
    """A window that covers its citing revision produces nothing."""

    def test_an_overlapping_window_is_silent(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-ok": ("2022-01-01", None)})
        build_revision(
            modelos,
            modelo="999",
            revision="2022",
            valid_from="2022-01-01",
            valid_to="2022-12-31",
            citations={"planted-ok": "revision.toml"},
        )
        findings, _, citations = scan(legal, modelos)
        assert citations == 1
        assert findings == []

    def test_an_undeclared_window_makes_no_claim_to_contradict(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-unwindowed": (None, None)})
        build_revision(
            modelos,
            modelo="999",
            revision="2022",
            valid_from="2022-01-01",
            valid_to="2022-12-31",
            citations={"planted-unwindowed": "revision.toml"},
        )
        findings, _, citations = scan(legal, modelos)
        assert citations == 0, "a source with no window must not be counted as checked"
        assert findings == []

    def test_an_open_ended_revision_is_covered_by_an_open_ended_source(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-open": ("2020-01-01", None)})
        build_revision(
            modelos,
            modelo="999",
            revision="2025-y-siguientes",
            valid_from="2025-01-01",
            valid_to=None,
            citations={"planted-open": "revision.toml"},
        )
        findings, _, _ = scan(legal, modelos)
        assert findings == []


class TestScreenLine:
    """The grammar other registry screens are read with."""

    def test_every_role_is_named_even_at_zero(self) -> None:
        line = screen_line([], revisions=7, citations=9)
        for role in ROLES:
            assert f"{role}=0" in line, "a role absent from the line reads as not measured"
        assert line.startswith("source_windows ")
        assert "revisions=7" in line
        assert "citations=9" in line

    def test_counts_are_per_role(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_catalogue(
            legal,
            {
                "planted-governing": ("2024-01-01", None),
                "planted-evolution": ("2021-01-01", "2021-12-31"),
                "planted-calendar": ("2023-01-01", "2023-12-31"),
            },
        )
        build_revision(
            modelos,
            modelo="999",
            revision="2022",
            valid_from="2022-01-01",
            valid_to="2022-12-31",
            citations={
                "planted-governing": "revision.toml",
                "planted-evolution": "identifier_evolutions/0001-x.toml",
                "planted-calendar": "filing_schedules/0001-x.toml",
            },
        )
        findings, revisions, citations = scan(legal, modelos)
        assert tally(findings) == {
            "governing_non_overlap": 1,
            "legal_window_non_overlap": 0,
            "superseded_alongside_current": 0,
            "evolution_origin": 1,
            "presentation_calendar": 1,
        }
        assert screen_line(findings, revisions, citations) == (
            "source_windows governing_non_overlap=1 legal_window_non_overlap=0 "
            "superseded_alongside_current=0 evolution_origin=1 presentation_calendar=1 "
            "revisions=1 citations=3"
        )


class TestSupersededAlongsideCurrent:
    """An earlier source cited beside the current one is a hand-off, not a defect."""

    def test_an_earlier_design_cited_beside_a_covering_sibling_is_reclassified(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_catalogue(
            legal,
            {
                "aeat-dr-190-2024": ("2024-01-01", "2024-12-31"),
                "aeat-dr-190-2025": ("2025-01-01", None),
            },
        )
        build_revision(
            modelos,
            modelo="190",
            revision="2025-y-siguientes",
            valid_from="2025-01-01",
            valid_to=None,
            citations={
                "aeat-dr-190-2024": "revision.toml",
                "aeat-dr-190-2025": "revision.toml",
            },
        )
        findings, _, _ = scan(legal, modelos)
        assert [f["role"] for f in findings] == ["superseded_alongside_current"]

    def test_an_earlier_design_cited_alone_stays_a_governing_defect(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"aeat-dr-190-2024": ("2024-01-01", "2024-12-31")})
        build_revision(
            modelos,
            modelo="190",
            revision="2025-y-siguientes",
            valid_from="2025-01-01",
            valid_to=None,
            citations={"aeat-dr-190-2024": "revision.toml"},
        )
        findings, _, _ = scan(legal, modelos)
        assert [f["role"] for f in findings] == ["governing_non_overlap"], (
            "with no covering sibling the revision really does rest on a stale design"
        )

    def test_a_different_family_is_not_treated_as_a_sibling(self) -> None:
        assert family_stem("aeat-dr-190-2024") == family_stem("aeat-dr-190-2025")
        assert family_stem("aeat-dr-190-2024") != family_stem("aeat-dr-193-2024")
        assert not has_current_sibling("aeat-dr-190-2024", {"aeat-dr-193-2025"})
        assert has_current_sibling("aeat-dr-190-2024", {"aeat-dr-190-2025"})


class TestSupersessionHasADirection:
    """Only an EARLIER source beside a covering one is superseded."""

    def test_a_later_sibling_beside_covering_earlier_ones_is_not_supersession(self, tree: tuple[Path, Path]) -> None:
        # Modelo 280's deadline windows cite the calendario of each filing
        # year's PRESENTATION year, so the newest of the three sits outside the
        # revision's span on purpose. Reading that as a hand-off would hide a
        # whole class of forward citation behind a role that means the opposite.
        legal, modelos = tree
        build_catalogue(
            legal,
            {
                "aeat-calendario-contribuyente-2023": ("2023-01-01", "2023-12-31"),
                "aeat-calendario-contribuyente-2024": ("2024-01-01", "2024-12-31"),
                "aeat-calendario-contribuyente-2025": ("2025-01-01", "2025-12-31"),
            },
        )
        build_revision(
            modelos,
            modelo="280",
            revision="2022-2024",
            valid_from="2022-01-01",
            valid_to="2024-12-31",
            citations={
                "aeat-calendario-contribuyente-2023": "deadline_windows/0001-w.toml",
                "aeat-calendario-contribuyente-2024": "deadline_windows/0001-w.toml",
                "aeat-calendario-contribuyente-2025": "deadline_windows/0001-w.toml",
            },
        )
        findings, _, _ = scan(legal, modelos)
        assert [f["role"] for f in findings] == ["presentation_calendar"]
        assert findings[0]["source"] == "aeat-calendario-contribuyente-2025"

    def test_an_earlier_sibling_beside_a_covering_later_one_still_is(self) -> None:
        assert has_current_sibling("aeat-dr-190-2024", {"aeat-dr-190-2025"})
        assert not has_current_sibling("aeat-dr-190-2025", {"aeat-dr-190-2024"})

    def test_a_family_with_no_trailing_year_is_left_to_the_role_logic(self) -> None:
        assert trailing_year("aeat-dr-190-2024") == 2024
        assert trailing_year("aeat-modelo-190-procedure") is None


def build_legal(legal: Path, entries: dict[str, dict[str, str]]) -> None:
    """Write one legal catalogue; each entry declares whichever axis it names."""
    legal.mkdir(parents=True, exist_ok=True)
    blocks = []
    for ref_id, fields in entries.items():
        lines = [f'[legal."{ref_id}"]', 'evidence_tier = "legal_authority"']
        lines += [f"{key} = {value}" for key, value in fields.items()]
        blocks.append("\n".join(lines))
    (legal / "planted-legal.toml").write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


class TestLegalWindowRole:
    """Legal references carry a period window too, and it was never checked."""

    def test_a_legal_ref_governing_other_periods_is_flagged(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_legal(
            legal, {"orden-planted:art-1": {"governs_periods_from": "2024-01-01", "governs_periods_to": "2024-12-31"}}
        )
        build_revision(
            modelos,
            modelo="200",
            revision="2025-y-siguientes",
            valid_from="2025-01-01",
            valid_to=None,
            citations={"orden-planted:art-1": "revision.toml"},
        )
        findings, _, _ = scan(legal, modelos)
        assert [f["role"] for f in findings] == ["legal_window_non_overlap"]

    def test_an_entry_declaring_only_effectiveness_makes_no_period_claim(self, tree: tuple[Path, Path]) -> None:
        # 719 of 724 legal entries are in this state. effective_from says when the
        # text came into force; an orden published after the ejercicio it governs
        # is effective LATER than the periods it reaches. Reading effectiveness as
        # a period window produced 59 findings, none of them a defect.
        legal, modelos = tree
        build_legal(legal, {"orden-planted:art-1": {"effective_from": "2025-07-01"}})
        build_revision(
            modelos,
            modelo="200",
            revision="2024",
            valid_from="2024-01-01",
            valid_to="2024-12-31",
            citations={"orden-planted:art-1": "revision.toml"},
        )
        findings, _, citations = scan(legal, modelos)
        assert findings == []
        assert citations == 0, "an entry with no period claim is not even counted as checked"

    def test_a_legal_ref_whose_periods_cover_the_revision_is_silent(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_legal(
            legal, {"orden-planted:art-1": {"governs_periods_from": "2024-01-01", "governs_periods_to": "2024-12-31"}}
        )
        build_revision(
            modelos,
            modelo="200",
            revision="2024",
            valid_from="2024-01-01",
            valid_to="2024-12-31",
            citations={"orden-planted:art-1": "revision.toml"},
        )
        findings, _, _ = scan(legal, modelos)
        assert findings == []

    def test_a_legal_role_is_never_reclassified_as_a_source_role(self, tree: tuple[Path, Path]) -> None:
        # The superseded/evolution/calendar roles describe SOURCE citations; a
        # legal reference outside its period window is its own finding.
        legal, modelos = tree
        build_legal(
            legal, {"orden-planted:art-1": {"governs_periods_from": "2024-01-01", "governs_periods_to": "2024-12-31"}}
        )
        build_revision(
            modelos,
            modelo="200",
            revision="2025",
            valid_from="2025-01-01",
            valid_to="2025-12-31",
            citations={"orden-planted:art-1": "deadline_windows/0001-w.toml"},
        )
        findings, _, _ = scan(legal, modelos)
        assert [f["role"] for f in findings] == ["legal_window_non_overlap"]


class TestConstructsNeedCalendarCorroboration:
    """A construct is an aggregate, not a filing calendar."""

    def test_a_construct_citing_a_source_no_deadline_window_cites_is_governing(self, tree: tuple[Path, Path]) -> None:
        # Modelo 131's 2024 and 2025 editions name a Sede help page only from
        # constructs. Treating constructs as calendar evidence classified the SAME
        # source two different ways on two editions of one modelo, depending on
        # which other files happened to cite it.
        legal, modelos = tree
        build_catalogue(legal, {"planted-help-page": ("2026-01-01", None)})
        build_revision(
            modelos,
            modelo="131",
            revision="2024",
            valid_from="2024-01-01",
            valid_to="2024-12-31",
            citations={"planted-help-page": "constructs/0001-constructs.toml"},
        )
        findings, _, _ = scan(legal, modelos)
        assert [f["role"] for f in findings] == ["governing_non_overlap"]

    def test_a_construct_citing_what_a_deadline_window_also_cites_is_calendar(self, tree: tuple[Path, Path]) -> None:
        legal, modelos = tree
        build_catalogue(legal, {"planted-calendario-2023": ("2023-01-01", "2023-12-31")})
        root = modelos / "322" / "revisions" / "2022"
        build_revision(
            modelos,
            modelo="322",
            revision="2022",
            valid_from="2022-01-01",
            valid_to="2022-12-31",
            citations={"planted-calendario-2023": "deadline_windows/0001-windows.toml"},
        )
        (root / "constructs").mkdir(parents=True, exist_ok=True)
        (root / "constructs" / "0001-constructs.toml").write_text(
            'source_refs = ["planted-calendario-2023"]\n', encoding="utf-8"
        )
        findings, _, _ = scan(legal, modelos)
        assert [f["role"] for f in findings] == ["presentation_calendar"], (
            "the construct references the deadline window's own evidence"
        )

    def test_the_corroboration_is_per_source_not_per_revision(self, tree: tuple[Path, Path]) -> None:
        # A revision having SOME deadline window must not launder an unrelated
        # source cited only from constructs.
        legal, modelos = tree
        build_catalogue(
            legal,
            {
                "planted-calendario-2023": ("2023-01-01", "2023-12-31"),
                "planted-help-page": ("2026-01-01", None),
            },
        )
        root = modelos / "131" / "revisions" / "2022"
        build_revision(
            modelos,
            modelo="131",
            revision="2022",
            valid_from="2022-01-01",
            valid_to="2022-12-31",
            citations={"planted-calendario-2023": "deadline_windows/0001-windows.toml"},
        )
        (root / "constructs").mkdir(parents=True, exist_ok=True)
        (root / "constructs" / "0001-constructs.toml").write_text(
            'source_refs = ["planted-help-page"]\n', encoding="utf-8"
        )
        findings, _, _ = scan(legal, modelos)
        roles = {f["source"]: f["role"] for f in findings}
        assert roles["planted-calendario-2023"] == "presentation_calendar"
        assert roles["planted-help-page"] == "governing_non_overlap"
